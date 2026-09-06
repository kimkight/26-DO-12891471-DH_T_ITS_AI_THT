"""A government warning that is on the label and could not be read cleanly (FR-5, ADR 0022).

**Measured on a real filing, 2026-09-06.** The bourbon's warning panel reads at
86.8 and the body comes back nearly complete, but printer registration marks
run through the prefix, so GOVERNMENT reads as a garble and a run of digits
arrives as a line of its own. Located by the prefix alone, that statement was
reported as absent: the label has no warning, said the row, about a label a
person would pass. Compared word for word, it fails, correctly, on tokens that
are the printer's and not the label's.

Two things change, and one does not. The statement is located by what survived
of its prefix, or by its body's own opening, and a line with no letter in it is
left out of the block. And a difference is reported as the statement being
present and not certified, rather than as a mismatch, when every line that
differs was read below the legibility floor. **What does not change is FR-5's
comparison**: a match is still identical text after whitespace and case
normalization, a near miss keeps its own outcome, and a difference read
confidently, an altered word set in clean type, is the mismatch it always was.
Nothing here passes anything. The synthetic lines below are the shapes of the
measured read; no real filing's text is in them (docs/07_TEST_STRATEGY.md
section 8).
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
from app.ocr import OcrLine  # noqa: E402
from app.parse import parse_fields  # noqa: E402
from app.verify import build_result  # noqa: E402
from app.warning import WARNING_BODY, WARNING_STATEMENT, check_warning, locate_warning  # noqa: E402

CLEAN = 95.0
DAMAGED = 64.0

# The statement as a narrow panel sets it, one clause per line.
STATEMENT_LINES = [
    "GOVERNMENT WARNING: (1) ACCORDING TO THE SURGEON",
    "GENERAL, WOMEN SHOULD NOT DRINK ALCOHOLIC",
    "BEVERAGES DURING PREGNANCY BECAUSE OF THE RISK OF",
    "BIRTH DEFECTS. (2) CONSUMPTION OF ALCOHOLIC",
    "BEVERAGES IMPAIRS YOUR ABILITY TO DRIVE A CAR OR",
    "OPERATE MACHINERY, AND MAY CAUSE HEALTH PROBLEMS.",
]


def read(rows: list[tuple[str, float]]) -> tuple[Outcome, dict, object]:
    """Lines with confidences, through the parser and the whole result path."""
    lines = [
        OcrLine(text=text, confidence=confidence, height=20.0, top=index * 30)
        for index, (text, confidence) in enumerate(rows)
    ]
    parsed = parse_fields(lines)
    result = build_result(parsed, {}, 90.0, ocr_ms=1.0)
    field = next(entry for entry in result.fields if entry.name == "government_warning")
    return field.outcome, result.warning_detail.model_dump(), parsed.warning


def clean(*rows: str) -> list[tuple[str, float]]:
    return [(row, CLEAN) for row in rows]


class TestLocatingTheStatementWithoutItsPrefix:
    """Found by what survived, and the prefix reported as illegible rather than judged."""

    def test_a_garbled_first_word_with_warning_intact_still_locates_it(self):
        rows = [("OeHEAAT Wi WARNING: (1) ACCORDING TO THE SURGEON", DAMAGED)] + clean(
            *STATEMENT_LINES[1:]
        )
        _, detail, check = read(rows)

        assert detail["statement_found"] is True
        assert detail["prefix_legible"] is False
        assert detail["prefix_is_capitalized"] is None
        assert check.body_matches is True

    def test_a_prefix_lost_entirely_is_located_by_the_bodys_opening(self):
        rows = [("(1) ACCORDING TO THE SURGEON", DAMAGED)] + clean(*STATEMENT_LINES[1:])
        _, detail, check = read(rows)

        assert detail["statement_found"] is True
        assert detail["prefix_legible"] is False
        assert detail["prefix_as_printed"] is None
        assert check.body_matches is True

    def test_warning_on_its_own_does_not_locate_a_statement(self):
        """Another warning, or the bare word, is not this statement."""
        rows = clean("WARNING: CONTAINS SULFITES", "STONE'S THROW", "750 ML")
        outcome, detail, _ = read(rows)

        assert detail["statement_found"] is False
        assert outcome is Outcome.MISMATCH

    def test_the_legible_prefix_is_still_found_first_and_checked(self):
        located = locate_warning(WARNING_STATEMENT)
        assert located is not None
        assert located.prefix_legible is True
        assert check_warning(WARNING_STATEMENT).prefix_is_upper_case is True

    def test_a_title_case_prefix_is_still_a_capitalization_failure(self):
        """FR-6 is untouched: what was read is judged; only what was not read is not."""
        check = check_warning(f"Government Warning: {WARNING_BODY}")
        assert check.prefix_legible is True
        assert check.prefix_is_upper_case is False


class TestLettersOnlyLinesBelongToTheBlock:
    def test_a_run_of_digits_inside_the_statement_is_not_part_of_it(self):
        rows = clean(*STATEMENT_LINES[:4]) + [("00000000", 96.0)] + clean(*STATEMENT_LINES[4:])
        outcome, detail, _ = read(rows)

        assert outcome is Outcome.MATCH
        assert detail["body_matches_regulation"] is True

    def test_a_run_of_digits_after_the_statement_does_not_over_run_it(self):
        rows = clean(*STATEMENT_LINES) + [("00000000", 96.0)]
        outcome, _, _ = read(rows)
        assert outcome is Outcome.MATCH

    def test_a_line_with_letters_in_it_is_still_part_of_the_block(self):
        """The exclusion is for letterless lines only; a word is a word."""
        rows = clean(*STATEMENT_LINES[:4]) + [("LOT 12A", CLEAN)] + clean(*STATEMENT_LINES[4:])
        outcome, _, _ = read(rows)
        assert outcome is Outcome.MISMATCH


class TestPresentAndNotCertified:
    """Every differing line read below the floor: a person looks, nothing passes."""

    OVERPRINTED = [
        ("OeHEAAT Wi WARNING: (1) ACCORDING TO THE anile", DAMAGED),
        (STATEMENT_LINES[1], CLEAN),
        (STATEMENT_LINES[2], CLEAN),
        ("BIRTH DEFECTS. ta a OF ALCOHOLIC", 68.5),
        (STATEMENT_LINES[4], CLEAN),
        (STATEMENT_LINES[5], CLEAN),
        ("00000000", 96.0),
    ]

    def test_the_measured_shape_is_present_and_not_certified(self):
        outcome, detail, _ = read(self.OVERPRINTED)

        assert outcome is Outcome.NOT_CERTIFIED
        assert detail["statement_found"] is True
        assert detail["not_certified"] is True
        assert detail["differing_lines"] == 2
        assert detail["illegible_lines"] == 2
        # And it is still not a match, by the comparison FR-5 fixes.
        assert detail["body_matches_regulation"] is False
        assert detail["near_miss"] is False

    def test_the_reason_says_what_is_being_asked_and_claims_nothing(self):
        _, _, check = read(self.OVERPRINTED)

        assert "is on the label" in check.reason
        assert "2 lines of it differ" in check.reason
        assert "not certified word for word" in check.reason
        assert "This is not a match" in check.reason
        assert "capitalization was not checked" in check.reason

    def test_a_damaged_prefix_alone_is_present_and_not_certified(self):
        """The body matches; the prefix could not be read; nothing passes."""
        rows = [("OeHEAAT Wi WARNING: (1) ACCORDING TO THE SURGEON", DAMAGED)] + clean(
            *STATEMENT_LINES[1:]
        )
        outcome, detail, _ = read(rows)

        assert outcome is Outcome.NOT_CERTIFIED
        assert detail["body_matches_regulation"] is True
        assert detail["prefix_is_capitalized"] is None

    def test_a_confidently_read_difference_is_still_a_mismatch(self):
        """An altered word in clean type is the label's, whatever else was damaged."""
        rows = [
            ("OeHEAAT Wi WARNING: (1) ACCORDING TO THE SURGEON", DAMAGED),
            (STATEMENT_LINES[1], CLEAN),
            (STATEMENT_LINES[2], CLEAN),
            (STATEMENT_LINES[3], CLEAN),
            ("BEVERAGES MAY IMPAIR YOUR ABILITY TO DRIVE A CAR OR", CLEAN),
            (STATEMENT_LINES[5], CLEAN),
        ]
        outcome, detail, _ = read(rows)

        assert outcome is Outcome.MISMATCH
        assert detail["not_certified"] is False
        assert detail["differing_lines"] == 2
        assert detail["illegible_lines"] == 1

    def test_a_misspelt_prefix_in_clean_type_is_a_mismatch(self):
        """Read at 95, the damage is the label's: not the reading's."""
        rows = [("GOVERMENT WARNING: (1) ACCORDING TO THE SURGEON", CLEAN)] + clean(
            *STATEMENT_LINES[1:]
        )
        outcome, detail, _ = read(rows)

        assert outcome is Outcome.MISMATCH
        assert detail["prefix_legible"] is False
        assert detail["not_certified"] is False

    def test_an_omitted_clause_is_a_mismatch_even_when_read_poorly(self):
        """Every line is a run of the statement, so nothing differs; the omission stands."""
        rows = [(row, DAMAGED) for row in STATEMENT_LINES if "OPERATE MACHINERY" not in row]
        outcome, detail, _ = read(rows)

        assert outcome is Outcome.MISMATCH
        assert detail["differing_lines"] == 0

    def test_a_near_miss_keeps_its_own_outcome(self):
        rows = [(row.replace("IMPAIRS", "MPAIRS"), DAMAGED) for row in STATEMENT_LINES]
        outcome, detail, _ = read(rows)

        assert outcome is Outcome.NEEDS_REVIEW
        assert detail["near_miss"] is True
        assert detail["not_certified"] is False

    def test_the_plain_text_path_is_unchanged(self):
        """A line with no reading behind it is never illegible (confidence 0)."""
        rows = [(row, 0.0) for row in STATEMENT_LINES]
        rows[4] = ("BEVERAGES MAY IMPAIR YOUR ABILITY TO DRIVE A CAR OR", 0.0)
        outcome, detail, _ = read(rows)

        assert outcome is Outcome.MISMATCH
        assert detail["illegible_lines"] == 0

    def test_the_floor_is_the_setting(self, monkeypatch):
        monkeypatch.setattr(settings, "warning_legible_confidence", 60.0)
        outcome, _, _ = read(self.OVERPRINTED)
        assert outcome is Outcome.MISMATCH

    @pytest.mark.parametrize("hyphen", ["-", "‐", "‑"])
    def test_a_hyphenated_column_has_no_differing_lines(self, hyphen):
        """A-15: a line ending in a line-break hyphen is a run of the statement."""
        rows = clean(
            "GOVERNMENT WARNING: (1) AC" + hyphen,
            "CORDING TO THE SURGEON GENERAL, WOMEN SHOULD NOT DRINK",
            "ALCOHOLIC BEVERAGES DURING PREGNANCY BECAUSE OF THE",
            "RISK OF BIRTH DEFECTS. (2) CONSUMP" + hyphen,
            "TION OF ALCOHOLIC BEVERAGES IMPAIRS YOUR ABILITY TO",
            "DRIVE A CAR OR OPERATE MACHINERY, AND MAY CAUSE",
            "HEALTH PROBLEMS.",
        )
        outcome, detail, _ = read(rows)
        assert outcome is Outcome.MATCH
        assert detail["differing_lines"] == 0
