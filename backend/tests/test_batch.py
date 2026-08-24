"""Batch verification over POST /api/verify-batch.

Covers FR-8 (every label returns a result, one unreadable image errors that row
only, an over-count batch is refused before anything is processed, every line
identifies its label, and CSV mismatches are reported), FR-9 (a per-row error
names the problem and reports no match), NFR-2 (the batch does not fail as a
whole and its progress is observable), NFR-6 (nothing is persisted), and
NFR-7 (the file count is checked before processing).

Stories: US-9, US-10, US-11. Decision reference: ADR 0006, assumption A-14.

The tiers are kept apart deliberately, following docs/07_TEST_STRATEGY.md
section 1. The reconciliation and refusal tests need no Tesseract, because every
one of them either rejects before decoding or fails to decode. The tests that
read real artwork carry the integration markers.
"""

from __future__ import annotations

import csv
import io
import json
import time

import pytest
from fastapi.testclient import TestClient
from samples.specs import SAMPLE_LABEL, SPECS

from app.batch import REQUIRED_COLUMNS
from app.config import settings
from app.main import app
from tests.conftest import requires_fonts, requires_tesseract

client = TestClient(app)

CORRUPT_IMAGE = b"this is not an image"


def application_csv(rows: list[dict[str, str]], columns=REQUIRED_COLUMNS) -> bytes:
    """Build an A-14 CSV. Written out rather than fixtured so each test's CSV is
    visible in the test that depends on it."""
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=list(columns))
    writer.writeheader()
    writer.writerows(rows)
    return buffer.getvalue().encode("utf-8")


def row_for(filename: str, spec=SAMPLE_LABEL) -> dict[str, str]:
    return {"filename": filename, **spec.application}


def submit(images: list[tuple[str, bytes]], csv_bytes: bytes, csv_name="applications.csv"):
    files = [("images", (name, content, "image/png")) for name, content in images]
    files.append(("applications", (csv_name, csv_bytes, "text/csv")))
    return client.post("/api/verify-batch", files=files)


def lines(response) -> list[dict]:
    """Parse the NDJSON body. Asserts the framing as it goes: one object per
    line is the contract ADR 0006 states, and a client that has to guess where a
    record ends cannot render progress."""
    assert response.headers["content-type"].startswith("application/x-ndjson")
    parsed = []
    for raw in response.text.splitlines():
        assert raw, "no blank lines: every line is one record"
        parsed.append(json.loads(raw))
    return parsed


class TestOverCount:
    """FR-8's third criterion and NFR-7's third."""

    def test_a_batch_over_the_limit_is_refused_and_the_message_names_the_limit(self, monkeypatch):
        monkeypatch.setattr(settings, "max_batch_files", 2)
        images = [(f"{index}.png", CORRUPT_IMAGE) for index in range(3)]
        response = submit(images, application_csv([row_for(name) for name, _ in images]))

        assert response.status_code == 413
        body = response.json()
        assert body["error"]["code"] == "batch_too_large"
        assert "2" in body["error"]["limit"]
        # Refused before processing: no result set for any label, and in
        # particular no field outcomes at all (FR-9's last criterion).
        assert "fields" not in response.text
        assert "match" not in response.text

    def test_a_batch_at_the_limit_is_accepted(self, monkeypatch):
        monkeypatch.setattr(settings, "max_batch_files", 2)
        images = [(f"{index}.png", CORRUPT_IMAGE) for index in range(2)]
        response = submit(images, application_csv([row_for(name) for name, _ in images]))
        assert response.status_code == 200
        assert len(lines(response)) == 2


class TestEveryLineIdentifiesItsLabel:
    """FR-8's fourth criterion, and the fields NFR-2 needs for progress."""

    def test_each_line_names_its_image_and_carries_its_position(self):
        images = [(f"{index:02d}.png", CORRUPT_IMAGE) for index in range(4)]
        response = submit(images, application_csv([row_for(name) for name, _ in images]))

        assert response.status_code == 200
        received = lines(response)
        assert len(received) == 4
        assert {line["filename"] for line in received} == {name for name, _ in images}
        # Position and total are what let a client render "3 of 4" from the
        # first line it receives, without counting parts itself (NFR-2).
        assert sorted(line["index"] for line in received) == [1, 2, 3, 4]
        assert {line["total"] for line in received} == {4}

    def test_a_part_with_no_filename_is_refused_in_the_documented_shape(self):
        """A part sent without a filename is not an upload at all: the multipart
        parser hands it over as a form field, so it never reaches the route. The
        rejection still has to name the problem in one shape (FR-9)."""
        files = [
            ("images", ("", CORRUPT_IMAGE, "image/png")),
            ("applications", ("a.csv", application_csv([row_for("a.png")]), "text/csv")),
        ]
        response = client.post("/api/verify-batch", files=files)

        assert response.status_code == 422
        error = response.json()["error"]
        assert error["code"] == "invalid_submission"
        assert "images" in error["message"]
        assert "fields" not in response.text

    def test_a_batch_with_no_application_csv_is_refused_in_the_documented_shape(self):
        files = [("images", ("a.png", CORRUPT_IMAGE, "image/png"))]
        response = client.post("/api/verify-batch", files=files)

        assert response.status_code == 422
        error = response.json()["error"]
        assert error["code"] == "invalid_submission"
        assert "applications" in error["message"]


