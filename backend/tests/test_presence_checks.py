"""Alcohol content and net contents are presence checks, and they pass.

FR-15, [ADR 0018](../../docs/adr/0018-presence-checks.md).

The author, on the released build: "Alcohol content and net content needs to
also say 'match' or 'Contains' in green when these items are found on the
artwork (that is the requirement right? to have the volume and alcohol content
listed?)."

It is the requirement. 27 CFR 5.63(a)(3), 4.32(b)(3) and 7.63(a)(3) put alcohol
content on the label; 5.63(b)(2), 4.32(b)(2) and 7.63(a)(5) put net contents
there. So when the artwork carries `42% ALC BY VOL`, the tool has established
something real and positive: the label carries a required element. That is not
circular, and it was being thrown away because the form happened to be silent.

The circular part was never the finding. It was comparing that value against the
same picture it was read from, and the fix is to stop presenting it as a
comparison at all: no application side, because there is nothing on that side.

These tests hold both paths open. Where the application declares the value the
row is a two-sided comparison and reports match or does not match exactly as
before; where it does not, the row is one-sided and reports the finding.

Fixtures are rendered at test time and no real applicant data appears here
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


@pytest.fixture(scope="module")
def artwork() -> bytes:
    """The sample label, which carries both required elements."""
    return render_png_bytes(SAMPLE_LABEL)


@pytest.fixture(scope="module")
def artwork_without_net_contents() -> bytes:
    """The same label with the net contents taken off it."""
    return render_png_bytes(replace(SAMPLE_LABEL, net_contents=""))


def document(images: list[bytes], **spec) -> bytes:
    """A filing whose form states only what `spec` names, carrying `images`.

    The paper form, which is TTB F 5100.31 itself: A-17 says it has no alcohol
    content and no net contents boxes, so this is the shape that leaves both to
    the artwork.
    """
    return as_pdf_bytes(paper_form_lines(ApplicationSpec(**spec)), images=images)


def printout(images: list[bytes], **spec) -> bytes:
    """A Public COLA Registry printout, which does state the two values.

    The other shape a filing arrives in, and the one that makes both rows real
    two-sided comparisons.
    """
    return as_pdf_bytes(registry_printout_lines(ApplicationSpec(**spec)), images=images)


def submit(pdf: bytes, **typed) -> dict:
    files = [("files", ("application.pdf", pdf, "application/pdf"))]
    response = client.post("/api/verify", files=files, data=typed)
    assert response.status_code == 200, response.text
    return response.json()


def rows(body: dict) -> dict:
    return {entry["name"]: entry for entry in body["fields"]}


class TestTheComparisonLayer:
    """The rule itself, with no OCR and no HTTP anywhere near it."""

    def test_the_label_carries_it_and_the_application_is_silent(self):
        result = compare_abv("45% Alc./Vol.", None)

        assert result.outcome is Outcome.PRESENT
        assert result.score is None
        assert "27 CFR 5.63(a)(3)" in result.reason

    def test_net_contents_the_same_way(self):
        result = compare_net_contents("750 mL", None)

        assert result.outcome is Outcome.PRESENT
        assert "27 CFR 5.63(b)(2)" in result.reason

    def test_an_empty_application_string_counts_as_silent(self):
        """A blank part is not a declaration, and the browser sends blanks."""
        assert compare_abv("45% Alc./Vol.", "   ").outcome is Outcome.PRESENT

    def test_a_declared_value_is_still_compared(self):
        agreeing = compare_abv("45% Alc./Vol.", "45")
        disagreeing = compare_abv("45% Alc./Vol.", "40")

        assert agreeing.outcome is Outcome.MATCH
        assert agreeing.score == 100.0
        assert disagreeing.outcome is Outcome.MISMATCH

    def test_absence_is_a_finding_and_not_a_presence_check(self):
        """The other answer to the same question (FR-14, ADR 0013)."""
        for result in (compare_abv(None, None), compare_net_contents(None, None)):
            assert result.outcome is Outcome.MISMATCH

    def test_a_label_that_contradicts_itself_is_still_reviewed(self):
        """A-12 wins over the presence check, and the order is deliberate.

        A presence check reporting "the element is there" over the top of a
        contradiction would answer a narrower question than the one the tool had
        already answered.
        """
        result = compare_abv("45% Alc./Vol. (100 Proof)", None)

        assert result.outcome is Outcome.NEEDS_REVIEW
        assert "contradicts itself" in result.reason


@requires_tesseract
@requires_fonts
class TestTheDocumentOnlySubmission:
    """The author's own case: her filing, uploaded alone."""

    def test_both_values_pass_as_presence_checks(self, artwork):
        by_name = rows(submit(document([artwork])))

        for name in ("alcohol_content", "net_contents"):
            entry = by_name[name]
            assert entry["outcome"] == "present"
            assert entry["label_value"], f"{name} should be read off the label"

    def test_neither_row_prints_the_same_string_twice(self, artwork):
        """No application side, because there is nothing on that side.

        This is the whole of the presentation half of the decision. The value
        the artwork supplied is the label, read once; showing it in both columns
        is what invited an agent to read a comparison into a row that never made
        one.
        """
        by_name = rows(submit(document([artwork])))

        for name in ("alcohol_content", "net_contents"):
            assert by_name[name]["application_value"] is None
            assert by_name[name]["application_value_source"] == "absent"

    def test_the_five_rows_are_still_five_rows(self, artwork):
        assert len(submit(document([artwork]))["fields"]) == 5

    def test_a_missing_element_is_a_failure_naming_the_regulation(
        self, artwork_without_net_contents
    ):
        """Absence is a real finding, whatever the form says (ADR 0013).

        And the reason carries the container carve-out, because an agent reading
        it needs to know when absence is not a defect: net contents may be blown,
        embossed or moulded into the container, which a flat label cannot show.
        """
        entry = rows(submit(document([artwork_without_net_contents])))["net_contents"]

        assert entry["outcome"] == "mismatch"
        assert "27 CFR 5.63(b)(2)" in entry["reason"]
        assert "blown, embossed, or molded into the container" in entry["reason"]


@requires_tesseract
@requires_fonts
class TestWhereTheApplicationDoesDeclareIt:
    """Both paths exist, and the second one is unchanged."""

    def test_a_form_that_states_the_value_is_a_two_sided_comparison(self, artwork):
        by_name = rows(submit(printout([artwork], alcohol_content="45% Alc./Vol.")))
        entry = by_name["alcohol_content"]

        assert entry["outcome"] == "match"
        assert entry["application_value"]
        assert entry["application_value_source"] == "parsed_from_form"

    def test_a_typed_value_is_a_two_sided_comparison(self, artwork):
        entry = rows(submit(document([artwork]), net_contents="750 mL"))["net_contents"]

        assert entry["outcome"] == "match"
        assert entry["application_value"] == "750 mL"
        assert entry["application_value_source"] == "typed"

    def test_a_declared_value_that_disagrees_does_not_match(self, artwork):
        entry = rows(submit(document([artwork]), net_contents="375 mL"))["net_contents"]

        assert entry["outcome"] == "mismatch"
        assert entry["application_value"] == "375 mL"

    def test_a_typed_value_beside_a_presence_check(self, artwork):
        """One row each way on one submission, which is the ordinary case."""
        by_name = rows(submit(document([artwork]), alcohol_content="45"))

        assert by_name["alcohol_content"]["outcome"] == "match"
        assert by_name["net_contents"]["outcome"] == "present"
