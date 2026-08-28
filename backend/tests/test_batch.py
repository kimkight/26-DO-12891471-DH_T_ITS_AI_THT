"""Batch verification over POST /api/verify-batch.

Covers FR-8 (every label returns a result, one unreadable image errors that row
only, an over-count batch is refused before anything is processed, every line
identifies its label, and pairing failures are reported), FR-9 (a per-row error
names the problem and reports no match), FR-11 (the application side of every
row is read off that row's COLA document), NFR-2 (the batch does not fail as a
whole and its progress is observable), NFR-6 (nothing is persisted), and NFR-7
(the file count is checked before processing).

Stories: US-9, US-10, US-11, US-23. Decision references: ADR 0006 for the
stream, ADR 0009 for what a batch is made of.

**A batch is label images plus COLA documents, paired by filename stem.**
`0001-stones-throw.png` pairs with `0001-stones-throw.pdf`. There is no CSV;
assumption A-14 invented that format and ADR 0009 supersedes it.

Every document here is generated at test time by samples/formmaker.py, with
invented values. No real filing and no personal data, which is the test data
policy in docs/07_TEST_STRATEGY.md section 8.

The tiers are kept apart deliberately, following docs/07_TEST_STRATEGY.md
section 1. The pairing and refusal tests need no Tesseract, because every one of
them either rejects before decoding or fails to decode. The tests that read real
artwork carry the integration markers.
"""

from __future__ import annotations

import json
import time

import pytest
from fastapi.testclient import TestClient
from samples.formmaker import ApplicationSpec, as_pdf_bytes, registry_printout_lines
from samples.specs import SAMPLE_LABEL, SPECS

from app.batch import pairing_stem
from app.config import settings
from app.main import app
from tests.conftest import requires_fonts, requires_tesseract

client = TestClient(app)

CORRUPT_IMAGE = b"this is not an image"
CORRUPT_DOCUMENT = b"this is not a pdf"


def document_for(spec=SAMPLE_LABEL) -> bytes:
    """A Registry printout carrying one label spec's application values.

    Written from the spec rather than fixtured, so the document a test depends
    on is visible in the test.
    """
    application = spec.application
    return as_pdf_bytes(
        registry_printout_lines(
            ApplicationSpec(
                brand_name=application.get("brand_name", ""),
                class_type=application.get("class_type", ""),
                alcohol_content=application.get("alcohol_content", ""),
                net_contents=application.get("net_contents", ""),
                beverage_type=application.get("beverage_type", ""),
            )
        )
    )


def submit(images: list[tuple[str, bytes]], documents: list[tuple[str, bytes]]):
    files = [("images", (name, content, "image/png")) for name, content in images]
    files += [
        ("application_documents", (name, content, "application/pdf")) for name, content in documents
    ]
    return client.post("/api/verify-batch", files=files)


def paired(images: list[tuple[str, bytes]], spec=SAMPLE_LABEL):
    """The submission for a set of images, each with a document named to match."""
    documents = [(f"{pairing_stem(name)}.pdf", document_for(spec)) for name, _ in images]
    return submit(images, documents)


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


class TestThePairingRule:
    """ADR 0009's contract, stated as the function both sides are keyed on."""

    @pytest.mark.parametrize(
        ("filename", "expected"),
        [
            ("0001-stones-throw.png", "0001-stones-throw"),
            ("0001-stones-throw.pdf", "0001-stones-throw"),
            ("0001-STONES-THROW.PDF", "0001-stones-throw"),
            ("  0001-stones-throw.jpg  ", "0001-stones-throw"),
            # Only the final extension is removed.
            ("0001-stones-throw.front.png", "0001-stones-throw.front"),
            # A browser sending a path pairs on the name.
            ("batch/0001-stones-throw.png", "0001-stones-throw"),
            # No extension at all is a stem in its own right.
            ("0001-stones-throw", "0001-stones-throw"),
        ],
    )
    def test_the_stem_is_the_name_without_its_final_extension(self, filename, expected):
        assert pairing_stem(filename) == expected

    def test_an_image_and_a_document_pair_when_their_stems_agree(self):
        response = submit(
            [("0001-stones-throw.png", CORRUPT_IMAGE)],
            [("0001-STONES-THROW.pdf", document_for())],
        )
        received = lines(response)
        assert len(received) == 1
        # Paired: the failure is the image, not the pairing.
        assert received[0]["error"]["code"] == "unreadable_image"


