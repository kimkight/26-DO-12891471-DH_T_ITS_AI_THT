"""Batch verification: CSV reconciliation, a bounded worker pool, an NDJSON stream.

Governing requirements: FR-8 (many labels in one submission, per-label results,
the count limit refused before anything is processed, every result naming its
label, and CSV mismatches reported per row), FR-9 (one unreadable image is that
row's error, not the batch's), NFR-2 (the batch does not fail as a whole and its
progress is observable), NFR-6 (nothing is persisted and no field value reaches
the logs), NFR-7 (the file count is checked before processing).
Decision reference: [ADR 0006](../../docs/adr/0006-batch-execution-model.md),
assumption A-14 for the CSV contract.

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
direct cost of having no job store.
"""

from __future__ import annotations

import csv
import io
import logging
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field

from app.config import settings
from app.schemas import BatchLine, ErrorDetail, VerificationResult
from app.verify import VerificationError, check_media_type, check_size, verify_image

logger = logging.getLogger(__name__)

# The A-14 column contract. `filename` keys the row to an image part; the rest
# are the application side of the comparison. `beverage_type` is in the contract
# because A-12 and A-13 need it: the proof cross-check applies to distilled
# spirits and the range handling for wine cites 27 CFR 4.36, so without the
# beverage class the tool would have to guess which rule to apply.
REQUIRED_COLUMNS = (
    "filename",
    "brand_name",
    "class_type",
    "alcohol_content",
    "net_contents",
    "beverage_type",
)

# The columns fed to the comparison. `beverage_type` is read from the CSV and
# carried for the rules that need it, but it is not itself a compared field:
# there are five fields on a label and beverage type is not one of them (FR-1).
COMPARED_COLUMNS = ("brand_name", "class_type", "alcohol_content", "net_contents")


@dataclass(frozen=True)
class SubmittedImage:
    """One image part, already read into memory.

    ``content_type`` is kept alongside the bytes because the media type check
    has to happen before anything is decoded (NFR-7), and by this point the
    ``UploadFile`` it came from may already be closed.
    """

    filename: str
    content_type: str | None
    content: bytes


@dataclass
class ApplicationTable:
    """The parsed CSV, plus what was wrong with it.

    ``duplicates`` is a set rather than a count because a duplicated
    ``filename`` makes that one row ambiguous and leaves every other row usable.
    FR-8 asks for "a per-row or batch-level error that names the problem", and
    per row is the more useful of the two here: one repeated line should not
    cost an agent the other 299 results.
    """

    rows: dict[str, dict[str, str]] = field(default_factory=dict)
    duplicates: set[str] = field(default_factory=set)


