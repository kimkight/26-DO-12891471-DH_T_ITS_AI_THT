"""A government warning that differs by one or two characters (FR-5, ADR 0012).

FR-5 compares the warning for exact text after whitespace normalization, and
that exactness is deliberate: Jenny Park, "It has to be exact. Like,
word-for-word." Nothing here loosens it. The body still has to be identical to
27 CFR 16.21 to be reported as a match, and `body_matches` is still that
comparison and nothing else.

What changed is what a very small difference is reported *as*. The author's own
COLA artwork, 2026-08-29, OCRs the statement with exactly one character wrong,
`MPAIRS` for `IMPAIRS`. Reporting that as a flat mismatch tells an agent their
label is defective when the truth is that the scan is imperfect. So a difference
within `TTB_WARNING_NEAR_MISS_EDITS` characters is routed to human judgement,
with the exact character-level difference shown. **It is never a pass.**
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.compare import Outcome  # noqa: E402
from app.config import settings  # noqa: E402
from app.parse import ParsedFields, lines_from_text, parse_fields  # noqa: E402
from app.verify import build_result  # noqa: E402
from app.warning import (  # noqa: E402
    WARNING_STATEMENT,
    body_diff,
    check_warning,
)


def outcome_for(text: str) -> tuple[Outcome, dict]:
    """Run one statement through the whole result-building path.

    Through `build_result` rather than through `check_warning` alone, because
    the routing decision is made there and the point of these tests is which
    outcome an agent sees.
    """
    parsed: ParsedFields = parse_fields(lines_from_text(text))
    result = build_result(parsed, {}, 90.0, ocr_ms=1.0)
    field = next(entry for entry in result.fields if entry.name == "government_warning")
    return field.outcome, result.warning_detail.model_dump()


class TestExactStaysMatch:
    """The rule FR-5 is written around, unchanged."""

    def test_the_statement_as_printed_matches(self):
        outcome, detail = outcome_for(WARNING_STATEMENT)

        assert outcome == Outcome.MATCH
        assert detail["body_matches_regulation"] is True
        assert detail["near_miss"] is False
        assert detail["edit_distance"] == 0
        assert detail["diff"] == []

    def test_whitespace_is_still_presentational(self):
        broken = WARNING_STATEMENT.replace(". (2)", ".\n\n   (2)")

        outcome, detail = outcome_for(broken)

        assert outcome == Outcome.MATCH
        assert detail["edit_distance"] == 0


class TestOneWrongCharacter:
    """The author's own case, 2026-08-29: `MPAIRS` for `IMPAIRS`."""

    MISREAD = WARNING_STATEMENT.replace("impairs", "mpairs")

    def test_it_needs_human_review_rather_than_reporting_a_mismatch(self):
        outcome, detail = outcome_for(self.MISREAD)

        assert outcome == Outcome.NEEDS_REVIEW
        assert detail["near_miss"] is True
        assert detail["edit_distance"] == 1

    def test_it_is_still_not_a_match(self):
        """The distinction the whole change turns on."""
        outcome, detail = outcome_for(self.MISREAD)

        assert outcome != Outcome.MATCH
        # The exact comparison is unchanged and still says no.
        assert detail["body_matches_regulation"] is False

    def test_the_exact_difference_is_shown(self):
        _, detail = outcome_for(self.MISREAD)

        differences = [segment for segment in detail["diff"] if segment["kind"] != "same"]
        assert differences == [{"kind": "missing", "text": "i"}]
        # And the whole statement is still reconstructible from the diff, so the
        # agent is reading a difference rather than a summary of one.
        assert (
            "".join(segment["text"] for segment in detail["diff"] if segment["kind"] != "missing")
            == check_warning(self.MISREAD).body_found
        )

    def test_the_reason_asks_for_judgement_and_claims_nothing(self):
        _, detail = outcome_for(self.MISREAD)
        reason = check_warning(self.MISREAD).reason

        assert "1 character" in reason
        assert "for you to judge" in reason
        # It must not read as a pass, and it must not read as a verdict of
        # defective. Both would be the tool overstating what it knows.
        assert "This is not a match" in reason
        assert "defect on the label" in reason


