"""A picture lifted out of a PDF is turned the way the page places it.

[ADR 0025](../../docs/adr/0025-orientation-from-the-placement.md), NFR-1, FR-1.

The orientation call exists for a photograph, which says nothing about which
way up it is beyond an EXIF tag that may lie. A picture inside a PDF says
exactly which way up it is: the placement matrix the page draws it with,
composed with the page's own ``/Rotate``. On the two real filings in
samples/real/ every one of the eight pictures is placed upright, and the
orientation call that was made on each of them bought no turn on any: it was
wrong on two, unable to answer on three, and right on one, for seven of the
bourbon's nineteen reads. So the turn is taken from the file, reported as
``placement``, and Tesseract is not asked.

Two things are asserted here and they are different claims. That the turn
read off the matrix is the turn the page shows is not argued from PDF sign
conventions; it is checked against PDFium's own render of the page, for every
quarter-turn composed with every page rotation. And that a picture the page
turns is read whole with no orientation call, while a picture the page slants
is left to Tesseract as before.

Fixtures are rendered at test time; no real applicant data appears here
(docs/07_TEST_STRATEGY.md section 8). Nothing reads samples/real/.
"""

from __future__ import annotations

import io
import sys
from pathlib import Path

import cv2
import numpy as np
import pypdfium2 as pdfium
import pytest
from fastapi.testclient import TestClient
from PIL import Image

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from samples.formmaker import ApplicationSpec, as_pdf_bytes, paper_form_lines  # noqa: E402
from samples.labelmaker import render_png_bytes  # noqa: E402
from samples.specs import SAMPLE_LABEL  # noqa: E402

from app import timing  # noqa: E402
from app.application_form import (  # noqa: E402
    _placement_rotation,
    _read_pdf_with_pdfium,
    parse_application_document,
)
from app.main import app  # noqa: E402
from app.ocr import (  # noqa: E402
    CARDINAL_ROTATIONS,
    decode,
    extract_text,
    preprocess,
    rotate_cardinal,
)
from tests.conftest import png_bytes, requires_fonts, requires_tesseract  # noqa: E402

client = TestClient(app)

# The four values the sample label prints, as the parser reports them. Read
# whole means every one of these comes back, whichever way the file stored the
# picture.
EXPECTED_VALUES = {
    "brand_name": "STONE'S THROW",
    "class_type": "Kentucky Straight Bourbon Whiskey",
    "alcohol_content": "45% Alc./Vol. (90 Proof)",
    "net_contents": "750 mL",
}


def filing(picture: bytes, **placement) -> bytes:
    """The paper form with one picture affixed, placed as the caller says."""
    return as_pdf_bytes(paper_form_lines(ApplicationSpec()), images=[picture], **placement)


def stored_turned(label_png: bytes, clockwise_degrees: int) -> bytes:
    """The label's pixels stored turned in the file, as PNG bytes."""
    pixels = decode(label_png).pixels
    turned = rotate_cardinal(pixels, clockwise_degrees)
    return png_bytes(Image.fromarray(cv2.cvtColor(turned, cv2.COLOR_BGR2RGB)))


@pytest.fixture(scope="module")
def label() -> bytes:
    """The sample label, rendered once for the module."""
    return render_png_bytes(SAMPLE_LABEL)


class _Matrix:
    def __init__(self, values):
        self._values = values

    def get(self):
        return self._values


class _Image:
    def __init__(self, matrix):
        self._matrix = matrix

    def get_matrix(self):
        if isinstance(self._matrix, Exception):
            raise self._matrix
        return _Matrix(self._matrix)


class _Page:
    def __init__(self, rotation: int = 0):
        self._rotation = rotation

    def get_rotation(self):
        return self._rotation


