"""The response contract: what a verification returns and what it discloses.

Governing requirements: FR-3 (every field result carries the label value, the
application value and the score, so an agent can judge the call), FR-2 (a field
the application did not supply reads as not compared, not as a mismatch), FR-6
and OOS-4 (the warning result reports capitalization separately and states that
bold type was not checked), NFR-1 (elapsed time is reported), NFR-3 (the
response says whether an external call was made), FR-9 (error responses carry no
field outcomes at all).

``external_call_made`` is ``False`` on every default-path response, and it is a
field rather than a comment because NFR-3's third criterion requires it:
"Enabling the fallback is visible in the response, so a user knows whether a
result involved an external call."
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.compare import Outcome
from app.warning import BOLD_TYPE_NOTE, WARNING_PREFIX

FIELD_LABELS = {
    "brand_name": "Brand name",
    "class_type": "Class or type designation",
    "alcohol_content": "Alcohol content",
    "net_contents": "Net contents",
    "government_warning": "Government warning statement",
}


class FieldResult(BaseModel):
    """One field, its two values, its score, its outcome, and why (FR-3)."""

    name: str = Field(description="Machine name of the field, for example brand_name.")
    display_name: str = Field(description="How the field is named to an agent.")
    found_on_label: bool = Field(
        description="False means the field could not be located on the label (FR-1)."
    )
    label_value: str | None = Field(
        default=None, description="The value read off the label, or null if not found."
    )
    application_value: str | None = Field(
        default=None, description="The value supplied with the application."
    )
    score: float | None = Field(
        default=None,
        description=(
            "Similarity score from 0 to 100 where one was computed. Null where "
            "the outcome came from a rule rather than a score, for example "
            "different units under A-13."
        ),
    )
    outcome: Outcome = Field(description="match, needs_review, mismatch, or not_compared.")
    reason: str = Field(description="Why this outcome, in terms an agent can check.")


class WarningResult(BaseModel):
    """The warning field's two checks, reported separately (FR-6)."""

    statement_found: bool
    prefix_as_printed: str | None = None
    prefix_is_capitalized: bool | None = Field(
        default=None,
        description=(
            f"Whether the {WARNING_PREFIX!r} prefix is in capital letters, as "
            "27 CFR 16.22(a)(2) requires. Null when no statement was found."
        ),
    )
    body_matches_regulation: bool = Field(
        description="Whether the statement text matches 27 CFR 16.21 word for word."
    )
    bold_type_checked: bool = Field(
        default=False,
        description="Always false. This prototype does not check bold type (OOS-4).",
    )
    bold_type_note: str = BOLD_TYPE_NOTE


class VerificationResult(BaseModel):
    """The full single-label response (US-1, FR-1 through FR-7)."""

    fields: list[FieldResult]
    warning_detail: WarningResult
    ocr_confidence: float = Field(
        description="Mean Tesseract word confidence from 0 to 100 for this image."
    )
    elapsed_ms: float = Field(description="End-to-end time inside the request handler (NFR-1).")
    ocr_ms: float = Field(description="Of which, decode, preprocessing and OCR.")
    external_call_made: bool = Field(
        default=False,
        description=(
            "False on the default path, which makes no outbound network call "
            "(NFR-3). True only when the optional Bedrock fallback ran."
        ),
    )


class ErrorDetail(BaseModel):
    """An error response. It carries no field outcomes at all (FR-9)."""

    code: str = Field(description="Stable machine code, for example unreadable_image.")
    message: str = Field(description="What went wrong, in the agent's terms.")
    limit: str | None = Field(
        default=None,
        description="The limit or accepted set that was exceeded, named explicitly (NFR-7).",
    )


class ErrorResponse(BaseModel):
    error: ErrorDetail
