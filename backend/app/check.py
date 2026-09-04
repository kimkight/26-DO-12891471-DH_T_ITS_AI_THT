"""The single-label check, as one function both routes call.

Governing requirements: FR-12 (one upload, sorted by the tool), FR-11 (the
application document as the input), FR-1 through FR-7 (what is compared), FR-9
(a message that names the problem and carries no field outcomes), NFR-1 (each
image is read once), NFR-6 (nothing is kept).
Decision references: [ADR 0011](../../docs/adr/0011-one-upload.md) for the
classification, [ADR 0010](../../docs/adr/0010-embedded-label-artwork.md) for
the artwork inside a document standing in as the label side,
[ADR 0020](../../docs/adr/0020-batch-items-are-derived.md) for why this is a
module of its own.

**Why this is not in `api.py` any more.** Until v1.4.0 this was the body of
`POST /api/verify`, and the batch path had a check of its own that took one
image and one document and knew nothing about classification or embedded
artwork. That is how the bulk page fell a generation behind the single-label
page: every rule added to one had to be added to the other, and three were
not. Now a batch row *is* this function. A row that holds a filed application
and nothing else is checked against the artwork inside it; a row that holds a
photograph and nothing else is checked for what a label must carry; a row that
holds both is the ordinary pair. There is one place the rules live, and the
batch cannot fall behind again without this file changing.

Two entry points. ``check_one_label`` takes the files as they were uploaded and
sorts them first, which is what the single-label route wants. ``check_sorted``
takes files already sorted, which is what the batch path wants, because it has
to look at the sorting before it decides whether a row is one label at all.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.application_form import (
    EmbeddedArtwork,
    UnreadableDocumentError,
    parse_application_document,
)
from app.classify import ClassifiedFile, SubmittedFile, classify, describe
from app.config import settings
from app.ocr import OcrResult
from app.schemas import FileClassification, VerificationResult
from app.verify import (
    NO_LABEL_MESSAGE,
    LabelSource,
    VerificationError,
    document_result,
    resolve_application,
    verify_photos,
)


@dataclass(frozen=True)
class Checked:
    """What a check hands back, for the response and for the log."""

    result: VerificationResult
    sorted_files: list[ClassifiedFile]
    documents_classified: int
    photos_read: int
    document_bytes: int


def classification(entry: ClassifiedFile, used: bool = True) -> FileClassification:
    """One sorted file, as the response reports it (FR-12)."""
    return FileClassification(
        filename=entry.filename,
        classified_as=entry.side,
        basis=entry.basis,
        reason=describe(entry),
        used=used,
    )


def check_one_label(
    submitted: list[SubmittedFile],
    application_values: dict[str, str],
    cleared_fields: frozenset[str] = frozenset(),
) -> Checked:
    """Sort, read and compare one label's files. Raises `VerificationError`.

    This is the body of `POST /api/verify` from the moment the parts are in
    memory. It is synchronous on purpose: everything in it is Tesseract and
    PDFium work, and the caller is what keeps it off the event loop.

    Classification happens before anything is compared, and reads each image
    exactly once; the read is handed on to whichever side the file lands on
    (ADR 0011).
    """
    return check_sorted(classify(submitted), application_values, cleared_fields)


def check_sorted(
    sorted_files: list[ClassifiedFile],
    application_values: dict[str, str],
    cleared_fields: frozenset[str] = frozenset(),
) -> Checked:
    """Read and compare one label whose files are already sorted.

    ``application_values`` are the agent's typed values, empty on the batch
    path where nothing is typed; ``cleared_fields`` are the ones an agent
    emptied after a document filled them (code review finding 29).
    """
    documents = [entry for entry in sorted_files if entry.side == "application_document"]
    labels = [entry for entry in sorted_files if entry.side == "label_image"]

    # Counted after sorting and before anything is compared, and named in the
    # message (FR-9, NFR-7). The bodies are in memory by now; the guarantee
    # kept here is that no photograph is verified.
    if len(labels) > settings.max_label_photos:
        raise VerificationError(
            code="too_many_photos",
            message=(
                f"{len(labels)} pictures of the label were submitted. Send at "
                f"most {settings.max_label_photos} pictures of the same label, "
                "or use the batch tab for many different labels."
            ),
            status_code=413,
            limit=f"maximum photographs of one label: {settings.max_label_photos}",
        )
    if len(documents) > 1:
        raise VerificationError(
            code="too_many_application_documents",
            message=(
                f"{len(documents)} of the files you sent read as label "
                "applications. Send one application for one label, plus any "
                "photos of that label."
            ),
            status_code=413,
            limit="maximum application documents for one label: 1",
        )

    document_bytes = 0
    parsed_application = None
    if documents:
        document = documents[0]
        document_bytes = len(document.file.content)
        try:
            parsed_application = parse_application_document(
                document.file.content,
                document.file.content_type,
                pre_read=document.read,
            )
        except UnreadableDocumentError as exc:
            # FR-9 applied to the application side: the message names the
            # problem and the response carries no field outcomes at all. The
            # typed path is still open, and the message says so.
            raise VerificationError(
                code="unreadable_application_document", message=str(exc)
            ) from exc

    contents = [entry.file.content for entry in labels]
    pre_read: list[OcrResult | None] = [entry.read for entry in labels]

    # The label side, decided before anything is compared. Pictures the
    # agent supplied always win: a picture of the bottle in front of them is
    # evidence about that bottle, and the artwork on file is not.
    label_source: LabelSource = "uploaded_photographs"
    panels: list[EmbeddedArtwork] | None = None
    if not contents:
        label_panels = parsed_application.label_panels if parsed_application else []
        if not label_panels:
            raise VerificationError(code="no_label_to_check", message=NO_LABEL_MESSAGE)
        # **Every panel that read is the label side, pooled** (ADR 0010 as
        # amended, #121). A filing that embeds its labels as separate panels
        # puts the brand on the front and the alcohol content on the back; the
        # check takes all of them the way ADR 0007 takes three photographs of
        # one bottle, and each value says which panel it was found on.
        contents = [panel.artwork.content for panel in label_panels]
        panels = [panel.artwork for panel in label_panels]
        # **The reads come with them, so no picture is read twice** (NFR-1).
        # `parse_application_document` has just put these exact bytes through
        # this exact pipeline to fill the application values; running them
        # through it again produced an identical result for a second full
        # Tesseract pass, which measurement on 2026-08-30 showed was about
        # half of this path's total time. This is the same reuse ADR 0011
        # already does with the classifier's read.
        pre_read = [panel.read for panel in label_panels]
        label_source = "application_artwork"

    application, sources = resolve_application(
        application_values, parsed_application, cleared_fields
    )
    result = verify_photos(
        contents,
        application,
        application_sources=sources,
        application_document=(document_result(parsed_application) if parsed_application else None),
        label_source=label_source,
        pre_read=pre_read,
        panels=panels,
    )
    result.files = [classification(entry) for entry in sorted_files]
    return Checked(
        result=result,
        sorted_files=sorted_files,
        documents_classified=len(documents),
        photos_read=len(contents),
        document_bytes=document_bytes,
    )
