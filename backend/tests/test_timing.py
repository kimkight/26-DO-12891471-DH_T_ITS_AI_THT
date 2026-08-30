"""elapsed_ms is elapsed, the phases are measured, and the picture is read once.

NFR-1. The author measured the deployed v1.1.0 build on 2026-08-30 with their
own mezcal COLA PDF, submitted alone, three runs from the browser:

    run   wall clock   server elapsed_ms   server ocr_ms
    1        6883 ms            3323 ms         3321 ms
    2        6786 ms            3214 ms         3213 ms
    3        6781 ms            3198 ms         3196 ms

`elapsed_ms` and `ocr_ms` are within 2 ms of each other in every run, because
`elapsed_ms` was measuring the label-side OCR span and calling itself the
request. Two control measurements from the same page and session bound what the
network could have been: `GET /api/health` round-tripped in 18 to 25 ms, and a
POST of the identical 382 KB file to a path that processes nothing took 68 to
111 ms. So roughly three and a half seconds of real server work per request was
both missing from the instrumentation and reported by the interface as "sending
the image and receiving the answer".

These tests are the three claims that fixes it: the clock covers the handler,
the phases are measured rather than inferred, and the picture chosen as the
label side is read once rather than twice.
"""

from __future__ import annotations

import io
import sys
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from PIL import Image

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from samples.formmaker import (  # noqa: E402
    ApplicationSpec,
    as_pdf_bytes,
    paper_form_lines,
)
from samples.labelmaker import render_png_bytes  # noqa: E402
from samples.specs import SAMPLE_LABEL  # noqa: E402

from app import timing  # noqa: E402
from app.main import app  # noqa: E402
from tests.conftest import requires_fonts, requires_tesseract  # noqa: E402

client = TestClient(app)


@pytest.fixture(scope="module")
def artwork() -> bytes:
    return render_png_bytes(SAMPLE_LABEL)


