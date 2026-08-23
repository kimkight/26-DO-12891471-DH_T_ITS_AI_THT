"""The verification HTTP surface: POST /api/verify.

Governing requirements: FR-1 and FR-2 (accept a label image plus application
data for the same five fields), FR-3 (one outcome per field), FR-9 (an
undecodable file, an image with no text, a disallowed type and an oversize file
each return a clear message, and no error path returns a match), NFR-6 (nothing
is persisted and no image content or field value reaches the logs), NFR-7 (size
is checked before the body is read and MIME before anything is decoded), NFR-3
(the default path makes no outbound call and says so in the response).

US-1 through US-7 are implemented here at the API level. There is no user
interface for them yet; US-2 and FR-10 are presentation requirements and are not
part of this module.
"""

from __future__ import annotations

import logging
import time
from typing import Annotated

from fastapi import APIRouter, File, Form, UploadFile
from fastapi.responses import JSONResponse
from starlette.formparsers import MultiPartParser
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.compare import Outcome, compare_abv, compare_net_contents, compare_text
from app.config import settings
from app.ocr import UndecodableImageError, extract_text
from app.parse import ParsedFields, parse_fields
from app.schemas import (
    FIELD_LABELS,
    ErrorDetail,
    ErrorResponse,
    FieldResult,
    VerificationResult,
    WarningResult,
)
from app.warning import WARNING_STATEMENT, WarningCheck

logger = logging.getLogger(__name__)

# Starlette spools any part over 1 MB to a temporary file on disk. NFR-6 says no
# uploaded image is written to disk, so the spool threshold is raised to the
# upload limit and nothing within the limit ever reaches the filesystem.
# max_part_size is raised with it because it is the parser's own hard cap and
# would otherwise reject at 1 MB, well below TTB_MAX_UPLOAD_BYTES.
MultiPartParser.spool_max_size = settings.max_upload_bytes
MultiPartParser.max_part_size = settings.max_upload_bytes

router = APIRouter(prefix="/api", tags=["verification"])

_SIZE_LIMIT_TEXT = f"{settings.max_upload_bytes} bytes"
_TYPE_LIMIT_TEXT = ", ".join(settings.allowed_mime_types)


def _error(status_code: int, code: str, message: str, limit: str | None = None) -> JSONResponse:
    """Build an error response.

    Errors are returned rather than raised as ``HTTPException`` so that the body
    shape is the one in ``ErrorResponse`` every time. FR-9's last criterion is
    the point: no error path returns a match outcome for any field, so no error
    body carries a fields array at all.
    """
    payload = ErrorResponse(error=ErrorDetail(code=code, message=message, limit=limit))
    return JSONResponse(status_code=status_code, content=payload.model_dump())


class UploadSizeLimitMiddleware(BaseHTTPMiddleware):
    """Reject an oversize request from its Content-Length, before the body is read.

    NFR-7's first criterion is that "file size is checked against
    TTB_MAX_UPLOAD_BYTES **before the body is read into memory**". A route
    dependency cannot satisfy that: FastAPI parses the multipart body while
    resolving the endpoint's parameters, so by the time any handler code runs
    the body has already been read. Middleware runs before routing, and
    returning here without calling ``call_next`` means the body is never
    consumed at all.

    Content-Length covers the whole multipart envelope, so the effective limit
    on the image itself is marginally below TTB_MAX_UPLOAD_BYTES. Erring strict
    is the right direction for a guard whose job is to stop a large body from
    being read, and the file's own size is checked exactly, after parsing, in
    the route below.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        declared = request.headers.get("content-length")
        if (
            request.method == "POST"
            and request.url.path.startswith("/api/verify")
            and declared is not None
            and declared.isdigit()
            and int(declared) > settings.max_upload_bytes
        ):
            return _oversize_response()
        return await call_next(request)


@router.post(
    "/verify",
    response_model=VerificationResult,
    responses={
        413: {"model": ErrorResponse},
        415: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
    },
    summary="Verify one label against its application data",
)
async def verify(
    image: Annotated[UploadFile, File(description="Label artwork, one image.")],
    brand_name: Annotated[str, Form()] = "",
    class_type: Annotated[str, Form()] = "",
    alcohol_content: Annotated[str, Form()] = "",
    net_contents: Annotated[str, Form()] = "",
    beverage_type: Annotated[str, Form()] = "",
) -> JSONResponse:
    """Verify one label. Nothing is persisted and nothing is logged about it."""
    started = time.perf_counter()
    if image.content_type not in settings.allowed_mime_types:
        # Checked before any byte is decoded (NFR-7, second criterion).
        return _error(
            415,
            "unsupported_media_type",
            (
                f"{image.content_type or 'The submitted file'} is not an accepted "
                "image type. Send one of the accepted types instead."
            ),
            limit=f"accepted types: {_TYPE_LIMIT_TEXT}",
        )

    content = await image.read()
    if len(content) > settings.max_upload_bytes:
        return _oversize_response()

    try:
        ocr = extract_text(content)
    except UndecodableImageError as exc:
        # Distinct from "no text found" below, because the agent's next action
        # differs: a corrupt file needs resending, a blank one needs a better
        # photograph (FR-9, Jenny Park interview).
        return _error(422, "unreadable_image", str(exc))

    if not ocr.has_text:
        return _error(
            422,
            "no_text_found",
            (
                "The image was read but no text could be extracted from it. This "
                "is not the same as the fields failing to match: nothing was "
                "compared."
            ),
        )

    parsed = parse_fields(ocr.lines)
    application = {
        "brand_name": brand_name,
        "class_type": class_type,
        "alcohol_content": alcohol_content,
        "net_contents": net_contents,
    }
    elapsed_ms = (time.perf_counter() - started) * 1000
    result = build_result(
        parsed, application, ocr.mean_confidence, ocr_ms=ocr.elapsed_ms, elapsed_ms=elapsed_ms
    )

    # NFR-6: counts and timings only. No image content, no extracted value, no
    # application value, no filename.
    logger.info(
        "verification completed",
        extra={
            "bytes_received": len(content),
            "ocr_ms": ocr.elapsed_ms,
            "beverage_type_supplied": bool(beverage_type.strip()),
        },
    )
    return JSONResponse(status_code=200, content=result.model_dump())


def _oversize_response() -> JSONResponse:
    return _error(
        413,
        "file_too_large",
        ("The uploaded file is larger than this service accepts. Send a smaller image."),
        limit=f"maximum upload size: {_SIZE_LIMIT_TEXT}",
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