class TestOverCount:
    """FR-8's third criterion and NFR-7's third."""

    def test_a_batch_over_the_limit_is_refused_and_the_message_names_the_limit(self, monkeypatch):
        monkeypatch.setattr(settings, "max_batch_files", 2)
        images = [(f"{index}.png", CORRUPT_IMAGE) for index in range(3)]
        response = paired(images)

        assert response.status_code == 413
        body = response.json()
        assert body["error"]["code"] == "batch_too_large"
        assert "2" in body["error"]["limit"]
        # Refused before processing: no result set for any label, and in
        # particular no field outcomes at all (FR-9's last criterion).
        assert "fields" not in response.text
        assert "match" not in response.text

    def test_too_many_documents_is_refused_on_the_same_limit(self, monkeypatch):
        monkeypatch.setattr(settings, "max_batch_files", 2)
        response = submit(
            [("a.png", CORRUPT_IMAGE)],
            [(f"{index}.pdf", document_for()) for index in range(3)],
        )
        assert response.status_code == 413
        assert response.json()["error"]["code"] == "batch_too_large"

    def test_a_batch_at_the_limit_is_accepted(self, monkeypatch):
        monkeypatch.setattr(settings, "max_batch_files", 2)
        images = [(f"{index}.png", CORRUPT_IMAGE) for index in range(2)]
        response = paired(images)
        assert response.status_code == 200
        assert len(lines(response)) == 2


class TestEveryLineIdentifiesItsLabel:
    """FR-8's fourth criterion, and the fields NFR-2 needs for progress."""

    def test_each_line_names_its_image_and_carries_its_position(self):
        images = [(f"{index:02d}.png", CORRUPT_IMAGE) for index in range(4)]
        response = paired(images)

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
            ("application_documents", ("a.pdf", document_for(), "application/pdf")),
        ]
        response = client.post("/api/verify-batch", files=files)

        assert response.status_code == 422
        error = response.json()["error"]
        assert error["code"] == "invalid_submission"
        assert "images" in error["message"]
        assert "fields" not in response.text


class TestOneBadItemDoesNotFailTheBatch:
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
        response = paired(images)

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

    def test_an_unreadable_document_errors_that_row_only(self):
        """FR-9 applied to the document half of a pair (ADR 0009)."""
        response = submit(
            [("broken-doc.png", CORRUPT_IMAGE), ("good-doc.png", CORRUPT_IMAGE)],
            [
                ("broken-doc.pdf", CORRUPT_DOCUMENT),
                ("good-doc.pdf", document_for()),
            ],
        )

        assert response.status_code == 200
        received = {line["filename"]: line for line in lines(response)}
        broken = received["broken-doc.png"]
        assert broken["error"]["code"] == "unreadable_application_document"
        assert "broken-doc.pdf" in broken["error"]["message"]
        assert broken["result"] is None
        # The other row still ran, and failed on its own terms rather than on
        # the neighbouring row's.
        assert received["good-doc.png"]["error"]["code"] == "unreadable_image"

    def test_a_disallowed_image_type_inside_a_batch_errors_that_row_only(self):
        files = [
            ("images", ("ok.png", CORRUPT_IMAGE, "image/png")),
            ("images", ("notes.pdf", b"%PDF-1.4", "application/pdf")),
            ("application_documents", ("ok.pdf", document_for(), "application/pdf")),
            ("application_documents", ("notes.pdf", document_for(), "application/pdf")),
        ]
        response = client.post("/api/verify-batch", files=files)
        assert response.status_code == 200
        received = {line["filename"]: line for line in lines(response)}
        assert received["notes.pdf"]["error"]["code"] == "unsupported_media_type"
        assert "image/png" in received["notes.pdf"]["error"]["limit"]
        assert received["ok.png"]["error"]["code"] == "unreadable_image"

    def test_a_disallowed_document_type_errors_that_row_only(self):
        files = [
            ("images", ("a.png", CORRUPT_IMAGE, "image/png")),
            ("images", ("b.png", CORRUPT_IMAGE, "image/png")),
            ("application_documents", ("a.pdf", document_for(), "application/pdf")),
            ("application_documents", ("b.txt", b"brand name: x", "text/plain")),
        ]
        response = client.post("/api/verify-batch", files=files)
        received = {line["filename"]: line for line in lines(response)}
        assert received["b.png"]["error"]["code"] == "unsupported_application_document"
        assert received["a.png"]["error"]["code"] == "unreadable_image"

    def test_an_oversize_image_inside_a_batch_errors_that_row_only(self, monkeypatch):
        # Above the generated documents, which are under a kilobyte, so the
        # limit this exercises is the one on the image.
        monkeypatch.setattr(settings, "max_upload_bytes", 4096)
        images = [("small.png", CORRUPT_IMAGE), ("big.png", b"x" * 8192)]
        response = paired(images)

        assert response.status_code == 200
        received = {line["filename"]: line for line in lines(response)}
        assert received["big.png"]["error"]["code"] == "file_too_large"
        assert "4096" in received["big.png"]["error"]["limit"]
        assert received["small.png"]["error"]["code"] == "unreadable_image"

    def test_an_oversize_document_inside_a_batch_errors_that_row_only(self, monkeypatch):
        """The document is an upload in its own right, bounded the same way."""
        monkeypatch.setattr(settings, "max_upload_bytes", 512)
        response = submit(
            [("a.png", CORRUPT_IMAGE), ("b.png", CORRUPT_IMAGE)],
            [("a.pdf", b"%PDF-1.4 tiny"), ("b.pdf", document_for())],
        )

        received = {line["filename"]: line for line in lines(response)}
        assert received["b.png"]["error"]["code"] == "file_too_large"
        # The other row got past the size check and failed on its own document.
        assert received["a.png"]["error"]["code"] == "unreadable_application_document"