class TestOneBadImageDoesNotFailTheBatch:
    """US-10, FR-8's second criterion, FR-9 applied per row."""

    @requires_tesseract
    @requires_fonts
    def test_a_batch_of_three_with_one_corrupt_image_returns_two_results_and_one_error(
        self, sample_label_png
    ):
        images = [
            ("good-1.png", sample_label_png),
            ("corrupt.png", CORRUPT_IMAGE),
            ("good-2.png", sample_label_png),
        ]
        response = submit(images, application_csv([row_for(name) for name, _ in images]))

        assert response.status_code == 200
        received = {line["filename"]: line for line in lines(response)}
        assert set(received) == {"good-1.png", "corrupt.png", "good-2.png"}

        bad = received["corrupt.png"]
        assert bad["status"] == "error"
        assert bad["error"]["code"] == "unreadable_image"
        assert bad["result"] is None, "an error line reports no field outcomes (FR-9)"

        for name in ("good-1.png", "good-2.png"):
            line = received[name]
            assert line["status"] == "ok", line
            assert line["error"] is None
            assert [field["name"] for field in line["result"]["fields"]] == [
                "brand_name",
                "class_type",
                "alcohol_content",
                "net_contents",
                "government_warning",
            ]

    def test_a_disallowed_type_inside_a_batch_errors_that_row_only(self):
        files = [
            ("images", ("ok.png", CORRUPT_IMAGE, "image/png")),
            ("images", ("notes.pdf", b"%PDF-1.4", "application/pdf")),
            (
                "applications",
                (
                    "a.csv",
                    application_csv([row_for("ok.png"), row_for("notes.pdf")]),
                    "text/csv",
                ),
            ),
        ]
        response = client.post("/api/verify-batch", files=files)
        assert response.status_code == 200
        received = {line["filename"]: line for line in lines(response)}
        assert received["notes.pdf"]["error"]["code"] == "unsupported_media_type"
        assert "image/png" in received["notes.pdf"]["error"]["limit"]
        # The other row still ran, and failed on its own terms rather than on
        # the neighbouring row's.
        assert received["ok.png"]["error"]["code"] == "unreadable_image"

    def test_an_oversize_image_inside_a_batch_errors_that_row_only(self, monkeypatch):
        monkeypatch.setattr(settings, "max_upload_bytes", 32)
        images = [("small.png", CORRUPT_IMAGE), ("big.png", b"x" * 64)]
        response = submit(images, application_csv([row_for(name) for name, _ in images]))

        assert response.status_code == 200
        received = {line["filename"]: line for line in lines(response)}
        assert received["big.png"]["error"]["code"] == "file_too_large"
        assert "32" in received["big.png"]["error"]["limit"]
        assert received["small.png"]["error"]["code"] == "unreadable_image"


class TestCsvReconciliation:
    """FR-8's sixth criterion: an unmatched row, a missing row and a duplicate
    row each produce an error that names the problem, and the rest still runs."""

    def test_a_csv_row_referencing_a_missing_file_errors_on_its_own_line(self):
        response = submit(
            [("present.png", CORRUPT_IMAGE)],
            application_csv([row_for("present.png"), row_for("absent.png")]),
        )

        assert response.status_code == 200
        received = {line["filename"]: line for line in lines(response)}
        assert set(received) == {"present.png", "absent.png"}

        missing = received["absent.png"]
        assert missing["status"] == "error"
        assert missing["error"]["code"] == "unmatched_application_row"
        assert "absent.png" in missing["error"]["message"]
        assert missing["result"] is None
        # The image that was submitted still got its own line.
        assert received["present.png"]["error"]["code"] == "unreadable_image"

    def test_an_image_with_no_csv_row_errors_on_its_own_line(self):
        response = submit(
            [("listed.png", CORRUPT_IMAGE), ("unlisted.png", CORRUPT_IMAGE)],
            application_csv([row_for("listed.png")]),
        )

        received = {line["filename"]: line for line in lines(response)}
        assert received["unlisted.png"]["error"]["code"] == "missing_application_row"
        assert "unlisted.png" in received["unlisted.png"]["error"]["message"]
        assert received["listed.png"]["error"]["code"] == "unreadable_image"

    def test_a_duplicated_csv_filename_errors_that_row_and_leaves_the_others(self):
        response = submit(
            [("twice.png", CORRUPT_IMAGE), ("once.png", CORRUPT_IMAGE)],
            application_csv([row_for("twice.png"), row_for("twice.png"), row_for("once.png")]),
        )

        received = {line["filename"]: line for line in lines(response)}
        assert received["twice.png"]["error"]["code"] == "duplicate_application_row"
        assert "twice.png" in received["twice.png"]["error"]["message"]
        assert received["once.png"]["error"]["code"] == "unreadable_image"

    def test_two_images_submitted_under_one_filename_stay_distinguishable(self):
        files = [
            ("images", ("same.png", CORRUPT_IMAGE, "image/png")),
            ("images", ("same.png", CORRUPT_IMAGE, "image/png")),
            ("applications", ("a.csv", application_csv([row_for("same.png")]), "text/csv")),
        ]
        response = client.post("/api/verify-batch", files=files)

        received = lines(response)
        assert len(received) == 2
        assert len({line["filename"] for line in received}) == 2, (
            "FR-8 requires each result to identify which label it belongs to, "
            "so two parts cannot both report under one name"
        )


