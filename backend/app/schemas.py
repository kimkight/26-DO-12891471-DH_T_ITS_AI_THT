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

# Where an application value came from (FR-11, ADR 0008, ADR 0010). Reported per
# field because a submission can mix all three: an agent uploads the
# application, some values come out of its text layer, some out of the label
# artwork embedded in it, and one is corrected by hand. The result has to say
# which is which or the agent cannot tell what they are checking.
#
# These four are the precedence order, highest first. `parsed_from_form` is the
# document's own text, whether that is an AcroForm field or the text layer;
# `parsed_from_artwork` is a picture inside the document, read by OCR, which is
# weaker evidence than text and is therefore only used where the text was
# silent.
ApplicationSource = Literal["typed", "parsed_from_form", "parsed_from_artwork", "absent"]

# Where inside the document one value was read (ADR 0010). Finer than
# ApplicationSource, which is about the agent as well as the document.
DocumentValueSource = Literal["form_fields", "embedded_text", "embedded_artwork", "absent"]


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
            "Where the application value came from, in precedence order: typed "
            "by the agent, parsed from the uploaded COLA document's own text, "
            "parsed from label artwork embedded in that document, or absent "
            "because none of the three supplied it (FR-11, ADR 0008, ADR 0010)."
        ),
    )


class WarningDiffSegment(BaseModel):
    """One run of the character-level difference against 27 CFR 16.21 (FR-5).

    Reported so that an agent looking at a near miss can see at a glance whether
    it is an artifact of reading or a real defect. ``kind`` reads from the
    label's point of view, because that is what the agent is looking at.
    """

    kind: Literal["same", "added", "missing"] = Field(
        description=(
            "'same' is text the label and the regulation agree on, 'added' is "
            "text on the label the regulation does not have, and 'missing' is "
            "text the regulation requires that the label does not show."
        )
    )
    text: str


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
    edit_distance: int | None = Field(
        default=None,
        description=(
            "How many single-character edits separate the statement as printed "
            "from 27 CFR 16.21. Zero when they match; null when no statement "
            "was found (FR-5, ADR 0012)."
        ),
    )
    near_miss: bool = Field(
        default=False,
        description=(
            "Whether the difference is small enough to be routed to human "
            "judgement rather than reported as a flat mismatch. **Never a "
            "pass.** The comparison itself is still exact: "
            "`body_matches_regulation` is false here, and a near miss is one of "
            "the two failing outcomes, not a third kind of success (FR-5, "
            "ADR 0012)."
        ),
    )
    diff: list[WarningDiffSegment] = Field(
        default_factory=list,
        description=(
            "The character-level difference against 27 CFR 16.21, in reading "
            "order. Empty when the statement matches, and when none was found."
        ),
    )


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
    source: DocumentValueSource = Field(
        default="absent",
        description=(
            "Where in the document this value was read: 'form_fields' is an "
            "AcroForm field, 'embedded_text' is the file's own text layer or a "
            "page read as an image, 'embedded_artwork' is a picture of the "
            "label embedded in the document and read by OCR, and 'absent' means "
            "the document did not carry it (ADR 0010). Artwork never overrides "
            "text: it fills what the text left empty."
        ),
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
            "compares are not items on TTB F 5100.31 at all (A-17). Where any "
            "value or label side came out of the embedded artwork, the last "
            "note states that this is a self-consistency check rather than "
            "independent verification of a bottle (ADR 0010)."
        ),
    )
    artwork_images_found: int = Field(
        default=0,
        description=(
            "How many raster images embedded in the document cleared the size "
            "floor and were treated as candidate label artwork (ADR 0010). "
            "Images below the floor, which is where agency seals, barcodes and "
            "signature blocks sit, are not counted."
        ),
    )
    artwork_images_read: int = Field(
        default=0,
        description=(
            "How many of those images produced readable text. Zero with a "
            "non-zero artwork_images_found means the pictures were there and "
            "could not be read, which is a different thing for an agent to act "
            "on than a document that carries no pictures at all."
        ),
    )
    label_artwork_available: bool = Field(
        default=False,
        description=(
            "Whether one of those images can stand in as the label side of the "
            "check when the agent supplied no photograph of their own "
            "(ADR 0010). See VerificationResult.label_source."
        ),
    )


