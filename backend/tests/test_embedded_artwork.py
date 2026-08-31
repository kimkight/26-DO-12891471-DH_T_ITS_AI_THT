"""The label artwork embedded in a COLA document (ADR 0010, FR-11, A-17).

The author uploaded a real COLA document to the deployed v1.0.1 build on
2026-08-29 and two of the five fields reconciled. The diagnosis was not that the
values were missing: the alcohol content and the net contents are genuinely
absent from the form's text layer, exactly as assumption A-17 says, and both
were printed on the flat label artwork embedded in the same file, at 1750 by
1150 pixels, which the parser never looked at.

These tests are the four cases that behaviour has to get right, and every
fixture is generated at test time by ``samples/formmaker.py`` and
``samples/labelmaker.py``. No real applicant data is committed
(docs/07_TEST_STRATEGY.md section 8).
"""

from __future__ import annotations

import io
import math
import sys
from dataclasses import fields
from pathlib import Path

import pytest
from PIL import Image, ImageDraw

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

from app.application_form import (  # noqa: E402
    SELF_CONSISTENCY_NOTE,
    parse_application_document,
)
from app.config import settings  # noqa: E402
from app.verify import document_result  # noqa: E402
from tests.conftest import requires_fonts, requires_tesseract  # noqa: E402