class TestUnusableCsv:
    """The batch-level half of FR-8's error criterion."""

    def test_a_csv_missing_a_required_column_is_refused_and_the_column_is_named(self):
        columns = [column for column in REQUIRED_COLUMNS if column != "alcohol_content"]
        body = application_csv([dict.fromkeys(columns, "x")], columns=columns)
        response = submit([("a.png", CORRUPT_IMAGE)], body)

        assert response.status_code == 422
        error = response.json()["error"]
        assert error["code"] == "invalid_application_csv"
        assert "alcohol_content" in error["message"]
        assert "fields" not in response.text

    def test_an_empty_csv_is_refused(self):
        response = submit([("a.png", CORRUPT_IMAGE)], b"")
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "invalid_application_csv"

    def test_a_csv_that_is_not_utf8_is_refused_with_a_message_an_agent_can_act_on(self):
        body = application_csv([row_for("a.png")]).replace(b"Stone", b"St\xffne")
        response = submit([("a.png", CORRUPT_IMAGE)], body)
        assert response.status_code == 422
        assert "UTF-8" in response.json()["error"]["message"]

    def test_a_header_only_csv_is_refused(self):
        response = submit([("a.png", CORRUPT_IMAGE)], application_csv([]))
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "invalid_application_csv"

    def test_a_batch_with_no_images_is_refused(self):
        files = [("applications", ("a.csv", application_csv([row_for("a.png")]), "text/csv"))]
        response = client.post("/api/verify-batch", files=files)
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "empty_batch"

    def test_the_csv_header_is_read_case_insensitively_and_ignores_surrounding_space(self):
        columns = [f" {column.upper()} " for column in REQUIRED_COLUMNS]
        values = ["a.png", "Stone's Throw", "Bourbon", "45", "750 mL", "spirits"]
        rows = [dict(zip(columns, values, strict=True))]
        response = submit([("a.png", CORRUPT_IMAGE)], application_csv(rows, columns=columns))

        assert response.status_code == 200
        assert lines(response)[0]["error"]["code"] == "unreadable_image"


class TestNothingIsPersisted:
    """NFR-6, asserted against the batch path as well as the single one."""

    def test_no_field_value_or_filename_reaches_the_logs(self, caplog):
        caplog.set_level("INFO")
        submit(
            [("secret-brand.png", CORRUPT_IMAGE)],
            application_csv([row_for("secret-brand.png")]),
        )
        logged = "\n".join(record.getMessage() for record in caplog.records)
        assert "secret-brand" not in logged
        assert "Stone's Throw" not in logged


@requires_tesseract
@requires_fonts
class TestTheGeneratedSampleSet:
    """A full run over the twelve-label set, which is case 7 in samples/README.md
    and the one case that needed FR-8 to exist before it could be exercised."""

    def test_every_one_of_the_twelve_labels_returns_a_line(self, label_png, capsys):
        images = [(spec.filename, label_png(**spec.__dict__)) for spec in SPECS]
        body = application_csv([{"filename": spec.filename, **spec.application} for spec in SPECS])

        started = time.perf_counter()
        response = submit(images, body)
        elapsed = time.perf_counter() - started

        assert response.status_code == 200
        received = lines(response)
        assert len(received) == len(SPECS)
        assert {line["filename"] for line in received} == {spec.filename for spec in SPECS}
        assert all(line["status"] == "ok" for line in received), [
            line for line in received if line["status"] != "ok"
        ]
        for line in received:
            assert len(line["result"]["fields"]) == 5
            assert line["result"]["external_call_made"] is False, "NFR-3"

        with capsys.disabled():
            print(
                f"\nBatch of {len(SPECS)} labels: {elapsed:.2f} s wall clock on "
                f"{settings.effective_batch_workers} workers "
                f"({elapsed / len(SPECS):.2f} s per label). Measured on this "
                "runner, not on production hardware. No batch latency target "
                "exists (OQ-6)."
            )


@pytest.mark.parametrize("workers", [1, 4])
def test_the_worker_pool_bound_is_honoured_and_every_line_still_returns(monkeypatch, workers):
    """ADR 0006 bounds concurrency so that a 300-file batch does not start 300
    Tesseract processes at once. The bound must not change what comes back."""
    monkeypatch.setattr(settings, "batch_workers", workers)
    assert settings.effective_batch_workers == workers

    images = [(f"{index:02d}.png", CORRUPT_IMAGE) for index in range(8)]
    response = submit(images, application_csv([row_for(name) for name, _ in images]))

    received = lines(response)
    assert len(received) == 8
    assert {line["filename"] for line in received} == {name for name, _ in images}
