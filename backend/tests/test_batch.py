"""Batch verification over POST /api/verify-batch.

Covers FR-8 (every label returns a result, one bad file errors that row only,
an over-count batch is refused before anything is processed, every line
identifies its label), FR-9 (a per-row error names the problem and reports no
match), FR-11 (the application side of a row is read off that row's COLA
document), FR-12 (one upload, sorted by the tool), NFR-2 (the batch does not
fail as a whole and its progress is observable), NFR-6 (nothing is persisted),
and NFR-7 (the count is checked before processing).

Stories: US-9, US-10, US-11, US-23. Decision references: ADR 0006 for the
stream, ADR 0020 for what a row is, ADR 0009 for the stem rule it keeps.

**A batch is one pile of files, and a row is every file that shares a stem.**
`0001-stones-throw.pdf` and `0001-stones-throw.png` are one row; each row is
classified from its files and run through the single-label check. There is no
CSV (A-14, superseded by ADR 0009) and there are no longer two parts that both
have to be filled (ADR 0009's contract, superseded by ADR 0020).

Every document here is generated at test time by samples/formmaker.py, with
invented values. No real filing and no personal data, which is the test data
policy in docs/07_TEST_STRATEGY.md section 8.

The tiers are kept apart deliberately, following docs/07_TEST_STRATEGY.md
section 1. The grouping and refusal tests need no Tesseract, because every one
of them either rejects before decoding or fails to decode. The tests that read
real artwork carry the integration markers.
"""

from __future__ import annotations

import json
import tempfile
import time
from dataclasses import replace
from pathlib import Path

import pytesseract.pytesseract
import pytest
from fastapi.testclient import TestClient
from samples.formmaker import (
    ApplicationSpec,
    as_pdf_bytes,
    as_png_bytes,
    paper_form_lines,
    registry_printout_lines,
)
from samples.labelmaker import render_png_bytes
from samples.specs import SAMPLE_LABEL, SPECS

from app.batch import group, pairing_stem
from app.classify import SubmittedFile
from app.config import settings
from app.main import app
from tests.conftest import requires_fonts, requires_tesseract

client = TestClient(app)

CORRUPT_IMAGE = b"this is not an image"
CORRUPT_DOCUMENT = b"this is not a pdf"

TYPES = {"png": "image/png", "jpeg": "image/jpeg", "pdf": "application/pdf"}


def spec_for(spec=SAMPLE_LABEL) -> ApplicationSpec:
    application = spec.application
    return ApplicationSpec(
        brand_name=application.get("brand_name", ""),
        class_type=application.get("class_type", ""),
        alcohol_content=application.get("alcohol_content", ""),
        net_contents=application.get("net_contents", ""),
        beverage_type=application.get("beverage_type", ""),
    )


def document_for(spec=SAMPLE_LABEL) -> bytes:
    """A Registry printout carrying one label spec's application values.

    Written from the spec rather than fixtured, so the document a test depends
    on is visible in the test. It carries no artwork, so on its own it is an
    application with nothing to check.
    """
    return as_pdf_bytes(registry_printout_lines(spec_for(spec)))


def filed_document_for(spec=SAMPLE_LABEL) -> bytes:
    """The same printout with the label artwork affixed, which is what an
    importer actually files: a complete row on its own (ADR 0010, ADR 0020)."""
    return as_pdf_bytes(registry_printout_lines(spec_for(spec)), images=[render_png_bytes(spec)])


def submit(files: list[tuple[str, bytes]], part: str = "files"):
    """Post the files in one repeated part. The type comes from the extension."""
    parts = []
    for name, content in files:
        extension = name.rsplit(".", 1)[-1].lower() if "." in name else ""
        parts.append((part, (name, content, TYPES.get(extension, "application/octet-stream"))))
    return client.post("/api/verify-batch", files=parts)