class TestPairing:
    """FR-8's sixth criterion under ADR 0009: an image with no document, a
    document with no image, and a duplicated stem each produce an error that
    names the problem, and the rest of the batch still runs."""

    def test_a_document_with_no_image_errors_on_its_own_line(self):
        response = submit(
            [("present.png", CORRUPT_IMAGE)],
            [("present.pdf", document_for()), ("absent.pdf", document_for())],
        )

        assert response.status_code == 200
        received = {line["filename"]: line for line in lines(response)}
        assert set(received) == {"present.png", "absent.pdf"}

        orphan = received["absent.pdf"]
        assert orphan["status"] == "error"
        assert orphan["error"]["code"] == "unmatched_application_document"
        assert "absent.pdf" in orphan["error"]["message"]
        assert orphan["result"] is None
        # The image that was submitted still got its own line.
        assert received["present.png"]["error"]["code"] == "unreadable_image"

    def test_an_image_with_no_document_errors_on_its_own_line(self):
        response = submit(
            [("listed.png", CORRUPT_IMAGE), ("unlisted.png", CORRUPT_IMAGE)],
            [("listed.pdf", document_for())],
        )

        received = {line["filename"]: line for line in lines(response)}
        assert received["unlisted.png"]["error"]["code"] == "missing_application_document"
        assert "unlisted" in received["unlisted.png"]["error"]["message"]
        assert received["listed.png"]["error"]["code"] == "unreadable_image"

    def test_two_documents_on_one_stem_error_that_row_and_leave_the_others(self):
        response = submit(
            [("twice.png", CORRUPT_IMAGE), ("once.png", CORRUPT_IMAGE)],
            [
                ("twice.pdf", document_for()),
                ("TWICE.PDF", document_for()),
                ("once.pdf", document_for()),
            ],
        )

        received = {line["filename"]: line for line in lines(response)}
        assert received["twice.png"]["error"]["code"] == "duplicate_application_document"
        assert "twice" in received["twice.png"]["error"]["message"]
        assert received["once.png"]["error"]["code"] == "unreadable_image"

    def test_two_images_on_one_stem_error_because_the_pairing_is_ambiguous(self):
        """One document cannot belong to two labels (ADR 0009)."""
        response = submit(
            [("same.png", CORRUPT_IMAGE), ("same.jpeg", CORRUPT_IMAGE)],
            [("same.pdf", document_for())],
        )

        received = lines(response)
        assert len(received) == 2
        assert {line["error"]["code"] for line in received} == {"duplicate_label_stem"}

    def test_two_images_submitted_under_one_filename_stay_distinguishable(self):
        files = [
            ("images", ("same.png", CORRUPT_IMAGE, "image/png")),
            ("images", ("same.png", CORRUPT_IMAGE, "image/png")),
            ("application_documents", ("same.pdf", document_for(), "application/pdf")),
        ]
        response = client.post("/api/verify-batch", files=files)

        received = lines(response)
        assert len(received) == 2
        assert len({line["filename"] for line in received}) == 2, (
            "FR-8 requires each result to identify which label it belongs to, "
            "so two parts cannot both report under one name"
        )


