"""``POST /api/classify`` is timed, and a scan is not read there (NFR-1, ADR 0024).

A three-page filing with no text layer measured 10322 ms in this request on
the deployed v1.5.0 build, before the agent had clicked anything, and nothing
showed it: the route logged counts only, with the comment "NFR-6: counts
only". A duration is a number about the request, not a word of its content,
so it is logged and returned now, in the same shape ``POST /api/verify`` uses.

And the ten seconds are gone from this request, for the reason ADR 0017 took
the artwork out of it: the check renders and reads the same pages a moment
later. The prefill pass reports ``extraction_path: "not_read"`` on such a
file, the interface treats every value as on its way, and the check reads the
pages once, under the read budget of ADR 0023.

Fixtures are rendered at test time (docs/07_TEST_STRATEGY.md section 8).
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

from app.main import app  # noqa: E402
from tests.conftest import requires_fonts, requires_tesseract  # noqa: E402
from tests.test_logging import json_log, records  # noqa: E402, F401

client = TestClient(app)


def classify(pdf: bytes, name: str = "cola.pdf") -> dict:
    response = client.post("/api/classify", files=[("files", (name, pdf, "application/pdf"))])
    assert response.status_code == 200, response.text
    return response.json()


def verify(pdf: bytes) -> dict:
    response = client.post("/api/verify", files=[("files", ("cola.pdf", pdf, "application/pdf"))])
    assert response.status_code == 200, response.text
    return response.json()


@pytest.fixture(scope="module")
def with_text_layer() -> bytes:
    return as_pdf_bytes(
        paper_form_lines(ApplicationSpec()), images=[render_png_bytes(SAMPLE_LABEL)]
    )


@pytest.fixture(scope="module")
def scan() -> bytes:
    png = as_png_bytes(paper_form_lines(ApplicationSpec()))
    if png is None:
        pytest.skip("no TrueType font available")
    return as_scanned_pdf_bytes(png)


@requires_fonts
class TestTheDurationIsMeasured:
    def test_the_response_carries_elapsed_ms_and_the_phases(self, with_text_layer):
        body = classify(with_text_layer)

        assert body["elapsed_ms"] > 0
        timings = body["timings"]
        assert timings["total_ms"] == body["elapsed_ms"]
        # The prefill pass on a text-layer document is PDFium and nothing else.
        assert timings["document_pdfium_ms"] > 0
        assert timings["tesseract_reads"] == 0
        assert timings["unaccounted_ms"] >= 0

    def test_the_log_line_carries_the_duration_and_still_no_content(
        self,
        with_text_layer,
        json_log,  # noqa: F811
    ):
        classify(with_text_layer, name="applicant-private.pdf")

        lines = [r for r in records(json_log) if r["message"] == "uploads classified"]
        assert len(lines) == 1
        assert isinstance(lines[0]["elapsed_ms"], float)
        assert lines[0]["elapsed_ms"] > 0
        assert lines[0]["tesseract_reads"] == 0
        assert lines[0]["application_document_path"] == "embedded_text"
        written = json_log.getvalue()
        assert "applicant-private" not in written
        assert ApplicationSpec().brand_name not in written


@requires_tesseract
@requires_fonts
class TestAScanIsNotReadOnThePrefillPass:
    """The ten seconds, and where they went."""

    def test_the_prefill_pass_counts_the_pages_and_reads_none(self, scan):
        body = classify(scan)

        document = body["application_document"]
        assert body["application_error"] is None
        assert document["extraction_path"] == "not_read"
        assert document["pages_read"] == 0
        assert document["pages_not_reached"] == 1
        assert document["artwork_read"] is False
        assert all(entry["found_on_document"] is False for entry in document["fields"])
        assert body["timings"]["tesseract_reads"] == 0
        assert body["timings"]["page_ocr_ms"] == 0.0
        assert any("no text to read" in note for note in document["notes"])

    def test_the_check_reads_the_pages_once_and_fills_the_values(self, scan):
        body = verify(scan)

        document = body["application_document"]
        assert document["extraction_path"] == "ocr"
        assert document["pages_read"] == 1
        assert document["pages_not_reached"] == 0
        brand = next(entry for entry in document["fields"] if entry["name"] == "brand_name")
        assert brand["found_on_document"] is True
        assert body["timings"]["page_ocr_ms"] > 0
        assert document["tesseract_reads"] == body["timings"]["tesseract_reads"]

    def test_read_application_still_reads_everything(self, scan):
        """The FR-11 route has no check behind it, so it reads the pages."""
        response = client.post(
            "/api/read-application",
            files=[("application_document", ("scan.pdf", scan, "application/pdf"))],
        )
        assert response.status_code == 200, response.text
        document = response.json()
        assert document["extraction_path"] == "ocr"
        assert document["pages_read"] == 1