class TestBeyondTheThreshold:
    """A real wording difference is still a mismatch, and is meant to be."""

    def test_a_missing_clause_is_a_mismatch(self):
        outcome, detail = outcome_for(WARNING_STATEMENT.replace("or operate machinery, ", ""))

        assert outcome == Outcome.MISMATCH
        assert detail["near_miss"] is False
        assert detail["edit_distance"] > settings.warning_near_miss_edits

    def test_an_altered_word_is_a_mismatch(self):
        altered = WARNING_STATEMENT.replace(
            "women should not drink alcoholic beverages",
            "women should avoid alcoholic beverages",
        )

        outcome, detail = outcome_for(altered)

        assert outcome == Outcome.MISMATCH
        assert detail["near_miss"] is False

    def test_an_added_word_is_a_mismatch(self):
        added = WARNING_STATEMENT.replace("birth defects", "serious birth defects")

        outcome, _ = outcome_for(added)

        assert outcome == Outcome.MISMATCH

    def test_the_diff_is_still_shown_on_a_mismatch(self):
        """It is evidence either way. Only the outcome depends on the size."""
        _, detail = outcome_for(WARNING_STATEMENT.replace("or operate machinery, ", ""))

        assert any(segment["kind"] == "missing" for segment in detail["diff"])

    @pytest.mark.parametrize("edits", [1, 2, 3, 4])
    def test_the_threshold_is_the_setting_rather_than_a_constant(self, edits, monkeypatch):
        """NFR-11: the number is configurable, and the routing reads it."""
        monkeypatch.setattr(settings, "warning_near_miss_edits", edits)
        # Three characters wrong: one substitution and two deletions.
        three = WARNING_STATEMENT.replace("machinery", "machnery").replace("impairs", "mpairs")
        three = three.replace("problems", "problms")

        outcome, detail = outcome_for(three)

        assert detail["edit_distance"] == 3
        assert outcome == (Outcome.NEEDS_REVIEW if edits >= 3 else Outcome.MISMATCH)


class TestCapitalizationIsNeverANearMiss:
    """Jenny Park's case is a defect a person caught, not a reading artifact."""

    def test_a_title_case_prefix_with_a_perfect_body_is_a_mismatch(self):
        titled = WARNING_STATEMENT.replace("GOVERNMENT WARNING:", "Government Warning:")

        outcome, detail = outcome_for(titled)

        assert outcome == Outcome.MISMATCH
        assert detail["prefix_is_capitalized"] is False
        # The body itself is untouched, and the result still says so (FR-6).
        assert detail["body_matches_regulation"] is True

    def test_a_title_case_prefix_and_a_near_miss_body_is_still_a_mismatch(self):
        both = WARNING_STATEMENT.replace("GOVERNMENT WARNING:", "Government Warning:").replace(
            "impairs", "mpairs"
        )

        outcome, detail = outcome_for(both)

        assert outcome == Outcome.MISMATCH
        assert detail["near_miss"] is True


class TestTheDiffItself:
    """Character level, because the differences worth telling apart are inside words."""

    def test_it_reads_from_the_label_point_of_view(self):
        segments = body_diff("the labl text", "the label text")

        assert [(segment.kind, segment.text) for segment in segments] == [
            ("same", "the lab"),
            ("missing", "e"),
            ("same", "l text"),
        ]

    def test_text_on_the_label_that_the_regulation_lacks_is_added(self):
        segments = body_diff("the labell text", "the label text")

        assert ("added", "l") in [(segment.kind, segment.text) for segment in segments]

    def test_two_identical_texts_produce_one_run(self):
        assert [(s.kind, s.text) for s in body_diff("same", "same")] == [("same", "same")]
