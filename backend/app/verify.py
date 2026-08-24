"""The single-image verification pipeline, shared by the one-label and batch paths.

Governing requirements: FR-1 and FR-2 (extract the five fields and compare them
against application data), FR-3 (one outcome per field), FR-9 (an undecodable
file, an image with no text, a disallowed type and an oversize file each return
a clear message, and no error path returns a match), NFR-1 (elapsed time is
reported), NFR-3 (the default path makes no outbound call and says so).

This module exists because FR-8 gives the same pipeline a second caller. The
batch path in ``app.batch`` has to run exactly what ``POST /api/verify`` runs,
or the two would drift and a batch result would stop meaning what a single
result means. Keeping the pipeline here rather than in ``app.api`` also keeps
the import graph acyclic: ``app.api`` imports ``app.batch``, and both import
this.

Failures are raised as ``VerificationError`` rather than returned as HTTP
responses, because the two callers need them in different shapes: the
single-label route turns one into a JSON error body, and the batch stream turns
one into a result line for that row without failing the request (FR-8, NFR-2).
"""

from __future__ import annotations

import time
from dataclasses import dataclass

from app.compare import Outcome, compare_abv, compare_net_contents, compare_text
from app.config import settings
from app.ocr import UndecodableImageError, extract_text
from app.parse import ParsedFields, parse_fields
from app.schemas import FIELD_LABELS, FieldResult, VerificationResult, WarningResult
from app.warning import WARNING_STATEMENT, WarningCheck

COMPARED_FIELDS = ("brand_name", "class_type", "alcohol_content", "net_contents")


def _size_limit_text() -> str:
    """Built per call, not at import.

    NFR-7's last criterion is that a rejection names the limit that was
    exceeded, and NFR-11 puts the limits in the environment. A module constant
    would name whatever the limit was when the module was first imported, which
    is the same value in a deployed process and a different one anywhere the
    setting is changed after import, including every test that varies it.
    """
    return f"maximum upload size: {settings.max_upload_bytes} bytes"


def _type_limit_text() -> str:
    return f"accepted types: {', '.join(settings.allowed_mime_types)}"


@dataclass(frozen=True)
class VerificationError(Exception):
    """One image could not be verified, and why.

    ``status_code`` is carried on the error rather than decided by the caller so
    that the single-label route and the batch stream cannot disagree about what
    a given failure means. ``limit`` is the value that was exceeded, named
    explicitly, which is NFR-7's last criterion and FR-9's third and fourth.
    """

    code: str
    message: str
    status_code: int = 422
    limit: str | None = None

    def __str__(self) -> str:
        return self.message


def check_media_type(content_type: str | None) -> None:
    """Reject a disallowed type before anything is decoded (NFR-7, FR-9)."""
    if content_type not in settings.allowed_mime_types:
        raise VerificationError(
            code="unsupported_media_type",
            message=(
                f"{content_type or 'The submitted file'} is not an accepted image "
                "type. Send one of the accepted types instead."
            ),
            status_code=415,
            limit=_type_limit_text(),
        )


def check_size(content: bytes) -> None:
    """Reject an oversize image exactly, after parsing (NFR-7, FR-9).

    The single-label path also rejects on Content-Length in middleware, before
    the body is read. This is the exact check on the file itself, and it is the
    only size check the batch path has: a batch envelope's Content-Length says
    nothing about any one image inside it.
    """
    if len(content) > settings.max_upload_bytes:
        raise VerificationError(
            code="file_too_large",
            message=(
                "The uploaded file is larger than this service accepts. Send a smaller image."
            ),
            status_code=413,
            limit=_size_limit_text(),
        )


def verify_image(content: bytes, application: dict[str, str]) -> VerificationResult:
    """Decode, read, parse and compare one image. Nothing is persisted (NFR-6).

    Raises ``VerificationError`` for every FR-9 failure. The media type and size
    checks are deliberately not called here: both have to happen before the
    bytes are in hand on the single-label path, so the caller runs them.
    """
    started = time.perf_counter()

    try:
        ocr = extract_text(content)
    except UndecodableImageError as exc:
        # Distinct from "no text found" below, because the agent's next action
        # differs: a corrupt file needs resending, a blank one needs a better
        # photograph (FR-9, Jenny Park interview).
        raise VerificationError(code="unreadable_image", message=str(exc)) from exc

    if not ocr.has_text:
        raise VerificationError(
            code="no_text_found",
            message=(
                "The image was read but no text could be extracted from it. This "
                "is not the same as the fields failing to match: nothing was "
                "compared."
            ),
        )

    parsed = parse_fields(ocr.lines)
    elapsed_ms = (time.perf_counter() - started) * 1000
    return build_result(
        parsed,
        application,
        ocr.mean_confidence,
        ocr_ms=ocr.elapsed_ms,
        elapsed_ms=elapsed_ms,
    )


def build_result(
    parsed: ParsedFields,
    application: dict[str, str],
    ocr_confidence: float,
    *,
    ocr_ms: float,
    elapsed_ms: float | None = None,
) -> VerificationResult:
    """Compare every field and assemble the response (FR-2, FR-3).

    Split out from the route so the comparison layer can be exercised without an
    HTTP client, and so scripts/measure.py runs exactly the code the API runs.
    """
    comparisons = {
        "brand_name": compare_text(parsed.brand_name, application.get("brand_name")),
        "class_type": compare_text(parsed.class_type, application.get("class_type")),
        "alcohol_content": compare_abv(parsed.alcohol_content, application.get("alcohol_content")),
        "net_contents": compare_net_contents(parsed.net_contents, application.get("net_contents")),
    }
    label_values = {
        "brand_name": parsed.brand_name,
        "class_type": parsed.class_type,
        "alcohol_content": parsed.alcohol_content,
        "net_contents": parsed.net_contents,
    }

    fields = [
        FieldResult(
            name=name,
            display_name=FIELD_LABELS[name],
            found_on_label=label_values[name] is not None,
            label_value=label_values[name],
            application_value=application.get(name) or None,
            score=comparison.score,
            outcome=comparison.outcome,
            reason=comparison.reason,
        )
        for name, comparison in comparisons.items()
    ]
    fields.append(_warning_field(parsed.warning, parsed.warning_text))

    return VerificationResult(
        fields=fields,
        warning_detail=WarningResult(
            statement_found=parsed.warning.found,
            prefix_as_printed=parsed.warning.prefix_found,
            prefix_is_capitalized=parsed.warning.prefix_is_upper_case,
            body_matches_regulation=parsed.warning.body_matches,
        ),
        ocr_confidence=ocr_confidence,
        elapsed_ms=round(ocr_ms if elapsed_ms is None else elapsed_ms, 1),
        ocr_ms=round(ocr_ms, 1),
        external_call_made=False,
    )


def _warning_field(warning: WarningCheck, warning_text: str | None) -> FieldResult:
    """The warning as one field row, with no review band (FR-5).

    The comparison side is the regulation rather than the application form: the
    required text is fixed by 27 CFR 16.21, so there is nothing for an applicant
    to declare and nothing to type in.
    """
    outcome = Outcome.MATCH if warning.passes else Outcome.MISMATCH
    return FieldResult(
        name="government_warning",
        display_name=FIELD_LABELS["government_warning"],
        found_on_label=warning.found,
        label_value=warning_text,
        application_value=WARNING_STATEMENT,
        score=None,
        outcome=outcome,
        reason=f"{warning.reason} {warning.bold_type_note}",
    )
