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
# `read_from_tick` is the fifth, added with ADR 0016: item 5's product type is
# three check boxes, and a ticked box is in the pixels of the page rather than in
# its text. It sits beside `parsed_from_artwork` rather than with
# `parsed_from_form` because both went through a recognition step and a text
# layer did not, and it is separate from it because a form's own box is not the
# label artwork.
ApplicationSource = Literal[
    "typed", "parsed_from_form", "parsed_from_artwork", "read_from_tick", "absent"
]

# Where inside the document one value was read (ADR 0010, ADR 0016). Finer than
# ApplicationSource, which is about the agent as well as the document.
DocumentValueSource = Literal[
    "form_fields", "embedded_text", "embedded_artwork", "product_type_box", "absent"
]


class SegmentationDetail(BaseModel):
    """How this photograph was cut up before its words were read (FR-1, FR-10).

    Filed label artwork is often one flat sheet carrying several panels side by
    side, and until v1.1.0 the reader assembled its words into lines across the
    whole width of it, so a sentence on one panel could end with two words from
    another. What stops that is cutting the sheet at its gutters first and
    grouping words inside a column second, and this reports what that cut found.

    Reported rather than kept internal for the same reason the orientation is.
    An agent holding a value has no way to tell a field read off the wrong panel
    from a field read badly, and those two need different things done about
    them. One column and bounds spanning the whole image is a sheet that was not
    cut at all, which is every single-panel label.
    """

    columns: int = Field(
        description=(
            "How many columns the sheet was cut into at its gutters, left to "
            "right. 1 means no blank on the sheet was wide enough to be a "
            "gutter, and the reading is exactly what it would have been before "
            "this existed."
        )
    )
    blocks: int = Field(
        description=(
            "How many distinct Tesseract layout blocks the words fell into "
            "across all the columns. A line never spans two of them."
        )
    )
    column_bounds: list[tuple[int, int]] = Field(
        default_factory=list,
        description=(
            "The cuts themselves, as (left, right) pixel pairs in the image as "
            "it was read, left edge inclusive and right edge exclusive. They "
            "cover the whole width with no gaps, so every word falls in exactly "
            "one column."
        ),
    )


class TextRegionDetail(BaseModel):
    """Which part of the segmented sheet one field's value was read from.

    ``column`` is the panel, numbered left to right from zero, and ``block`` is
    Tesseract's own layout block inside it. An agent who sees a brand name
    should be able to see that it came from the front panel, and an agent
    looking at a surprising value should be able to see that it came from
    somewhere the value has no business coming from.
    """

    column: int = Field(description="The column, numbered left to right from zero.")
    block: int = Field(description="Tesseract's layout block number within that column.")


