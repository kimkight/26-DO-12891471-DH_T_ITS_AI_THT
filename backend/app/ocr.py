"""Local OCR: OpenCV preprocessing, then Tesseract word-level recognition.

Governing requirements: FR-1 (extract the five fields from label artwork),
NFR-1 (about 5 seconds per label, so elapsed time is measured and returned),
NFR-3 (no outbound network call on the default path), FR-9 (an undecodable
image and an image with no text are distinct failures). Decision reference:
D-4, ADR 0003.

**Orientation.** The first real-artwork test submitted a photograph of a bottle
taken sideways, and the engine found none of the five fields. Two separate
things were wrong and both are handled here. A phone writes the orientation it
was held at into the EXIF tag rather than turning the pixels, and
``cv2.imdecode`` ignores that tag entirely, so the array the pipeline saw was
sideways even though every viewer shows the photograph upright. And a
photograph genuinely taken sideways carries no tag at all. ``decode`` applies
the EXIF transform through Pillow before OpenCV sees a pixel, and
``detect_orientation`` asks Tesseract which cardinal quarter-turn brings the
text upright. What was chosen, and on what evidence, is carried on the result
and reported in the response, because an agent whose photograph was turned
should be told it was turned.

The EXIF tag is a claim rather than a fact, so the quarter-turn check runs
whether or not a tag was found and applied. A tag survives an edit that turned
the pixels, and a wrong transpose has to be caught by the same net that catches
an untagged sideways photograph. All three figures go out on the response: the
tag that was found, the transpose that was applied, and whatever further turn
the check chose.

**Two reads, and the better one wins (v1.0.1).** Preprocessing is not free of
risk. Adaptive thresholding earns its keep on the printed artwork the sample
set is built from, and destroys a soft-contrast photograph: measured over the
twelve-label set degraded to a photograph-like fixture, the thresholded image
read zero words where the plain grayscale read all sixty-two, and Tesseract's
orientation detection was right in 0 of 48 cases on the thresholded image
against 44 of 48 on the grayscale. Two consequences, both here. The orientation
call is made on the grayscale. And ``extract_text`` reads the preprocessed
image, and, unless that read comes back confident, reads the plain
EXIF-corrected grayscale too and keeps whichever scored higher. Which one won
is on the result, for the same reason the rotation is: an agent cannot see it
otherwise. The measurement is in docs/07_TEST_STRATEGY.md section 2.

**A picture lifted out of a PDF is turned the way the page places it, and
Tesseract is not asked (ADR 0025).** The orientation call above exists for a
photograph, which carries no statement of which way up it is beyond an EXIF
tag that may lie. A picture inside a PDF carries one: the placement matrix
the page draws it with, composed with the page's own rotation, says exactly
how the picture appears to anyone who opens the file. ``extract_text`` takes
that turn as ``placement_rotation``, applies it, reports the method as
``placement`` and makes no orientation call at all. Measured on the two
filings in samples/real/, every one of the eight pictures is placed upright,
the OSD call was wrong or unable to answer on five of the six panels it was
asked about, and the reads it cost bought no turn on any of them. Where the
placement is not a quarter-turn, a skew or a mirror, the caller passes None
and the photograph path above runs unchanged. And where the reading taken
at the placement turn shows only type set at a quarter-turn and nothing
upright, which is a side strip whose type runs along it, affixed the way it
is, Tesseract is asked after all and the picture is read again the way it
answers; ``_reads_as_sideways`` is the gate and carries the evidence.

**A colour source that read nothing twice is not read a third time (ADR
0026).** On a coloured image the plain grayscale is read to compete with a
confident read of a transformed image that may have lost an ink class. When
the colour arm and the preprocessed arm have both returned no words at all
there is no such read to compete with, and the grayscale cannot carry more
contrast than the best of the three channels Tesseract has already
thresholded; see ``_needs_the_plain_read``. The rule is written on "nothing
came back", never on a confidence, because a low confidence is a read that
has to be compared and a read of nothing is not.

Nothing in this module opens a socket. ``pytesseract`` runs the Tesseract binary
that ships in the container image, and OpenCV works on the decoded array in
memory. That is what makes the default path work with egress blocked, which is
the environment Marcus Williams describes.

Nothing is kept (NFR-6). The image is decoded from the request bytes into a
numpy array and released with the request. ``pytesseract`` hands the engine
each image through a temporary file that it writes to the temporary directory
and deletes, with the engine's output file, before the call returns; nothing
outlives the request. The promise NFR-6 makes is about retention, and
docs/06_SECURITY_AND_COMPLIANCE.md section 3.2 says where the bytes are while a
request runs. Until v1.3.0 this docstring said nothing was written to disk,
which was not true of any request the service accepted (code review finding 4).

``OMP_THREAD_LIMIT`` is pinned below. See the comment there: it is what lets
either path call this from a worker thread at all.
"""

from __future__ import annotations

import io
import os
import time
from dataclasses import dataclass, field
from typing import Literal

# Tesseract is built against OpenMP, and its OpenMP runtime deadlocks when the
# binary is invoked from a thread other than the process's main thread. Until
# v1.3.0 the single-label path never hit this, because `POST /api/verify` ran
# extract_text on the event loop thread; that was not a safety property, it
# was the loop being blocked for the length of every request, so that
# `/api/health` could not answer while a label was being read (code review
# finding 8). Both paths now run it in a worker thread: the batch path (FR-8,
# ADR 0006) in its own pool and the single-label path behind a capacity
# limiter in `app.api`. Without this pin the Tesseract child process never
# exits and the request hangs rather than failing.
#
# One thread per invocation is also the right shape for the work rather than
# merely the safe one. ADR 0006 parallelizes across images, so letting each of
# those also fan out across cores would oversubscribe the CPU the pool is
# already sized to. Measured cost on a four-core runner: median 527 ms per
# label for the twelve-label sample set, against NFR-1's roughly 5 seconds.
#
# setdefault, not assignment, so an operator can still override it from the
# environment (NFR-11). It is set before pytesseract is imported because the
# value is read by the Tesseract child process when it is spawned.
os.environ.setdefault("OMP_THREAD_LIMIT", "1")

import cv2  # noqa: E402
import numpy as np  # noqa: E402
import pytesseract  # noqa: E402
from PIL import Image, ImageOps, UnidentifiedImageError  # noqa: E402
from pytesseract import Output  # noqa: E402

from app import timing  # noqa: E402
from app.config import settings  # noqa: E402

# The EXIF tag that records which way up the camera was held. Pillow exposes it
# by number rather than by name, and 1 means "already upright".
_EXIF_ORIENTATION_TAG = 0x0112

# The four quarter-turns. Anything else is a skew, which deskew handles.
CARDINAL_ROTATIONS = (0, 90, 180, 270)

# How Tesseract reports a hopeless orientation call. Both of the two misreads in
# the measurement recorded in ADR 0003 and A-15 came back below this, and every
# correct answer in that run came back above it. Above it OSD decides alone, and
# 46 of 48 is the record that earns it. Below it the verdict is not taken on
# trust: ``_second_opinion_on_180`` scores the chosen rotation against its
# opposite and keeps the better one. See docs/07_TEST_STRATEGY.md section 2.
LOW_ORIENTATION_CONFIDENCE = 1.0

# The band inside which two reads are treated as equally confident, in mean
# word confidence points.
#
# **Why a band is needed at all: mean word confidence is blind to omission.**
# It is the right signal for the comparison v1.0.1 introduced, where
# thresholding *garbles* text and the garbled words score low. It is the wrong
# signal on its own for the comparison this release introduces, where
# converting a colour label to grayscale *drops* an entire ink class. A word
# that was never read contributes no confidence, so the variant that lost two
# of the five required fields scores the same as the variant that kept them.
#
# Two measurements, and they agree. On the author's mezcal COLA artwork the
# colour image read 257 words at a mean of 89.1 and the grayscale read 106 at
# 89.9: the grayscale wins by 0.8 while losing "42% ALC BY VOL" outright. On
# the three-class fixture in tests/test_colour_arm.py the colour image reads 93
# words at 95.613 and the grayscale 87 at 95.609, a gap of 0.004 the same way
# round. In both cases the two reads are, on this signal, the same read.
#
# So: mean word confidence ranks, and only a tie on it is broken by how much
# text was recovered. One point is above both measured gaps and far below every
# gap the v1.0.1 comparison actually has to settle. Re-measured over the
# twelve-label sample set on 2026-08-30: on the clean renderings the comparison
# never runs at all, because the preprocessed read clears
# PREPROCESS_SHORT_CIRCUIT_CONFIDENCE on all twelve and nothing else is read;
# on the same set degraded to a photograph-like fixture, where both arms are
# read every time, the two are never closer than 29.0 points apart. So the band
# fires on no case in that set, and nothing v1.0.1 decided is decided
# differently here.
EQUAL_CONFIDENCE_BAND = 1.0

