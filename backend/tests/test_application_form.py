"""Reading the application values off an uploaded COLA document.

Requirements: FR-11 (the label application is accepted as an alternative to
typing the same values), FR-2 (those values are what the label is compared
against), FR-9 (an empty or unreadable document returns a clear message and no
field reports a match), OOS-1 (this is document parsing, not COLA system
integration: nothing here opens a socket).

Every fixture is generated at test time by samples/formmaker.py. No real
applicant's form and no real permit number is committed, which is the test data
policy in docs/07_TEST_STRATEGY.md section 8. The item map the parser uses is
transcribed from TTB F 5100.31 (04/2023); see
docs/adr/0008-cola-form-as-application-input.md.
"""

from __future__ import annotations

import pytest
from samples.formmaker import (
    ApplicationSpec,
    as_fillable_pdf_bytes,
    as_pdf_bytes,
    as_png_bytes,
    paper_form_lines,
    registry_printout_lines,
)

from app.application_form import UnreadableDocumentError, parse_application_document

from .conftest import requires_fonts, requires_tesseract

REGISTRY_SPEC = ApplicationSpec(
    brand_name="STONE'S THROW",
    fanciful_name="Small Batch Reserve",
    beverage_type="distilled spirits",
    class_type="BOURBON WHISKY",
    class_type_code="141",
    alcohol_content="45% ALC/VOL",
    net_contents="750 ML",
)


class TestThePaperFormsTextLayer:
    """TTB F 5100.31 as a digitally generated PDF: read the file, not the pixels."""

    @pytest.fixture
    def parsed(self):
        pdf = as_pdf_bytes(paper_form_lines(ApplicationSpec()))
        return parse_application_document(pdf, "application/pdf")

    def test_the_extraction_path_is_the_text_layer(self, parsed):
        assert parsed.path == "embedded_text"
        assert parsed.pages_read == 1

    def test_item_6_gives_the_brand_name(self, parsed):
        assert parsed.values["brand_name"] == "STONE'S THROW"

    def test_item_7_gives_the_fanciful_name(self, parsed):
        assert parsed.fanciful_name == "Small Batch Reserve"

    def test_the_three_values_the_form_has_no_item_for_are_not_found(self, parsed):
        """The honest result of reading the real form (A-17).

        The class or type designation, the alcohol content and the net contents
        are not numbered items on the 04/2023 edition. They are on the labels
        affixed to the application.
        """
        assert parsed.values["class_type"] is None
        assert parsed.values["alcohol_content"] is None
        assert parsed.values["net_contents"] is None

    def test_each_absent_value_is_explained_rather_than_left_blank(self, parsed):
        joined = " ".join(parsed.notes)
        assert "class or type designation is not an item" in joined
        assert "alcohol content is not an item" in joined
        assert "net contents is an item" in joined

    def test_a_ticked_box_cannot_be_read_from_text_so_the_type_is_not_found(self, parsed):
        """Item 5 prints all three options whichever one was ticked."""
        assert parsed.values["beverage_type"] is None
        assert any("ticked box cannot be read" in note for note in parsed.notes)

    def test_item_15_is_not_read_as_a_net_contents_statement(self):
        """Item 15 is free text, and reading it as a net contents is a guess.

        It carries whatever is blown, branded or embossed on the container and
        is not on the labels. Net contents is only its example. Taking the box's
        contents as a net contents statement would report a guess as a reading,
        which is what FR-1 forbids.
        """
        spec = ApplicationSpec(net_contents="750 ML EMBOSSED ON THE PUNT")
        parsed = parse_application_document(as_pdf_bytes(paper_form_lines(spec)), "application/pdf")
        assert parsed.values["net_contents"] is None


class TestARegistryPrintout:
    """The Public COLA Registry detail page carries what the form does not."""

    @pytest.fixture
    def parsed(self):
        pdf = as_pdf_bytes(registry_printout_lines(REGISTRY_SPEC))
        return parse_application_document(pdf, "application/pdf")

    def test_every_compared_value_is_read(self, parsed):
        assert parsed.values["brand_name"] == "STONE'S THROW"
        assert parsed.values["class_type"] == "BOURBON WHISKY"
        assert parsed.values["alcohol_content"] == "45% ALC/VOL"
        assert parsed.values["net_contents"] == "750 ML"

    def test_the_class_type_code_is_recorded_and_the_description_compared(self, parsed):
        assert parsed.class_type_code == "141"
        assert parsed.values["class_type"] == "BOURBON WHISKY"

    def test_a_printout_naming_one_product_type_gives_the_beverage_type(self):
        wine = ApplicationSpec(
            beverage_type="wine",
            class_type="TABLE WINE",
            class_type_code="80",
            alcohol_content="12.5% ALC/VOL",
            net_contents="750 ML",
        )
        parsed = parse_application_document(
            as_pdf_bytes(registry_printout_lines(wine)), "application/pdf"
        )
        assert parsed.values["beverage_type"] == "wine"

    def test_nothing_is_explained_away_that_was_actually_found(self, parsed):
        assert not [note for note in parsed.notes if "class or type" in note]

    def test_a_blank_key_does_not_borrow_the_next_keys_value(self):
        blank = ApplicationSpec(
            brand_name="",
            class_type="BOURBON WHISKY",
            alcohol_content="45% ALC/VOL",
            net_contents="750 ML",
        )
        parsed = parse_application_document(
            as_pdf_bytes(registry_printout_lines(blank)), "application/pdf"
        )
        assert parsed.values["brand_name"] is None
        assert parsed.fanciful_name == "Small Batch Reserve"


