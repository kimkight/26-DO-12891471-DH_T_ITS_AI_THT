"""FastAPI application entry point.

Scope note: this module currently exposes only the health endpoint. Label
extraction and comparison are not implemented yet; see the Status section of
README.md and docs/02_PROJECT_SCOPE.md.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app import __version__
from app.config import settings

# Built frontend assets are copied here by the Dockerfile. When running the
# backend alone (for example under pytest) the directory will not exist, so the
# static mount is registered conditionally rather than failing at import time.
STATIC_DIR = Path(__file__).resolve().parent / "static"

app = FastAPI(
    title=settings.app_name,
    version=__version__,
    description=(
        "Prototype API for verifying alcohol beverage label artwork "
        "against application data."
    ),
)


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
