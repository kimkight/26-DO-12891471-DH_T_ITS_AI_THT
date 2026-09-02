# syntax=docker/dockerfile:1

# ---------------------------------------------------------------------------
# Stage 1: build the frontend.
# ---------------------------------------------------------------------------
# Both base images are pinned by the digest of their multi-architecture
# manifest list as well as by tag (code review finding 12, #111). The tag says
# what the image is for a reader; the digest is what is pulled, and a
# re-published tag changes nothing here until someone changes this line.
# Dependabot's docker ecosystem understands the tag-plus-digest form and
# proposes the new digest when the tag moves within its pinned line
# (.github/dependabot.yml). Resolved 2026-09-02 from the Docker Hub registry.
FROM node:22-bookworm-slim@sha256:83f487e0a63425e5b4d146fb5e5be574bcbe1b7b843d3ebafdd95eaf7767a7e5 AS frontend-build

WORKDIR /build

# Copy manifests first so dependency installation is cached independently of
# source changes. `npm ci` installs exactly the tree in package-lock.json and
# fails if the lock file and package.json disagree, so the image is built from
# the same versions CI resolved.
# @playwright/test is a dev dependency of the accessibility test, and its
# postinstall script downloads browser binaries. This stage compiles the
# frontend and never opens a browser, so the download is skipped: it would add
# hundreds of megabytes to a layer that is discarded, and it would need network
# access to a host the build has no other reason to reach.
ENV PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1

COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund

COPY frontend/ ./
RUN npm run build

# ---------------------------------------------------------------------------
# Stage 2: runtime image, backend plus built frontend assets.
# ---------------------------------------------------------------------------
FROM python:3.11-slim-bookworm@sha256:528257d48c1da0dcecc2e725d1ae34498d60c965f1241e39cd6a85a8859bdf84 AS runtime

# Tesseract and the English language data are installed here because the
# default extraction path runs OCR locally, inside the container, with no
# outbound network calls. See docs/adr/0003-local-ocr-default-bedrock-optional.md.
# tesseract-ocr-osd carries the orientation and script detection model, which is
# what turns a sideways photograph upright before it is read; without it
# app/ocr.py reports the orientation as "unavailable" and reads the image as it
# arrived. libgl1 and libglib2.0-0 are OpenCV runtime dependencies.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        tesseract-ocr \
        tesseract-ocr-eng \
        tesseract-ocr-osd \
        libgl1 \
        libglib2.0-0 \
        curl \
    && rm -rf /var/lib/apt/lists/*

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Dependencies come from the lock file, with --require-hashes, so every wheel
# that lands in the image is verified against the digest recorded at
# resolution time. This runs before the application source is copied, so
# editing app/ does not invalidate the dependency layer.
COPY backend/requirements.lock ./
RUN pip install --no-cache-dir --require-hashes -r requirements.lock

# The project itself is installed with --no-deps: its dependencies are already
# present at the locked versions, and resolving them again here would defeat
# the lock file.
COPY backend/pyproject.toml ./
COPY backend/app ./app
RUN pip install --no-cache-dir --no-deps .

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