class TestUnusableSubmissions:
    """The batch-level half of FR-8's error criterion."""

    def test_a_batch_with_no_images_is_refused(self):
        files = [("application_documents", ("a.pdf", document_for(), "application/pdf"))]
        response = client.post("/api/verify-batch", files=files)
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "empty_batch"

    def test_a_batch_with_no_documents_at_all_is_refused_and_the_rule_is_stated(self):
        """Batch level rather than 300 identical per-row errors."""
        files = [("images", ("a.png", CORRUPT_IMAGE, "image/png"))]
        response = client.post("/api/verify-batch", files=files)

        assert response.status_code == 422
        error = response.json()["error"]
        assert error["code"] == "missing_application_documents"
        assert ".pdf" in error["message"], "the message states the pairing rule"
        assert "fields" not in response.text


class TestWhatTheDocumentSupplied:
    """FR-11 on the batch path: every value comes from that row's document."""

    @requires_tesseract
    @requires_fonts
    def test_the_row_compares_against_what_its_document_said(self, sample_label_png):
        response = paired([("01-spirits-clean.png", sample_label_png)])
        line = lines(response)[0]
        assert line["status"] == "ok", line

        by_name = {field["name"]: field for field in line["result"]["fields"]}
        assert by_name["brand_name"]["application_value"] == "Stone's Throw"
        assert by_name["brand_name"]["outcome"] == "match"
        # Nothing was typed on this path, so every supplied value is parsed.
        assert by_name["brand_name"]["application_value_source"] == "parsed_from_form"

    @requires_tesseract
    @requires_fonts
    def test_the_row_carries_the_parsed_block_so_the_reading_is_visible(self, sample_label_png):
        response = paired([("01-spirits-clean.png", sample_label_png)])
        document = lines(response)[0]["result"]["application_document"]

        assert document is not None
        assert document["extraction_path"] == "embedded_text"
        assert {field["name"] for field in document["fields"]} == {
            "brand_name",
            "class_type",
            "alcohol_content",
            "net_contents",
            "beverage_type",
        }

    @requires_tesseract
    @requires_fonts
    def test_a_beverage_type_the_document_did_not_state_says_so(self, sample_label_png):
        """A Registry printout for a bourbon names no product type, and the row
        reports that rather than inferring one (FR-1's rule, applied here).

        No per-field comparison reads the beverage type: the proof cross-check
        keys off a proof statement the label itself carries, and the wine range
        handling keys off a range, both per A-12 and A-13. So an unstated
        beverage type costs the comparison nothing, and the row says it was not
        stated instead of guessing.
        """
        response = paired([("01-spirits-clean.png", sample_label_png)])
        document = lines(response)[0]["result"]["application_document"]

        beverage = next(field for field in document["fields"] if field["name"] == "beverage_type")
        assert beverage["found_on_document"] is False
        assert beverage["value"] is None
        assert any("ticked box cannot be read" in note for note in document["notes"])

    @requires_tesseract
    @requires_fonts
    def test_a_value_the_document_omits_is_not_compared_rather_than_mismatched(
        self, sample_label_png
    ):
        """FR-2: a field the application did not supply is not a mismatch."""
        response = submit(
            [("a.png", sample_label_png)],
            [
                (
                    "a.pdf",
                    as_pdf_bytes(
                        registry_printout_lines(ApplicationSpec(brand_name="Stone's Throw"))
                    ),
                )
            ],
        )
        by_name = {field["name"]: field for field in lines(response)[0]["result"]["fields"]}
        assert by_name["net_contents"]["outcome"] == "not_compared"
        assert by_name["net_contents"]["application_value_source"] == "absent"


class TestNothingIsPersisted:
    """NFR-6, asserted against the batch path as well as the single one."""

    def test_no_field_value_or_filename_reaches_the_logs(self, caplog):
        caplog.set_level("INFO")
        paired([("secret-brand.png", CORRUPT_IMAGE)])
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
        documents = [(f"{pairing_stem(spec.filename)}.pdf", document_for(spec)) for spec in SPECS]

        started = time.perf_counter()
        response = submit(images, documents)
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
            assert line["result"]["application_document"] is not None, "FR-11"

        with capsys.disabled():
            print(
                f"\nBatch of {len(SPECS)} labels with their COLA documents: "
                f"{elapsed:.2f} s wall clock on "
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
    response = paired(images)

    received = lines(response)
    assert len(received) == 8
    assert {line["filename"] for line in received} == {name for name, _ in images}
