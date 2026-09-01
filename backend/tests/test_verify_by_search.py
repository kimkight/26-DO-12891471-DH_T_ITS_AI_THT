"""The comparison, inverted: is the declared value on the label? (ADR 0015)

The author submitted her mezcal COLA alone to the deployed v1.1.0 build on
2026-08-30. The application side filled correctly, the artwork read correctly and
the right way up, and two of the four compared fields came back as defects:

    ============== ================================ ==================
    field           reported                          on the artwork
    ============== ================================ ==================
    brand name      Does not match. Not found on      ``DEL MAGUEY``,
                    the label.                        exactly
    class or type   Does not match. Not found on      ``MEZCAL``,
                    the label.                        exactly
    ============== ================================ ==================

Both strings were in the OCR output the tool was already holding. What failed was
the step before the comparison: those two fields were located by type size, the
largest text on that sheet is a misread of ``Vida Clasico``, and the ranking
declined rather than guess. The comparison never saw a value to compare.

So the question is inverted. The application declares the answer, and the check
becomes whether that answer appears on the label. This module pins the contract
that replaces it:

* ``TestFoundInSmallTypeOnABusyPanel`` renders the shape of that artwork, a label
  whose largest text is not the brand and whose brand is set no larger than the
  clutter around it, and asserts the declared brand and class are found. It fails
  against the build this release starts from, where both report not found.
* ``TestAValueTheLabelDoesNotCarry`` asserts that a declared value genuinely
  absent from the label is still reported as not found. The inversion must not
  become a way of agreeing with the applicant.
* ``TestCaseAndPunctuation`` is FR-4 through the new path, including Dave
  Morrison's ``STONE'S THROW`` case, and asserts the row shows the label's own
  casing beside the declared value.
* ``TestInsideALongerWord`` asserts that a value appearing only inside a longer
  word is not a match, which is what stops ``VIDA`` being found in
  ``INDIVIDUAL``.
* ``TestTheRegistryCode`` covers the class or type case: the application states
  ``MEZCAL FB`` and no label prints ``FB``.
* ``TestTheWarningIsUntouched`` asserts FR-5 still runs the exact statutory
  comparison and is not routed through any of this.

Requirements: FR-1 (what is reported about a field on the label), FR-2, FR-3
(the three outcomes at A-4's thresholds), FR-4 (case and punctuation), FR-5
(unchanged). Every fixture is rendered at test time; no image is committed, and
no real applicant data appears anywhere here (docs/07_TEST_STRATEGY.md
section 8).
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from samples.labelmaker import BusyLabelSpec, render_busy_png_bytes  # noqa: E402
from samples.warning_text import WARNING_STATEMENT  # noqa: E402

from app.compare import Outcome  # noqa: E402
from app.config import settings  # noqa: E402
from app.parse import TextRegion, lines_from_text  # noqa: E402
from app.search import (  # noqa: E402
    PRESENCE_LIMIT,
    find_on_label,
    label_units,
    verify_presence,
    without_trailing_code,
)
from app.verify import verify_photos  # noqa: E402

from .conftest import requires_fonts, requires_tesseract  # noqa: E402

# The shape of the author's artwork: one large decorative line that is not the
# brand, and the brand set the same size as everything around it.
MEZCAL_SHAPED = BusyLabelSpec(
    display="Vida Clasico",
    brand="DEL MAGUEY",
    clutter=(
        "SINGLE VILLAGE",
        "PRODUCTO DE MEXICO",
        "HECHO EN OAXACA",
        "IMPORTED BY THE NAMED IMPORTER",
    ),
    class_type="MEZCAL",
    alcohol_content="42% ALC BY VOL",
    net_contents="750 ML",
    warning=WARNING_STATEMENT,
)

DECLARED = {
    "brand_name": "DEL MAGUEY",
    "class_type": "MEZCAL FB",
    "alcohol_content": "42",
    "net_contents": "750 ML",
}


def units_of(*lines: str):
    """Searchable units built from plain text, for the cases that need no image."""
    return label_units(lines_from_text("\n".join(lines)))


def row(result, name: str):
    return next(field for field in result.fields if field.name == name)


class TestTheSearchItself:
    """The unit level: what ``find_on_label`` answers, with no image involved."""

    def test_an_exact_run_of_words_scores_one_hundred(self):
        hit = find_on_label("DEL MAGUEY", units_of("PRODUCTO DE MEXICO DEL MAGUEY SINGLE VILLAGE"))
        assert hit is not None
        assert hit.score == 100.0
        assert hit.text == "DEL MAGUEY"

    def test_the_hit_reports_the_region_it_was_found_in(self):
        units = units_of("DEL MAGUEY")
        hit = find_on_label("DEL MAGUEY", units)
        assert hit is not None
        assert hit.region == TextRegion(column=0, block=0)

    def test_a_value_set_across_two_lines_is_still_found(self):
        """A brand too long for one line is one brand, not two (see LabelUnit)."""
        hit = find_on_label("STONE'S THROW", units_of("STONE'S", "THROW"))
        assert hit is not None
        assert hit.score == 100.0

    def test_a_window_is_scored_rather_than_the_whole_panel(self):
        """A hit is not diluted by the body copy printed around it."""
        clutter = " ".join(["filler"] * 40)
        hit = find_on_label("DEL MAGUEY", units_of(f"{clutter} DEL MAGUEY {clutter}"))
        assert hit is not None
        assert hit.score == 100.0

    def test_nothing_read_means_nothing_found(self):
        assert find_on_label("DEL MAGUEY", []) is None

    def test_a_declared_value_of_only_punctuation_finds_nothing(self):
        assert find_on_label("--", units_of("DEL MAGUEY")) is None


class TestFoundInSmallTypeOnABusyPanel:
    """The author's case. Both fields were reported as not found; both are there."""

    @requires_tesseract
    @requires_fonts
    def test_the_declared_brand_is_found_although_it_is_not_the_largest_text(self):
        result = verify_photos([render_busy_png_bytes(MEZCAL_SHAPED)], dict(DECLARED))
        brand = row(result, "brand_name")
        assert brand.outcome is Outcome.MATCH
        assert brand.found_on_label
        assert brand.label_value == "DEL MAGUEY"

    @requires_tesseract
    @requires_fonts
    def test_the_declared_class_or_type_is_found_too(self):
        result = verify_photos([render_busy_png_bytes(MEZCAL_SHAPED)], dict(DECLARED))
        assert row(result, "class_type").outcome is Outcome.MATCH

    @requires_tesseract
    @requires_fonts
    def test_the_row_says_where_on_the_sheet_it_was_found(self):
        """What replaces the extracted value: a place, not a guess (FR-1, FR-10)."""
        result = verify_photos([render_busy_png_bytes(MEZCAL_SHAPED)], dict(DECLARED))
        brand = row(result, "brand_name")
        assert brand.label_region is not None
        assert f"column {brand.label_region.column}" in brand.reason
        assert f"block {brand.label_region.block}" in brand.reason

    @requires_tesseract
    @requires_fonts
    def test_the_row_states_the_limit_of_what_a_hit_establishes(self):
        result = verify_photos([render_busy_png_bytes(MEZCAL_SHAPED)], dict(DECLARED))
        assert PRESENCE_LIMIT in row(result, "brand_name").reason

    @requires_tesseract
    @requires_fonts
    def test_all_four_declared_values_are_found_on_this_label(self):
        """The whole of the author's table, end to end."""
        result = verify_photos([render_busy_png_bytes(MEZCAL_SHAPED)], dict(DECLARED))
        assert [row(result, name).outcome for name in DECLARED] == [Outcome.MATCH] * 4


