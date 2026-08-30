"""One upload, sorted by the server (FR-12, ADR 0011).

The author's words on 2026-08-29, having been blocked from submitting a COLA
document because a label image was also required: "if COLA is uploaded, I don't
also need an image", and "these should be combined; just one upload; simplify
the interface. You should be able to upload (pdfs or images)."

So there is one part, `files`, taking PDFs and images in any mix, and the server
decides what each file is **from the file** rather than from the part it arrived
in. These tests are that rule, including the case that matters most: a file
dropped into the wrong one of the two older parts is still read correctly.

Requirements: FR-12, FR-11, FR-1, FR-9 (a message that names the problem and
carries no field outcomes), NFR-7 (type and size checked per file before
anything is decoded), NFR-6.

Fixtures are generated at test time; no real applicant data is committed
(docs/07_TEST_STRATEGY.md section 8).
"""

from __future__ import annotations

import sys
from pathlib import Path

from fastapi.testclient import TestClient

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from samples.formmaker import (  # noqa: E402
    ApplicationSpec,
    as_pdf_bytes,
    as_png_bytes,
    paper_form_lines,
    registry_printout_lines,
)
from samples.labelmaker import render_png_bytes  # noqa: E402
from samples.specs import SAMPLE_LABEL  # noqa: E402

from app.config import settings  # noqa: E402
from app.main import app  # noqa: E402
from tests.conftest import requires_fonts, requires_tesseract  # noqa: E402

client = TestClient(app)

REGISTRY = ApplicationSpec(
    class_type="KENTUCKY STRAIGHT BOURBON WHISKEY",
    class_type_code="141",
    alcohol_content="45% ALC/VOL",
    net_contents="750 ML",
)


def registry_pdf() -> bytes:
    return as_pdf_bytes(registry_printout_lines(REGISTRY))


def part(name: str, content: bytes, filename: str, content_type: str):
    return (name, (filename, content, content_type))


def classification(body, filename):
    return next(entry for entry in body["files"] if entry["filename"] == filename)


@requires_tesseract
@requires_fonts
class TestTheServerSortsTheFiles:
    """One part in, two sides out, and the response says which is which."""

    def test_a_pdf_and_a_photo_in_one_part_are_sorted(self, sample_label_png):
        response = client.post(
            "/api/verify",
            files=[
                part("files", registry_pdf(), "application.pdf", "application/pdf"),
                part("files", sample_label_png, "label.png", "image/png"),
            ],
        )

        assert response.status_code == 200, response.text
        body = response.json()
        assert classification(body, "application.pdf")["classified_as"] == "application_document"
        assert classification(body, "application.pdf")["basis"] == "pdf_header"
        assert classification(body, "label.png")["classified_as"] == "label_image"
        assert classification(body, "label.png")["basis"] == "no_form_markers"
        # The check ran on the photograph, with the document as the application
        # side, which is the two-file case working as one upload.
        assert body["label_source"] == "uploaded_photographs"
        assert body["application_document"] is not None

    def test_the_part_a_file_arrived_in_does_not_decide(self, sample_label_png):
        """A COLA PDF dropped into the photo part is still the application.

        This is the whole point of classifying. The older named parts are kept
        so a caller written against v1.0 keeps working, and a file sent through
        either of them goes through the same rule.
        """
        response = client.post(
            "/api/verify",
            files=[
                part("image", registry_pdf(), "application.pdf", "application/pdf"),
                part("application_document", sample_label_png, "label.png", "image/png"),
            ],
        )

        assert response.status_code == 200, response.text
        body = response.json()
        assert classification(body, "application.pdf")["classified_as"] == "application_document"
        assert classification(body, "label.png")["classified_as"] == "label_image"
        # And the values came off the document, not off the photograph.
        brand = next(item for item in body["fields"] if item["name"] == "brand_name")
        assert brand["application_value_source"] == "parsed_from_form"

    def test_a_photograph_of_a_form_is_the_application_side(self, sample_label_png):
        """An image that reads as a COLA form is a form, not a label."""
        scanned = as_png_bytes(paper_form_lines(ApplicationSpec()))
        assert scanned is not None

        response = client.post(
            "/api/verify",
            files=[
                part("files", scanned, "scan.png", "image/png"),
                part("files", sample_label_png, "label.png", "image/png"),
            ],
        )

        assert response.status_code == 200, response.text
        body = response.json()
        entry = classification(body, "scan.png")
        assert entry["classified_as"] == "application_document"
        assert entry["basis"] in ("form_markers", "form_values")
        assert classification(body, "label.png")["classified_as"] == "label_image"

    def test_the_reason_is_a_sentence_an_agent_can_read(self, sample_label_png):
        response = client.post(
            "/api/verify",
            files=[part("files", sample_label_png, "label.png", "image/png")],
        )

        assert response.status_code == 200, response.text
        assert (
            classification(response.json(), "label.png")["reason"]
            == "We read this picture as a label."
        )