def paired(images: list[tuple[str, bytes]], spec=SAMPLE_LABEL):
    """The submission for a set of images, each with a document named to match."""
    documents = [(f"{pairing_stem(name)}.pdf", document_for(spec)) for name, _ in images]
    return submit([*images, *documents])


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


def by_name(response) -> dict[str, dict]:
    return {line["filename"]: line for line in lines(response)}


class TestTheStemRule:
    """ADR 0009's rule, kept by ADR 0020 as the thing that groups a row."""

    @pytest.mark.parametrize(
        ("filename", "expected"),
        [
            ("0001-stones-throw.png", "0001-stones-throw"),
            ("0001-stones-throw.pdf", "0001-stones-throw"),
            ("0001-STONES-THROW.PDF", "0001-stones-throw"),
            ("  0001-stones-throw.jpg  ", "0001-stones-throw"),
            # Only the final extension is removed.
            ("0001-stones-throw.front.png", "0001-stones-throw.front"),
            # A browser sending a path groups on the name.
            ("batch/0001-stones-throw.png", "0001-stones-throw"),
            # No extension at all is a stem in its own right.
            ("0001-stones-throw", "0001-stones-throw"),
        ],
    )
    def test_the_stem_is_the_name_without_its_final_extension(self, filename, expected):
        assert pairing_stem(filename) == expected

    def test_files_that_share_a_stem_are_one_row_in_order_of_first_appearance(self):
        files = [
            SubmittedFile("b.pdf", "application/pdf", b""),
            SubmittedFile("a.png", "image/png", b""),
            SubmittedFile("B.PNG", "image/png", b""),
            SubmittedFile("c.pdf", "application/pdf", b""),
        ]
        rows = group(files)
        assert [(row.position, row.stem, row.filenames) for row in rows] == [
            (1, "b", ["b.pdf", "B.PNG"]),
            (2, "a", ["a.png"]),
            (3, "c", ["c.pdf"]),
        ]

    def test_an_image_and_a_document_group_when_their_stems_agree(self):
        response = submit(
            [("0001-stones-throw.png", CORRUPT_IMAGE), ("0001-STONES-THROW.pdf", document_for())]
        )
        received = lines(response)
        assert len(received) == 1
        assert received[0]["filenames"] == ["0001-stones-throw.png", "0001-STONES-THROW.pdf"]
        # Grouped: the failure is the image, not the grouping.
        assert received[0]["error"]["code"] == "unreadable_image"


class TestOverCount:
    """FR-8's third criterion and NFR-7's third. The limit is on rows, not files."""

    def test_a_batch_over_the_limit_is_refused_and_the_message_names_the_limit(self, monkeypatch):
        monkeypatch.setattr(settings, "max_batch_files", 2)
        response = paired([(f"{index}.png", CORRUPT_IMAGE) for index in range(3)])

        assert response.status_code == 413
        body = response.json()
        assert body["error"]["code"] == "batch_too_large"
        assert "2" in body["error"]["limit"]
        assert "3 labels" in body["error"]["message"]
        # Refused before processing: no result set for any label, and in
        # particular no field outcomes at all (FR-9's last criterion).
        assert "fields" not in response.text
        assert "match" not in response.text

    def test_a_batch_at_the_limit_is_accepted_however_many_files_its_rows_hold(self, monkeypatch):
        """Two rows of two files each is two labels, not four (A-1)."""
        monkeypatch.setattr(settings, "max_batch_files", 2)
        response = paired([(f"{index}.png", CORRUPT_IMAGE) for index in range(2)])
        assert response.status_code == 200
        assert len(lines(response)) == 2


