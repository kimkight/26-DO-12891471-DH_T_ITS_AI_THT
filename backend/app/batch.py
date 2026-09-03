"""Batch verification: one file part, rows grouped by stem, each row the single-label check.

Governing requirements: FR-8 (many labels in one submission, per-label results,
the count limit refused before anything is processed, every result naming its
label, one bad file never failing the batch), FR-9 (a per-row error names the
problem and reports no match), FR-11 (the application side of a row is read off
its own COLA document), FR-12 (one upload, sorted by the tool), NFR-2 (the batch
does not fail as a whole and its progress is observable), NFR-6 (nothing is
persisted and no field value reaches the logs), NFR-7 (the count is checked
before processing).
Decision references: [ADR 0006](../../docs/adr/0006-batch-execution-model.md)
for the stream, [ADR 0020](../../docs/adr/0020-batch-items-are-derived.md) for
what a row is, which supersedes the pairing contract of
[ADR 0009](../../docs/adr/0009-batch-cola-documents.md).

**A batch is a pile of files, and a row is every file that shares a stem.**
The stem is the filename with its final extension removed, compared without
regard to case, exactly as ADR 0009 defined it: ``0001-stones-throw.pdf`` and
``0001-stones-throw.png`` land in one row. What changed in v1.4.0 is what the
stem is for. It used to be a precondition: an image with no document of the
same name was an error, a document with no image was an error, and a batch
with no images at all was refused before it started. Now it is a convenience.
Each row is classified from its files (ADR 0011) and handed to the same check
the single-label tab runs (``app.check``), so:

- a filed application that carries its own label artwork is a complete row on
  its own, checked against that artwork (ADR 0010);
- a photograph with no application is a valid row too, checked for what a
  label must carry, with the comparison rows saying there is nothing to
  compare against yet;
- an application and an image that share a stem are the ordinary pair, and
  since the sides are decided by classification rather than by extension, a
  scan of the form and a photograph of the label pair correctly whichever
  extension each has;
- a file that cannot be classified, or cannot be read, is a visible row with
  a plain error, never an absence.

**The total is known before any file is read**, which is what NFR-2's progress
display depends on. Grouping is on names alone, so the first line of the
stream can say "1 of 300" before the first OCR pass has started. The cost of
that is one rule the agent still has to know: two label images that share a
stem are one row, and a row holds one image on this path (ADR 0009's one
photograph per label, unchanged), so they are reported as ambiguous rather
than checked. Name the files apart, or check that label on the single-label
tab, which takes several photographs of one label.

**Why a stream rather than a response body.** ADR 0006 rules out an
asynchronous job model because D-9 forbids the persistence one needs, and rules
out a single buffered response because 300 labels at about 5 seconds each is
about 25 minutes in one request, which exceeds every idle timeout between the
browser and the application and produces exactly the frozen page NFR-2 forbids.
What is left is one request whose body arrives in pieces. The response stream
is the only copy of the results; there is no job store, and nothing outlives
the request: the parts the multipart parser spooled and the temporary file the
OCR engine reads each image through are gone when it returns (NFR-6, and
docs/06_SECURITY_AND_COMPLIANCE.md section 3.2 for where the bytes are while
it runs).

**What is deliberately not here.** No retry, no partial resubmission, and no
resume. A dropped connection loses the batch, which ADR 0006 records as the
direct cost of having no job store.
"""

from __future__ import annotations

import logging
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass

from app import timing
from app.check import check_sorted
from app.classify import SubmittedFile, classify
from app.config import settings
from app.schemas import BatchLine, ErrorDetail, VerificationResult
from app.verify import VerificationError, check_document_media_type, check_size

logger = logging.getLogger(__name__)