@requires_tesseract
@requires_fonts
class TestThreeValidSubmissions:
    """The three shapes FR-12 names, each of which has to complete."""

    def test_an_application_document_alone(self):
        """Task 0's artwork supplies the label side (ADR 0010)."""
        pdf = as_pdf_bytes(
            paper_form_lines(ApplicationSpec()), images=[render_png_bytes(SAMPLE_LABEL)]
        )

        response = client.post(
            "/api/verify", files=[part("files", pdf, "application.pdf", "application/pdf")]
        )

        assert response.status_code == 200, response.text
        body = response.json()
        assert body["label_source"] == "application_artwork"
        assert len(body["fields"]) == 5

    def test_a_label_photo_plus_typed_values(self, sample_label_png):
        response = client.post(
            "/api/verify",
            files=[part("files", sample_label_png, "label.png", "image/png")],
            data={"brand_name": "Stone's Throw", "alcohol_content": "45"},
        )

        assert response.status_code == 200, response.text
        body = response.json()
        brand = next(item for item in body["fields"] if item["name"] == "brand_name")
        assert brand["application_value_source"] == "typed"
        assert body["application_document"] is None

    def test_both(self, sample_label_png):
        response = client.post(
            "/api/verify",
            files=[
                part("files", registry_pdf(), "application.pdf", "application/pdf"),
                part("files", sample_label_png, "label.png", "image/png"),
            ],
        )

        assert response.status_code == 200, response.text
        assert len(response.json()["fields"]) == 5


@requires_tesseract
@requires_fonts
class TestWhatIsRefused:
    """Each refusal names the problem and carries no field outcomes (FR-9)."""

    def test_nothing_at_all(self):
        response = client.post("/api/verify", data={"brand_name": "Stone's Throw"})

        assert response.status_code == 422
        body = response.json()
        assert body["error"]["code"] == "no_files"
        assert (
            "Upload the label application, an image of the label, or both"
            in (body["error"]["message"])
        )
        assert "fields" not in body

    def test_an_application_with_no_artwork_and_no_photo(self):
        """The FR-9 message names the missing piece and offers the photo."""
        response = client.post(
            "/api/verify", files=[part("files", registry_pdf(), "a.pdf", "application/pdf")]
        )

        assert response.status_code == 422
        body = response.json()
        assert body["error"]["code"] == "no_label_to_check"
        assert "Add an image of the label" in body["error"]["message"]
        assert "fields" not in body

    def test_more_than_one_application_document(self):
        response = client.post(
            "/api/verify",
            files=[
                part("files", registry_pdf(), "one.pdf", "application/pdf"),
                part("files", registry_pdf(), "two.pdf", "application/pdf"),
            ],
        )

        assert response.status_code == 413
        body = response.json()
        assert body["error"]["code"] == "too_many_application_documents"
        assert "fields" not in body

    def test_more_label_pictures_than_the_limit(self, sample_label_png):
        response = client.post(
            "/api/verify",
            files=[
                part("files", sample_label_png, f"label-{index}.png", "image/png")
                for index in range(settings.max_label_photos + 1)
            ],
        )

        assert response.status_code == 413
        body = response.json()
        assert body["error"]["code"] == "too_many_photos"
        assert str(settings.max_label_photos) in body["error"]["limit"]
        assert "fields" not in body


@requires_tesseract
@requires_fonts
class TestTheClassifyRoute:
    """What the interface asks for before it asks for a check (ADR 0011)."""

    def test_it_sorts_and_reads_without_comparing_anything(self, sample_label_png):
        response = client.post(
            "/api/classify",
            files=[
                part("files", registry_pdf(), "application.pdf", "application/pdf"),
                part("files", sample_label_png, "label.png", "image/png"),
            ],
        )

        assert response.status_code == 200, response.text
        body = response.json()
        assert classification(body, "application.pdf")["classified_as"] == "application_document"
        assert classification(body, "label.png")["classified_as"] == "label_image"
        assert body["label_images"] == 1
        assert body["application_document"]["fields"]
        # Nothing was compared.
        assert "fields" not in body

    def test_a_second_application_document_is_reported_as_not_used(self):
        response = client.post(
            "/api/classify",
            files=[
                part("files", registry_pdf(), "one.pdf", "application/pdf"),
                part("files", registry_pdf(), "two.pdf", "application/pdf"),
            ],
        )

        assert response.status_code == 200, response.text
        body = response.json()
        assert classification(body, "one.pdf")["used"] is True
        assert classification(body, "two.pdf")["used"] is False

    def test_an_unreadable_application_keeps_its_classification(self):
        """The file is still a PDF; what failed is reading it (FR-9)."""
        response = client.post(
            "/api/classify",
            files=[part("files", b"%PDF-1.4 broken", "broken.pdf", "application/pdf")],
        )

        assert response.status_code == 200, response.text
        body = response.json()
        assert classification(body, "broken.pdf")["classified_as"] == "application_document"
        assert body["application_document"] is None
        assert body["application_error"]["code"] == "unreadable_application_document"

    def test_no_files_names_what_to_do(self):
        response = client.post("/api/classify")

        assert response.status_code == 422
        assert response.json()["error"]["code"] == "no_files"
