"""The artwork is read once, at check time, and the prefill pass is cheap.

[ADR 0017](../../docs/adr/0017-read-the-artwork-once.md), NFR-1, NFR-6.

The author measured her own mezcal filing against the deployed build on
2026-09-01, submitted alone, 382 KB:

    request               when it runs                      measured
    POST /api/classify    the moment she picks the file     5492 ms, 5410 ms
    POST /api/verify      when she selects "Check this"     5331 to 5498 ms

Both requests were reading the same pictures. `/api/classify` came back with
`artwork_images_read: 1`, which is the whole of the cost in it; the document's
own text layer takes 277 ms. So one document cost about eleven seconds of
waiting for one Tesseract pass paid for twice.

These tests are the three claims that fixes it: the prefill pass does not read
the pictures, it still says everything the interface needs to tell "no artwork"
from "artwork not read yet", and the check reads them exactly as it always did
so nothing an agent sees on the result is lost.

Fixtures are rendered at test time and no real applicant data appears here
(docs/07_TEST_STRATEGY.md section 8).
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from samples.formmaker import ApplicationSpec, as_pdf_bytes, paper_form_lines  # noqa: E402
from samples.labelmaker import render_png_bytes  # noqa: E402
from samples.specs import SAMPLE_LABEL  # noqa: E402

from app.application_form import parse_application_document  # noqa: E402
from app.main import app  # noqa: E402
from tests.conftest import requires_fonts, requires_tesseract  # noqa: E402

client = TestClient(app)


@pytest.fixture(scope="module")
def artwork() -> bytes:
    return render_png_bytes(SAMPLE_LABEL)


@pytest.fixture(scope="module")
def with_artwork(artwork: bytes) -> bytes:
    """A filing carrying its own label artwork, which is the ordinary case."""
    return as_pdf_bytes(paper_form_lines(ApplicationSpec()), images=[artwork])


@pytest.fixture(scope="module")
def without_artwork() -> bytes:
    """The same filing with no pictures in it at all."""
    return as_pdf_bytes(paper_form_lines(ApplicationSpec()))


def classify(pdf: bytes) -> dict:
    response = client.post("/api/classify", files=[("files", ("cola.pdf", pdf, "application/pdf"))])
    assert response.status_code == 200, response.text
    return response.json()


def verify(pdf: bytes) -> dict:
    response = client.post("/api/verify", files=[("files", ("cola.pdf", pdf, "application/pdf"))])
    assert response.status_code == 200, response.text
    return response.json()


@requires_tesseract
@requires_fonts
class TestThePrefillPassDoesNotReadThePictures:
    """The half of the eleven seconds that was being paid for twice."""

    def test_no_picture_is_read(self, with_artwork):
        document = classify(with_artwork)["application_document"]

        assert document["artwork_read"] is False
        assert document["artwork_images_read"] == 0

    def test_the_pictures_are_still_counted(self, with_artwork):
        """Counting costs nothing; reading is what cost five seconds."""
        document = classify(with_artwork)["application_document"]

        assert document["artwork_images_found"] >= 1

    def test_no_value_is_attributed_to_the_artwork(self, with_artwork):
        """A value nothing read is a value nothing may claim to have read."""
        document = classify(with_artwork)["application_document"]

        sources = {entry["name"]: entry["source"] for entry in document["fields"]}
        assert "embedded_artwork" not in sources.values()

    def test_the_text_layer_still_answers_what_it_carries(self, with_artwork):
        """The brand name is an item on the form, so it fills as it always did."""
        document = classify(with_artwork)["application_document"]

        brand = next(entry for entry in document["fields"] if entry["name"] == "brand_name")
        assert brand["found_on_document"] is True
        assert brand["value"]

    def test_a_document_with_no_pictures_is_distinguishable(self, without_artwork):
        """ "No artwork" and "artwork not read" must not look the same (ADR 0017).

        Both return `artwork_images_read: 0`, and only one of them is a gap the
        agent has to fill by typing. The count separates them.
        """
        document = classify(without_artwork)["application_document"]

        assert document["artwork_read"] is False
        assert document["artwork_images_found"] == 0

    def test_a_scan_whose_pictures_are_unread_is_not_called_unreadable(self, artwork):
        """A picture left unread is not a document that could not be read.

        A filing whose text layer carries nothing used to be rescued by its
        artwork. Raising here would tell an agent their file is unreadable at
        prefill time and then verify it a moment later.
        """
        pdf = as_pdf_bytes([], images=[artwork])

        body = classify(pdf)

        assert body["application_error"] is None
        assert body["application_document"]["artwork_read"] is False


@requires_tesseract
@requires_fonts
class TestTheCheckStillReadsTheArtwork:
    """Nothing an agent sees on the result is lost by moving the read."""

    def test_the_check_reads_it_and_says_so(self, with_artwork):
        document = verify(with_artwork)["application_document"]

        assert document["artwork_read"] is True
        assert document["artwork_images_read"] == 1

    def test_alcohol_content_and_net_contents_are_filled_by_the_check(self, with_artwork):
        """The two values A-17 says the form does not carry (ADR 0017)."""
        fields = {entry["name"]: entry for entry in verify(with_artwork)["fields"]}

        for name in ("alcohol_content", "net_contents"):
            assert fields[name]["application_value"], f"{name} should be filled by the check"
            assert fields[name]["application_value_source"] == "parsed_from_artwork"

    def test_the_artwork_is_still_the_label_side(self, with_artwork):
        assert verify(with_artwork)["label_source"] == "application_artwork"

    def test_the_read_application_route_still_reads_everything(self, with_artwork):
        """FR-11's route has no second request behind it to do the reading."""
        response = client.post(
            "/api/read-application",
            files=[("application_document", ("cola.pdf", with_artwork, "application/pdf"))],
        )

        assert response.status_code == 200, response.text
        assert response.json()["artwork_read"] is True


@requires_tesseract
@requires_fonts
class TestTheParserItself:
    """The flag at the unit tier, with no HTTP anywhere near it."""

    def test_reading_the_artwork_is_the_default(self, with_artwork):
        assert parse_application_document(with_artwork, "application/pdf").artwork_read is True

    def test_the_prefill_reading_carries_no_artwork_label_side(self, with_artwork):
        """No picture may stand in as the label side until one has been read."""
        parsed = parse_application_document(with_artwork, "application/pdf", read_artwork=False)

        assert parsed.label_artwork is None
        assert parsed.label_artwork_read is None