class TestARegistryPrintoutWithDescriptiveCaptions:
    """The caption shape the author read off a deployed-target printout.

    Deployed-target evidence, 2026-08-28: a printout carrying the line
    "Class/Type Description: Kentucky Straight Bourbon Whiskey" was parsed as
    "Description: Kentucky Straight Bourbon Whiskey". The caption pattern matched
    "Class/Type" and left the rest of the caption at the front of the value, so
    the class or type compared against the label was the caption word plus the
    designation. This is a defect against FR-11 and A-17.
    """

    BOURBON = ApplicationSpec(
        brand_name="STONE'S THROW",
        fanciful_name="Small Batch Reserve",
        beverage_type="distilled spirits",
        class_type="Kentucky Straight Bourbon Whiskey",
        class_type_code="141",
        alcohol_content="45% ALC/VOL",
        net_contents="750 ML",
    )

    @pytest.fixture
    def parsed(self):
        pdf = as_pdf_bytes(registry_printout_lines(self.BOURBON, captions="descriptive"))
        return parse_application_document(pdf, "application/pdf")

    def test_the_caption_word_is_not_left_in_the_class_or_type(self, parsed):
        assert parsed.values["class_type"] == "Kentucky Straight Bourbon Whiskey"

    def test_the_code_is_still_captured_separately(self, parsed):
        """Split across its own caption here, rather than joined by a dash."""
        assert parsed.class_type_code == "141"

    def test_the_brand_name_is_unaffected(self, parsed):
        """A caption with no residual word keeps reading exactly as it did."""
        assert parsed.values["brand_name"] == "STONE'S THROW"

    def test_the_other_captions_still_read(self, parsed):
        assert parsed.values["alcohol_content"] == "45% ALC/VOL"
        assert parsed.values["net_contents"] == "750 ML"
        assert parsed.fanciful_name == "Small Batch Reserve"

    def test_nothing_is_explained_away_that_was_found(self, parsed):
        assert not [note for note in parsed.notes if "class or type" in note]


class TestCaptionResidueInGeneral:
    """The rule, exercised without going through a PDF.

    ``_from_lines`` is the seam every one of the three ways in converges on, so
    a line-level test states the rule once rather than three times.
    """

    @staticmethod
    def _read(lines: list[str]):
        from app.application_form import _from_lines
        from app.ocr import OcrLine

        return _from_lines(
            [
                OcrLine(text=text, confidence=0.0, height=0.0, top=position)
                for position, text in enumerate(lines)
            ]
        )

    @pytest.mark.parametrize(
        "line",
        [
            "Class/Type Description: Kentucky Straight Bourbon Whiskey",
            "CLASS/TYPE DESIGNATION: Kentucky Straight Bourbon Whiskey",
            "Class or Type Description - Kentucky Straight Bourbon Whiskey",
        ],
    )
    def test_each_caption_shape_yields_the_designation_alone(self, line):
        assert self._read([line]).values["class_type"] == "Kentucky Straight Bourbon Whiskey"

    def test_a_brand_name_is_not_touched(self):
        assert self._read(["Brand Name: STONE'S THROW"]).values["brand_name"] == "STONE'S THROW"

    def test_a_value_that_merely_contains_a_caption_word_keeps_it(self):
        """Anchored, so only a leading residue is removed."""
        parsed = self._read(["Class/Type Description: Whisky Specialty, Code Named"])
        assert parsed.values["class_type"] == "Whisky Specialty, Code Named"

    def test_the_code_line_is_not_read_as_the_designation(self):
        """It is printed first, so without the rule it would win the caption."""
        parsed = self._read(
            [
                "Class/Type Code: 141",
                "Class/Type Description: Kentucky Straight Bourbon Whiskey",
            ]
        )
        assert parsed.values["class_type"] == "Kentucky Straight Bourbon Whiskey"
        assert parsed.class_type_code == "141"

    def test_the_joined_form_still_splits_the_code_from_the_description(self):
        parsed = self._read(["CLASS/TYPE: 141 - BOURBON WHISKY"])
        assert parsed.class_type_code == "141"
        assert parsed.values["class_type"] == "BOURBON WHISKY"

    def test_a_caption_wrapped_onto_a_second_line_is_read_the_same_way(self):
        parsed = self._read(["CLASS/TYPE", "Description: Kentucky Straight Bourbon Whiskey"])
        assert parsed.values["class_type"] == "Kentucky Straight Bourbon Whiskey"

    def test_a_caption_carrying_only_residue_reports_not_found(self):
        """An empty box is not found, not the caption word (FR-1)."""
        assert self._read(["Class/Type Description:"]).values["class_type"] is None