class TestEveryLineIdentifiesItsLabel:
    """FR-8's fourth criterion, and the fields NFR-2 needs for progress."""

    def test_each_line_names_its_row_and_carries_its_position(self):
        images = [(f"{index:02d}.png", CORRUPT_IMAGE) for index in range(4)]
        response = paired(images)

        assert response.status_code == 200
        received = lines(response)
        assert len(received) == 4
        assert {line["filename"] for line in received} == {name for name, _ in images}
        # Index and total are what let a client render "3 of 4" from the
        # first line it receives, without counting parts itself (NFR-2).
        assert sorted(line["index"] for line in received) == [1, 2, 3, 4]
        assert {line["total"] for line in received} == {4}
        # Position is submission order, which is what lets a client show the
        # rows in the order the agent submitted them (ADR 0020).
        assert {line["filename"]: line["position"] for line in received} == {
            "00.png": 1,
            "01.png": 2,
            "02.png": 3,
            "03.png": 4,
        }

    def test_a_row_is_named_after_its_label_image_where_it_has_one(self):
        response = submit([("a.pdf", document_for()), ("a.png", CORRUPT_IMAGE)])
        line = lines(response)[0]
        assert line["filename"] == "a.png"
        assert line["filenames"] == ["a.pdf", "a.png"]

    def test_a_part_with_no_filename_is_refused_in_the_documented_shape(self):
        """A part sent without a filename is not an upload at all: the multipart
        parser hands it over as a form field, so it never reaches the route. The
        rejection still has to name the problem in one shape (FR-9)."""
        files = [
            ("files", ("", CORRUPT_IMAGE, "image/png")),
            ("files", ("a.pdf", document_for(), "application/pdf")),
        ]
        response = client.post("/api/verify-batch", files=files)

        assert response.status_code == 422
        error = response.json()["error"]
        assert error["code"] == "invalid_submission"
        assert "files" in error["message"]
        assert "fields" not in response.text

    def test_two_files_submitted_under_one_filename_stay_distinguishable(self):
        response = submit([("same.png", CORRUPT_IMAGE), ("same.png", CORRUPT_IMAGE)])
        received = lines(response)
        # One row, because they share a stem; two names inside it.
        assert len(received) == 1
        assert len(set(received[0]["filenames"])) == 2, (
            "FR-8 requires each result to identify which label it belongs to, "
            "so two parts cannot both report under one name"
        )
        assert received[0]["error"]["code"] == "duplicate_label_stem"


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
        received = by_name(response)
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

    def test_an_unreadable_document_errors_that_row_only_and_names_the_document(self):
        """FR-9 applied to the document half of a row (ADR 0009, kept)."""
        response = submit(
            [
                ("broken-doc.png", CORRUPT_IMAGE),
                ("good-doc.png", CORRUPT_IMAGE),
                ("broken-doc.pdf", CORRUPT_DOCUMENT),
                ("good-doc.pdf", document_for()),
            ]
        )

        assert response.status_code == 200
        received = by_name(response)
        broken = received["broken-doc.png"]
        assert broken["error"]["code"] == "unreadable_application_document"
        assert "broken-doc.pdf" in broken["error"]["message"]
        assert broken["result"] is None
        # The other row still ran, and failed on its own terms rather than on
        # the neighbouring row's.
        assert received["good-doc.png"]["error"]["code"] == "unreadable_image"

    def test_a_disallowed_type_inside_a_batch_errors_that_row_only(self):
        """The same guard, with the same accepted list, the single-label route
        applies to its one part: PDF plus the image types (FR-12)."""
        files = [
            ("files", ("a.png", CORRUPT_IMAGE, "image/png")),
            ("files", ("b.txt", b"brand name: x", "text/plain")),
            ("files", ("a.pdf", document_for(), "application/pdf")),
        ]
        response = client.post("/api/verify-batch", files=files)
        received = by_name(response)
        assert received["b.txt"]["error"]["code"] == "unsupported_application_document"
        assert "application/pdf" in received["b.txt"]["error"]["limit"]
        assert received["a.png"]["error"]["code"] == "unreadable_image"

    def test_an_oversize_file_inside_a_batch_errors_that_row_only(self, monkeypatch):
        # Above the generated documents, which are under a kilobyte, so the
        # limit this exercises is the one on the image.
        monkeypatch.setattr(settings, "max_upload_bytes", 4096)
        response = paired([("small.png", CORRUPT_IMAGE), ("big.png", b"x" * 8192)])

        assert response.status_code == 200
        received = by_name(response)
        assert received["big.png"]["error"]["code"] == "file_too_large"
        assert "4096" in received["big.png"]["error"]["limit"]
        assert received["small.png"]["error"]["code"] == "unreadable_image"

    def test_an_oversize_document_inside_a_batch_errors_that_row_only(self, monkeypatch):
        """The document is an upload in its own right, bounded the same way."""
        monkeypatch.setattr(settings, "max_upload_bytes", 512)
        response = submit(
            [
                ("a.png", CORRUPT_IMAGE),
                ("b.png", CORRUPT_IMAGE),
                ("a.pdf", b"%PDF-1.4 tiny"),
                ("b.pdf", document_for()),
            ]
        )
        received = by_name(response)
        assert received["b.png"]["error"]["code"] == "file_too_large"
        # The other row got past the size check and failed on its own document.
        assert received["a.png"]["error"]["code"] == "unreadable_application_document"


