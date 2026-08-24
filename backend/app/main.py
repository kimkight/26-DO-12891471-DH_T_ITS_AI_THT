"""FastAPI application entry point.

Scope note: this module exposes the health endpoint and the verification
endpoints in app.api, single-label (US-1 through US-7) and batch (US-9 through
US-11, FR-8, ADR 0006). The interface those endpoints serve is FR-10 and is
built in frontend/; see the Status section of README.md.

The exception handlers here exist so that every rejection leaves this service in
one documented shape. FR-9 requires a rejection to name the problem, and an
agent, or a client rendering for one, cannot read two different error bodies
depending on which layer refused the request.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.formparsers import MultiPartException

from app import __version__, api
from app.config import settings
from app.schemas import ErrorDetail, ErrorResponse

# Built frontend assets are copied here by the Dockerfile. When running the
# backend alone (for example under pytest) the directory will not exist, so the
# static mount is registered conditionally rather than failing at import time.
STATIC_DIR = Path(__file__).resolve().parent / "static"

app = FastAPI(
    title=settings.app_name,
    version=__version__,
    description="Verifies label artwork against application data.",
)


# Registered before the router so it runs before routing, which is what makes
# the size check happen before the body is read (NFR-7).
app.add_middleware(api.UploadSizeLimitMiddleware)
app.include_router(api.router)


@app.exception_handler(MultiPartException)
async def malformed_multipart(_: Request, exc: MultiPartException) -> JSONResponse:
    """Turn a malformed or oversize multipart body into the documented shape.

    Without this the parser's own 400 escapes with a different body, and FR-9
    requires every rejection to name the problem in one consistent way.
    """
    payload = ErrorResponse(
        error=ErrorDetail(
            code="malformed_upload",
            message=f"The upload could not be read as a form submission. {exc.message}",
            limit=f"maximum upload size: {settings.max_upload_bytes} bytes",
        )
    )
    return JSONResponse(status_code=400, content=payload.model_dump())


@app.exception_handler(RequestValidationError)
async def malformed_submission(_: Request, exc: RequestValidationError) -> JSONResponse:
    """Turn FastAPI's own validation error into the documented shape.

    Without this, a submission missing a required part escapes as FastAPI's
    ``{"detail": [...]}`` while every other rejection uses ``ErrorResponse``.
    FR-9 requires the problem to be named; it does not permit naming it in two
    different shapes depending on which layer refused.

    The message names the missing or wrong parts by location rather than
    echoing the submitted values, so nothing an applicant typed is reflected
    back into the response (NFR-6).
    """
    parts = sorted({name for name in (_part_name(error) for error in exc.errors()) if name})
    named = ", ".join(parts) if parts else "the submitted form"
    payload = ErrorResponse(
        error=ErrorDetail(
            code="invalid_submission",
            message=(
                f"The submission is missing something the request needs, or sent "
                f"it in the wrong form: {named}. Check that every image is "
                "attached as a file with a filename."
            ),
        )
    )
    return JSONResponse(status_code=422, content=payload.model_dump())


def _part_name(error: dict) -> str | None:
    """The name of the request part an error is about, or None.

    A location reads like ``("body", "images", 0)``: the envelope, the part
    name, then a position within it. The part name is the actionable half, so
    the position is dropped rather than reported as a bare "0".
    """
    for element in error.get("loc", ()):
        if isinstance(element, str) and element != "body":
            return element
    return None


@app.get("/api/health", tags=["operations"])
def health() -> dict[str, str]:
    """Liveness and readiness probe.

    Used by docker-compose, the container orchestrator health check, and the
    Application Load Balancer target group.
    """
    return {
        "status": "ok",
        "service": settings.app_name,
        "version": __version__,
        "environment": settings.environment,
    }


if STATIC_DIR.is_dir():
    app.mount("/assets", StaticFiles(directory=STATIC_DIR / "assets"), name="assets")

    @app.get("/", include_in_schema=False)
    def index() -> FileResponse:
        """Serve the single-page frontend shell."""
        return FileResponse(STATIC_DIR / "index.html")
