"""Unit tests for locating the five fields inside OCR text.

Requirements: FR-1 (a value or an explicit "not found" for each of the five
fields). The type-size heuristic for brand name and class or type is exercised
through synthetic line heights rather than through a real image, which keeps
this tier free of Tesseract as docs/07_TEST_STRATEGY.md section 1 requires.
"""

import pytest

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


def located(statement: str, field: str) -> str | None:
    """One statement on a label of its own, through the parser."""
    parsed = parse_fields(lines_from_text(f"STONE'S THROW\n{statement}\nSmall batch"))
    return getattr(parsed, field)


class TestTheAlcoholStatementShapesFiledLabelsPrint:
    """FR-7, against 27 CFR 5.65(b)(2) to (b)(4), 7.65(b)(4) and (b)(5), 4.36(b).

    **Measured, not assumed.** On 2026-09-06 the author transcribed the alcohol
    statement from the label artwork of nine approved applications in TTB's
    Public COLA Registry, across six beverage classes. Five of the nine print
    the slash form, which is the regulation's own first example; exactly one
    prints ``ALC BY VOL``, and it is the filing this matcher was first
    calibrated to. The strings here are generic forms in the same shapes, not
    the transcriptions (docs/07_TEST_STRATEGY.md section 8).

    Each case is the shape it is named for. The rule that accepts them is the
    one Session 8 set and this does not widen: a number and an alcohol marker on
    one line. What the cases add is the proof that the shapes labels actually
    use are inside that rule, so a change to it that dropped one is caught.
    """

    @pytest.mark.parametrize(
        "statement",
        [
            pytest.param("44% ALC BY VOL", id="alc_by_vol_the_form_the_matcher_was_calibrated_to"),
            pytest.param("38% ALC/VOL", id="slash_5_65_b_4_i"),
            pytest.param("5.2% ALC/VOL", id="slash_with_a_decimal_figure_7_65_b_5_i"),
            pytest.param("43% ALC./VOL. [86 PROOF]", id="slash_with_periods_and_bracketed_proof"),
            pytest.param("46% ALC./VOL. - (92 PROOF)", id="slash_dash_parenthesised_proof"),
            pytest.param("47% ALC./VOL.- (94 PROOF)", id="slash_dash_fused_parenthesised_proof"),
            pytest.param("46.3% ALC/VOL (92.6 PROOF)", id="decimal_figure_and_decimal_proof"),
            pytest.param("ALC.12% BY VOL", id="alc_period_fused_to_the_figure_4_36_b_1"),
            pytest.param("ALC. 12% BY VOL", id="alc_period_then_the_figure"),
            pytest.param("46.3 % ALC / VOL", id="spaces_around_the_slash_and_the_percent"),
            pytest.param("46.3%ALC/VOL", id="no_space_between_the_figure_and_the_marker"),
            pytest.param("12% ALCOHOL BY VOLUME", id="spelled_out_figure_first_5_65_b_4_iv"),
            pytest.param("ALCOHOL BY VOLUME 12%", id="spelled_out_figure_last_5_65_b_2_i_C"),
            pytest.param("ALCOHOL 12 PERCENT BY VOLUME", id="spelled_out_percent_5_65_b_2_i_A"),
            pytest.param("ABV 40%", id="abv_before_the_figure"),
            pytest.param("40% ABV", id="abv_after_the_figure"),
            pytest.param("40% alc/vol", id="lower_case"),
        ],
    )
    def test_each_shape_is_located_as_the_alcohol_content(self, statement):
        assert located(statement, "alcohol_content") == statement

    @pytest.mark.parametrize(
        "statement",
        [
            pytest.param("46.3% ALCIVOL", id="slash_read_as_a_capital_i"),
            pytest.param("46.3% ALClVOL", id="slash_read_as_a_lower_l"),
            pytest.param("46.3% ALC1VOL", id="slash_read_as_a_one"),
            pytest.param("46.3% ALC|VOL", id="slash_read_as_a_bar"),
            pytest.param("46.3% ALC.IVOL.", id="slash_read_as_a_letter_with_the_periods"),
        ],
    )
    def test_the_slash_survives_being_read_as_a_letter(self, statement):
        """OCR turns a slash between two capitals into I, l, 1 or a bar.

        Neither half of ``ALCIVOL`` is then a word of its own, so the marker
        rule admits ALC and VOL joined by up to three such characters. It is
        untested against a real read, which is said rather than implied: the
        slash survived on every whole-panel read the author measured on
        2026-09-06, and this is headroom for the read where it does not.
        """
        assert located(statement, "alcohol_content") == statement

    @pytest.mark.parametrize(
        "statement",
        [
            pytest.param("ALCOHOL 11% TO 14% BY VOLUME", id="range_4_36_b_2"),
            pytest.param("11-14% ALC/VOL", id="range_with_a_dash"),
        ],
    )
    def test_the_wine_range_form_is_located(self, statement):
        """Decided either way, as asked: a range is located, and then routed.

        27 CFR 4.36(b)(2) permits "Alcohol __ % to __ % by volume" on wine.
        It is an alcohol statement, so it is found as one; what happens next
        is A-12's rule, unchanged, that a range against a single declared value
        is a person's call (``compare_abv``). Not locating it would report a
        compliant wine label as carrying no alcohol content at all.
        """
        assert located(statement, "alcohol_content") == statement

    @pytest.mark.parametrize(
        "statement",
        [
            pytest.param("Aged 12 years, 45% of the barrels", id="a_percent_with_no_marker"),
            pytest.param("ALC/VOL", id="a_marker_with_no_figure"),
            pytest.param("Reduced by 7% since 2024", id="marketing_copy"),
        ],
    )
    def test_nothing_here_admits_a_bare_percentage(self, statement):
        """The rule is still a marker beside a number, and only that."""
        assert located(statement, "alcohol_content") is None


