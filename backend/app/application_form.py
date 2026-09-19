"""Read the application-side values off an uploaded COLA document.

Governing requirements: FR-11 (accept the label application as an alternative to
typing the same values), FR-2 (those values are what the label is compared
against), FR-9 (a document that cannot be read returns a clear message and no
field reports a match), NFR-3 (no outbound network call: the document is parsed
here, in this process), NFR-6 (nothing is persisted), OOS-1.

**This is not the COLA integration OOS-1 excludes, and the difference is the
whole basis for the feature.** OOS-1 rules out integrating with the COLA system:
no API calls, no COLAs Online authorization, no registry lookups. Nothing here
does any of those. What is accepted is a copy of a document the applicant
already has, uploaded by the agent in the same way a label photograph is
uploaded, and read locally. It needs no credentials and it opens no socket. See
docs/adr/0008-cola-form-as-application-input.md.

**Three ways in, tried in order.** A COLA document reaches an agent in one of
three shapes and each hides its values somewhere different:

1. *Form fields.* An applicant's filled-in copy of the downloadable form keeps
   its values in AcroForm fields. They are not in the page's text layer at all,
   so reading the page would find the blank template's captions and nothing
   else.
2. *Text layer.* COLAs Online output and a Public COLA Registry printout are
   digitally generated, so the characters are in the file. Extraction is
   deterministic: no recognition step, no confidence figure, no misread.
3. *OCR.* A scan or a photograph of a printed form carries pixels only. It goes
   through exactly the Tesseract pipeline label artwork goes through, and
   inherits its accuracy and its failure modes.

The first two are tried on every PDF; OCR runs only when neither found a single
mapped value, because rasterizing and reading pages costs about what reading a
label photograph costs and there is nothing to gain by paying it for a document
that has already answered.

**Four, in fact: the document carries its own label artwork.** An applicant
affixes the label artwork to the application, so a filed PDF carries pictures of
the labels alongside the typed items. Three of the five values this tool
compares are not items on the form at all, which is assumption A-17, and on the
author's own document, 2026-08-29, they were sitting inside those pictures: the
alcohol content and the net contents are absent from the text layer exactly as
A-17 says, and both are printed on the flat label artwork embedded in the file.
So every embedded raster image at or above a size floor is read through the same
Tesseract pipeline label artwork goes through, and what it says fills the fields
the text layer left empty. It never overrides the text layer. The precedence,
end to end, is: typed by the agent, then the document's text layer or form
fields, then the embedded artwork, then absent. See
[ADR 0010](../../docs/adr/0010-embedded-label-artwork.md).

**Comparing artwork lifted out of the application against the application it
came from is a self-consistency check.** It proves the artwork on file carries
the mandatory elements and that they agree with the typed form data. It is not
independent verification of a physical bottle, and nothing here should be read
as claiming it is; that still needs a photograph of the bottle.

**What the form does not carry.** The item map below is transcribed from
TTB F 5100.31 (04/2023) as downloaded, not from memory, and the honest result is
that three of the five values this tool compares are not items on the form at
all. The class or type designation, the alcohol content and the net contents
appear on the labels affixed to the application rather than in a numbered box;
net contents appears in item 15 only when it is blown, branded or embossed on
the container **and** does not appear on the labels. A Public COLA Registry
printout does carry class or type, and carries the code alongside the
description. Where a value is not on the document, this reports it as not found
and the agent supplies it, which is assumption A-17.
"""

from __future__ import annotations

import ctypes
import io
import logging
import math
import re
import threading
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass, field, replace
from functools import cached_property
from typing import Literal

import pypdfium2 as pdfium
import pypdfium2.raw as pdfium_raw
from PIL import Image

from app import timing
from app.compare import Outcome
from app.config import settings
from app.ocr import OcrLine, OcrResult, UndecodableImageError, extract_text
from app.parse import ParsedFields, parse_fields
from app.product_type import (
    CAPTION_TEXT,
    CaptionBox,
    ProductTypeReading,
    caption_boxes_from_words,
    read_product_type,
    word_boxes_from_ocr,
)
from app.search import LabelUnit, label_units, verify_presence

# The values a COLA document can supply. Four of them are compared against the
# label (FR-2); the beverage type is carried for the interface, which asks for
# it, and is not compared, because no source states a rule that reads it.
APPLICATION_FIELDS = (
    "brand_name",
    "class_type",
    "alcohol_content",
    "net_contents",
    "beverage_type",
)

# ``not_read`` is the prefill pass on a document with no text layer: its pages
# were located and counted and deliberately not read, because reading them is
# the most expensive thing this module does and the check a moment later reads
# them anyway (ADR 0024, extending ADR 0017 from the pictures to the pages).
ExtractionPath = Literal["form_fields", "embedded_text", "ocr", "not_read"]

# Where one value came from, inside the document (ADR 0010). Reported per value
# because a document can now answer from two different places at once, and a
# reading taken off a picture is a different kind of evidence from a reading
# taken out of a text layer: the first went through OCR and can be misread, the
# second cannot.
ValueSource = Literal["form_fields", "embedded_text", "embedded_artwork", "product_type_box"]

# The four values the embedded artwork can supply. The beverage type is not one
# of them: item 5 is three check boxes, a label does not print "distilled
# spirits" as a form answer, and inferring one from the artwork would be exactly
# the guess FR-1 forbids (ADR 0008). It is read from the form's own rendered
# page instead, where the tick actually is; see ``app.product_type`` and
# [ADR 0016](../../docs/adr/0016-product-type-from-the-page.md).
ARTWORK_FIELDS = ("brand_name", "class_type", "alcohol_content", "net_contents")

PDF_MAGIC = b"%PDF"

logger = logging.getLogger(__name__)

# **PDFium is not thread-safe, and the batch path reads documents in a pool.**
#
# PDFium keeps process-global state and its API has to be serialized by the
# caller; pypdfium2 wraps it and inherits that. Reading two documents at once
# segfaults the process, which on the batch path takes the stream and every
# completed result with it: exactly the whole-batch failure NFR-2 forbids, and
# not something a per-row error can catch, because the process is gone.
#
# So every call into PDFium is made under this lock. What is deliberately left
# outside it is the OCR fallback: pages are rendered to bytes under the lock and
# read by Tesseract after it is released, so a batch of scanned documents still
# spends its expensive step in parallel. Text-layer and form-field reading, the
# ordinary case, are milliseconds and serialize harmlessly.
#
# This is the same shape of problem as the OpenMP one in app.ocr, found the same
# way: a library that is fine on the single-label path and not fine in a worker
# pool.
_PDFIUM_LOCK = threading.Lock()


class UnreadableDocumentError(Exception):
    """The bytes submitted could not be read as a COLA document (FR-9)."""


@dataclass(frozen=True)
class EmbeddedArtwork:
    """One raster image lifted whole out of an application document (ADR 0010).

    ``content`` is PNG bytes of the embedded image at its own resolution, not a
    render of the page it sits on. That distinction is the decision: a page
    rasterized at a fixed DPI throws away resolution the embedded picture
    already has, and hands the OCR engine the form's own printed captions mixed
    in with the label text. Lifting the image out gives the pipeline the flat
    artwork on its own, which is the input it handles well.

    ``image`` is the picture itself, copied out of PDFium's buffer while the
    lock was held, and ``content`` is encoded from it on first use. The encode
    is Pillow work and not a PDFium call, so it has no business inside the
    lock, and a picture the prefill pass counts and never reads (ADR 0017) is
    never encoded at all (v1.3.0, code review finding 25).
    """

    page: int
    width: int
    height: int
    image: Image.Image = field(repr=False, compare=False)
    # The clockwise quarter-turn the page applies when it draws this picture,
    # composed from the image's placement matrix and the page's own rotation
    # (ADR 0025), or None when the placement is not a quarter-turn. It is
    # what ``extract_text`` is given instead of an orientation call: a PDF
    # states which way up its pictures are, and a photograph does not. See
    # ``_placement_rotation``.
    placement_rotation: int | None = None

    @property
    def pixels(self) -> int:
        return self.width * self.height

    @cached_property
    def content(self) -> bytes:
        """PNG bytes at the picture's own resolution, encoded outside the lock."""
        return _png_bytes(self.image)


@dataclass(frozen=True)
class RejectedImage:
    """One embedded image that was not treated as candidate label artwork.

    Carries the page it sat on, how big it was, and the named reason. It
    deliberately does not carry the picture, or anything read out of it: on a
    filed application the commonest rejection is the applicant's own
    handwritten signature, which is personal data and has no business in a
    response, a log, or a fixture (NFR-6).
    """

    page: int
    width: int
    height: int
    reason: RejectionReason


@dataclass(frozen=True)
class AcceptedImage:
    """One embedded image that cleared the floor, and what happened to it.

    The other half of ``RejectedImage``, and reported for the same reason: an
    agent looking at a value the artwork did not supply needs the table of what
    was read, at what size, with what confidence, as much as the table of what
    was set aside. The picture itself never travels (NFR-6).
    """

    page: int
    width: int
    height: int
    status: AcceptedStatus
    # Mean word confidence of the read, where one ran.
    ocr_confidence: float | None = None


@dataclass(frozen=True)
class LabelPanel:
    """One embedded picture that was read, with what it was read to say.

    Carried together so that the label side never reads the same picture a
    second time (NFR-1, ADR 0017): the check takes every panel here, with its
    reading, and pools them the way ADR 0007 pools photographs.
    """

    artwork: EmbeddedArtwork
    read: OcrResult


