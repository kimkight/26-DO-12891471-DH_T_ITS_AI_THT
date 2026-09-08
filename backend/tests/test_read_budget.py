"""One document's reading has a ceiling in Tesseract reads, and says what it left.

[ADR 0023](../../docs/adr/0023-a-read-budget-per-document.md), NFR-1.

The bourbon filing in samples/real/ measured 8064 ms on the deployed v1.5.0
build, 7679 ms of it artwork OCR: nineteen Tesseract reads over five panels,
because on that document no panel's first read settles it and every panel
pays for both arms. Nothing bounded that but the count of pictures, and a
count of pictures bounds nothing about what each one costs. The ceiling is
in reads rather than milliseconds so that the same document gets the same
answer on every host; the setting's comment and the ADR say why.

The other half of the decision is that a budget which cut silently would be
worse than the slowness: every picture and page the reader did not get to is
listed as ``not_reached``, counted, and said in words in the notes, so that a
value reported not found can be traced to something nobody looked at.

Fixtures are rendered at test time; no real applicant data appears here
(docs/07_TEST_STRATEGY.md section 8). Nothing reads samples/real/.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from samples.formmaker import (  # noqa: E402
    ApplicationSpec,
    as_pdf_bytes,
    as_png_bytes,
    as_scanned_pdf_bytes,
    paper_form_lines,
)
from samples.labelmaker import render_png_bytes  # noqa: E402
from samples.specs import SAMPLE_LABEL  # noqa: E402

from app import timing  # noqa: E402
from app.application_form import parse_application_document  # noqa: E402
from app.config import settings  # noqa: E402
from app.main import app  # noqa: E402
from app.ocr import extract_text  # noqa: E402
from tests.conftest import requires_fonts, requires_tesseract  # noqa: E402
from tests.test_artwork_panels import PANELS, SIDE_PAGE, bourbon_document  # noqa: E402

client = TestClient(app)


def verify(pdf: bytes) -> dict:
    response = client.post("/api/verify", files=[("files", ("cola.pdf", pdf, "application/pdf"))])
    assert response.status_code == 200, response.text
    return response.json()


@pytest.fixture(scope="module")
def artwork() -> bytes:
    return render_png_bytes(SAMPLE_LABEL)


@pytest.fixture(scope="module")
def parsed():
    """The five-panel fixture under a ceiling of two reads, once for the module.

    A module-scoped fixture cannot take ``monkeypatch``, which is
    function-scoped, so the setting is put back by hand.
    """
    before = settings.max_document_reads
    settings.max_document_reads = 2
    try:
        return parse_application_document(bourbon_document(), "application/pdf")
    finally:
        # Restored before the value is handed out, not at module teardown: a
        # yield here would leave the ceiling at two for every test after the
        # first that used this, which is exactly the order-dependence it
        # would take a slow afternoon to find.
        settings.max_document_reads = before


@pytest.fixture(scope="module")
def scan() -> bytes:
    """A one-page scan of the paper form: no text layer anywhere in it."""
    png = as_png_bytes(paper_form_lines(ApplicationSpec()))
    if png is None:
        pytest.skip("no TrueType font available")
    return as_scanned_pdf_bytes(png)


@requires_tesseract
@requires_fonts
class TestTheResultCountsItsOwnReads:
    """``OcrResult.tesseract_reads`` is what the budget adds up, so it has to
    agree with the tally ``app.timing`` keeps for the request."""

    def test_the_count_on_the_result_is_the_count_the_recording_saw(self, artwork):
        with timing.recording() as recorded:
            result = extract_text(artwork)

        assert result.tesseract_reads == recorded.tesseract_reads
        # The orientation call and at least one arm.
        assert result.tesseract_reads >= 2

    def test_with_orientation_off_it_is_the_arms_alone(self, artwork):
        with timing.recording() as recorded:
            result = extract_text(artwork, correct_orientation=False)

        assert result.tesseract_reads == recorded.tesseract_reads
        assert result.orientation.method == "disabled"
        assert result.tesseract_reads >= 1


@requires_tesseract
@requires_fonts
class TestTheDefaultAdmitsTheMeasuredFilings:
    """The ceiling sits above what any measured filing costs, so it decides
    nothing on them; what it decides is the runaway case."""

    def test_the_setting_is_above_the_bourbons_nineteen_reads(self):
        assert settings.max_document_reads > 19

    def test_the_five_panel_fixture_is_read_in_full(self):
        parsed = parse_application_document(bourbon_document(), "application/pdf")

        assert parsed.read_budget == settings.max_document_reads
        assert parsed.read_budget_reached is False
        assert parsed.tesseract_reads <= settings.max_document_reads
        assert parsed.pages_not_reached == 0
        assert not any(image.status == "not_reached" for image in parsed.artwork_images_accepted)
        assert parsed.artwork_images_read == len(PANELS)


@requires_tesseract
@requires_fonts
class TestTheBudgetStopsTheReaderAndSaysSo:
    """The runaway case, made small: a ceiling of two reads on a five-panel filing."""

    def test_the_first_picture_is_read_whole_and_the_rest_are_not_reached(self, parsed):
        """Checked between pictures, never inside one: the picture being read
        when the line is crossed finishes, and the next one is not started."""
        statuses = [image.status for image in parsed.artwork_images_accepted]
        assert statuses[0] == "read"
        assert statuses[1:] == ["not_reached"] * (len(PANELS) - 1)
        assert parsed.artwork_images_read == 1

    def test_the_reads_spent_are_reported_against_the_ceiling(self, parsed):
        assert parsed.read_budget == 2
        assert parsed.read_budget_reached is True
        # The one picture read cost at least the orientation call and one arm,
        # which is how a budget of two is passed by one picture's reads.
        assert parsed.tesseract_reads >= 2

    def test_the_values_on_the_unread_strip_are_absent_and_the_note_says_why(self, parsed):
        """The strip carries the alcohol content and the net contents. Absent
        here means unread, and the notes say so rather than leaving "not
        found" to be read as "not on the label"."""
        assert parsed.values["alcohol_content"] is None
        assert parsed.values["net_contents"] is None
        note = next((note for note in parsed.notes if "was reached" in note), None)
        assert note is not None, parsed.notes
        assert f"{len(PANELS) - 1} pictures" in note
        assert "2 reads" in note
        assert "may be on what was not read" in note

    def test_the_response_carries_it_and_the_check_still_runs(self, monkeypatch):
        monkeypatch.setattr(settings, "max_document_reads", 2)

        body = verify(bourbon_document())

        document = body["application_document"]
        assert document["read_budget"] == 2
        assert document["read_budget_reached"] is True
        assert [image["status"] for image in document["artwork_images_accepted"]][1:] == [
            "not_reached"
        ] * (len(PANELS) - 1)
        strip = next(
            image for image in document["artwork_images_accepted"] if image["page"] == SIDE_PAGE
        )
        assert strip["status"] == "not_reached"
        assert any("was reached" in note for note in document["notes"])
        # One panel read is one photograph pooled as the label side; the check
        # ran on what was read and reported the rest.
        assert body["label_source"] == "application_artwork"
        assert len(body["photos"]) == 1
        assert body["timings"]["ocr_passes"] == 1


