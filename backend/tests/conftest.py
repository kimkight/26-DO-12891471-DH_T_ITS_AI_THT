"""Shared test fixtures.

The repository root is put on the import path so that tests can use
samples/labelmaker.py, which renders label artwork at test time. Nothing under
samples/ is part of the application or ships in the container image; it exists
so that no binary image file has to be committed (samples/README.md).
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from samples.labelmaker import LabelSpec, available_fonts, render_png_bytes  # noqa: E402
from samples.specs import SAMPLE_LABEL  # noqa: E402

# Tesseract is a system package rather than a Python one, so a checkout without
# it still runs the unit tier. docs/07_TEST_STRATEGY.md section 1 puts anything
# involving Tesseract in the integration and accuracy tiers for this reason.
requires_tesseract = pytest.mark.skipif(
    shutil.which("tesseract") is None,
    reason="Tesseract is not installed on this machine; this is an integration-tier test.",
)
requires_fonts = pytest.mark.skipif(
    available_fonts() is None,
    reason="No TrueType font is available to render label artwork with.",
)


@pytest.fixture
def sample_label_png() -> bytes:
    """The assignment's sample label, rendered at test time."""
    return render_png_bytes(SAMPLE_LABEL)


@pytest.fixture
def label_png():
    """Render an arbitrary label spec to PNG bytes."""

    def _render(**overrides) -> bytes:
        spec = LabelSpec(**{**SAMPLE_LABEL.__dict__, **overrides})
        return render_png_bytes(spec)

    return _render
