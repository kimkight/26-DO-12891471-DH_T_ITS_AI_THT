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

Nothing in this module opens a socket. ``pytesseract`` runs the Tesseract binary
that ships in the container image, and OpenCV works on the decoded array in
memory. That is what makes the default path work with egress blocked, which is
the environment Marcus Williams describes.

Nothing is written to disk either (NFR-6). The image is decoded from the request
bytes into a numpy array and released with the request.

``OMP_THREAD_LIMIT`` is pinned below. See the comment there: it is what lets the
batch path call this from a worker thread at all.
"""

from __future__ import annotations

import io
import os
import time
from dataclasses import dataclass, field
from typing import Literal

# Tesseract is built against OpenMP, and its OpenMP runtime deadlocks when the
# binary is invoked from a thread other than the process's main thread. The
# single-label path never hit this: `POST /api/verify` is an async handler, so
# extract_text runs on the event loop thread. The batch path (FR-8, ADR 0006)
# runs it in a worker pool, and without this the Tesseract child process never
# exits and the batch hangs rather than failing.
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

from app.config import settings  # noqa: E402

# The EXIF tag that records which way up the camera was held. Pillow exposes it
# by number rather than by name, and 1 means "already upright".
_EXIF_ORIENTATION_TAG = 0x0112

# The four quarter-turns. Anything else is a skew, which deskew handles.
CARDINAL_ROTATIONS = (0, 90, 180, 270)

# How Tesseract reports a hopeless orientation call. Both of the two misreads in
# the measurement recorded in ADR 0003 and A-15 came back below this, and every
# correct answer in that run came back above it, so it is carried on the result
# as the caveat rather than used to override the answer: there is nothing better
# to fall back to. See docs/07_TEST_STRATEGY.md section 2.
LOW_ORIENTATION_CONFIDENCE = 1.0

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
PREPROCESS_SHORT_CIRCUIT_CONFIDENCE = 85.0


class UndecodableImageError(Exception):
    """The bytes submitted could not be decoded as an image (FR-9)."""


@dataclass(frozen=True)
class OcrLine:
    """One line of recognized text, with the evidence needed to rank it.

    ``height`` is the mean glyph box height of the words in the line, in pixels
    of the preprocessed image. It is the only signal available for telling a
    brand name from body text, because Tesseract reports geometry per word and
    reports nothing about typeface.
    """

    text: str
    confidence: float
    height: float
    top: int


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
    orientation and script detection answered, ``unavailable`` when it could not
    (too little text to judge, or no ``osd`` training data installed), and
    ``disabled`` when ``TTB_CORRECT_ORIENTATION`` is off.
    """

    exif_orientation: int | None = None
    exif_transposed: bool = False
    rotation_degrees: int = 0
    method: Literal["osd", "unavailable", "disabled"] = "disabled"
    confidence: float | None = None

    @property
    def low_confidence(self) -> bool:
        """True when Tesseract answered but had almost nothing to go on."""
        return (
            self.method == "osd"
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
    """The two images OCR may read, and how both were turned to get there.

    ``binary`` is the preprocessed image: grayscale, scaled, adaptively
    thresholded and deskewed. ``gray`` is the same pixels with none of that
    done to them, scaled and turned upright and nothing more. Both exist
    because preprocessing is not reliably an improvement; see the module
    docstring and ``extract_text``.
    """

    binary: np.ndarray
    gray: np.ndarray
    orientation: Orientation


@dataclass(frozen=True)
class ReadPath:
    """Which of the two images was read, and what each of them scored.

    ``variant`` is the one whose words were kept. ``preprocessed_confidence`` is
    always present because the preprocessed read always runs.
    ``plain_confidence`` is null when the preprocessed read scored well enough
    that the plain one was never run, which is the common case and the reason
    the second read costs nothing on artwork that reads cleanly.
    """

    variant: Literal["preprocessed", "plain"] = "preprocessed"
    preprocessed_confidence: float = 0.0
    plain_confidence: float | None = None


@dataclass(frozen=True)
class OcrResult:
    """Everything the extraction step produces, and nothing about compliance."""

    text: str
    mean_confidence: float
    elapsed_ms: float
    lines: list[OcrLine] = field(default_factory=list)
    orientation: Orientation = Orientation()
    read_path: ReadPath = ReadPath()

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
) -> Prepared:
    """Scale and turn upright, then produce both the plain and the binary image.

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

    resized = resize_long_edge(decoded.pixels)
    gray = cv2.cvtColor(resized, cv2.COLOR_BGR2GRAY) if resized.ndim == 3 else resized

    if correct:
        degrees, confidence, method = detect_orientation(gray)
        gray = rotate_cardinal(gray, degrees)
    else:
        degrees, confidence, method = 0, None, "disabled"

    binary = cv2.adaptiveThreshold(
        cv2.medianBlur(gray, 3), 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 31, 15
    )

    if deskew_image:
        inverted = cv2.bitwise_not(binary)
        binary = deskew(binary, inverted)

    return Prepared(
        binary=binary,
        gray=gray,
        orientation=Orientation(
            exif_orientation=decoded.exif_orientation,
            exif_transposed=decoded.exif_transposed,
            rotation_degrees=degrees,
            method=method,
            confidence=None if confidence is None else round(confidence, 2),
        ),
    )


def extract_text(
    image_bytes: bytes,
    *,
    deskew_image: bool = True,
    correct_orientation: bool | None = None,
) -> OcrResult:
    """Run the full local extraction path and time it.

    **Preprocessing has to earn the read it is given.** The preprocessed image is
    read first. If it comes back at or above
    ``PREPROCESS_SHORT_CIRCUIT_CONFIDENCE`` the answer is kept and nothing else
    runs, which is what happens on eleven of the twelve sample labels. Otherwise
    the plain upright grayscale is read too and the higher-scoring of the two is
    kept. Which one won, and what both scored, go out on the result.

    This is the same shape as the rotation decision one level up: do the thing
    that usually helps, then check that it did. The cost is one extra Tesseract
    invocation on the images where preprocessing did not score well, roughly
    doubling the per-label OCR time in that case and leaving it unchanged
    otherwise. It is paid on the batch path too, per image. Measured figures are
    in docs/07_TEST_STRATEGY.md section 4.

    Ranking by mean word confidence works here where it does not work for
    rotation (A-15), and for a reason that does not generalize between the two:
    Tesseract's layout analysis silently corrects a quarter-turn, so it returns
    identical scores for the two rotations that have to be told apart, but it
    does nothing of the kind for thresholding, so the two images genuinely score
    differently.

    The elapsed time is returned rather than logged, because NFR-1 requires the
    latency to be measured and reported rather than asserted, and NFR-6 forbids
    putting anything about the request in the logs.
    """
    started = time.perf_counter()
    decoded = decode(image_bytes)
    prepared = preprocess(
        decoded, deskew_image=deskew_image, correct_orientation=correct_orientation
    )

    preprocessed_lines, preprocessed_confidence = _read(prepared.binary)
    if preprocessed_confidence >= PREPROCESS_SHORT_CIRCUIT_CONFIDENCE:
        lines, mean_confidence = preprocessed_lines, preprocessed_confidence
        read_path = ReadPath(
            variant="preprocessed",
            preprocessed_confidence=round(preprocessed_confidence, 1),
            plain_confidence=None,
        )
    else:
        plain_lines, plain_confidence = _read(prepared.gray)
        plain_wins = plain_confidence > preprocessed_confidence
        lines = plain_lines if plain_wins else preprocessed_lines
        mean_confidence = plain_confidence if plain_wins else preprocessed_confidence
        read_path = ReadPath(
            variant="plain" if plain_wins else "preprocessed",
            preprocessed_confidence=round(preprocessed_confidence, 1),
            plain_confidence=round(plain_confidence, 1),
        )

    elapsed_ms = (time.perf_counter() - started) * 1000
    return OcrResult(
        text="\n".join(line.text for line in lines),
        mean_confidence=round(mean_confidence, 1),
        elapsed_ms=round(elapsed_ms, 1),
        lines=lines,
        orientation=prepared.orientation,
        read_path=read_path,
    )


def _read(image: np.ndarray) -> tuple[list[OcrLine], float]:
    """Read one prepared image and return its lines and mean word confidence."""
    data = pytesseract.image_to_data(image, lang="eng", output_type=Output.DICT)
    lines, confidences = _assemble_lines(data)
    mean_confidence = float(sum(confidences) / len(confidences)) if confidences else 0.0
    return lines, mean_confidence


def _assemble_lines(data: dict) -> tuple[list[OcrLine], list[float]]:
    """Group Tesseract's word rows into lines, keeping confidence and size."""
    grouped: dict[tuple[int, int, int, int], list[int]] = {}
    for index, word in enumerate(data.get("text", [])):
        if not str(word).strip():
            continue
        if float(data["conf"][index]) < 0:
            continue
        key = (
            data["page_num"][index],
            data["block_num"][index],
            data["par_num"][index],
            data["line_num"][index],
        )
        grouped.setdefault(key, []).append(index)

    lines: list[OcrLine] = []
    confidences: list[float] = []
    for key in sorted(grouped, key=lambda k: (k[0], min(data["top"][i] for i in grouped[k]))):
        indices = grouped[key]
        words = [str(data["text"][i]).strip() for i in indices]
        word_confidences = [float(data["conf"][i]) for i in indices]
        heights = [float(data["height"][i]) for i in indices]
        confidences.extend(word_confidences)
        lines.append(
            OcrLine(
                text=" ".join(words),
                confidence=round(sum(word_confidences) / len(word_confidences), 1),
                height=round(sum(heights) / len(heights), 1),
                top=min(int(data["top"][i]) for i in indices),
            )
        )
    return lines, confidences
