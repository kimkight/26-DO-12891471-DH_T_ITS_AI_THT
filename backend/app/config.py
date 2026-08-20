"""Runtime configuration, sourced entirely from environment variables.

No secrets are stored in the repository. See .env.example for the shape of the
environment and docs/05_ARCHITECTURE.md for how configuration is injected.
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


settings = Settings()