def signature_strip(width: int, height: int) -> bytes:
    """A picture shaped like a handwritten signature, drawn here, never real.

    Ink strokes rather than a solid mark, so that what rejects it is the floor
    and not an empty image failing to decode, and so that a floor which let it
    through would demonstrably hand OCR something to misread. Nothing about it
    resembles any person's signature: it is three sine-ish strokes drawn from
    arithmetic.
    """
    image = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(image)
    baseline = height // 2
    amplitude = height // 3
    for offset, step in ((0, 7), (width // 3, 11), (2 * width // 3, 5)):
        points = [
            (
                offset + x,
                baseline + int(amplitude * math.sin(x / max(1, step)) * math.cos(x / 40)),
            )
            for x in range(0, width // 3, 3)
        ]
        if len(points) > 1:
            draw.line(points, fill="black", width=max(2, height // 60), joint="curve")
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def solid_png(width: int, height: int) -> bytes:
    """A picture too small to be label artwork: a seal, a barcode, a signature.

    Drawn with a mark on it rather than left blank, so that what rejects it is
    the size floor rather than an empty image failing to decode.
    """
    image = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(image)
    draw.rectangle((2, 2, width - 3, height - 3), outline="black", width=2)
    draw.line((2, 2, width - 3, height - 3), fill="black", width=2)
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


@pytest.fixture
def label_artwork() -> bytes:
    """The sample label as flat artwork, which is what an applicant affixes."""
    return render_png_bytes(SAMPLE_LABEL)


@requires_tesseract
@requires_fonts
class TestTheDocumentCarriesItsOwnArtwork:
    """The author's own case: the values were in the file, in the pictures."""

    def test_the_artwork_fills_what_the_text_layer_left_empty(self, label_artwork):
        """Every value is recovered, and each one says where it came from.

        The paper form carries a brand name in item 6 and carries no class or
        type, alcohol content or net contents at all (A-17). The artwork carries
        all four. What comes back is the union, and the source map is what makes
        it checkable rather than merely correct.
        """
        pdf = as_pdf_bytes(paper_form_lines(ApplicationSpec()), images=[label_artwork])

        parsed = parse_application_document(pdf, "application/pdf")

        assert parsed.values["brand_name"] == "STONE'S THROW"
        assert parsed.value_sources["brand_name"] == "embedded_text"
        for name in ("class_type", "alcohol_content", "net_contents"):
            assert parsed.values[name] is not None, f"{name} should come off the artwork"
            assert parsed.value_sources[name] == "embedded_artwork"
        assert "45" in parsed.values["alcohol_content"]
        assert "750" in parsed.values["net_contents"]

        # Item 5 is three check boxes and the text layer prints all three
        # captions, so the beverage type is still not read. ADR 0008 records
        # that, and nothing here changes it: a label does not print a form
        # answer, so the artwork cannot supply it either.
        assert parsed.values["beverage_type"] is None
        assert "beverage_type" not in parsed.value_sources

    def test_the_artwork_is_offered_as_a_label_side(self, label_artwork):
        """The largest readable picture can stand in for a photograph (ADR 0010)."""
        pdf = as_pdf_bytes(paper_form_lines(ApplicationSpec()), images=[label_artwork])

        parsed = parse_application_document(pdf, "application/pdf")

        assert parsed.artwork_images_found == 1
        assert parsed.artwork_images_read == 1
        assert parsed.label_artwork is not None
        # Extracted at its own resolution, not at whatever a page render would
        # have produced. That is the decision ADR 0010 turns on.
        assert (parsed.label_artwork.width, parsed.label_artwork.height) == (1000, 1500)

    def test_the_limitation_is_stated_rather_than_left_to_a_document(self, label_artwork):
        """Self-consistency, said in the response (ADR 0010)."""
        pdf = as_pdf_bytes(paper_form_lines(ApplicationSpec()), images=[label_artwork])

        parsed = parse_application_document(pdf, "application/pdf")

        assert SELF_CONSISTENCY_NOTE in parsed.notes
        assert "self-consistency" in SELF_CONSISTENCY_NOTE
        assert "photograph of that bottle" in SELF_CONSISTENCY_NOTE

    def test_a_field_the_artwork_supplied_carries_no_absence_note(self, label_artwork):
        """A value that is no longer absent must not be explained as absent.

        Without the artwork the parser tells the agent that the alcohol content
        is not an item on the form and has to be typed. With it, the value is
        there, and repeating the note would send the agent looking for a box
        that has already been answered.
        """
        pdf = as_pdf_bytes(paper_form_lines(ApplicationSpec()), images=[label_artwork])

        parsed = parse_application_document(pdf, "application/pdf")

        assert not any("alcohol content is not an item" in note for note in parsed.notes)
        assert any("type of product is item 5" in note for note in parsed.notes)


@requires_tesseract
@requires_fonts
class TestTheTextLayerWins:
    """Precedence: text beats artwork, always, and the source says which won."""

    def test_a_text_layer_alcohol_content_is_kept_when_the_artwork_disagrees(self, label_artwork):
        """The document's own statement is read; the artwork's is recognized.

        A Registry printout states the alcohol content in its text layer. The
        artwork prints 45%. They are made to disagree deliberately: the point of
        the precedence rule is that the value the file itself carries is not
        subject to an OCR engine's opinion of a picture.
        """
        spec = ApplicationSpec(
            class_type="Kentucky Straight Bourbon Whiskey",
            alcohol_content="40% Alc./Vol.",
            net_contents="700 mL",
        )
        pdf = as_pdf_bytes(registry_printout_lines(spec), images=[label_artwork])

        parsed = parse_application_document(pdf, "application/pdf")

        assert parsed.values["alcohol_content"] == "40% Alc./Vol."
        assert parsed.value_sources["alcohol_content"] == "embedded_text"
        assert parsed.values["net_contents"] == "700 mL"
        assert parsed.value_sources["net_contents"] == "embedded_text"
        # The artwork was still read, and is still available as a label side.
        assert parsed.artwork_images_read == 1
        assert parsed.label_artwork is not None


@requires_tesseract
@requires_fonts
class TestTheSizeFloor:
    """Seals, barcodes and signature blocks are small. Label artwork is not."""

    def test_only_tiny_images_leave_the_artwork_fields_absent(self):
        """Below the floor, nothing is read and nothing crashes.

        The three shapes are the ones a real filing carries: a square seal, a
        wide flat barcode, and a signature strip. Each is rejected by a
        different half of the floor, which is why the floor has two halves.
        """
        pdf = as_pdf_bytes(
            paper_form_lines(ApplicationSpec()),
            images=[solid_png(200, 200), solid_png(900, 120), solid_png(300, 90)],
        )

        parsed = parse_application_document(pdf, "application/pdf")

        assert parsed.artwork_images_found == 0
        assert parsed.artwork_images_read == 0
        assert parsed.label_artwork is None
        assert parsed.values["alcohol_content"] is None
        assert parsed.values["net_contents"] is None
        assert parsed.values["class_type"] is None
        # The brand name is still item 6, read out of the text layer.
        assert parsed.values["brand_name"] == "STONE'S THROW"
        assert SELF_CONSISTENCY_NOTE not in parsed.notes

    def test_a_wide_barcode_is_rejected_by_the_edge_floor_not_the_area_floor(self):
        """Stated as an assertion so the two halves cannot silently become one.

        A 900 by 120 strip is 108,000 pixels, which is under the area floor as
        well. A 2000 by 200 strip is 400,000, which clears it. The edge floor is
        what rejects that, and this asserts it rather than trusting the numbers
        to stay where they are.
        """
        wide = solid_png(2000, 200)
        assert settings.min_artwork_pixels <= 2000 * 200
        assert min(2000, 200) < settings.min_artwork_edge_px

        parsed = parse_application_document(
            as_pdf_bytes(paper_form_lines(ApplicationSpec()), images=[wide]),
            "application/pdf",
        )

        assert parsed.artwork_images_found == 0


class TestTheApplicantsSignatureIsNeverLabelArtwork:
    """The shape test, which is the one a better scanner cannot defeat (v1.1.0).

    A filed TTB F 5100.31 carries the applicant's handwritten signature. It is
    not label artwork, and it is the most personal artefact on the form: the
    standing rule on this repository is that no real applicant's data is
    handled or committed, and reading a signature through an OCR pipeline and
    letting what comes back fill a compliance field is the opposite of that.

    The author's own document carries the signature at 687 by 195, which the two
    absolute floors reject twice over. That is not the interesting case. The
    interesting case is the same strip scanned at 300 dpi rather than 100: about
    2000 by 580, which clears the short-edge floor and clears the area floor by
    more than four times, and is still a signature. An absolute size is a
    property of the scanner. The shape is a property of the thing scanned.
    """

    def test_the_authors_own_signature_is_rejected_on_size(self):
        """687 by 195, and the reason reported is the first floor it fails."""
        pdf = as_pdf_bytes(paper_form_lines(ApplicationSpec()), images=[signature_strip(687, 195)])

        parsed = parse_application_document(pdf, "application/pdf")

        assert parsed.artwork_images_found == 0
        assert [image.reason for image in parsed.artwork_images_rejected] == ["short_edge"]

    def test_the_same_signature_scanned_larger_is_rejected_on_shape(self):
        """The case no absolute floor catches, asserted against both of them.

        Both size floors are asserted to pass here rather than assumed to, so
        that this test cannot quietly start passing for the wrong reason if
        somebody raises one of them.
        """
        width, height = 2000, 580
        assert min(width, height) >= settings.min_artwork_edge_px
        assert width * height >= settings.min_artwork_pixels

        pdf = as_pdf_bytes(
            paper_form_lines(ApplicationSpec()), images=[signature_strip(width, height)]
        )

        parsed = parse_application_document(pdf, "application/pdf")

        assert parsed.artwork_images_found == 0
        assert [image.reason for image in parsed.artwork_images_rejected] == ["aspect_ratio"]

    def test_a_rejection_carries_no_trace_of_the_picture(self):
        """NFR-6. The page, the size, the reason, and nothing else.

        Asserted on the fields of the record rather than on one instance,
        because the thing being prevented is somebody adding the bytes to it
        later for debugging and shipping it.
        """
        pdf = as_pdf_bytes(paper_form_lines(ApplicationSpec()), images=[signature_strip(2000, 580)])

        parsed = parse_application_document(pdf, "application/pdf")
        rejected = parsed.artwork_images_rejected[0]

        assert {field.name for field in fields(rejected)} == {"page", "width", "height", "reason"}
        assert rejected.page == 2


@requires_tesseract
@requires_fonts
class TestTheArtworkIsChosenOverTheSignature:
    """The author's document, in the shape it actually has.

    Page 1 is the form, page 2 carries the signature, page 3 carries the label
    artwork. The artwork is what the check has to run on, and the response has
    to say so: which page it came from, what else was in the file, and why each
    of those was not used.
    """

    def test_the_artwork_is_read_and_the_signature_is_not(self, label_artwork):
        pdf = as_pdf_bytes(
            paper_form_lines(ApplicationSpec()),
            images=[signature_strip(2000, 580), label_artwork],
        )

        parsed = parse_application_document(pdf, "application/pdf")

        assert parsed.artwork_images_found == 1
        assert parsed.artwork_images_read == 1
        assert parsed.label_artwork is not None
        assert parsed.label_artwork.page == 3
        assert [image.reason for image in parsed.artwork_images_rejected] == ["aspect_ratio"]

    def test_the_values_come_off_the_artwork_and_not_off_the_signature(self, label_artwork):
        """The failure this prevents, stated as the values it would corrupt.

        OCR of a signature returns short garbage of the same shape as the
        "AMoviy TS" the deployed build reported for a brand name. A pipeline
        that reads it is one bad sort order away from filling a compliance
        field with somebody's handwriting.
        """
        pdf = as_pdf_bytes(
            paper_form_lines(ApplicationSpec()),
            images=[signature_strip(2000, 580), label_artwork],
        )

        parsed = parse_application_document(pdf, "application/pdf")

        assert parsed.values["alcohol_content"] == "45% Alc./Vol. (90 Proof)"
        assert parsed.values["net_contents"] == "750 mL"

    def test_the_response_says_which_page_the_label_came_from(self, label_artwork):
        """An agent reading a poor result has to know which picture was read."""
        pdf = as_pdf_bytes(
            paper_form_lines(ApplicationSpec()),
            images=[signature_strip(2000, 580), label_artwork],
        )

        document = document_result(parse_application_document(pdf, "application/pdf"))

        assert document.label_artwork_page == 3
        assert [image.reason for image in document.artwork_images_rejected] == ["aspect_ratio"]
        assert [image.page for image in document.artwork_images_rejected] == [2]


@requires_tesseract
@requires_fonts
class TestADocumentWithNoPictures:
    """A document carrying no images behaves exactly as v1.0.1 did."""

    def test_the_paper_form_reads_the_same_as_it_always_did(self):
        pdf = as_pdf_bytes(paper_form_lines(ApplicationSpec()))

        parsed = parse_application_document(pdf, "application/pdf")

        assert parsed.values["brand_name"] == "STONE'S THROW"
        assert parsed.values["class_type"] is None
        assert parsed.values["alcohol_content"] is None
        assert parsed.values["net_contents"] is None
        assert parsed.fanciful_name == "Small Batch Reserve"
        assert parsed.path == "embedded_text"
        assert parsed.artwork_images_found == 0
        assert parsed.label_artwork is None
        # The absence notes are the whole of the v1.0.1 behaviour here: three of
        # the five values are not items on the form, and the agent is told why.
        assert any("alcohol content is not an item" in note for note in parsed.notes)
        assert SELF_CONSISTENCY_NOTE not in parsed.notes

    def test_the_registry_printout_reads_the_same_as_it_always_did(self):
        spec = ApplicationSpec(
            class_type="Kentucky Straight Bourbon Whiskey",
            class_type_code="141",
            alcohol_content="45% Alc./Vol.",
            net_contents="750 mL",
        )

        parsed = parse_application_document(
            as_pdf_bytes(registry_printout_lines(spec)), "application/pdf"
        )

        assert parsed.values["class_type"] == "Kentucky Straight Bourbon Whiskey"
        assert parsed.class_type_code == "141"
        assert parsed.values["alcohol_content"] == "45% Alc./Vol."
        assert parsed.artwork_images_found == 0
        assert SELF_CONSISTENCY_NOTE not in parsed.notes


@requires_tesseract
@requires_fonts
class TestAnApplicationDocumentOnTheApiWithNoPhotograph:
    """The whole point of ADR 0010: one file, and the check still runs.

    The agent's words on 2026-08-29 were "if COLA is uploaded, I don't also need
    an image". These are the end-to-end assertions behind that.
    """

    def post(self, document: bytes, image: bytes | None = None):
        from fastapi.testclient import TestClient

        from app.main import app

        files = [("application_document", ("application.pdf", document, "application/pdf"))]
        if image is not None:
            files.append(("image", ("label.png", image, "image/png")))
        return TestClient(app).post("/api/verify", files=files)

    def test_the_check_runs_from_the_application_alone(self, label_artwork):
        """All five compared fields get an outcome, from one uploaded file."""
        pdf = as_pdf_bytes(paper_form_lines(ApplicationSpec()), images=[label_artwork])

        response = self.post(pdf)

        assert response.status_code == 200, response.text
        body = response.json()
        assert {entry["name"] for entry in body["fields"]} == {
            "brand_name",
            "class_type",
            "alcohol_content",
            "net_contents",
            "government_warning",
        }
        # Nothing was compared against nothing: every compared field has an
        # application value that came from somewhere in the document.
        for name in ("brand_name", "class_type", "alcohol_content", "net_contents"):
            entry = next(item for item in body["fields"] if item["name"] == name)
            assert entry["application_value"], f"{name} should have an application value"
            assert entry["application_value_source"] in (
                "parsed_from_form",
                "parsed_from_artwork",
            )
        warning = next(item for item in body["fields"] if item["name"] == "government_warning")
        assert warning["found_on_label"] is True

    def test_the_response_says_the_label_came_out_of_the_application(self, label_artwork):
        """The self-consistency limitation, in the response (ADR 0010)."""
        pdf = as_pdf_bytes(paper_form_lines(ApplicationSpec()), images=[label_artwork])

        body = self.post(pdf).json()

        assert body["label_source"] == "application_artwork"
        assert body["self_consistency_note"] == SELF_CONSISTENCY_NOTE
        assert [photo["origin"] for photo in body["photos"]] == ["application_artwork"]
        assert body["application_document"]["label_artwork_available"] is True
        assert body["application_document"]["artwork_images_read"] == 1

    def test_a_photograph_the_agent_supplied_wins_over_the_artwork(
        self, label_artwork, sample_label_png
    ):
        """Evidence about the bottle in front of the agent beats the file's copy."""
        pdf = as_pdf_bytes(paper_form_lines(ApplicationSpec()), images=[label_artwork])

        body = self.post(pdf, image=sample_label_png).json()

        assert body["label_source"] == "uploaded_photographs"
        assert body["self_consistency_note"] is None
        assert [photo["origin"] for photo in body["photos"]] == ["uploaded"]

    def test_an_application_with_no_readable_artwork_names_the_missing_piece(self):
        """FR-9's shape: say what is missing, do not report a field outcome."""
        pdf = as_pdf_bytes(paper_form_lines(ApplicationSpec()), images=[solid_png(200, 200)])

        response = self.post(pdf)

        assert response.status_code == 422
        body = response.json()
        assert body["error"]["code"] == "no_label_to_check"
        assert "image of the label" in body["error"]["message"]
        assert "fields" not in body