class TestAFilledInFillableForm:
    """An applicant's filled copy keeps its values in AcroForm fields."""

    @pytest.fixture
    def parsed(self):
        pdf = as_fillable_pdf_bytes(ApplicationSpec())
        return parse_application_document(pdf, "application/pdf")

    def test_the_extraction_path_is_the_form_fields(self, parsed):
        assert parsed.path == "form_fields"

    def test_the_field_values_are_read_even_though_the_text_layer_is_blank(self, parsed):
        assert parsed.values["brand_name"] == "STONE'S THROW"
        assert parsed.fanciful_name == "Small Batch Reserve"

    def test_item_5s_ticked_box_gives_the_beverage_type(self, parsed):
        """The one place a checkbox can actually be read."""
        assert parsed.values["beverage_type"] == "distilled spirits"

    def test_each_of_the_three_product_types_maps_to_this_applications_words(self):
        for chosen, expected in (
            ("wine", "wine"),
            ("distilled spirits", "distilled spirits"),
            ("malt beverage", "malt beverage"),
        ):
            pdf = as_fillable_pdf_bytes(ApplicationSpec(beverage_type=chosen))
            parsed = parse_application_document(pdf, "application/pdf")
            assert parsed.values["beverage_type"] == expected, chosen


@requires_tesseract
@requires_fonts
class TestARasterisedCopy:
    """A scan or photograph of the same document, with no text layer at all."""

    def test_a_png_of_the_registry_printout_reads_the_same_values(self):
        png = as_png_bytes(registry_printout_lines(REGISTRY_SPEC))
        parsed = parse_application_document(png, "image/png")
        assert parsed.path == "ocr"
        assert parsed.values["brand_name"] == "STONE'S THROW"
        assert parsed.values["class_type"] == "BOURBON WHISKY"
        assert parsed.values["net_contents"] == "750 ML"

    def test_a_pdf_with_no_text_layer_falls_back_to_reading_its_pages(self):
        """The scanned-PDF case: pixels wrapped in a PDF container."""
        import io

        from PIL import Image

        png = as_png_bytes(registry_printout_lines(REGISTRY_SPEC))
        image = Image.open(io.BytesIO(png)).convert("RGB")
        buffer = io.BytesIO()
        image.save(buffer, format="PDF")
        parsed = parse_application_document(buffer.getvalue(), "application/pdf")
        assert parsed.path == "ocr"
        assert parsed.values["brand_name"] == "STONE'S THROW"

    def test_a_value_ocr_could_not_read_is_not_found_rather_than_guessed(self):
        """Not found is the required answer, not an approximation (FR-1)."""
        png = as_png_bytes(paper_form_lines(ApplicationSpec()))
        parsed = parse_application_document(png, "image/png")
        assert parsed.values["alcohol_content"] is None
        assert parsed.values["class_type"] is None


class TestUnreadableDocuments:
    """FR-9 applied to the second upload."""

    def test_an_empty_file_says_so_and_leaves_the_typed_path_open(self):
        with pytest.raises(UnreadableDocumentError) as caught:
            parse_application_document(b"", "application/pdf")
        assert "empty" in str(caught.value)
        assert "type the application values" in str(caught.value)

    def test_bytes_that_are_not_a_document_at_all_say_so(self):
        with pytest.raises(UnreadableDocumentError) as caught:
            parse_application_document(b"this is not a pdf", "application/pdf")
        assert "could not be" in str(caught.value)

    def test_a_truncated_pdf_says_so_rather_than_returning_nothing_found(self):
        pdf = as_pdf_bytes(registry_printout_lines(REGISTRY_SPEC))
        with pytest.raises(UnreadableDocumentError):
            parse_application_document(pdf[: len(pdf) // 3], "application/pdf")


class TestNoOutboundCall:
    """OOS-1 and NFR-3: reading the document is local, and provably so."""

    def test_parsing_a_document_opens_no_socket(self, monkeypatch):
        import socket

        def refuse(*args, **kwargs):
            raise AssertionError("the parser opened a socket")

        monkeypatch.setattr(socket.socket, "connect", refuse)
        monkeypatch.setattr(socket, "create_connection", refuse)
        parsed = parse_application_document(
            as_pdf_bytes(registry_printout_lines(REGISTRY_SPEC)), "application/pdf"
        )
        assert parsed.values["brand_name"] == "STONE'S THROW"
