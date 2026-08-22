# syntax=docker/dockerfile:1

# ---------------------------------------------------------------------------
# Stage 1: build the frontend.
# ---------------------------------------------------------------------------
# Base images are pinned by digest at release time. See
# docs/06_SECURITY_AND_COMPLIANCE.md; the TODO below tracks that step.
# TODO: pin both base images by sha256 digest before the first tagged release.
FROM node:26-bookworm-slim AS frontend-build

WORKDIR /build

# Copy manifests first so dependency installation is cached independently of
# source changes.
COPY frontend/package.json ./
# No package-lock.json is committed yet (see docs/OPEN_QUESTIONS.md, OQ-3), so
# this uses `npm install`. Switch to `npm ci` once a lockfile exists.
RUN npm install --no-audit --no-fund

COPY frontend/ ./
RUN npm run build

# ---------------------------------------------------------------------------
# Stage 2: runtime image, backend plus built frontend assets.
# ---------------------------------------------------------------------------
FROM python:3.11-slim-bookworm AS runtime

# Tesseract and the English language data are installed here because the
# default extraction path runs OCR locally, inside the container, with no
# outbound network calls. See docs/adr/0003-local-ocr-default-bedrock-optional.md.
# libgl1 and libglib2.0-0 are OpenCV runtime dependencies.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        tesseract-ocr \
        tesseract-ocr-eng \
        libgl1 \
        libglib2.0-0 \
        curl \
    && rm -rf /var/lib/apt/lists/*

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY backend/pyproject.toml ./
COPY backend/app ./app
RUN pip install --no-cache-dir ".[ocr,matching]"

# Built frontend assets are served by the backend container as static files.
COPY --from=frontend-build /build/dist ./app/static

# Run as an unprivileged user. Created after installation so that application
# files stay owned by root and are not writable at runtime.
RUN useradd --create-home --uid 10001 --shell /usr/sbin/nologin appuser
USER 10001

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl --fail --silent http://localhost:8000/api/health || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