class TestRowsAreDerivedNotDemanded:
    """ADR 0020: what a row is, decided from its files rather than from two parts.

    Until v1.4.0 an application with no image of the same name was an error
    (`unmatched_application_document`), an image with no application was an
    error (`missing_application_document`), and a batch with no images at all
    was refused before it started. None of those is an error now, and the
    codes are gone: each is a row, checked for what it can be checked for.
    """

    @requires_tesseract
    @requires_fonts
    def test_an_application_that_carries_its_own_artwork_is_a_complete_row(self):
        """The single most important behaviour in v1.4.0: twelve filed
        applications and no images give twelve checked labels."""
        response = submit([("filed.pdf", filed_document_for())])
        line = lines(response)[0]

        assert line["status"] == "ok", line
        assert line["filenames"] == ["filed.pdf"]
        result = line["result"]
        assert result["label_source"] == "application_artwork"
        assert result["self_consistency_note"]
        assert [field["name"] for field in result["fields"]] == [
            "brand_name",
            "class_type",
            "alcohol_content",
            "net_contents",
            "government_warning",
        ]
        fields = {field["name"]: field for field in result["fields"]}
        assert fields["brand_name"]["outcome"] == "match"
        assert fields["government_warning"]["found_on_label"] is True

    def test_an_application_with_no_artwork_and_no_image_is_a_visible_row_not_an_absence(self):
        """Nothing is silently dropped: the row says what is missing (FR-9)."""
        response = submit([("bare.pdf", document_for()), ("other.png", CORRUPT_IMAGE)])
        received = by_name(response)
        assert set(received) == {"bare.pdf", "other.png"}
        bare = received["bare.pdf"]
        assert bare["status"] == "error"
        assert bare["error"]["code"] == "no_label_to_check"
        assert "image of the label" in bare["error"]["message"]
        assert bare["result"] is None

    @requires_tesseract
    @requires_fonts
    def test_an_image_with_no_application_is_a_valid_row(self, sample_label_png):
        """As on the single-label tab (code review finding 19): the required
        elements are checked for presence, the comparisons say there is nothing
        to compare against, and it is not an error."""
        response = submit([("alone.png", sample_label_png)])
        line = lines(response)[0]

        assert line["status"] == "ok", line
        result = line["result"]
        assert result["label_source"] == "uploaded_photographs"
        assert result["application_document"] is None
        fields = {field["name"]: field for field in result["fields"]}
        assert fields["brand_name"]["outcome"] == "not_compared"
        assert fields["class_type"]["outcome"] == "not_compared"
        assert fields["alcohol_content"]["outcome"] == "present"
        assert fields["net_contents"]["outcome"] == "present"
        assert fields["government_warning"]["outcome"] == "match"

    @requires_tesseract
    @requires_fonts
    def test_a_scan_of_the_form_and_a_photograph_pair_by_what_they_are_not_by_extension(
        self, sample_label_png
    ):
        """Classification first. Two PNGs on one stem, one a picture of the
        application and one a picture of the label, are the ordinary pair;
        under the two-part contract an agent had to know which box to drop
        each in, and under a rule keyed on extension both would be images."""
        scan = as_png_bytes(registry_printout_lines(spec_for()))
        assert scan is not None
        response = submit([("0007-form.png", scan), ("0007-form.jpeg", sample_label_png)])
        line = lines(response)[0]

        assert line["status"] == "ok", line
        result = line["result"]
        sides = {entry["filename"]: entry["classified_as"] for entry in result["files"]}
        assert sides == {
            "0007-form.png": "application_document",
            "0007-form.jpeg": "label_image",
        }
        assert line["filename"] == "0007-form.jpeg", "named after its label image"
        assert result["label_source"] == "uploaded_photographs"
        assert result["application_document"]["extraction_path"] == "ocr"
        fields = {field["name"]: field for field in result["fields"]}
        assert fields["brand_name"]["application_value"], "read off the scanned form"

    def test_two_applications_on_one_stem_are_ambiguous_and_leave_the_others(self):
        response = submit(
            [
                ("twice.png", CORRUPT_IMAGE),
                ("twice.pdf", document_for()),
                ("TWICE.PDF", document_for()),
                ("once.png", CORRUPT_IMAGE),
                ("once.pdf", document_for()),
            ]
        )
        received = by_name(response)
        assert received["twice.png"]["error"]["code"] == "duplicate_application_document"
        assert "twice.pdf" in received["twice.png"]["error"]["message"]
        assert "TWICE.PDF" in received["twice.png"]["error"]["message"]
        assert received["once.png"]["error"]["code"] == "unreadable_image"

    def test_two_label_images_on_one_stem_are_one_row_and_it_is_ambiguous(self):
        """ADR 0009's one photograph per label, unchanged: the message sends a
        label with several photographs to the single-label tab."""
        response = submit(
            [
                ("same.png", CORRUPT_IMAGE),
                ("same.jpeg", CORRUPT_IMAGE),
                ("same.pdf", document_for()),
            ]
        )
        received = lines(response)
        assert len(received) == 1
        assert received[0]["error"]["code"] == "duplicate_label_stem"
        assert "single-label" in received[0]["error"]["message"]
        assert set(received[0]["filenames"]) == {"same.png", "same.jpeg", "same.pdf"}

    def test_the_older_part_names_still_work_and_go_through_the_same_classifier(self):
        """A caller written against ADR 0009 keeps working, and a PDF dropped
        in the `images` part is still read as an application (FR-12)."""
        files = [
            ("images", ("a.png", CORRUPT_IMAGE, "image/png")),
            ("application_documents", ("a.pdf", document_for(), "application/pdf")),
            ("images", ("b.pdf", document_for(), "application/pdf")),
        ]
        response = client.post("/api/verify-batch", files=files)
        received = by_name(response)
        assert set(received) == {"a.png", "b.pdf"}
        assert received["a.png"]["error"]["code"] == "unreadable_image"
        assert received["b.pdf"]["error"]["code"] == "no_label_to_check"