@dataclass(frozen=True)
class ParsedApplication:
    """What an uploaded COLA document said, and how it was read.

    ``values`` carries every key in ``APPLICATION_FIELDS``; ``None`` means the
    document did not state it, explicitly, in the same sense FR-1 gives "not
    found" on a label. ``notes`` says why in the cases where the reason is a
    property of the form rather than of this document.
    """

    values: dict[str, str | None]
    fanciful_name: str | None = None
    class_type_code: str | None = None
    path: ExtractionPath = "embedded_text"
    pages_read: int = 0
    notes: list[str] = field(default_factory=list)
    # Where each value came from, for the values that were found (ADR 0010). A
    # field the document did not carry has no entry.
    value_sources: dict[str, ValueSource] = field(default_factory=dict)
    # How many embedded raster images cleared the size floor, and how many of
    # those produced readable text. Both are reported so that "the artwork
    # supplied nothing" and "there was no artwork" are distinguishable, which is
    # the difference between a scan worth retaking and a document that simply
    # files its labels separately.
    artwork_images_found: int = 0
    artwork_images_read: int = 0
    # Every embedded image that did not clear the floor, with the reason. See
    # RejectedImage: the picture itself never travels.
    artwork_images_rejected: list[RejectedImage] = field(default_factory=list)
    # Every embedded image that did clear it, with what happened to it, largest
    # first. Reported so that the next person debugging a filing has the same
    # table of sizes the author had to instrument the deployed build to get.
    artwork_images_accepted: list[AcceptedImage] = field(default_factory=list)
    # For each value taken off the artwork, the panel it was read from.
    artwork_value_panels: dict[str, EmbeddedArtwork] = field(default_factory=dict)
    # Every panel that read with text, in rank order, largest first, which is
    # the order the label side takes them and the order ``artwork_images_accepted``
    # lists them (ADR 0010 as amended; one order since 2026-09-06). The check
    # pools all of them: the brand may be on the front and the alcohol content
    # on the back.
    label_panels: list[LabelPanel] = field(default_factory=list)
    # Whether the artwork pass ran at all on this reading (ADR 0017).
    #
    # False means the pictures inside the document were located and counted and
    # deliberately not read. It is not the same as "there was no artwork" and it
    # is not the same as "the artwork read nothing": a caller has to be able to
    # tell a document that carries no pictures from one whose pictures are still
    # to be read at check time, because the second one is not a gap the agent
    # has to fill.
    artwork_read: bool = True
    # The first of those panels: the one the response names as the page the
    # label came from (ADR 0010, FR-1). Kept alongside ``label_panels`` because
    # one picture is still the ordinary case, and a caller that wants the
    # pool takes the list.
    label_artwork: EmbeddedArtwork | None = None
    # **What that image was already read to say, so it is read once.** The
    # picture chosen as the label side is by construction a picture this module
    # has just put through the OCR pipeline to fill the application values. The
    # label side used to put the identical bytes through the identical pipeline
    # again, which on the author's own filing was a second three-second pass for
    # a result already in memory. Handing the read on is the same trick ADR 0011
    # plays with the classifier's read, for the same reason.
    label_artwork_read: OcrResult | None = None
    # What this reading cost against the per-document ceiling (NFR-1,
    # ADR 0023): the Tesseract invocations spent on pages and pictures
    # together, the ceiling itself, whether it was reached, and how many pages
    # the OCR fallback did not get to because of it. Pictures it did not get
    # to are in ``artwork_images_accepted`` as ``not_reached``.
    tesseract_reads: int = 0
    read_budget: int = 0
    read_budget_reached: bool = False
    pages_not_reached: int = 0

    @property
    def found_any(self) -> bool:
        """Whether this reading produced anything at all.

        The fanciful name counts. It is not compared against the label, but a
        document that gave it up is a document that was read, and falling back
        to OCR after reading one successfully would pay for a second reading of
        a file that has already answered.
        """
        return self.fanciful_name is not None or any(
            value is not None for value in self.values.values()
        )


def reads_as_application(lines: list[OcrLine]) -> bool:
    """Whether these lines carry at least one mapped COLA application value.

    Exposed for ``app.classify``, which decides whether an uploaded picture is a
    form or a label and must not reach into this module's internals to do it. A
    label carries no ``BRAND NAME:`` caption, because a label prints the brand
    rather than captioning it.
    """
    return _from_lines(lines).found_any


def parse_application_document(
    content: bytes,
    content_type: str | None,
    *,
    pre_read: OcrResult | None = None,
    read_artwork: bool = True,
    read_pages: bool = True,
) -> ParsedApplication:
    """Read one uploaded COLA document. Never reaches the network (NFR-3).

    ``pre_read`` is an OCR result for an image that has already been read, which
    is what ``app.classify`` produces while deciding that this file is a form at
    all (ADR 0011). Passing it back means the picture is read once rather than
    twice. It is ignored for a PDF, whose text does not come from OCR.

    ``read_artwork`` decides whether the pictures embedded in a PDF are put
    through Tesseract. It is the whole of
    [ADR 0017](../../docs/adr/0017-read-the-artwork-once.md): the prefill pass
    sets it False and takes the text layer alone, which costs milliseconds, and
    the check sets it True because the check needs the artwork anyway. Reading
    it twice was the same picture through the same pipeline in two requests, for
    one submission. It has no effect on an image, which carries no objects to
    lift out.

    ``read_pages`` is the same decision for a PDF that carries no text layer
    ([ADR 0024](../../docs/adr/0024-the-scanned-form-is-read-once.md)). Reading
    such a file means rendering every page and putting each through the label
    pipeline, which on a three-page scan measured about ten seconds on the
    deployed build, and the check re-read the same pages a moment later. The
    prefill pass sets it False and reports the path as ``not_read``; the check
    sets it True. It has no effect on a document with a text layer, whose
    pages are never rendered for reading, and no effect on an image, which is
    read the one way it can be.
    """
    if not content:
        raise UnreadableDocumentError(
            "The uploaded application document is empty. Send the file again, or "
            "type the application values instead."
        )
    if _is_pdf(content, content_type):
        return _parse_pdf(content, read_artwork=read_artwork, read_pages=read_pages)
    return _parse_image(content, pre_read=pre_read)


def _is_pdf(content: bytes, content_type: str | None) -> bool:
    """Decide by the bytes, and by the declared type only as a fallback.

    A browser labels an uploaded file from its extension, which an agent can
    rename. The header is what the file is.
    """
    return content.startswith(PDF_MAGIC) or content_type == "application/pdf"


@dataclass(frozen=True)
class _PdfContents:
    """What one pass over a PDF produced, with every PDFium call already done.

    Everything expensive is deliberately left for the caller to do once the lock
    is released: the rendered pages and the embedded artwork come back as
    decoded pictures copied out of PDFium's buffers, the PNG encoding of them
    happens after the lock, and Tesseract reads them outside the critical
    section. Until v1.3.0 the encodes happened inside it, for every embedded
    picture that cleared the floor rather than only the ones read; that was
    code review finding 25.
    """

    text_side: ParsedApplication | None
    rendered_pages: list[Image.Image]
    artwork: list[EmbeddedArtwork]
    artwork_found: int
    artwork_rejected: list[RejectedImage]
    pages: int
    # One rendered page and, where the file carried a text layer, the three
    # item 5 caption boxes located in it exactly (ADR 0016). None for the boxes
    # means the page has no text layer and the captions have to be recognized,
    # which happens outside the lock like every other Tesseract read.
    item_five: tuple[Image.Image, list[CaptionBox] | None] | None = None


def _png_bytes(image: Image.Image) -> bytes:
    """One decoded picture as PNG bytes. Pillow work; never called under the lock."""
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def _parse_pdf(
    content: bytes, *, read_artwork: bool = True, read_pages: bool = True
) -> ParsedApplication:
    """Read one PDF. Every PDFium call is made under ``_PDFIUM_LOCK``.

    **One budget for the whole document** (NFR-1, ADR 0023). ``budget`` counts
    every Tesseract invocation this reading makes, on the embedded pictures and
    on the rendered pages alike, against ``Settings.max_document_reads``. It is
    consulted before each picture and before each page, never inside one, so a
    picture is read whole or not at all; what it stops is listed on the result
    as ``not_reached`` and counted in ``pages_not_reached``, and the notes say
    so in words. A budget that cut silently would be worse than the slowness it
    prevents, because an agent would read "not found" for a value nobody looked
    for.
    """
    budget = _ReadBudget(limit=settings.max_document_reads)
    with _PDFIUM_LOCK, timing.phase("document_pdfium"):
        contents = _read_pdf_with_pdfium(content, render_pages=read_pages)

    # The page renders are encoded here, after the lock, because encoding is
    # Pillow work that serialised every document in a batch for nothing
    # (finding 25). The embedded artwork encodes itself on first use, inside
    # the artwork read below, so a picture the prefill pass never reads is
    # never encoded.
    # Attributed to the PDFium phase, though outside the lock: it is PDF work
    # without recognition, which is what that phase names. Until ADR 0025 the
    # encode of the item 5 render and the sampling of its boxes below sat
    # outside every phase, about 80 ms on a session container, invisible
    # while the artwork OCR beside them was ten times that and visible once
    # ADR 0025 and ADR 0026 halved it.
    with timing.phase("document_pdfium"):
        rendered_pages = [_png_bytes(page) for page in contents.rendered_pages]
        item_five_page = (
            None
            if contents.item_five is None
            else (_png_bytes(contents.item_five[0]), contents.item_five[1])
        )

    # The artwork read happens here, outside the lock, for the reason the page
    # OCR below does: Tesseract is the expensive part and there is no reason for
    # one document's reading to block another's.
    #
    # Where the caller asked for the text layer alone it does not happen at all,
    # and the pictures are counted rather than read (ADR 0017). That is the
    # single most expensive thing this module does, and on the prefill pass it
    # was being paid for a second time by the check that followed it.
    #
    # The text side's values go in so the stopping rule can ask the question
    # the check will ask: whether the declared brand and class or type appear
    # on the panels read so far. On a scan there is no text side yet, and the
    # rule falls back to the panels' own reading of those two.
    artwork = (
        _read_artwork(
            contents.artwork,
            contents.artwork_rejected,
            declared=None if contents.text_side is None else contents.text_side.values,
            budget=budget,
        )
        if read_artwork
        else _unread_artwork(contents.artwork, contents.artwork_rejected)
    )
    # Item 5, sampled off the rendered page (ADR 0016). Outside the lock like
    # every other expensive step, and only where nothing has answered it already.
    # None here means no page's text layer named the item; the scan branch below
    # gets a second chance at it from the pages it renders anyway. Where the
    # captions have to be recognized rather than read out of a text layer that
    # is one Tesseract read, charged to the budget and never gated by it: it is
    # one read of one page, and it is what settles the beverage type.
    if item_five_page is not None and item_five_page[1] is not None:
        # Captions from the text layer, so no read inside: the sample is PDF
        # work without recognition and is attributed with the encode above.
        with timing.phase("document_pdfium"):
            item_five = read_item_five(item_five_page)
    else:
        item_five = read_item_five(item_five_page)
        if item_five_page is not None:
            budget.charge(1)

    if contents.text_side is not None:
        return _with_notes(
            _with_product_type(_merge_artwork(contents.text_side, artwork), item_five),
            path=contents.text_side.path,
            pages_read=contents.pages,
            budget=budget,
        )

    # No text layer, and this is the prefill pass: the pages are not read here
    # (ADR 0024). What comes back says that the file is a scan whose values
    # are still to be read, which the interface treats as values on their way
    # rather than as gaps, exactly as it treats the pictures ADR 0017 leaves
    # to the check. Nothing is a value here and nothing claims to be.
    if not read_pages:
        return _deferred_reading(contents, artwork, budget)

    # Nothing in the file itself, so it is a scan: read the pages rendered
    # above.
    # Orientation correction is off because a page rendered from a PDF is
    # already the right way up, and the OSD pass costs about as much again as
    # the read it precedes (see app.ocr).
    ocr_lines: list[OcrLine] = []
    pages_not_reached = 0
    for rendered in rendered_pages:
        if not budget.allows():
            pages_not_reached += 1
            continue
        with timing.phase("page_ocr"):
            page_read = extract_text(rendered, correct_orientation=False)
        budget.charge(page_read.tesseract_reads)
        ocr_lines.extend(page_read.lines)
    # Item 5 on a page with no text layer to search (ADR 0016). The captions have
    # to be recognized, so this is gated on the page OCR above having read the
    # item's own caption: a document that is not this form never pays for it, and
    # one that is pays for exactly one page.
    if (
        item_five is None
        and rendered_pages
        and _ITEM_FIVE_CAPTION.search("\n".join(line.text for line in ocr_lines))
    ):
        item_five = read_item_five((rendered_pages[0], None))
        budget.charge(1)

    # A document whose pictures were deliberately left unread is not a document
    # that could not be read (ADR 0017), and neither is one whose pages the
    # budget did not reach: both are documents that were not looked at, and
    # the response says which. Raising here would tell an agent their file is
    # unreadable at prefill time and then verify it a moment later.
    if (
        not ocr_lines
        and not artwork.values
        and not (artwork.images_found and not artwork.read)
        and not pages_not_reached
    ):
        raise UnreadableDocumentError(
            "No text could be read from the uploaded PDF, either from the file "
            "itself, or by reading its pages as images, or from any picture "
            "embedded in it. Nothing was taken from it. Type the application "
            "values instead."
        )
    from_pages = (
        _from_lines(ocr_lines)
        if ocr_lines
        else ParsedApplication(values=dict.fromkeys(APPLICATION_FIELDS))
    )
    return _with_notes(
        _with_product_type(
            _merge_artwork(_sourced(from_pages, "embedded_text"), artwork), item_five
        ),
        path="ocr",
        pages_read=contents.pages - pages_not_reached,
        budget=budget,
        pages_not_reached=pages_not_reached,
    )


