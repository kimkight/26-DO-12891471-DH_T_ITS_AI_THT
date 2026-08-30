"""Read the application-side values off an uploaded COLA document.

Governing requirements: FR-11 (accept the label application as an alternative to
typing the same values), FR-2 (those values are what the label is compared
against), FR-9 (a document that cannot be read returns a clear message and no
field reports a match), NFR-3 (no outbound network call: the document is parsed
here, in this process), NFR-6 (nothing is persisted), OOS-1.

**This is not the COLA integration OOS-1 excludes, and the difference is the
whole basis for the feature.** OOS-1 rules out integrating with the COLA system:
no API calls, no COLAs Online authorization, no registry lookups. Nothing here
does any of those. What is accepted is a copy of a document the applicant
already has, uploaded by the agent in the same way a label photograph is
uploaded, and read locally. It needs no credentials and it opens no socket. See
docs/adr/0008-cola-form-as-application-input.md.

**Three ways in, tried in order.** A COLA document reaches an agent in one of
three shapes and each hides its values somewhere different:

1. *Form fields.* An applicant's filled-in copy of the downloadable form keeps
   its values in AcroForm fields. They are not in the page's text layer at all,
   so reading the page would find the blank template's captions and nothing
   else.
2. *Text layer.* COLAs Online output and a Public COLA Registry printout are
   digitally generated, so the characters are in the file. Extraction is
   deterministic: no recognition step, no confidence figure, no misread.
3. *OCR.* A scan or a photograph of a printed form carries pixels only. It goes
   through exactly the Tesseract pipeline label artwork goes through, and
   inherits its accuracy and its failure modes.

The first two are tried on every PDF; OCR runs only when neither found a single
mapped value, because rasterizing and reading pages costs about what reading a
label photograph costs and there is nothing to gain by paying it for a document
that has already answered.

**Four, in fact: the document carries its own label artwork.** An applicant
affixes the label artwork to the application, so a filed PDF carries pictures of
the labels alongside the typed items. Three of the five values this tool
compares are not items on the form at all, which is assumption A-17, and on the
author's own document, 2026-08-29, they were sitting inside those pictures: the
alcohol content and the net contents are absent from the text layer exactly as
A-17 says, and both are printed on the flat label artwork embedded in the file.
So every embedded raster image at or above a size floor is read through the same
Tesseract pipeline label artwork goes through, and what it says fills the fields
the text layer left empty. It never overrides the text layer. The precedence,
end to end, is: typed by the agent, then the document's text layer or form
fields, then the embedded artwork, then absent. See
[ADR 0010](../../docs/adr/0010-embedded-label-artwork.md).

**Comparing artwork lifted out of the application against the application it
came from is a self-consistency check.** It proves the artwork on file carries
the mandatory elements and that they agree with the typed form data. It is not
independent verification of a physical bottle, and nothing here should be read
as claiming it is; that still needs a photograph of the bottle.

**What the form does not carry.** The item map below is transcribed from
TTB F 5100.31 (04/2023) as downloaded, not from memory, and the honest result is
that three of the five values this tool compares are not items on the form at
all. The class or type designation, the alcohol content and the net contents
appear on the labels affixed to the application rather than in a numbered box;
net contents appears in item 15 only when it is blown, branded or embossed on
the container **and** does not appear on the labels. A Public COLA Registry
printout does carry class or type, and carries the code alongside the
description. Where a value is not on the document, this reports it as not found
and the agent supplies it, which is assumption A-17.
"""

from __future__ import annotations

import ctypes
import io
import logging
import re
import threading
from dataclasses import dataclass, field
from typing import Literal

import pypdfium2 as pdfium
import pypdfium2.raw as pdfium_raw

from app.config import settings
from app.ocr import OcrLine, UndecodableImageError, extract_text
from app.parse import parse_fields

# The values a COLA document can supply. Four of them are compared against the
# label (FR-2); the beverage type is carried for the interface, which asks for
# it, and is not compared, because no source states a rule that reads it.
APPLICATION_FIELDS = (
    "brand_name",
    "class_type",
    "alcohol_content",
    "net_contents",
    "beverage_type",
)

ExtractionPath = Literal["form_fields", "embedded_text", "ocr"]

# Where one value came from, inside the document (ADR 0010). Reported per value
# because a document can now answer from two different places at once, and a
# reading taken off a picture is a different kind of evidence from a reading
# taken out of a text layer: the first went through OCR and can be misread, the
# second cannot.
ValueSource = Literal["form_fields", "embedded_text", "embedded_artwork"]

# The four values the embedded artwork can supply. The beverage type is not one
# of them: item 5 is three check boxes, a label does not print "distilled
# spirits" as a form answer, and inferring one from the artwork would be exactly
# the guess FR-1 forbids (ADR 0008).
ARTWORK_FIELDS = ("brand_name", "class_type", "alcohol_content", "net_contents")

PDF_MAGIC = b"%PDF"

logger = logging.getLogger(__name__)