class TestThePlacementIsReadFromTheMatrix:
    """Arithmetic on the six numbers, with no PDF and no engine.

    The matrix is ``(a, b, c, d, e, f)`` in PDF user space, y upward. A
    picture drawn turned counter-clockwise by an angle carries that angle's
    cosine and sine in both columns; the result is the clockwise quarter-turn
    that brings the stored raster to what the page shows, so a
    counter-clockwise placement of 90 comes back as 270.
    """

    @pytest.mark.parametrize(
        ("matrix", "expected"),
        [
            ((487.5, 0.0, 0.0, 216.0, 32.25, 214.5), 0),
            ((0.0, 500.0, -500.0, 0.0, 100.0, 100.0), 270),
            ((-500.0, 0.0, 0.0, -500.0, 100.0, 100.0), 180),
            ((0.0, -500.0, 500.0, 0.0, 100.0, 100.0), 90),
            # Unequal scales are still a quarter-turn.
            ((0.0, 300.0, -800.0, 0.0, 0.0, 0.0), 270),
            # Rounding in the writer's cos and sin is not a slant.
            ((0.0000001, 500.0, -500.0, 0.0000001, 0.0, 0.0), 270),
        ],
    )
    def test_each_quarter_turn_is_read_as_the_clockwise_turn_that_undoes_it(self, matrix, expected):
        assert _placement_rotation(_Image(matrix), _Page()) == expected

    @pytest.mark.parametrize(
        ("matrix", "why"),
        [
            ((-500.0, 0.0, 0.0, 500.0, 0.0, 0.0), "mirrored, the determinant is negative"),
            ((0.0, 0.0, 0.0, 500.0, 0.0, 0.0), "degenerate, the determinant is zero"),
            ((492.4, 86.8, -86.8, 492.4, 0.0, 0.0), "a slant of ten degrees"),
            ((500.0, 0.0, 100.0, 500.0, 0.0, 0.0), "a skew, the two columns disagree"),
        ],
    )
    def test_anything_but_a_quarter_turn_is_left_to_tesseract(self, matrix, why):
        assert _placement_rotation(_Image(matrix), _Page()) is None, why

    def test_a_matrix_that_cannot_be_read_is_left_to_tesseract(self):
        assert _placement_rotation(_Image(RuntimeError("no matrix")), _Page()) is None

    @pytest.mark.parametrize("page_rotation", [0, 90, 180, 270])
    @pytest.mark.parametrize(
        ("matrix", "placement_turn"),
        [
            ((500.0, 0.0, 0.0, 500.0, 0.0, 0.0), 0),
            ((0.0, 500.0, -500.0, 0.0, 0.0, 0.0), 270),
        ],
    )
    def test_the_page_rotation_is_added_to_the_placement(
        self, matrix, placement_turn, page_rotation
    ):
        """``/Rotate`` is clockwise by the PDF's convention and is applied to
        the page after the picture is placed on it, so it adds."""
        expected = (placement_turn + page_rotation) % 360
        assert _placement_rotation(_Image(matrix), _Page(page_rotation)) == expected


@requires_fonts
class TestTheTurnIsTheOneThePageShows:
    """The sign conventions, checked against PDFium's render rather than argued.

    For every quarter-turn placement composed with every page rotation: the
    page is rendered the way a viewer shows it, the picture is lifted out the
    way the reader lifts it, and the raster turned by ``placement_rotation``
    has to be the one that matches the render. Sixteen cases, no engine.
    """

    @staticmethod
    def displayed(pdf: bytes) -> np.ndarray:
        """The picture page as PDFium renders it, cropped to its ink."""
        document = pdfium.PdfDocument(io.BytesIO(pdf))
        try:
            page = document[1]
            rendered = np.asarray(page.render(scale=1.0).to_pil().convert("L"))
            page.close()
        finally:
            document.close()
        rows, columns = np.where(rendered < 250)
        return rendered[rows.min() : rows.max() + 1, columns.min() : columns.max() + 1]

    @staticmethod
    def distance(candidate: np.ndarray, shown: np.ndarray) -> float:
        size = (256, 256)
        a = cv2.resize(candidate, size).astype(np.float32)
        b = cv2.resize(shown, size).astype(np.float32)
        return float(np.abs(a - b).mean())

    @pytest.mark.parametrize("page_rotate", [0, 90, 180, 270])
    @pytest.mark.parametrize("placement_degrees", [0, 90, 180, 270])
    def test_the_raster_turned_by_the_placement_is_what_the_page_shows(
        self, label, placement_degrees, page_rotate
    ):
        pdf = filing(label, image_placement_degrees=placement_degrees, page_rotate=page_rotate)
        artwork = _read_pdf_with_pdfium(pdf, render_pages=False).artwork[0]
        raster = np.asarray(Image.open(io.BytesIO(label)).convert("L"))
        shown = self.displayed(pdf)

        assert artwork.placement_rotation in CARDINAL_ROTATIONS
        distances = {
            turn: self.distance(rotate_cardinal(raster, turn), shown) for turn in CARDINAL_ROTATIONS
        }
        assert min(distances, key=distances.get) == artwork.placement_rotation, distances

    def test_a_slanted_placement_carries_no_turn(self, label):
        pdf = filing(label, image_placement_degrees=10)
        artwork = _read_pdf_with_pdfium(pdf, render_pages=False).artwork[0]
        assert artwork.placement_rotation is None

    def test_an_upright_placement_carries_zero(self, label):
        pdf = filing(label)
        artwork = _read_pdf_with_pdfium(pdf, render_pages=False).artwork[0]
        assert artwork.placement_rotation == 0


