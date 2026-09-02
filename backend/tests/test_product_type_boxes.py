"""Item 5's three check boxes, read off the rendered page (ADR 0016).

The author asked whether beverage type is a field on the application. **It is:
item 5 on TTB F 5100.31 (04/2023), "TYPE OF PRODUCT (Required)", three check
boxes.** The tool left it blank on every filing that was not an unflattened
AcroForm copy, because it read only the text layer, where all three captions
print and no tick can be seen.

The tick is in the pixels, and the tool already renders the pages. On the
author's own document, rendered at scale 2.0, the ticked box is plainly darker
than the two empty ones: 217.5 for DISTILLED SPIRITS against 239.9 for WINE and
241.8 for MALT BEVERAGE, a 22 point separation on deliberately loose
coordinates. The two boxes that are the same differ by 1.9.

**This module is that measurement, reproduced on fixtures drawn at test time.**
The tick grey is chosen to land where her filing landed rather than to pass:
the reader measures the ticked box at 212 against 233 and 235 on the text-layer
PDF, and 201 against 223 and 226 on a scan of the same page.

What is asserted:

* each of the three ticked in turn, on all three inputs a filing arrives as: a
  PDF with a text layer, a photograph or scan of the form, and a PDF that is
  nothing but a scan;
* a form with **none** ticked, and a form with **two** ticked, both reported as
  not determined, because on this evidence they are the same situation;
* the margin, from both sides, by varying how dark the tick is drawn;
* that the boxes are located from their own captions and not from any pixel
  coordinate, by reading the same page at two different scales;
* that an AcroForm radio group still wins, and that a ticked box outranks the
  weaker inference drawn from a page's text.

Requirements: FR-11, FR-1 (not found rather than a guess), NFR-1 (the cost, and
where it is not paid). Assumption A-17, amended. No real application data
appears anywhere here (docs/07_TEST_STRATEGY.md section 8).
"""

from __future__ import annotations

import io
import sys
from pathlib import Path

import pypdfium2 as pdfium
import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from samples.formmaker import (  # noqa: E402
    ApplicationSpec,
    as_fillable_pdf_bytes,
    as_pdf_with_product_type_boxes,
    as_png_with_product_type_boxes,
    as_scanned_pdf_bytes,
    paper_form_lines,
)

from app import timing  # noqa: E402
from app.application_form import (  # noqa: E402
    _item_five_page,
    _png_bytes,
    parse_application_document,
    read_item_five,
)
from app.product_type import (  # noqa: E402
    OPTIONS,
    PRODUCT_TYPE_MARGIN,
    caption_boxes_from_words,
    read_product_type,
    word_boxes_from_ocr,
)

from .conftest import requires_fonts, requires_tesseract  # noqa: E402

FORM_LINES = paper_form_lines(ApplicationSpec())

# The caption the form prints, against the words this application uses.
TICKED = {
    "WINE": "wine",
    "DISTILLED SPIRITS": "distilled spirits",
    "MALT BEVERAGES": "malt beverage",
}


def text_layer_pdf(ticked: str | None, **kwargs) -> bytes:
    return as_pdf_with_product_type_boxes(FORM_LINES, ticked=ticked, **kwargs)


def scan_png(ticked: str | None, **kwargs) -> bytes | None:
    return as_png_with_product_type_boxes(FORM_LINES, ticked=ticked, **kwargs)


def read_from_pdf(data: bytes):
    """The reading alone, without the rest of the document parse around it."""
    document = pdfium.PdfDocument(io.BytesIO(data))
    try:
        page = _item_five_page(document, len(document))
    finally:
        document.close()
    # The render leaves the lock as a picture and is encoded afterwards
    # (v1.3.0, finding 25), which is what `_parse_pdf` does for the real path.
    return read_item_five(None if page is None else (_png_bytes(page[0]), page[1]))


class TestATextLayerPdf:
    """The ordinary filing: a PDF whose text layer states the captions."""

    @pytest.mark.parametrize("caption", list(TICKED))
    def test_each_option_in_turn_is_read(self, caption):
        parsed = parse_application_document(text_layer_pdf(caption), "application/pdf")
        assert parsed.values["beverage_type"] == TICKED[caption]

    def test_the_value_is_marked_as_read_from_the_box_rather_than_from_text(self):
        """A tick went through a recognition step and a text layer does not."""
        parsed = parse_application_document(text_layer_pdf("WINE"), "application/pdf")
        assert parsed.value_sources["beverage_type"] == "product_type_box"

    def test_the_reading_says_what_it_measured(self):
        reading = read_from_pdf(text_layer_pdf("DISTILLED SPIRITS"))
        assert reading is not None
        assert set(reading.luminance) == set(OPTIONS)
        assert "luminance points darker" in reading.reason

    def test_the_captions_are_located_from_the_text_layer_at_no_ocr_cost(self):
        """A document that states its captions never pays for recognizing them."""
        with timing.recording() as recorded:
            parse_application_document(text_layer_pdf("WINE"), "application/pdf")
        assert recorded.get("item_five_ocr") == 0.0


class TestNoneTickedAndTwoTicked:
    """Both are not determined, because on this evidence they are the same."""

    def test_a_form_with_no_box_ticked_is_not_determined(self):
        parsed = parse_application_document(text_layer_pdf(None), "application/pdf")
        assert parsed.values["beverage_type"] is None

    def test_a_form_with_two_boxes_ticked_is_not_determined(self):
        data = text_layer_pdf("WINE", also_ticked="MALT BEVERAGES")
        parsed = parse_application_document(data, "application/pdf")
        assert parsed.values["beverage_type"] is None

    def test_the_note_says_the_boxes_were_sampled_and_did_not_settle_it(self):
        """Different from "this document did not name one type" (FR-1)."""
        reading = read_from_pdf(text_layer_pdf(None))
        assert reading is not None
        assert reading.value is None
        assert reading.sampled
        assert "inside the" in reading.reason

    def test_the_agent_is_still_told_to_choose_it(self):
        parsed = parse_application_document(text_layer_pdf(None), "application/pdf")
        assert any("Choose it yourself" in note for note in parsed.notes)