@dataclass
class _ReadBudget:
    """How many Tesseract invocations one document may still cost (ADR 0023).

    ``limit`` is ``Settings.max_document_reads`` and ``spent`` is every read
    made so far, taken from ``OcrResult.tesseract_reads`` after each picture or
    page rather than from the request's recording, so that the same arithmetic
    holds outside a recording: in a test, in ``scripts/measure.py``, and on the
    batch path where each row has a recording of its own.

    Checked, not enforced mid-read: ``allows`` is asked before a picture or a
    page is started, and a picture is read whole. So the reads can pass the
    limit by at most one picture's cost, which is three arms for a picture
    the document places (ADR 0025) and eight at the very most for one it does
    not, and the last picture read is never a half-comparison with an arm
    missing.
    """

    limit: int
    spent: int = 0

    def allows(self) -> bool:
        return self.spent < self.limit

    def charge(self, reads: int) -> None:
        self.spent += reads

    @property
    def reached(self) -> bool:
        return self.spent >= self.limit


def _deferred_reading(
    contents: _PdfContents, artwork: _ArtworkReading, budget: _ReadBudget
) -> ParsedApplication:
    """A scan on the prefill pass: counted, not read (ADR 0024).

    Every value is absent because nothing was read, not because the document
    lacks it, and the one note says so. The absence notes ``_with_notes``
    attaches are deliberately not attached: "the form has no box for this"
    is true of the form and not of a reading that never happened, and the
    check attaches them a moment later when it has read the pages.
    """
    return ParsedApplication(
        values=dict.fromkeys(APPLICATION_FIELDS),
        path="not_read",
        pages_read=0,
        notes=[DEFERRED_PAGES_NOTE],
        artwork_images_found=artwork.images_found,
        artwork_images_read=artwork.images_read,
        artwork_images_rejected=artwork.rejected,
        artwork_images_accepted=artwork.accepted,
        artwork_read=artwork.read,
        tesseract_reads=budget.spent,
        read_budget=budget.limit,
        read_budget_reached=budget.reached,
        pages_not_reached=contents.pages,
    )


@contextmanager
def _open_page(document: pdfium.PdfDocument, index: int) -> Iterator[pdfium.PdfPage]:
    """One page, closed when the caller is done with it rather than by the GC.

    **This is the page-level half of the rule ``_read_pdf_with_pdfium`` already
    applies to the document, and it is not tidiness.** Every pypdfium2 handle is
    an ``AutoCloseable``, and each one registers a weakref of itself in its
    parent's ``_kids`` set. A page left to the garbage collector takes that
    weakref with it whenever the collector happens to run, and the collector is
    free to run in the middle of ``PdfDocument.close()``, which walks exactly
    that set. It raised on CI on 2026-08-30:

        File "pypdfium2/internal/bases.py", line 168, in close
          for k_wref in self._kids:
        RuntimeError: Set changed size during iteration

    The library defers the child closes to avoid mutating the set from inside
    its own loop; what it cannot defend against is a weakref callback firing
    from a collection it did not ask for. So the pages are closed here, in
    order, while they are still referenced, and ``_kids`` is empty by the time
    the document is closed. ``PdfDocument.get_page`` caches nothing, so each
    call was adding another weakref for the collector to drop later.

    It is the same argument the document's own ``close()`` rests on: a
    collection running on another thread would call into PDFium outside
    ``_PDFIUM_LOCK``. That is true of a page handle as much as of a document
    one, and it was only ever half enforced.
    """
    page = document[index]
    try:
        yield page
    finally:
        page.close()


def _read_pdf_with_pdfium(content: bytes, *, render_pages: bool = True) -> _PdfContents:
    """Everything that touches PDFium, in one place, for one document.

    ``render_pages`` is False on the prefill pass (ADR 0024): a document with
    no text layer comes back with its pages counted and none rendered, because
    a render nobody reads is PDFium time under the lock for nothing.

    Returns the reading taken from the file itself, when it carried values, plus
    the pages rendered to PNG bytes for the OCR fallback and every embedded
    raster image that cleared the size floor. The document is closed here rather
    than left to the garbage collector, because a collection running on another
    thread would call into PDFium outside the lock.
    """
    try:
        document = pdfium.PdfDocument(io.BytesIO(content))
        page_count = len(document)
    except Exception as exc:  # pypdfium2 raises its own error types
        raise UnreadableDocumentError(
            "The uploaded file could not be opened as a PDF. It may be damaged, "
            "or password protected. Send it again, or type the application "
            "values instead."
        ) from exc

    try:
        if not page_count:
            raise UnreadableDocumentError(
                "The uploaded PDF has no pages in it. Send the file again, or type "
                "the application values instead."
            )

        pages = min(page_count, settings.max_document_pages)

        # Every page is searched for artwork, not only the pages read for text.
        # The author's own document states its brand name on page 1 and carries
        # the label artwork on page 3, and a page limit chosen to bound how much
        # text is read has nothing to say about where the pictures are. The cost
        # is bounded by the count of images actually read rather than by the
        # page count (ADR 0010).
        artwork, artwork_found, artwork_rejected = _embedded_images(document, page_count)

        from_fields = _from_form_fields(document, pages)
        lines = _pdf_text_lines(document, pages)
        from_text = _from_lines(lines)

        merged = _combine(from_fields, from_text)

        # Item 5 is read off the page only where nothing has answered it
        # already. An AcroForm radio group states it exactly, and a page render
        # costs real milliseconds (NFR-1), so this is skipped on an unflattened
        # form and paid for on every other kind of filing.
        item_five = None if merged.values.get("beverage_type") else _item_five_page(document, pages)

        if merged.found_any:
            path: ExtractionPath = "form_fields" if from_fields.found_any else "embedded_text"
            return _PdfContents(
                text_side=ParsedApplication(
                    values=merged.values,
                    fanciful_name=merged.fanciful_name,
                    class_type_code=merged.class_type_code,
                    path=path,
                    value_sources=merged.value_sources,
                ),
                rendered_pages=[],
                artwork=artwork,
                artwork_found=artwork_found,
                artwork_rejected=artwork_rejected,
                pages=pages,
                item_five=item_five,
            )

        rendered_pages: list[bytes] = []
        for index in range(pages if render_pages else 0):
            try:
                rendered_pages.append(_render_page(document, index))
            except Exception as exc:
                # One page that will not render is not the document failing. The
                # class name and the page number go to the log and nothing else:
                # NFR-6 forbids anything about the content reaching it.
                logger.warning(
                    "application document page could not be rendered",
                    extra={"page": index + 1, "cause": type(exc).__name__},
                )
        return _PdfContents(
            text_side=None,
            rendered_pages=rendered_pages,
            artwork=artwork,
            artwork_found=artwork_found,
            artwork_rejected=artwork_rejected,
            pages=pages,
            item_five=item_five,
        )
    finally:
        document.close()