@requires_tesseract
@requires_fonts
class TestAPlacedPictureMakesNoOrientationCall:
    """The reads, and what the response says about them."""

    def test_the_turn_is_applied_and_reported_and_costs_nothing(self, label):
        """The same pixels stored sideways and given the turn that undoes it
        read exactly as the upright file does, with no engine call spent on
        deciding which way up they are."""
        with timing.recording() as recorded:
            result = extract_text(stored_turned(label, 90), placement_rotation=270)

        assert result.orientation.method == "placement"
        assert result.orientation.rotation_degrees == 270
        assert result.orientation.confidence is None
        assert result.orientation.check is None
        for value in EXPECTED_VALUES.values():
            for word in value.split():
                assert word in result.text, (word, result.text)
        # One arm on the clean rendering and nothing else: the orientation
        # call is not made, and the count on the result agrees with the tally.
        assert result.tesseract_reads == recorded.tesseract_reads == 1

    def test_the_placement_is_applied_whatever_the_setting_says(self, label):
        """``TTB_CORRECT_ORIENTATION`` governs the OSD call. A placement turn is
        a fact about the file, costs nothing, and is applied either way."""
        result = extract_text(
            stored_turned(label, 180), placement_rotation=180, correct_orientation=False
        )
        assert result.orientation.method == "placement"
        assert result.orientation.rotation_degrees == 180
        assert "THROW" in result.text

    def test_a_placement_that_is_not_a_quarter_turn_is_refused(self, label):
        with pytest.raises(ValueError, match="quarter-turn"):
            preprocess(decode(label), placement_rotation=45)

    @pytest.mark.parametrize("stored_clockwise", [90, 180, 270])
    def test_a_filing_whose_page_turns_the_picture_is_read_whole(self, label, stored_clockwise):
        """The case a real filing has not yet shown: the raster stored on its
        side and the page drawing it upright. Read whole, one read."""
        # A picture stored turned clockwise by k is drawn upright by a placement
        # of k counter-clockwise, which is what the fixture writer takes.
        pdf = filing(
            stored_turned(label, stored_clockwise), image_placement_degrees=stored_clockwise
        )

        parsed = parse_application_document(pdf, "application/pdf")

        for name, value in EXPECTED_VALUES.items():
            assert parsed.values[name] == value
        assert parsed.tesseract_reads == 1

    def test_the_response_names_the_method(self, label):
        pdf = filing(stored_turned(label, 90), image_placement_degrees=90)

        response = client.post(
            "/api/verify", files=[("files", ("cola.pdf", pdf, "application/pdf"))]
        )

        assert response.status_code == 200, response.text
        body = response.json()
        orientation = body["photos"][0]["orientation"]
        assert orientation["method"] == "placement"
        assert orientation["rotation_degrees"] == 270
        assert orientation["confidence"] is None
        assert body["timings"]["tesseract_reads"] == 1
        assert body["timings"]["ocr_passes"] == 1

    def test_a_slanted_placement_is_left_to_tesseract(self, label):
        """No quarter-turn to take from the file, so the orientation call is
        made as it always was: one read for it, and the rest as before."""
        pdf = filing(label, image_placement_degrees=10)

        response = client.post(
            "/api/verify", files=[("files", ("cola.pdf", pdf, "application/pdf"))]
        )

        assert response.status_code == 200, response.text
        body = response.json()
        orientation = body["photos"][0]["orientation"]
        assert orientation["method"] != "placement"
        assert orientation["method"] in (
            "osd",
            "osd_180_check",
            "osd_180_check_full_resolution",
            "unavailable",
        )
        assert body["timings"]["tesseract_reads"] >= 2
