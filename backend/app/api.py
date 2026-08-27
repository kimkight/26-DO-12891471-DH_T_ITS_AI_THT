"""The verification HTTP surface: POST /api/verify and POST /api/verify-batch.

Governing requirements: FR-1 and FR-2 (accept a label image plus application
data for the same five fields), FR-3 (one outcome per field), FR-8 (many labels
in one submission, results streaming back per label), FR-9 (an undecodable file,
an image with no text, a disallowed type and an oversize file each return a
clear message, and no error path returns a match), NFR-2 (a batch does not fail
as a whole and its progress is observable), NFR-6 (nothing is persisted and no
image content or field value reaches the logs), NFR-7 (size is checked before
the body is read, MIME before anything is decoded, and the batch file count
before anything is processed), NFR-3 (the default path makes no outbound call
and says so in the response).

US-1 through US-7 and US-9 through US-11 are implemented here at the API level.
The pipeline both routes run is in ``app.verify``; the batch reconciliation,
worker pool and stream are in ``app.batch``. US-2 and FR-10 are presentation
requirements and are not part of this module.
"""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, File, Form, UploadFile
from fastapi.responses import JSONResponse, StreamingResponse
from starlette.formparsers import MultiPartParser
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app import batch
from app.config import settings
from app.schemas import ErrorDetail, ErrorResponse, VerificationResult
from app.verify import (
    VerificationError,
    build_result,
    check_media_type,
    check_size,
    verify_photos,
)

__all__ = ["UploadSizeLimitMiddleware", "build_result", "router"]

logger = logging.getLogger(__name__)

# Starlette spools any part over 1 MB to a temporary file on disk. NFR-6 says no
# uploaded image is written to disk, so the spool threshold is raised to the
# upload limit and nothing within the limit ever reaches the filesystem. This is
# a class attribute the parser reads through `self`, with no constructor
# override, so setting it here does reach every request.
#
# max_part_size is raised alongside it, but note what it does and does not do.
# The parser applies it to non-file parts only; a file part streams into the
# spooled file with no cap of its own. So this bounds the batch CSV and the
# single-label form fields, not the images. Images are bounded exactly, after
# parsing, by verify.check_size. Note also that the parser takes max_part_size
# as a constructor argument defaulted to 1 MB and assigns it to the instance, so
# this class-level value is shadowed on every request; it is set for the case
# where a future caller constructs a parser without passing one, not relied on.
MultiPartParser.spool_max_size = settings.max_upload_bytes
MultiPartParser.max_part_size = settings.max_upload_bytes

router = APIRouter(prefix="/api", tags=["verification"])


