"""The single-image verification pipeline, shared by the one-label and batch paths.

Governing requirements: FR-1 and FR-2 (extract the five fields and compare them
against application data), FR-3 (one outcome per field), FR-9 (an undecodable
file, an image with no text, a disallowed type and an oversize file each return
a clear message, and no error path returns a match), NFR-1 (elapsed time is
reported), NFR-3 (the default path makes no outbound call and says so).

This module exists because FR-8 gives the same pipeline a second caller. The
batch path in ``app.batch`` has to run exactly what ``POST /api/verify`` runs,
or the two would drift and a batch result would stop meaning what a single
result means. Keeping the pipeline here rather than in ``app.api`` also keeps
the import graph acyclic: ``app.api`` imports ``app.batch``, and both import
this.

Failures are raised as ``VerificationError`` rather than returned as HTTP
responses, because the two callers need them in different shapes: the
single-label route turns one into a JSON error body, and the batch stream turns
one into a result line for that row without failing the request (FR-8, NFR-2).
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Literal

from app.application_form import (
    APPLICATION_FIELDS,
    SELF_CONSISTENCY_NOTE,
    ParsedApplication,
)
from app.compare import Outcome, compare_abv, compare_net_contents, compare_text
from app.config import settings
from app.ocr import Orientation, ReadPath, UndecodableImageError, extract_text
from app.parse import ParsedFields, parse_fields
from app.schemas import (
    FIELD_LABELS,
    ApplicationDocumentResult,
    ApplicationSource,
    ErrorDetail,
    FieldResult,
    OrientationDetail,
    ParsedApplicationField,
    PhotoResult,
    ReadPathDetail,
    VerificationResult,
    WarningResult,
)
from app.warning import WARNING_STATEMENT, WarningCheck

COMPARED_FIELDS = ("brand_name", "class_type", "alcohol_content", "net_contents")

# What the label side of a check was read from (ADR 0010). A label lifted out of
# the application document is a self-consistency check, and the response says so
# rather than letting the two look alike.
LabelSource = Literal["uploaded_photographs", "application_artwork"]


def _size_limit_text() -> str:
    """Built per call, not at import.

    NFR-7's last criterion is that a rejection names the limit that was
    exceeded, and NFR-11 puts the limits in the environment. A module constant
    would name whatever the limit was when the module was first imported, which
    is the same value in a deployed process and a different one anywhere the
    setting is changed after import, including every test that varies it.
    """
    return f"maximum upload size: {settings.max_upload_bytes} bytes"


def _type_limit_text() -> str:
    return f"accepted types: {', '.join(settings.allowed_mime_types)}"


@dataclass(frozen=True)
class VerificationError(Exception):
    """One image could not be verified, and why.

    ``status_code`` is carried on the error rather than decided by the caller so
    that the single-label route and the batch stream cannot disagree about what
    a given failure means. ``limit`` is the value that was exceeded, named
    explicitly, which is NFR-7's last criterion and FR-9's third and fourth.
    """

    code: str
    message: str
    status_code: int = 422
    limit: str | None = None

    def __str__(self) -> str:
        return self.message


def check_media_type(content_type: str | None) -> None:
    """Reject a disallowed type before anything is decoded (NFR-7, FR-9)."""
    if content_type not in settings.allowed_mime_types:
        raise VerificationError(
            code="unsupported_media_type",
            message=(
                f"{content_type or 'The submitted file'} is not an accepted image "
                "type. Send one of the accepted types instead."
            ),
            status_code=415,
            limit=_type_limit_text(),
        )


def check_document_media_type(content_type: str | None) -> None:
    """The same guard for an uploaded COLA document (FR-11, NFR-7, FR-9).

    A separate list rather than the label one, because a PDF is the ordinary
    shape of this document and is not something to accept as label artwork.
    """
    if content_type not in settings.allowed_document_mime_types:
        raise VerificationError(
            code="unsupported_application_document",
            message=(
                f"{content_type or 'The submitted file'} is not an accepted type "
                "for a label application. Send a PDF, or a scan or photograph of "
                "the form, or type the application values instead."
            ),
            status_code=415,
            limit=(
                "accepted application document types: "
                f"{', '.join(settings.allowed_document_mime_types)}"
            ),
        )


# How a document-side source maps onto the source reported per field. The
# document distinguishes an AcroForm field from a text layer; the comparison
# does not, because both are text the file itself states and neither went
# through a recognition step. What the comparison does distinguish is text from
# artwork (ADR 0010).
_DOCUMENT_SOURCES: dict[str, ApplicationSource] = {
    "form_fields": "parsed_from_form",
    "embedded_text": "parsed_from_form",
    "embedded_artwork": "parsed_from_artwork",
}


def resolve_application(
    typed: dict[str, str], parsed: ParsedApplication | None
) -> tuple[dict[str, str], dict[str, ApplicationSource]]:
    """Decide each application value, and record where it came from (FR-11).

    **The precedence is typed, then the document's text, then the artwork
    embedded in the document, then absent** (ADR 0010). The first two thirds of
    that were always here. The third is new: a value the text layer did not
    carry may have been read off a picture of the label inside the same
    document, and it arrives already resolved by ``app.application_form``, which
    never lets artwork override text.

    **A typed value always wins.** An agent who corrects a field has read the
    document and disagreed with what was read off it, and the tool defers to the
    agent everywhere else it makes a judgement (FR-3, OOS-8). A blank field is
    not a correction: it is the absence of one, so the parsed value stands.

    The returned source map is reported per field, because a submission can mix
    all three and a result that did not say which was which would leave an agent
    unable to tell what they were checking. It matters most for the artwork: a
    value recognized off a picture can be misread in a way a value read out of a
    text layer cannot.
    """
    values: dict[str, str] = {}
    sources: dict[str, ApplicationSource] = {}
    for name in APPLICATION_FIELDS:
        entered = (typed.get(name) or "").strip()
        from_document = (parsed.values.get(name) if parsed else None) or ""
        if entered:
            values[name] = entered
            sources[name] = "typed"
        elif from_document:
            values[name] = from_document
            sources[name] = _DOCUMENT_SOURCES.get(
                (parsed.value_sources.get(name) if parsed else None) or "", "parsed_from_form"
            )
        else:
            values[name] = ""
            sources[name] = "absent"
    return values, sources


def document_result(parsed: ParsedApplication) -> ApplicationDocumentResult:
    """The parsed block, reported in its own right rather than folded in."""
    return ApplicationDocumentResult(
        extraction_path=parsed.path,
        pages_read=parsed.pages_read,
        fields=[
            ParsedApplicationField(
                name=name,
                display_name=FIELD_LABELS[name],
                value=parsed.values.get(name),
                found_on_document=parsed.values.get(name) is not None,
                source=parsed.value_sources.get(name, "absent"),
            )
            for name in APPLICATION_FIELDS
        ],
        fanciful_name=parsed.fanciful_name,
        class_type_code=parsed.class_type_code,
        notes=parsed.notes,
        artwork_images_found=parsed.artwork_images_found,
        artwork_images_read=parsed.artwork_images_read,
        label_artwork_available=parsed.label_artwork is not None,
    )


def check_size(content: bytes) -> None:
    """Reject an oversize image exactly, after parsing (NFR-7, FR-9).

    The single-label path also rejects on Content-Length in middleware, before
    the body is read. This is the exact check on the file itself, and it is the
    only size check the batch path has: a batch envelope's Content-Length says
    nothing about any one image inside it.
    """
    if len(content) > settings.max_upload_bytes:
        raise VerificationError(
            code="file_too_large",
            message=(
                "The uploaded file is larger than this service accepts. Send a smaller image."
            ),
            status_code=413,
            limit=_size_limit_text(),
        )


NO_TEXT_MESSAGE = (
    "The image was read but no text could be extracted from it. This is not the "
    "same as the fields failing to match: nothing was compared."
)


def verify_image(
    content: bytes,
    application: dict[str, str],
    *,
    application_sources: dict[str, ApplicationSource] | None = None,
    application_document: ApplicationDocumentResult | None = None,
) -> VerificationResult:
    """Verify one label from one photograph.

    Kept as its own entry point because that is what the batch path submits: one
    image per label, paired with one COLA document (FR-8, ADR 0006, ADR 0007,
    ADR 0009). It is a call to ``verify_photos`` with a list of one, so a batch
    row runs exactly the code a single-photograph submission runs.

    The two FR-11 arguments are passed straight through. A batch row supplies
    them, because every value on the batch path is read off that row's document
    rather than typed; a caller that omits them gets the response this function
    always returned.
    """
    return verify_photos(
        [content],
        application,
        application_sources=application_sources,
        application_document=application_document,
    )


NO_LABEL_MESSAGE = (
    "There is nothing to check the application against. The application "
    "document was read, but it carries no label artwork this tool could read, "
    "so there is no label side to compare. Add a photo of the label and run the "
    "check again."
)


@dataclass(frozen=True)
class _Read:
    """One photograph, read or failed. Internal to the merge below."""

    index: int
    parsed: ParsedFields | None
    orientation: Orientation
    confidence: float
    ocr_ms: float
    read_path: ReadPath = ReadPath()
    error: VerificationError | None = None


def verify_photos(
    contents: list[bytes],
    application: dict[str, str],
    *,
    application_sources: dict[str, ApplicationSource] | None = None,
    application_document: ApplicationDocumentResult | None = None,
    label_source: LabelSource = "uploaded_photographs",
) -> VerificationResult:
    """Read every photograph of one label and compare the union (ADR 0007).

    Each photograph is decoded, turned upright and read on its own, and the
    fields found across all of them are merged: a field counts as found if any
    photograph shows it, and where two photographs both show it the reading with
    the higher per-field OCR confidence wins, ties going to the earlier
    photograph. The response says which photograph each value came from.

    A photograph that cannot be read does not fail the submission while another
    one did read. That is the FR-8 rule for a batch, applied inside one label,
    and for the same reason: an agent who took three photographs should not lose
    the two good ones to the one that was out of focus. Every photograph is
    still reported, so the result never looks like it used more evidence than it
    had.

    Raises ``VerificationError`` only when no photograph could be read at all
    (FR-9). Nothing is persisted (NFR-6). The media type and size checks are
    deliberately not called here: both have to happen before the bytes are in
    hand on the single-label path, so the caller runs them.
    """
    started = time.perf_counter()
    reads = [_read_one(index, content) for index, content in enumerate(contents, start=1)]
    usable = [read for read in reads if read.parsed is not None]

    if not usable:
        raise _combined_failure(reads)

    merged, sources = _merge(usable)
    elapsed_ms = (time.perf_counter() - started) * 1000
    return build_result(
        merged,
        application,
        round(sum(read.confidence for read in usable) / len(usable), 1),
        ocr_ms=round(sum(read.ocr_ms for read in reads), 1),
        elapsed_ms=elapsed_ms,
        photos=[_photo_result(read, label_source) for read in reads],
        sources=sources,
        application_sources=application_sources,
        application_document=application_document,
        label_source=label_source,
    )


def _read_one(index: int, content: bytes) -> _Read:
    """Decode, turn upright, read and parse one photograph. Never raises."""
    try:
        ocr = extract_text(content)
    except UndecodableImageError as exc:
        # Distinct from "no text found" below, because the agent's next action
        # differs: a corrupt file needs resending, a blank one needs a better
        # photograph (FR-9, Jenny Park interview).
        return _Read(
            index=index,
            parsed=None,
            orientation=Orientation(),
            confidence=0.0,
            ocr_ms=0.0,
            error=VerificationError(code="unreadable_image", message=str(exc)),
        )

    if not ocr.has_text:
        return _Read(
            index=index,
            parsed=None,
            orientation=ocr.orientation,
            confidence=ocr.mean_confidence,
            ocr_ms=ocr.elapsed_ms,
            read_path=ocr.read_path,
            error=VerificationError(code="no_text_found", message=NO_TEXT_MESSAGE),
        )

    return _Read(
        index=index,
        parsed=parse_fields(ocr.lines),
        orientation=ocr.orientation,
        confidence=ocr.mean_confidence,
        ocr_ms=ocr.elapsed_ms,
        read_path=ocr.read_path,
    )


def _combined_failure(reads: list[_Read]) -> VerificationError:
    """What to raise when not one photograph could be read (FR-9).

    A single photograph keeps exactly the error it always returned, so nothing
    about the one-photograph contract changes. Several photographs get their own
    code, because "all three of your photographs were unreadable" is a different
    thing for an agent to act on than "your photograph was unreadable", and
    FR-9 requires the message to name the problem rather than approximate it.
    """
    if len(reads) == 1:
        return reads[0].error or VerificationError(code="no_text_found", message=NO_TEXT_MESSAGE)

    codes = {read.error.code for read in reads if read.error}
    detail = (
        "None of them could be decoded as an image."
        if codes == {"unreadable_image"}
        else "No text could be read from any of them."
        if codes == {"no_text_found"}
        else "Some could not be decoded and no text could be read from the rest."
    )
    return VerificationError(
        code="all_photos_unreadable",
        message=(
            f"All {len(reads)} photographs of this label were unreadable. {detail} "
            "Nothing was compared."
        ),
    )


# Located by pattern, so confidence is the only evidence there is about which
# of two readings is better.
_PATTERN_FIELDS = ("alcohol_content", "net_contents")
# Located by type size, so type size is what decides between two readings too.
_TYPE_SIZE_FIELDS = ("brand_name", "class_type")
_MERGED_FIELDS = (*_TYPE_SIZE_FIELDS, *_PATTERN_FIELDS)


def _merge(reads: list[_Read]) -> tuple[ParsedFields, dict[str, int]]:
    """Take each field from the photograph that read it best (ADR 0007).

    **Each field is merged by the signal that located it**, which is the whole
    of the rule and the reason it is not one line.

    Alcohol content and net contents are found by pattern, so the only thing
    that separates two readings of them is how confidently each was read.

    The brand name and the class or type designation are found by type size:
    on a label the brand name is the largest text (see app.parse). Merging
    those two by confidence would let the small print on a photograph of the
    back of the bottle, read perfectly, outscore the brand name on a photograph
    of the front. So they are merged by type size as well, which is comparable
    between photographs because every image is scaled to the same long edge
    before it is read.

    The warning is chosen differently again, and deliberately: see
    ``_pick_warning``.

    In every case an exact tie goes to the earlier photograph, so the result
    does not depend on which of two equal readings the iterator reached first.
    """
    values: dict[str, str | None] = {}
    sources: dict[str, int] = {}

    for name in _MERGED_FIELDS:
        candidates = [read for read in reads if getattr(read.parsed, name) is not None]
        if not candidates:
            values[name] = None
            continue
        best = max(candidates, key=_ranker(name))
        values[name] = getattr(best.parsed, name)
        sources[name] = best.index

    warning_read = _pick_warning(reads)
    if warning_read is not None:
        sources["government_warning"] = warning_read.index

    return (
        ParsedFields(
            brand_name=values["brand_name"],
            class_type=values["class_type"],
            alcohol_content=values["alcohol_content"],
            net_contents=values["net_contents"],
            warning=warning_read.parsed.warning if warning_read else reads[0].parsed.warning,
            warning_text=warning_read.parsed.warning_text if warning_read else None,
        ),
        sources,
    )


def _ranker(name: str):
    """The sort key that picks between two readings of one field."""
    if name in _TYPE_SIZE_FIELDS:
        return lambda read: (
            read.parsed.prominence.get(name, 0.0),
            read.parsed.confidence.get(name, 0.0),
            -read.index,
        )
    return lambda read: (read.parsed.confidence.get(name, 0.0), -read.index)


def _pick_warning(reads: list[_Read]) -> _Read | None:
    """Choose the photograph the warning is reported from.

    The longest located statement wins, ties going to the higher confidence and
    then to the earlier photograph. Confidence alone is the wrong rule here: a
    statement running off the edge of the frame is read with perfect confidence
    and is simply incomplete, and it would beat the photograph that captured the
    whole thing.

    **This does not soften FR-5.** Length separates a photograph that saw more
    of the statement from one that saw less; it does not separate a compliant
    statement from a defective one. An altered or added word does not shorten
    the text, and an omitted word can only be reported at all from a photograph
    that shows the whole statement. The residual risk, that two photographs both
    show the whole warning and one is misread longer than the other, is recorded
    in ADR 0007 rather than dismissed.
    """
    found = [read for read in reads if read.parsed.warning.found]
    if not found:
        return None
    return max(
        found,
        key=lambda read: (
            len(read.parsed.warning_text or ""),
            read.parsed.confidence.get("government_warning", 0.0),
            -read.index,
        ),
    )


def _photo_result(read: _Read, label_source: LabelSource = "uploaded_photographs") -> PhotoResult:
    return PhotoResult(
        index=read.index,
        origin="application_artwork" if label_source == "application_artwork" else "uploaded",
        orientation=OrientationDetail(
            exif_orientation=read.orientation.exif_orientation,
            exif_transposed=read.orientation.exif_transposed,
            rotation_degrees=read.orientation.rotation_degrees,
            method=read.orientation.method,
            confidence=read.orientation.confidence,
        ),
        ocr_confidence=read.confidence,
        read_path=ReadPathDetail(
            variant=read.read_path.variant,
            preprocessed_confidence=read.read_path.preprocessed_confidence,
            plain_confidence=read.read_path.plain_confidence,
        ),
        text_found=read.parsed is not None,
        error=None
        if read.error is None
        else ErrorDetail(code=read.error.code, message=read.error.message, limit=read.error.limit),
    )


def build_result(
    parsed: ParsedFields,
    application: dict[str, str],
    ocr_confidence: float,
    *,
    ocr_ms: float,
    elapsed_ms: float | None = None,
    photos: list[PhotoResult] | None = None,
    sources: dict[str, int] | None = None,
    application_sources: dict[str, ApplicationSource] | None = None,
    application_document: ApplicationDocumentResult | None = None,
    label_source: LabelSource = "uploaded_photographs",
) -> VerificationResult:
    """Compare every field and assemble the response (FR-2, FR-3).

    Split out from the route so the comparison layer can be exercised without an
    HTTP client, and so scripts/measure.py runs exactly the code the API runs.

    ``photos`` and ``sources`` carry ADR 0007's per-photograph reporting. Both
    are optional so that a caller holding parsed fields and no images, which is
    what the comparison tests and scripts/measure.py are, still gets a valid
    response: one photograph is then assumed and no field is attributed.

    ``application_sources`` and ``application_document`` carry FR-11. Both are
    optional too, and a caller that omits them gets exactly the response this
    function always returned: every supplied application value reads as typed,
    which is what it was, and no parsed block is reported.
    """
    attribution = sources or {}
    value_sources = application_sources or {}
    comparisons = {
        "brand_name": compare_text(parsed.brand_name, application.get("brand_name")),
        "class_type": compare_text(parsed.class_type, application.get("class_type")),
        "alcohol_content": compare_abv(parsed.alcohol_content, application.get("alcohol_content")),
        "net_contents": compare_net_contents(parsed.net_contents, application.get("net_contents")),
    }
    label_values = {
        "brand_name": parsed.brand_name,
        "class_type": parsed.class_type,
        "alcohol_content": parsed.alcohol_content,
        "net_contents": parsed.net_contents,
    }

    fields = [
        FieldResult(
            name=name,
            display_name=FIELD_LABELS[name],
            found_on_label=label_values[name] is not None,
            label_value=label_values[name],
            application_value=application.get(name) or None,
            score=comparison.score,
            outcome=comparison.outcome,
            reason=comparison.reason,
            source_photo=attribution.get(name),
            application_value_source=value_sources.get(
                name, "typed" if application.get(name) else "absent"
            ),
        )
        for name, comparison in comparisons.items()
    ]
    fields.append(
        _warning_field(parsed.warning, parsed.warning_text, attribution.get("government_warning"))
    )

    return VerificationResult(
        fields=fields,
        photos=photos
        or [
            PhotoResult(
                index=1,
                orientation=OrientationDetail(
                    exif_orientation=None,
                    exif_transposed=False,
                    rotation_degrees=0,
                    method="disabled",
                    confidence=None,
                ),
                ocr_confidence=ocr_confidence,
                read_path=ReadPathDetail(
                    variant="preprocessed",
                    preprocessed_confidence=ocr_confidence,
                    plain_confidence=None,
                ),
                text_found=True,
            )
        ],
        warning_detail=WarningResult(
            statement_found=parsed.warning.found,
            prefix_as_printed=parsed.warning.prefix_found,
            prefix_is_capitalized=parsed.warning.prefix_is_upper_case,
            body_matches_regulation=parsed.warning.body_matches,
        ),
        ocr_confidence=ocr_confidence,
        elapsed_ms=round(ocr_ms if elapsed_ms is None else elapsed_ms, 1),
        ocr_ms=round(ocr_ms, 1),
        external_call_made=False,
        application_document=application_document,
        label_source=label_source,
        self_consistency_note=(
            SELF_CONSISTENCY_NOTE if label_source == "application_artwork" else None
        ),
    )


def _warning_field(
    warning: WarningCheck, warning_text: str | None, source_photo: int | None = None
) -> FieldResult:
    """The warning as one field row, with no review band (FR-5).

    The comparison side is the regulation rather than the application form: the
    required text is fixed by 27 CFR 16.21, so there is nothing for an applicant
    to declare and nothing to type in.
    """
    outcome = Outcome.MATCH if warning.passes else Outcome.MISMATCH
    return FieldResult(
        name="government_warning",
        display_name=FIELD_LABELS["government_warning"],
        found_on_label=warning.found,
        label_value=warning_text,
        application_value=WARNING_STATEMENT,
        score=None,
        outcome=outcome,
        reason=f"{warning.reason} {warning.bold_type_note}",
        source_photo=source_photo,
    )
