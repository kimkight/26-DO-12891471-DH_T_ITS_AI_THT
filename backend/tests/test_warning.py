"""Unit tests for the government warning checks.

Covers docs/07_TEST_STRATEGY.md section 1 rows "Government warning body" and
"Warning capitalization", and UAT rows 3, 4, 5 and 15 from section 6.
Requirements: FR-5, FR-6, OOS-4.
"""

import re
from pathlib import Path

from app.warning import (
    WARNING_BODY,
    WARNING_PREFIX,
    WARNING_STATEMENT,
    check_warning,
    normalize_whitespace,
)

TITLE_CASE = f"Government Warning: {WARNING_BODY}"
ALTERED_WORD = WARNING_STATEMENT.replace("should not drink", "should avoid")


class TestTheConstantMatchesTheRegulation:
    def test_the_statement_is_the_text_quoted_in_the_requirements(self):
        """The constant is copied from docs/03_REQUIREMENTS.md section 1.

        The requirements document quotes 27 CFR 16.21 verbatim from eCFR, so
        this test fails if either the constant or the quotation drifts.
        """
        doc = (Path(__file__).resolve().parents[2] / "docs" / "03_REQUIREMENTS.md").read_text(
            encoding="utf-8"
        )
        quoted = re.search(r"> (GOVERNMENT WARNING:.*?health problems\.)", doc, re.S)
        assert quoted is not None
        assert normalize_whitespace(quoted.group(1).replace("\n>", " ")) == WARNING_STATEMENT


class TestWarningBody:
    def test_exact_text_matches(self):
        result = check_warning(WARNING_STATEMENT)
        assert result.body_matches
        assert result.passes

    def test_line_breaks_and_runs_of_spaces_do_not_break_the_match(self):
        """FR-5: whitespace is presentational; everything else is substantive."""
        broken = WARNING_STATEMENT.replace(". (2)", ".\n\n   (2)").replace(": (1)", ":\n(1)")
        result = check_warning(broken)
        assert result.body_matches
        assert result.passes

    def test_one_altered_word_is_a_mismatch(self):
        """UAT row 4: mismatch, not needs human review."""
        result = check_warning(ALTERED_WORD)
        assert not result.body_matches
        assert not result.passes

    def test_an_added_word_is_a_mismatch(self):
        result = check_warning(WARNING_STATEMENT.replace("birth defects", "serious birth defects"))
        assert not result.body_matches

    def test_an_omitted_word_is_a_mismatch(self):
        result = check_warning(WARNING_STATEMENT.replace("or operate machinery, ", ""))
        assert not result.body_matches

    def test_no_warning_at_all_reports_not_found(self):
        """UAT row 5."""
        result = check_warning("STONE'S THROW\nKentucky Straight Bourbon Whiskey\n750 mL")
        assert not result.found
        assert not result.passes
        assert "not found" in result.reason


class TestWarningCapitalization:
    def test_capital_prefix_passes(self):
        assert check_warning(WARNING_STATEMENT).prefix_is_upper_case is True

    def test_title_case_prefix_fails_and_names_capitalization(self):
        """UAT row 3: the capitalization check fails and the reason says so."""
        result = check_warning(TITLE_CASE)
        assert result.prefix_is_upper_case is False
        assert not result.passes
        assert "Capitalization" in result.reason

    def test_title_case_prefix_leaves_the_body_result_intact(self):
        """FR-6: the two results are reported separately, so one failure reads clearly."""
        result = check_warning(TITLE_CASE)
        assert result.body_matches is True

    def test_lower_case_prefix_fails(self):
        result = check_warning(f"government warning: {WARNING_BODY}")
        assert result.prefix_is_upper_case is False


class TestBoldTypeIsNeverClaimed:
    """UAT row 15: overstating what was checked is the harmful failure (OOS-4)."""

    def test_every_result_says_bold_type_was_not_checked(self):
        for text in (WARNING_STATEMENT, TITLE_CASE, ALTERED_WORD, "no warning here"):
            result = check_warning(text)
            assert result.bold_type_checked is False
            assert "not checked" in result.bold_type_note

    def test_no_reason_string_claims_bold_was_verified(self):
        for text in (WARNING_STATEMENT, TITLE_CASE, ALTERED_WORD, "no warning here"):
            assert "bold" not in check_warning(text).reason.lower()

    def test_the_prefix_constant_is_the_one_the_regulation_names(self):
        assert WARNING_PREFIX == "GOVERNMENT WARNING:"