class TestTheNetContentsShapesFiledLabelsPrint:
    """FR-7 and A-13, against 27 CFR 5.70(a), 7.70(a) and 4.37.

    The same nine registry labels print net contents in six shapes, and a
    pattern that assumed a number followed by ML read about half of them. This
    is the alcohol content defect above found before it cost anything: a
    presence check calibrated to one document, which prints 750 ML. The
    strings are generic forms in the measured shapes.
    """

    @pytest.mark.parametrize(
        "statement",
        [
            pytest.param("375 ML", id="metric_with_a_space"),
            pytest.param("200ml", id="metric_fused_lower_case"),
            pytest.param("500ml e", id="metric_with_the_estimated_quantity_sign"),
            pytest.param("CONT.700ML.e", id="cont_prefix_fused_with_the_sign"),
            pytest.param("700 ML. - L AB1234C", id="metric_fused_to_a_lot_code"),
            pytest.param("1 PINT", id="us_customary_pint_7_70_a_2"),
            pytest.param("1 PT.", id="pint_abbreviated"),
            pytest.param("1 QUART", id="quart"),
            pytest.param("1 GALLON", id="gallon"),
            pytest.param("12 FL OZ", id="fluid_ounces_7_70_a_1"),
            pytest.param("12 OZ", id="ounces_without_fl"),
            pytest.param("1L", id="litre_fused_5_70_a"),
            pytest.param("1.75 LITRE", id="litre_spelled_the_other_way_5_70_a"),
            pytest.param("50 CL", id="centilitres_5_70_a"),
        ],
    )
    def test_each_shape_is_located_as_the_net_contents(self, statement):
        assert located(statement, "net_contents") == statement

    def test_a_value_on_the_alcohol_line_is_found_by_both_rules(self):
        """Two of the nine labels print both statements on one line."""
        parsed = parse_fields(lines_from_text("STONE'S THROW\n44% ALC/VOL 700 ML\nSmall batch"))
        assert parsed.alcohol_content == "44% ALC/VOL 700 ML"
        assert parsed.net_contents == "44% ALC/VOL 700 ML"

    @pytest.mark.parametrize(
        "statement",
        [
            pytest.param("750", id="a_bare_number"),
            pytest.param("EST. 2016", id="a_year"),
            pytest.param("BATCH 142", id="a_batch_number"),
            pytest.param("ML", id="a_unit_with_no_figure"),
        ],
    )
    def test_a_number_that_is_not_against_a_unit_is_not_a_net_contents(self, statement):
        assert located(statement, "net_contents") is None
