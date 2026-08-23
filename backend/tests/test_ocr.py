"""Unit tests for image preprocessing.

Requirements: FR-1, NFR-3, NFR-6. These tests use OpenCV and Pillow but not
Tesseract, so they stay in the unit tier as docs/07_TEST_STRATEGY.md section 1
requires.
"""

import io

import cv2
import numpy as np
import pytest
from PIL import Image

from app.ocr import UndecodableImageError, decode, deskew, estimate_skew, resize_long_edge


def rendered_text_image(rotate_degrees: float = 0.0) -> np.ndarray:
    """A black-on-white image with enough horizontal ink to estimate skew from."""
    image = Image.new("RGB", (900, 600), (255, 255, 255))
    from PIL import ImageDraw

    draw = ImageDraw.Draw(image)
    for row in range(6):
        draw.rectangle((80, 80 + row * 80, 820, 110 + row * 80), fill=(0, 0, 0))
    if rotate_degrees:
        image = image.rotate(rotate_degrees, expand=True, fillcolor=(255, 255, 255))
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return decode(buffer.getvalue())


def binarize(image: np.ndarray) -> np.ndarray:
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    return cv2.adaptiveThreshold(
        cv2.medianBlur(gray, 3), 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 31, 15
    )


class TestDecode:
    def test_bytes_that_are_not_an_image_raise_rather_than_return_empty(self):
        with pytest.raises(UndecodableImageError):
            decode(b"not an image")

    def test_empty_bytes_raise(self):
        with pytest.raises(UndecodableImageError):
            decode(b"")


class TestResize:
    @pytest.mark.parametrize("size", [(400, 300), (4000, 3000), (300, 4000)])
    def test_the_long_edge_lands_on_the_configured_size(self, size):
        image = np.zeros((size[1], size[0], 3), dtype=np.uint8)
        resized = resize_long_edge(image, long_edge=1600)
        assert max(resized.shape[:2]) == 1600

    def test_the_aspect_ratio_is_preserved(self):
        image = np.zeros((600, 900, 3), dtype=np.uint8)
        resized = resize_long_edge(image, long_edge=1600)
        height, width = resized.shape[:2]
        assert abs(width / height - 900 / 600) < 0.01


class TestDeskew:
    """The rotation has to undo the lean, not repeat it."""

    @pytest.mark.parametrize("rotation", [4.0, -4.0, 7.0])
    def test_a_rotated_image_comes_back_closer_to_upright(self, rotation):
        image = rendered_text_image(rotate_degrees=rotation)
        binary = binarize(image)
        before = abs(estimate_skew(cv2.bitwise_not(binary)))
        corrected = deskew(binary, cv2.bitwise_not(binary))
        after = abs(estimate_skew(cv2.bitwise_not(corrected)))
        assert before > 1.0, "the fixture should be measurably skewed to begin with"
        assert after < before / 2

    def test_an_upright_image_is_left_alone(self):
        image = rendered_text_image()
        binary = binarize(image)
        corrected = deskew(binary, cv2.bitwise_not(binary))
        assert corrected is binary

    def test_an_implausibly_large_estimate_is_refused(self):
        image = rendered_text_image()
        binary = binarize(image)
        assert deskew(binary, cv2.bitwise_not(binary), max_degrees=0.0) is binary

    def test_a_nearly_blank_image_yields_no_angle(self):
        blank = np.zeros((400, 400), dtype=np.uint8)
        assert estimate_skew(blank) == 0.0