def _parse_image(content: bytes, *, pre_read: OcrResult | None = None) -> ParsedApplication:
    """A photograph or scan of the form, submitted as an image.

    No embedded artwork here, by construction: an image has no objects inside
    it to lift out. What the pixels show is what was read, and the whole picture
    is already going through the label pipeline.
    """
    try:
        # As in app.verify._read_one: a read handed on by the classifier is not
        # a pass, and is not counted as one.
        if pre_read is not None:
            result = pre_read
        else:
            with timing.phase("document_ocr"):
                result = extract_text(content)
    except UndecodableImageError as exc:
        raise UnreadableDocumentError(
            "The uploaded application document could not be decoded as an image "
            "or a PDF. Send it again, or type the application values instead."
        ) from exc
    if not result.has_text:
        raise UnreadableDocumentError(
            "The uploaded application document was read but no text could be "
            "extracted from it. Nothing was taken from it. Type the application "
            "values instead."
        )
    parsed = _sourced(_from_lines(result.lines), "embedded_text")

    # Item 5 (ADR 0016). A photograph or scan of the form **is** the rendered
    # page, so the sample is taken on the bytes as submitted rather than on a
    # render of them. The word boxes have to come from a second pass for the same
    # reason: ``extract_text`` reads a thresholded, resized and deskewed copy, and
    # every one of those transforms moves the words relative to the pixels a
    # sample would be taken from.
    #
    # Gated on the read above having found item 5's own caption, so a document
    # that is not this form never pays the pass, and gated on nothing else having
    # answered, so a form that stated its type in text does not either.
    if parsed.values.get("beverage_type") is None and _ITEM_FIVE_CAPTION.search(result.text):
        parsed = _with_product_type(parsed, read_item_five((content, None)))

    # One picture, read once: its reads are reported against the ceiling for
    # the same reason a PDF's are, and never gated by it, because a single
    # image is the least a document can cost.
    budget = _ReadBudget(limit=settings.max_document_reads)
    budget.charge(result.tesseract_reads)
    return _with_notes(parsed, path="ocr", pages_read=1, budget=budget)


# --------------------------------------------------------------------------
# The embedded label artwork (ADR 0010, amended 2026-09-03).
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class _ArtworkReading:
    """What every embedded picture in one document was read to say."""

    values: dict[str, str]
    images_found: int
    images_read: int
    rejected: list[RejectedImage] = field(default_factory=list)
    # Every picture that cleared the floor, with what happened to it, largest
    # first. This is the other half of ``rejected``: the table an agent needs
    # to see why a value is absent is the one that lists what was read as well
    # as what was set aside.
    accepted: list[AcceptedImage] = field(default_factory=list)
    # The panel each value in ``values`` was taken from.
    value_panels: dict[str, EmbeddedArtwork] = field(default_factory=dict)
    # Every picture that read with text, in the order they were read, which
    # is rank order, largest first: the same order ``accepted`` lists them
    # in, so that "photo 3" on a row and the third read entry in the artwork
    # table are one picture (2026-09-06). Empty when nothing was read.
    label_panels: list[LabelPanel] = field(default_factory=list)
    # The first panel that yielded a label value, or None where none did. It
    # is what the response names as the page the label came from; it used to
    # be found by putting the valued panels first in ``label_panels``, which
    # made that list's order mean two things at once.
    first_valued: LabelPanel | None = None
    # Whether Tesseract was run over these pictures at all (ADR 0017). False
    # means they were located and counted and left unread.
    read: bool = True


def _embedded_images(
    document: pdfium.PdfDocument, page_count: int
) -> tuple[list[EmbeddedArtwork], int, list[RejectedImage]]:
    """Lift every embedded raster image out of the document, largest first.

    **Extracted rather than rendered, and the difference is the decision.**
    ``_render_page`` rasterizes a whole page at a chosen scale, which is right
    for reading a scanned form and wrong for reading the artwork on it: the
    render is capped at ``ocr_long_edge_px`` across the whole page, so a picture
    occupying a third of it comes out at a third of that, well below the
    resolution the file already holds. It also hands Tesseract the form's own
    printed captions mixed in with the label text. Lifting the image object out
    gives the pipeline the artwork at its native size and nothing else.

    Only images clearing the area floor survive; see ``_rejection`` and
    ``Settings.min_artwork_pixels``. Every survivor is returned, largest first;
    how many of them are read is ``_read_artwork``'s decision, bounded by
    ``max_artwork_images``, and a survivor past that bound is reported as
    accepted and not read rather than dropped. The count returned alongside is
    how many cleared the floor.

    **What was rejected is returned too, with the reason (v1.1.0).** A filed
    application carries the applicant's handwritten signature, and a rejection
    that happens silently is one an agent cannot check. Only the page number,
    the dimensions and the named reason travel: never the picture, never
    anything read out of it. The signature in particular is the most personal
    artefact on the form, and nothing here puts an extracted image in a log
    line or keeps one past the request (NFR-6). A picture that is read goes to
    the OCR engine through the short-lived temporary file ``pytesseract``
    writes and deletes; a rejected one is never decoded at all.

    Called under ``_PDFIUM_LOCK``, and only PDFium work happens here: the
    pictures come back decoded and copied, and the PNG encode each one needs
    before Tesseract can read it is deferred to first use, outside the lock and
    only for the pictures actually read (finding 25). Every failure here is one
    image skipped, not a document failing: a PDF can carry an image in a colour
    space or a filter PDFium will not hand back, and the rest of the file is
    still readable.
    """
    candidates: list[EmbeddedArtwork] = []
    rejected: list[RejectedImage] = []
    for index in range(page_count):
        with _open_page(document, index) as page:
            for obj in page.get_objects():
                if not isinstance(obj, pdfium.PdfImage):
                    continue
                try:
                    width, height = obj.get_px_size()
                except Exception as exc:
                    logger.warning(
                        "embedded image size could not be read",
                        extra={"page": index + 1, "cause": type(exc).__name__},
                    )
                    continue
                reason = _rejection(width, height)
                if reason is None and (picture := _artwork_bitmap(obj, index)) is None:
                    reason = "unreadable"
                if reason is not None:
                    rejected.append(
                        RejectedImage(page=index + 1, width=width, height=height, reason=reason)
                    )
                    continue
                candidates.append(
                    EmbeddedArtwork(
                        page=index + 1,
                        width=width,
                        height=height,
                        image=picture,
                        placement_rotation=_placement_rotation(obj, page),
                    )
                )

    candidates.sort(key=lambda art: (-art.pixels, art.page))
    rejected.sort(key=lambda image: (image.page, -image.width * image.height))
    return candidates, len(candidates), rejected


# Why one embedded image was not treated as candidate label artwork. Named
# rather than free text so that the reason is a value an agent's tooling can
# read, and so that adding a test to the floor forces a name for what it
# rejects. ``short_edge`` and ``aspect_ratio`` were reasons until v1.5.0; the
# two rules behind them rejected five of the six pictures on a real filing and
# are gone (ADR 0010 as amended, #121).
RejectionReason = Literal["area", "unreadable"]

# What happened to one picture that cleared the floor. ``read`` means Tesseract
# ran and text came back; ``no_text`` means it ran and nothing did;
# ``undecodable`` means the picture would not decode for it; ``not_needed``
# means the panels read before it already carried all five values, so reading
# stopped (ADR 0010 as amended a second time); ``not_read`` means it was never
# put through the engine for a reason that is not the stopping rule, either
# because the prefill pass deliberately reads nothing (ADR 0017) or because it
# fell past ``max_artwork_images``. The two are kept apart because they mean
# opposite things to the next person reading a response: ``not_needed`` says
# the values were found without this picture, ``not_read`` says nothing about
# whether they are on it.
# ``not_reached`` (ADR 0023) means the document's read budget was spent
# before the reader got to this picture. It is kept apart from ``not_read``
# for the same reason ``not_needed`` is: an agent has to be able to see that
# the values may be on a picture nobody looked at, and why nobody did.
AcceptedStatus = Literal["read", "no_text", "not_needed", "not_read", "not_reached", "undecodable"]


def _rejection(width: int, height: int) -> RejectionReason | None:
    """Why this embedded image is not label artwork, or None if it might be.

    One test: the area floor in ``Settings.min_artwork_pixels``, which is what
    separates the applicant's signature from a label panel on both real filings
    the author has measured. Agency seals, barcodes, logos and signature strips
    are furniture on the form and small; label panels are the thing the form is
    about and are not.

    There used to be three tests. A short-edge floor and an aspect-ratio ceiling
    were added so that a signature scanned at a higher resolution would still be
    excluded by its shape, and they were set from one document whose artwork is
    one flat sheet. On the second document the author measured, a bourbon filing
    whose labels are embedded as separate panels, the two shape tests rejected
    every panel: front, back, wrap-around and side band, at ratios from 3.24 to
    9.07 and short edges from 187 to 340. The signature that motivated them,
    687 by 195, has a ratio of 3.52 and a short edge of 195, which no ceiling and
    no floor can place on the other side of those panels. Area does, with margin
    on both sides. The numbers are beside the setting.
    """
    if width * height < settings.min_artwork_pixels:
        return "area"
    return None


# How far from a quarter-turn a placement may be and still be read as one.
# A page that draws a picture with a rotation matrix writes cos and sin of the
# angle into it, and a quarter-turn arrives as 0 and 1 to floating-point
# precision, not to the degree; the tolerance exists for that rounding, and a
# picture placed at a real slant falls outside it and is left to Tesseract.
_PLACEMENT_TOLERANCE_DEGREES = 1.0


def _placement_rotation(image: pdfium.PdfImage, page: pdfium.PdfPage) -> int | None:
    """The clockwise quarter-turn the page applies when it draws this picture.

    **A PDF says which way up its pictures are, and a photograph does not
    (ADR 0025).** The raster ``_artwork_bitmap`` lifts out is the picture in
    its own coordinate space; how it appears to anyone who opens the file is
    that raster under the placement matrix the page draws it with, composed
    with the page's own ``/Rotate``. Both are in the file, both are exact, and
    neither costs a Tesseract call. The eight pictures on the two filings in
    samples/real/ are all placed with an axis-aligned, positive-scale matrix
    on an unrotated page, so the answer is 0 for every one of them, and it was
    0 for every one of them after the orientation call as well, at the cost
    of that call.

    The matrix is ``[a b c d e f]`` in PDF user space, where y runs upward. A
    picture drawn upright has ``b`` and ``c`` at zero and ``a`` and ``d``
    positive; one drawn turned by an angle has that angle's cosine and sine in
    the first column and the same angle in the second. The angle is read from
    both columns and the two have to agree, so a skewed placement is not
    mistaken for a turned one, and the determinant has to be positive, so a
    mirrored one is not either. ``/Rotate`` is clockwise by the PDF's own
    convention and the placement angle is counter-clockwise, which is why one
    is subtracted from the other. Whether the composed turn is the right one
    is not argued from those conventions: tests/test_placement_orientation.py
    renders the page and checks that the raster, turned by this figure, is
    the picture the page shows.

    Returns None wherever the placement is not a quarter-turn, or cannot be
    read: a slant, a mirror, a degenerate matrix. That is not a failure; it
    is the case the orientation call exists for, and the caller passes None
    on to ``extract_text`` and Tesseract is asked as it always was.
    """
    try:
        a, b, c, d, _, _ = image.get_matrix().get()
        page_turn = int(page.get_rotation()) % 360
    except Exception:
        return None
    if a * d - b * c <= 0:
        return None
    turns: list[int] = []
    for angle in (math.degrees(math.atan2(b, a)), math.degrees(math.atan2(-c, d))):
        nearest = round(angle / 90) * 90
        if abs(angle - nearest) > _PLACEMENT_TOLERANCE_DEGREES:
            return None
        turns.append(int(nearest) % 360)
    if turns[0] != turns[1]:
        return None
    return (page_turn - turns[0]) % 360