# **PDFium is not thread-safe, and the batch path reads documents in a pool.**
#
# PDFium keeps process-global state and its API has to be serialized by the
# caller; pypdfium2 wraps it and inherits that. Reading two documents at once
# segfaults the process, which on the batch path takes the stream and every
# completed result with it: exactly the whole-batch failure NFR-2 forbids, and
# not something a per-row error can catch, because the process is gone.
#
# So every call into PDFium is made under this lock. What is deliberately left
# outside it is the OCR fallback: pages are rendered to bytes under the lock and
# read by Tesseract after it is released, so a batch of scanned documents still
# spends its expensive step in parallel. Text-layer and form-field reading, the
# ordinary case, are milliseconds and serialize harmlessly.
#
# This is the same shape of problem as the OpenMP one in app.ocr, found the same
# way: a library that is fine on the single-label path and not fine in a worker
# pool.
_PDFIUM_LOCK = threading.Lock()


class UnreadableDocumentError(Exception):
    """The bytes submitted could not be read as a COLA document (FR-9)."""


@dataclass(frozen=True)
class EmbeddedArtwork:
    """One raster image lifted whole out of an application document (ADR 0010).

    ``content`` is PNG bytes of the embedded image at its own resolution, not a
    render of the page it sits on. That distinction is the decision: a page
    rasterized at a fixed DPI throws away resolution the embedded picture
    already has, and hands the OCR engine the form's own printed captions mixed
    in with the label text. Lifting the image out gives the pipeline the flat
    artwork on its own, which is the input it handles well.
    """

    page: int
    width: int
    height: int
    content: bytes

    @property
    def pixels(self) -> int:
        return self.width * self.height


@dataclass(frozen=True)
class ParsedApplication:
    """What an uploaded COLA document said, and how it was read.

    ``values`` carries every key in ``APPLICATION_FIELDS``; ``None`` means the
    document did not state it, explicitly, in the same sense FR-1 gives "not
    found" on a label. ``notes`` says why in the cases where the reason is a
    property of the form rather than of this document.
    """

    values: dict[str, str | None]
    fanciful_name: str | None = None
    class_type_code: str | None = None
    path: ExtractionPath = "embedded_text"
    pages_read: int = 0
    notes: list[str] = field(default_factory=list)
    # Where each value came from, for the values that were found (ADR 0010). A
    # field the document did not carry has no entry.
    value_sources: dict[str, ValueSource] = field(default_factory=dict)
    # How many embedded raster images cleared the size floor, and how many of
    # those produced readable text. Both are reported so that "the artwork
    # supplied nothing" and "there was no artwork" are distinguishable, which is
    # the difference between a scan worth retaking and a document that simply
    # files its labels separately.
    artwork_images_found: int = 0
    artwork_images_read: int = 0
    # The embedded image the label side can be taken from when the agent
    # supplied no photograph of their own (ADR 0010, FR-1).
    label_artwork: EmbeddedArtwork | None = None

    @property
    def found_any(self) -> bool:
        """Whether this reading produced anything at all.

        The fanciful name counts. It is not compared against the label, but a
        document that gave it up is a document that was read, and falling back
        to OCR after reading one successfully would pay for a second reading of
        a file that has already answered.
        """
        return self.fanciful_name is not None or any(
            value is not None for value in self.values.values()
        )


def parse_application_document(content: bytes, content_type: str | None) -> ParsedApplication:
    """Read one uploaded COLA document. Never reaches the network (NFR-3)."""
    if not content:
        raise UnreadableDocumentError(
            "The uploaded application document is empty. Send the file again, or "
            "type the application values instead."
        )
    if _is_pdf(content, content_type):
        return _parse_pdf(content)
    return _parse_image(content)


def _is_pdf(content: bytes, content_type: str | None) -> bool:
    """Decide by the bytes, and by the declared type only as a fallback.

    A browser labels an uploaded file from its extension, which an agent can
    rename. The header is what the file is.
    """
    return content.startswith(PDF_MAGIC) or content_type == "application/pdf"


@dataclass(frozen=True)
class _PdfContents:
    """What one pass over a PDF produced, with every PDFium call already done.

    Everything expensive is deliberately left for the caller to do once the lock
    is released: the rendered pages and the embedded artwork come back as bytes,
    and Tesseract reads them outside the critical section.
    """

    text_side: ParsedApplication | None
    rendered_pages: list[bytes]
    artwork: list[EmbeddedArtwork]
    artwork_found: int
    pages: int


