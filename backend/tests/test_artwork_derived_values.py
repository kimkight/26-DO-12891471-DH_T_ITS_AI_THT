"""Values read off the artwork are filled in, and never called a match.

FR-14, ADR 0013. The author's decision of 2026-08-30: a COLA document that
states no alcohol content and no net contents, which is the ordinary shape of
TTB F 5100.31 (A-17), has both printed on the label artwork it carries, and the
tool fills them from there rather than asking an agent to hand-type two values
off a document it has already read.

What these tests hold it to is the other half of that decision. A value read off
the artwork, compared against the same artwork standing in as the label, cannot
disagree. A match chip on that row would be structurally incapable of ever
saying anything else, and a tool that shows one loses a sceptical agent
permanently. So it is filled, it is labelled for what it is, and it is kept out
of the count of fields that match.

Every fixture is generated at test time by ``samples/formmaker.py`` and
``samples/labelmaker.py``; no real applicant data is committed
(docs/07_TEST_STRATEGY.md section 8).
"""

from __future__ import annotations

import sys
from dataclasses import replace
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from samples.formmaker import (  # noqa: E402
    ApplicationSpec,
    as_pdf_bytes,
    paper_form_lines,
    registry_printout_lines,
)
from samples.labelmaker import render_png_bytes  # noqa: E402
from samples.specs import SAMPLE_LABEL  # noqa: E402

from app.compare import Outcome, compare_abv, compare_net_contents  # noqa: E402
from app.main import app  # noqa: E402
from tests.conftest import requires_fonts, requires_tesseract  # noqa: E402

client = TestClient(app)

# The four compared fields plus the warning: five rows on every result.
COMPARED = ("brand_name", "class_type", "alcohol_content", "net_contents")


def artwork(**overrides) -> bytes:
    """The sample label as flat artwork, which is what an applicant affixes."""
    return render_png_bytes(replace(SAMPLE_LABEL, **overrides))


def submit(pdf: bytes, *, images: list[bytes] | None = None, **typed) -> dict:
    """One submission through the real route, exactly as the interface makes it."""
    files = [("files", ("application.pdf", pdf, "application/pdf"))]
    for index, image in enumerate(images or [], start=1):
        files.append(("files", (f"label-{index}.png", image, "image/png")))
    response = client.post("/api/verify", files=files, data=typed or None)
    assert response.status_code == 200, response.text
    return response.json()


def rows(body: dict) -> dict[str, dict]:
    return {entry["name"]: entry for entry in body["fields"]}


def document_only(**spec_overrides) -> bytes:
    """A paper form carrying its own label artwork and nothing else useful.

    ``ApplicationSpec`` defaults leave the class or type, the alcohol content
    and the net contents blank, which is what TTB F 5100.31 actually looks
    like: three of the five values this tool compares are not items on the form
    (A-17).
    """
    art = spec_overrides.pop("artwork", None)
    spec = ApplicationSpec(**spec_overrides)
    return as_pdf_bytes(paper_form_lines(spec), images=[art if art is not None else artwork()])


def printout_with_artwork(**spec_overrides) -> bytes:
    """A Public COLA Registry printout, which *does* state the three A-17 values.

    Needed for the precedence tests: the paper form has no alcohol content item
    at all, so there is no way to make its text state one. A printout is the
    other document an agent actually holds, and it carries the artwork the same
    way.
    """
    art = spec_overrides.pop("artwork", None)
    spec = ApplicationSpec(**spec_overrides)
    return as_pdf_bytes(
        registry_printout_lines(spec), images=[art if art is not None else artwork()]
    )


