"""Batch verification: pairing by filename stem, a bounded worker pool, an NDJSON stream.

Governing requirements: FR-8 (many labels in one submission, per-label results,
the count limit refused before anything is processed, every result naming its
label, and pairing failures reported per row), FR-9 (one unreadable image, or
one unreadable document, is that row's error rather than the batch's), FR-11
(the application side of every row is read off the applicant's own COLA
document), NFR-2 (the batch does not fail as a whole and its progress is
observable), NFR-6 (nothing is persisted and no field value reaches the logs),
NFR-7 (the file count is checked before processing).
Decision references: [ADR 0006](../../docs/adr/0006-batch-execution-model.md)
for the stream, [ADR 0009](../../docs/adr/0009-batch-cola-documents.md) for what
a batch is made of, [ADR 0008](../../docs/adr/0008-cola-form-as-application-input.md)
for how one document is read.

**A batch is label images plus COLA documents, paired by filename stem.**
``0001-stones-throw.png`` pairs with ``0001-stones-throw.pdf``: the stem is the
filename with its final extension removed, compared without regard to case. Each
document is read by the FR-11 parser, and what it says is the application side
for that label. There is no CSV. A-14, which invented one, is superseded by
ADR 0009: no source ever stated that format, and what an importer actually files
with TTB is, per application, a COLA form plus label images.

**Why a stream rather than a response body.** ADR 0006 rules out an
asynchronous job model because D-9 forbids the persistence one needs, and rules
out a single buffered response because 300 labels at about 5 seconds each is
about 25 minutes in one request, which exceeds every idle timeout between the
browser and the application and produces exactly the frozen page NFR-2 forbids.
What is left is one request whose body arrives in pieces. The response stream is
the only copy of the results; there is no job store and nothing is written to
disk.

**What is deliberately not here.** No retry, no partial resubmission, and no
resume. A dropped connection loses the batch, which ADR 0006 records as the
direct cost of having no job store. One photograph per label, too: ADR 0007's
several photographs of one label stay on the single-label path, because a stem
that paired several images to one document would need a rule for a group only
partly readable, and no source asks for one (ADR 0009).
"""

from __future__ import annotations

import logging
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field

from app import timing
from app.application_form import UnreadableDocumentError, parse_application_document
from app.config import settings
from app.schemas import BatchLine, ErrorDetail, VerificationResult
from app.verify import (
    VerificationError,
    check_document_media_type,
    check_media_type,
    check_size,
    document_result,
    resolve_application,
    verify_image,
)

logger = logging.getLogger(__name__)


def pairing_stem(filename: str) -> str:
    """The key both sides of a pair are matched on (ADR 0009).

    The filename with its final extension removed, folded to lower case. Case is
    folded because an agent's file manager and an agent's scanner disagree about
    it routinely and a pairing that failed on `.PDF` against `.pdf` would be a
    puzzle rather than an error. Only the final extension is removed, so
    ``0001-stones-throw.front.png`` has the stem ``0001-stones-throw.front`` and
    pairs with ``0001-stones-throw.front.pdf`` rather than with
    ``0001-stones-throw.pdf``.

    Any directory part a browser sends with a `webkitdirectory` selection is
    dropped, because the pairing is on names rather than on paths.
    """
    name = filename.strip().rsplit("/", 1)[-1].rsplit("\\", 1)[-1]
    base, separator, _ = name.rpartition(".")
    return (base if separator and base else name).casefold()


@dataclass(frozen=True)
class SubmittedImage:
    """One label image part, already read into memory.

    ``content_type`` is kept alongside the bytes because the media type check
    has to happen before anything is decoded (NFR-7), and by this point the
    ``UploadFile`` it came from may already be closed.
    """

    filename: str
    content_type: str | None
    content: bytes


@dataclass(frozen=True)
class SubmittedDocument:
    """One COLA document part, already read into memory (FR-11, ADR 0009)."""

    filename: str
    content_type: str | None
    content: bytes


@dataclass
class DocumentTable:
    """The submitted COLA documents, keyed by pairing stem, plus what was wrong.

    ``duplicates`` is a set rather than a count because two documents on one
    stem make that one pair ambiguous and leave every other pair usable. FR-8
    asks for "a per-row or batch-level error that names the problem", and per
    row is the more useful of the two here: one repeated stem should not cost an
    agent the other 299 results.
    """

    documents: dict[str, SubmittedDocument] = field(default_factory=dict)
    duplicates: set[str] = field(default_factory=set)