def _artwork_bitmap(image: pdfium.PdfImage, page_index: int) -> Image.Image | None:
    """One embedded image, decoded at its own resolution and copied, or None.

    ``render=False`` asks PDFium for the image's own bitmap rather than for a
    rendering of it as placed on the page, which is what keeps the resolution.
    ``convert("RGB")`` always returns a new image, so what leaves here owns its
    pixels and outlives the document handle that is closed under the lock.
    """
    try:
        return image.get_bitmap(render=False).to_pil().convert("RGB")
    except Exception as exc:
        # NFR-6: the class name and the page number, nothing the picture showed.
        logger.warning(
            "embedded image could not be extracted",
            extra={"page": page_index + 1, "cause": type(exc).__name__},
        )
        return None


def _accepted(
    image: EmbeddedArtwork, status: AcceptedStatus, confidence: float | None = None
) -> AcceptedImage:
    return AcceptedImage(
        page=image.page,
        width=image.width,
        height=image.height,
        status=status,
        ocr_confidence=confidence,
    )


def _unread_artwork(
    images: list[EmbeddedArtwork], rejected: list[RejectedImage] | None = None
) -> _ArtworkReading:
    """Count the pictures and read none of them (ADR 0017).

    **This is not a degenerate case of ``_read_artwork``; it is the point of the
    decision.** The prefill pass exists so that the five boxes fill as fast as
    the file uploads, and the only thing in it that was not fast was a full
    Tesseract pass over every picture in the document, run to fill two values
    that the check a moment later reads the same pictures for again.

    What survives is everything that costs nothing: how many pictures cleared
    the floor, which ones, and which did not and why. What does not survive is
    any value, and any claim that one of these pictures can stand in as the
    label side, because deciding that means reading them. ``read`` says which
    of the two readings this is, so that "no artwork" and "artwork not yet
    read" are never confused for each other downstream.
    """
    return _ArtworkReading(
        values={},
        rejected=list(rejected or []),
        accepted=[_accepted(image, "not_read") for image in images],
        images_found=len(images),
        images_read=0,
        read=False,
    )


def _read_artwork(
    images: list[EmbeddedArtwork],
    rejected: list[RejectedImage] | None = None,
    *,
    declared: Mapping[str, str | None] | None = None,
    budget: _ReadBudget | None = None,
) -> _ArtworkReading:
    """Read the surviving embedded pictures, largest first, until the values are in hand.

    **And never past the document's read budget** (ADR 0023). Before each
    picture ``budget.allows`` is asked; the first time it says no, that picture
    and every one after it are listed as ``not_reached`` and the reading
    stops. The check is between pictures, so the picture being read when the
    line is crossed is read whole. A caller that passes no budget gets one at
    the configured ceiling, so the rule holds wherever this is called from.

    **The pipeline is the one label artwork goes through, with one thing
    known that a photograph cannot tell it.** ``extract_text`` is given the
    turn the document itself applies to the picture, ``placement_rotation``
    (ADR 0025), and makes no orientation call; the preprocessed-against-plain
    best-of and the colour arm apply exactly as they do to a photograph. The
    artwork is flat, which is the input that pipeline handles well; that is
    the whole reason this is worth doing. A picture whose placement is not a
    quarter-turn carries None and is turned by Tesseract as before.

    **Panels are read in rank order, and reading stops when the panels read
    so far carry all five values** (ADR 0010 as amended a second time). After
    each panel ``_satisfied`` asks whether the pool now holds the declared
    brand and class or type, the alcohol content, the net contents and the
    government warning; the first time it does, the rest are listed as
    ``not_needed`` and never read. A one-sheet filing is one read. A filing
    that spreads its values over five panels is five reads, because the
    fifth is where the last value was. A filing missing a value altogether
    reads every panel up to ``max_artwork_images``, which is the one case the
    sweep is doing real work, and the response says which panels were read
    and how well.

    **Why the stop is keyed to the check's question and not to "did this
    panel yield a value".** The rule this replaces stopped once the four
    application values were in hand, and on a filing whose government
    warning sat on a further panel it reported the warning absent. The rule
    before that read every panel to a fixed count, and on a filing with five
    panels it never looked at the fifth. Both decided correctness with a
    number that had nothing to do with where the values were. This one stops
    only when nothing the check needs is still unread, and ``max_artwork_images``
    is left as a ceiling on the worst case.

    Values are taken per field from the panel that read that field most
    confidently among the panels read, which is the rule ADR 0007 uses to
    merge two photographs of one label and the rule that keeps a large
    picture read badly from overriding a smaller one read well. The panel each
    value came from is recorded, so a value that was misread can be traced to
    the picture it was read off.

    ``label_panels`` is every picture that read with text, in the order they
    were read, which is rank order. **That order is the one the response
    reports (2026-09-06).** The label side takes these panels as its
    photographs, each field's ``source_photo`` counts them from one, and the
    artwork table on the application block lists the same pictures largest
    first; on the author's bourbon the list used to put the panels that
    yielded a value first, so "read from photo 5" pointed at the fifth entry
    of one list and the first of the other, and nothing on screen said which.
    One order, and it is the one the table already shows.

    ``first_valued`` keeps what that reordering used to buy: the panel named as
    the page the label came from is still the first that yielded a value, so
    a large scan of a page of prose is not named as the label when a smaller
    picture of the label was there. Nothing is dropped from the pool for it.

    A picture that will not decode is skipped rather than fatal. It is a picture
    inside a document, and the document may have answered already.
    """
    values: dict[str, str] = {}
    value_confidence: dict[str, float] = {}
    value_panels: dict[str, EmbeddedArtwork] = {}
    accepted: list[AcceptedImage] = []
    with_values: list[LabelPanel] = []
    without_values: list[LabelPanel] = []
    readings: list[ParsedFields] = []
    units: list[LabelUnit] = []

    bound = settings.max_artwork_images
    accepted.extend(_accepted(image, "not_read") for image in images[bound:])
    budget = _ReadBudget(limit=settings.max_document_reads) if budget is None else budget

    for position, image in enumerate(images[:bound]):
        if not budget.allows():
            accepted.extend(_accepted(rest, "not_reached") for rest in images[position:bound])
            break
        try:
            with timing.phase("artwork_ocr"):
                result = extract_text(image.content, placement_rotation=image.placement_rotation)
        except UndecodableImageError as exc:
            logger.warning(
                "embedded image could not be decoded",
                extra={"page": image.page, "cause": type(exc).__name__},
            )
            accepted.append(_accepted(image, "undecodable"))
            continue
        budget.charge(result.tesseract_reads)
        if not result.has_text:
            accepted.append(_accepted(image, "no_text", result.mean_confidence))
            continue
        accepted.append(_accepted(image, "read", result.mean_confidence))

        parsed = parse_fields(result.lines)
        found = {
            name: value for name in ARTWORK_FIELDS if (value := getattr(parsed, name)) is not None
        }
        for name, value in found.items():
            confidence = parsed.confidence.get(name, 0.0)
            # Strictly greater, so a tie goes to the larger panel, which was
            # read first.
            if name not in values or confidence > value_confidence[name]:
                values[name] = value
                value_confidence[name] = confidence
                value_panels[name] = image
        panel = LabelPanel(artwork=image, read=result)
        (with_values if found else without_values).append(panel)

        readings.append(parsed)
        units.extend(label_units(result.lines))
        if _satisfied(readings, units, declared or {}):
            accepted.extend(_accepted(rest, "not_needed") for rest in images[position + 1 : bound])
            break

    accepted.sort(key=lambda image: (-(image.width * image.height), image.page))
    valued = {id(panel) for panel in with_values}
    panels = sorted(
        with_values + without_values,
        key=lambda panel: (-panel.artwork.pixels, panel.artwork.page),
    )
    return _ArtworkReading(
        values=values,
        rejected=list(rejected or []),
        accepted=accepted,
        value_panels=value_panels,
        images_found=len(images),
        images_read=len(panels),
        label_panels=panels,
        first_valued=next((panel for panel in panels if id(panel) in valued), None),
    )


# The five things the check needs from the label side, and how each is known
# to be in hand. The first two are the check's own search (ADR 0015); the
# other three are located by pattern and by the statement's prefix.
_SEARCHED_FOR_STOP = (("brand_name", False), ("class_type", True))
_PATTERN_FOR_STOP = ("alcohol_content", "net_contents")


def _satisfied(
    readings: list[ParsedFields], units: list[LabelUnit], declared: Mapping[str, str | None]
) -> bool:
    """Whether the panels read so far carry everything the check will look for.

    Five questions, one per value, and every one has to be yes.

    **The brand name and the class or type are asked the way the check asks
    them.** The check does not take a panel's largest text as the brand; it
    searches the pooled label text for the value the application declares
    (FR-1, ADR 0015). So where the document's text side declares one, this
    searches the panels read so far for it with the same function and stops
    only on a hit at the match threshold. A hit in the review band is not
    enough to stop on: a later panel may print the value cleanly, and stopping
    on the near miss would turn a match into a review for the sake of one
    read. Where nothing is declared, a scan with no text layer say, the
    panels' own reading of the field stands in, which is what the check falls
    back to as well.

    **The alcohol content, the net contents and the government warning are
    located by pattern**, so a panel either shows them or does not, and the
    first panel to show one settles it. The warning counts as found when its
    prefix was located, whatever the body says: a defective statement is still
    the statement, and no other panel prints a second one.

    ``declared`` is the text side's values, or empty on a scan.
    """
    for name, strip_code in _SEARCHED_FOR_STOP:
        stated = (declared.get(name) or "").strip()
        if not stated:
            if not any(getattr(parsed, name) is not None for parsed in readings):
                return False
            continue
        comparison, _ = verify_presence(name, stated, units, strip_trailing_code=strip_code)
        if comparison.outcome is not Outcome.MATCH:
            return False
    for name in _PATTERN_FOR_STOP:
        if not any(getattr(parsed, name) is not None for parsed in readings):
            return False
    return any(parsed.warning.found for parsed in readings)