class TestAValueTheLabelDoesNotCarry:
    """The inversion must not become a way of agreeing with the applicant."""

    def test_a_declared_brand_absent_from_the_label_is_not_found(self):
        comparison, hit = verify_presence(
            "Brand name", "STORMY RIDGE", units_of("DEL MAGUEY SINGLE VILLAGE MEZCAL")
        )
        assert comparison.outcome is Outcome.MISMATCH
        assert "not found on the label" in comparison.reason
        # The closest text is still reported, because an agent judging the call
        # needs to see what the label does say (FR-3).
        assert hit is not None

    @requires_tesseract
    @requires_fonts
    def test_end_to_end_a_wrong_brand_still_reports_a_defect(self):
        declared = {**DECLARED, "brand_name": "STORMY RIDGE DISTILLERY"}
        result = verify_photos([render_busy_png_bytes(MEZCAL_SHAPED)], declared)
        assert row(result, "brand_name").outcome is Outcome.MISMATCH

    def test_an_empty_label_reading_reports_not_found_rather_than_a_match(self):
        comparison, hit = verify_presence("Brand name", "DEL MAGUEY", [])
        assert comparison.outcome is Outcome.MISMATCH
        assert hit is None


class TestCaseAndPunctuation:
    """FR-4 through the search, including Dave Morrison's case."""

    def test_upper_case_on_the_label_and_title_case_on_the_form_match(self):
        comparison, hit = verify_presence(
            "Brand name", "Stone's Throw", units_of("STONE'S THROW BOURBON")
        )
        assert comparison.outcome is Outcome.MATCH
        assert hit is not None

    def test_the_row_shows_the_label_own_casing(self):
        """The hit carries what the label printed, not the declared value echoed."""
        _, hit = verify_presence("Brand name", "Stone's Throw", units_of("STONE'S THROW BOURBON"))
        assert hit is not None
        assert hit.text == "STONE'S THROW"

    def test_a_typographic_apostrophe_matches_a_straight_one(self):
        comparison, _ = verify_presence("Brand name", "Stone’s Throw", units_of("STONE'S THROW"))
        assert comparison.outcome is Outcome.MATCH

    def test_punctuation_the_reading_invented_does_not_defeat_a_match(self):
        comparison, _ = verify_presence("Brand name", "DEL MAGUEY", units_of("DEL, MAGUEY."))
        assert comparison.outcome is Outcome.MATCH

    def test_two_genuinely_different_names_do_not_match(self):
        comparison, _ = verify_presence("Brand name", "Stone's Throw", units_of("STORMY RIDGE"))
        assert comparison.outcome is Outcome.MISMATCH