def collect_documents(documents: list[SubmittedDocument]) -> DocumentTable:
    """Key the submitted documents by pairing stem (ADR 0009).

    Nothing is parsed here. Reading a document costs about what reading a label
    photograph costs when it falls back to OCR, so it is done inside the worker
    pool, per row, where it is both parallelized and attributable to the row it
    belongs to.
    """
    table = DocumentTable()
    for document in documents:
        stem = pairing_stem(document.filename)
        if not stem:
            # A part with no usable name cannot be paired with anything and
            # cannot be reported against a label either. It is counted in the
            # completion log and otherwise ignored.
            continue
        if stem in table.documents:
            table.duplicates.add(stem)
            continue
        table.documents[stem] = document
    return table


def over_count_error(count: int, *, part: str = "images") -> ErrorDetail:
    """The FR-8 refusal, which names the limit and happens before processing."""
    return ErrorDetail(
        code="batch_too_large",
        message=(
            f"This batch has {count} {part}, which is more than this service "
            "accepts in one submission. Split it into smaller batches and send "
            "them one after another."
        ),
        limit=f"maximum labels per batch: {settings.max_batch_files}",
    )


def plan(images: list[SubmittedImage], table: DocumentTable) -> tuple[list[str], int]:
    """Reconcile the two sides and say how many lines will be emitted.

    Returns the filenames of the documents that paired with no image, and the
    total line count. The total is known before any OCR runs, which is what lets
    the first line of the stream carry it and a client render "1 of 300"
    immediately (NFR-2).

    Every submitted image produces exactly one line, whether it verifies or
    errors, and every unpaired document produces one more.
    """
    stems = {pairing_stem(image.filename) for image in images}
    unpaired = [
        document.filename for stem, document in table.documents.items() if stem not in stems
    ]
    return unpaired, len(images) + len(unpaired)


def _row_error(
    image: SubmittedImage, table: DocumentTable, image_stems: dict[str, int]
) -> ErrorDetail | None:
    """The pairing failures that stop one image being verified (FR-8, ADR 0009)."""
    stem = pairing_stem(image.filename)
    if image_stems.get(stem, 0) > 1:
        return ErrorDetail(
            code="duplicate_label_stem",
            message=(
                f"More than one image in this batch is named {stem} before its "
                "file extension, so which label the matching application "
                "document belongs to is ambiguous. Nothing was compared for this "
                "label. Give each label a name of its own."
            ),
        )
    if stem in table.duplicates:
        return ErrorDetail(
            code="duplicate_application_document",
            message=(
                f"More than one application document in this batch is named "
                f"{stem} before its file extension. Nothing was compared for "
                "this label, because which document applies is ambiguous. Remove "
                "the repeated document."
            ),
        )
    if stem not in table.documents:
        return ErrorDetail(
            code="missing_application_document",
            message=(
                f"No application document in this batch is named {stem} before "
                f"its file extension, so there is nothing to compare "
                f"{image.filename} against. Attach a COLA document with that "
                "name, or remove the image from the batch."
            ),
        )
    return None


def _verify_one(
    image: SubmittedImage, table: DocumentTable, image_stems: dict[str, int]
) -> tuple[str, ErrorDetail | None, VerificationResult | None]:
    """Verify one label against its document, returning a result or an error, never raising.

    A raised exception here would kill the stream and take the completed results
    with it, which is the failure NFR-2 names. Every failure becomes this row's
    error instead, which is FR-8's second criterion and FR-9 applied per row.

    The document is read here rather than up front for two reasons. It is where
    the cost is parallelized, and it is where a document that cannot be read
    becomes one row's error rather than the batch's.
    """
    reconciliation = _row_error(image, table, image_stems)
    if reconciliation is not None:
        return image.filename, reconciliation, None

    document = table.documents[pairing_stem(image.filename)]
    # **One recording per row, not one per batch** (NFR-1). A batch line's
    # `elapsed_ms` is the time that row took; a share of the batch's wall clock
    # would be a different number that happened to have the same units. This is
    # also why the context variable in app/timing.py is deliberately not
    # propagated into worker threads: each worker opens its own here.
    with timing.recording():
        return _verify_one_row(image, document)