def _merge_artwork(text_side: ParsedApplication, artwork: _ArtworkReading) -> ParsedApplication:
    """Fill what the text layer left empty from the artwork, never the reverse.

    This is the precedence rule, and it is the whole of it on the document side:
    a value the file itself states wins over a value recognized out of a
    picture, because the first is read and the second is guessed at by an OCR
    engine. A typed value beats both, and that decision is made one layer up in
    ``app.verify.resolve_application``.
    """
    values = dict(text_side.values)
    sources = dict(text_side.value_sources)
    value_panels: dict[str, EmbeddedArtwork] = {}
    for name, value in artwork.values.items():
        if values.get(name) is None:
            values[name] = value
            sources[name] = "embedded_artwork"
            value_panels[name] = artwork.value_panels[name]
    # The page the label came from is the first panel that yielded a value,
    # and only when none did the first panel read; the pool itself stays in
    # rank order (2026-09-06).
    first = artwork.first_valued or (artwork.label_panels[0] if artwork.label_panels else None)
    return ParsedApplication(
        values=values,
        fanciful_name=text_side.fanciful_name,
        class_type_code=text_side.class_type_code,
        path=text_side.path,
        value_sources=sources,
        artwork_value_panels=value_panels,
        artwork_images_found=artwork.images_found,
        artwork_images_read=artwork.images_read,
        artwork_images_rejected=artwork.rejected,
        artwork_images_accepted=artwork.accepted,
        artwork_read=artwork.read,
        label_panels=artwork.label_panels,
        label_artwork=None if first is None else first.artwork,
        label_artwork_read=None if first is None else first.read,
    )


def _with_product_type(
    parsed: ParsedApplication, reading: ProductTypeReading | None
) -> ParsedApplication:
    """Fill the beverage type from item 5's boxes, where they answered (ADR 0016).

    **It never overrides a value the document already stated**, which is the same
    precedence every other value follows: an AcroForm radio group and a text layer
    that names exactly one type are both statements the file makes, and a tick
    read off pixels is a recognition of one. A reading that did not clear the
    margin leaves the field exactly as it was, so ``_with_notes`` attaches A-17's
    absence note and the agent chooses.

    The reason is carried into the notes either way, because "the boxes were
    sampled and two were too close to separate" is a different thing for an agent
    to know than "this document did not name one type".
    """
    if reading is None or not _may_overwrite_product_type(parsed):
        return parsed if reading is None else _with_extra_note(parsed, reading.reason)
    if reading.value is None and not reading.sampled:
        return _with_extra_note(parsed, reading.reason)

    values = {**parsed.values, "beverage_type": reading.value}
    sources = dict(parsed.value_sources)
    if reading.value is None:
        sources.pop("beverage_type", None)
    else:
        sources["beverage_type"] = "product_type_box"
    return _with_extra_note(
        _replacing(parsed, values=values, value_sources=sources), reading.reason
    )


def _may_overwrite_product_type(parsed: ParsedApplication) -> bool:
    """Whether a ticked box outranks what is already in the beverage type.

    **A form field outranks it and a text inference does not**, and the
    difference is what each of the two actually is.

    An AcroForm radio group is a statement the file makes: item 5's widget
    records which option is on, and nothing was recognized to get it. A ticked
    box read off the page is a recognition, so it does not overrule that, exactly
    as the embedded artwork does not overrule the text layer (ADR 0010).

    ``_sole_product_type`` is neither. It is an inference from absence: the text
    names one of the three types and not the other two, so it is taken to be
    stating one rather than offering a choice. That holds on a Registry printout
    and it fails on a scan, where OCR dropping two captions produces the same
    evidence and the wrong answer. A ticked box is direct evidence of the thing
    being inferred, so it wins over the inference and only over the inference.

    **In both directions**, which is the part worth stating. Where the boxes were
    located and sampled and no single one stood out, the sampling has established
    that the page offers three options and shows no clear choice among them, and
    that supersedes an inference which only ever meant "the text mentioned one of
    them". A scanned form with nothing ticked used to come back as whichever
    caption OCR happened to read cleanly; it now comes back as not determined,
    which is what the page says.
    """
    current = parsed.values.get("beverage_type")
    if not current:
        return True
    return parsed.value_sources.get("beverage_type") == "embedded_text"


def _with_extra_note(parsed: ParsedApplication, note: str) -> ParsedApplication:
    """Append one note, skipping an empty one."""
    if not note:
        return parsed
    return _replacing(parsed, notes=[*parsed.notes, note])


def _replacing(parsed: ParsedApplication, **changes) -> ParsedApplication:
    """A copy of one reading with some fields changed.

    ``dataclasses.replace`` in a named wrapper, so the several places that need
    it read as what they are doing rather than as a dataclass idiom.
    """
    return replace(parsed, **changes)


def _sourced(parsed: ParsedApplication, source: ValueSource) -> ParsedApplication:
    """Attribute every value a reading found to one source."""
    return ParsedApplication(
        values=parsed.values,
        fanciful_name=parsed.fanciful_name,
        class_type_code=parsed.class_type_code,
        path=parsed.path,
        value_sources={name: source for name, value in parsed.values.items() if value is not None},
    )


def _render_page(document: pdfium.PdfDocument, index: int) -> Image.Image:
    """Rasterize one page, with any filled form fields drawn.

    ``init_forms`` is what puts an unflattened form's values into the pixels.
    Without it a scanned-looking render of a filled form shows the blank
    template, and the OCR fallback would find captions and no answers.
    """
    document.init_forms()
    with _open_page(document, index) as page:
        return _render_at(page, _render_scale(page))


def _render_scale(page) -> float:
    """The scale one page is rasterized at, from the page size and NFR-11.

    Split out so that the item 5 read can render a page **and** convert the text
    layer's page-point coordinates into that render's pixels using the same
    number. Two places computing it separately is exactly how a sample window
    ends up a few pixels off the box it was meant to cover.
    """
    return max(1.0, settings.ocr_long_edge_px / max(page.get_width(), page.get_height()))


def _render_at(page, scale: float) -> Image.Image:
    """One already-open page, rasterized at a given scale and copied.

    Copied before the page is closed. ``to_pil`` can hand back an image sharing
    the bitmap's buffer, and the bitmap is the page's child, so closing the page
    frees it. The copy is the one PDFium-dependent step; the PNG encode is
    Pillow work and is done by the caller after the lock is released
    (finding 25).
    """
    return page.render(scale=scale).to_pil().copy()


# What identifies item 5's page, in the caption the form prints above the three
# boxes. Matched loosely and case-insensitively, because a scan reads it in
# whatever case the form sets it and a different edition may punctuate it
# differently.
_ITEM_FIVE_CAPTION = re.compile(r"type\s+of\s+product", re.IGNORECASE)


def _item_five_page(
    document: pdfium.PdfDocument, pages: int
) -> tuple[Image.Image, list[CaptionBox] | None] | None:
    """Render the page carrying item 5, with its caption boxes where they exist.

    **Every PDFium call for item 5 is here, under the lock**, and nothing
    expensive is: the page comes back as a copied render, and the PNG encode,
    the sampling, and the OCR fallback where a page has no text layer, all
    happen after the lock is released.

    The page is found by its own caption rather than by number. Item 5 is on page
    1 of TTB F 5100.31 (04/2023), and hard-coding that would be the same mistake
    as hard-coding a pixel: the form has editions, a filing can carry a cover
    sheet, and a Registry printout is not this form at all. A document with no
    "TYPE OF PRODUCT" caption anywhere simply has no item 5 to read.

    **The caption boxes come out of the text layer where there is one.** They are
    exact, they cost nothing, and they went through no recognition step, which is
    the same argument that puts the text layer ahead of OCR everywhere else in
    this module. A page with no text layer returns None for them and pays for a
    Tesseract read instead.
    """
    for index in range(pages):
        try:
            with _open_page(document, index) as page:
                textpage = page.get_textpage()
                text = textpage.get_text_bounded()
                if not _ITEM_FIVE_CAPTION.search(text):
                    continue
                scale = _render_scale(page)
                captions = _item_five_captions(textpage, page.get_height(), scale)
                rendered = _render_at(page, scale)
        except Exception as exc:
            # One page that will not render or read is not the document failing.
            # As everywhere else here, the log gets the class name and the page
            # number and nothing the page said (NFR-6).
            logger.warning(
                "item 5 could not be read from this page",
                extra={"page": index + 1, "cause": type(exc).__name__},
            )
            continue
        return rendered, captions
    return None


def _item_five_captions(textpage, page_height: float, scale: float) -> list[CaptionBox] | None:
    """Item 5's three caption boxes from the text layer, in render pixels.

    PDFium reports character boxes in page points with the origin at the bottom
    left; a render puts the origin at the top left and multiplies by the scale.
    Both conversions happen here, so nothing downstream has to know that the two
    coordinate systems differ.

    Returns None where the page carries no usable text layer, which is the signal
    to recognize the captions instead.
    """
    found: list[CaptionBox] = []
    for option, caption in CAPTION_TEXT.items():
        boxes = _search_boxes(textpage, caption)
        if boxes is None:
            continue
        left, bottom, right, top = boxes
        found.append(
            CaptionBox(
                option=option,
                left=left * scale,
                top=(page_height - top) * scale,
                right=right * scale,
                bottom=(page_height - bottom) * scale,
            )
        )
    return found or None


