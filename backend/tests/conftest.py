"""Shared test fixtures.

The repository root is put on the import path so that tests can use
samples/labelmaker.py, which renders label artwork at test time. Nothing under
samples/ is part of the application or ships in the container image; it exists
so that no binary image file has to be committed (samples/README.md).
"""

from __future__ import annotations

import io
import shutil
import sys
from pathlib import Path

import numpy as np
import pytest
from PIL import Image, ImageFilter

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


# How a file carrying each EXIF orientation value stores its pixels: the inverse
# of the transform a viewer applies. A fixture built this way is the file a
# camera writing that tag would have written, which is the case the hotfix in
# v1.0.1 exists for. The mirrored values and the two transposes are here for the
# same reason the rotations are: a front camera writes 2 and 5, and a mapping
# written by hand gets exactly those wrong.
EXIF_STORAGE_TRANSFORMS = {
    1: None,
    2: Image.FLIP_LEFT_RIGHT,
    3: Image.ROTATE_180,
    4: Image.FLIP_TOP_BOTTOM,
    5: Image.TRANSPOSE,
    6: Image.ROTATE_90,  # the viewer turns it 90 clockwise, so it is stored turned back
    7: Image.TRANSVERSE,
    8: Image.ROTATE_270,
}


def stored_as_exif(image: Image.Image, orientation: int) -> Image.Image:
    """The pixels a file tagged ``orientation`` holds, for a given upright image."""
    transform = EXIF_STORAGE_TRANSFORMS[orientation]
    return image if transform is None else image.transpose(transform)


def png_with_exif_orientation(image: Image.Image, orientation: int) -> bytes:
    """Save an image as PNG carrying an EXIF orientation tag.

    PNG rather than JPEG: the encoding is lossless, so a decoded array can be
    compared exactly against the upright original, and any difference in a read
    is the pipeline's rather than the encoder's.
    """
    exif = image.getexif()
    exif[0x0112] = orientation
    buffer = io.BytesIO()
    image.save(buffer, format="PNG", exif=exif)
    return buffer.getvalue()


def photographic(image: Image.Image, *, contrast=0.18, blur=2.0, lift=30, noise=4.0) -> Image.Image:
    """Degrade rendered artwork into something shaped like a phone photograph.

    Soft contrast, a slight blur and a little sensor noise. Nothing here is a
    photograph of anything; it is the three properties of one that adaptive
    thresholding handles worst, applied deterministically so that a test built
    on it cannot flake. The seed is fixed for the same reason.
    """
    pixels = np.asarray(image).astype(np.float32)
    pixels = (pixels - 128.0) * contrast + 128.0 + lift
    blurred = Image.fromarray(np.clip(pixels, 0, 255).astype(np.uint8)).filter(
        ImageFilter.GaussianBlur(blur)
    )
    pixels = np.asarray(blurred).astype(np.float32)
    pixels += np.random.default_rng(20260828).normal(0, noise, pixels.shape)
    return Image.fromarray(np.clip(pixels, 0, 255).astype(np.uint8))


def upright_rgb(image_bytes: bytes) -> Image.Image:
    """Rendered artwork as a plain RGB image, which is what a viewer shows."""
    return Image.open(io.BytesIO(image_bytes)).convert("RGB")


def png_bytes(image: Image.Image) -> bytes:
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


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
