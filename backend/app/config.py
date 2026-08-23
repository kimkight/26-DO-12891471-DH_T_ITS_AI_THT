"""Runtime configuration, sourced entirely from environment variables.

No secrets are stored in the repository. See .env.example for the shape of the
environment and docs/05_ARCHITECTURE.md for how configuration is injected.

Governing requirements: NFR-11 (configuration through environment variables),
NFR-3 (no outbound calls on the default path), NFR-7 (input validation),
FR-3 and FR-7 (the thresholds and the ABV tolerance the comparison rules read).
"""

from __future__ import annotations

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
    allowed_mime_types: tuple[str, ...] = ("image/jpeg", "image/png", "image/webp", "image/tiff")

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


settings = Settings()
