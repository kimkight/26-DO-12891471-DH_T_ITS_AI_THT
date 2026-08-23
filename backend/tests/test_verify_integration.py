"""End to end over POST /api/verify with real OCR against rendered artwork.

Covers docs/07_TEST_STRATEGY.md section 2 and UAT rows 1, 3, 7, 8 and 11.
Requirements: FR-1, FR-2, FR-3, FR-5, FR-6, FR-7, NFR-1, NFR-3.

The label is rendered with Pillow at test time rather than committed as a file,
because samples/README.md keeps label artwork out of the repository. The
latency figure this test prints is one measurement on one machine and is not a
published number; scripts/measure.py produces the reported set.
"""

import logging
import socket
import time

import pytest
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


class TestNothingSensitiveReachesTheLogs:
    """UAT row 17: inspect the logs after a verification (NFR-6)."""

    def test_no_extracted_or_application_value_appears_in_any_log_record(
        self, sample_label_png, caplog
    ):
        caplog.set_level(logging.DEBUG)
        response = verify(sample_label_png, SAMPLE_LABEL.application)
        assert response.status_code == 200

        logged = " ".join(record.getMessage() for record in caplog.records)
        logged += " " + " ".join(str(record.__dict__) for record in caplog.records)

        # Only values distinctive enough for a substring search to mean
        # something. "45" would match a timestamp or an object address and
        # report a leak that is not one; the fields it stands for are covered
        # by the allow-list assertion in the next test.
        candidates = [
            SAMPLE_LABEL.brand_name,
            SAMPLE_LABEL.class_type,
            SAMPLE_LABEL.alcohol_content,
            SAMPLE_LABEL.net_contents,
            *SAMPLE_LABEL.application.values(),
            "GOVERNMENT WARNING",
            "Surgeon General",
        ]
        forbidden = [value for value in candidates if value and len(value) >= 5]
        assert len(forbidden) >= 6, "the guard should be checking real values"
        for value in forbidden:
            assert value not in logged, f"{value!r} reached the logs"

    def test_the_completion_record_carries_counts_and_timings_only(self, sample_label_png, caplog):
        caplog.set_level(logging.INFO)
        verify(sample_label_png, SAMPLE_LABEL.application)
        completions = [r for r in caplog.records if r.getMessage() == "verification completed"]
        assert completions, "the verification should log that it completed"
        record = completions[0]
        assert isinstance(record.bytes_received, int)
        assert isinstance(record.ocr_ms, float)
        assert record.beverage_type_supplied is True

        # An allow-list rather than a search, because this is the one record the
        # verification path writes and NFR-6 is a statement about what may be in
        # it. A new field added here has to be added to this list deliberately.
        standard = set(logging.LogRecord("", 0, "", 0, "", None, None).__dict__)
        added = set(record.__dict__) - standard - {"taskName", "asctime", "message"}
        assert added == {"bytes_received", "ocr_ms", "beverage_type_supplied"}


class TestEgressBlocked:
    """UAT row 16 and NFR-3: the default path completes with no network."""

    def test_verification_succeeds_when_every_socket_is_refused(
        self, sample_label_png, monkeypatch
    ):
        """Marcus Williams's constraint, asserted rather than assumed.

        The whole socket constructor is replaced, so any attempt to open a
        connection during the request raises rather than silently succeeding.
        The test client speaks to the app in process and does not use one.
        """

        real_socket = socket.socket

        class RefusedSocket(real_socket):
            def __init__(self, family=socket.AF_INET, *args, **kwargs):
                # AF_UNIX is left alone: asyncio builds its own self-pipe from a
                # Unix socketpair, so refusing that would break the event loop
                # rather than test the application. Only outbound IP sockets are
                # what NFR-3 is about.
                if family in (socket.AF_INET, socket.AF_INET6):
                    raise OSError("egress is blocked for this test")
                super().__init__(family, *args, **kwargs)

        def refuse_connection(*args, **kwargs):
            raise OSError("egress is blocked for this test")

        monkeypatch.setattr(socket, "socket", RefusedSocket)
        monkeypatch.setattr(socket, "create_connection", refuse_connection)

        # Prove the guard is live, so that a passing test cannot mean the patch
        # silently stopped working.
        with pytest.raises(OSError, match="egress is blocked"):
            socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        response = verify(sample_label_png, SAMPLE_LABEL.application)
        assert response.status_code == 200
        assert response.json()["external_call_made"] is False