# The share of the working resolution the 180-degree check scores its two
# candidates at (OQ-27, closed 2026-09-01).
#
# **The check does not read the label; it picks which way up to read it.** Its
# two Tesseract passes exist to separate one number from another, and on the
# author's mezcal artwork those numbers were 91.8 upright against 32.1 upside
# down. Fifty points and more does not need every pixel, and the passes were
# costing the most expensive thing this pipeline does, twice, at full size.
#
# The scale is measured rather than chosen, over the set ADR 0003 was decided
# on: the twelve sample labels at all four cardinal rotations, forty-eight
# cases, with the check forced to run on every one of them. Run twice, on the
# clean renderings and on the same set degraded into something shaped like a
# phone photograph, which is the input the check exists for. The degraded run:
#
# ======  ==========  =========  ================
# scale   long edge   right      both candidates
# ======  ==========  =========  ================
#  1.00      1600 px  48 of 48           1504 ms
#  0.60       960 px  48 of 48            957 ms
#  0.50       800 px  48 of 48            781 ms
#  0.40       640 px  48 of 48            649 ms
#  0.30       480 px  44 of 48            381 ms
#  0.25       400 px  48 of 48            312 ms
# ======  ==========  =========  ================
#
# The clean run is 48 of 48 at every scale, which is why the degraded set is the
# one that decides: an easy input cannot separate a good scale from a bad one.
#
# Half, and not lower, for two reasons. It is right in as many cases as full
# resolution is, on both sets, and on the one real filing measured it keeps the
# candidates 37 points apart. And the first failure is one step below it, at
# 0.30, where the score puts the four beer-label cases 1.9 points the wrong way
# round. That 0.25 is right in 48 of 48 again is not a reason to go lower: a
# rule whose accuracy is not monotone in its own parameter is a rule that has
# started reading noise, and OQ-27's single-image table has 0.25 answering
# backwards on the author's own artwork. So the scale sits one measured step
# above the first failure rather than at the last passing value.
#
# Nothing about the text an agent reads changes. The winning rotation is applied
# to the full-resolution image and the pipeline reads that, exactly as before.
ORIENTATION_CHECK_SCALE = 0.5

# What counts as colour a grayscale conversion would discard. Both figures are
# measured; the table is in ``has_colour``.
_COLOUR_CHROMA = 32
_COLOUR_PIXEL_SHARE = 0.01

# When the preprocessed read scores at least this, the plain read is not run.
#
# Measured over the twelve-label sample set on 2026-08-29. Every label where
# preprocessing was the right choice scored 95.1 or better; the one label where
# it was not (05-spirits-no-warning, a sparse label) scored 41.4 against the
# plain read's 95.0. Over the same set degraded to a photograph-like fixture,
# the highest the preprocessed read reached while still losing to the plain one
# was 68.4. 85 sits above every measured case where preprocessing lost and ten
# points below every case where it won, which is as much margin as the two
# clusters allow. It is not a quality bar for the answer: a read scoring below
# it is not discarded, it is compared.
#
# **What it does and does not fire on, measured on the two real filings in
# samples/real/ on 2026-09-08 (session container, Tesseract 5.3.4).** The
# question was whether the second pass could be skipped on a panel whose first
# pass had already read confidently, and the answer is that it already is, and
# that on the bourbon filing no first pass ever does. First pass is the colour
# arm on a coloured panel and the preprocessed arm on a monochrome one:
#
# =========================  ========  ===============  =====================  ========
# panel                      source    first pass       second pass            winner
# =========================  ========  ===============  =====================  ========
# mezcal, 1750 x 1150        colour    colour 89.6      not run                colour
# bourbon, 1950 x 862        colour    colour 0.0       pre 0.0, plain 0.0     none read
# bourbon, 1350 x 300        mono      pre 44.7         plain 89.9             plain
# bourbon, 1103 x 340        colour    colour 41.2      pre 29.0, plain 36.6   colour
# bourbon, 1050 x 309        mono      pre 56.3         plain 86.8             plain
# bourbon, 187 x 1697        mono      pre 67.0         plain 23.6             preprocessed
# =========================  ========  ===============  =====================  ========
#
# The mezcal's one panel clears the line on its first pass and costs one arm.
# On the bourbon the highest first pass is 67.0, one word on the strip, and the
# two panels that read well read well on the *second* pass: the plain arm is
# where the brand name and the government warning come from. So there is no
# second pass on that filing this rule could drop without changing the answer,
# and 11 of the 12 arm reads its 19 Tesseract reads contained are each doing
# the work v1.0.1 measured for. The twelfth was the plain arm on the 1950 by
# 862 panel, read after the colour arm and the preprocessed arm had both
# returned no words at all; ADR 0026 stops that one, on the evidence in
# ``_needs_the_plain_read``. The other 7 were orientation: one OSD call per
# panel and the two-read second opinion where OSD answered under the floor,
# and on a picture lifted out of a PDF the page's own placement now answers
# that question for nothing (ADR 0025). The same filings after both: the
# mezcal 1 read, the bourbon 11, with every winning arm and every score in the
# table unchanged. What bounds a document that carries more panels than these
# is `Settings.max_document_reads`, not this constant.
PREPROCESS_SHORT_CIRCUIT_CONFIDENCE = 85.0


# What separates the gutter between two printed panels from the space between
# two words. Two conditions, and a blank has to clear both to be read as a
# column boundary.
#
# **Why a column split is needed on top of Tesseract's own blocks.** Filed label
# artwork is one flat sheet carrying several panels side by side, and the
# author's mezcal COLA is three panels plus a strip of text set at 90 degrees
# between them. Grouping words by ``block_num`` already keeps that strip out of
# the panels either side of it, and it is not enough: on the same artwork
# Tesseract returns blocks spanning x 44 to 1526 of a 1600 pixel image, with the
# left panel's ``ORIGEN PROTEGIDA`` sitting inside the government warning
# printed on the right one. Splicing one panel's words into another panel's
# sentence is what made the statement read as altered when the label prints it
# correctly.
#
# **The first condition is a share of the image width.** A gutter is a fraction
# of the sheet, and the same artwork arrives at whatever resolution the filing
# was scanned at, so the figure has to scale with the image rather than be a
# pixel count. 2.5 percent is 40 pixels at the 1600 pixel working width
# ``resize_long_edge`` gives a landscape sheet, which is the width the three
# gutters on the author's artwork were measured at: 63, 86 and 70 pixels, or
# 3.94, 5.38 and 4.38 percent. The widest blank on that sheet that is not a
# gutter is 28 pixels, 1.75 percent, inside the vertical strip. So the condition
# separates the two clusters on this artwork with margin on both sides.
#
# **The second condition is the size of the type beside the blank, and a width
# share alone cannot do without it.** Sample label 05 sets ``LANTERN HILL``
# across the head of the label in 75 pixel display type, and the word space in
# it is 53 pixels, 4.97 percent of that label's width: wider, as a share, than
# two of the three real gutters. Nothing else on that sparse label prints at
# that x, so the blank survives the projection and a width rule alone cuts the
# brand name in half. It is not a gutter, and what says so is the type either
# side of it: 53 pixels is two thirds of one glyph.
#
# So a blank also has to be wider than the largest type touching it by
# ``COLUMN_GAP_TYPE_SIZES``. Measured over every blank of 8 pixels or more on
# the author's artwork and on the twelve sample labels, as a multiple of that
# type:
#
# ==============================================  ========  ==========
# blank                                            width     multiple
# ==============================================  ========  ==========
# mezcal, gutter left of the front panel                63        2.17
# mezcal, gutter right of the front panel               86        1.59
# mezcal, gutter left of the back panel                 70        3.33
# mezcal, inside the vertical strip                     28        0.93
# mezcal, four word spaces                               8   0.15-0.38
# sample 05, the word space in ``LANTERN HILL``         53        0.71
# ==============================================  ========  ==========
#
# 1.25 sits between 0.93 and 1.59, which is the whole of the gap between the two
# clusters. A blank wider than the type beside it is tall is not a word space in
# any typeface; a blank narrower than that is not a gutter on any sheet.
#
# **Type size here is the shorter side of the word's box, not its height.** A
# word set at 90 degrees comes back about one cap-height wide and one word long,
# so height measures its length there and width measures it on upright type. The
# shorter side is the cap height either way, which is what lets the strip on
# this artwork be measured by the same rule as the panels beside it.
COLUMN_GAP_WIDTH_SHARE = 0.025
COLUMN_GAP_TYPE_SIZES = 1.25