def _parse_pdf(content: bytes) -> ParsedApplication:
    """Read one PDF. Every PDFium call is made under ``_PDFIUM_LOCK``."""
    with _PDFIUM_LOCK:
        contents = _read_pdf_with_pdfium(content)

    # The artwork read happens here, outside the lock, for the reason the page
    # OCR below does: Tesseract is the expensive part and there is no reason for
    # one document's reading to block another's.
    artwork = _read_artwork(contents.artwork)

    if contents.text_side is not None:
        return _with_notes(
            _merge_artwork(contents.text_side, artwork),
            path=contents.text_side.path,
            pages_read=contents.pages,
        )

    # Nothing in the file itself, so it is a scan: read the pages rendered
    # above.
    # Orientation correction is off because a page rendered from a PDF is
    # already the right way up, and the OSD pass costs about as much again as
    # the read it precedes (see app.ocr).
    ocr_lines: list[OcrLine] = []
    for rendered in contents.rendered_pages:
        ocr_lines.extend(extract_text(rendered, correct_orientation=False).lines)
    if not ocr_lines and not artwork.values:
        raise UnreadableDocumentError(
            "No text could be read from the uploaded PDF, either from the file "
            "itself, or by reading its pages as images, or from any picture "
            "embedded in it. Nothing was taken from it. Type the application "
            "values instead."
        )
    from_pages = (
        _from_lines(ocr_lines)
        if ocr_lines
        else ParsedApplication(values=dict.fromkeys(APPLICATION_FIELDS))
    )
    return _with_notes(
        _merge_artwork(_sourced(from_pages, "embedded_text"), artwork),
        path="ocr",
        pages_read=contents.pages,
    )


def _read_pdf_with_pdfium(content: bytes) -> _PdfContents:
    """Everything that touches PDFium, in one place, for one document.

    Returns the reading taken from the file itself, when it carried values, plus
    the pages rendered to PNG bytes for the OCR fallback and every embedded
    raster image that cleared the size floor. The document is closed here rather
    than left to the garbage collector, because a collection running on another
    thread would call into PDFium outside the lock.
    """
    try:
        document = pdfium.PdfDocument(io.BytesIO(content))
        page_count = len(document)
    except Exception as exc:  # pypdfium2 raises its own error types
        raise UnreadableDocumentError(
            "The uploaded file could not be opened as a PDF. It may be damaged, "
            "or password protected. Send it again, or type the application "
            "values instead."
        ) from exc

    try:
        if not page_count:
            raise UnreadableDocumentError(
                "The uploaded PDF has no pages in it. Send the file again, or type "
                "the application values instead."
            )

        pages = min(page_count, settings.max_document_pages)

        # Every page is searched for artwork, not only the pages read for text.
        # The author's own document states its brand name on page 1 and carries
        # the label artwork on page 3, and a page limit chosen to bound how much
        # text is read has nothing to say about where the pictures are. The cost
        # is bounded by the count of images actually read rather than by the
        # page count (ADR 0010).
        artwork, artwork_found = _embedded_images(document, page_count)

        from_fields = _from_form_fields(document, pages)
        lines = _pdf_text_lines(document, pages)
        from_text = _from_lines(lines)

        merged = _combine(from_fields, from_text)
        if merged.found_any:
            path: ExtractionPath = "form_fields" if from_fields.found_any else "embedded_text"
            return _PdfContents(
                text_side=ParsedApplication(
                    values=merged.values,
                    fanciful_name=merged.fanciful_name,
                    class_type_code=merged.class_type_code,
                    path=path,
                    value_sources=merged.value_sources,
                ),
                rendered_pages=[],
                artwork=artwork,
                artwork_found=artwork_found,
                pages=pages,
            )

        rendered_pages: list[bytes] = []
        for index in range(pages):
            try:
                rendered_pages.append(_render_page(document, index))
            except Exception as exc:
                # One page that will not render is not the document failing. The
                # class name and the page number go to the log and nothing else:
                # NFR-6 forbids anything about the content reaching it.
                logger.warning(
                    "application document page could not be rendered",
                    extra={"page": index + 1, "cause": type(exc).__name__},
                )
        return _PdfContents(
            text_side=None,
            rendered_pages=rendered_pages,
            artwork=artwork,
            artwork_found=artwork_found,
            pages=pages,
        )
    finally:
        document.close()


def _parse_image(content: bytes) -> ParsedApplication:
    """A photograph or scan of the form, submitted as an image.

    No embedded artwork here, by construction: an image has no objects inside
    it to lift out. What the pixels show is what was read, and the whole picture
    is already going through the label pipeline.
    """
    try:
        result = extract_text(content)
    except UndecodableImageError as exc:
        raise UnreadableDocumentError(
            "The uploaded application document could not be decoded as an image "
            "or a PDF. Send it again, or type the application values instead."
        ) from exc
    if not result.has_text:
        raise UnreadableDocumentError(
            "The uploaded application document was read but no text could be "
            "extracted from it. Nothing was taken from it. Type the application "
            "values instead."
        )
    return _with_notes(
        _sourced(_from_lines(result.lines), "embedded_text"), path="ocr", pages_read=1
    )


# --------------------------------------------------------------------------
# The embedded label artwork (ADR 0010).
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class _ArtworkReading:
    """What every embedded picture in one document was read to say."""

    values: dict[str, str]
    images_found: int
    images_read: int
    label_artwork: EmbeddedArtwork | None


