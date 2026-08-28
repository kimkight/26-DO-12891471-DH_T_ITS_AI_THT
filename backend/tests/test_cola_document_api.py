"""POST /api/verify with a COLA document instead of, or alongside, typed values.

Requirements: FR-11 (the label application is accepted as an alternative to
typing the same values), FR-2 (a value the application did not supply reads as
not compared), FR-3 (parsed values are surfaced for confirmation rather than
silently trusted), FR-9 (an empty or unreadable document returns a clear message
and no field reports a match), NFR-7 (type checked before anything is decoded),
OOS-1 (document parsing, not COLA system integration).

Fixtures are generated at test time by samples/formmaker.py; no real
applicant's form is committed (docs/07_TEST_STRATEGY.md section 8).
"""

import io

from fastapi.testclient import TestClient
from PIL import Image
from samples.formmaker import (
    ApplicationSpec,
    as_pdf_bytes,
    registry_printout_lines,
)

from app.main import app

client = TestClient(app)

SPEC = ApplicationSpec(
    brand_name="STONE'S THROW",
    fanciful_name="Small Batch Reserve",
    beverage_type="distilled spirits",
    class_type="KENTUCKY STRAIGHT BOURBON WHISKEY",
    class_type_code="141",
    alcohol_content="45% ALC/VOL",
    net_contents="750 ML",
)


def registry_pdf(spec: ApplicationSpec = SPEC) -> bytes:
    return as_pdf_bytes(registry_printout_lines(spec))


def blank_png(size=(80, 80)) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", size, (255, 255, 255)).save(buffer, format="PNG")
    return buffer.getvalue()


def post(image: bytes, document: bytes | None = None, data=None, doc_type="application/pdf"):
    files = [("image", ("label.png", image, "image/png"))]
    if document is not None:
        files.append(("application_document", ("application.pdf", document, doc_type)))
    return client.post("/api/verify", files=files, data=data or {})


def field(body, name):
    return next(entry for entry in body["fields"] if entry["name"] == name)


def parsed_field(body, name):
    return next(entry for entry in body["application_document"]["fields"] if entry["name"] == name)


class TestNothingChangesWhenNoDocumentIsSent:
    """The path that existed before FR-11 behaves exactly as it did."""

    def test_typed_values_alone_report_no_parsed_block(self, sample_label_png):
        response = post(sample_label_png, data={"brand_name": "Stone's Throw"})
        assert response.status_code == 200
        body = response.json()
        assert body["application_document"] is None
        assert field(body, "brand_name")["application_value_source"] == "typed"

    def test_neither_typed_nor_uploaded_is_not_compared_rather_than_a_mismatch(
        self, sample_label_png
    ):
        response = post(sample_label_png)
        assert response.status_code == 200
        body = response.json()
        assert body["application_document"] is None
        for name in ("brand_name", "class_type", "alcohol_content", "net_contents"):
            entry = field(body, name)
            assert entry["outcome"] == "not_compared"
            assert entry["application_value_source"] == "absent"


class TestAnUploadedDocumentSuppliesTheApplicationValues:
    def test_the_parsed_values_are_compared_against_the_label(self, sample_label_png):
        response = post(sample_label_png, registry_pdf())
        assert response.status_code == 200
        body = response.json()
        brand = field(body, "brand_name")
        assert brand["application_value"] == "STONE'S THROW"
        assert brand["application_value_source"] == "parsed_from_form"
        assert brand["outcome"] == "match"

    def test_the_parsed_block_is_reported_in_its_own_right(self, sample_label_png):
        """FR-3's philosophy: surfaced for confirmation, never silently trusted."""
        body = post(sample_label_png, registry_pdf()).json()
        document = body["application_document"]
        assert document["extraction_path"] == "embedded_text"
        assert document["pages_read"] == 1
        assert document["class_type_code"] == "141"
        assert document["fanciful_name"] == "Small Batch Reserve"
        assert parsed_field(body, "net_contents")["value"] == "750 ML"

    def test_a_printout_that_never_names_a_product_type_reports_it_as_not_found(
        self, sample_label_png
    ):
        """A bourbon printout does not contain the words "distilled spirits".

        Item 5's three checkboxes are not on a registry printout at all, and
        inferring the product type from a class or type designation that never
        says it would be a guess. The agent chooses it, and the note says why.
        """
        body = post(sample_label_png, registry_pdf()).json()
        assert parsed_field(body, "beverage_type")["found_on_document"] is False
        assert any(
            "ticked box cannot be read" in note for note in body["application_document"]["notes"]
        )

    def test_a_value_the_document_did_not_carry_is_reported_as_not_found(self, sample_label_png):
        spec = ApplicationSpec(brand_name="STONE'S THROW", class_type="", alcohol_content="")
        body = post(sample_label_png, registry_pdf(spec)).json()
        entry = parsed_field(body, "alcohol_content")
        assert entry["found_on_document"] is False
        assert entry["value"] is None
        assert field(body, "alcohol_content")["application_value_source"] == "absent"
        assert field(body, "alcohol_content")["outcome"] == "not_compared"