class TestTheMargin:
    """The number, from both sides, by varying how dark the tick is drawn.

    The reader wants ``PRODUCT_TYPE_MARGIN`` luminance points between the darkest
    box and the next. These two assert that a tick that clears it is read and a
    mark too faint to clear it is not, on the same page and the same geometry.
    """

    def test_a_tick_as_dark_as_the_author_measured_clears_the_margin(self):
        reading = read_from_pdf(text_layer_pdf("DISTILLED SPIRITS", grey=110))
        assert reading is not None
        assert reading.value == "distilled spirits"
        assert reading.separation is not None
        assert reading.separation >= PRODUCT_TYPE_MARGIN

    def test_a_mark_too_faint_to_clear_the_margin_is_not_read(self):
        reading = read_from_pdf(text_layer_pdf("DISTILLED SPIRITS", grey=235))
        assert reading is not None
        assert reading.value is None
        assert reading.separation is not None
        assert reading.separation < PRODUCT_TYPE_MARGIN

    def test_two_empty_boxes_are_within_a_few_points_of_each_other(self):
        """The noise floor. The author measured 1.9 points between hers."""
        reading = read_from_pdf(text_layer_pdf(None))
        assert reading is not None
        assert reading.separation is not None
        assert reading.separation < PRODUCT_TYPE_MARGIN / 2


class TestNoPixelCoordinateIsHardCoded:
    """The author's constraint: the form has editions and renders at scales."""

    @requires_tesseract
    @requires_fonts
    @pytest.mark.parametrize("font_size", [18, 30])
    def test_the_same_page_reads_the_same_at_two_type_sizes(self, font_size):
        """Everything is in caption text heights, so the size cancels out."""
        png = scan_png("MALT BEVERAGES", font_size=font_size)
        if png is None:
            pytest.skip("no TrueType font available")
        reading = read_product_type(png, caption_boxes_from_words(word_boxes_from_ocr(png)))
        assert reading.value == "malt beverage"

    def test_a_page_whose_captions_were_not_found_is_not_sampled(self):
        """A Registry printout is not this form and has no boxes to read."""
        reading = read_product_type(b"", [])
        assert reading.value is None
        assert not reading.sampled
        assert "not all found" in reading.reason


class TestAScanOfTheForm:
    """A photograph or scan: the captions have to be recognized first."""

    @requires_tesseract
    @requires_fonts
    @pytest.mark.parametrize("caption", list(TICKED))
    def test_each_option_in_turn_is_read_from_an_uploaded_image(self, caption):
        png = scan_png(caption)
        if png is None:
            pytest.skip("no TrueType font available")
        parsed = parse_application_document(png, "image/png")
        assert parsed.values["beverage_type"] == TICKED[caption]

    @requires_tesseract
    @requires_fonts
    @pytest.mark.parametrize("caption", list(TICKED))
    def test_each_option_in_turn_is_read_from_a_rasterised_pdf(self, caption):
        """A PDF that is nothing but a scan: no text layer anywhere in it."""
        png = scan_png(caption)
        if png is None:
            pytest.skip("no TrueType font available")
        parsed = parse_application_document(as_scanned_pdf_bytes(png), "application/pdf")
        assert parsed.values["beverage_type"] == TICKED[caption]

    @requires_tesseract
    @requires_fonts
    def test_a_scan_with_nothing_ticked_is_not_determined(self):
        """**The defect this supersedes.**

        A scan whose OCR lost two of the three captions used to read as whichever
        caption survived, through ``_sole_product_type``: the text named one type
        and not the other two, which is what a document *stating* one type looks
        like. Sampling the boxes establishes that the page offers three and shows
        no choice among them, and that supersedes the inference.
        """
        png = scan_png(None)
        if png is None:
            pytest.skip("no TrueType font available")
        parsed = parse_application_document(as_scanned_pdf_bytes(png), "application/pdf")
        assert parsed.values["beverage_type"] is None


class TestPrecedence:
    """What outranks what, and why (ADR 0010's rule, applied again)."""

    def test_an_acroform_radio_group_still_wins(self):
        """A widget's state is a statement the file makes; a tick is recognized."""
        parsed = parse_application_document(
            as_fillable_pdf_bytes(ApplicationSpec()), "application/pdf"
        )
        assert parsed.values["beverage_type"] == "distilled spirits"
        assert parsed.value_sources["beverage_type"] == "form_fields"

    @requires_tesseract
    @requires_fonts
    def test_a_ticked_box_outranks_the_inference_drawn_from_the_page_text(self):
        png = scan_png("MALT BEVERAGES")
        if png is None:
            pytest.skip("no TrueType font available")
        parsed = parse_application_document(as_scanned_pdf_bytes(png), "application/pdf")
        assert parsed.values["beverage_type"] == "malt beverage"
        assert parsed.value_sources["beverage_type"] == "product_type_box"


class TestBeverageTypeIsStillNeverComparedAgainstTheLabel:
    """Reading it changes what fills the field, and nothing else (A-17)."""

    def test_it_is_not_one_of_the_compared_fields(self):
        from app.verify import COMPARED_FIELDS

        assert "beverage_type" not in COMPARED_FIELDS

    def test_the_artwork_is_still_never_asked_for_it(self):
        """A label does not print a form answer, so the artwork cannot supply it."""
        from app.application_form import ARTWORK_FIELDS

        assert "beverage_type" not in ARTWORK_FIELDS