# What each upload route accepts as a whole request body, checked from
# Content-Length before the body is read. The two differ by construction: a
# batch envelope carries many images plus a CSV, so measuring it against the
# per-image limit would reject every batch of more than one file. Matching is
# exact rather than by prefix for the same reason; a prefix match on
# "/api/verify" would apply the single-file limit to "/api/verify-batch".
def _envelope_limit(path: str) -> int | None:
    """The whole-body limit for an upload route, or None if the path is not one.

    Read per request rather than captured at import, so that an environment
    that sets TTB_MAX_UPLOAD_BYTES or TTB_MAX_BATCH_FILES is reflected in both
    the check and the message that names it (NFR-7, NFR-11).
    """
    if path == "/api/verify":
        return settings.effective_max_verify_bytes
    if path == "/api/verify-batch":
        return settings.effective_max_batch_bytes
    return None


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

    Content-Length covers the whole multipart envelope, and the single-label
    route now accepts up to TTB_MAX_LABEL_PHOTOS photographs of one label
    (ADR 0007), so its envelope limit is that many times TTB_MAX_UPLOAD_BYTES.

    **That loosens this guard, and the loosening is deliberate and bounded.**
    Before ADR 0007 a single-label body over TTB_MAX_UPLOAD_BYTES was refused
    here, without being read. It now takes a body up to three times that before
    this guard fires, and a 25 MB single-photograph submission is read into
    memory and then refused exactly by verify.check_size after parsing. The
    alternative was to bound the envelope at one photograph, which would reject
    every two-photograph submission, so there is no version of this that both
    accepts three photographs and refuses 25 MB from the header: the middleware
    cannot count the parts without reading the body it is trying not to read.
    What is kept is that the body is still bounded before it is read, at 30 MB
    on the defaults rather than 10 MB, and that every individual photograph is
    still checked exactly against TTB_MAX_UPLOAD_BYTES. Lower
    TTB_MAX_LABEL_PHOTOS or TTB_MAX_UPLOAD_BYTES to tighten it.

    The batch route is measured against its own envelope limit, which is
    TTB_MAX_BATCH_FILES times TTB_MAX_UPLOAD_BYTES by default. That bounds the
    request, not any one image in it: each image is still checked exactly
    against TTB_MAX_UPLOAD_BYTES after parsing, and an oversize one is that
    row's error rather than the batch's.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        limit = _envelope_limit(request.url.path)
        declared = request.headers.get("content-length")
        if (
            request.method == "POST"
            and limit is not None
            and declared is not None
            and declared.isdigit()
            and int(declared) > limit
        ):
            return _oversize_response(limit)
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
    image: Annotated[
        list[UploadFile],
        File(
            description=(
                "Label artwork. One part, or the same part repeated for up to "
                "TTB_MAX_LABEL_PHOTOS photographs of the same label (ADR 0007)."
            )
        ),
    ],
    brand_name: Annotated[str, Form()] = "",
    class_type: Annotated[str, Form()] = "",
    alcohol_content: Annotated[str, Form()] = "",
    net_contents: Annotated[str, Form()] = "",
    beverage_type: Annotated[str, Form()] = "",
) -> JSONResponse:
    """Verify one label from one to three photographs of it.

    One `image` part behaves exactly as it always did. More than one is ADR
    0007: a label wraps a round bottle, so no single photograph shows all of it
    flat, and the photographs are read independently and their fields merged.

    Nothing is persisted and nothing is logged about it.
    """
    # Counted before anything is read, decoded or compared, and named in the
    # message (FR-9, NFR-7). The bodies are in memory by now because FastAPI
    # parses the multipart form while resolving these parameters; the guarantee
    # kept here is that no photograph is processed.
    if len(image) > settings.max_label_photos:
        return _error(
            413,
            "too_many_photos",
            (
                f"{len(image)} photographs were submitted for one label. Send at "
                f"most {settings.max_label_photos} photographs of the same label, "
                "or use the batch tab for many different labels."
            ),
            limit=f"maximum photographs of one label: {settings.max_label_photos}",
        )

    contents: list[bytes] = []
    try:
        for part in image:
            # Checked before any byte is decoded (NFR-7, second criterion).
            check_media_type(part.content_type)
            content = await part.read()
            check_size(content)
            contents.append(content)
        result = verify_photos(
            contents,
            {
                "brand_name": brand_name,
                "class_type": class_type,
                "alcohol_content": alcohol_content,
                "net_contents": net_contents,
            },
        )
    except VerificationError as exc:
        return _error(exc.status_code, exc.code, exc.message, limit=exc.limit)

    # NFR-6: counts and timings only. No image content, no extracted value, no
    # application value, no filename.
    logger.info(
        "verification completed",
        extra={
            "bytes_received": sum(len(content) for content in contents),
            "photos_received": len(contents),
            "ocr_ms": result.ocr_ms,
            "beverage_type_supplied": bool(beverage_type.strip()),
        },
    )
    return JSONResponse(status_code=200, content=result.model_dump())


def _oversize_response(limit: int | None = None) -> JSONResponse:
    """FR-9's fourth criterion: rejected before reading, with the limit named."""
    enforced = settings.max_upload_bytes if limit is None else limit
    if enforced == settings.max_upload_bytes:
        message = "The uploaded file is larger than this service accepts. Send a smaller image."
    elif enforced == settings.effective_max_verify_bytes:
        message = (
            "This submission is larger than this service accepts in one request. "
            "Send fewer photographs of the label, or smaller ones."
        )
    else:
        message = (
            "This submission is larger than this service accepts in one request. "
            "Split it into smaller batches and send them one after another."
        )
    return _error(413, "file_too_large", message, limit=f"maximum upload size: {enforced} bytes")