def _embedded_images(
    document: pdfium.PdfDocument, page_count: int
) -> tuple[list[EmbeddedArtwork], int]:
    """Lift every embedded raster image out of the document, largest first.

    **Extracted rather than rendered, and the difference is the decision.**
    ``_render_page`` rasterizes a whole page at a chosen scale, which is right
    for reading a scanned form and wrong for reading the artwork on it: the
    render is capped at ``ocr_long_edge_px`` across the whole page, so a picture
    occupying a third of it comes out at a third of that, well below the
    resolution the file already holds. It also hands Tesseract the form's own
    printed captions mixed in with the label text. Lifting the image object out
    gives the pipeline the artwork at its native size and nothing else.

    Only images clearing both halves of the size floor survive; see
    ``Settings.min_artwork_edge_px``. They are returned largest first, and no
    more than ``max_artwork_images`` of them, because each one costs a full OCR
    read. The count returned alongside is how many cleared the floor, which is
    not the same as how many were read.

    Called under ``_PDFIUM_LOCK``. Every failure here is one image skipped, not
    a document failing: a PDF can carry an image in a colour space or a filter
    PDFium will not hand back, and the rest of the file is still readable.
    """
    candidates: list[EmbeddedArtwork] = []
    for index in range(page_count):
        page = document[index]
        for obj in page.get_objects():
            if not isinstance(obj, pdfium.PdfImage):
                continue
            try:
                width, height = obj.get_px_size()
            except Exception as exc:
                logger.warning(
                    "embedded image size could not be read",
                    extra={"page": index + 1, "cause": type(exc).__name__},
                )
                continue
            if not _clears_floor(width, height):
                continue
            content = _artwork_png(obj, index)
            if content is None:
                continue
            candidates.append(
                EmbeddedArtwork(page=index + 1, width=width, height=height, content=content)
            )

    candidates.sort(key=lambda art: (-art.pixels, art.page))
    return candidates[: settings.max_artwork_images], len(candidates)


def _clears_floor(width: int, height: int) -> bool:
    """Whether one embedded image is big enough to be label artwork.

    Both halves have to be met. The edge floor rejects a long thin barcode or
    signature strip whatever its area; the area floor rejects a small square
    seal or logo. Agency seals, barcodes and signature blocks are small; label
    artwork is not.
    """
    return (
        min(width, height) >= settings.min_artwork_edge_px
        and width * height >= settings.min_artwork_pixels
    )


def _artwork_png(image: pdfium.PdfImage, page_index: int) -> bytes | None:
    """One embedded image as PNG bytes at its own resolution, or None.

    ``render=False`` asks PDFium for the image's own bitmap rather than for a
    rendering of it as placed on the page, which is what keeps the resolution.
    """
    try:
        pil = image.get_bitmap(render=False).to_pil()
        buffer = io.BytesIO()
        pil.convert("RGB").save(buffer, format="PNG")
        return buffer.getvalue()
    except Exception as exc:
        # NFR-6: the class name and the page number, nothing the picture showed.
        logger.warning(
            "embedded image could not be extracted",
            extra={"page": page_index + 1, "cause": type(exc).__name__},
        )
        return None


def _read_artwork(images: list[EmbeddedArtwork]) -> _ArtworkReading:
    """Read every surviving embedded picture through the label OCR pipeline.

    **The pipeline is the one label artwork goes through, unchanged.**
    ``extract_text`` is called with its defaults, so the v1.0.1 orientation
    decision and the preprocessed-against-plain best-of both apply exactly as
    they do to a photograph. The artwork is flat, which is the input that
    pipeline handles well; that is the whole reason this is worth doing.

    Values are taken from the images in size order, so the largest picture that
    states a field wins and a smaller one fills what the larger one did not
    show, which is the front-and-back case. ``label_artwork`` is the image the
    label side can be taken from: the largest one that both read and yielded a
    label value, falling back to the largest one that read at all. Preferring
    the one that yielded values keeps a large scan of a signature page from
    being offered as the label when a smaller picture of the label was there.

    A picture that will not decode is skipped rather than fatal. It is a picture
    inside a document, and the document may have answered already.
    """
    values: dict[str, str] = {}
    read_count = 0
    with_values: EmbeddedArtwork | None = None
    any_read: EmbeddedArtwork | None = None

    for image in images:
        try:
            result = extract_text(image.content)
        except UndecodableImageError as exc:
            logger.warning(
                "embedded image could not be decoded",
                extra={"page": image.page, "cause": type(exc).__name__},
            )
            continue
        if not result.has_text:
            continue
        read_count += 1
        any_read = any_read or image

        parsed = parse_fields(result.lines)
        found = {
            name: value for name in ARTWORK_FIELDS if (value := getattr(parsed, name)) is not None
        }
        if found:
            with_values = with_values or image
        for name, value in found.items():
            values.setdefault(name, value)

    return _ArtworkReading(
        values=values,
        images_found=len(images),
        images_read=read_count,
        label_artwork=with_values or any_read,
    )


