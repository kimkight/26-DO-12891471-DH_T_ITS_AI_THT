"""End to end over POST /api/verify with real OCR against rendered artwork.

Covers docs/07_TEST_STRATEGY.md section 2 and UAT rows 1, 3, 7, 8 and 11.
Requirements: FR-1, FR-2, FR-3, FR-5, FR-6, FR-7, NFR-1, NFR-3.

The label is rendered with Pillow at test time rather than committed as a file,
because samples/README.md keeps label artwork out of the repository. The
latency figure this test prints is one measurement on one machine and is not a
published number; scripts/measure.py produces the reported set.
"""

import time

from fastapi.testclient import TestClient
from samples.specs import SAMPLE_LABEL, TITLE_CASE_WARNING

from app.main import app
from tests.conftest import requires_fonts, requires_tesseract

client = TestClient(app)

FIVE_SECOND_TARGET = 5.0

pytestmark = [requires_tesseract, requires_fonts]


def verify(png: bytes, application: dict[str, str]):
    return client.post(
        "/api/verify",
        files={"image": ("label.png", png, "image/png")},
        data=application,
    )


class TestCleanLabel:
    def test_all_five_fields_return_and_the_request_is_under_five_seconds(
        self, sample_label_png, capsys
    ):
        """UAT rows 1 and 11, measured rather than asserted (NFR-1)."""
        started = time.perf_counter()
        response = verify(sample_label_png, SAMPLE_LABEL.application)
        elapsed = time.perf_counter() - started

        assert response.status_code == 200, response.text
        body = response.json()
        names = [field["name"] for field in body["fields"]]
        assert names == [
            "brand_name",
            "class_type",
            "alcohol_content",
            "net_contents",
            "government_warning",
        ]
        for field in body["fields"]:
            assert field["outcome"] in {"match", "needs_review", "mismatch", "not_compared"}

        with capsys.disabled():
            print(
                f"\nMeasured single-label verification: {elapsed:.2f} s end to end "
                f"({body['ocr_ms']:.0f} ms of it in decode, preprocessing and OCR; "
                f"mean OCR confidence {body['ocr_confidence']:.1f}). "
                f"Target is about {FIVE_SECOND_TARGET:.0f} s (NFR-1). "
                "Measured on this runner, not on production hardware."
            )
        assert elapsed < FIVE_SECOND_TARGET

    def test_the_default_path_reports_that_no_external_call_was_made(self, sample_label_png):
        """NFR-3: the response says whether a result involved an external call."""
        body = verify(sample_label_png, SAMPLE_LABEL.application).json()
        assert body["external_call_made"] is False

    def test_the_sample_labels_numeric_fields_match_the_application(self, sample_label_png):
        """UAT rows 7, 8 and 20: 45% Alc./Vol. (90 Proof) against 45, and 750 mL."""
        body = verify(sample_label_png, SAMPLE_LABEL.application).json()
        outcomes = {field["name"]: field["outcome"] for field in body["fields"]}
        assert outcomes["alcohol_content"] == "match"
        assert outcomes["net_contents"] == "match"

    def test_the_brand_name_never_hard_mismatches_on_a_case_difference(self, sample_label_png):
        """UAT row 2, through the full pipeline rather than the comparison alone."""
        body = verify(sample_label_png, SAMPLE_LABEL.application).json()
        outcomes = {field["name"]: field["outcome"] for field in body["fields"]}
        assert outcomes["brand_name"] != "mismatch"

    def test_a_correct_warning_matches_and_never_claims_bold_was_checked(self, sample_label_png):
        """UAT row 15."""
        body = verify(sample_label_png, SAMPLE_LABEL.application).json()
        detail = body["warning_detail"]
        assert detail["statement_found"] is True
        assert detail["bold_type_checked"] is False
        assert "not checked" in detail["bold_type_note"]


class TestTitleCaseWarning:
    def test_a_title_case_warning_fails_capitalization_and_names_the_reason(self, label_png):
        """UAT row 3, end to end."""
        png = label_png(warning=TITLE_CASE_WARNING)
        body = verify(png, SAMPLE_LABEL.application).json()
        warning = next(f for f in body["fields"] if f["name"] == "government_warning")
        assert body["warning_detail"]["prefix_is_capitalized"] is False
        assert warning["outcome"] != "match"
        assert "apitalization" in warning["reason"]


class TestNothingIsPersisted:
    def test_two_identical_requests_share_no_state(self, sample_label_png):
        """NFR-6: nothing is retained between requests, so results are identical."""
        first = verify(sample_label_png, SAMPLE_LABEL.application).json()
        second = verify(sample_label_png, SAMPLE_LABEL.application).json()
        assert [f["outcome"] for f in first["fields"]] == [f["outcome"] for f in second["fields"]]
