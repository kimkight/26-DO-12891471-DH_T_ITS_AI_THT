"""Unit tests for normalization, scoring, and the three outcomes.

Covers docs/07_TEST_STRATEGY.md section 1 rows "Text normalization", "Outcome
classification" and "Numeric parsing", and UAT rows 2, 7, 8, 18, 19, 20, 21 and
22 from section 6. Requirements: FR-3, FR-4, FR-7, A-4, A-12, A-13.
"""

import pytest

from app.compare import (
    Outcome,
    classify,
    compare_abv,
    compare_net_contents,
    compare_text,
    normalize_text,
    parse_abv,
    parse_net_contents,
)
from app.config import settings


class TestNormalization:
    def test_casefolds_and_strips_surrounding_whitespace(self):
        assert normalize_text("  STONE'S THROW  ") == normalize_text("Stone's Throw")

    def test_typographic_apostrophe_folds_onto_the_straight_one(self):
        assert normalize_text("Stone’s Throw") == normalize_text("Stone's Throw")

    def test_punctuation_is_dropped_rather_than_scored(self):
        assert normalize_text("Alc./Vol.") == normalize_text("Alc Vol")

    def test_normalization_does_not_merge_different_names(self):
        assert normalize_text("Stone's Throw") != normalize_text("Stormy Ridge")


class TestOutcomeClassification:
    """Boundary values are the point, not the middle of the band (FR-3)."""

    def test_score_at_the_match_threshold_is_a_match(self):
        assert classify(settings.match_threshold) is Outcome.MATCH

    def test_score_just_below_the_match_threshold_needs_review(self):
        assert classify(settings.match_threshold - 0.1) is Outcome.NEEDS_REVIEW

    def test_score_at_the_review_threshold_needs_review(self):
        assert classify(settings.review_threshold) is Outcome.NEEDS_REVIEW

    def test_score_just_below_the_review_threshold_is_a_mismatch(self):
        assert classify(settings.review_threshold - 0.1) is Outcome.MISMATCH


class TestBrandName:
    def test_stones_throw_never_reports_a_mismatch(self):
        """UAT row 2. A hard mismatch here is a failure of the test (FR-4)."""
        result = compare_text("STONE'S THROW", "Stone's Throw")
        assert result.outcome is not Outcome.MISMATCH
        assert result.outcome is Outcome.MATCH

    def test_typographic_apostrophe_matches_the_straight_one(self):
        result = compare_text("STONE’S THROW", "Stone's Throw")
        assert result.outcome is Outcome.MATCH

    def test_two_different_brand_names_still_mismatch(self):
        result = compare_text("Stone's Throw", "Copper Kettle")
        assert result.outcome is Outcome.MISMATCH

    def test_a_missing_application_value_is_not_compared_not_a_mismatch(self):
        """FR-2: not compared is distinguished from mismatch."""
        result = compare_text("Stone's Throw", "")
        assert result.outcome is Outcome.NOT_COMPARED

    def test_a_field_not_found_on_the_label_never_reports_a_match(self):
        result = compare_text(None, "Stone's Throw")
        assert result.outcome is Outcome.MISMATCH
        assert "not found" in result.reason