class FieldResult(BaseModel):
    """One field, its two values, its score, its outcome, and why (FR-3)."""

    name: str = Field(description="Machine name of the field, for example brand_name.")
    display_name: str = Field(description="How the field is named to an agent.")
    found_on_label: bool = Field(
        description=(
            "False means the field was not found on the label (FR-1). Where the "
            "application declared a value, this reports whether that value was "
            "found by searching the label for it (ADR 0015); where it declared "
            "none, it reports whether the extractor could locate one."
        )
    )
    label_value: str | None = Field(
        default=None,
        description=(
            "What the label carries for this field, or null if not found. Where "
            "the field was decided by searching, this is the label's own printing "
            "of the matched run, so an agent can see the label's casing beside "
            "the application's (FR-4)."
        ),
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
    outcome: Outcome = Field(
        description=(
            "match, needs_review, mismatch, not_compared, or artwork_derived. "
            "The last is not a verdict about agreement (FR-14, ADR 0013): it "
            "marks a row whose application value was read off the same label "
            "artwork that supplied the label side, so the two values compared "
            "are one reading of one picture and could not have disagreed. It is "
            "excluded from any count of fields that match, and it never carries "
            "a score."
        )
    )
    reason: str = Field(description="Why this outcome, in terms an agent can check.")
    label_region: TextRegionDetail | None = Field(
        default=None,
        description=(
            "Which panel of the label the value was found in, or null where "
            "the field was not found on the label. See SegmentationDetail for "
            "what the numbers mean. This is what replaces an extracted value as "
            "the useful half of the row: an agent can see that the brand was "
            "found on the front panel rather than in the small print (ADR 0015)."
        ),
    )
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
    artwork_read: bool = Field(
        default=True,
        description=(
            "Whether the embedded pictures were put through OCR on this "
            "reading (ADR 0017). False on the prefill pass, which takes the "
            "document's text layer alone and leaves the pictures to the check "
            "that reads them anyway. A caller has to be able to tell that from "
            "a document carrying no pictures, because artwork_images_read is "
            "zero in both cases and only one of them is a gap the agent has to "
            "fill."
        ),
    )
    artwork_images_rejected: list[RejectedImageDetail] = Field(
        default_factory=list,
        description=(
            "Every embedded raster image that did not clear the floor, with the "
            "reason it did not. Reported because the commonest rejection on a "
            "filed application is the applicant's own handwritten signature, "
            "and a rejection nobody can see is one nobody can check. The "
            "picture itself never appears here, or in a log, or on disk."
        ),
    )
    label_artwork_page: int | None = Field(
        default=None,
        description=(
            "The page the chosen label artwork was lifted from, or null when no "
            "image was chosen. Stated because a document carries several "
            "pictures and an agent reading a poor result is entitled to know "
            "which one was read."
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


class RejectedImageDetail(BaseModel):
    """One embedded image that was not treated as candidate label artwork.

    The page, the size, and the named reason. Deliberately not the picture and
    not a word of what it showed: on a filed application the commonest
    rejection is the applicant's handwritten signature, which is personal data
    (NFR-6).
    """

    page: int = Field(description="The page the image sat on, numbered from 1.")
    width: int = Field(description="Its width in pixels, as the file stores it.")
    height: int = Field(description="Its height in pixels, as the file stores it.")
    reason: Literal["short_edge", "area", "aspect_ratio", "unreadable"] = Field(
        description=(
            "Why it was not treated as label artwork. 'short_edge' and 'area' "
            "are the absolute size floors. 'aspect_ratio' is the shape test, "
            "which is the one a higher-resolution scan cannot defeat: a "
            "signature strip is wide and short at any resolution. 'unreadable' "
            "means it cleared the floor and could not be decoded."
        )
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


class RotationScoreDetail(BaseModel):
    """What one candidate rotation scored when the image was actually read."""

    rotation_degrees: int = Field(description="The clockwise turn that was scored, in degrees.")
    confidence: float = Field(description="Mean Tesseract word confidence at that turn.")
    words: int = Field(description="How many words were read at that turn.")


class OrientationCheckDetail(BaseModel):
    """The second opinion on a low-confidence orientation verdict (FR-1, A-15).

    Tesseract's orientation detection is right in 46 of 48 measured cases and
    keeps the decision wherever it is confident (ADR 0003). Where it is not, its
    answer is scored against the opposite turn by mean word confidence and the
    better one is kept.

    `candidates` always holds exactly two entries, and deliberately not four.
    Tesseract's own layout analysis already corrects a quarter-turn, so an
    upright image and the same image turned 90 degrees produce identical output
    and identical scores; a score that cannot separate those two is no use for
    choosing between them. It separates a turn from its opposite cleanly, which
    is the one axis this check is asked to decide.
    """

    osd_rotation_degrees: int = Field(description="The turn Tesseract's own detection chose.")
    osd_confidence: float = Field(description="Its confidence in that turn.")
    floor: float = Field(
        description="The confidence at or above which the verdict would have been taken as final."
    )
    candidates: list[RotationScoreDetail] = Field(
        description="The two turns that were scored: the one chosen and its 180-degree opposite."
    )
    chosen_rotation_degrees: int = Field(description="The turn that was kept and applied.")
    overrode_osd: bool = Field(
        description=(
            "Whether the opposite turn scored higher and replaced the verdict. "
            "False means the scores agreed with Tesseract, or tied, and its "
            "answer stood."
        )
    )


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
    method: Literal["osd", "osd_180_check", "unavailable", "disabled"] = Field(
        description=(
            "Where the rotation came from. 'osd' is Tesseract's orientation and "
            "script detection, taken at its word; 'osd_180_check' means it "
            "answered below the confidence floor and its answer was scored "
            "against the opposite turn, which is reported in `check`; "
            "'unavailable' means it could not judge, usually too little text, "
            "and the image was left as it arrived; 'disabled' means "
            "TTB_CORRECT_ORIENTATION is off."
        )
    )
    confidence: float | None = Field(
        default=None,
        description=(
            "Tesseract's confidence in its own orientation verdict. Null when "
            "no judgement was made. A value near zero means the answer was a "
            "guess, and below the floor reported in `check.floor` it was "
            "treated as one."
        ),
    )
    check: OrientationCheckDetail | None = Field(
        default=None,
        description=(
            "The second opinion taken when Tesseract's confidence fell under "
            "the floor, or null when it did not. Reported in full because a "
            "rotation that overrode Tesseract's own verdict is exactly the "
            "decision an agent looking at a poor result has to be able to audit."
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

    variant: Literal["preprocessed", "plain", "colour"] = Field(
        description=(
            "Which image the reported text came from. 'preprocessed' is the "
            "adaptively thresholded and deskewed image; 'plain' is the upright "
            "grayscale with no preprocessing, which wins on soft-contrast "
            "photographs where thresholding destroys the text; 'colour' is the "
            "image as the file holds it, which wins on label artwork printed in "
            "more than two tones, where flattening to luminance drops a whole "
            "ink class."
        )
    )
    preprocessed_confidence: float = Field(
        default=0.0,
        description=(
            "Mean word confidence of the preprocessed read, or 0.0 when a "
            "confident colour read ended the comparison before it ran."
        ),
    )
    plain_confidence: float | None = Field(
        default=None,
        description=(
            "Mean word confidence of the plain read, or null when the "
            "comparison was already settled and it was not run."
        ),
    )
    colour_confidence: float | None = Field(
        default=None,
        description=(
            "Mean word confidence of the colour read, or null when the image "
            "carried no colour a grayscale conversion would have discarded, in "
            "which case reading it would have repeated the plain read exactly."
        ),
    )
    decided_by: Literal["short_circuit", "confidence", "coverage"] = Field(
        default="short_circuit",
        description=(
            "How the winning read was chosen. 'short_circuit' means the first "
            "read scored well enough that nothing else ran. 'confidence' means "
            "it scored clearly above every other read. 'coverage' means two "
            "reads were equally confident about what each of them read and the "
            "one that recovered more text was kept, which is the case mean "
            "confidence alone cannot decide: a word that was never read lowers "
            "no score."
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
    segmentation: SegmentationDetail = Field(
        default_factory=lambda: SegmentationDetail(columns=1, blocks=0, column_bounds=[]),
        description="How this photograph's sheet was cut into panels before it was read.",
    )
    text_found: bool = Field(description="Whether any text was read from this photograph.")
    error: ErrorDetail | None = Field(
        default=None,
        description="Why this photograph could not be read, or null if it was read.",
    )


class PhaseTimings(BaseModel):
    """Where a request's time went, measured rather than inferred (NFR-1).

    **Every figure here was recorded by a timer around the work it names. None
    is a subtraction.** That distinction is the whole reason this block exists:
    the field the response used to call `elapsed_ms` measured only the label-side
    OCR, and the interface presented the difference between it and the browser's
    wall clock as network time. It was not network time. It was document
    parsing, artwork extraction and a second OCR pass nobody was counting.

    The phase fields are **disjoint**: no phase is opened inside another, so they
    sum to `accounted_ms`. What `total_ms` has left over is in
    `unaccounted_ms`, reported as its own line rather than folded into whichever
    phase is nearest. That is multipart handling, response construction, and the
    small change between spans; if it ever grows, it is visible instead of
    hiding inside a number that claims to mean something else.
    """

    total_ms: float = Field(
        description=(
            "Everything inside the request handler, from entry to the response "
            "being built. This is the figure NFR-1's five-second target is "
            "about. It does not include time on the wire or in the browser, "
            "which the server cannot see and does not guess at."
        )
    )
    classify_ocr_ms: float = Field(
        default=0.0,
        description=(
            "Reading an uploaded image to decide whether it is a form or a label (ADR 0011)."
        ),
    )
    document_pdfium_ms: float = Field(
        default=0.0,
        description=(
            "Everything the uploaded PDF gives up without recognition: its text "
            "layer, its AcroForm fields, the embedded images lifted out of it, "
            "and any page rendered for the OCR fallback. Serialized behind one "
            "lock, because PDFium is not thread-safe."
        ),
    )
    document_ocr_ms: float = Field(
        default=0.0,
        description="Reading an application document that arrived as an image rather than a PDF.",
    )
    page_ocr_ms: float = Field(
        default=0.0,
        description=(
            "Reading PDF pages as images, which happens only when the file carried no text layer."
        ),
    )
    artwork_ocr_ms: float = Field(
        default=0.0,
        description=(
            "Reading the label artwork embedded in the application document "
            "(ADR 0010). On a filing whose form states no alcohol content and no "
            "net contents, which is the ordinary case under A-17, this is where "
            "those values come from."
        ),
    )
    item_five_ocr_ms: float = Field(
        default=0.0,
        description=(
            "Recognizing item 5's three check box captions on a rendered page "
            "(ADR 0016). Zero on every document that carried a text layer, which "
            "states those captions exactly and for nothing; a scanned or "
            "photographed form is the only input that pays for this."
        ),
    )
    label_ocr_ms: float = Field(
        default=0.0,
        description=(
            "Reading the label side. Zero when the label side is artwork already "
            "read under artwork_ocr_ms, because that read is reused rather than "
            "repeated."
        ),
    )
    compare_ms: float = Field(
        default=0.0, description="Comparing the fields and assembling this response."
    )
    ocr_ms: float = Field(
        default=0.0,
        description=(
            "Every Tesseract pass in this request, wherever it ran: the sum of "
            "classify_ocr_ms, document_ocr_ms, page_ocr_ms, artwork_ocr_ms, "
            "item_five_ocr_ms and label_ocr_ms."
        ),
    )
    ocr_passes: int = Field(
        default=0,
        description=(
            "How many separate pictures were read end to end. The count is the "
            "half that makes the duration diagnosable: three passes where one "
            "would do is a fact about the code, and a slow machine is not."
        ),
    )
    tesseract_reads: int = Field(
        default=0,
        description=(
            "How many times the engine was invoked on an image inside those "
            "passes. Always at least ocr_passes and often more: one picture "
            "costs an orientation call, up to two more where that call came "
            "back unsure and its answer was scored against the opposite turn, "
            "and one per image variant compared. Reported because a pass count "
            "alone cannot show the engine being run five times for one picture."
        ),
    )
    accounted_ms: float = Field(default=0.0, description="The sum of the named phases above.")
    unaccounted_ms: float = Field(
        default=0.0,
        description=(
            "total_ms minus accounted_ms: multipart handling, response "
            "construction, and the gaps between spans. Reported rather than "
            "attributed, because nobody measured what is in it."
        ),
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
    elapsed_ms: float = Field(
        description=(
            "End-to-end time inside the request handler (NFR-1): from entry to "
            "the response being built, covering multipart handling, "
            "classification, document parsing, embedded image extraction, every "
            "OCR pass, the comparison and response construction. **Before "
            "v1.1.0 this field measured only the label-side OCR span**, which on "
            "the application-document path was about half the request; see "
            "`timings` for the breakdown."
        )
    )
    ocr_ms: float = Field(
        description=(
            "Of which, decode, preprocessing and OCR, across every pass in the "
            "request rather than the label side alone."
        )
    )
    timings: PhaseTimings | None = Field(
        default=None,
        description=(
            "The phase breakdown, present on any response produced inside a "
            "request. Null where the pipeline was called directly, for example "
            "by scripts/measure.py, which opens no recording."
        ),
    )
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