def _merge_artwork(text_side: ParsedApplication, artwork: _ArtworkReading) -> ParsedApplication:
    """Fill what the text layer left empty from the artwork, never the reverse.

    This is the precedence rule, and it is the whole of it on the document side:
    a value the file itself states wins over a value recognized out of a
    picture, because the first is read and the second is guessed at by an OCR
    engine. A typed value beats both, and that decision is made one layer up in
    ``app.verify.resolve_application``.
    """
    values = dict(text_side.values)
    sources = dict(text_side.value_sources)
    for name, value in artwork.values.items():
        if values.get(name) is None:
            values[name] = value
            sources[name] = "embedded_artwork"
    return ParsedApplication(
        values=values,
        fanciful_name=text_side.fanciful_name,
        class_type_code=text_side.class_type_code,
        path=text_side.path,
        value_sources=sources,
        artwork_images_found=artwork.images_found,
        artwork_images_read=artwork.images_read,
        label_artwork=artwork.label_artwork,
    )


def _sourced(parsed: ParsedApplication, source: ValueSource) -> ParsedApplication:
    """Attribute every value a reading found to one source."""
    return ParsedApplication(
        values=parsed.values,
        fanciful_name=parsed.fanciful_name,
        class_type_code=parsed.class_type_code,
        path=parsed.path,
        value_sources={name: source for name, value in parsed.values.items() if value is not None},
    )


def _render_page(document: pdfium.PdfDocument, index: int) -> bytes:
    """Rasterize one page to PNG bytes, with any filled form fields drawn.

    ``init_forms`` is what puts an unflattened form's values into the pixels.
    Without it a scanned-looking render of a filled form shows the blank
    template, and the OCR fallback would find captions and no answers.
    """
    document.init_forms()
    page = document[index]
    scale = max(1.0, settings.ocr_long_edge_px / max(page.get_width(), page.get_height()))
    bitmap = page.render(scale=scale)
    buffer = io.BytesIO()
    bitmap.to_pil().save(buffer, format="PNG")
    return buffer.getvalue()


def _pdf_text_lines(document: pdfium.PdfDocument, pages: int) -> list[OcrLine]:
    """The text layer, as the same line records the label parser works on.

    Height is zero on every line, exactly as ``app.parse.lines_from_text`` does
    it: a PDF text layer carries no type size this reader needs, and every rule
    here is about which caption a line starts with rather than how big it is.
    """
    lines: list[OcrLine] = []
    position = 0
    for index in range(pages):
        try:
            text = document[index].get_textpage().get_text_bounded()
        except Exception as exc:
            # As above: the page is skipped, and the log records the class name
            # and the page number rather than anything the page said (NFR-6).
            logger.warning(
                "application document page carried no readable text layer",
                extra={"page": index + 1, "cause": type(exc).__name__},
            )
            continue
        for raw_line in text.splitlines():
            stripped = raw_line.strip()
            if stripped:
                lines.append(OcrLine(text=stripped, confidence=0.0, height=0.0, top=position))
                position += 1
    return lines


# --------------------------------------------------------------------------
# The item map, transcribed from TTB F 5100.31 (04/2023).
# --------------------------------------------------------------------------
#
# The AcroForm field names are the ones the downloaded form actually carries.
# They are matched loosely, on the item number and the caption words, because a
# form saved through a different editor can rewrite the exact string while
# keeping the caption.
_FIELD_NAME_PATTERNS = {
    "brand_name": re.compile(r"\bbrand\s*name\b", re.IGNORECASE),
    "fanciful_name": re.compile(r"\bfanciful\s*name\b", re.IGNORECASE),
}

# Item 5, TYPE OF PRODUCT, is one radio group named "Check Box22" whose three
# widgets export Wine, Spirits and Malt. The names are TTB's; the words on the
# right are the ones this application uses everywhere else.
_PRODUCT_TYPE_FIELD = re.compile(r"check\s*box\s*22|type\s*of\s*product", re.IGNORECASE)
_PRODUCT_TYPE_EXPORTS = {
    "wine": "wine",
    "spirits": "distilled spirits",
    "distilledspirits": "distilled spirits",
    "malt": "malt beverage",
    "maltbeverages": "malt beverage",
}

# Captions this reader takes a value from. Anchored at the start of a line,
# after an optional item number, so that "(e.g., net contents)" inside item 15's
# own caption is not read as a net contents statement.
_VALUE_CAPTIONS: dict[str, re.Pattern[str]] = {
    "brand_name": re.compile(r"^\s*(?:item\s+)?(?:6\s*[.)]\s*)?brand\s+name\b", re.IGNORECASE),
    "fanciful_name": re.compile(
        r"^\s*(?:item\s+)?(?:7\s*[.)]\s*)?fanciful\s+name\b", re.IGNORECASE
    ),
    # Not an item on the form. A Public COLA Registry printout carries it, and
    # captions it "Class/Type Description" alongside a separate
    # "Class/Type Code". The negative lookahead is what keeps the code line from
    # being read as the designation: without it the code line is matched first,
    # because it is printed first, and the description is never reached.
    "class_type": re.compile(
        r"^\s*class\s*(?:/|\s+or\s+|\s+)\s*type(?:\s+(?:designation|description))?\b"
        r"(?!\s*code\b)",
        re.IGNORECASE,
    ),
    "alcohol_content": re.compile(r"^\s*alcohol\s+content\b", re.IGNORECASE),
    "net_contents": re.compile(r"^\s*net\s+contents\b", re.IGNORECASE),
}