class TestAlcoholContentParsing:
    @pytest.mark.parametrize(
        ("value", "percent", "proof"),
        [
            ("45% Alc./Vol. (90 Proof)", 45.0, 90.0),
            ("45%", 45.0, None),
            ("45", 45.0, None),
            ("45.0%", 45.0, None),
            ("ABV 12.5 percent", 12.5, None),
            ("40% alc. by vol.", 40.0, None),
            ("38% ALC/VOL", 38.0, None),
            ("43% ALC./VOL. [86 PROOF]", 43.0, 86.0),
            ("47% ALC./VOL.- (94 PROOF)", 47.0, 94.0),
            ("ALC.12% BY VOL", 12.0, None),
            ("46.3% ALC/VOL (92.6 PROOF)", 46.3, 92.6),
        ],
    )
    def test_reads_the_percentage_and_any_proof(self, value, percent, proof):
        reading = parse_abv(value)
        assert reading.percent == percent
        assert reading.proof == proof

    @pytest.mark.parametrize(
        "value",
        [
            pytest.param("46.3% ALC/VOL (92-6 PROOF)", id="point_read_as_a_dash"),
            pytest.param("46.3% ALC/VOL (92\u00b06 PROOF)", id="point_read_as_a_degree_sign"),
            pytest.param("46.3% ALC/VOL (92\u00b76 PROOF)", id="point_read_as_a_middle_dot"),
            pytest.param("46.3% ALC/VOL (92,6 PROOF)", id="point_read_as_a_comma"),
        ],
    )
    def test_a_decimal_point_misread_inside_the_proof_figure_is_repaired(self, value):
        """Measured on a real filing, 2026-09-06 (docs/09_DEPLOYMENT.md section 9).

        A proof printed to one decimal place came back with its point read as
        a dash by one segmentation mode and a degree sign by another. The proof
        pattern then read the last digit as the whole proof, and a label that
        agrees with itself was reported as contradicting itself under A-12.
        """
        reading = parse_abv(value)
        assert (reading.percent, reading.proof) == (46.3, 92.6)

    def test_the_repair_does_not_touch_a_range_of_percentages(self):
        reading = parse_abv("12-14% alc/vol")
        assert reading.is_range
        assert (reading.range_low, reading.range_high) == (12.0, 14.0)

    def test_the_repair_needs_exactly_one_digit_after_the_separator(self):
        """A dash between two whole numbers before PROOF is left as it was."""
        assert parse_abv("80-90 PROOF").proof == 90.0

    def test_a_range_is_recognized_as_a_range(self):
        reading = parse_abv("12 to 14% alc/vol")
        assert reading.is_range
        assert (reading.range_low, reading.range_high) == (12.0, 14.0)


class TestAlcoholContentComparison:
    def test_sample_label_value_against_a_bare_application_number(self):
        """UAT rows 7 and 20: 45% Alc./Vol. (90 Proof) against 45 is a match."""
        result = compare_abv("45% Alc./Vol. (90 Proof)", "45")
        assert result.outcome is Outcome.MATCH
        assert "90 proof" in result.reason.lower()

    def test_forty_five_matches_forty_five_point_zero(self):
        """UAT row 18."""
        assert compare_abv("45", "45.0%").outcome is Outcome.MATCH

    def test_forty_five_mismatches_forty_five_point_one(self):
        """UAT row 19. A match or a review outcome is a failure of this test."""
        result = compare_abv("45", "45.1")
        assert result.outcome is Outcome.MISMATCH
        assert "45" in result.reason
        assert "45.1" in result.reason
        assert "0.1" in result.reason

    def test_a_repaired_proof_that_is_twice_the_abv_matches(self):
        """The same label, read with its decimal point damaged, still agrees."""
        comparison = compare_abv("46.3% ALC/VOL (92-6 PROOF)", "46.3")
        assert comparison.outcome is Outcome.MATCH
        assert "92.6 proof is twice" in comparison.reason

    def test_a_proof_that_really_is_a_whole_number_is_still_cross_checked(self):
        """The repair changes a misread, not the rule: 46.3 and 92 still disagree."""
        comparison = compare_abv("46.3% ALC/VOL (92 PROOF)", "46.3")
        assert comparison.outcome is Outcome.NEEDS_REVIEW
        assert "contradicts itself" in comparison.reason

    def test_proof_that_is_not_twice_the_abv_needs_review(self):
        """UAT row 21: 92 proof against 45 percent is an internal inconsistency."""
        result = compare_abv("45% Alc./Vol. (92 Proof)", "45")
        assert result.outcome is Outcome.NEEDS_REVIEW
        assert "92" in result.reason
        assert "90" in result.reason

    def test_a_label_range_against_a_single_application_value_needs_review(self):
        result = compare_abv("12 to 14% alc/vol", "13")
        assert result.outcome is Outcome.NEEDS_REVIEW
        assert "27 CFR 4.36" in result.reason

    def test_an_unparseable_value_needs_review_and_says_it_fell_back(self):
        """FR-7 fallback, routed to review by A-12."""
        result = compare_abv("forty five percent", "45")
        assert result.outcome is Outcome.NEEDS_REVIEW
        assert "text comparison" in result.reason

    def test_zero_tolerance_is_the_default(self):
        assert settings.abv_tolerance == 0.0


