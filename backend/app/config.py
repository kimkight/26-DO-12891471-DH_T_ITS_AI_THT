"""Runtime configuration, sourced entirely from environment variables.

No secrets are stored in the repository. See .env.example for the shape of the
environment and docs/05_ARCHITECTURE.md for how configuration is injected.

Governing requirements: NFR-11 (configuration through environment variables),
NFR-3 (no outbound calls on the default path), NFR-7 (input validation),
FR-3 and FR-7 (the thresholds and the ABV tolerance the comparison rules read).
"""

from __future__ import annotations

import os

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings.

    Defaults are chosen so that a fresh checkout runs with no network egress:
    ``enable_bedrock_fallback`` is off unless explicitly enabled
    (see docs/adr/0003-local-ocr-default-bedrock-optional.md).
    """

    model_config = SettingsConfigDict(env_prefix="TTB_", env_file=None, extra="ignore")

    app_name: str = "TTB Label Verifier"
    environment: str = "local"
    log_level: str = "INFO"

    # Extraction path. Off by default; the default path makes no outbound calls.
    enable_bedrock_fallback: bool = False
    bedrock_region: str = "us-east-1"
    bedrock_model_id: str = ""

    # Upload guards. Enforced before any image is decoded.
    max_upload_bytes: int = 10 * 1024 * 1024
    max_batch_files: int = 300

    # How many photographs of one label the single-label path accepts
    # (ADR 0007). Three because a label wraps a round bottle and no single
    # photograph shows all of it flat: front, back and the seam between them is
    # the most a submission needs, and no source asks for more. The batch path
    # stays one photograph per row.
    max_label_photos: int = 3
    allowed_mime_types: tuple[str, ...] = ("image/jpeg", "image/png", "image/webp", "image/tiff")

    # How many pages of an uploaded COLA document are read (ADR 0008, FR-11).
    # The application side of TTB F 5100.31 is page 1; the rest of the file is
    # instructions and the allowable-revisions table, which carry no applicant
    # values. A Public COLA Registry printout runs to one or two. Three is one
    # more than either needs, and it bounds what a 400-page PDF can cost when
    # the OCR fallback runs: that path reads each page the way it reads a label
    # photograph, so the page count is a latency limit as much as a parsing one.
    max_document_pages: int = 3

    # Matching thresholds. See docs/adr/0004-fuzzy-matching-with-review-band.md.
    match_threshold: int = 95
    review_threshold: int = 80

    # Allowed difference between the label ABV and the application ABV, in
    # percentage points. 0.0 is a compliance position rather than a tuning
    # starting point: the regulatory tolerances in 27 CFR 5.65, 4.36 and 7.65
    # govern actual against labeled content, and this tool compares two values
    # the applicant declared. See assumption A-12 in docs/ASSUMPTIONS.md.
    abv_tolerance: float = 0.0

    # Image preprocessing. The long edge the image is scaled to before OCR.
    # See docs/07_TEST_STRATEGY.md section 4 for the latency budget this feeds.
    ocr_long_edge_px: int = 1600

    # Turn a sideways photograph upright before reading it, using Tesseract's
    # orientation and script detection. On by default because the first real
    # photograph submitted to the deployed prototype was sideways and the engine
    # found none of its five fields.
    #
    # It is a setting rather than a constant because it is not free: the OSD
    # pass costs roughly as much again as the read it precedes, which matters
    # most on the batch path where that cost is paid once per image. The
    # measured figures are in docs/07_TEST_STRATEGY.md section 4.
    correct_orientation: bool = True

    # Batch execution. See docs/adr/0006-batch-execution-model.md.
    #
    # 0 means "derive it", because both values follow from figures already set
    # rather than from a number invented here. A derived default is visible in
    # the response and overridable by environment (NFR-11); a hardcoded one
    # would look like a measurement.
    batch_workers: int = 0
    max_batch_bytes: int = 0

    @property
    def effective_batch_workers(self) -> int:
        """How many images are decoded and read at once.

        ADR 0006 bounds concurrency by CPU rather than by network wait, because
        OCR runs in-process and is CPU bound (ADR 0003). The bound exists so
        that 300 simultaneous Tesseract invocations do not exhaust memory, not
        to hit a throughput figure: no source states a batch latency target
        (OQ-6).

        ``sched_getaffinity`` reports the cores this process may actually use,
        which is what a container CPU limit constrains; ``os.cpu_count``
        reports the host's. On a task pinned to a subset of the host's cores
        the two differ, and the smaller is the honest one. It is Linux only, so
        ``os.cpu_count`` is the fallback, and the floor of 1 keeps a
        single-core runner making progress. ``os.process_cpu_count`` would say
        this in one call but arrived in Python 3.13, and this project targets
        3.11.
        """
        if self.batch_workers > 0:
            return self.batch_workers
        if hasattr(os, "sched_getaffinity"):
            available = len(os.sched_getaffinity(0))
        else:
            available = os.cpu_count() or 1
        return max(1, available)

    @property
    def allowed_document_mime_types(self) -> tuple[str, ...]:
        """What an uploaded COLA document may be (FR-11, NFR-7).

        A PDF is what COLAs Online and the Public COLA Registry produce. The
        image types are the ones already accepted for label artwork, because a
        scan or a phone photograph of a printed form is the other way the
        document reaches an agent, and there is no reason for the two lists to
        drift apart.
        """
        return ("application/pdf", *self.allowed_mime_types)

    @property
    def effective_max_verify_bytes(self) -> int:
        """The largest single-label request body accepted, in bytes.

        ``(max_label_photos + 1) * max_upload_bytes``, for the same reason the
        batch envelope is derived rather than set: that product is the largest
        submission the stated limits already permit, and a smaller figure here
        would be a further limit no source asks for. The plus one is the
        optional COLA document (FR-11, ADR 0008), which is an upload in its own
        right and is bounded by the same per-file limit. Without it a submission
        of three photographs plus the application would be refused for being one
        file larger than the photographs alone.

        Each file is still checked exactly against ``max_upload_bytes`` after
        parsing, so this loosens only what the Content-Length guard rejects
        before reading, not what is accepted.
        """
        return (self.max_label_photos + 1) * self.max_upload_bytes

    @property
    def effective_max_batch_bytes(self) -> int:
        """The largest batch envelope accepted, in bytes.

        Derived as ``2 * max_batch_files * max_upload_bytes`` rather than set to
        a figure of its own, because that product is the largest batch the
        stated limits already permit, and inventing a smaller number here would
        impose a further limit no source asks for. The factor of two is
        ADR 0009: a batch carries one label image and one COLA document per
        label, and each of the two is an upload bounded by
        ``max_upload_bytes``. Before ADR 0009 the application side of a whole
        batch was one CSV of a few kilobytes, and the factor was one.

        Read the arithmetic before deploying: at the defaults this is 600 files
        times 10 MB, about 6 GiB, and FastAPI has the whole envelope parsed
        before the route runs. That is a task sizing input, not a memory
        guarantee, and it is twice what it was. It interacts with OQ-13 item 6
        and is recorded there.
        """
        if self.max_batch_bytes > 0:
            return self.max_batch_bytes
        return 2 * self.max_batch_files * self.max_upload_bytes


settings = Settings()
