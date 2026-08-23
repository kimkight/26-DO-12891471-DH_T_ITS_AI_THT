"""FastAPI application entry point.

Scope note: this module exposes the health endpoint and the single-label
verification endpoint in app.api (US-1 through US-7). Batch verification, FR-8
and ADR 0006, is not implemented yet; see the Status section of README.md and
docs/02_PROJECT_SCOPE.md.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, Request
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
