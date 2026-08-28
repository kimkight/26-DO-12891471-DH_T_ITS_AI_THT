"""Unit tests for locating the five fields inside OCR text.

Requirements: FR-1 (a value or an explicit "not found" for each of the five
fields). The type-size heuristic for brand name and class or type is exercised
through synthetic line heights rather than through a real image, which keeps
this tier free of Tesseract as docs/07_TEST_STRATEGY.md section 1 requires.
"""

from app.ocr import OcrLine
from app.parse import lines_from_text, parse_fields
from app.warning import WARNING_STATEMENT

SAMPLE_LABEL_TEXT = f"""STONE'S THROW
Kentucky Straight Bourbon Whiskey
45% Alc./Vol. (90 Proof)
750 mL
{WARNING_STATEMENT}"""


def sized(*rows: tuple[str, float]) -> list[OcrLine]:
    """Build OCR lines with explicit type sizes, in reading order."""
    return [
        OcrLine(text=text, confidence=90.0, height=height, top=index * 100)
        for index, (text, height) in enumerate(rows)
    ]


class TestSampleLabel:
    def test_all_five_fields_are_located(self):
        parsed = parse_fields(lines_from_text(SAMPLE_LABEL_TEXT))
        assert parsed.brand_name == "STONE'S THROW"
        assert parsed.class_type == "Kentucky Straight Bourbon Whiskey"
        assert parsed.alcohol_content == "45% Alc./Vol. (90 Proof)"
        assert parsed.net_contents == "750 mL"
        assert parsed.warning.passes

    def test_the_warning_lines_are_not_offered_as_other_fields(self):
        parsed = parse_fields(lines_from_text(SAMPLE_LABEL_TEXT))
        assert "GOVERNMENT WARNING" not in (parsed.brand_name or "")
        assert "GOVERNMENT WARNING" not in (parsed.class_type or "")


class TestTypeSizeHeuristic:
    def test_the_largest_line_is_taken_as_the_brand_name(self):
        lines = sized(
            ("DISTILLED AND BOTTLED BY THE STONE'S THROW DISTILLING CO.", 12.0),
            ("STONE'S THROW", 80.0),
            ("Kentucky Straight Bourbon Whiskey", 30.0),
            ("45% Alc./Vol. (90 Proof)", 14.0),
            ("750 mL", 14.0),
        )
        parsed = parse_fields(lines)
        assert parsed.brand_name == "STONE'S THROW"
        assert parsed.class_type == "Kentucky Straight Bourbon Whiskey"

    def test_reading_order_breaks_a_tie_when_no_size_is_available(self):
        parsed = parse_fields(lines_from_text("STONE'S THROW\nKentucky Straight Bourbon"))
        assert parsed.brand_name == "STONE'S THROW"
        assert parsed.class_type == "Kentucky Straight Bourbon"


class TestNotFoundIsExplicit:
    def test_a_label_without_net_contents_reports_it_as_not_found(self):
        text = "STONE'S THROW\nKentucky Straight Bourbon Whiskey\n45% Alc./Vol. (90 Proof)"
        parsed = parse_fields(lines_from_text(text))
        assert parsed.net_contents is None
        assert parsed.alcohol_content == "45% Alc./Vol. (90 Proof)"

    def test_a_label_without_a_warning_reports_it_as_not_found(self):
        parsed = parse_fields(lines_from_text("STONE'S THROW\n750 mL"))
        assert parsed.warning.found is False
        assert parsed.warning_text is None

    def test_an_empty_label_reports_every_field_as_not_found(self):
        parsed = parse_fields([])
        assert parsed.brand_name is None
        assert parsed.class_type is None
        assert parsed.alcohol_content is None
        assert parsed.net_contents is None
        assert parsed.warning.found is False


class TestWarningBlockAssembly:
    def test_a_warning_split_across_many_lines_is_reassembled(self):
        wrapped = "\n".join(
            [
                "STONE'S THROW",
                "GOVERNMENT WARNING: (1) According to the Surgeon General, women",
                "should not drink alcoholic beverages during pregnancy because of",
                "the risk of birth defects. (2) Consumption of alcoholic beverages",
                "impairs your ability to drive a car or operate machinery, and may",
                "cause health problems.",
            ]
        )
        parsed = parse_fields(lines_from_text(wrapped))
        assert parsed.warning.passes

    def test_a_title_case_warning_is_still_located_so_it_can_be_reported(self):
        text = WARNING_STATEMENT.replace("GOVERNMENT WARNING:", "Government Warning:")
        parsed = parse_fields(lines_from_text(f"STONE'S THROW\n{text}"))
        assert parsed.warning.found is True
        assert parsed.warning.prefix_is_upper_case is False
        assert parsed.warning.body_matches is True


class TestAlcoholContentNeedsAnAlcoholMarker:
    """FR-1 and FR-7: a percent is only an ABV when its line says so.

    The defect this tier exists for was found on real artwork. In the author's
    three-photograph bottle test on 2026-08-27 the deployed prototype reported
    the alcohol content as `7%`, read from a line of marketing copy on the back
    label about reducing environmental impact, because the pattern accepted any
    percent token in reading order.
    """

    MARKETING_BACK_LABEL = "\n".join(
        [
            "STONE'S THROW",
            "Kentucky Straight Bourbon Whiskey",
            "Our lighter bottle and recycled carton reduce our environmental",
            "impact by 7% against the 2024 baseline.",
            "750 mL",
        ]
    )

    def test_a_percent_in_marketing_copy_is_not_read_as_alcohol_content(self):
        parsed = parse_fields(lines_from_text(self.MARKETING_BACK_LABEL))
        assert parsed.alcohol_content is None

    def test_the_rest_of_that_label_is_still_read(self):
        """Not found is one field, not a failed parse (FR-1)."""
        parsed = parse_fields(lines_from_text(self.MARKETING_BACK_LABEL))
        assert parsed.brand_name == "STONE'S THROW"
        assert parsed.net_contents == "750 mL"

    def test_the_sample_label_statement_still_extracts(self):
        parsed = parse_fields(lines_from_text(SAMPLE_LABEL_TEXT))
        assert parsed.alcohol_content == "45% Alc./Vol. (90 Proof)"

    def test_a_real_photograph_style_statement_still_extracts(self):
        text = "STONE'S THROW\n12.5% ALC. BY VOL.\n750 mL"
        parsed = parse_fields(lines_from_text(text))
        assert parsed.alcohol_content == "12.5% ALC. BY VOL."

    def test_ocr_noise_around_an_intact_marker_does_not_lose_the_line(self):
        """The marker has to survive OCR, the words around it do not."""
        text = "STONE'S THROW\n12.5% AlC. 8Y VOL.\n750 mL"
        parsed = parse_fields(lines_from_text(text))
        assert parsed.alcohol_content == "12.5% AlC. 8Y VOL."

    def test_each_marker_in_the_fr_7_set_is_accepted(self):
        for statement in (
            "45% ALC/VOL",
            "45% ALC. BY VOL.",
            "ALCOHOL 45% BY VOLUME",
            "ABV 45%",
            "90 PROOF",
        ):
            parsed = parse_fields(lines_from_text(f"STONE'S THROW\n{statement}\n750 mL"))
            assert parsed.alcohol_content == statement, statement

    def test_a_marker_with_no_number_is_not_reported_as_a_reading(self):
        """OCR splitting the statement gives not found, not `ALC./VOL.`."""
        parsed = parse_fields(lines_from_text("STONE'S THROW\nALC./VOL.\n750 mL"))
        assert parsed.alcohol_content is None