# Every caption on the application side of the form, plus the keys a registry
# printout prints. A value stops at the next one of these: it is what keeps
# "6. BRAND NAME (Required)" on a blank form from reading item 7's caption as
# the brand name.
_STOP_CAPTIONS = re.compile(
    r"""^\s*(?:
        (?:item\s+)?\d{1,2}[a-z]?\s*[.)]\s*\S       # any numbered item caption
      | part\s+i{1,3}\b
      | ttb\s+f\s*5100\.31
      | ttb\s+id\b
      | serial\s*\#
      | status\s*:
      | origin\s*:
      | vintage\s*:
      | approval\s+date\b
      | expiration\s+date\b
      | qualifications\b
      | brand\s+name\b
      | fanciful\s+name\b
      | class\s*(?:/|\s+or\s+|\s+)\s*type\b
      | alcohol\s+content\b
      | net\s+contents\b
      | a\.\s*certificate
      | domestic\b
      | imported\b
    )""",
    re.IGNORECASE | re.VERBOSE,
)

# A trailing instruction on a caption, for example "(Required)" or "(If any)".
#
# The brackets are matched loosely on purpose. Tesseract routinely reads an
# opening parenthesis as a brace or a bracket, and a closing one as a 1 or a
# pipe, and this pattern has to run over OCR output as well as over a text
# layer. What is not loosened is the word inside: a bracketed phrase that is not
# one of the form's three instructions is left alone, because it might be part
# of the value.
_CAPTION_QUALIFIER = re.compile(
    r"^\s*[(\[{]\s*(?:required|if\s+any|if\s+on\s+label)\s*[)\]}1|]?", re.IGNORECASE
)

# A caption word left over after the caption above has matched.
#
# **Why this exists.** A Public COLA Registry printout does not print
# "Class/Type:". It prints "Class/Type Description: Kentucky Straight Bourbon
# Whiskey", and the caption pattern that matched "Class/Type" left "Description:"
# at the front of the value, so the class or type was read as
# "Description: Kentucky Straight Bourbon Whiskey" and compared against the
# label as that. The residue is stripped here rather than by lengthening every
# caption pattern, because the same three words attach to more than one caption
# and no value is one of them on its own.
#
# Anchored, and applied only to what is left after a caption has matched, so a
# value that merely contains one of these words keeps it.
_RESIDUAL_CAPTION_WORDS = re.compile(
    r"^[\s:.\-–]*(?:description|designation|code)\b", re.IGNORECASE
)

# "Class/Type Code: 141", which a registry printout prints beside the
# description. Read separately so the code is still recorded where a printout
# splits it from the designation rather than writing "141 - BOURBON WHISKY" on
# one line.
_CLASS_TYPE_CODE_CAPTION = re.compile(
    r"^\s*class\s*(?:/|\s+or\s+|\s+)\s*type\s+code\b", re.IGNORECASE
)

# The code itself, taken from the head of that caption's value.
_LEADING_CODE = re.compile(r"^(\d{1,4})\b")

# The three product types item 5 offers, in the words this application uses.
_PRODUCT_TYPE_WORDS = {
    "wine": re.compile(r"\bwines?\b", re.IGNORECASE),
    "distilled spirits": re.compile(r"\bdistilled\s+spirits\b", re.IGNORECASE),
    "malt beverage": re.compile(r"\bmalt\s+beverages?\b", re.IGNORECASE),
}

# A class or type printed as "141 - BOURBON WHISKY", which is how a registry
# printout carries the code alongside the description. The character class
# carries an en dash alongside the hyphen because a document may be typeset with
# one; this is parsing input, not prose.
_CODED_CLASS_TYPE = re.compile(r"^\s*(\d{1,4})\s*[-–:]\s*(.+)$")

# How many lines below a caption a value may be. Two, because item 8's caption
# runs to three lines on the real form and a value that far below a one-line
# caption is more likely to be the next block than this one's answer.
_VALUE_LOOKAHEAD = 2