class FileClassification(BaseModel):
    """What one uploaded file was taken to be, and why (FR-12, ADR 0011).

    **Reported so a misclassification is visible rather than silent.** The
    single upload accepts PDFs and images in any mix and decides what each one
    is from the file itself rather than from which control it arrived in. That
    is right far more often than trusting the control was, and when it is wrong
    an agent has to be able to see it and act, which they cannot do if the
    decision is never stated.
    """

    filename: str = Field(description="The name the file was submitted under.")
    classified_as: Literal["application_document", "label_image"] = Field(
        description=(
            "Which side of the check this file was used as: the label "
            "application, or a picture of the label."
        )
    )
    basis: Literal[
        "pdf_header",
        "declared_pdf",
        "form_markers",
        "form_values",
        "no_form_markers",
        "undecodable",
    ] = Field(
        description=(
            "The evidence the classification rests on: the file's own PDF "
            "header, its declared type, COLA form wording found in the picture, "
            "a filled-in form value found in it, the absence of both, or a file "
            "that could not be opened."
        )
    )
    reason: str = Field(description="The same judgement as one sentence an agent can read.")
    used: bool = Field(
        default=True,
        description=(
            "False when the file was classified but not used, which happens "
            "only where more of one side was submitted than the check accepts."
        ),
    )


class ClassificationResult(BaseModel):
    """What POST /api/classify returns: the sorting, plus the application read.

    It exists so the interface can tell an agent what each file was taken to be,
    and can put the application values in front of them for confirmation, before
    any check runs. It compares nothing.
    """

    files: list[FileClassification] = Field(
        description="One entry per submitted file, in submission order."
    )
    application_document: ApplicationDocumentResult | None = Field(
        default=None,
        description=(
            "What the file classified as the application side was read to say, "
            "or null when no file classified that way."
        ),
    )
    label_images: int = Field(description="How many files classified as pictures of the label.")
    application_error: ErrorDetail | None = Field(
        default=None,
        description=(
            "Set when a file classified as the application side could not be "
            "read (FR-9). The classification still stands and is reported; what "
            "failed is the reading of it."
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

    exif_orientation: int | None = Field(
        default=None,
        description=(
            "The EXIF orientation tag found in the file, 1 to 8, or null when "
            "the file carried none. Reported alongside what was done with it, "
            "because a tag is a claim about the pixels rather than a fact: a "
            "non-zero `rotation_degrees` on a file that carried a tag means the "
            "tag was wrong and the quarter-turn check corrected it."
        ),
    )
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


class ReadPathDetail(BaseModel):
    """Whether preprocessing helped this photograph, and by how much.

    Reported for the same reason the orientation is: the choice is invisible in
    the result otherwise. The pipeline reads the preprocessed image and, unless
    that read comes back confident, reads the plain upright grayscale as well
    and keeps whichever scored higher. An agent looking at a poor result is
    entitled to know that preprocessing was tried and lost, and an operator
    reading batch latency is entitled to know which images paid for two reads.
    """

    variant: Literal["preprocessed", "plain"] = Field(
        description=(
            "Which image the reported text came from. 'preprocessed' is the "
            "adaptively thresholded and deskewed image; 'plain' is the upright "
            "grayscale with no preprocessing, which wins on soft-contrast "
            "photographs where thresholding destroys the text."
        )
    )
    preprocessed_confidence: float = Field(
        description="Mean word confidence of the preprocessed read, which always runs."
    )
    plain_confidence: float | None = Field(
        default=None,
        description=(
            "Mean word confidence of the plain read, or null when the "
            "preprocessed read scored well enough that the plain one was not run."
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
    origin: Literal["uploaded", "application_artwork"] = Field(
        default="uploaded",
        description=(
            "Where this label image came from: 'uploaded' is a photograph the "
            "agent submitted, 'application_artwork' is a picture of the label "
            "lifted out of the uploaded application document (ADR 0010). The "
            "second is a self-consistency check rather than a check of a "
            "physical bottle; see VerificationResult.self_consistency_note."
        ),
    )
    orientation: OrientationDetail = Field(
        description="How this photograph was turned before it was read."
    )
    ocr_confidence: float = Field(
        description="Mean Tesseract word confidence from 0 to 100 for this photograph."
    )
    read_path: ReadPathDetail = Field(
        description="Whether preprocessing or the plain grayscale produced the text kept."
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
    files: list[FileClassification] = Field(
        default_factory=list,
        description=(
            "What each submitted file was taken to be, in submission order "
            "(FR-12, ADR 0011). Empty for a request that used the older named "
            "parts and so had nothing to sort."
        ),
    )
    label_source: Literal["uploaded_photographs", "application_artwork"] = Field(
        default="uploaded_photographs",
        description=(
            "What the label side of this check was read from. "
            "'application_artwork' means the agent uploaded no photograph and "
            "the label artwork embedded in their application document was used "
            "instead (ADR 0010)."
        ),
    )
    self_consistency_note: str | None = Field(
        default=None,
        description=(
            "Set only when label_source is 'application_artwork'. It states, in "
            "the response rather than only in a document, that checking artwork "
            "taken out of an application against that same application is a "
            "self-consistency check and not independent verification of a "
            "bottle (ADR 0010)."
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