class TestInsideALongerWord:
    """A value present only inside a longer word has not been found."""

    def test_a_short_value_inside_a_longer_word_is_not_a_match(self):
        comparison, _ = verify_presence("Brand name", "VIDA", units_of("INDIVIDUAL BOTTLES"))
        assert comparison.outcome is not Outcome.MATCH

    def test_the_exact_pass_requires_whole_words(self):
        hit = find_on_label("VIDA", units_of("INDIVIDUAL BOTTLES"))
        assert hit is None or hit.score < 100.0

    def test_a_whole_word_next_to_a_longer_one_is_still_found(self):
        """The rule is word boundaries, not a ban on short values."""
        hit = find_on_label("VIDA", units_of("INDIVIDUAL VIDA BOTTLES"))
        assert hit is not None
        assert hit.score == 100.0


class TestTheRegistryCode:
    """``MEZCAL FB``: the description is on the label and the code is not."""

    def test_a_trailing_code_is_identified(self):
        assert without_trailing_code("MEZCAL FB") == ("MEZCAL", "FB")

    def test_a_designation_with_no_code_is_left_alone(self):
        assert without_trailing_code("Kentucky Straight Bourbon Whiskey")[1] is None

    def test_the_code_comes_off_and_the_description_is_found(self):
        comparison, hit = verify_presence(
            "Class or type designation",
            "MEZCAL FB",
            units_of("SINGLE VILLAGE MEZCAL"),
            strip_trailing_code=True,
        )
        assert comparison.outcome is Outcome.MATCH
        assert hit is not None
        assert hit.text == "MEZCAL"

    def test_the_row_says_the_code_was_left_off(self):
        comparison, _ = verify_presence(
            "Class or type designation",
            "MEZCAL FB",
            units_of("SINGLE VILLAGE MEZCAL"),
            strip_trailing_code=True,
        )
        assert "registry code" in comparison.reason

    def test_the_full_value_is_searched_for_first(self):
        """Stripping can never lose a match, because it only runs after a miss."""
        comparison, _ = verify_presence(
            "Class or type designation",
            "MEZCAL FB",
            units_of("MEZCAL FB"),
            strip_trailing_code=True,
        )
        assert comparison.outcome is Outcome.MATCH
        assert "registry code" not in comparison.reason

    def test_nothing_is_stripped_from_the_brand_name(self):
        """Only the class or type carries a code; the brand is searched whole."""
        comparison, _ = verify_presence(
            "Brand name", "MEZCAL FB", units_of("SINGLE VILLAGE MEZCAL")
        )
        assert comparison.outcome is not Outcome.MATCH