def _from_form_fields(document: pdfium.PdfDocument, pages: int) -> ParsedApplication:
    """Read AcroForm field values, which is where a filled-in form keeps them."""
    values: dict[str, str | None] = dict.fromkeys(APPLICATION_FIELDS)
    fanciful: str | None = None

    if document.get_formtype() == pdfium_raw.FORMTYPE_NONE:
        return ParsedApplication(values=values)
    document.init_forms()
    formenv = document.formenv
    if formenv is None:
        return ParsedApplication(values=values)

    for index in range(pages):
        page = document[index]
        for annotation in _widgets(page):
            name = _widget_text(pdfium_raw.FPDFAnnot_GetFormFieldName, formenv, annotation)
            value = _widget_text(pdfium_raw.FPDFAnnot_GetFormFieldValue, formenv, annotation)
            if _PRODUCT_TYPE_FIELD.search(name) and pdfium_raw.FPDFAnnot_IsChecked(
                formenv, annotation
            ):
                export = _widget_text(
                    pdfium_raw.FPDFAnnot_GetFormFieldExportValue, formenv, annotation
                )
                values["beverage_type"] = values["beverage_type"] or _product_type(export)
            if not value:
                continue
            if _FIELD_NAME_PATTERNS["brand_name"].search(name):
                values["brand_name"] = values["brand_name"] or value
            elif _FIELD_NAME_PATTERNS["fanciful_name"].search(name):
                fanciful = fanciful or value
            pdfium_raw.FPDFPage_CloseAnnot(annotation)

    return ParsedApplication(values=values, fanciful_name=fanciful, path="form_fields")


def _widgets(page):
    """Every widget annotation on one page, opened for reading."""
    for index in range(pdfium_raw.FPDFPage_GetAnnotCount(page)):
        annotation = pdfium_raw.FPDFPage_GetAnnot(page, index)
        if pdfium_raw.FPDFAnnot_GetSubtype(annotation) == pdfium_raw.FPDF_ANNOT_WIDGET:
            yield annotation
        else:
            pdfium_raw.FPDFPage_CloseAnnot(annotation)


def _widget_text(getter, formenv, annotation) -> str:
    """Call one of PDFium's UTF-16 string getters and return a Python string.

    PDFium's convention is to report the buffer size first and fill it on a
    second call, and it reports it in bytes including the terminator while
    taking a buffer of unsigned shorts. Both halves are handled here so that no
    caller has to know it.
    """
    size = getter(formenv, annotation, None, 0)
    if size <= 0:
        return ""
    buffer = (ctypes.c_ushort * size)()
    getter(formenv, annotation, buffer, size * 2)
    return bytes(buffer).decode("utf-16-le", "ignore").rstrip("\x00").strip()


def _product_type(export: str) -> str | None:
    """Map item 5's export value onto the words this application uses."""
    return _PRODUCT_TYPE_EXPORTS.get(re.sub(r"[^a-z]", "", export.lower()))


def _from_lines(lines: list[OcrLine]) -> ParsedApplication:
    """Read captions and their values out of a document's text."""
    texts = [line.text for line in lines]
    values: dict[str, str | None] = dict.fromkeys(APPLICATION_FIELDS)
    fanciful: str | None = None
    code: str | None = None

    for name, caption in _VALUE_CAPTIONS.items():
        found = _value_for(texts, caption)
        if found is None:
            continue
        if name == "fanciful_name":
            fanciful = found
        elif name == "class_type":
            coded = _CODED_CLASS_TYPE.match(found)
            if coded:
                code, found = coded.group(1), coded.group(2).strip()
            values[name] = found
        else:
            values[name] = found

    if code is None:
        code = _class_type_code(texts)

    values["beverage_type"] = _sole_product_type(texts)
    return ParsedApplication(values=values, fanciful_name=fanciful, class_type_code=code)


def _class_type_code(texts: list[str]) -> str | None:
    """The code from a "Class/Type Code" caption, where the document splits it out."""
    captioned = _value_for(texts, _CLASS_TYPE_CODE_CAPTION)
    if not captioned:
        return None
    digits = _LEADING_CODE.match(captioned)
    return digits.group(1) if digits else None


def _value_for(texts: list[str], caption: re.Pattern[str]) -> str | None:
    """The value printed against one caption, on its line or just below it.

    Two shapes, because the two documents differ. A registry printout puts the
    key and the value on one line separated by a colon; the form puts the
    caption in a box and the value under it. Anything that is itself a caption
    ends the value, so a blank box reads as not found rather than as whatever
    was printed next.
    """
    for index, text in enumerate(texts):
        match = caption.match(text)
        if not match:
            continue
        remainder = _strip_qualifier(text[match.end() :])
        if remainder:
            return remainder
        collected: list[str] = []
        for offset in range(1, _VALUE_LOOKAHEAD + 1):
            if index + offset >= len(texts):
                break
            candidate = texts[index + offset].strip()
            if not candidate or _STOP_CAPTIONS.match(candidate):
                break
            collected.append(candidate)
        # The residue is stripped here too, for the document that wraps a
        # caption onto two lines and prints "Description: ..." on the second.
        joined = _strip_residual_caption(" ".join(collected).strip()).lstrip(" :-–\t").strip()
        return joined or None
    return None


def _strip_qualifier(text: str) -> str:
    """Drop a caption's own instruction, its residual words, and the separator."""
    text = _CAPTION_QUALIFIER.sub("", text)
    text = _strip_residual_caption(text)
    return text.lstrip(" :-–\t").strip()


