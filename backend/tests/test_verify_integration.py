"""End to end over POST /api/verify with real OCR against rendered artwork.

Covers docs/07_TEST_STRATEGY.md section 2 and UAT rows 1, 3, 7, 8 and 11.
Requirements: FR-1, FR-2, FR-3, FR-5, FR-6, FR-7, NFR-1, NFR-3.

The label is rendered with Pillow at test time rather than committed as a file,
because samples/README.md keeps label artwork out of the repository. The
latency figure this test prints is one measurement on one machine and is not a
published number; scripts/measure.py produces the reported set.
"""

import io
import logging
import socket
import time

import cv2
import numpy as np
import pytest
from fastapi.testclient import TestClient
from PIL import Image
from samples.specs import SAMPLE_LABEL, TITLE_CASE_WARNING
from samples.warning_text import WARNING_STATEMENT, hyphenated_column

from app.main import app
from app.ocr import decode
from tests.conftest import (
    photographic,
    png_bytes,
    png_with_exif_orientation,
    requires_fonts,
    requires_tesseract,
    stored_as_exif,
    upright_rgb,
)

client = TestClient(app)

FIVE_SECOND_TARGET = 5.0

pytestmark = [requires_tesseract, requires_fonts]


def verify(png: bytes, application: dict[str, str], content_type: str = "image/png"):
    suffix = "jpg" if content_type == "image/jpeg" else "png"
    return client.post(
        "/api/verify",
        files={"image": (f"label.{suffix}", png, content_type)},
        data=application,
    )


def turned_png(png: bytes, turns: int) -> bytes:
    """The same artwork photographed sideways: the pixels really are turned.

    ``np.rot90`` turns counter-clockwise, so ``turns`` quarter-turns need a
    clockwise correction of ``turns * 90`` degrees, which is the figure the
    response reports.
    """
    turned = np.ascontiguousarray(np.rot90(decode(png).pixels, turns))
    buffer = io.BytesIO()
    Image.fromarray(cv2.cvtColor(turned, cv2.COLOR_BGR2RGB)).save(buffer, format="PNG")
    return buffer.getvalue()


def exif_tagged_jpeg(png: bytes, orientation: int) -> bytes:
    """The same artwork as a phone would store it: sideways pixels plus a tag.

    Orientation 6 means "turn this 90 degrees clockwise to display it", so the
    pixels are turned counter-clockwise here and the tag records the way back.
    """
    sideways = np.ascontiguousarray(np.rot90(decode(png).pixels, 1))
    image = Image.fromarray(cv2.cvtColor(sideways, cv2.COLOR_BGR2RGB))
    exif = image.getexif()
    exif[0x0112] = orientation
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", exif=exif, quality=95)
    return buffer.getvalue()


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
        assert record.photos_received == 1
        assert isinstance(record.ocr_ms, float)
        assert record.beverage_type_supplied is True

        # An allow-list rather than a search, because this is the one record the
        # verification path writes and NFR-6 is a statement about what may be in
        # it. A new field added here has to be added to this list deliberately.
        standard = set(logging.LogRecord("", 0, "", 0, "", None, None).__dict__)
        added = set(record.__dict__) - standard - {"taskName", "asctime", "message"}
        assert added == {
            "bytes_received",
            "photos_received",
            "ocr_ms",
            "beverage_type_supplied",
            # FR-11 added two. Both are a count and a path name; neither can
            # carry an item value, a filename or anything the document said.
            "application_document_bytes",
            "application_document_path",
            # ADR 0010 added one. It is one of two fixed strings naming where
            # the label side came from, and cannot carry anything the document
            # or the artwork said.
            "label_source",
        }
        assert record.application_document_bytes == 0
        assert record.application_document_path is None


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


def exif_tagged_png(image_bytes: bytes, orientation: int) -> bytes:
    """The artwork stored the way a file carrying ``orientation`` stores it.

    The pixels are put through the inverse of the transform a viewer applies,
    which makes the fixture the file a camera writing that tag would have
    written, rather than upright pixels with a tag bolted on.
    """
    stored = stored_as_exif(upright_rgb(image_bytes), orientation)
    return png_with_exif_orientation(stored, orientation)