@requires_tesseract
@requires_fonts
class TestTheBudgetCoversThePagesOfAScan:
    """The same ceiling bounds the OCR fallback over rendered pages (ADR 0024
    puts that read in the check; this is what bounds it there)."""

    def test_within_the_budget_the_page_is_read(self, scan):
        parsed = parse_application_document(scan, "application/pdf")

        assert parsed.path == "ocr"
        assert parsed.pages_read == 1
        assert parsed.pages_not_reached == 0
        assert parsed.values["brand_name"]
        assert parsed.tesseract_reads >= 1

    def test_past_the_budget_the_page_is_not_reached_and_the_document_is_not_called_unreadable(
        self, scan, monkeypatch
    ):
        """A page nobody read is not a page that could not be read. The
        ceiling is zero here so that nothing at all is read, which is the
        worst case the message has to survive."""
        monkeypatch.setattr(settings, "max_document_reads", 0)

        parsed = parse_application_document(scan, "application/pdf")

        assert parsed.path == "ocr"
        assert parsed.pages_read == 0
        assert parsed.pages_not_reached == 1
        assert parsed.read_budget_reached is True
        assert parsed.values["brand_name"] is None
        # The scan's own raster is a picture above the floor, so the note
        # counts one page and one picture, in one sentence.
        note = next((note for note in parsed.notes if "was reached" in note), None)
        assert note is not None, parsed.notes
        assert note.startswith("1 page and 1 picture of this application were not read")
        assert "0 reads, was reached after 0" in note


@requires_tesseract
@requires_fonts
class TestADocumentWithATextLayerPaysNothingForThis:
    """The ordinary filing: a text layer, one picture, one pass, and the
    budget fields say so without changing anything else."""

    def test_the_counts_are_reported_and_nothing_is_cut(self, artwork):
        pdf = as_pdf_bytes(paper_form_lines(ApplicationSpec()), images=[artwork])

        body = verify(pdf)

        document = body["application_document"]
        assert document["pages_not_reached"] == 0
        assert document["read_budget_reached"] is False
        assert document["tesseract_reads"] == body["timings"]["tesseract_reads"]
        assert body["timings"]["ocr_passes"] == 1
