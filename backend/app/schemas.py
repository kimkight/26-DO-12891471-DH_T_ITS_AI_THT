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

``application_document`` and ``application_value_source`` carry FR-11: an agent
may upload the label application instead of typing the same values, and the
response has to say what was read off it and which of the two supplied each
value. The parsed block is reported separately from the comparison because a
parsed value is a reading of a document, not a fact about an application, and
the agent confirms it before a verification runs (ADR 0008).
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from app.compare import Outcome
from app.warning import BOLD_TYPE_NOTE, WARNING_PREFIX

FIELD_LABELS = {
    "brand_name": "Brand name",
    "class_type": "Class or type designation",
    "alcohol_content": "Alcohol content",
    "net_contents": "Net contents",
    "beverage_type": "Beverage type",
    "government_warning": "Government warning statement",
}

# Where an application value came from (FR-11, ADR 0008). Reported per field
# because a submission can mix the two: an agent uploads the application and
# corrects one value by hand, and the result has to say which is which or the
# agent cannot tell what they are checking.
ApplicationSource = Literal["typed", "parsed_from_form", "absent"]


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
    source_photo: int | None = Field(
        default=None,
        description=(
            "Which submitted photograph this value was read from, numbered from "
            "1 in submission order (ADR 0007). Null where the field was not "
            "found on any photograph."
        ),
    )
    application_value_source: ApplicationSource = Field(
        default="typed",
        description=(
            "Where the application value came from: typed by the agent, parsed "
            "from an uploaded COLA document, or absent because neither supplied "
            "it (FR-11, ADR 0008). A typed value always wins over a parsed one."
        ),
    )


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


class ParsedApplicationField(BaseModel):
    """One value read off an uploaded COLA document (FR-11, ADR 0008)."""

    name: str = Field(description="Machine name of the field, for example brand_name.")
    display_name: str = Field(description="How the field is named to an agent.")
    value: str | None = Field(
        default=None, description="What the document said, or null if it did not say."
    )
    found_on_document: bool = Field(
        description="False means the document did not carry this value (FR-1's rule, applied here)."
    )