@router.post(
    "/verify-batch",
    responses={
        200: {
            "content": {"application/x-ndjson": {}},
            "description": (
                "One JSON object per line, one line per item, emitted as each "
                "item finishes. See the BatchLine schema."
            ),
        },
        413: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
    },
    summary="Verify many labels against one CSV of application data",
)
async def verify_batch(
    applications: Annotated[
        UploadFile,
        File(description="One CSV of application data keyed by image filename (A-14)."),
    ],
    images: Annotated[
        list[UploadFile],
        # Defaulted rather than required so that a submission with no images at
        # all reaches the route and gets the message below, which says what to
        # do about it, instead of the generic missing-part rejection. The
        # default is never mutated; FastAPI reads it and builds a new list.
        File(description="Label artwork, one part per image, repeated."),
    ] = [],  # noqa: B006
) -> Response:
    """Verify a batch of labels and stream the results (FR-8, NFR-2, ADR 0006).

    The response is `application/x-ndjson`: one JSON object per line, each
    naming the image it belongs to, emitted as each label finishes rather than
    in submission order. Nothing is persisted; the stream is the only copy of
    the results (D-9, NFR-6).

    Three rejections happen before any image is read, and each names what was
    exceeded (FR-9, NFR-7):

    * more images than `TTB_MAX_BATCH_FILES`, which is FR-8's third criterion,
      "the request is rejected with a message naming the limit, before any file
      is processed";
    * a request body over the batch envelope limit, caught in middleware from
      Content-Length before the body is read at all;
    * an application CSV that cannot serve as application data for any row.

    Everything else is a per-row error on its own line, which is what keeps one
    bad image from costing an agent the other 299 results (FR-8, US-10).
    """
    # FR-8, third criterion. Counted before anything is read, decoded or
    # compared. The bodies are in memory by now, because FastAPI parses the
    # multipart form while resolving these parameters; "before any file is
    # processed" is the guarantee the requirement states and the one kept here.
    if len(images) > settings.max_batch_files:
        detail = batch.over_count_error(len(images))
        return _error(413, detail.code, detail.message, limit=detail.limit)

    if not images:
        return _error(
            422,
            "empty_batch",
            "No images were submitted. Attach at least one label image and the "
            "application data CSV.",
        )

    try:
        table = batch.parse_applications_csv(await applications.read())
    except batch.ApplicationCsvError as exc:
        # Batch level rather than per row: with no usable header there is no row
        # to attach an error to, and repeating one message 300 times down the
        # stream would tell an agent nothing the first line did not.
        return _error(422, "invalid_application_csv", exc.message, limit=exc.limit)

    submitted = [
        batch.SubmittedImage(
            filename=image.filename or f"image-{position + 1}",
            content_type=image.content_type,
            content=await image.read(),
        )
        for position, image in enumerate(images)
    ]
    submitted = _name_duplicates(submitted)

    return StreamingResponse(
        batch.stream(submitted, table),
        media_type="application/x-ndjson",
        headers={
            # Without this a proxy may buffer the whole response and hand it
            # over in one block at the end, which reinstates exactly the frozen
            # page NFR-2 forbids. It is a hint to intermediaries, not a
            # guarantee, and it is worth verifying against the load balancer at
            # deployment time (OQ-13).
            "Cache-Control": "no-store",
            "X-Accel-Buffering": "no",
        },
    )


def _name_duplicates(images: list[batch.SubmittedImage]) -> list[batch.SubmittedImage]:
    """Make every image part identifiable, which FR-8's fourth criterion needs.

    Two parts submitted under one filename cannot both be reported against that
    name without the results becoming ambiguous, and a part with no filename at
    all cannot be reported against anything. Both are renamed to a positional
    label here, so that every line in the stream identifies exactly one
    submitted part. The renamed part then matches no CSV row and is reported as
    `missing_application_row`, which names the real problem: the agent has to
    fix the filenames before the batch can be checked.
    """
    seen: set[str] = set()
    named: list[batch.SubmittedImage] = []
    for position, image in enumerate(images):
        name = image.filename
        if name in seen:
            name = f"{image.filename} (duplicate, part {position + 1})"
        seen.add(name)
        named.append(
            batch.SubmittedImage(
                filename=name, content_type=image.content_type, content=image.content
            )
        )
    return named
