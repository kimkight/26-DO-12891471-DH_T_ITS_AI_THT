"""Logging that emits: one JSON line per record from the application's own logger.

Governing requirements: NFR-6 (no image content, filename or extracted value in
a log line; what is logged is counts, timings and path names), NFR-11 (the
level is configuration, `TTB_LOG_LEVEL`).

**Why this module exists.** Until v1.3.0 nothing configured the application's
logging. Uvicorn's default configuration attaches handlers to its own three
loggers and leaves the root logger at WARNING with no handler, so every
`logger.info` in `app.*` was discarded, the `ocr_ms` figure the deployment
runbook told an operator to read from CloudWatch was never written, and
`TTB_LOG_LEVEL` was read by nothing (code review finding 9). The test that
certified the completion record passed because `caplog` installs its own
handler at DEBUG. `TestLoggingEmits` in `tests/test_logging.py` now runs the
real configuration, including once under a real uvicorn process.

**The shape.** One handler on the `app` logger, writing one JSON object per
record to stderr, which is where the container's log driver reads. The
`extra` fields a call site attaches are rendered as top-level keys, so a
record reads as `{"level": "INFO", "message": "verification completed",
"ocr_ms": 1234.5, ...}` rather than as a message with its figures dropped,
which is what Python's last-resort handler did with the warnings that did get
out. Records still propagate to the root logger, so a test's `caplog` sees
them; under uvicorn the root has no handler and nothing is written twice.
"""

from __future__ import annotations

import json
import logging
import sys
from typing import IO

__all__ = ["APP_LOGGER", "JsonFormatter", "configure_logging"]

# The logger every module in this package logs through, by the package name.
# `logging.getLogger(__name__)` in `app.api` yields `app.api`, a child of it.
APP_LOGGER = "app"

# The attributes every LogRecord carries. Anything else on a record is an
# `extra` the call site attached, and is what the formatter renders.
_STANDARD_ATTRIBUTES = frozenset(logging.LogRecord("", 0, "", 0, "", None, None).__dict__) | {
    "asctime",
    "message",
    "taskName",
}


class JsonFormatter(logging.Formatter):
    """One JSON object per record, with the call site's `extra` fields as keys."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "time": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for key, value in record.__dict__.items():
            if key not in _STANDARD_ATTRIBUTES:
                payload[key] = value
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        # `default=str` so that a value the call site attached which is not
        # JSON-native (a Path, an enum) is written as its text rather than
        # taking the record down. NFR-6 is kept by the call sites, which attach
        # counts, timings and path names only.
        return json.dumps(payload, default=str)


def configure_logging(level: str, stream: IO[str] | None = None) -> logging.Logger:
    """Attach the JSON handler to the `app` logger at ``level``, and return it.

    Idempotent: a second call replaces the handler this module installed rather
    than adding another, so a test that reconfigures with its own stream does
    not leave two handlers writing. An unrecognised level name falls back to
    INFO and says so in the first record written, rather than refusing to start
    over a typo in an environment variable (NFR-11).
    """
    logger = logging.getLogger(APP_LOGGER)
    for handler in list(logger.handlers):
        if getattr(handler, "ttb_installed", False):
            logger.removeHandler(handler)

    handler = logging.StreamHandler(stream if stream is not None else sys.stderr)
    handler.ttb_installed = True  # type: ignore[attr-defined]
    handler.setFormatter(JsonFormatter())
    logger.addHandler(handler)

    resolved = logging.getLevelNamesMapping().get(level.strip().upper())
    logger.setLevel(resolved if resolved is not None else logging.INFO)
    logger.propagate = True
    if resolved is None:
        logger.warning(
            "unrecognised log level, using INFO",
            extra={"configured_level": level},
        )
    return logger