class TestTypedValuesOverrideParsedOnes:
    """The precedence rule in ADR 0008, field by field."""

    def test_a_typed_field_wins_over_the_document(self, sample_label_png):
        body = post(
            sample_label_png, registry_pdf(), data={"brand_name": "A DIFFERENT BRAND"}
        ).json()
        brand = field(body, "brand_name")
        assert brand["application_value"] == "A DIFFERENT BRAND"
        assert brand["application_value_source"] == "typed"

    def test_the_fields_the_agent_left_alone_still_come_from_the_document(self, sample_label_png):
        body = post(
            sample_label_png, registry_pdf(), data={"brand_name": "A DIFFERENT BRAND"}
        ).json()
        assert field(body, "net_contents")["application_value"] == "750 ML"
        assert field(body, "net_contents")["application_value_source"] == "parsed_from_form"

    def test_the_document_block_still_reports_what_was_read_not_what_was_used(
        self, sample_label_png
    ):
        """An agent has to be able to see what they overrode."""
        body = post(
            sample_label_png, registry_pdf(), data={"brand_name": "A DIFFERENT BRAND"}
        ).json()
        assert parsed_field(body, "brand_name")["value"] == "STONE'S THROW"

    def test_an_empty_typed_field_is_not_treated_as_a_correction(self, sample_label_png):
        body = post(sample_label_png, registry_pdf(), data={"brand_name": "   "}).json()
        assert field(body, "brand_name")["application_value"] == "STONE'S THROW"
        assert field(body, "brand_name")["application_value_source"] == "parsed_from_form"


class TestRejections:
    """FR-9 and NFR-7 applied to the second upload."""

    def test_a_disallowed_document_type_is_refused_and_names_what_is_accepted(
        self, sample_label_png
    ):
        response = post(sample_label_png, b"brand,name\n", doc_type="text/csv")
        assert response.status_code == 415
        body = response.json()
        assert body["error"]["code"] == "unsupported_application_document"
        assert "application/pdf" in body["error"]["limit"]
        assert "fields" not in body

    def test_an_unreadable_document_says_so_and_offers_the_typed_path(self, sample_label_png):
        response = post(sample_label_png, b"this is not a pdf at all")
        assert response.status_code == 422
        body = response.json()
        assert body["error"]["code"] == "unreadable_application_document"
        assert "type the application values" in body["error"]["message"]

    def test_no_error_path_returns_a_match(self, sample_label_png):
        for response in (
            post(sample_label_png, b"this is not a pdf at all"),
            post(sample_label_png, b"", doc_type="application/pdf"),
            post(sample_label_png, b"x", doc_type="text/csv"),
        ):
            assert response.status_code >= 400
            assert "fields" not in response.json()
            assert "match" not in response.text

    def test_an_unreadable_label_is_still_the_label_error(self):
        """The document does not rescue a submission with no readable label."""
        response = post(b"not an image", registry_pdf())
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "unreadable_image"


class TestNothingSensitiveReachesTheLogs:
    """NFR-6: counts and a path name, never an item value."""

    def test_no_parsed_value_is_logged(self, sample_label_png, caplog):
        with caplog.at_level("INFO"):
            post(sample_label_png, registry_pdf())
        emitted = " ".join(record.getMessage() for record in caplog.records)
        emitted += " ".join(str(record.__dict__) for record in caplog.records)
        assert "STONE'S THROW" not in emitted
        assert "KENTUCKY STRAIGHT BOURBON WHISKEY" not in emitted
        assert "application.pdf" not in emitted


class TestReadApplicationOnItsOwn:
    """POST /api/read-application: parse the document, compare nothing (FR-11).

    The interface reads the document first so that the parsed values reach an
    agent as editable fields before any verification runs (ADR 0008).
    """

    def read(self, document: bytes, content_type="application/pdf"):
        return client.post(
            "/api/read-application",
            files={"application_document": ("application.pdf", document, content_type)},
        )

    def test_it_returns_the_parsed_block_and_no_field_outcomes(self):
        response = self.read(registry_pdf())
        assert response.status_code == 200
        body = response.json()
        assert "fields" in body
        assert "outcome" not in response.text
        assert body["extraction_path"] == "embedded_text"

    def test_every_application_value_is_reported_found_or_not(self):
        body = self.read(registry_pdf()).json()
        names = [entry["name"] for entry in body["fields"]]
        assert names == [
            "brand_name",
            "class_type",
            "alcohol_content",
            "net_contents",
            "beverage_type",
        ]

    def test_a_disallowed_type_is_refused_and_names_what_is_accepted(self):
        response = self.read(b"brand,name\n", content_type="text/csv")
        assert response.status_code == 415
        assert response.json()["error"]["code"] == "unsupported_application_document"

    def test_an_unreadable_document_says_so_and_offers_the_typed_path(self):
        response = self.read(b"not a pdf")
        assert response.status_code == 422
        assert "type the application values" in response.json()["error"]["message"]

    def test_no_parsed_value_reaches_the_logs(self, caplog):
        with caplog.at_level("INFO"):
            self.read(registry_pdf())
        emitted = " ".join(str(record.__dict__) for record in caplog.records)
        assert "STONE'S THROW" not in emitted
        assert "application.pdf" not in emitted
