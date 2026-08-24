"""Local OCR: OpenCV preprocessing, then Tesseract word-level recognition.

Governing requirements: FR-1 (extract the five fields from label artwork),
NFR-1 (about 5 seconds per label, so elapsed time is measured and returned),
NFR-3 (no outbound network call on the default path), FR-9 (an undecodable
image and an image with no text are distinct failures). Decision reference:
D-4, ADR 0003.

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

import os
import time
from dataclasses import dataclass, field

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
from pytesseract import Output  # noqa: E402

from app.config import settings  # noqa: E402


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
class OcrResult:
    """Everything the extraction step produces, and nothing about compliance."""

    text: str
    mean_confidence: float
    elapsed_ms: float
    lines: list[OcrLine] = field(default_factory=list)

    @property
    def has_text(self) -> bool:
        return bool(self.text.strip())


def decode(image_bytes: bytes) -> np.ndarray:
    """Decode image bytes into a BGR array.

    Raises ``UndecodableImageError`` rather than returning an empty array, so
    that the caller cannot mistake a failed decode for a blank label. FR-9
    requires those two to read differently to the agent.
    """
    if not image_bytes:
        raise UndecodableImageError("The uploaded file was empty.")
    buffer = np.frombuffer(image_bytes, dtype=np.uint8)
    image = cv2.imdecode(buffer, cv2.IMREAD_COLOR)
    if image is None:
        raise UndecodableImageError(
            "The file could not be decoded as an image. It may be corrupt or truncated."
        )
    return image


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


def preprocess(image: np.ndarray, *, deskew_image: bool = True) -> np.ndarray:
    """Grayscale, scale, adaptive threshold, and optionally deskew.

    Adaptive thresholding rather than a global one, because Jenny Park's
    "the lighting is bad, or there's glare on the bottle" is uneven illumination
    across one image, which is exactly the case a global threshold handles worst.
    """
    resized = resize_long_edge(image)
    gray = cv2.cvtColor(resized, cv2.COLOR_BGR2GRAY) if resized.ndim == 3 else resized
    gray = cv2.medianBlur(gray, 3)
    binary = cv2.adaptiveThreshold(
        gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 31, 15
    )
    if deskew_image:
        inverted = cv2.bitwise_not(binary)
        binary = deskew(binary, inverted)
    return binary


def extract_text(image_bytes: bytes, *, deskew_image: bool = True) -> OcrResult:
    """Run the full local extraction path and time it.

    The elapsed time is returned rather than logged, because NFR-1 requires the
    latency to be measured and reported rather than asserted, and NFR-6 forbids
    putting anything about the request in the logs.
    """
    started = time.perf_counter()
    image = decode(image_bytes)
    prepared = preprocess(image, deskew_image=deskew_image)
    data = pytesseract.image_to_data(prepared, lang="eng", output_type=Output.DICT)
    lines, confidences = _assemble_lines(data)
    text = "\n".join(line.text for line in lines)
    mean_confidence = float(sum(confidences) / len(confidences)) if confidences else 0.0
    elapsed_ms = (time.perf_counter() - started) * 1000
    return OcrResult(
        text=text,
        mean_confidence=round(mean_confidence, 1),
        elapsed_ms=round(elapsed_ms, 1),
        lines=lines,
    )


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