class TestTheThresholdsAreTheOnesAlreadyConfigured:
    """No new scale. FR-3 and A-4 classify the search score as they classify any."""

    def test_a_score_at_the_match_threshold_is_a_match(self):
        assert settings.match_threshold == 95
        comparison, _ = verify_presence("Brand name", "DEL MAGUEY", units_of("DEL MAGUEY"))
        assert comparison.score == 100.0
        assert comparison.outcome is Outcome.MATCH

    def test_a_near_reading_lands_in_the_review_band(self):
        """One character misread is a person's call, not a defect (FR-3)."""
        comparison, _ = verify_presence("Brand name", "DEL MAGUEY", units_of("DEL MACUEY"))
        assert comparison.outcome is Outcome.NEEDS_REVIEW
        assert settings.review_threshold <= (comparison.score or 0) < settings.match_threshold


class TestTheWarningIsUntouched:
    """FR-5 is a search for a fixed statutory string already, and is unchanged."""

    @requires_tesseract
    @requires_fonts
    def test_the_warning_still_matches_word_for_word(self):
        result = verify_photos([render_busy_png_bytes(MEZCAL_SHAPED)], dict(DECLARED))
        warning = row(result, "government_warning")
        assert warning.outcome is Outcome.MATCH
        assert warning.application_value == WARNING_STATEMENT

    @requires_tesseract
    @requires_fonts
    def test_the_warning_carries_no_similarity_score(self):
        """FR-5 excludes fuzzy tolerance, so it is not scored on any scale."""
        result = verify_photos([render_busy_png_bytes(MEZCAL_SHAPED)], dict(DECLARED))
        assert row(result, "government_warning").score is None

    @requires_tesseract
    @requires_fonts
    def test_an_altered_warning_is_still_a_mismatch(self):
        spec = BusyLabelSpec(
            **{
                **MEZCAL_SHAPED.__dict__,
                "warning": WARNING_STATEMENT.replace(
                    "should not drink alcoholic beverages", "should avoid alcoholic beverages"
                ),
            }
        )
        result = verify_photos([render_busy_png_bytes(spec)], dict(DECLARED))
        assert row(result, "government_warning").outcome is Outcome.MISMATCH


class TestTheExtractorIsStillTheFallback:
    """Nothing to search for means nothing to search for (FR-2)."""

    @requires_tesseract
    @requires_fonts
    def test_a_field_the_application_did_not_supply_is_not_compared(self):
        declared = {**DECLARED, "brand_name": ""}
        result = verify_photos([render_busy_png_bytes(MEZCAL_SHAPED)], declared)
        brand = row(result, "brand_name")
        assert brand.outcome is Outcome.NOT_COMPARED
        assert brand.application_value is None

    @requires_tesseract
    @requires_fonts
    def test_the_extractor_alone_reports_the_largest_text_which_is_not_the_brand(self):
        """What the search replaced, pinned so the reason for replacing it is visible.

        With nothing declared there is nothing to search for, so type size
        decides, and on this label type size answers ``Vida Clasico``: confident,
        and not the brand name. That is the whole argument for the inversion, and
        it is asserted here rather than described.
        """
        declared = {**DECLARED, "brand_name": ""}
        result = verify_photos([render_busy_png_bytes(MEZCAL_SHAPED)], declared)
        assert row(result, "brand_name").label_value == "Vida Clasico"
