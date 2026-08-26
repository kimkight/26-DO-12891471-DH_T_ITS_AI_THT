"""The sample set's own ground truth is checked against the requirements.

The accuracy tier scores the pipeline against samples/expected.csv, so a defect
in the sample set reads as a defect in the pipeline. These tests hold the sample
set to the same source of truth the application is held to: the 27 CFR 16.21
text quoted in docs/03_REQUIREMENTS.md section 1.

Requirements: FR-5, A-14 (the batch CSV contract the applications file follows).
"""

import re
from pathlib import Path

from samples.specs import ALTERED_WARNING, SPECS, TITLE_CASE_WARNING
from samples.warning_text import HYPHENATED_SPLITS, hyphenated_column
from samples.warning_text import WARNING_STATEMENT as SAMPLE_WARNING

from app.warning import WARNING_STATEMENT as APP_WARNING
from app.warning import check_warning, join_line_break_hyphens, normalize_whitespace

REPO_ROOT = Path(__file__).resolve().parents[2]


class TestTheSampleSetsWarningIsTheRegulationsText:
    def test_the_sample_copy_matches_the_requirements_document(self):
        doc = (REPO_ROOT / "docs" / "03_REQUIREMENTS.md").read_text(encoding="utf-8")
        quoted = re.search(r"> (GOVERNMENT WARNING:.*?health problems\.)", doc, re.S)
        assert quoted is not None
        assert normalize_whitespace(quoted.group(1).replace("\n>", " ")) == SAMPLE_WARNING

    def test_the_sample_copy_and_the_application_copy_agree(self):
        """They are separate constants on purpose; this is what keeps them honest."""
        assert SAMPLE_WARNING == APP_WARNING


class TestTheDefectsAreActuallyDefective:
    """A sample labelled as a defect that is not one would score as a false pass."""

    def test_the_title_case_sample_fails_only_capitalization(self):
        result = check_warning(TITLE_CASE_WARNING)
        assert result.prefix_is_upper_case is False
        assert result.body_matches is True

    def test_the_altered_sample_fails_only_the_body(self):
        result = check_warning(ALTERED_WARNING)
        assert result.prefix_is_upper_case is True
        assert result.body_matches is False


class TestTheSampleSetCoversWhatItClaims:
    def test_twelve_labels(self):
        assert len(SPECS) == 12

    def test_filenames_are_unique(self):
        assert len({spec.filename for spec in SPECS}) == len(SPECS)

    def test_all_three_beverage_classes_appear(self):
        assert {spec.beverage_type for spec in SPECS} == {
            "distilled spirits",
            "wine",
            "malt beverage",
        }

    def test_every_named_defect_is_present(self):
        assert any(spec.warning == TITLE_CASE_WARNING for spec in SPECS)
        assert any(spec.warning == ALTERED_WARNING for spec in SPECS)
        assert any(spec.warning is None for spec in SPECS)
        assert any(spec.net_contents is None for spec in SPECS)
        assert any(spec.rotate_degrees for spec in SPECS)
        assert any(spec.low_contrast for spec in SPECS)

    def test_one_sample_declares_an_abv_that_disagrees_with_the_label(self):
        assert any(
            spec.alcohol_content.startswith("40%") and spec.application["alcohol_content"] == "40.5"
            for spec in SPECS
        )

    def test_every_spec_supplies_the_a14_application_columns(self):
        for spec in SPECS:
            assert set(spec.application) == {
                "brand_name",
                "class_type",
                "alcohol_content",
                "net_contents",
                "beverage_type",
            }


class TestTheHyphenatedColumnIsTheRegulationsText:
    """A-15's fixture has to be the regulation set in a narrow column, and
    nothing else. If it drifts, the test that uses it stops proving anything."""

    def test_rejoining_the_hyphens_reproduces_the_statement_exactly(self):
        column = hyphenated_column()
        rejoined = normalize_whitespace(join_line_break_hyphens(column))
        assert rejoined == SAMPLE_WARNING

    def test_it_actually_splits_the_three_words_the_real_label_split(self):
        column = hyphenated_column()
        for head, tail in HYPHENATED_SPLITS.values():
            assert f"{head}-\n{tail}" in column

    def test_it_is_set_in_a_narrow_column(self):
        lines = hyphenated_column().split("\n")
        assert len(lines) > 5
        assert max(len(line) for line in lines) <= 30