class UndecodableImageError(Exception):
    """The bytes submitted could not be decoded as an image (FR-9)."""


@dataclass(frozen=True)
class OcrLine:
    """One line of recognized text, with the evidence needed to rank it.

    ``height`` is the mean glyph box height of the words in the line, in pixels
    of the preprocessed image. It is the only signal available for telling a
    brand name from body text, because Tesseract reports geometry per word and
    reports nothing about typeface.

    ``column`` and ``block`` say which region of the sheet the line was set in:
    the column ``_columns`` cut the page into, and Tesseract's own block number
    inside it. A line never spans two of either (see ``_assemble_lines``), so
    the pair identifies one piece of the layout and is what the response uses to
    say which panel a field was read from. ``width`` is the mean glyph box width
    over the line's words, carried because it is the other half of the only
    signal that tells upright type from type set at 90 degrees; see
    ``sideways`` and ``app.parse``.

    All four default so that ``lines_from_text``, the plain-text path that has
    no image behind it, still builds a line record.
    """

    text: str
    confidence: float
    height: float
    top: int
    column: int = 0
    block: int = 0
    width: float = 0.0

    @property
    def sideways(self) -> bool:
        """Whether this line is type set at 90 degrees rather than upright.

        **The reported height of a rotated word is its length, not its type
        size.** Tesseract reads a vertical strip in place and reports the
        bounding box in page coordinates, so a word set sideways comes back
        about one cap-height wide and one word long. On the author's mezcal
        artwork that made the producer's tax identifier, printed in the gutter
        strip, the tallest text on the sheet at 81.5 pixels against a 43 pixel
        display line, which is how it came to be reported as the brand name. The
        box is not lying; it is answering a different question, and any ranking
        by type size has to know that before it uses the number.

        Wider than tall is the whole test, and it carries no threshold because
        the two cases are nowhere near each other. Measured on that artwork, over
        the mean word box of each line: the panels' own lines run from 0.05 to
        0.85 in height over width, and the four lines of the two vertical strips
        run 3.30, 3.59, 3.90 and 5.43.

        One line on that sheet lands between them, at 1.17, and it is a
        two-character misreading of a rule printed under the lot number. It is
        excluded as sideways and nothing is lost by that: the exclusion decides
        only which lines may compete on type size, and a garbled fragment is not
        a candidate for the brand name in either case. That is the shape of this
        rule's error, and it is the cheap direction to be wrong in.
        """
        return self.width > 0 and self.height > self.width


OrientationMethod = Literal[
    "osd",
    "osd_180_check",
    "osd_180_check_full_resolution",
    "unavailable",
    "disabled",
    "placement",
]


@dataclass(frozen=True)
class RotationScore:
    """What one candidate rotation scored when the image was actually read."""

    rotation_degrees: int
    confidence: float
    words: int


@dataclass(frozen=True)
class OrientationCheck:
    """The second opinion taken when OSD answered below the floor (FR-1, A-15).

    Reported in full rather than reduced to its outcome. A rotation that
    overrode Tesseract's own verdict is exactly the kind of decision an agent
    looking at a poor result has to be able to audit, and "we turned it 180
    degrees" says nothing about who decided that or on what evidence.

    ``candidates`` holds both scored rotations, always two: the one OSD chose
    and its 180-degree opposite. It is deliberately not four. See
    ``_second_opinion_on_180``.
    """

    osd_rotation_degrees: int
    osd_confidence: float
    floor: float
    candidates: tuple[RotationScore, ...]
    chosen_rotation_degrees: int
    overrode_osd: bool


@dataclass(frozen=True)
class Orientation:
    """How the image was turned upright before OCR, and on what evidence.

    Carried out to the response (FR-1, FR-10) rather than kept internal, because
    a photograph the tool silently turned and then read badly is indistinguishable
    to an agent from a photograph the tool simply read badly.

    All three of the things that could have turned the image are reported
    separately, because they can disagree and the disagreement is the
    interesting case. ``exif_orientation`` is the tag value found in the file,
    1 to 8, or null when the file carried none. ``exif_transposed`` says the tag
    was applied, which is every value but 1. ``rotation_degrees`` is the
    clockwise quarter-turn applied *after* that transform, which is Tesseract's
    own convention for the figure, and a non-zero value on a file that carried a
    tag means the tag was wrong about its own pixels.

    ``method`` says where the quarter-turn came from: ``osd`` when Tesseract's
    orientation and script detection answered and was taken at its word,
    ``osd_180_check`` when it answered below ``LOW_ORIENTATION_CONFIDENCE`` and
    the answer was put to the second opinion described in ``check``,
    ``osd_180_check_full_resolution`` when that second opinion read no words
    either way at the reduced scale and was taken again at full resolution
    before deciding (v1.3.0), ``unavailable`` when it could not answer (too
    little text to judge, or no ``osd`` training data installed),
    ``disabled`` when ``TTB_CORRECT_ORIENTATION`` is off, and ``placement``
    when the turn came from the document the picture was lifted out of, the
    page's placement matrix composed with its own rotation, and Tesseract was
    not asked (ADR 0025). A placement turn costs no read and carries no
    confidence, because it is a fact about the file rather than a verdict.

    ``confidence`` is always Tesseract's own figure for its own verdict, not a
    score from the second opinion. The second opinion's scores are in ``check``,
    kept separate so the two are never confused for one another.
    """

    exif_orientation: int | None = None
    exif_transposed: bool = False
    rotation_degrees: int = 0
    method: OrientationMethod = "disabled"
    confidence: float | None = None
    check: OrientationCheck | None = None

    @property
    def low_confidence(self) -> bool:
        """True when Tesseract answered but had almost nothing to go on."""
        return (
            self.method in ("osd", "osd_180_check", "osd_180_check_full_resolution")
            and self.confidence is not None
            and self.confidence < LOW_ORIENTATION_CONFIDENCE
        )


@dataclass(frozen=True)
class DecodedImage:
    """The pixels, plus the EXIF orientation tag that was found and applied.

    ``exif_orientation`` is the raw tag value, kept rather than reduced to the
    boolean, so that the response can say which orientation a file claimed and
    not merely that it claimed one.
    """

    pixels: np.ndarray
    exif_transposed: bool = False
    exif_orientation: int | None = None


@dataclass(frozen=True)
class Prepared:
    """The images OCR may read, and how all of them were turned to get there.

    ``binary`` is the preprocessed image: grayscale, scaled, adaptively
    thresholded and deskewed. ``gray`` is the same pixels with none of that
    done to them, scaled and turned upright and nothing more. ``colour`` is the
    scaled, turned RGB image, which is to say the pixels the file actually
    holds. All three exist because neither transform is reliably an
    improvement; see the module docstring and ``extract_text``.

    ``colour`` is None when the source carries no colour to lose, which is
    every grayscale scan, fax and monochrome render. Reading it would be
    reading ``gray`` a second time under another name, for the price of a full
    Tesseract pass.
    """

    binary: np.ndarray
    gray: np.ndarray
    orientation: Orientation
    colour: np.ndarray | None = None


@dataclass(frozen=True)
class ReadPath:
    """Which of the three images was read, and what each of them scored.

    ``variant`` is the one whose words were kept. ``preprocessed_confidence`` is
    always present because the preprocessed read always runs. The other two are
    null when their read never ran: ``plain_confidence`` when the comparison was
    already settled, or when the colour arm and the preprocessed arm had both
    returned no words at all (ADR 0026), and ``colour_confidence`` on a source
    that carries no colour at all.

    ``decided_by`` says how the winner was picked, because on this evidence the
    three cases are not the same claim. ``short_circuit`` means the preprocessed
    read cleared ``PREPROCESS_SHORT_CIRCUIT_CONFIDENCE`` on a monochrome source
    and nothing else was read. ``confidence`` means the winner scored higher
    than every other arm by more than ``EQUAL_CONFIDENCE_BAND``. ``coverage``
    means the leaders were inside that band, which is to say equally confident,
    and the winner is the one that recovered more text. See the band's own
    comment for why that last case has to exist.
    """

    variant: Literal["preprocessed", "plain", "colour"] = "preprocessed"
    preprocessed_confidence: float = 0.0
    plain_confidence: float | None = None
    colour_confidence: float | None = None
    decided_by: Literal["short_circuit", "confidence", "coverage"] = "short_circuit"