class TestTheBatchIsTheSameCheck:
    """ADR 0020's whole point, asserted rather than inferred: a row's result is
    the single-label route's result for the same files."""

    @requires_tesseract
    @requires_fonts
    @pytest.mark.parametrize(
        "files",
        [
            pytest.param([("01.png", "label"), ("01.pdf", "document")], id="pair"),
            pytest.param([("01.pdf", "filed")], id="application-alone"),
            pytest.param([("01.png", "label")], id="image-alone"),
        ],
    )
    def test_a_row_and_a_single_label_check_agree(self, sample_label_png, files):
        contents = {
            "label": sample_label_png,
            "document": document_for(),
            "filed": filed_document_for(),
        }
        parts = [(name, contents[kind]) for name, kind in files]
        single = client.post(
            "/api/verify",
            files=[
                ("files", (name, content, TYPES[name.rsplit(".", 1)[-1]]))
                for name, content in parts
            ],
        )
        assert single.status_code == 200, single.text
        row = lines(submit(parts))[0]
        assert row["status"] == "ok", row

        def comparable(result: dict) -> list[tuple]:
            return [
                (
                    field["name"],
                    field["outcome"],
                    field["label_value"],
                    field["application_value"],
                    field["application_value_source"],
                )
                for field in result["fields"]
            ]

        assert comparable(row["result"]) == comparable(single.json())
        assert row["result"]["label_source"] == single.json()["label_source"]
        assert [entry["classified_as"] for entry in row["result"]["files"]] == [
            entry["classified_as"] for entry in single.json()["files"]
        ]