def _strip_residual_caption(text: str) -> str:
    """Remove caption words the matched pattern left behind.

    Repeated rather than applied once, because a caption can carry more than one
    of them ("Class/Type Designation Description"). Each pass shortens the
    string, so this terminates.
    """
    while True:
        shortened = _RESIDUAL_CAPTION_WORDS.sub("", text, count=1)
        if shortened == text:
            return text
        text = shortened


def _sole_product_type(texts: list[str]) -> str | None:
    """Item 5, when the document names exactly one of the three types.

    **A ticked box cannot be read from text.** Item 5 is three checkboxes, and a
    document's text layer prints the caption of an unticked box exactly as it
    prints the caption of a ticked one, so a form that names all three has said
    nothing about which was chosen. Where a document names one and only one, it
    is stating a product type rather than offering a choice, and that is taken.
    Anything else is not found, and the agent supplies it. Reading an "X" beside
    one of three boxes out of a scan is the kind of guess FR-1 forbids.
    """
    blob = "\n".join(texts)
    present = [name for name, pattern in _PRODUCT_TYPE_WORDS.items() if pattern.search(blob)]
    return present[0] if len(present) == 1 else None


def _combine(preferred: ParsedApplication, fallback: ParsedApplication) -> ParsedApplication:
    """Take each value from the form fields, falling back to the text layer.

    The source of each value is recorded as it is chosen rather than inferred
    afterwards, because the two sides can carry the same value and a reader
    comparing them after the fact cannot tell which one it came from.
    """
    values: dict[str, str | None] = {}
    sources: dict[str, ValueSource] = {}
    for name in APPLICATION_FIELDS:
        from_fields = preferred.values.get(name)
        from_text = fallback.values.get(name)
        values[name] = from_fields or from_text
        if from_fields:
            sources[name] = "form_fields"
        elif from_text:
            sources[name] = "embedded_text"
    return ParsedApplication(
        values=values,
        fanciful_name=preferred.fanciful_name or fallback.fanciful_name,
        class_type_code=preferred.class_type_code or fallback.class_type_code,
        value_sources=sources,
    )


# What to say about a value the document did not carry, where the reason is a
# property of the form rather than of this particular document. Written out
# because "not found" alone invites an agent to go looking for a box that is not
# there (A-17).
_ABSENCE_NOTES = {
    "class_type": (
        "The class or type designation is not an item on TTB F 5100.31 "
        "(04/2023). It appears on the labels affixed to the application, and on "
        "a Public COLA Registry printout. Enter it yourself."
    ),
    "alcohol_content": (
        "The alcohol content is not an item on TTB F 5100.31 (04/2023). It "
        "appears on the labels affixed to the application, and on a Public COLA "
        "Registry printout. Enter it yourself."
    ),
    "net_contents": (
        "The net contents is an item on TTB F 5100.31 (04/2023) only when it is "
        "blown, branded or embossed on the container and does not appear on the "
        "labels (item 15). Otherwise it is on the labels themselves, and on a "
        "Public COLA Registry printout. Enter it yourself."
    ),
    "beverage_type": (
        "The type of product is item 5 on TTB F 5100.31 (04/2023), three "
        "checkboxes. A ticked box cannot be read from a document's text, and "
        "this document did not name one type on its own. Choose it yourself."
    ),
}


# What is said, once, whenever a value or a label side came out of the pictures
# inside the application rather than out of a photograph the agent took
# (ADR 0010). It is a limitation, written down where the reading is reported,
# rather than a caveat left to a document nobody has open.
SELF_CONSISTENCY_NOTE = (
    "Some of this was read from the label artwork inside the application "
    "document. Checking that artwork against the application it came from is a "
    "self-consistency check: it shows that the artwork on file carries the "
    "mandatory elements and agrees with the typed form data. It is not an "
    "independent check of the bottle. Verifying the physical bottle against the "
    "filing still needs a photograph of that bottle."
)


def _with_notes(parsed: ParsedApplication, *, path: ExtractionPath, pages_read: int):
    """Attach the honest explanation for each value the document did not carry.

    A value the embedded artwork supplied gets no absence note, because it is no
    longer absent. What it gets instead is the self-consistency note, once, for
    the whole reading.
    """
    notes = [
        _ABSENCE_NOTES[name]
        for name in APPLICATION_FIELDS
        if parsed.values.get(name) is None and name in _ABSENCE_NOTES
    ]
    from_artwork = "embedded_artwork" in parsed.value_sources.values()
    if from_artwork or parsed.label_artwork is not None:
        notes.append(SELF_CONSISTENCY_NOTE)
    return ParsedApplication(
        values=parsed.values,
        fanciful_name=parsed.fanciful_name,
        class_type_code=parsed.class_type_code,
        path=path,
        pages_read=pages_read,
        notes=notes,
        value_sources=parsed.value_sources,
        artwork_images_found=parsed.artwork_images_found,
        artwork_images_read=parsed.artwork_images_read,
        label_artwork=parsed.label_artwork,
    )