class TestNetContents:
    @pytest.mark.parametrize(
        ("value", "quantity", "unit"),
        [
            ("750 mL", 750.0, "mL"),
            ("750ml", 750.0, "mL"),
            ("750 milliliters", 750.0, "mL"),
            ("1 L", 1.0, "L"),
            ("25.4 fl oz", 25.4, "fl oz"),
            ("25.4 fl. oz.", 25.4, "fl oz"),
            # The six shapes measured on nine registry labels, 2026-09-06, as
            # generic forms; see tests/test_parse.py for the shapes by name.
            ("500ml e", 500.0, "mL"),
            ("CONT.700ML.e", 700.0, "mL"),
            ("700 ML. - L AB1234C", 700.0, "mL"),
            ("1L", 1.0, "L"),
            ("1 PINT", 1.0, "pint"),
            ("1 PT.", 1.0, "pint"),
            ("1 QUART", 1.0, "quart"),
            ("1 GALLON", 1.0, "gallon"),
            ("12 OZ", 12.0, "fl oz"),
            ("50 CL", 50.0, "cL"),
            ("44% ALC/VOL 700 ML", 700.0, "mL"),
        ],
    )
    def test_reads_the_quantity_and_folds_the_unit_spelling(self, value, quantity, unit):
        reading = parse_net_contents(value)
        assert (reading.value, reading.unit) == (quantity, unit)

    def test_one_pint_matches_one_pt(self):
        assert compare_net_contents("1 PINT", "1 pt").outcome is Outcome.MATCH

    def test_a_pint_against_fluid_ounces_needs_review_and_is_not_converted(self):
        """A-13: 16 fl oz is one pint, and the tool does not say so."""
        comparison = compare_net_contents("1 PINT", "16 fl oz")
        assert comparison.outcome is Outcome.NEEDS_REVIEW
        assert "No conversion" in comparison.reason

    def test_twelve_ounces_matches_twelve_fluid_ounces(self):
        assert compare_net_contents("12 OZ", "12 fl. oz.").outcome is Outcome.MATCH

    def test_750_ml_matches_750ml(self):
        """UAT row 8."""
        assert compare_net_contents("750 mL", "750ml").outcome is Outcome.MATCH

    def test_different_units_need_review_and_are_not_converted(self):
        """UAT row 22. No conversion is performed and no match is reported."""
        result = compare_net_contents("750 mL", "25.4 fl oz")
        assert result.outcome is Outcome.NEEDS_REVIEW
        assert "no conversion" in result.reason.lower()

    def test_same_unit_different_quantity_is_a_mismatch(self):
        assert compare_net_contents("750 mL", "700 mL").outcome is Outcome.MISMATCH

    def test_a_missing_unit_needs_review_rather_than_assuming_one(self):
        result = compare_net_contents("750 mL", "750")
        assert result.outcome is Outcome.NEEDS_REVIEW

    def test_an_unparseable_value_falls_back_to_text_comparison_and_says_so(self):
        """FR-7. A-13 states no rule for this case, so FR-7's general one applies."""
        result = compare_net_contents("seven hundred fifty", "seven hundred fifty")
        assert result.outcome is Outcome.MATCH
        assert "as text" in result.reason