def pairing_stem(filename: str) -> str:
    """The key the files of one row share (ADR 0009, kept by ADR 0020).

    The filename with its final extension removed, folded to lower case. Case is
    folded because an agent's file manager and an agent's scanner disagree about
    it routinely and a grouping that failed on `.PDF` against `.pdf` would be a
    puzzle rather than an error. Only the final extension is removed, so
    ``0001-stones-throw.front.png`` has the stem ``0001-stones-throw.front`` and
    groups with ``0001-stones-throw.front.pdf`` rather than with
    ``0001-stones-throw.pdf``.

    Any directory part a browser sends with a `webkitdirectory` selection is
    dropped, because the grouping is on names rather than on paths.
    """
    name = filename.strip().rsplit("/", 1)[-1].rsplit("\\", 1)[-1]
    base, separator, _ = name.rpartition(".")
    # `lower`, not `casefold`, since v1.3.0: the page previews the grouping with
    # JavaScript's `toLowerCase`, and `casefold` also rewrites `ß` to `ss`, so
    # `Straße.png` paired with `STRASSE.pdf` here and not there (code review
    # finding 21). The two plain lower-case mappings agree, and the same vectors
    # are asserted on both sides.
    return (base if separator and base else name).lower()


@dataclass(frozen=True)
class BatchItem:
    """One row of the batch: every submitted file that shares a stem.

    ``position`` is the row's place in submission order, counted from 1 by the
    first file of the row to arrive. Rows finish out of order, so it is what a
    client uses to show them in the order the agent submitted them.
    """

    position: int
    stem: str
    files: tuple[SubmittedFile, ...]

    @property
    def filenames(self) -> list[str]:
        return [file.filename for file in self.files]


def group(files: list[SubmittedFile]) -> list[BatchItem]:
    """Group the submitted files into rows by stem, in order of first appearance.

    Names only: nothing is read, decoded or classified here, which is what
    lets the total be known before any work starts (NFR-2). The same grouping
    is done on the page before the batch is sent, in
    ``frontend/src/lib/pairing.ts``, so the page can lay out one pending row
    per item and fill each in by ``position`` as its line arrives.
    """
    rows: dict[str, list[SubmittedFile]] = {}
    for file in files:
        rows.setdefault(pairing_stem(file.filename), []).append(file)
    return [
        BatchItem(position=position, stem=stem, files=tuple(members))
        for position, (stem, members) in enumerate(rows.items(), start=1)
    ]


def over_count_error(count: int, *, part: str = "labels") -> ErrorDetail:
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


@dataclass(frozen=True)
class RowOutcome:
    """What one row came back with: a result or an error, and the name to show."""

    item: BatchItem
    name: str
    error: ErrorDetail | None = None
    result: VerificationResult | None = None


def check_item(item: BatchItem) -> RowOutcome:
    """Run one row through the single-label check, returning a result or an error, never raising.

    A raised exception here would kill the stream and take the completed results
    with it, which is the failure NFR-2 names. Every failure becomes this row's
    error instead, which is FR-8's second criterion and FR-9 applied per row.

    **One recording per row, not one per batch** (NFR-1). A batch line's
    `elapsed_ms` is the time that row took; a share of the batch's wall clock
    would be a different number that happened to have the same units. This is
    also why the context variable in app/timing.py is deliberately not
    propagated into worker threads: each worker opens its own here.
    """
    with timing.recording():
        return _check_item(item)