def _verify_one_row(
    image: SubmittedImage, document: SubmittedDocument
) -> tuple[str, ErrorDetail | None, VerificationResult | None]:
    """One row's work, inside the recording opened above.

    Split out so that the recording is a `with` block around the whole of it
    rather than a try/finally around several return paths.
    """
    try:
        # Both guards run before anything is decoded or parsed (NFR-7).
        check_media_type(image.content_type)
        check_size(image.content)
        check_document_media_type(document.content_type)
        check_size(document.content)
        try:
            parsed = parse_application_document(document.content, document.content_type)
        except UnreadableDocumentError as exc:
            # FR-9 applied to the document half of the pair. The message names
            # the document rather than the label, because that is the file the
            # agent has to do something about, and this row reports no field
            # outcomes at all.
            raise VerificationError(
                code="unreadable_application_document",
                message=f"{document.filename}: {exc}",
                status_code=422,
            ) from exc

        # Nothing is typed on the batch path, so every value is either read off
        # the document or absent, and the result says which per field (FR-11).
        application, sources = resolve_application({}, parsed)
        result = verify_image(
            image.content,
            application,
            application_sources=sources,
            application_document=document_result(parsed),
        )
    except VerificationError as exc:
        detail = ErrorDetail(code=exc.code, message=exc.message, limit=exc.limit)
        return image.filename, detail, None
    except Exception:  # noqa: BLE001
        # Deliberately broad. An unforeseen failure in one image is still one
        # row's error, not the batch's, and the alternative is a truncated
        # stream with no explanation in it. The traceback goes to the log
        # without the filename or any field value (NFR-6).
        logger.exception("batch item failed unexpectedly")
        return (
            image.filename,
            ErrorDetail(
                code="verification_failed",
                message=(
                    "This label could not be checked because of an unexpected "
                    "error. The rest of the batch was unaffected. Try submitting "
                    "this label on its own."
                ),
            ),
            None,
        )
    return image.filename, None, result


def stream(images: list[SubmittedImage], table: DocumentTable) -> Iterator[str]:
    """Yield one NDJSON line per item, as each finishes (ADR 0006).

    Concurrency is bounded by ``settings.effective_batch_workers`` so that a
    300-file batch does not start 300 Tesseract processes at once. The bound is
    the pool's, not the caller's: every image is submitted immediately and the
    pool decides how many run.

    This is a synchronous generator on purpose. Starlette iterates one in a
    worker thread, so the pool's threads and the event loop stay separate, and
    OCR being CPU bound and in-process (ADR 0003) means there is nothing for an
    async version to await.
    """
    unpaired, total = plan(images, table)
    image_stems: dict[str, int] = {}
    for image in images:
        stem = pairing_stem(image.filename)
        image_stems[stem] = image_stems.get(stem, 0) + 1
    emitted = 0

    # Unpaired documents need no work, so they go out first and the stream
    # starts immediately rather than after the first image finishes.
    for name in unpaired:
        emitted += 1
        yield _line(
            BatchLine(
                filename=name,
                index=emitted,
                total=total,
                status="error",
                error=ErrorDetail(
                    code="unmatched_application_document",
                    message=(
                        f"{name} is an application document with no label image "
                        "of the same name in this batch. Nothing was checked for "
                        "it."
                    ),
                ),
            )
        )

    failures = 0
    with ThreadPoolExecutor(max_workers=settings.effective_batch_workers) as pool:
        futures = [pool.submit(_verify_one, image, table, image_stems) for image in images]
        try:
            for future in as_completed(futures):
                filename, error, result = future.result()
                emitted += 1
                if error is not None:
                    failures += 1
                yield _line(
                    BatchLine(
                        filename=filename,
                        index=emitted,
                        total=total,
                        status="error" if error is not None else "ok",
                        result=result,
                        error=error,
                    )
                )
        finally:
            # A client that closes the connection mid-batch closes this
            # generator. Cancelling what has not started keeps a dropped
            # request from holding the pool for the rest of the batch.
            for future in futures:
                future.cancel()

    # NFR-6: counts only. No filename, no image content, no field value, and
    # nothing any document said.
    logger.info(
        "batch completed",
        extra={
            "images": len(images),
            "documents": len(table.documents),
            "unpaired_documents": len(unpaired),
            "duplicate_documents": len(table.duplicates),
            "failures": failures + len(unpaired),
            "workers": settings.effective_batch_workers,
        },
    )


def _line(line: BatchLine) -> str:
    """One NDJSON line. ``model_dump_json`` keeps it on one line by construction."""
    return line.model_dump_json() + "\n"