def _search_boxes(textpage, text: str) -> tuple[float, float, float, float] | None:
    """The bounding box of the first occurrence of one caption, in page points."""
    searcher = textpage.search(text, match_case=False)
    try:
        found = searcher.get_next()
        if found is None:
            return None
        start, count = found
        boxes = [textpage.get_charbox(index) for index in range(start, start + count)]
    finally:
        searcher.close()
    usable = [box for box in boxes if box is not None]
    if not usable:
        return None
    return (
        min(box[0] for box in usable),
        min(box[1] for box in usable),
        max(box[2] for box in usable),
        max(box[3] for box in usable),
    )


def read_item_five(page: tuple[bytes, list[CaptionBox] | None] | None) -> ProductTypeReading | None:
    """Decide item 5 from the rendered page, outside the PDFium lock (ADR 0016).

    ``None`` in means the document carried no item 5 page, and ``None`` out means
    exactly what it always meant: the type of product was not determined and the
    agent chooses.
    """
    if page is None:
        return None
    rendered, captions = page
    if captions is None:
        with timing.phase("item_five_ocr"):
            captions = caption_boxes_from_words(word_boxes_from_ocr(rendered))
    return read_product_type(rendered, captions)


def _pdf_text_lines(document: pdfium.PdfDocument, pages: int) -> list[OcrLine]:
    """The text layer, as the same line records the label parser works on.

    Height is zero on every line, exactly as ``app.parse.lines_from_text`` does
    it: a PDF text layer carries no type size this reader needs, and every rule
    here is about which caption a line starts with rather than how big it is.
    """
    lines: list[OcrLine] = []
    position = 0
    for index in range(pages):
        try:
            with _open_page(document, index) as page:
                text = page.get_textpage().get_text_bounded()
        except Exception as exc:
            # As above: the page is skipped, and the log records the class name
            # and the page number rather than anything the page said (NFR-6).
            logger.warning(
                "application document page carried no readable text layer",
                extra={"page": index + 1, "cause": type(exc).__name__},
            )
            continue
        for raw_line in text.splitlines():
            stripped = raw_line.strip()
            if stripped:
                lines.append(OcrLine(text=stripped, confidence=0.0, height=0.0, top=position))
                position += 1
    return lines


# --------------------------------------------------------------------------
# The item map, transcribed from TTB F 5100.31 (04/2023).
# --------------------------------------------------------------------------
#
# The AcroForm field names are the ones the downloaded form actually carries.
# They are matched loosely, on the item number and the caption words, because a
# form saved through a different editor can rewrite the exact string while
# keeping the caption.
_FIELD_NAME_PATTERNS = {
    "brand_name": re.compile(r"\bbrand\s*name\b", re.IGNORECASE),
    "fanciful_name": re.compile(r"\bfanciful\s*name\b", re.IGNORECASE),
}

# Item 5, TYPE OF PRODUCT, is one radio group named "Check Box22" whose three
# widgets export Wine, Spirits and Malt. The names are TTB's; the words on the
# right are the ones this application uses everywhere else.
_PRODUCT_TYPE_FIELD = re.compile(r"check\s*box\s*22|type\s*of\s*product", re.IGNORECASE)
_PRODUCT_TYPE_EXPORTS = {
    "wine": "wine",
    "spirits": "distilled spirits",
    "distilledspirits": "distilled spirits",
    "malt": "malt beverage",
    "maltbeverages": "malt beverage",
}

# Captions this reader takes a value from. Anchored at the start of a line,
# after an optional item number, so that "(e.g., net contents)" inside item 15's
# own caption is not read as a net contents statement.
_VALUE_CAPTIONS: dict[str, re.Pattern[str]] = {
    "brand_name": re.compile(r"^\s*(?:item\s+)?(?:6\s*[.)]\s*)?brand\s+name\b", re.IGNORECASE),
    "fanciful_name": re.compile(
        r"^\s*(?:item\s+)?(?:7\s*[.)]\s*)?fanciful\s+name\b", re.IGNORECASE
    ),
    # Not an item on the form. A Public COLA Registry printout carries it, and
    # captions it "Class/Type Description" alongside a separate
    # "Class/Type Code". The negative lookahead is what keeps the code line from
    # being read as the designation: without it the code line is matched first,
    # because it is printed first, and the description is never reached.
    "class_type": re.compile(
        r"^\s*class\s*(?:/|\s+or\s+|\s+)\s*type(?:\s+(?:designation|description))?\b"
        r"(?!\s*code\b)",
        re.IGNORECASE,
    ),
    "alcohol_content": re.compile(r"^\s*alcohol\s+content\b", re.IGNORECASE),
    "net_contents": re.compile(r"^\s*net\s+contents\b", re.IGNORECASE),
}

# Every caption on the application side of the form, plus the keys a registry
# printout prints. A value stops at the next one of these: it is what keeps
# "6. BRAND NAME (Required)" on a blank form from reading item 7's caption as
# the brand name.
_STOP_CAPTIONS = re.compile(
    r"""^\s*(?:
        (?:item\s+)?\d{1,2}[a-z]?\s*[.)]\s*\S       # any numbered item caption
      | part\s+i{1,3}\b
      | ttb\s+f\s*5100\.31
      | ttb\s+id\b
      | serial\s*\#
      | status\s*:
      | origin\s*:
      | vintage\s*:
      | approval\s+date\b
      | expiration\s+date\b
      | qualifications\b
      | brand\s+name\b
      | fanciful\s+name\b
      | class\s*(?:/|\s+or\s+|\s+)\s*type\b
      | alcohol\s+content\b
      | net\s+contents\b
      | a\.\s*certificate
      | domestic\b
      | imported\b
    )""",
    re.IGNORECASE | re.VERBOSE,
)

# A trailing instruction on a caption, for example "(Required)" or "(If any)".
#
# The brackets are matched loosely on purpose. Tesseract routinely reads an
# opening parenthesis as a brace or a bracket, and a closing one as a 1 or a
# pipe, and this pattern has to run over OCR output as well as over a text
# layer. What is not loosened is the word inside: a bracketed phrase that is not
# one of the form's three instructions is left alone, because it might be part
# of the value.
_CAPTION_QUALIFIER = re.compile(
    r"^\s*[(\[{]\s*(?:required|if\s+any|if\s+on\s+label)\s*[)\]}1|]?", re.IGNORECASE
)

# A caption word left over after the caption above has matched.
#
# **Why this exists.** A Public COLA Registry printout does not print
# "Class/Type:". It prints "Class/Type Description: Kentucky Straight Bourbon
# Whiskey", and the caption pattern that matched "Class/Type" left "Description:"
# at the front of the value, so the class or type was read as
# "Description: Kentucky Straight Bourbon Whiskey" and compared against the
# label as that. The residue is stripped here rather than by lengthening every
# caption pattern, because the same three words attach to more than one caption
# and no value is one of them on its own.
#
# Anchored, and applied only to what is left after a caption has matched, so a
# value that merely contains one of these words keeps it.
_RESIDUAL_CAPTION_WORDS = re.compile(
    r"^[\s:.\-–]*(?:description|designation|code)\b", re.IGNORECASE
)

# "Class/Type Code: 141", which a registry printout prints beside the
# description. Read separately so the code is still recorded where a printout
# splits it from the designation rather than writing "141 - BOURBON WHISKY" on
# one line.
_CLASS_TYPE_CODE_CAPTION = re.compile(
    r"^\s*class\s*(?:/|\s+or\s+|\s+)\s*type\s+code\b", re.IGNORECASE
)

# The code itself, taken from the head of that caption's value.
_LEADING_CODE = re.compile(r"^(\d{1,4})\b")

# The three product types item 5 offers, in the words this application uses.
_PRODUCT_TYPE_WORDS = {
    "wine": re.compile(r"\bwines?\b", re.IGNORECASE),
    "distilled spirits": re.compile(r"\bdistilled\s+spirits\b", re.IGNORECASE),
    "malt beverage": re.compile(r"\bmalt\s+beverages?\b", re.IGNORECASE),
}

# A class or type printed as "141 - BOURBON WHISKY", which is how a registry
# printout carries the code alongside the description. The character class
# carries an en dash alongside the hyphen because a document may be typeset with
# one; this is parsing input, not prose.
_CODED_CLASS_TYPE = re.compile(r"^\s*(\d{1,4})\s*[-–:]\s*(.+)$")

# How many lines below a caption a value may be. Two, because item 8's caption
# runs to three lines on the real form and a value that far below a one-line
# caption is more likely to be the next block than this one's answer.
_VALUE_LOOKAHEAD = 2


def _from_form_fields(document: pdfium.PdfDocument, pages: int) -> ParsedApplication:
    """Read AcroForm field values, which is where a filled-in form keeps them."""
    values: dict[str, str | None] = dict.fromkeys(APPLICATION_FIELDS)
    fanciful: str | None = None

    if document.get_formtype() == pdfium_raw.FORMTYPE_NONE:
        return ParsedApplication(values=values)
    document.init_forms()
    formenv = document.formenv
    if formenv is None:
        return ParsedApplication(values=values)

    for index in range(pages):
        with _open_page(document, index) as page:
            for annotation in _widgets(page):
                name = _widget_text(pdfium_raw.FPDFAnnot_GetFormFieldName, formenv, annotation)
                value = _widget_text(pdfium_raw.FPDFAnnot_GetFormFieldValue, formenv, annotation)
                if _PRODUCT_TYPE_FIELD.search(name) and pdfium_raw.FPDFAnnot_IsChecked(
                    formenv, annotation
                ):
                    export = _widget_text(
                        pdfium_raw.FPDFAnnot_GetFormFieldExportValue, formenv, annotation
                    )
                    values["beverage_type"] = values["beverage_type"] or _product_type(export)
                if not value:
                    continue
                if _FIELD_NAME_PATTERNS["brand_name"].search(name):
                    values["brand_name"] = values["brand_name"] or value
                elif _FIELD_NAME_PATTERNS["fanciful_name"].search(name):
                    fanciful = fanciful or value
                pdfium_raw.FPDFPage_CloseAnnot(annotation)

    return ParsedApplication(values=values, fanciful_name=fanciful, path="form_fields")


def _widgets(page):
    """Every widget annotation on one page, opened for reading."""
    for index in range(pdfium_raw.FPDFPage_GetAnnotCount(page)):
        annotation = pdfium_raw.FPDFPage_GetAnnot(page, index)
        if pdfium_raw.FPDFAnnot_GetSubtype(annotation) == pdfium_raw.FPDF_ANNOT_WIDGET:
            yield annotation
        else:
            pdfium_raw.FPDFPage_CloseAnnot(annotation)