def _check_item(item: BatchItem) -> RowOutcome:
    """One row's work, inside the recording opened above."""
    # The row is named after its first file until the sorting says which file
    # is the label image; an agent finds a row by the name they gave it.
    name = item.files[0].filename
    try:
        # Both guards run before anything is decoded (NFR-7), per file, with
        # the list the single-label route uses: PDF plus the image types,
        # because one part now takes both.
        for file in item.files:
            check_document_media_type(file.content_type)
            check_size(file.content)

        # Classification first (ADR 0011, ADR 0020). Which file is the
        # application and which is the label is the file's own evidence, not
        # its extension; each image is read exactly once and the read is handed
        # on to the check.
        sorted_files = classify(list(item.files))
        documents = [entry for entry in sorted_files if entry.side == "application_document"]
        labels = [entry for entry in sorted_files if entry.side == "label_image"]
        if labels:
            name = labels[0].filename

        if len(documents) > 1:
            raise VerificationError(
                code="duplicate_application_document",
                message=(
                    f"More than one file named {item.stem} before its file "
                    "extension reads as a label application ("
                    f"{', '.join(entry.filename for entry in documents)}), so "
                    "which one applies to this label is ambiguous. Nothing was "
                    "compared for it. Keep one application for each label."
                ),
            )
        if len(labels) > 1:
            # ADR 0009's one photograph per label, unchanged by ADR 0020. The
            # single-label tab reads several photographs of one label and
            # merges them; this path enumerates rows from names before it has
            # read anything, and a row with several pictures in it would need
            # a rule for a group only partly readable that no source asks for.
            raise VerificationError(
                code="duplicate_label_stem",
                message=(
                    f"More than one file named {item.stem} before its file "
                    "extension reads as a label image ("
                    f"{', '.join(entry.filename for entry in labels)}). This "
                    "page checks one image for each label, so nothing was "
                    "compared for it. Give each label a name of its own, or "
                    "check a label with several photographs on the "
                    "single-label tab."
                ),
            )

        # Nothing is typed on the batch path, so every value is either read off
        # the row's document or absent, and the result says which per field
        # (FR-11). Everything from here is the single-label check, unchanged.
        try:
            checked = check_sorted(sorted_files, {})
        except VerificationError as exc:
            if exc.code == "unreadable_application_document" and documents:
                # FR-8: the row names the document, because that is the file
                # the agent has to do something about.
                raise VerificationError(
                    code=exc.code,
                    message=f"{documents[0].filename}: {exc.message}",
                    status_code=exc.status_code,
                    limit=exc.limit,
                ) from exc
            raise
    except VerificationError as exc:
        detail = ErrorDetail(code=exc.code, message=exc.message, limit=exc.limit)
        return RowOutcome(item=item, name=name, error=detail)
    except Exception:  # noqa: BLE001
        # Deliberately broad. An unforeseen failure in one row is still one
        # row's error, not the batch's, and the alternative is a truncated
        # stream with no explanation in it. The traceback goes to the log
        # without the filename or any field value (NFR-6).
        logger.exception("batch item failed unexpectedly")
        return RowOutcome(
            item=item,
            name=name,
            error=ErrorDetail(
                code="verification_failed",
                message=(
                    "This label could not be checked because of an unexpected "
                    "error. The rest of the batch was unaffected. Try submitting "
                    "this label on its own."
                ),
            ),
        )
    return RowOutcome(item=item, name=name, result=checked.result)


def stream(items: list[BatchItem]) -> Iterator[str]:
    """Yield one NDJSON line per row, as each finishes (ADR 0006).

    Concurrency is bounded by ``settings.effective_batch_workers`` so that a
    300-file batch does not start 300 Tesseract processes at once. The bound is
    the pool's, not the caller's: every row is submitted immediately and the
    pool decides how many run.

    This is a synchronous generator on purpose. Starlette iterates one in a
    worker thread, so the pool's threads and the event loop stay separate, and
    OCR being CPU bound and in-process (ADR 0003) means there is nothing for an
    async version to await. `GET /api/health` keeps answering while a batch
    runs, which `tests/test_event_loop.py` asserts.
    """
    total = len(items)
    emitted = 0
    failures = 0
    artwork_sided = 0

    with ThreadPoolExecutor(max_workers=settings.effective_batch_workers) as pool:
        futures = [pool.submit(check_item, item) for item in items]
        try:
            for future in as_completed(futures):
                row = future.result()
                emitted += 1
                if row.error is not None:
                    failures += 1
                elif row.result is not None and row.result.label_source == "application_artwork":
                    artwork_sided += 1
                yield _line(
                    BatchLine(
                        filename=row.name,
                        filenames=row.item.filenames,
                        position=row.item.position,
                        index=emitted,
                        total=total,
                        status="error" if row.error is not None else "ok",
                        result=row.result,
                        error=row.error,
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
            "rows": total,
            "files": sum(len(item.files) for item in items),
            "failures": failures,
            "artwork_sided": artwork_sided,
            "workers": settings.effective_batch_workers,
        },
    )


def _line(line: BatchLine) -> str:
    """One NDJSON line. ``model_dump_json`` keeps it on one line by construction."""
    return line.model_dump_json() + "\n"