@dataclass(frozen=True)
class Segmentation:
    """How the sheet was cut up before its words were assembled into lines.

    Reported out to the response (FR-1, FR-10) for the same reason the
    orientation is: a field read off the wrong panel is indistinguishable, to an
    agent looking only at the value, from a field read badly. An agent who sees
    a brand name should be able to see which part of the sheet it came from,
    and an agent who sees something odd should be able to see that the sheet was
    read as four panels rather than one.

    ``columns`` is how many the x-gap rule cut, ``blocks`` how many distinct
    Tesseract blocks survived inside them, and ``column_bounds`` the cuts
    themselves in pixels of the image as read, left edge inclusive and right
    edge exclusive. One column and bounds spanning the whole width is a sheet
    that was not cut at all, which is every single-panel label.
    """

    columns: int = 1
    blocks: int = 0
    column_bounds: tuple[tuple[int, int], ...] = ()


@dataclass(frozen=True)
class OcrResult:
    """Everything the extraction step produces, and nothing about compliance."""

    text: str
    mean_confidence: float
    elapsed_ms: float
    lines: list[OcrLine] = field(default_factory=list)
    orientation: Orientation = Orientation()
    read_path: ReadPath = ReadPath()
    segmentation: Segmentation = Segmentation()
    # How many times Tesseract was invoked to produce this result: the
    # orientation call, the second opinion's scored rotations where it ran, and
    # one per arm read. It is the same count ``app.timing`` tallies for the
    # request, carried on the result so that a caller reading several pictures
    # can add them up without a recording open, which is what the per-document
    # read budget in ``app.application_form`` does.
    tesseract_reads: int = 0

    @property
    def has_text(self) -> bool:
        return bool(self.text.strip())


def decode(image_bytes: bytes) -> DecodedImage:
    """Decode image bytes into a BGR array, honouring the EXIF orientation tag.

    Pillow first, OpenCV second. The order is the whole point: a phone records
    which way it was held in EXIF tag 0x0112 and writes the sensor's pixels
    unturned, and ``cv2.imdecode`` drops the tag on the floor. Every viewer the
    agent used to look at the photograph applied it, so an image that looks
    upright on screen arrived at the pipeline on its side. ``ImageOps.exif_transpose``
    applies the tag, including the four mirrored orientations that leave the
    dimensions unchanged, before OpenCV sees anything.

    ``ImageOps.exif_transpose`` is Pillow's own implementation of the tag, used
    rather than a mapping written here, because a mapping written here is eight
    cases of which six are easy to get backwards. Its output is asserted against
    every one of the eight values in tests/test_ocr.py::TestExifOrientation: for
    each value the fixture is stored the way a file carrying that tag stores it,
    and the decoded array is compared pixel for pixel against the upright
    original, which is what a browser puts on screen.

    OpenCV remains the fallback for bytes Pillow will not open, so no format the
    service accepted before is refused now. That path reports no tag, because it
    read none, rather than reporting the absence of one.

    Raises ``UndecodableImageError`` rather than returning an empty array, so
    that the caller cannot mistake a failed decode for a blank label. FR-9
    requires those two to read differently to the agent.
    """
    if not image_bytes:
        raise UndecodableImageError("The uploaded file was empty.")

    try:
        with Image.open(io.BytesIO(image_bytes)) as opened:
            opened.load()
            tag = opened.getexif().get(_EXIF_ORIENTATION_TAG)
            upright = ImageOps.exif_transpose(opened)
            pixels = cv2.cvtColor(np.asarray(upright.convert("RGB")), cv2.COLOR_RGB2BGR)
        tag = int(tag) if isinstance(tag, int) and 1 <= tag <= 8 else None
        return DecodedImage(
            pixels=pixels,
            exif_transposed=tag not in (None, 1),
            exif_orientation=tag,
        )
    except (UnidentifiedImageError, OSError, ValueError, SyntaxError):
        # Pillow could not read it. That is not yet a decode failure: OpenCV
        # reads some encodings Pillow does not, and the accepted type set
        # (A-3) is checked before this is ever called.
        pass

    buffer = np.frombuffer(image_bytes, dtype=np.uint8)
    image = cv2.imdecode(buffer, cv2.IMREAD_COLOR)
    if image is None:
        raise UndecodableImageError(
            "The file could not be decoded as an image. It may be corrupt or truncated."
        )
    return DecodedImage(pixels=image, exif_transposed=False, exif_orientation=None)


def resize_long_edge(image: np.ndarray, long_edge: int | None = None) -> np.ndarray:
    """Scale the image so its long edge is ``long_edge`` pixels.

    Both directions are handled: a large photograph is scaled down so OCR does
    not spend its budget on pixels it does not need (NFR-1), and a small image
    is scaled up because Tesseract reads small glyphs poorly.
    """
    target = long_edge or settings.ocr_long_edge_px
    height, width = image.shape[:2]
    current = max(height, width)
    if current == 0 or current == target:
        return image
    scale = target / current
    interpolation = cv2.INTER_AREA if scale < 1 else cv2.INTER_CUBIC
    return cv2.resize(
        image,
        (max(1, round(width * scale)), max(1, round(height * scale))),
        interpolation=interpolation,
    )


def estimate_skew(binary: np.ndarray) -> float:
    """Estimate the page rotation in degrees from the ink pixels.

    A positive result means the content leans one way; ``deskew`` rotates by the
    negation to bring it back. Returns 0.0 when there is too little ink to
    estimate from, so that a nearly blank image is not rotated on the strength
    of noise.
    """
    coordinates = np.column_stack(np.where(binary > 0))
    if coordinates.shape[0] < 50:
        return 0.0
    angle = cv2.minAreaRect(coordinates.astype(np.float32))[-1]
    if angle > 45:
        angle -= 90
    elif angle < -45:
        angle += 90
    return float(angle)


def deskew(image: np.ndarray, binary: np.ndarray, max_degrees: float = 15.0) -> np.ndarray:
    """Rotate the image upright, within a bounded correction.

    The correction is the negation of the estimated angle, because the estimate
    describes the lean and the rotation has to undo it. Getting that sign wrong
    doubles the skew instead of removing it, which reads as an OCR accuracy
    problem rather than as the geometry bug it is; test_ocr.py asserts the
    direction so it cannot regress silently.

    The bound exists because a large estimated angle usually means the estimate
    is wrong rather than that the label is on its side, and rotating on a wrong
    estimate makes the OCR worse rather than better.
    """
    angle = estimate_skew(binary)
    if abs(angle) < 0.3 or abs(angle) > max_degrees:
        return image
    height, width = image.shape[:2]
    matrix = cv2.getRotationMatrix2D((width / 2, height / 2), -angle, 1.0)
    return cv2.warpAffine(
        image,
        matrix,
        (width, height),
        flags=cv2.INTER_CUBIC,
        borderMode=cv2.BORDER_REPLICATE,
    )