def photographic_png(image_bytes: bytes) -> bytes:
    """The artwork degraded into something shaped like a phone photograph."""
    return png_bytes(photographic(upright_rgb(image_bytes)))


class TestTheKetelOneHotfix:
    """The 2026-08-28 submission, reproduced against the API (UAT rows 54 to 56).

    A photograph of a real back label, flagged by the interface as saved
    sideways by the camera, returned no government warning and brand-name
    shrapnel from the fine print. A controlled experiment against the deployed
    URL narrowed it to two things, and this class holds both to account through
    the HTTP contract rather than only at the unit tier.
    """

    @pytest.mark.parametrize("orientation", [1, 2, 3, 4, 5, 6, 7, 8])
    def test_every_exif_orientation_returns_the_same_field_outcomes(
        self, sample_label_png, orientation
    ):
        """UAT row 55. Eight values, and phones write several of them."""
        body = verify(
            exif_tagged_png(sample_label_png, orientation),
            SAMPLE_LABEL.application,
        ).json()

        photo = body["photos"][0]
        assert photo["orientation"]["exif_orientation"] == orientation
        assert photo["orientation"]["exif_transposed"] is (orientation != 1)
        assert photo["orientation"]["rotation_degrees"] == 0
        outcomes = {field["name"]: field["outcome"] for field in body["fields"]}
        assert outcomes["government_warning"] == "match"
        assert outcomes["brand_name"] == "match"
        assert outcomes["net_contents"] == "match"

    def test_a_tag_that_lies_about_its_pixels_is_caught_and_reported(self, sample_label_png):
        """UAT row 56. The tag says sideways, the pixels are upright.

        An edit that turns the pixels can leave the tag behind, so applying the
        tag is what breaks the image. The quarter-turn check runs regardless of
        whether a tag was applied, which is what rescues this, and the response
        reports all three figures so the disagreement is visible rather than
        silently absorbed.
        """
        lying = png_with_exif_orientation(upright_rgb(sample_label_png), orientation=6)

        body = verify(lying, SAMPLE_LABEL.application).json()

        photo = body["photos"][0]
        assert photo["orientation"]["exif_orientation"] == 6
        assert photo["orientation"]["exif_transposed"] is True
        assert photo["orientation"]["rotation_degrees"] == 270
        outcomes = {field["name"]: field["outcome"] for field in body["fields"]}
        assert outcomes["government_warning"] == "match"

    def test_a_photograph_like_image_keeps_the_read_preprocessing_would_have_lost(
        self, sample_label_png
    ):
        """UAT row 54. Preprocessing must not be able to make it worse."""
        body = verify(photographic_png(sample_label_png), SAMPLE_LABEL.application).json()

        photo = body["photos"][0]
        assert photo["text_found"] is True
        assert photo["read_path"]["variant"] == "plain"
        read_path = photo["read_path"]
        assert read_path["plain_confidence"] > read_path["preprocessed_confidence"]
        outcomes = {field["name"]: field["outcome"] for field in body["fields"]}
        assert outcomes["government_warning"] == "match"

    def test_the_exif_variant_matches_the_upright_one_on_the_same_photograph(
        self, sample_label_png
    ):
        """The controlled experiment itself: identical pixels, one of them tagged.

        The deployed build returned no warning from the upright file and no text
        at all from the tagged one.
        """
        soft = photographic_png(sample_label_png)
        upright_body = verify(soft, SAMPLE_LABEL.application).json()
        tagged_body = verify(exif_tagged_png(soft, 6), SAMPLE_LABEL.application).json()

        upright_outcomes = {f["name"]: f["outcome"] for f in upright_body["fields"]}
        tagged_outcomes = {f["name"]: f["outcome"] for f in tagged_body["fields"]}
        assert upright_outcomes["government_warning"] == "match"
        assert tagged_outcomes == upright_outcomes
        assert tagged_body["photos"][0]["orientation"]["rotation_degrees"] == 0