class ApplicationDocumentResult(BaseModel):
    """What an uploaded COLA document was read to say, as a distinct block.

    **Surfaced for confirmation, never silently trusted.** FR-3's philosophy is
    that the tool recommends and the agent judges, and a parsed value is a
    reading of a document rather than a fact about an application. So it is
    reported here in its own right, separately from the comparison, and the
    interface puts it into editable fields before a verification runs. An
    agent's correction always wins (ADR 0008).
    """

    extraction_path: Literal["form_fields", "embedded_text", "ocr"] = Field(
        description=(
            "How the values were read. 'form_fields' means the PDF's AcroForm "
            "fields, which is where a filled-in copy of the downloadable form "
            "keeps them; 'embedded_text' means the file's own text layer, which "
            "is deterministic; 'ocr' means the pages were read as images, which "
            "carries the same accuracy and failure modes as reading a label "
            "photograph."
        )
    )
    pages_read: int = Field(description="How many pages of the document were read.")
    fields: list[ParsedApplicationField] = Field(
        description="One entry per application value, whether or not it was found."
    )
    fanciful_name: str | None = Field(
        default=None,
        description=(
            "Item 7 on TTB F 5100.31, carried because the document states it. It "
            "is not compared: no source states a rule that reads it."
        ),
    )
    class_type_code: str | None = Field(
        default=None,
        description=(
            "The numeric class or type code, where a Public COLA Registry "
            "printout carried one alongside the description. The description is "
            "what is compared."
        ),
    )
    notes: list[str] = Field(
        default_factory=list,
        description=(
            "Why a value is missing, where the reason is a property of the form "
            "rather than of this document. Three of the five values this tool "
            "compares are not items on TTB F 5100.31 at all (A-17)."
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


class OrientationDetail(BaseModel):
    """How the submitted image was turned before it was read (FR-1, FR-10).

    Reported because the correction is invisible in the result otherwise. A
    photograph the tool turned and then read well and a photograph the tool
    turned the wrong way and then read badly produce the same shape of
    response, and only this tells them apart. It is also what lets the
    interface say "we turned your photograph upright" rather than leaving an
    agent to wonder why a sideways photograph worked.
    """

    exif_transposed: bool = Field(
        description=(
            "Whether the EXIF orientation tag was applied. True means the file "
            "stored its pixels sideways and recorded which way up the camera was."
        )
    )
    rotation_degrees: int = Field(
        description=(
            "The clockwise quarter-turn applied after the EXIF transform, in "
            "degrees: 0, 90, 180 or 270."
        )
    )
    method: Literal["osd", "unavailable", "disabled"] = Field(
        description=(
            "Where the rotation came from. 'osd' is Tesseract's orientation and "
            "script detection; 'unavailable' means it could not judge, usually "
            "too little text, and the image was left as it arrived; 'disabled' "
            "means TTB_CORRECT_ORIENTATION is off."
        )
    )
    confidence: float | None = Field(
        default=None,
        description=(
            "Tesseract's confidence in the orientation. Null when no judgement "
            "was made. A value near zero means the answer was a guess."
        ),
    )


class PhotoResult(BaseModel):
    """One submitted photograph of the label, and how it read (ADR 0007).

    One label may be photographed up to three times, because a label wraps a
    round bottle and no single photograph shows all of it flat. Every photograph
    is reported, including the ones that failed: a submission where two of three
    photographs were unreadable produced a result from one photograph, and an
    agent deciding whether to trust it needs to know that.

    ``error`` is set only for a photograph that could not be read at all. It
    does not fail the verification while another photograph did read, which is
    the same rule FR-8 applies to a batch, applied within one label.
    """

    index: int = Field(description="Position in submission order, numbered from 1.")
    orientation: OrientationDetail = Field(
        description="How this photograph was turned before it was read."
    )
    ocr_confidence: float = Field(
        description="Mean Tesseract word confidence from 0 to 100 for this photograph."
    )
    text_found: bool = Field(description="Whether any text was read from this photograph.")
    error: ErrorDetail | None = Field(
        default=None,
        description="Why this photograph could not be read, or null if it was read.",
    )


class VerificationResult(BaseModel):
    """The full single-label response (US-1, FR-1 through FR-7, ADR 0007)."""

    fields: list[FieldResult]
    warning_detail: WarningResult
    photos: list[PhotoResult] = Field(
        description=(
            "One entry per submitted photograph, in submission order. A "
            "single-photograph submission has one entry."
        )
    )
    ocr_confidence: float = Field(
        description=(
            "Mean Tesseract word confidence from 0 to 100, over the photographs "
            "that read. Per-photograph figures are in `photos`."
        )
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
    application_document: ApplicationDocumentResult | None = Field(
        default=None,
        description=(
            "What an uploaded COLA document was read to say, or null when none "
            "was uploaded (FR-11, ADR 0008). Parsing it involves no network "
            "call and nothing is persisted."
        ),
    )


class BatchLine(BaseModel):
    """One line of the batch NDJSON stream (FR-8, NFR-2, ADR 0006).

    One JSON object per line, one line per item, emitted as each item finishes
    rather than in submission order. ``filename`` is what FR-8's fourth
    criterion requires: "The result identifies which label each result belongs
    to." It is null only on a batch-level error, which is a problem with the
    submission rather than with any one label.

    ``index`` and ``total`` exist for NFR-2's second criterion, that "batch
    progress is observable to the user rather than presenting as a frozen
    page". A client can render "42 of 300" from the first line it receives
    without waiting for the batch to end or counting parts itself.

    Exactly one of ``result`` and ``error`` is set. An error line carries no
    field outcomes at all, which is FR-9's last criterion applied per row.
    """

    filename: str | None = Field(
        description="The image this line belongs to. Null only on a batch-level error."
    )
    index: int = Field(description="1-based position of this line in the emission order.")
    total: int = Field(description="How many lines this batch will emit in total.")
    status: Literal["ok", "error"] = Field(description="Whether this item was verified.")
    result: VerificationResult | None = Field(
        default=None, description="The verification, on an ok line."
    )
    error: ErrorDetail | None = Field(
        default=None, description="What went wrong, on an error line."
    )
