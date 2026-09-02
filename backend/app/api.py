"""The HTTP surface: POST /api/verify, /api/verify-batch and /api/read-application.

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

There is a third route, ``POST /api/read-application``: it parses an uploaded
COLA document and compares nothing (FR-11, ADR 0008). It exists so that the
parsed values reach an agent as editable fields before a verification runs.

US-1 through US-7 and US-9 through US-11 are implemented here at the API level,
and US-23 is the COLA document path. The pipeline both verification routes run
is in ``app.verify``; the batch reconciliation, worker pool and stream are in
``app.batch``; the document parser is in ``app.application_form``. US-2 and
FR-10 are presentation requirements and are not part of this module.

The batch route takes label images and COLA documents, paired by filename stem
(FR-8, [ADR 0009](../../docs/adr/0009-batch-cola-documents.md)). It took a CSV
of application data until ADR 0009 superseded assumption A-14; the parser the
documents go through is the FR-11 one the single-label route uses.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import Annotated, TypeVar

import anyio
from fastapi import APIRouter, File, Form, UploadFile
from fastapi.responses import JSONResponse, StreamingResponse
from starlette.formparsers import MultiPartParser
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app import batch, timing
from app.application_form import UnreadableDocumentError, parse_application_document
from app.classify import ClassifiedFile, SubmittedFile, classify, describe
from app.config import settings
from app.ocr import OcrResult
from app.schemas import (
    ApplicationDocumentResult,
    ClassificationResult,
    ErrorDetail,
    ErrorResponse,
    FileClassification,
    VerificationResult,
)
from app.verify import (
    NO_FILES_MESSAGE,
    NO_LABEL_MESSAGE,
    LabelSource,
    VerificationError,
    build_result,
    check_document_media_type,
    check_size,
    document_result,
    resolve_application,
    verify_photos,
)

__all__ = ["UploadSizeLimitMiddleware", "build_result", "router"]

logger = logging.getLogger(__name__)

T = TypeVar("T")

# Starlette spools any multipart part over `spool_max_size` to a temporary file.
# The threshold is raised to the per-file limit so that every part the service
# accepts stays in memory. A part over the limit rolls over to a temporary file
# before `verify.check_size` refuses it after parsing, and that file is deleted
# with the request. NFR-6 is a promise about retention, not about a disk that
# is never touched, and docs/06_SECURITY_AND_COMPLIANCE.md section 3.2 says
# where the bytes live and how wide this window is; until v1.3.0 this comment
# said nothing within the limit reached the filesystem, which was true, and
# implied nothing above it did either, which was not (code review finding 4).
# This is a class attribute the parser reads through `self`, with no
# constructor override, so setting it here does reach every request.
#
# max_part_size is raised alongside it, but note what it does and does not do.
# The parser applies it to non-file parts only; a file part streams into the
# spooled file with no cap of its own. So this bounds the single-label form
# fields, not the uploads. Images are bounded exactly, after
# parsing, by verify.check_size. Note also that the parser takes max_part_size
# as a constructor argument defaulted to 1 MB and assigns it to the instance, so
# this class-level value is shadowed on every request; it is set for the case
# where a future caller constructs a parser without passing one, not relied on.
MultiPartParser.spool_max_size = settings.max_upload_bytes
MultiPartParser.max_part_size = settings.max_upload_bytes

router = APIRouter(prefix="/api", tags=["verification"])


# **The check runs in a worker thread, and the number of them is bounded**
# (v1.3.0, code review finding 8). Every Tesseract pass on the single-label
# path used to run on the event loop thread, so `GET /api/health` could not be
# answered until the request finished: measured at 3.34 s of waiting for a
# 3.35 s request in the review session, and 7.8 s on the deployed target for a
# three-photograph submission, against a 5 s health-check timeout that stops
# the task after three misses. The batch path never had this problem, because
# ADR 0006 gave it a pool.
#
# The limiter is not optional. anyio's default thread pool is forty threads,
# and forty concurrent OCR passes on a 1 vCPU, 8 GiB task would trade a stalled
# probe for an out-of-memory kill. It is sized like the batch pool, from the
# same setting, so an operator who pins TTB_BATCH_WORKERS to the task's CPU
# allocation has pinned this too. `to_thread.run_sync` copies the context, so
# the timing recording the route opened is the one the thread writes to;
# `_PDFIUM_LOCK` and `OMP_THREAD_LIMIT=1` already cover a worker thread, because
# the batch pool has always been one.
#
# Created on first use rather than at import, because a limiter is bound to
# the running event loop's backend.
_check_limiter: anyio.CapacityLimiter | None = None


def _limiter() -> anyio.CapacityLimiter:
    global _check_limiter  # noqa: PLW0603
    if _check_limiter is None:
        _check_limiter = anyio.CapacityLimiter(settings.effective_batch_workers)
    return _check_limiter


async def _off_the_loop(work: Callable[..., T], *args: object) -> T:
    """Run blocking work in a worker thread, at most `effective_batch_workers` at once."""
    return await anyio.to_thread.run_sync(work, *args, limiter=_limiter())


# What each upload route accepts as a whole request body, checked from
# Content-Length before the body is read. The two differ by construction: a
# batch envelope carries many images plus one COLA document each, so measuring
# it against the per-image limit would reject every batch of more than one
# label. Matching is
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
    if path == "/api/read-application":
        return settings.max_upload_bytes
    if path == "/api/classify":
        # The same envelope the single-label check accepts, because it is the
        # same pile of files: the agent chooses them once and both routes see
        # the whole set (FR-12, ADR 0011).
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
    (ADR 0007) plus one optional COLA document (ADR 0008), so its envelope limit
    is one more than that many times TTB_MAX_UPLOAD_BYTES: 40 MB on the
    defaults.

    **That loosens this guard, and the loosening is deliberate and bounded.**
    Before ADR 0007 a single-label body over TTB_MAX_UPLOAD_BYTES was refused
    here, without being read. It now takes a body up to four times that before
    this guard fires, and a 25 MB single-photograph submission is parsed, which
    means Starlette spools it to a temporary file once it passes the per-file
    limit, and then refused exactly by verify.check_size; the spooled file is
    deleted with the request (NFR-6, docs/06 section 3.2). The
    alternative was to bound the envelope at one photograph, which would reject
    every two-photograph submission, so there is no version of this that both
    accepts three photographs and refuses 25 MB from the header: the middleware
    cannot count the parts without reading the body it is trying not to read.
    What is kept is that the body is still bounded before it is read, at 40 MB
    on the defaults rather than 10 MB, and that every individual photograph and
    the application document are each still checked exactly against
    TTB_MAX_UPLOAD_BYTES. Lower TTB_MAX_LABEL_PHOTOS or TTB_MAX_UPLOAD_BYTES to
    tighten it.

    The batch route is measured against its own envelope limit, which is twice
    TTB_MAX_BATCH_FILES times TTB_MAX_UPLOAD_BYTES by default: a batch carries
    one label image and one COLA document per label (ADR 0009), and each of the
    two is an upload bounded by the same per-file limit. That bounds the
    request, not any one file in it: each image and each document is still
    checked exactly against TTB_MAX_UPLOAD_BYTES after parsing, and an oversize
    one is that row's error rather than the batch's.
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
    files: Annotated[
        list[UploadFile],
        File(
            description=(
                "Everything being submitted for one label, in one repeated "
                "part: the label application as a PDF or an image of one, "
                "photographs of the label, or any mix of the two. The server "
                "decides what each file is from the file rather than from the "
                "part it arrived in, and reports that per file in `files` "
                "(FR-12, ADR 0011)."
            )
        ),
    ] = [],  # noqa: B006
    image: Annotated[
        list[UploadFile],
        File(
            description=(
                "Label artwork, under the older name. One part, or the same "
                "part repeated for up to TTB_MAX_LABEL_PHOTOS photographs of "
                "the same label (ADR 0007). Kept so that a caller written "
                "against v1.0 keeps working; a file sent here still goes "
                "through the same classifier."
            )
        ),
        # Defaulted rather than required, so that a submission carrying only an
        # application document reaches the route and is checked against the
        # artwork inside it (ADR 0010). The default is never mutated; FastAPI
        # reads it and builds a new list.
    ] = [],  # noqa: B006
    application_document: Annotated[
        UploadFile | None,
        File(
            description=(
                "The label application, under the older name: a COLA document "
                "(PDF, or a scan or photograph of one). Read locally, with no "
                "call to the COLA system (FR-11, ADR 0008, OOS-1). Kept for the "
                "same reason `image` is; a file sent here goes through the same "
                "classifier."
            )
        ),
    ] = None,
    brand_name: Annotated[str, Form()] = "",
    class_type: Annotated[str, Form()] = "",
    alcohol_content: Annotated[str, Form()] = "",
    net_contents: Annotated[str, Form()] = "",
    beverage_type: Annotated[str, Form()] = "",
    cleared_fields: Annotated[
        list[str],
        Form(
            description=(
                "Application fields the agent emptied after the uploaded "
                "document filled them, repeated once per field. A cleared "
                "field is left out of the check rather than re-read from the "
                "document (v1.3.0, code review finding 29)."
            )
        ),
    ] = [],  # noqa: B006
) -> JSONResponse:
    """Verify one label from whatever was uploaded for it.

    **One repeated `files` part is the contract** (FR-12, ADR 0011): the label
    application, photographs of the label, or any mix, and the server decides
    what each file is from the file itself. `image` and `application_document`
    are the older names for the same two things and still work; whatever arrives
    in them goes through the same classifier, so a COLA PDF dropped into the
    photo part is still read as the application.

    More than one label picture is ADR 0007: a label wraps a round bottle, so no
    single photograph shows all of it flat, and the photographs are read
    independently and their fields merged.

    **No label picture at all is ADR 0010.** An applicant affixes the label
    artwork to the application, so a filed COLA document carries pictures of the
    labels. When none is uploaded and the document carries readable artwork, the
    largest such picture becomes the label side, and the response says so in
    `label_source` and carries the self-consistency note. When it carries none,
    the request is refused with a message naming the missing piece, which is an
    FR-9 message rather than a validation error on a field.

    The application values may be typed, or read from the uploaded COLA
    document, or both: a typed value overrides the parsed one field by field,
    and the response says which of the four sources each value came from
    (FR-11, ADR 0008, ADR 0010). Reading that document is document parsing, not
    the COLA system integration OOS-1 excludes: it opens no socket and needs no
    credentials.

    Nothing is kept and nothing about its content is logged (NFR-6).

    The reading runs in a worker thread behind a capacity limiter (v1.3.0), so
    the event loop, and `GET /api/health` with it, keeps answering while a
    label is being read; see `_off_the_loop`.
    """
    # **The recording opens here, which is the point of it** (NFR-1). Before
    # v1.1.0 the clock started inside `verify_photos`, after the multipart form
    # had been parsed, after the files had been classified and after the COLA
    # document had been read. On the application-document path those three are
    # most of the request, and none of them was in the number the response
    # called `elapsed_ms`. See app/timing.py for the measurement that showed it.
    with timing.recording() as record:
        return await _verify(
            record,
            files,
            image,
            application_document,
            {
                "brand_name": brand_name,
                "class_type": class_type,
                "alcohol_content": alcohol_content,
                "net_contents": net_contents,
                "beverage_type": beverage_type,
            },
            frozenset(cleared_fields),
        )


async def _verify(
    record: timing.Recording,
    files: list[UploadFile],
    image: list[UploadFile],
    application_document: UploadFile | None,
    application_values: dict[str, str],
    cleared_fields: frozenset[str] = frozenset(),
) -> JSONResponse:
    """The handler proper, inside the recording opened by the route.

    Split out only so that the recording is a `with` block around the whole of
    it rather than a try/finally wrapped around four return paths, each of which
    would be a place for the clock to stop early.
    """
    try:
        submitted = await _read_parts(files, image, application_document)
    except VerificationError as exc:
        return _error(exc.status_code, exc.code, exc.message, limit=exc.limit)

    if not submitted:
        # Distinct from "your document carried no artwork" below, because the
        # agent's next action differs: one needs a file, the other needs a
        # different file (FR-9).
        return _error(422, "no_files", NO_FILES_MESSAGE)

    # Everything that reads pixels, off the event loop and behind the limiter.
    try:
        checked = await _off_the_loop(
            _check_one_label, submitted, application_values, cleared_fields
        )
    except VerificationError as exc:
        return _error(exc.status_code, exc.code, exc.message, limit=exc.limit)
    result = checked.result

    # NFR-6: counts and timings only. No image content, no extracted value, no
    # application value, no filename.
    logger.info(
        "verification completed",
        extra={
            "bytes_received": sum(len(entry.file.content) for entry in checked.sorted_files),
            "photos_received": checked.photos_read,
            # A count of files and a count of each side. No filename, no
            # content, nothing either one said (NFR-6).
            "files_received": len(checked.sorted_files),
            "documents_classified": checked.documents_classified,
            "ocr_ms": result.ocr_ms,
            "beverage_type_supplied": bool(application_values["beverage_type"].strip()),
            # Counts and a path name only. No item value, no filename, nothing
            # the document said (NFR-6).
            "application_document_bytes": checked.document_bytes,
            "application_document_path": (
                result.application_document.extraction_path if result.application_document else None
            ),
            # A source name, not a value (NFR-6). It is here because an operator
            # reading latency needs to know which submissions paid for reading
            # the pictures inside a document (ADR 0010).
            "label_source": result.label_source,
        },
    )
    # Stamped here rather than in `build_result`, so that assembling the
    # response body is inside the number too. It is the last thing measured and
    # the last thing before serialisation, which is what "end to end inside the
    # handler" has to mean if it is to mean anything (NFR-1).
    result.elapsed_ms = record.total_ms
    if result.timings is not None:
        result.timings.total_ms = record.total_ms
        result.timings.unaccounted_ms = round(max(record.total_ms - record.accounted_ms, 0.0), 1)
    return JSONResponse(status_code=200, content=result.model_dump())


@dataclass(frozen=True)
class _Checked:
    """What `_check_one_label` hands back to the route, for the response and the log."""

    result: VerificationResult
    sorted_files: list[ClassifiedFile]
    documents_classified: int
    photos_read: int
    document_bytes: int


def _check_one_label(
    submitted: list[SubmittedFile],
    application_values: dict[str, str],
    cleared_fields: frozenset[str] = frozenset(),
) -> _Checked:
    """Sort, read and compare, in a worker thread. Raises `VerificationError`.

    This is the body of `POST /api/verify` from the moment the parts are in
    memory. It is synchronous on purpose: everything in it is Tesseract and
    PDFium work, and `_off_the_loop` is what keeps it off the event loop.
    """
    # Classification happens before anything is compared, and reads each image
    # exactly once; the read is handed on to whichever side the file lands on
    # (ADR 0011).
    sorted_files = classify(submitted)
    documents = [entry for entry in sorted_files if entry.side == "application_document"]
    labels = [entry for entry in sorted_files if entry.side == "label_image"]

    # Counted after sorting and before anything is compared, and named in the
    # message (FR-9, NFR-7). The bodies are in memory by now because FastAPI
    # parses the multipart form while resolving these parameters; the guarantee
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
    if not contents:
        artwork = parsed_application.label_artwork if parsed_application else None
        if artwork is None:
            raise VerificationError(code="no_label_to_check", message=NO_LABEL_MESSAGE)
        contents = [artwork.content]
        # **The read comes with it, so this picture is read once** (NFR-1).
        # `parse_application_document` has just put these exact bytes through
        # this exact pipeline to fill the application values; running them
        # through it again produced an identical result for a second full
        # Tesseract pass, which measurement on 2026-08-30 showed was about
        # half of this path's total time. This is the same reuse ADR 0011
        # already does with the classifier's read.
        pre_read = [parsed_application.label_artwork_read if parsed_application else None]
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
    )
    result.files = [_classification(entry) for entry in sorted_files]
    return _Checked(
        result=result,
        sorted_files=sorted_files,
        documents_classified=len(documents),
        photos_read=len(contents),
        document_bytes=document_bytes,
    )


@router.post(
    "/read-application",
    response_model=ApplicationDocumentResult,
    responses={
        413: {"model": ErrorResponse},
        415: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
    },
    summary="Read the application values off a COLA document, without verifying",
)
async def read_application(
    application_document: Annotated[
        UploadFile,
        File(description="A COLA document: a PDF, or a scan or photograph of one."),
    ],
) -> JSONResponse:
    """Parse a COLA document and return what it says, comparing nothing (FR-11).

    **This exists because of what FR-11 requires of the interface, not to give
    the API a second way in.** The parsed values have to reach the agent as
    editable fields *before* a verification runs, so that the agent confirms or
    corrects them and the check runs on what they confirmed (FR-3, ADR 0008).
    Reaching that through `POST /api/verify` would mean submitting the label
    photographs and running OCR over them once to read the form and again to
    run the check the agent then asked for.

    `POST /api/verify` still accepts the same part, for a caller that wants one
    request, and the precedence rule is the same in both places: a typed value
    overrides a parsed one.

    Nothing is kept (NFR-6) and no outbound call is made (NFR-3, OOS-1).
    """
    try:
        check_document_media_type(application_document.content_type)
        content = await application_document.read()
        check_size(content)
        parsed = await _off_the_loop(
            parse_application_document, content, application_document.content_type
        )
    except UnreadableDocumentError as exc:
        return _error(422, "unreadable_application_document", str(exc))
    except VerificationError as exc:
        return _error(exc.status_code, exc.code, exc.message, limit=exc.limit)

    # NFR-6: a byte count and a path name. Nothing the document said.
    logger.info(
        "application document read",
        extra={
            "application_document_bytes": len(content),
            "application_document_path": parsed.path,
        },
    )
    return JSONResponse(status_code=200, content=document_result(parsed).model_dump())


async def _read_parts(
    files: list[UploadFile],
    image: list[UploadFile],
    application_document: UploadFile | None,
) -> list[SubmittedFile]:
    """Read every uploaded part into memory, checking each before it is decoded.

    The three parts are folded into one list here and sorted by the classifier
    afterwards, which is the whole of FR-12 on the server: the part a file
    arrived in stops meaning anything the moment it has been read.

    The media-type check happens per file and before anything is decoded
    (NFR-7). It is the document list, PDF plus the image types, because the one
    part now accepts both; a file whose type is not on that list is refused with
    the accepted set named.
    """
    parts = [*files, *image, *([application_document] if application_document else [])]
    submitted: list[SubmittedFile] = []
    for position, part in enumerate(parts, start=1):
        check_document_media_type(part.content_type)
        content = await part.read()
        check_size(content)
        submitted.append(
            SubmittedFile(
                filename=part.filename or f"file-{position}",
                content_type=part.content_type,
                content=content,
            )
        )
    return submitted


def _classification(entry: ClassifiedFile, used: bool = True) -> FileClassification:
    """One sorted file, as the response reports it (FR-12)."""
    return FileClassification(
        filename=entry.filename,
        classified_as=entry.side,
        basis=entry.basis,
        reason=describe(entry),
        used=used,
    )


@router.post(
    "/classify",
    response_model=ClassificationResult,
    responses={
        413: {"model": ErrorResponse},
        415: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
    },
    summary="Say what each uploaded file is, and read the application side",
)
async def classify_uploads(
    files: Annotated[
        list[UploadFile],
        File(
            description=(
                "The files an agent has chosen for one label: the application, "
                "photographs of the label, or any mix."
            )
        ),
    ] = [],  # noqa: B006
) -> JSONResponse:
    """Sort the uploaded files and read the application side, verifying nothing.

    **This exists for the interface, not to give the API a second way in**, in
    exactly the sense `POST /api/read-application` does (ADR 0008). An agent
    dropping files into one control has to be told what each one was taken to
    be, and has to see the application values before a check runs so they can
    confirm or correct them. A caller with no interface should send everything
    to `POST /api/verify` in one request instead, which classifies the same way
    and reads each image once.

    **It reads the document's text layer and not the pictures inside it**
    ([ADR 0017](../../docs/adr/0017-read-the-artwork-once.md)). The response
    says so in `application_document.artwork_read`, and the values the artwork
    would have supplied arrive with the check that reads it. A caller that wants
    the artwork values without verifying has `POST /api/read-application`, which
    still reads everything.

    Nothing is compared, nothing is kept (NFR-6), and no outbound call is
    made (NFR-3).
    """
    try:
        submitted = await _read_parts(files, [], None)
    except VerificationError as exc:
        return _error(exc.status_code, exc.code, exc.message, limit=exc.limit)

    if not submitted:
        return _error(422, "no_files", NO_FILES_MESSAGE)

    payload = await _off_the_loop(_sort_and_read, submitted)

    # NFR-6: counts only. No filename, no content, nothing any file said.
    logger.info(
        "uploads classified",
        extra={
            "files_received": len(payload.files),
            "documents_classified": sum(
                1 for entry in payload.files if entry.classified_as == "application_document"
            ),
            "labels_classified": payload.label_images,
        },
    )
    return JSONResponse(status_code=200, content=payload.model_dump())


def _sort_and_read(submitted: list[SubmittedFile]) -> ClassificationResult:
    """The body of `POST /api/classify`, in a worker thread (see `_off_the_loop`)."""
    sorted_files = classify(submitted)
    documents = [entry for entry in sorted_files if entry.side == "application_document"]
    labels = [entry for entry in sorted_files if entry.side == "label_image"]

    parsed = None
    application_error = None
    if documents:
        try:
            parsed = parse_application_document(
                documents[0].file.content,
                documents[0].file.content_type,
                pre_read=documents[0].read,
                # **The artwork is not read here (ADR 0017).** This route runs
                # the moment an agent picks a file, and its job is to fill the
                # boxes. Reading every picture inside the document to fill two
                # of them cost about five seconds, and then `POST /api/verify`
                # read the same pictures again a moment later, because the check
                # needs them for the label side. One submission, one document,
                # two full Tesseract passes over the same artwork, in two
                # requests the agent waits through one after the other.
                read_artwork=False,
            )
        except UnreadableDocumentError as exc:
            # The classification stands and is reported; what failed is reading
            # the file, and the message says so (FR-9).
            application_error = ErrorDetail(
                code="unreadable_application_document", message=str(exc), limit=None
            )

    return ClassificationResult(
        # Only the first application-side file is read, so any further one is
        # reported as classified and not used rather than silently dropped.
        files=[_classification(entry, used=entry not in documents[1:]) for entry in sorted_files],
        application_document=document_result(parsed) if parsed else None,
        label_images=len(labels),
        application_error=application_error,
    )


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
    summary="Verify many labels against their COLA documents, paired by filename",
)
async def verify_batch(
    images: Annotated[
        list[UploadFile],
        # Defaulted rather than required so that a submission with no images at
        # all reaches the route and gets the message below, which says what to
        # do about it, instead of the generic missing-part rejection. The
        # default is never mutated; FastAPI reads it and builds a new list.
        File(description="Label artwork, one part per image, repeated."),
    ] = [],  # noqa: B006
    application_documents: Annotated[
        list[UploadFile],
        File(
            description=(
                "The COLA documents, one part per document, repeated. Each pairs "
                "with the image of the same name before its file extension "
                "(ADR 0009)."
            )
        ),
    ] = [],  # noqa: B006
) -> Response:
    """Verify a batch of labels and stream the results (FR-8, NFR-2, ADR 0006).

    **A batch is label images plus COLA documents, paired by filename stem**
    (ADR 0009). `0001-stones-throw.png` pairs with `0001-stones-throw.pdf`: the
    stem is the filename with its final extension removed, compared without
    regard to case. Each document is read by the FR-11 parser and what it says
    is the application side for that label. There is no CSV: A-14 invented that
    format and ADR 0009 supersedes it.

    The response is `application/x-ndjson`: one JSON object per line, each
    naming the image it belongs to, emitted as each label finishes rather than
    in submission order. Nothing is persisted; the stream is the only copy of
    the results (D-9, NFR-6).

    Four rejections happen before any image is read, and each names what was
    exceeded (FR-9, NFR-7):

    * more images than `TTB_MAX_BATCH_FILES`, which is FR-8's third criterion,
      "the request is rejected with a message naming the limit, before any file
      is processed";
    * more documents than the same limit, for the same reason;
    * a request body over the batch envelope limit, caught in middleware from
      Content-Length before the body is read at all;
    * a submission carrying no images, or no documents at all.

    Everything else is a per-row error on its own line, which is what keeps one
    bad image from costing an agent the other 299 results (FR-8, US-10).
    """
    # FR-8, third criterion. Counted before anything is read, decoded or
    # compared. The bodies are in memory by now, because FastAPI parses the
    # multipart form while resolving these parameters; "before any file is
    # processed" is the guarantee the requirement states and the one kept here.
    #
    # Both sides are counted against the same limit, because the limit is on
    # labels and a batch carries one document per label (A-1, ADR 0009).
    for count, part in ((len(images), "images"), (len(application_documents), "documents")):
        if count > settings.max_batch_files:
            detail = batch.over_count_error(count, part=part)
            return _error(413, detail.code, detail.message, limit=detail.limit)

    if not images:
        return _error(
            422,
            "empty_batch",
            "No images were submitted. Attach the label images and one COLA "
            "document for each, named to match.",
        )

    if not application_documents:
        # Batch level rather than per row, for the reason the CSV refusal it
        # replaces was batch level: with no documents at all there is nothing to
        # compare any label against, and repeating one message 300 times down
        # the stream would tell an agent nothing the first line did not.
        return _error(
            422,
            "missing_application_documents",
            "No application documents were submitted. Attach one COLA document "
            "for each label image, named to match the image before its file "
            "extension: 0001-stones-throw.png pairs with 0001-stones-throw.pdf.",
        )

    submitted = [
        batch.SubmittedImage(
            filename=image.filename or f"image-{position + 1}",
            content_type=image.content_type,
            content=await image.read(),
        )
        for position, image in enumerate(images)
    ]
    submitted = _name_duplicates(submitted)
    table = batch.collect_documents(
        [
            batch.SubmittedDocument(
                filename=document.filename or f"document-{position + 1}",
                content_type=document.content_type,
                content=await document.read(),
            )
            for position, document in enumerate(application_documents)
        ]
    )

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
    submitted part. Renaming does not change the pairing stem, which is taken
    before the parenthetical suffix, so two parts under one filename still share
    a stem and are both reported as `duplicate_label_stem` (ADR 0009). That
    names the real problem: the agent has to fix the filenames before the batch
    can be checked.
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