class ApplicationCsvError(Exception):
    """The CSV could not be used at all, so no row can be verified.

    This is the batch-level half of FR-8's error criterion. A missing header, an
    unreadable encoding, or a header missing a required column is not a problem
    with one label; it makes every comparison impossible, so it is refused
    before any image is read rather than repeated 300 times down the stream.
    """

    def __init__(self, message: str, limit: str | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.limit = limit


def parse_applications_csv(raw: bytes) -> ApplicationTable:
    """Read the application CSV into rows keyed by filename (A-14).

    Raises ``ApplicationCsvError`` when the file cannot serve as application
    data at all. Everything survivable, which is a duplicated filename, is
    recorded on the table and reported against the row it affects.
    """
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ApplicationCsvError(
            "The application data file could not be read as UTF-8 text. Save it "
            "as CSV with UTF-8 encoding and submit it again."
        ) from exc

    reader = csv.DictReader(io.StringIO(text))
    if reader.fieldnames is None:
        raise ApplicationCsvError(
            "The application data file is empty. It needs a header row and one row per image."
        )

    present = {(name or "").strip().lower() for name in reader.fieldnames}
    missing = [column for column in REQUIRED_COLUMNS if column not in present]
    if missing:
        raise ApplicationCsvError(
            "The application data file is missing the column "
            f"{'s ' if len(missing) > 1 else ' '}"
            f"{', '.join(missing)}. Check the header row.",
            limit=f"required columns: {', '.join(REQUIRED_COLUMNS)}",
        )

    table = ApplicationTable()
    for row in reader:
        normalized = {
            (key or "").strip().lower(): (value or "").strip() for key, value in row.items()
        }
        name = normalized.get("filename", "")
        if not name:
            # A row with no filename cannot be matched to an image and cannot be
            # reported against one either, so there is nothing to attach an
            # error to. It is counted in the log line and otherwise ignored.
            continue
        if name in table.rows:
            table.duplicates.add(name)
            continue
        table.rows[name] = normalized

    if not table.rows:
        raise ApplicationCsvError(
            "The application data file has a header row but no usable rows. Each "
            "row needs a filename matching one of the submitted images."
        )
    return table


def over_count_error(count: int) -> ErrorDetail:
    """The FR-8 refusal, which names the limit and happens before processing."""
    return ErrorDetail(
        code="batch_too_large",
        message=(
            f"This batch has {count} images, which is more than this service "
            "accepts in one submission. Split it into smaller batches and send "
            "them one after another."
        ),
        limit=f"maximum images per batch: {settings.max_batch_files}",
    )


def plan(images: list[SubmittedImage], table: ApplicationTable) -> tuple[list[str], int]:
    """Reconcile the images against the CSV and say how many lines will be emitted.

    Returns the CSV filenames that matched no image, and the total line count.
    The total is known before any OCR runs, which is what lets the first line of
    the stream carry it and a client render "1 of 300" immediately (NFR-2).

    Every submitted image produces exactly one line, whether it verifies or
    errors, and every unmatched CSV row produces one more. Duplicated image
    filenames still produce one line each; they are reported as errors rather
    than verified, because two results under one name would break FR-8's
    requirement that a result identify which label it belongs to.
    """
    submitted = [image.filename for image in images]
    unmatched = [name for name in table.rows if name not in set(submitted)]
    return unmatched, len(images) + len(unmatched)


def _row_error(image: SubmittedImage, table: ApplicationTable) -> ErrorDetail | None:
    """The reconciliation failures that stop one image being verified (FR-8)."""
    if image.filename in table.duplicates:
        return ErrorDetail(
            code="duplicate_application_row",
            message=(
                f"The application data file has more than one row for "
                f"{image.filename}. Nothing was compared for this label, because "
                "which row applies is ambiguous. Remove the repeated row."
            ),
        )
    if image.filename not in table.rows:
        return ErrorDetail(
            code="missing_application_row",
            message=(
                f"No row in the application data file has the filename "
                f"{image.filename}, so there is nothing to compare this label "
                "against. Add a row for it, or remove the image from the batch."
            ),
        )
    return None


def _verify_one(
    image: SubmittedImage, table: ApplicationTable
) -> tuple[str, ErrorDetail | None, VerificationResult | None]:
    """Verify one image, returning either its result or its error, never raising.

    A raised exception here would kill the stream and take the completed results
    with it, which is the failure NFR-2 names. Every failure becomes this row's
    error instead, which is FR-8's second criterion and FR-9 applied per row.
    """
    reconciliation = _row_error(image, table)
    if reconciliation is not None:
        return image.filename, reconciliation, None

    row = table.rows[image.filename]
    application = {column: row.get(column, "") for column in COMPARED_COLUMNS}
    try:
        check_media_type(image.content_type)
        check_size(image.content)
        result = verify_image(image.content, application)
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


def stream(images: list[SubmittedImage], table: ApplicationTable) -> Iterator[str]:
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
    unmatched, total = plan(images, table)
    emitted = 0

    # Unmatched CSV rows need no work, so they go out first and the stream
    # starts immediately rather than after the first image finishes.
    for name in unmatched:
        emitted += 1
        yield _line(
            BatchLine(
                filename=name,
                index=emitted,
                total=total,
                status="error",
                error=ErrorDetail(
                    code="unmatched_application_row",
                    message=(
                        f"The application data file has a row for {name} but no "
                        "image with that filename was submitted. Nothing was "
                        "checked for it."
                    ),
                ),
            )
        )

    failures = 0
    with ThreadPoolExecutor(max_workers=settings.effective_batch_workers) as pool:
        futures = [pool.submit(_verify_one, image, table) for image in images]
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

    # NFR-6: counts only. No filename, no image content, no field value.
    logger.info(
        "batch completed",
        extra={
            "images": len(images),
            "unmatched_rows": len(unmatched),
            "duplicate_rows": len(table.duplicates),
            "failures": failures + len(unmatched),
            "workers": settings.effective_batch_workers,
        },
    )


def _line(line: BatchLine) -> str:
    """One NDJSON line. ``model_dump_json`` keeps it on one line by construction."""
    return line.model_dump_json() + "\n"