def rotate_cardinal(image: np.ndarray, degrees: int) -> np.ndarray:
    """Turn an image clockwise by 0, 90, 180 or 270 degrees.

    ``np.rot90`` turns counter-clockwise, so the count is negated. It is used
    rather than ``warpAffine`` because a quarter-turn is an index permutation:
    no interpolation, no border fill, no loss, and no cost worth measuring.
    """
    turns = (-(degrees // 90)) % 4
    if turns == 0:
        return image
    return np.ascontiguousarray(np.rot90(image, turns))


def detect_orientation(binary: np.ndarray) -> tuple[int, float | None, str]:
    """Ask Tesseract which quarter-turn brings the text upright.

    Returns the clockwise correction in degrees, Tesseract's confidence in it,
    and where the answer came from.

    **Why OSD rather than reading the image four times and keeping the best
    score.** Both were measured over the twelve-label sample set at all four
    cardinal rotations, forty-eight cases, on 2026-08-26. OSD was right in 46;
    picking the rotation with the highest mean word confidence was right in 7.
    The reason the second one fails is not tuning. Tesseract's own layout
    analysis already detects and corrects text rotated a quarter-turn clockwise,
    so an upright image and the same image turned clockwise produce
    byte-identical output: on the sample label, 62 words and a mean confidence
    of 95.4 either way. A score that is equal on the two cases it has to
    separate cannot separate them, whatever threshold is put around it. The
    measurement is recorded in docs/07_TEST_STRATEGY.md section 2 and asserted
    in tests/test_ocr.py::TestWhyOrientationUsesOsd so the claim cannot go stale.

    OSD is deterministic and local. It reads ``osd.traineddata`` from the same
    installed data directory as ``eng``, opens no socket (NFR-3), and returns
    the same answer for the same pixels.

    **It is asked on the grayscale, not on the thresholded image.** Until
    v1.0.1 it was asked on the thresholded one, which is fine on printed artwork
    and useless on a photograph: over the twelve-label sample set degraded to a
    soft-contrast, slightly blurred fixture and turned to all four cardinal
    rotations, OSD read the thresholded image correctly in 0 of 48 cases and the
    grayscale in 44 of 48. On the undegraded set the two are level, 46 and 45.
    That is the failure the 2026-08-28 submission hit: the tag was applied
    correctly, the threshold destroyed the photograph, OSD turned what was left
    the wrong way, and the read came back empty.
    """
    try:
        timing.tesseract_read()
        osd = pytesseract.image_to_osd(binary, output_type=Output.DICT)
    except (pytesseract.TesseractError, ValueError, KeyError):
        # "Too few characters" for a nearly blank image, or no osd.traineddata
        # installed. Neither is a reason to fail the verification: the image is
        # left as it is and the response says the orientation was not judged.
        return 0, None, "unavailable"

    rotation = int(osd.get("rotate", 0)) % 360
    confidence = osd.get("orientation_conf")
    confidence = float(confidence) if confidence is not None else None
    if rotation not in CARDINAL_ROTATIONS:
        return 0, confidence, "unavailable"
    return rotation, confidence, "osd"


def preprocess(
    decoded: DecodedImage,
    *,
    deskew_image: bool = True,
    correct_orientation: bool | None = None,
    placement_rotation: int | None = None,
) -> Prepared:
    """Scale and turn upright, then produce both the plain and the binary image.

    ``placement_rotation`` is the clockwise quarter-turn the document the
    picture came out of applies when it draws it (ADR 0025). When it is given
    it is the whole answer to the orientation question: it is applied, the
    method is reported as ``placement``, and Tesseract's orientation detection
    is not run whatever ``correct_orientation`` says, because the setting
    governs the OSD call and a placement turn is not one. It is None for a
    photograph, and for a picture whose placement is not a quarter-turn, and
    then everything below runs exactly as it did before the argument existed.

    Two images come back. ``gray`` is the scaled, upright grayscale and nothing
    else; ``binary`` is that same image adaptively thresholded and deskewed.
    ``extract_text`` decides between them.

    Adaptive thresholding rather than a global one, because Jenny Park's
    "the lighting is bad, or there's glare on the bottle" is uneven illumination
    across one image, which is exactly the case a global threshold handles worst.

    The order is deliberate, and changed in v1.0.1. The cardinal turn is decided
    on the grayscale and applied to both images before the threshold is taken:
    the turn is a fact about the photograph rather than about one rendering of
    it, and asking OSD on the thresholded image is what broke the 2026-08-28
    submission (see ``detect_orientation``). The turn still comes before the
    deskew, because the two corrections answer different questions and only one
    of them is bounded: ``deskew`` refuses any estimate over 15 degrees on the
    grounds that a large estimate is usually a wrong one, so a sideways label has
    to be brought within a few degrees of upright before the small-angle
    correction has anything it can act on.

    The quarter-turn check runs whether or not the EXIF tag was applied. That is
    deliberate and it is the second half of this hotfix: a tag is a claim about
    pixels that any editor can invalidate, so a file whose tag lies about its own
    contents has to be rescued by the same net that catches a photograph carrying
    no tag at all.
    """
    correct = settings.correct_orientation if correct_orientation is None else correct_orientation
    if placement_rotation is not None and placement_rotation % 360 not in CARDINAL_ROTATIONS:
        raise ValueError(f"A placement turn is a quarter-turn; got {placement_rotation}.")

    resized = resize_long_edge(decoded.pixels)
    gray = cv2.cvtColor(resized, cv2.COLOR_BGR2GRAY) if resized.ndim == 3 else resized
    colour = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB) if has_colour(resized) else None

    check: OrientationCheck | None = None
    confidence: float | None
    method: OrientationMethod
    if placement_rotation is not None:
        degrees, confidence, method = placement_rotation % 360, None, "placement"
    elif correct:
        degrees, confidence, method = detect_orientation(gray)
        if method == "osd" and confidence is not None and confidence < LOW_ORIENTATION_CONFIDENCE:
            degrees, check, rescored = _second_opinion_on_180(gray, degrees, confidence)
            method = "osd_180_check_full_resolution" if rescored else "osd_180_check"
    else:
        degrees, confidence, method = 0, None, "disabled"
    gray = rotate_cardinal(gray, degrees)
    if colour is not None:
        colour = rotate_cardinal(colour, degrees)

    binary = cv2.adaptiveThreshold(
        cv2.medianBlur(gray, 3), 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 31, 15
    )

    if deskew_image:
        inverted = cv2.bitwise_not(binary)
        binary = deskew(binary, inverted)

    return Prepared(
        binary=binary,
        gray=gray,
        colour=colour,
        orientation=Orientation(
            exif_orientation=decoded.exif_orientation,
            exif_transposed=decoded.exif_transposed,
            rotation_degrees=degrees,
            method=method,
            confidence=None if confidence is None else round(confidence, 2),
            check=check,
        ),
    )


def has_colour(image: np.ndarray) -> bool:
    """Whether this array holds colour a grayscale conversion would discard.

    A three-channel array is not the same thing as a colour image, and an exact
    channel comparison is the wrong test: a photograph of a grayscale document
    carries independent sensor noise in each channel, so every one of them is a
    colour image by that reading, and each would buy a full Tesseract pass to
    learn nothing. What matters is whether enough of the image carries enough
    chroma that flattening it to luminance could take a whole ink class with it.

    Both numbers are measured rather than chosen. Chroma here is
    ``max(R,G,B) - min(R,G,B)`` per pixel:

    ============================================  ======  ==============
    image                                          max     % >= 32
    ============================================  ======  ==============
    the twelve rendered sample labels                  0           0.000
    a sample label degraded to a photograph           30           0.000
    the three-class colour fixture                   140          84.381
    ============================================  ======  ==============

    So ``_COLOUR_CHROMA`` is 32: above every pixel the photograph-like fixture
    produces from sensor noise, and far below the chroma between any ink and
    ground a label prints. And ``_COLOUR_PIXEL_SHARE`` is one percent, which a
    coloured ground or a line of coloured type clears many times over and a
    stray coloured seal in the corner of an otherwise black-and-white label does
    not. The gap between the two clusters is 0.000 percent against 84 percent,
    which is not a threshold sitting on a knife edge.

    The consequence is the one that matters for NFR-1: every image in the sample
    set, and every grayscale scan and fax, takes exactly the v1.0.1 path at
    exactly the v1.0.1 cost. Nothing pays for this feature that cannot use it.
    """
    if image.ndim != 3 or image.shape[2] != 3:
        return False
    chroma = image.max(axis=2).astype(np.int16) - image.min(axis=2).astype(np.int16)
    return float((chroma >= _COLOUR_CHROMA).mean()) >= _COLOUR_PIXEL_SHARE


def _second_opinion_on_180(
    gray: np.ndarray, osd_degrees: int, osd_confidence: float
) -> tuple[int, OrientationCheck, bool]:
    """Score the OSD rotation against its opposite, and keep the better one.

    Returns the rotation kept, the check as reported to the agent, and whether
    the scoring had to be repeated at full resolution.

    **This is the narrow half of ADR 0003, and it is narrow on purpose.** That
    decision measured both approaches over the twelve-label sample set at all
    four cardinal rotations and found OSD right in 46 of 48 cases against 7 for
    picking the rotation with the highest mean word confidence. Nothing here
    disputes that number, and above ``LOW_ORIENTATION_CONFIDENCE`` OSD still
    decides alone.

    What the 7 of 48 hides is *which* cases the sweep loses. It loses the
    quarter-turns, and for a reason that is a property of Tesseract rather than
    of the threshold: layout analysis already detects and corrects text rotated
    a quarter-turn, so an upright image and the same image turned 90 degrees
    produce byte-identical output. A score that is equal on two cases cannot
    separate them, and no tuning changes that.

    It says nothing whatever about 0 against 180, where the same score separates
    the two cleanly. Measured on the author's mezcal COLA artwork: the colour
    image read 257 words at a mean of 89.1 upright and 254 at 35.3 upside down,
    and the grayscale 106 at 89.9 against 107 at 30.4. Fifty points and more,
    on the one axis where OSD had just admitted it was guessing.

    So the fallback is not the sweep ADR 0003 rejected. It is two rotations, not
    four, chosen so that every case it can decide is a case the score can
    actually decide. The opposite is the only other candidate offered, and a tie
    leaves the OSD verdict standing.

    Costs two Tesseract reads, and only on an image where OSD's own confidence
    fell under the floor. On the twelve-label sample set that is no image at all.

    **Both are read at ``ORIENTATION_CHECK_SCALE``, and the winner is applied to
    the full-resolution image** (OQ-27). Scoring is not reading: what these two
    passes have to do is separate two numbers that the measurement above puts
    fifty points and more apart, and doing that at half the working resolution
    is right in as many of the forty-eight measured cases as doing it at full
    resolution, for about half the time. The text an agent reads is unchanged,
    because it is read afterwards, from the full-size image, by the pipeline
    that always read it.

    **A tie of nothing is not a verdict (v1.3.0, code review finding 24).**
    Type too small to read at the reduced scale scores zero words and zero
    confidence both ways, and a tie leaves the OSD answer standing, which is
    the answer this check exists to second-guess: fine-print-only artwork filed
    upside down, with OSD saying 0 degrees at 0.03, was read upside down. So
    when neither candidate yields a word at ``ORIENTATION_CHECK_SCALE`` both
    are scored again at full resolution before anything is decided, and only
    a tie at full resolution falls back to the OSD verdict. The path taken is
    reported in ``Orientation.method`` and the outcome in ``overrode_osd``;
    ``check.candidates`` carries the scores that decided it. The
    full-resolution pass costs two more reads and runs only on an image the
    reduced pass could not read at all; on the twelve sample labels and on the
    author's own artwork, which score dozens of words at half scale, it never
    runs, and the measured figures in the CHANGELOG say so.
    """
    opposite = (osd_degrees + 180) % 360
    full_edge = max(gray.shape[:2])
    scored = _score_rotations(
        gray, (osd_degrees, opposite), max(1, round(full_edge * ORIENTATION_CHECK_SCALE))
    )
    rescored = all(candidate.words == 0 for candidate in scored)
    if rescored:
        scored = _score_rotations(gray, (osd_degrees, opposite), full_edge)

    chosen, challenger = scored
    # Strictly greater, so a tie leaves Tesseract's own answer in place. The
    # OSD verdict is a weak signal here, but it is still a signal, and a
    # coin-flip is not an improvement on it.
    overrode = challenger.confidence > chosen.confidence
    kept = challenger if overrode else chosen
    check = OrientationCheck(
        osd_rotation_degrees=osd_degrees,
        osd_confidence=round(osd_confidence, 2),
        floor=LOW_ORIENTATION_CONFIDENCE,
        candidates=tuple(scored),
        chosen_rotation_degrees=kept.rotation_degrees,
        overrode_osd=overrode,
    )
    return kept.rotation_degrees, check, rescored


def _score_rotations(
    gray: np.ndarray, rotations: tuple[int, int], long_edge: int
) -> list[RotationScore]:
    """Read the image at each rotation, scaled to ``long_edge``, and score it."""
    scored: list[RotationScore] = []
    for degrees in rotations:
        lines, confidence, _ = _read(resize_long_edge(rotate_cardinal(gray, degrees), long_edge))
        scored.append(
            RotationScore(
                rotation_degrees=degrees,
                confidence=round(confidence, 1),
                words=sum(len(line.text.split()) for line in lines),
            )
        )
    return scored


def extract_text(
    image_bytes: bytes,
    *,
    deskew_image: bool = True,
    correct_orientation: bool | None = None,
    placement_rotation: int | None = None,
) -> OcrResult:
    """Run the full local extraction path and time it.

    ``placement_rotation`` is for a picture lifted out of a document that
    states how it is placed; see ``preprocess``. A photograph passes nothing
    and is turned the way it always was. **A placed picture whose reading
    comes back as sideways type and nothing else is put to Tesseract after
    all** (ADR 0025): ``_reads_as_sideways`` decides that on the word boxes of
    the reading, for no read, and where Tesseract then names a different turn
    the picture is read again at that turn and that reading is kept. Where it
    names the same turn, or cannot answer, the first reading stands and only
    the orientation call was spent. The reported orientation is then
    Tesseract's, method and confidence and check, exactly as for a
    photograph, so that a turn taken on its verdict can be audited as one.

    **Preprocessing has to earn the read it is given.** The preprocessed image is
    read first. On a monochrome source, if it comes back at or above
    ``PREPROCESS_SHORT_CIRCUIT_CONFIDENCE`` the answer is kept and nothing else
    runs, which is what happens on eleven of the twelve sample labels. Otherwise
    the plain upright grayscale is read too and the higher-scoring is kept.

    **On a colour source the colour image is read first (v1.1.0).** Everything
    above describes a source with no colour to lose, and on one it still holds
    exactly. A coloured label is a different problem. Filed label artwork
    routinely carries dark-on-light and light-on-dark text on one ground, and a
    threshold separates two luminance classes, not three, so one ink class
    dissolves into the background while everything left standing still reads at
    95. On the three-class fixture in tests/test_colour_arm.py the preprocessed
    read scores 82.2 and the plain grayscale 95.6, and *both* have already
    dropped "42% ALC BY VOL" and "750 ML" by the time they score it.

    So on a coloured image the untransformed pixels are read first, because they
    are the only rendering that cannot have lost an ink class before Tesseract
    sees them, and the transformed ones have to earn their place against it
    rather than the other way around:

    * colour first, and if it clears ``PREPROCESS_SHORT_CIRCUIT_CONFIDENCE``
      that is the whole read. One Tesseract pass, which is one fewer than the
      author's mezcal artwork pays today.
    * otherwise preprocessed and plain are both read and all three are ranked.
      Three passes, on an image whose own pixels have already read poorly, which
      is the case where a transform has something to contribute.

    Neither transform gets to end the comparison on a coloured source, and that
    is deliberate: the failure being guarded against is a confident read of what
    survived a transform, so a confident read from a transform is not evidence
    that nothing was lost.

    * except that when the colour read and the preprocessed read have both
      returned no words at all, the plain read is not made (ADR 0026). Two
      passes, on an image that is a picture and not a label, or a label whose
      type no arm can find; ``_needs_the_plain_read`` has the evidence.

    Ranking is by mean word confidence, with ties inside
    ``EQUAL_CONFIDENCE_BAND`` broken by how much text the arm recovered. The
    band exists because this comparison has to detect omission and mean
    confidence cannot: a word that was never read contributes no confidence to
    lower. It never overrides a real difference in confidence; see the band's
    own comment for the two measurements that set it.

    The elapsed time is returned rather than logged, because NFR-1 requires the
    latency to be measured and reported rather than asserted, and NFR-6 forbids
    putting anything about the request in the logs.
    """
    started = time.perf_counter()
    decoded = decode(image_bytes)
    prepared = preprocess(
        decoded,
        deskew_image=deskew_image,
        correct_orientation=correct_orientation,
        placement_rotation=placement_rotation,
    )
    arms = _read_arms(prepared)
    winner, decided_by = _rank(arms)

    # A placed picture that reads as sideways type and nothing else is the
    # one case the placement cannot settle: a strip whose type runs along it,
    # affixed the way it is. Tesseract is asked, as it is for a photograph,
    # and only if it names another turn is the picture read again. The reads
    # of a reading set aside are still reads, and are counted.
    set_aside = 0
    correct = settings.correct_orientation if correct_orientation is None else correct_orientation
    if placement_rotation is not None and correct and _reads_as_sideways(winner.lines):
        asked = preprocess(decoded, deskew_image=deskew_image, correct_orientation=True)
        if asked.orientation.rotation_degrees != prepared.orientation.rotation_degrees:
            set_aside = len(arms)
            arms = _read_arms(asked)
            winner, decided_by = _rank(arms)
        prepared = asked

    scored = {arm.variant: round(arm.confidence, 1) for arm in arms}

    elapsed_ms = (time.perf_counter() - started) * 1000
    return OcrResult(
        text="\n".join(line.text for line in winner.lines),
        mean_confidence=round(winner.confidence, 1),
        elapsed_ms=round(elapsed_ms, 1),
        lines=winner.lines,
        orientation=prepared.orientation,
        segmentation=winner.segmentation,
        tesseract_reads=_orientation_reads(prepared.orientation) + len(arms) + set_aside,
        read_path=ReadPath(
            variant=winner.variant,
            preprocessed_confidence=scored.get("preprocessed", 0.0),
            plain_confidence=scored.get("plain"),
            colour_confidence=scored.get("colour"),
            decided_by=decided_by,
        ),
    )


def _read_arms(prepared: Prepared) -> list[_Arm]:
    """Read the arms ``extract_text`` describes, in its order, and no more."""
    arms: list[_Arm] = []
    if prepared.colour is not None:
        lines, confidence, segmentation = _read(prepared.colour)
        arms.append(_Arm("colour", lines, confidence, segmentation))

    if not arms or arms[0].confidence < PREPROCESS_SHORT_CIRCUIT_CONFIDENCE:
        lines, confidence, segmentation = _read(prepared.binary)
        arms.append(_Arm("preprocessed", lines, confidence, segmentation))

    if _needs_the_plain_read(arms, colour_read=prepared.colour is not None):
        lines, confidence, segmentation = _read(prepared.gray)
        arms.append(_Arm("plain", lines, confidence, segmentation))
    return arms


def _reads_as_sideways(lines: list[OcrLine]) -> bool:
    """Whether a reading shows type set at a quarter-turn and nothing upright.

    **The one thing a placement cannot tell (ADR 0025).** The page says which
    way up it draws the picture; it does not say which way the type on the
    picture runs. A side strip printed to be read along its length, affixed
    to the form the way it is, is placed upright and reads sideways, and the
    orientation call was what turned it. This is the gate that keeps that
    call for exactly that picture, and it costs no read: it is arithmetic on
    the word boxes the reading already returned, through ``OcrLine.sideways``,
    which is the same test ``app.parse`` uses to keep a rotated strip out of
    the brand ranking.

    Two conditions, and both have to hold. **No upright word at all**: a
    picture with any upright type on it is placed the right way up for that
    type, and the sideways words beside it are the arced lettering, the
    vertical strip and the single tall glyph that every real panel carries
    some of. **And at least one sideways line of two or more words**: a lone
    glyph has no direction to speak of, ``i`` and ``1`` and ``|`` are taller
    than they are wide whichever way up the page is, and one of them is what
    the bourbon's strip reads as.

    Measured 2026-09-08 at the placement turn, on every panel of the two
    filings in samples/real/ and on the five-panel fixture in
    tests/test_artwork_panels.py, whose side strip is set vertically:

    ==============================  ======  ==========  ========  ==================
    panel                            words    sideways   upright   sideways lines
    ==============================  ======  ==========  ========  ==================
    bourbon, 1950 x 862                  0           0         0                   0
    bourbon, 1350 x 300                 16           1        15                   0
    bourbon, 1103 x 340                  8           5         3                   0
    bourbon, 1050 x 309                 53           1        52                   0
    bourbon, 187 x 1697                  1           0         1                   0
    mezcal, 1750 x 1150                258          28       230                   4
    fixture side strip, 187 x 1697      48          48         0                   3
    ==============================  ======  ==========  ========  ==================

    The fixture strip is the only row with no upright word, and it is the
    only one Tesseract is asked about. A simple majority would also have
    asked about the 1103 by 340 panel, whose arced lettering reads as five
    tall boxes against three upright ones, for a read that comes back
    unable to answer; and any rule on sideways lines alone would have asked
    about the mezcal, whose two vertical strips are four such lines beside
    230 upright words, for the three reads its second opinion costs. Neither
    is a picture placed the wrong way up, and neither pays.
    """
    upright = sum(len(line.text.split()) for line in lines if not line.sideways)
    if upright:
        return False
    return any(line.sideways and len(line.text.split()) >= 2 for line in lines)


def _orientation_reads(orientation: Orientation) -> int:
    """How many engine invocations turning the image upright cost.

    None where no call was made: ``disabled``, and ``placement``, where the
    turn came from the document and Tesseract was never asked (ADR 0025). One
    for the OSD call whenever it was attempted, which is every other method:
    an OSD call that came back "too few characters" was still a call, and
    ``detect_orientation`` tallies it as one. Two more where the second
    opinion scored the OSD verdict against its opposite, and two more again
    where that scoring read nothing at the reduced scale and was repeated at
    full resolution. The same arithmetic ``timing.tesseract_read`` records as
    it happens, restated here from the reported method so the two cannot
    drift apart without ``tests/test_ocr.py`` noticing.
    """
    if orientation.method in ("disabled", "placement"):
        return 0
    if orientation.method == "osd_180_check":
        return 3
    if orientation.method == "osd_180_check_full_resolution":
        return 5
    return 1


def _needs_the_plain_read(arms: list[_Arm], *, colour_read: bool) -> bool:
    """Whether the plain upright grayscale still has anything to contribute.

    Two rules, one per kind of source, and they are the two paragraphs of
    ``extract_text`` in code. On a source with no colour to lose the plain read
    runs when the preprocessed read fell short of the short-circuit confidence,
    which is v1.0.1 unchanged. On a coloured source it runs whenever the colour
    read fell short, whatever the preprocessed read then scored, because a
    confident read of a thresholded colour image is exactly the evidence this
    release stopped trusting.

    **With one exception, on the coloured source only (ADR 0026): when the
    colour read and the preprocessed read have both returned no words at all,
    the plain read is not made.** The test is on words, not on confidence. A
    read of nothing scores 0.0 and so does nothing else; a read of something
    that scored badly is a read the comparison exists for, and the 1350 by
    300 panel on the bourbon filing in samples/real/, preprocessed 44.7 and
    then plain 89.9 with the brand name on it, is why no confidence floor
    would do here.

    Two reasons the third read has nothing left to find, one structural and
    one measured. The plain arm on a coloured source is there to compete with
    a *confident* read of a transformed image that may have dropped an ink
    class; where the transformed read found nothing there is nothing to
    compete with, and the colour arm, the one rendering that cannot have lost
    an ink class, has already read the untransformed pixels and found nothing
    either. And the plain arm is one grayscale, a weighted mean of the three
    channels, whose contrast between any two inks can never exceed the
    contrast of the channel that separates them best; the colour arm hands
    Tesseract all three channels and it thresholds each and keeps the best,
    so there is no two-tone label the plain arm can separate that the colour
    arm could not. Measured on 2026-09-08 over the three low-contrast shapes
    docs/09 section 9 names (pale mint on white, gold on near-black, pale pink
    on deep purple) at 24 and 46 pixel type, each clean, under an
    illumination gradient, under glare and at two levels of contrast loss,
    plus the three-class colour fixture under the same four, thirty cases in
    all: the colour arm read every case the plain arm read, and the one case
    where the colour arm read nothing, the bourbon's 1950 by 862 painting,
    every arm read nothing. The preprocessed arm is not touched by this rule
    and its full-resolution read still runs, because a local threshold is the
    one thing the colour arm does not do, and on a source with no colour the
    photograph-like fixture in tests/test_ocr.py still reads zero words
    preprocessed and every word plain, which is v1.0.1's own finding and the
    reason the rule stops at the coloured source.
    """
    if not colour_read:
        return arms[-1].confidence < PREPROCESS_SHORT_CIRCUIT_CONFIDENCE
    colour = arms[0]
    if colour.confidence >= PREPROCESS_SHORT_CIRCUIT_CONFIDENCE:
        return False
    preprocessed = arms[1]
    return colour.words > 0 or preprocessed.words > 0


@dataclass(frozen=True)
class _Arm:
    """One rendering of the image, read, with what it scored and how it was cut.

    The segmentation travels with the arm rather than being taken from the last
    read, because each rendering is segmented on its own word boxes and only the
    winning arm's lines are kept. Reporting another arm's layout beside them
    would describe a reading that was discarded.
    """

    variant: Literal["preprocessed", "plain", "colour"]
    lines: list[OcrLine]
    confidence: float
    segmentation: Segmentation = Segmentation()

    @property
    def words(self) -> int:
        return sum(len(line.text.split()) for line in self.lines)


def _rank(arms: list[_Arm]) -> tuple[_Arm, Literal["short_circuit", "confidence", "coverage"]]:
    """Pick the arm to keep, and say what picked it.

    Mean word confidence ranks. Where the leader is clear of every other arm by
    more than ``EQUAL_CONFIDENCE_BAND`` it wins outright, and that is the rule
    v1.0.1 set and this release does not change: an arm that recovered more
    text than the leader but scored materially below it still loses.

    The band is what mean confidence on its own cannot express. Two arms inside
    it are, on this evidence, equally confident about what each of them read,
    and the question of which read *more* is then the only question left. That
    is the case the colour arm exists for, and it is the case where the losing
    arm dropped an entire ink class without any word it did keep scoring a
    point lower for it.

    Order is stable: with everything equal the earliest arm wins, and the arms
    arrive in the order ``extract_text`` read them. On a source with no colour
    to lose that is the preprocessed read first, which is v1.0.1 unchanged; on a
    coloured one it is the colour read first, which is the arm that cannot have
    lost an ink class before Tesseract saw it.
    """
    if len(arms) == 1:
        return arms[0], "short_circuit"

    best = max(arm.confidence for arm in arms)
    contenders = [arm for arm in arms if best - arm.confidence <= EQUAL_CONFIDENCE_BAND]
    if len(contenders) == 1:
        return contenders[0], "confidence"

    leader = max(contenders, key=lambda arm: arm.words)
    if leader.words == max(arm.words for arm in contenders if arm is not leader):
        # Equally confident and equally full: confidence is still the reason,
        # and calling it coverage would claim a distinction nothing measured.
        return max(contenders, key=lambda arm: arm.confidence), "confidence"
    return leader, "coverage"


def _read(image: np.ndarray) -> tuple[list[OcrLine], float, Segmentation]:
    """Read one prepared image and return its lines, confidence and layout.

    One Tesseract pass, which is the same one this function has always made.
    The segmentation below is arithmetic on the word boxes that pass already
    returns, so a sheet of four panels costs exactly what a sheet of one costs.
    """
    timing.tesseract_read()
    data = pytesseract.image_to_data(image, lang="eng", output_type=Output.DICT)
    lines, confidences, segmentation = _assemble_lines(data, width=int(image.shape[1]))
    mean_confidence = float(sum(confidences) / len(confidences)) if confidences else 0.0
    return lines, mean_confidence, segmentation


def _columns(data: dict, indices: list[int], width: int) -> list[tuple[int, int]]:
    """Cut the sheet into columns at every blank wide enough to be a gutter.

    Every word box the read returned is projected onto the x axis, and a run of
    pixel columns no box covers is a candidate boundary. A candidate becomes a
    boundary when it clears both of ``COLUMN_GAP_WIDTH_SHARE`` and
    ``COLUMN_GAP_TYPE_SIZES``; see those constants for what each one is for and
    what each was measured against. The cut is placed in the middle of the blank
    rather than at either end, so a word box overhanging its panel by a pixel
    cannot move the boundary onto its neighbour.

    Returns one ``(left, right)`` pair per column, left to right, covering the
    whole width with no gaps between them: the first starts at 0 and the last
    ends at ``width``, so every word falls in exactly one column and none can be
    lost between two.

    A sheet with no blank clearing both conditions comes back as a single column
    spanning the image, which is the answer for every single-panel label and is
    what keeps their reading identical to what it was before this existed.
    """
    if not indices:
        return [(0, width)]

    boxes = [
        (
            max(0, int(data["left"][index])),
            min(width, max(0, int(data["left"][index])) + max(0, int(data["width"][index]))),
            min(int(data["width"][index]), int(data["height"][index])),
        )
        for index in indices
    ]

    covered = np.zeros(width + 1, dtype=bool)
    for left, right, _ in boxes:
        covered[left : right + 1] = True

    minimum_width = max(1, round(width * COLUMN_GAP_WIDTH_SHARE))
    bounds: list[int] = [0]
    run = 0
    for x in range(width + 1):
        if not covered[x]:
            run += 1
            continue
        blank = (x - run, x)
        run = 0
        # A blank running to either edge is a margin, not a gutter, and cutting
        # at it would put a column number on no words at all.
        if blank[0] <= 0 or blank[1] >= width:
            continue
        if blank[1] - blank[0] < minimum_width:
            continue
        if not _is_gutter(boxes, blank):
            continue
        cut = blank[0] + (blank[1] - blank[0]) // 2
        if cut > bounds[-1]:
            bounds.append(cut)

    bounds.append(width)
    return [(bounds[index], bounds[index + 1]) for index in range(len(bounds) - 1)]


def _is_gutter(boxes: list[tuple[int, int, int]], blank: tuple[int, int]) -> bool:
    """Whether a blank is wider than the type beside it, so not a word space.

    The type beside it is the largest of the word boxes ending just before the
    blank and those starting just after it, measured on the shorter side of each
    box. "Just" is the blank's own width: a word further from it than the blank
    is wide is not what the blank is separating.

    A blank with no word within that reach is left to the width condition alone.
    That is the sparse case where there is nothing to measure against, and
    refusing every such cut would put the whole sheet back in one column.
    """
    left, right = blank
    reach = right - left
    adjacent = [
        size
        for box_left, box_right, size in boxes
        if (left - reach <= box_right <= left) or (right <= box_left <= right + reach)
    ]
    if not adjacent:
        return True
    return reach >= COLUMN_GAP_TYPE_SIZES * max(adjacent)


def _assemble_lines(data: dict, *, width: int) -> tuple[list[OcrLine], list[float], Segmentation]:
    """Group Tesseract's word rows into lines within one region of the sheet.

    **A line never spans two panels, and it takes both rules to hold that.**

    The first is Tesseract's own: words are grouped by ``block_num`` and
    ``par_num`` as well as ``line_num``, so a block the layout analysis
    separated stays separate. That is what keeps the vertical strip on the
    author's mezcal artwork, which Tesseract does put in blocks of its own, from
    being read into the panels either side of it.

    The second is ``_columns``, and it is needed because the first is not
    sufficient. On the same artwork Tesseract returns blocks spanning almost the
    full width of the sheet, so ``HECHO EN MEXICO`` from the left panel and
    ``long, smooth finish.`` from the right one arrive in one block, one
    paragraph and one line. Cutting at the gutters first and grouping inside a
    column second separates them, and it is what makes the government warning
    come out as the statement 27 CFR 16.21 sets rather than as that statement
    with two lines of a neighbouring panel spliced through it.

    Reading order is column by column, and each column top to bottom. A sheet
    printed as columns is read as columns; a page whose text runs across it is
    one column and is read exactly as it was before this existed.
    """
    usable = [
        index
        for index, word in enumerate(data.get("text", []))
        if str(word).strip() and float(data["conf"][index]) >= 0
    ]

    columns = _columns(data, usable, width)
    grouped: dict[tuple[int, int, int, int, int], list[int]] = {}
    for index in usable:
        centre = int(data["left"][index]) + int(data["width"][index]) / 2
        column = next(
            (number for number, (left, right) in enumerate(columns) if left <= centre < right),
            len(columns) - 1,
        )
        key = (
            data["page_num"][index],
            column,
            data["block_num"][index],
            data["par_num"][index],
            data["line_num"][index],
        )
        grouped.setdefault(key, []).append(index)

    lines: list[OcrLine] = []
    confidences: list[float] = []
    ordered = sorted(
        grouped,
        key=lambda k: (k[0], k[1], min(data["top"][i] for i in grouped[k])),
    )
    for key in ordered:
        indices = grouped[key]
        words = [str(data["text"][i]).strip() for i in indices]
        word_confidences = [float(data["conf"][i]) for i in indices]
        heights = [float(data["height"][i]) for i in indices]
        widths = [float(data["width"][i]) for i in indices]
        confidences.extend(word_confidences)
        lines.append(
            OcrLine(
                text=" ".join(words),
                confidence=round(sum(word_confidences) / len(word_confidences), 1),
                height=round(sum(heights) / len(heights), 1),
                top=min(int(data["top"][i]) for i in indices),
                column=key[1],
                block=key[2],
                width=round(sum(widths) / len(widths), 1),
            )
        )
    segmentation = Segmentation(
        columns=len(columns),
        blocks=len({(key[1], key[2]) for key in grouped}),
        column_bounds=tuple(columns),
    )
    return lines, confidences, segmentation