class TestUnusableSubmissions:
    """The batch-level half of FR-8's error criterion, which is now one case."""

    def test_a_batch_with_no_files_is_refused(self):
        response = client.post("/api/verify-batch", files=[])
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "empty_batch"
        assert "fields" not in response.text

    def test_a_batch_of_images_alone_runs(self):
        """What used to be refused as `missing_application_documents`."""
        response = submit([("a.png", CORRUPT_IMAGE), ("b.png", CORRUPT_IMAGE)])
        assert response.status_code == 200
        assert len(lines(response)) == 2

    def test_a_batch_of_applications_alone_runs(self):
        """What used to be a stream of `unmatched_application_document`."""
        response = submit([("a.pdf", document_for()), ("b.pdf", document_for())])
        assert response.status_code == 200
        assert {line["error"]["code"] for line in lines(response)} == {"no_label_to_check"}


class TestWhatTheDocumentSupplied:
    """FR-11 on the batch path: every value comes from that row's document."""

    @requires_tesseract
    @requires_fonts
    def test_the_row_compares_against_what_its_document_said(self, sample_label_png):
        response = paired([("01-spirits-clean.png", sample_label_png)])
        line = lines(response)[0]
        assert line["status"] == "ok", line

        fields = {field["name"]: field for field in line["result"]["fields"]}
        assert fields["brand_name"]["application_value"] == "Stone's Throw"
        assert fields["brand_name"]["outcome"] == "match"
        # Nothing was typed on this path, so every supplied value is parsed.
        assert fields["brand_name"]["application_value_source"] == "parsed_from_form"

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
        reports that rather than inferring one (FR-1's rule, applied here)."""
        response = paired([("01-spirits-clean.png", sample_label_png)])
        document = lines(response)[0]["result"]["application_document"]

        beverage = next(field for field in document["fields"] if field["name"] == "beverage_type")
        assert beverage["found_on_document"] is False
        assert beverage["value"] is None
        assert any("ticked box is not in a document's text" in note for note in document["notes"])

    @requires_tesseract
    @requires_fonts
    def test_a_value_the_document_omits_is_not_compared_rather_than_mismatched(
        self, sample_label_png
    ):
        """FR-2: a field the application did not supply is not a mismatch."""
        response = submit(
            [
                ("a.png", sample_label_png),
                (
                    "a.pdf",
                    as_pdf_bytes(
                        registry_printout_lines(ApplicationSpec(brand_name="Stone's Throw"))
                    ),
                ),
            ]
        )
        fields = {field["name"]: field for field in lines(response)[0]["result"]["fields"]}
        # **Amended by ADR 0018.** Not a mismatch, which is what FR-2 forbids
        # here, and not "nothing to compare" either: the label carries the net
        # contents 27 CFR requires, so the row reports that one-sided finding
        # and passes. The application side stays empty, because it is empty.
        assert fields["net_contents"]["outcome"] == "present"
        assert fields["net_contents"]["application_value"] is None
        assert fields["net_contents"]["application_value_source"] == "absent"


class TestNothingIsRetainedOnTheBatchPath:
    """NFR-6, asserted against the batch path as well as the single one."""

    def test_no_field_value_or_filename_reaches_the_logs(self, caplog):
        caplog.set_level("INFO")
        paired([("secret-brand.png", CORRUPT_IMAGE)])
        logged = "\n".join(record.getMessage() for record in caplog.records)
        assert "secret-brand" not in logged
        assert "Stone's Throw" not in logged

    @requires_tesseract
    @requires_fonts
    def test_the_engines_temporary_files_are_gone_when_the_stream_ends(
        self, sample_label_png, tmp_path, monkeypatch
    ):
        directory = tmp_path / "tmp"
        directory.mkdir()
        monkeypatch.setattr(tempfile, "tempdir", str(directory))
        created: list[Path] = []
        real = tempfile.NamedTemporaryFile

        def counted(*args, **kwargs):
            handle = real(*args, **kwargs)
            created.append(Path(handle.name))
            return handle

        monkeypatch.setattr(pytesseract.pytesseract, "NamedTemporaryFile", counted)

        response = paired([("01-clean.png", sample_label_png)])

        assert response.status_code == 200
        assert lines(response)[0]["status"] == "ok"
        assert created, "the engine reads each image through a temporary file"
        assert {path.parent for path in created} == {directory}
        assert sorted(directory.iterdir()) == []


@requires_tesseract
@requires_fonts
class TestTheGeneratedSampleSet:
    """A full run over the twelve-label set, which is case 7 in samples/README.md
    and the one case that needed FR-8 to exist before it could be exercised."""

    def test_every_one_of_the_twelve_labels_returns_a_line(self, label_png, capsys):
        images = [(spec.filename, label_png(**spec.__dict__)) for spec in SPECS]
        documents = [(f"{pairing_stem(spec.filename)}.pdf", document_for(spec)) for spec in SPECS]

        started = time.perf_counter()
        response = submit([*images, *documents])
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

    def test_every_one_of_the_twelve_filed_applications_returns_a_checked_label(self, capsys):
        """The ADR 0020 case over the whole set: applications alone, no images."""
        documents = [
            (f"{pairing_stem(spec.filename)}.pdf", filed_document_for(spec)) for spec in SPECS
        ]

        started = time.perf_counter()
        response = submit(documents)
        elapsed = time.perf_counter() - started

        received = lines(response)
        assert len(received) == len(SPECS)
        assert all(line["status"] == "ok" for line in received), [
            line for line in received if line["status"] != "ok"
        ]
        assert {line["result"]["label_source"] for line in received} == {"application_artwork"}
        # Submission order is recoverable from the lines however they arrived.
        assert sorted(line["position"] for line in received) == list(range(1, len(SPECS) + 1))

        with capsys.disabled():
            reads = [line["result"]["timings"]["tesseract_reads"] for line in received]
            passes = [line["result"]["timings"]["ocr_passes"] for line in received]
            print(
                f"\nBatch of {len(SPECS)} filed applications and no images: "
                f"{elapsed:.2f} s wall clock on {settings.effective_batch_workers} workers "
                f"({elapsed / len(SPECS):.2f} s per label); tesseract_reads per row "
                f"{min(reads)} to {max(reads)}, ocr_passes per row {min(passes)} to "
                f"{max(passes)}. Measured on this runner, not on production hardware."
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


@requires_tesseract
@requires_fonts
class TestTheSameArtworkRulesApplyPerRow:
    """FR-14, FR-15, ADR 0013 and ADR 0018, exercised through the batch path.

    SC-3 is the reason the artwork rules exist at all: importers submit "200,
    300 label applications" at once and nobody is sitting there to hand-type two
    values off a document the tool has already read. So the rules have to hold
    per row, and they are asserted here through the real stream rather than
    inferred from the single-label path sharing a function with it.

    **On a paired row the artwork side and the photograph are two pictures**,
    so a value the document's artwork supplied is a real comparison against the
    photograph. **On an application-alone row they are one picture**, and the
    row says so exactly as the single-label tab does: the two presence fields
    pass as Contains, and a field with no presence rule that came off the
    artwork is reported as read from the artwork rather than as a match.
    """

    def _document_with_artwork(self, sample_label_png: bytes) -> bytes:
        """A paper form that states no alcohol content and carries the artwork.

        Three of the five values are not items on TTB F 5100.31 (A-17), so this
        is what the ordinary filed document looks like.
        """
        return as_pdf_bytes(paper_form_lines(ApplicationSpec()), images=[sample_label_png])

    def test_a_paired_row_fills_both_values_from_the_artwork_and_compares_them_for_real(
        self, sample_label_png
    ):
        response = submit(
            [("a.png", sample_label_png), ("a.pdf", self._document_with_artwork(sample_label_png))]
        )
        result = lines(response)[0]["result"]
        fields = {field["name"]: field for field in result["fields"]}

        assert result["label_source"] == "uploaded_photographs"
        for name in ("alcohol_content", "net_contents"):
            entry = fields[name]
            assert entry["application_value_source"] == "parsed_from_artwork"
            assert entry["outcome"] == "match"

    def test_an_application_alone_row_reports_its_one_sided_checks_honestly(self, sample_label_png):
        response = submit([("a.pdf", self._document_with_artwork(sample_label_png))])
        result = lines(response)[0]["result"]
        fields = {field["name"]: field for field in result["fields"]}

        assert result["label_source"] == "application_artwork"
        for name in ("alcohol_content", "net_contents"):
            assert fields[name]["outcome"] == "present"
            assert fields[name]["application_value"] is None
        # Class or type is not on the form and has no presence rule, so where
        # the artwork supplied it and is also the label side it is one reading
        # of one picture, and the row says so rather than claiming a match.
        assert fields["class_type"]["outcome"] in ("artwork_derived", "not_compared")
        assert fields["class_type"]["outcome"] != "match"

    def test_a_row_whose_label_omits_a_mandatory_element_reports_the_finding(
        self, sample_label_png
    ):
        """The presence rule is per row, and it is never "not compared"."""
        without_net_contents = render_png_bytes(replace(SAMPLE_LABEL, net_contents=""))
        response = submit(
            [
                ("a.png", without_net_contents),
                ("a.pdf", as_pdf_bytes(paper_form_lines(ApplicationSpec()))),
            ]
        )
        entry = next(
            field
            for field in lines(response)[0]["result"]["fields"]
            if field["name"] == "net_contents"
        )

        assert entry["found_on_label"] is False
        assert entry["outcome"] == "mismatch"
        assert "27 CFR 5.63(b)(2)" in entry["reason"]


class TestTheFoldIsTheSameOnBothSides:
    """Code review finding 21 (v1.3.0): the page's grouping preview uses the server's rule.

    The server folded with `casefold`, which rewrites `ß` to `ss`, and the page
    with `toLowerCase`, which does not, so `Straße.png` paired with
    `STRASSE.pdf` on the server and not on the page. Both sides now use their
    language's plain lower-case mapping, and these vectors are asserted in
    `frontend/src/__tests__/batchTable.test.tsx` as well, character for
    character, so a divergence fails a test rather than a batch.
    """

    @pytest.mark.parametrize(
        ("filename", "expected"),
        [
            ("Label.PNG", "label"),
            ("ÉTIQUETTE.png", "étiquette"),
            ("Straße.png", "straße"),
            ("STRASSE.pdf", "strasse"),
            ("İstanbul.pdf", "i̇stanbul"),
        ],
    )
    def test_the_plain_lower_case_mapping(self, filename, expected):
        assert pairing_stem(filename) == expected

    def test_a_sharp_s_and_a_double_s_no_longer_pair(self):
        """What `casefold` would have paired, and the page would not have."""
        assert pairing_stem("Straße.png") != pairing_stem("STRASSE.pdf")