def _widget_text(getter, formenv, annotation) -> str:
    """Call one of PDFium's UTF-16 string getters and return a Python string.

    PDFium's convention is to report the buffer size first and fill it on a
    second call, and it reports it in bytes including the terminator while
    taking a buffer of unsigned shorts. Both halves are handled here so that no
    caller has to know it.
    """
    size = getter(formenv, annotation, None, 0)
    if size <= 0:
        return ""
    buffer = (ctypes.c_ushort * size)()
    getter(formenv, annotation, buffer, size * 2)
    return bytes(buffer).decode("utf-16-le", "ignore").rstrip("\x00").strip()


def _product_type(export: str) -> str | None:
    """Map item 5's export value onto the words this application uses."""
    return _PRODUCT_TYPE_EXPORTS.get(re.sub(r"[^a-z]", "", export.lower()))


def _from_lines(lines: list[OcrLine]) -> ParsedApplication:
    """Read captions and their values out of a document's text."""
    texts = [line.text for line in lines]
    values: dict[str, str | None] = dict.fromkeys(APPLICATION_FIELDS)
    fanciful: str | None = None
    code: str | None = None

    for name, caption in _VALUE_CAPTIONS.items():
        found = _value_for(texts, caption)
        if found is None:
            continue
        if name == "fanciful_name":
            fanciful = found
        elif name == "class_type":
            coded = _CODED_CLASS_TYPE.match(found)
            if coded:
                code, found = coded.group(1), coded.group(2).strip()
            values[name] = found
        else:
            values[name] = found

    if code is None:
        code = _class_type_code(texts)

    values["beverage_type"] = _sole_product_type(texts)
    return ParsedApplication(values=values, fanciful_name=fanciful, class_type_code=code)


def _class_type_code(texts: list[str]) -> str | None:
    """The code from a "Class/Type Code" caption, where the document splits it out."""
    captioned = _value_for(texts, _CLASS_TYPE_CODE_CAPTION)
    if not captioned:
        return None
    digits = _LEADING_CODE.match(captioned)
    return digits.group(1) if digits else None


def _value_for(texts: list[str], caption: re.Pattern[str]) -> str | None:
    """The value printed against one caption, on its line or just below it.

    Two shapes, because the two documents differ. A registry printout puts the
    key and the value on one line separated by a colon; the form puts the
    caption in a box and the value under it. Anything that is itself a caption
    ends the value, so a blank box reads as not found rather than as whatever
    was printed next.
    """
    for index, text in enumerate(texts):
        match = caption.match(text)
        if not match:
            continue
        remainder = _strip_qualifier(text[match.end() :])
        if remainder:
            return remainder
        collected: list[str] = []
        for offset in range(1, _VALUE_LOOKAHEAD + 1):
            if index + offset >= len(texts):
                break
            candidate = texts[index + offset].strip()
            if not candidate or _STOP_CAPTIONS.match(candidate):
                break
            collected.append(candidate)
        # The residue is stripped here too, for the document that wraps a
        # caption onto two lines and prints "Description: ..." on the second.
        joined = _strip_residual_caption(" ".join(collected).strip()).lstrip(" :-–\t").strip()
        return joined or None
    return None


def _strip_qualifier(text: str) -> str:
    """Drop a caption's own instruction, its residual words, and the separator."""
    text = _CAPTION_QUALIFIER.sub("", text)
    text = _strip_residual_caption(text)
    return text.lstrip(" :-–\t").strip()


def _strip_residual_caption(text: str) -> str:
    """Remove caption words the matched pattern left behind.

    Repeated rather than applied once, because a caption can carry more than one
    of them ("Class/Type Designation Description"). Each pass shortens the
    string, so this terminates.
    """
    while True:
        shortened = _RESIDUAL_CAPTION_WORDS.sub("", text, count=1)
        if shortened == text:
            return text
        text = shortened


def _sole_product_type(texts: list[str]) -> str | None:
    """Item 5, when the document names exactly one of the three types.

    **A ticked box cannot be read from text.** Item 5 is three checkboxes, and a
    document's text layer prints the caption of an unticked box exactly as it
    prints the caption of a ticked one, so a form that names all three has said
    nothing about which was chosen. Where a document names one and only one, it
    is stating a product type rather than offering a choice, and that is taken.
    Anything else is not found, and the agent supplies it. Reading an "X" beside
    one of three boxes out of a scan is the kind of guess FR-1 forbids.
    """
    blob = "\n".join(texts)
    present = [name for name, pattern in _PRODUCT_TYPE_WORDS.items() if pattern.search(blob)]
    return present[0] if len(present) == 1 else None


def _combine(preferred: ParsedApplication, fallback: ParsedApplication) -> ParsedApplication:
    """Take each value from the form fields, falling back to the text layer.

    The source of each value is recorded as it is chosen rather than inferred
    afterwards, because the two sides can carry the same value and a reader
    comparing them after the fact cannot tell which one it came from.
    """
    values: dict[str, str | None] = {}
    sources: dict[str, ValueSource] = {}
    for name in APPLICATION_FIELDS:
        from_fields = preferred.values.get(name)
        from_text = fallback.values.get(name)
        values[name] = from_fields or from_text
        if from_fields:
            sources[name] = "form_fields"
        elif from_text:
            sources[name] = "embedded_text"
    return ParsedApplication(
        values=values,
        fanciful_name=preferred.fanciful_name or fallback.fanciful_name,
        class_type_code=preferred.class_type_code or fallback.class_type_code,
        value_sources=sources,
    )


# What to say about a value the document did not carry, where the reason is a
# property of the form rather than of this particular document. Written out
# because "not found" alone invites an agent to go looking for a box that is not
# there (A-17).
_ABSENCE_NOTES = {
    "class_type": (
        "The class or type designation is not an item on TTB F 5100.31 "
        "(04/2023). It appears on the labels affixed to the application, and on "
        "a Public COLA Registry printout. Enter it yourself."
    ),
    "alcohol_content": (
        "The alcohol content is not an item on TTB F 5100.31 (04/2023). It "
        "appears on the labels affixed to the application, and on a Public COLA "
        "Registry printout. Enter it yourself."
    ),
    "net_contents": (
        "The net contents is an item on TTB F 5100.31 (04/2023) only when it is "
        "blown, branded or embossed on the container and does not appear on the "
        "labels (item 15). Otherwise it is on the labels themselves, and on a "
        "Public COLA Registry printout. Enter it yourself."
    ),
    "beverage_type": (
        "The type of product is item 5 on TTB F 5100.31 (04/2023), three check "
        "boxes. A ticked box is not in a document's text, so the boxes are read "
        "off the rendered page instead (ADR 0016); on this document that did not "
        "settle it. Choose it yourself."
    ),
}


# What is said, once, whenever a value or a label side came out of the pictures
# inside the application rather than out of a photograph the agent took
# (ADR 0010). It is a limitation, written down where the reading is reported,
# rather than a caveat left to a document nobody has open.
SELF_CONSISTENCY_NOTE = (
    "Some of this was read from the label artwork inside the application "
    "document. Checking that artwork against the application it came from is a "
    "self-consistency check: it shows that the artwork on file carries the "
    "mandatory elements and agrees with the typed form data. It is not an "
    "independent check of the bottle. Verifying the physical bottle against the "
    "filing still needs a photograph of that bottle."
)


def _with_notes(
    parsed: ParsedApplication,
    *,
    path: ExtractionPath,
    pages_read: int,
    budget: _ReadBudget | None = None,
    pages_not_reached: int = 0,
):
    """Attach the honest explanation for each value the document did not carry.

    A value the embedded artwork supplied gets no absence note, because it is no
    longer absent. What it gets instead is the self-consistency note, once, for
    the whole reading.

    **What the read budget left unread is said in words here** (ADR 0023), as
    well as in the statuses and counts, because the notes are what the
    interface prints under the values and what a batch line carries: a value
    reported not found on a document whose pages or pictures were never
    looked at has to say so where the agent reads it.
    """
    notes = [
        _ABSENCE_NOTES[name]
        for name in APPLICATION_FIELDS
        if parsed.values.get(name) is None and name in _ABSENCE_NOTES
    ]
    panels_not_reached = sum(
        1 for image in parsed.artwork_images_accepted if image.status == "not_reached"
    )
    if budget is not None and (pages_not_reached or panels_not_reached):
        notes.append(_budget_note(budget, pages_not_reached, panels_not_reached))
    # Notes a step upstream already attached, kept rather than rebuilt over.
    # The item 5 sampling reason is one of these, and it is the sentence that
    # says *why* the boxes did not settle it, which is a different thing for an
    # agent to know from the absence note above (ADR 0016).
    notes.extend(parsed.notes)
    from_artwork = "embedded_artwork" in parsed.value_sources.values()
    if from_artwork or parsed.label_artwork is not None:
        notes.append(SELF_CONSISTENCY_NOTE)
    return replace(
        parsed,
        path=path,
        pages_read=pages_read,
        notes=notes,
        tesseract_reads=0 if budget is None else budget.spent,
        read_budget=settings.max_document_reads if budget is None else budget.limit,
        read_budget_reached=False if budget is None else budget.reached,
        pages_not_reached=pages_not_reached,
    )


def _budget_note(budget: _ReadBudget, pages: int, panels: int) -> str:
    """The sentence that says what the budget did not get to, in the voice of
    the artwork table's own "not read" copy."""
    left: list[str] = []
    if pages:
        left.append(f"{pages} page{'s' if pages != 1 else ''}")
    if panels:
        left.append(f"{panels} picture{'s' if panels != 1 else ''}")
    return (
        f"{' and '.join(left)} of this application {'were' if pages + panels != 1 else 'was'} "
        f"not read: the limit on how much reading one application may cost, "
        f"{budget.limit} read{'s' if budget.limit != 1 else ''}, was reached after "
        f"{budget.spent}. Any value reported "
        "not found may be on what was not read."
    )


# What the prefill pass says about a document with no text layer (ADR 0024).
DEFERRED_PAGES_NOTE = (
    "This file has no text to read, so its pages will be read as pictures when "
    "the label is checked, the way a label image is read. Nothing has been taken "
    "from it yet."
)
