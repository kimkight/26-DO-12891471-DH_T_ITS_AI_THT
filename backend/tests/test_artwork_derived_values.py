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

    def test_both_values_are_filled_and_neither_is_called_a_match(self):
        """The decision, in one assertion each way.

        The values arrive, so no agent is asked to type what the tool already
        read; and neither row claims agreement, because both sides of it are one
        reading of one picture.
        """
        body = submit(document_only())
        by_name = rows(body)

        assert body["label_source"] == "application_artwork"
        for name in ("alcohol_content", "net_contents"):
            entry = by_name[name]
            assert entry["application_value"], f"{name} was not filled from the artwork"
            assert entry["label_value"], f"{name} was not read off the label"
            assert entry["outcome"] == "artwork_derived"
            # Never a match, and never a score. A similarity of 100 between a
            # string and itself would read as evidence of the one thing that
            # was not established.
            assert entry["score"] is None
            assert entry["application_value_source"] == "parsed_from_artwork"

    def test_the_row_says_where_the_value_came_from_without_a_footnote(self):
        """An agent must see why this row is different from the row itself."""
        by_name = rows(submit(document_only()))
        reason = by_name["alcohol_content"]["reason"]
        assert "label artwork inside the application document" in reason
        assert "same artwork is the label being checked" in reason
        assert "rather than as a match" in reason

    def test_the_tally_counts_only_the_fields_that_could_have_disagreed(self):
        """The summary line stops saying five of five.

        The brand name comes off the form's own text layer and the warning is
        checked against 27 CFR 16.21, so both are real comparisons. The three
        the artwork supplied are not, and the count says so rather than
        absorbing them.
        """
        body = submit(document_only())
        outcomes = [entry["outcome"] for entry in body["fields"]]
        verifiable = [outcome for outcome in outcomes if outcome != "artwork_derived"]
        derived = [outcome for outcome in outcomes if outcome == "artwork_derived"]

        assert len(outcomes) == 5
        assert derived, "nothing was reported as read from the artwork"
        assert verifiable.count("match") == len(verifiable)
        assert len(verifiable) + len(derived) == 5

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
        # dragged along with it.
        assert by_name["net_contents"]["outcome"] == "artwork_derived"

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

    def test_a_consistent_proof_with_no_application_value_is_still_not_compared(self):
        """FR-2 is untouched where the label says nothing contradictory."""
        result = compare_abv("45% Alc./Vol. (90 Proof)", None)
        assert result.outcome is Outcome.NOT_COMPARED

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