@requires_tesseract
@requires_fonts
class TestTheFormIsSilentAndTheArtworkIsNot:
    """The author's own case, and the one SC-3's batch path is made of."""

    def test_the_two_presence_fields_are_presence_checks_and_they_pass(self):
        """**Amended by ADR 0018, and this is the amendment.**

        These two rows used to be `artwork_derived`: the value was read off the
        artwork, written into the application column, and compared with itself.
        ADR 0013 was right that such a comparison establishes nothing, and wrong
        to keep presenting it as a comparison at all.

        27 CFR requires alcohol content and net contents on the label. The label
        carries both, which is a real, positive, non-circular finding, and it is
        reported as one: a one-sided presence check with no application side,
        and a passing outcome.
        """
        body = submit(document_only())
        by_name = rows(body)

        assert body["label_source"] == "application_artwork"
        for name in ("alcohol_content", "net_contents"):
            entry = by_name[name]
            assert entry["label_value"], f"{name} was not read off the label"
            assert entry["outcome"] == "present"
            # No application side, because there is nothing on that side. A row
            # printing the same string twice is what invited the confusion.
            assert entry["application_value"] is None
            assert entry["application_value_source"] == "absent"
            # No score. A score is a similarity between two strings and there is
            # only one string here.
            assert entry["score"] is None

    def test_the_presence_row_cites_the_regulation_it_answers(self):
        """The row says which requirement it just satisfied, from the row itself.

        An agent has to be able to see, without reading anything else on the
        page, that this is a check of the label against 27 CFR rather than a
        comparison against the form.
        """
        by_name = rows(submit(document_only()))
        reason = by_name["alcohol_content"]["reason"]

        assert "27 CFR 5.63(a)(3)" in reason
        assert "The application declared no value" in reason
        assert "rather than a comparison" in reason

    def test_the_tally_counts_presence_checks_alongside_comparisons(self):
        """The summary line counts both kinds of check.

        It used to read "3 of 3 verifiable fields match; 2 read from the artwork
        only", which was the honest thing to say while the two presence rows were
        circular comparisons. They are not comparisons any more, so they count.
        """
        body = submit(document_only())
        outcomes = [entry["outcome"] for entry in body["fields"]]

        assert len(outcomes) == 5
        assert outcomes.count("present") == 2
        # The brand name off the form's text layer and the warning against
        # 27 CFR 16.21: two real comparisons, both matching.
        assert outcomes.count("match") == 2

    def test_the_artwork_derived_state_survives_where_it_still_applies(self):
        """ADR 0013 is narrowed by ADR 0018, not deleted.

        This fixture's class or type designation is not on the printout's text
        layer, so it is read off the artwork and compared against that same
        artwork. That is exactly the case ADR 0013 was built for, and it is not a
        presence field: 27 CFR requires alcohol content and net contents on the
        label, which is what makes those two answerable one-sidedly, and this
        tool asserts no such rule for the class or type.

        It should be rare after ADR 0018, and on the author's own filing it does
        not arise at all, because that form states the class or type in item 9.
        Rare is not never, and the state has to keep working.
        """
        entry = rows(submit(document_only()))["class_type"]

        assert entry["outcome"] == "artwork_derived"
        assert entry["score"] is None
        assert entry["application_value_source"] == "parsed_from_artwork"

    def test_a_photograph_makes_the_same_row_a_real_comparison_again(self):
        """The rule keys on provenance, not on a field name (ADR 0013).

        The agent uploads the same document and a photograph of the label. The
        alcohol content still comes off the artwork inside the document, but the
        label side is now a second, independent picture, so comparing them is a
        real comparison and is reported as one.
        """
        by_name = rows(submit(document_only(), images=[artwork()]))
        entry = by_name["alcohol_content"]
        assert entry["application_value_source"] == "parsed_from_artwork"
        assert entry["outcome"] == "match"
        assert entry["score"] == 100.0


@requires_tesseract
@requires_fonts
class TestATypedOrStatedValueStillWins:
    """FR-11's precedence is unchanged, which is Dave Morrison's override."""

    def test_a_form_that_states_the_alcohol_content_is_compared_normally(self):
        """The form's own text beats the artwork, and the row is a real match."""
        pdf = printout_with_artwork(alcohol_content="45")
        by_name = rows(submit(pdf))
        entry = by_name["alcohol_content"]

        assert entry["application_value_source"] == "parsed_from_form"
        assert entry["application_value"] == "45"
        assert entry["outcome"] == "match"
        # And the field beside it, which the form still does not state, is not
        # dragged along with it: it is the presence check ADR 0018 makes it.
        assert by_name["net_contents"]["outcome"] == "present"
        assert by_name["net_contents"]["application_value"] is None

    def test_a_typed_value_beats_the_artwork_and_is_compared_normally(self):
        """A value the agent typed is independent evidence, so it is compared."""
        by_name = rows(submit(document_only(), net_contents="750 mL"))
        entry = by_name["net_contents"]

        assert entry["application_value_source"] == "typed"
        assert entry["outcome"] == "match"

    def test_a_typed_value_that_disagrees_reports_a_mismatch(self):
        """The override cuts both ways, which is what makes it worth having."""
        by_name = rows(submit(document_only(), alcohol_content="40"))
        assert by_name["alcohol_content"]["outcome"] == "mismatch"


