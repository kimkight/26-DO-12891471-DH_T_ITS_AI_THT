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
