"""Validation and error handling on POST /api/verify.

Covers docs/07_TEST_STRATEGY.md section 1 row "Validation" and section 2's
error cases, and UAT row 6. Requirements: FR-9, NFR-7, NFR-3.

None of these tests needs Tesseract: every one of them is a rejection that
happens before any decoding, or a decode that fails.
"""

import io

from fastapi.testclient import TestClient
from PIL import Image

from app.config import settings
from app.main import app

client = TestClient(app)

APPLICATION_DATA = {
    "brand_name": "Stone's Throw",
    "class_type": "Kentucky Straight Bourbon Whiskey",
    "alcohol_content": "45",
    "net_contents": "750 mL",
    "beverage_type": "distilled spirits",
}


def blank_png(size=(80, 80)) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", size, (255, 255, 255)).save(buffer, format="PNG")
    return buffer.getvalue()


def post(content: bytes, filename="label.png", content_type="image/png"):
    return client.post(
        "/api/verify",
        files={"image": (filename, content, content_type)},
        data=APPLICATION_DATA,
    )


class TestNoErrorPathReturnsAMatch:
    """FR-9's last criterion, asserted against every error path at once."""

    def test_error_bodies_carry_no_field_outcomes_at_all(self):
        responses = [
            post(b"this is not an image", filename="label.png"),
            post(blank_png(), content_type="application/pdf"),
            post(b""),
        ]
        for response in responses:
            assert response.status_code >= 400
            body = response.json()
            assert "fields" not in body
            assert "match" not in response.text


class TestDisallowedType:
    """What the one upload accepts, and what it still refuses (FR-12, NFR-7).

    **A PDF is no longer a disallowed type here, and that is the change.**
    Before FR-12 the single-label route took label images in one part and the
    application in another, so a PDF arriving in the image part was refused as
    the wrong kind of file. There is now one part that takes both, and the
    server decides what a file is from the file (ADR 0011). What is still
    refused, before anything is decoded, is a type on neither list.
    """

    def test_a_type_on_neither_list_is_rejected_and_names_the_accepted_set(self):
        response = post(b"plain text", filename="notes.txt", content_type="text/plain")
        assert response.status_code == 415
        error = response.json()["error"]
        assert error["code"] == "unsupported_application_document"
        for mime_type in (*settings.allowed_mime_types, "application/pdf"):
            assert mime_type in error["limit"]

    def test_a_pdf_is_accepted_and_read_as_the_application(self):
        """Not a rejection any more. It is a file that failed to open as a PDF.

        The bytes here are a PNG declared as `application/pdf`, so the
        classifier takes the declared type at its word, the application parser
        tries to open it, and it fails. The message is about a document that
        could not be read rather than about a type that is not accepted, which
        is the honest one: the type is accepted now.
        """
        response = post(blank_png(), filename="label.pdf", content_type="application/pdf")
        assert response.status_code == 422
        error = response.json()["error"]
        assert error["code"] == "unreadable_application_document"
        assert "fields" not in response.json()


class TestOversize:
    def test_an_oversize_upload_is_rejected_and_names_the_limit(self):
        oversize = b"\x00" * (settings.max_upload_bytes + 1024)
        response = post(oversize)
        assert response.status_code == 413
        error = response.json()["error"]
        assert error["code"] == "file_too_large"
        assert str(settings.max_upload_bytes) in error["limit"]

    def test_the_rejection_happens_from_the_declared_length(self):
        """NFR-7: the size check reads Content-Length, before the body is read.

        Measured against the route's envelope limit, which is
        TTB_MAX_LABEL_PHOTOS times TTB_MAX_UPLOAD_BYTES since ADR 0007: the
        route accepts up to three photographs of one label, so bounding the
        envelope at one image would reject every two-photograph submission. Each
        photograph is still checked exactly against TTB_MAX_UPLOAD_BYTES after
        parsing, which is the case above.
        """
        response = client.post(
            "/api/verify",
            content=b"\x00" * (settings.effective_max_verify_bytes + 1024),
            headers={"content-type": "multipart/form-data; boundary=x"},
        )
        assert response.status_code == 413
        assert response.json()["error"]["code"] == "file_too_large"


class TestUnreadableImage:
    def test_a_corrupt_file_says_the_image_could_not_be_read(self):
        """UAT row 6."""
        response = post(b"GIF89a not really a gif at all")
        assert response.status_code == 422
        error = response.json()["error"]
        assert error["code"] == "unreadable_image"
        assert "could not be decoded" in error["message"]

    def test_an_empty_file_is_reported_as_unreadable(self):
        response = post(b"")
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "unreadable_image"


class TestNoTextFound:
    def test_a_blank_image_is_distinct_from_fields_not_matching(self):
        """FR-9: no text found and fields did not match are different messages."""
        response = post(blank_png(size=(400, 400)))
        assert response.status_code == 422
        error = response.json()["error"]
        assert error["code"] == "no_text_found"
        assert "not the same as the fields failing to match" in error["message"]


class TestHealthEndpointStillWorks:
    def test_mounting_the_verification_router_did_not_disturb_health(self):
        assert client.get("/api/health").status_code == 200