@requires_tesseract
@requires_fonts
class TestPresenceIsAnIndependentFinding:
    """The half of the check that was never circular (FR-14, ADR 0013)."""

    def test_artwork_without_net_contents_reports_the_regulatory_finding(self):
        """27 CFR requires it on the label whatever the form says.

        Absence is a real result about the label, answerable from the artwork
        alone, so it is reported rather than folded into "not compared".
        """
        pdf = document_only(artwork=artwork(net_contents=""))
        entry = rows(submit(pdf))["net_contents"]

        assert entry["found_on_label"] is False
        assert entry["outcome"] == "mismatch"
        assert "27 CFR 5.63(b)(2)" in entry["reason"]
        # And the carve-out is stated, so a finding is not read as a violation.
        assert "blown, embossed, or molded" in entry["reason"]

    def test_artwork_without_alcohol_content_reports_the_regulatory_finding(self):
        pdf = document_only(artwork=artwork(alcohol_content=""))
        entry = rows(submit(pdf))["alcohol_content"]

        assert entry["found_on_label"] is False
        assert entry["outcome"] == "mismatch"
        assert "27 CFR 5.63(a)(3)" in entry["reason"]
        assert entry["outcome"] != "artwork_derived"


@requires_tesseract
@requires_fonts
class TestTheOneNonCircularInternalCheck:
    """A-12 applied within the label rather than across label and form."""

    def test_a_percentage_and_a_proof_that_disagree_are_reported(self):
        """A real defect with a real failure mode, and it is never absorbed.

        The overlay relabels agreement and nothing else, so this reaches an
        agent as the failing outcome FR-7 and A-12 fix for it rather than as a
        value that was merely read off the artwork.
        """
        pdf = document_only(artwork=artwork(alcohol_content="45% Alc./Vol. (100 Proof)"))
        entry = rows(submit(pdf))["alcohol_content"]

        assert entry["outcome"] != "artwork_derived"
        assert entry["outcome"] == "needs_review"
        assert "27 CFR 5.65" in entry["reason"]
        assert "contradicts itself" in entry["reason"]


class TestTheLabelOnlyChecksNeedNoApplicationValue:
    """Unit tier: both checks read one string and reach a verdict from it."""

    def test_the_proof_cross_check_fires_with_no_application_value(self):
        """It used to be silenced by a row that had nothing to compare."""
        result = compare_abv("45% Alc./Vol. (100 Proof)", None)
        assert result.outcome is Outcome.NEEDS_REVIEW
        assert "contradicts itself" in result.reason

    def test_a_consistent_proof_with_no_application_value_is_a_presence_check(self):
        """**Amended by ADR 0018.** It used to report "not compared".

        Nothing about the proof cross-check changes: it ran, it found no
        contradiction, and it said nothing. What changes is the row underneath
        it, which used to report FR-2's "the application supplied no value" and
        now reports the finding that was there all along, that the label carries
        the alcohol content 27 CFR requires.
        """
        result = compare_abv("45% Alc./Vol. (90 Proof)", None)
        assert result.outcome is Outcome.PRESENT
        assert result.score is None

    @pytest.mark.parametrize(
        ("compare", "section"),
        [
            (compare_abv, "27 CFR 5.63(a)(3)"),
            (compare_net_contents, "27 CFR 5.63(b)(2)"),
        ],
    )
    def test_absence_from_the_label_is_a_finding_even_with_no_form_value(self, compare, section):
        """Neither side stated it, and the label was still required to."""
        result = compare(None, None)
        assert result.outcome is Outcome.MISMATCH
        assert section in result.reason

    def test_the_existing_cross_field_proof_rule_is_unchanged(self):
        """UAT row 21 still reads exactly as docs/07_TEST_STRATEGY.md says."""
        result = compare_abv("45% Alc./Vol. (92 Proof)", "45")
        assert result.outcome is Outcome.NEEDS_REVIEW
