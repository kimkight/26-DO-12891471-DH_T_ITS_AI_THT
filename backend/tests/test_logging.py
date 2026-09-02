"""The application's own logger emits, at the configured level, under uvicorn.

Code review finding 9 (#108): nothing configured the root logger, uvicorn's
default configuration attaches handlers to its own loggers only, so every
`logger.info` in `app.*` was discarded and `TTB_LOG_LEVEL` did nothing. The
test that certified the completion record passed because `caplog` installs its
own handler at DEBUG, so it could not tell.

These tests run the real configuration. The first class drives
`configure_logging` with a stream of its own; the last one starts a real
uvicorn process, because "emits under uvicorn" is a claim about that process
and not about this one. NFR-6 is asserted on the same output: the uploaded
filename and the values never reach a line the handler wrote.

Requirements: NFR-6, NFR-11. The fixture is rendered at test time and carries
invented values only (docs/07_TEST_STRATEGY.md section 8).
"""

from __future__ import annotations

import io
import json
import logging
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient
from samples.specs import SAMPLE_LABEL

from app.config import settings
from app.logging_config import APP_LOGGER, configure_logging
from app.main import app
from tests.conftest import requires_fonts, requires_tesseract

BACKEND = Path(__file__).resolve().parents[1]

# A filename an agent might give a real file, and which must never be logged.
UNLOGGED_FILENAME = "applicant-private-filing-7391.png"


@pytest.fixture
def json_log() -> io.StringIO:
    """The real handler, writing to a stream this test owns; restored afterwards."""
    stream = io.StringIO()
    configure_logging("INFO", stream)
    yield stream
    configure_logging(settings.log_level)


def records(stream: io.StringIO) -> list[dict]:
    return [json.loads(line) for line in stream.getvalue().splitlines() if line.strip()]


class TestTheConfiguration:
    def test_an_info_record_is_written_as_one_json_line_with_its_extras(self, json_log):
        logging.getLogger("app.somewhere").info("something happened", extra={"count": 3})

        written = records(json_log)
        assert len(written) == 1
        assert written[0]["message"] == "something happened"
        assert written[0]["level"] == "INFO"
        assert written[0]["logger"] == "app.somewhere"
        assert written[0]["count"] == 3

    def test_the_configured_level_is_the_level(self):
        stream = io.StringIO()
        configure_logging("WARNING", stream)
        try:
            logging.getLogger("app.somewhere").info("dropped")
            logging.getLogger("app.somewhere").warning("kept")
        finally:
            configure_logging(settings.log_level)

        assert [record["message"] for record in records(stream)] == ["kept"]

    def test_an_unknown_level_falls_back_to_info_and_says_so(self):
        stream = io.StringIO()
        configure_logging("LOUD", stream)
        try:
            logging.getLogger("app.somewhere").info("still written")
        finally:
            configure_logging(settings.log_level)

        written = records(stream)
        assert written[0]["message"] == "unrecognised log level, using INFO"
        assert written[0]["configured_level"] == "LOUD"
        assert written[1]["message"] == "still written"
        assert logging.getLogger(APP_LOGGER).level == logging.INFO

    def test_reconfiguring_replaces_the_handler_rather_than_stacking_one(self):
        first, second = io.StringIO(), io.StringIO()
        configure_logging("INFO", first)
        configure_logging("INFO", second)
        try:
            logging.getLogger("app.somewhere").info("once")
        finally:
            configure_logging(settings.log_level)

        assert first.getvalue() == ""
        assert len(records(second)) == 1

    def test_the_exception_is_rendered_and_nothing_else_is_lost(self, json_log):
        try:
            raise ValueError("boom")
        except ValueError:
            logging.getLogger("app.somewhere").exception("row failed", extra={"row": 4})

        written = records(json_log)
        assert written[0]["row"] == 4
        assert "ValueError: boom" in written[0]["exception"]


@requires_tesseract
@requires_fonts
class TestTheCompletionRecordReachesTheHandler:
    """The record the runbook reads for `ocr_ms`, through the real handler."""

    def test_a_verification_writes_its_completion_record(self, sample_label_png, json_log):
        client = TestClient(app)
        response = client.post(
            "/api/verify",
            files={"files": (UNLOGGED_FILENAME, sample_label_png, "image/png")},
            data=SAMPLE_LABEL.application,
        )
        assert response.status_code == 200

        completions = [r for r in records(json_log) if r["message"] == "verification completed"]
        assert len(completions) == 1
        assert isinstance(completions[0]["ocr_ms"], float)
        assert completions[0]["photos_received"] == 1

    def test_no_filename_or_value_reaches_a_line_the_handler_wrote(
        self, sample_label_png, json_log
    ):
        client = TestClient(app)
        client.post(
            "/api/verify",
            files={"files": (UNLOGGED_FILENAME, sample_label_png, "image/png")},
            data=SAMPLE_LABEL.application,
        )

        written = json_log.getvalue()
        assert "verification completed" in written, "the guard should be checking real output"
        assert UNLOGGED_FILENAME not in written
        assert "applicant-private" not in written
        for value in (SAMPLE_LABEL.brand_name, SAMPLE_LABEL.class_type, "GOVERNMENT WARNING"):
            assert value not in written, f"{value!r} reached the log"


def _free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


@requires_tesseract
@requires_fonts
class TestUnderUvicorn:
    """The claim as the review tested it: a real uvicorn process, its stderr read.

    This is the test that could not exist before finding 9 was fixed, and it
    was watched go red with the configuration call removed from `app.main`
    before it was committed.
    """

    @pytest.mark.parametrize(
        ("level", "expected"),
        [("INFO", True), ("WARNING", False)],
        ids=["INFO emits the record", "WARNING withholds it"],
    )
    def test_the_completion_record_is_written_by_the_process(
        self, sample_label_png, level, expected
    ):
        port = _free_port()
        env = {**os.environ, "TTB_LOG_LEVEL": level}
        process = subprocess.Popen(  # noqa: S603 - the command is this interpreter and this app
            [
                sys.executable,
                "-m",
                "uvicorn",
                "app.main:app",
                "--host",
                "127.0.0.1",
                "--port",
                str(port),
                "--log-level",
                "warning",
            ],
            cwd=BACKEND,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        try:
            base = f"http://127.0.0.1:{port}"
            deadline = time.monotonic() + 90
            while True:
                try:
                    if httpx.get(f"{base}/api/health", timeout=2).status_code == 200:
                        break
                except httpx.HTTPError:
                    pass
                assert time.monotonic() < deadline, "uvicorn did not start in time"
                assert process.poll() is None, "uvicorn exited before it answered"
                time.sleep(0.25)

            response = httpx.post(
                f"{base}/api/verify",
                files={"files": (UNLOGGED_FILENAME, sample_label_png, "image/png")},
                data=SAMPLE_LABEL.application,
                timeout=120,
            )
            assert response.status_code == 200, response.text
        finally:
            process.terminate()
            stdout, stderr = process.communicate(timeout=30)

        output = stdout + stderr
        completions = [
            json.loads(line)
            for line in output.splitlines()
            if line.startswith("{") and '"verification completed"' in line
        ]
        assert bool(completions) is expected, output[-2000:]
        if expected:
            assert isinstance(completions[0]["ocr_ms"], float)
            assert completions[0]["level"] == "INFO"
        # NFR-6, on the process's real output rather than on a test handler.
        assert UNLOGGED_FILENAME not in output
        assert SAMPLE_LABEL.brand_name not in output
