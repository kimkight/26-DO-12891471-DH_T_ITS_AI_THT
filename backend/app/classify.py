"""Decide what each uploaded file is, from the file, not from the box it came in.

Governing requirements: FR-12 (one upload accepting PDFs and images in any mix),
FR-11 (the label application as the input), FR-1 (label artwork), FR-9 (a
message that names the problem), NFR-3 (no outbound call), NFR-6 (nothing is
persisted and no file content reaches the logs).
Decision reference: [ADR 0011](../../docs/adr/0011-one-upload.md).

**Why classify at all.** Before this, the interface asked for two different
things in two different places, and the server believed whichever box a file
arrived in. An agent who dropped their COLA PDF into the photo picker got it
read as label artwork; an agent who dropped a photograph into the application
picker got it read as a form. The box is a guess about intent, and the file
itself is the fact.

**The rule, in full.**

1. A file whose bytes begin with ``%PDF``, or which declares
   ``application/pdf``, is the **application side**. The bytes are checked
   first: a browser labels a file from its extension, which an agent can
   rename, and the header is what the file is. Nothing is decoded, and no OCR
   runs, to reach this answer.
2. An image is read once through the ordinary OCR pipeline, and what comes back
   decides it. If the text carries a COLA form or Public COLA Registry marker,
   or the application parser finds at least one mapped value in it, it is the
   **application side**. Otherwise it is a **label side**.
3. An image that cannot be decoded at all is a **label side**, carrying its
   error. That is deliberate: FR-9's message for an unreadable photograph tells
   an agent to send a better one, which is what they need to hear, and routing
   an undecodable file to the application parser would produce a message about
   a document instead.

**Each image is read exactly once.** The ``OcrResult`` produced here is handed
back with the classification and reused by whichever path the file lands on, so
classifying costs nothing beyond the read that path was going to pay for
anyway. That is the reason this module returns the read rather than a verdict
alone.

Nothing here is persisted and nothing about a file's content reaches the logs
(NFR-6).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

from app.application_form import PDF_MAGIC, reads_as_application
from app.ocr import OcrResult, UndecodableImageError, extract_text

FileSide = Literal["application_document", "label_image"]

# Why one file was classified as it was. A stable machine value; the sentence an
# agent reads is built from it in `describe`.
ClassificationBasis = Literal[
    "pdf_header",
    "declared_pdf",
    "form_markers",
    "form_values",
    "no_form_markers",
    "undecodable",
]

# Text that only a COLA application or a Public COLA Registry page carries.
#
# These are printed strings from the documents themselves, not inferences about
# them: the form number and its OMB control number appear on every copy of
# TTB F 5100.31, the title runs across the top of the application, and a
# Registry detail page names itself. They are matched loosely because this runs
# over OCR output, where a space or a full stop routinely goes missing.
_FORM_MARKERS = (
    re.compile(r"ttb\s*f\s*5100\.?\s*31", re.IGNORECASE),
    re.compile(r"omb\s*no\.?\s*1513[-\s]?0020", re.IGNORECASE),
    re.compile(
        r"application\s+for\s+and\s+certification\s*/?\s*exemption\s+of\s+label",
        re.IGNORECASE,
    ),
    re.compile(r"public\s+cola\s+registry", re.IGNORECASE),
    re.compile(r"alcohol\s+and\s+tobacco\s+tax\s+and\s+trade\s+bureau", re.IGNORECASE),
)


@dataclass(frozen=True)
class SubmittedFile:
    """One uploaded part, already read into memory.

    ``content_type`` travels with the bytes because the media-type check has to
    happen before anything is decoded (NFR-7), and by this point the
    ``UploadFile`` it came from may already be closed.
    """

    filename: str
    content_type: str | None
    content: bytes


@dataclass(frozen=True)
class ClassifiedFile:
    """What one uploaded file was judged to be, and on what evidence.

    ``read`` is the OCR result for an image, so the path this file lands on does
    not read it a second time. It is ``None`` for a PDF, which reaches its
    answer from its first four bytes.

    ``error`` is set only for an image that could not be decoded. It is carried
    rather than raised so that one bad file does not cost an agent the others,
    which is the FR-8 rule applied to a single submission.
    """

    file: SubmittedFile
    side: FileSide
    basis: ClassificationBasis
    read: OcrResult | None = None
    error: str | None = None

    @property
    def filename(self) -> str:
        return self.file.filename


def is_pdf(content: bytes, content_type: str | None) -> bool:
    """Whether these bytes are a PDF. The header wins over the declared type."""
    return content.startswith(PDF_MAGIC) or content_type == "application/pdf"


def looks_like_application(result: OcrResult) -> bool:
    """Whether text read off an image is a COLA document rather than a label.

    Two tests, and either is enough. A printed marker is the strong one: a label
    does not print the form's own number, its OMB control number, the bureau's
    name or the Registry's. Finding a mapped caption value is the weaker one,
    and it is here because a photograph of a form may be cropped past the
    letterhead; a label carries no ``BRAND NAME:`` caption, because a label
    prints the brand rather than captioning it.
    """
    if any(marker.search(result.text) for marker in _FORM_MARKERS):
        return True
    return reads_as_application(result.lines)


def classify(files: list[SubmittedFile]) -> list[ClassifiedFile]:
    """Classify every uploaded file. Reads each image exactly once."""
    return [_classify_one(file) for file in files]


def _classify_one(file: SubmittedFile) -> ClassifiedFile:
    if is_pdf(file.content, file.content_type):
        return ClassifiedFile(
            file=file,
            side="application_document",
            basis="pdf_header" if file.content.startswith(PDF_MAGIC) else "declared_pdf",
        )

    try:
        result = extract_text(file.content)
    except UndecodableImageError as exc:
        return ClassifiedFile(file=file, side="label_image", basis="undecodable", error=str(exc))

    if any(marker.search(result.text) for marker in _FORM_MARKERS):
        return ClassifiedFile(
            file=file, side="application_document", basis="form_markers", read=result
        )
    if reads_as_application(result.lines):
        return ClassifiedFile(
            file=file, side="application_document", basis="form_values", read=result
        )
    return ClassifiedFile(file=file, side="label_image", basis="no_form_markers", read=result)


# What each basis means, in the words an agent reads. Written out rather than
# generated, because "we could not open this file" and "this does not look like
# a form" lead an agent to different next actions.
_REASONS: dict[ClassificationBasis, str] = {
    "pdf_header": "This is a PDF, so we read it as the label application.",
    "declared_pdf": "This was sent as a PDF, so we read it as the label application.",
    "form_markers": (
        "This picture carries the wording of a COLA application, so we read it as "
        "the label application rather than as a label."
    ),
    "form_values": (
        "This picture reads as a filled-in COLA application, so we read it as the "
        "label application rather than as a label."
    ),
    "no_form_markers": "We read this picture as a label.",
    "undecodable": "We could not open this file. We tried to read it as a label.",
}


def describe(classified: ClassifiedFile) -> str:
    """One sentence saying what this file was taken to be, and why."""
    return _REASONS[classified.basis]