class TestASidewaysPhotograph:
    """The first real-artwork failure, end to end (UAT rows 23 and 24).

    A photograph of a real bottle was submitted to the deployed prototype and
    none of the five fields were found. Two things were wrong: the photograph
    was turned a quarter-turn, and phone photographs carry the turn in an EXIF
    tag that OpenCV drops on decode. Both are reproduced here against the API.
    """

    @pytest.mark.parametrize("turns", [1, 2, 3])
    def test_a_turned_photograph_returns_its_fields_and_says_it_was_turned(
        self, sample_label_png, turns
    ):
        turned = turned_png(sample_label_png, turns)
        body = verify(turned, SAMPLE_LABEL.application).json()

        assert body["photos"][0]["orientation"]["rotation_degrees"] == turns * 90
        assert body["photos"][0]["orientation"]["method"] == "osd"
        outcomes = {field["name"]: field["outcome"] for field in body["fields"]}
        assert outcomes["brand_name"] == "match"
        assert outcomes["alcohol_content"] == "match"
        assert outcomes["net_contents"] == "match"
        assert outcomes["government_warning"] == "match"

    def test_a_photograph_whose_turn_is_only_in_its_exif_tag_reads_the_same(self, sample_label_png):
        """The pixels are stored sideways and the tag says so. Before this
        change the tag was ignored and the pipeline read the sideways pixels."""
        tagged = exif_tagged_jpeg(sample_label_png, orientation=6)
        body = verify(tagged, SAMPLE_LABEL.application, content_type="image/jpeg").json()

        assert body["photos"][0]["orientation"]["exif_transposed"] is True
        assert body["photos"][0]["orientation"]["rotation_degrees"] == 0
        outcomes = {field["name"]: field["outcome"] for field in body["fields"]}
        assert outcomes["brand_name"] == "match"
        assert outcomes["government_warning"] == "match"

    def test_an_upright_photograph_reports_that_nothing_was_turned(self, sample_label_png):
        body = verify(sample_label_png, SAMPLE_LABEL.application).json()
        assert len(body["photos"]) == 1
        photo = body["photos"][0]
        assert photo["index"] == 1
        assert photo["text_found"] is True
        assert photo["error"] is None
        assert photo["orientation"]["exif_transposed"] is False
        assert photo["orientation"]["rotation_degrees"] == 0
        assert photo["orientation"]["method"] == "osd"

    def test_the_turn_is_still_within_the_five_second_target(self, sample_label_png, capsys):
        """NFR-1. Orientation detection is a second pass over the image, so the
        budget is re-measured rather than assumed to still hold."""
        turned = turned_png(sample_label_png, 1)
        started = time.perf_counter()
        response = verify(turned, SAMPLE_LABEL.application)
        elapsed = time.perf_counter() - started

        assert response.status_code == 200
        with capsys.disabled():
            print(
                f"\nMeasured single-label verification of a turned photograph: "
                f"{elapsed:.2f} s end to end "
                f"({response.json()['ocr_ms']:.0f} ms of it in decode, orientation, "
                f"preprocessing and OCR). Target is about {FIVE_SECOND_TARGET:.0f} s "
                "(NFR-1). Measured on this runner, not on production hardware."
            )
        assert elapsed < FIVE_SECOND_TARGET


class TestAHyphenatedWarningColumn:
    """UAT row 25 and assumption A-15, end to end.

    A real bottle sets the warning in a column a few words wide and hyphenates
    to fill it. Before this change the split words read as altered wording and a
    compliant label reported a mismatch.
    """

    def test_a_narrow_hyphenated_column_reports_a_match(self, label_png):
        png = label_png(warning=hyphenated_column())
        body = verify(png, SAMPLE_LABEL.application).json()

        warning = next(f for f in body["fields"] if f["name"] == "government_warning")
        assert body["warning_detail"]["statement_found"] is True
        assert body["warning_detail"]["prefix_is_capitalized"] is True
        assert body["warning_detail"]["body_matches_regulation"] is True
        assert warning["outcome"] == "match"

    def test_an_altered_word_in_a_hyphenated_column_still_reports_a_mismatch(self, label_png):
        """FR-5 is unchanged. The join widens what counts as the same wording,
        not what counts as a match."""
        altered = hyphenated_column(
            WARNING_STATEMENT.replace("should not drink", "should avoid drinking")
        )
        body = verify(label_png(warning=altered), SAMPLE_LABEL.application).json()

        warning = next(f for f in body["fields"] if f["name"] == "government_warning")
        assert body["warning_detail"]["body_matches_regulation"] is False
        assert warning["outcome"] == "mismatch"