@pytest.fixture(scope="module")
def second_artwork(artwork: bytes) -> bytes:
    """A smaller second picture, so a document has more than one candidate."""
    image = Image.open(io.BytesIO(artwork))
    smaller = image.resize((image.width // 2, image.height // 2))
    buffer = io.BytesIO()
    smaller.save(buffer, format="PNG")
    return buffer.getvalue()


def document(images: list[bytes]) -> bytes:
    return as_pdf_bytes(paper_form_lines(ApplicationSpec()), images=images)


def verify(pdf: bytes) -> tuple[dict, float]:
    """One submission through the real route, with the wall clock beside it."""
    started = time.perf_counter()
    response = client.post("/api/verify", files=[("files", ("cola.pdf", pdf, "application/pdf"))])
    wall_ms = (time.perf_counter() - started) * 1000
    assert response.status_code == 200, response.text
    return response.json(), wall_ms


class TestTheRecorderItself:
    """Unit tier: the mechanism, with no OCR anywhere near it."""

    def test_phases_outside_a_recording_are_a_no_op(self):
        """scripts/measure.py and every comparison test call into this path."""
        assert timing.current() is None
        with timing.phase("label_ocr"):
            pass
        assert timing.current() is None

    def test_a_recording_accumulates_by_phase_and_counts_the_spans(self):
        with timing.recording() as record:
            for _ in range(3):
                with timing.phase("artwork_ocr"):
                    time.sleep(0.01)
            with timing.phase("compare"):
                pass
        assert record.count("artwork_ocr") == 3
        assert record.get("artwork_ocr") >= 25
        assert record.count("compare") == 1

    def test_ocr_totals_cover_every_reading_phase_and_nothing_else(self):
        with timing.recording() as record:
            with timing.phase("artwork_ocr"):
                time.sleep(0.01)
            with timing.phase("label_ocr"):
                time.sleep(0.01)
            with timing.phase("document_pdfium"):
                time.sleep(0.01)
        # PDFium is not Tesseract, so it is not in ocr_ms; it is in the
        # accounted total, because it is real work that really happened.
        assert record.ocr_passes == 2
        assert record.ocr_ms < record.accounted_ms
        assert record.get("document_pdfium") >= 5

    def test_a_recording_does_not_leak_into_the_next_one(self):
        with timing.recording() as first, timing.phase("compare"):
            pass
        with timing.recording() as second:
            pass
        assert first.count("compare") == 1
        assert second.count("compare") == 0
        assert timing.current() is None


@requires_tesseract
@requires_fonts
class TestElapsedIsElapsed:
    """The defect, stated as the assertion that would have caught it."""

    def test_elapsed_ms_is_not_the_ocr_span(self, artwork):
        """The two used to be within 2 ms of each other on every run.

        They are allowed to be close on a path where OCR really is almost all of
        the work; what they may not be is equal, because `elapsed_ms` now
        includes parsing the PDF and lifting the picture out of it, and those
        take measurable time.
        """
        body, _ = verify(document([artwork]))
        assert body["elapsed_ms"] > body["ocr_ms"]
        assert body["timings"]["document_pdfium_ms"] > 0

    def test_elapsed_ms_covers_the_whole_handler(self, artwork):
        """Measured against the wall clock the test client itself sees.

        The gap between them is the test client and the ASGI plumbing, which is
        tens of milliseconds. Before this change the gap was the whole of the
        document-reading half of the request.
        """
        body, wall_ms = verify(document([artwork]))
        assert body["elapsed_ms"] <= wall_ms
        assert body["elapsed_ms"] > wall_ms * 0.8

    def test_the_phases_account_for_the_time_rather_than_leaving_it_over(self, artwork):
        """`unaccounted_ms` is the one subtraction, and it should be small.

        A large unaccounted figure would mean a phase is missing, which is the
        state this replaced. It is asserted as a fraction rather than as a
        constant so the test says "almost all of it was attributed" rather than
        pinning a number to this machine.
        """
        body, _ = verify(document([artwork]))
        timings = body["timings"]
        assert timings["accounted_ms"] > timings["total_ms"] * 0.9
        assert timings["unaccounted_ms"] == pytest.approx(
            timings["total_ms"] - timings["accounted_ms"], abs=1.0
        )

    def test_every_phase_is_reported_even_where_it_did_no_work(self, artwork):
        """A path not taken reports zero rather than being absent.

        A missing key and a zero are different things to a reader, and only one
        of them says "this step ran and cost nothing".
        """
        body, _ = verify(document([artwork]))
        for name in (
            "classify_ocr_ms",
            "document_pdfium_ms",
            "document_ocr_ms",
            "page_ocr_ms",
            "artwork_ocr_ms",
            "label_ocr_ms",
            "compare_ms",
            "ocr_ms",
            "ocr_passes",
            "tesseract_reads",
            "accounted_ms",
            "unaccounted_ms",
            "total_ms",
        ):
            assert name in body["timings"], name


@requires_tesseract
@requires_fonts
class TestThePictureIsReadOnce:
    """The finding the instrumentation turned up, and the fix for it."""

    def test_the_label_side_reuses_the_read_the_artwork_pass_already_did(self, artwork):
        """One picture, one Tesseract pass.

        It used to be two: `parse_application_document` read the picture to fill
        the application values, and the label side then read the identical bytes
        through the identical pipeline. On the author's deployed measurement
        that second pass was about 3.3 seconds for a result already in memory.
        """
        body, _ = verify(document([artwork]))

        assert body["label_source"] == "application_artwork"
        assert body["timings"]["ocr_passes"] == 1
        assert body["timings"]["artwork_ocr_ms"] > 0
        assert body["timings"]["label_ocr_ms"] == 0

    def test_the_engine_invocations_inside_that_pass_are_counted_too(self, artwork):
        """One pass is not one invocation, and the response says both (v1.1.0).

        A pass is one picture read end to end; a read is one call into
        Tesseract. The arms added in v1.1.0 all happen inside a pass, so a
        release that tripled the engine calls would leave `ocr_passes` at 1 and
        nothing would show it. That is the same class of mistake the 2026-08-30
        finding was, which is what this module exists for.
        """
        body, _ = verify(document([artwork]))

        timings = body["timings"]
        assert timings["tesseract_reads"] >= timings["ocr_passes"]
        # The orientation call plus at least one image read, per picture read.
        assert timings["tesseract_reads"] >= 2

    def test_the_reused_read_produces_the_same_answers(self, artwork):
        """Reuse is only worth having if it changes nothing but the clock."""
        body, _ = verify(document([artwork]))
        by_name = {field["name"]: field for field in body["fields"]}

        assert by_name["alcohol_content"]["label_value"]
        assert by_name["net_contents"]["label_value"]
        assert body["ocr_confidence"] > 0
        assert body["photos"][0]["origin"] == "application_artwork"
        assert body["photos"][0]["text_found"] is True

    def test_reading_stops_once_every_value_has_been_found(self, artwork, second_artwork):
        """A second picture that cannot add anything is not read.

        The values are taken in size order and never overwritten, so once all
        four are in hand a further pass cannot change one thing in the response.
        Before this it cost a full second on this runner and about three on the
        deployed target.
        """
        body, _ = verify(document([artwork, second_artwork]))
        document_block = body["application_document"]

        assert document_block["artwork_images_found"] == 2
        assert document_block["artwork_images_read"] == 1
        assert body["timings"]["ocr_passes"] == 1

    def test_a_picture_that_answers_only_part_is_still_followed_by_the_next(
        self, artwork, second_artwork
    ):
        """The front-and-back case ADR 0010 reads several pictures for.

        The largest picture carries no net contents, so the reading must go on
        to the next one. This is the case the early exit must not break, and it
        is asserted rather than argued.
        """
        from dataclasses import replace

        front = render_png_bytes(replace(SAMPLE_LABEL, net_contents=""))
        body, _ = verify(document([front, second_artwork]))

        assert body["application_document"]["artwork_images_read"] == 2
        assert body["timings"]["ocr_passes"] == 2
        net_contents = next(field for field in body["fields"] if field["name"] == "net_contents")
        # Filled from the second picture, which is what the extra pass bought.
        assert net_contents["application_value"]


@requires_tesseract
@requires_fonts
class TestTheBatchPathTimesEachRowSeparately:
    """One recording per row, not a share of the batch's wall clock."""

    def test_each_line_carries_its_own_phases(self, artwork):
        pdf = document([artwork])
        files = [
            ("images", ("a.png", artwork, "image/png")),
            ("images", ("b.png", artwork, "image/png")),
            ("application_documents", ("a.pdf", pdf, "application/pdf")),
            ("application_documents", ("b.pdf", pdf, "application/pdf")),
        ]
        response = client.post("/api/verify-batch", files=files)
        assert response.status_code == 200

        import json

        results = [json.loads(line)["result"] for line in response.text.splitlines()]
        assert len(results) == 2
        for result in results:
            timings = result["timings"]
            assert timings is not None
            # A row's own work, not the batch's: two rows running in parallel
            # would each report the batch's wall clock if the recording were
            # shared, which is the bug this shape prevents.
            assert timings["total_ms"] > 0
            assert timings["ocr_passes"] >= 1
            assert timings["accounted_ms"] > timings["total_ms"] * 0.8
