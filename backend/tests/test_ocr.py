"""Unit tests for image preprocessing, plus the orientation strategy.

Requirements: FR-1, NFR-3, NFR-6. Most of these use OpenCV and Pillow but not
Tesseract, so they stay in the unit tier as docs/07_TEST_STRATEGY.md section 1
requires. The orientation classes at the end do call Tesseract and are marked
for the integration tier accordingly.
"""

import io

import cv2
import numpy as np
import pytest
from PIL import Image
from samples.labelmaker import render_png_bytes
from samples.specs import SAMPLE_LABEL

from app.ocr import (
    DecodedImage,
    UndecodableImageError,
    decode,
    deskew,
    detect_orientation,
    estimate_skew,
    extract_text,
    preprocess,
    resize_long_edge,
    rotate_cardinal,
)
from tests.conftest import requires_fonts, requires_tesseract


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
    return decode(buffer.getvalue()).pixels


def jpeg_with_exif_orientation(image: Image.Image, orientation: int) -> bytes:
    """Save an image as JPEG carrying an EXIF orientation tag.

    The pixels are written exactly as given. That is the case this exists to
    reproduce: a phone stores the sensor's pixels unturned and records which way
    up it was held, so the file is sideways and every viewer shows it upright.
    """
    exif = image.getexif()
    exif[0x0112] = orientation
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", exif=exif, quality=95)
    return buffer.getvalue()


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


class TestExifOrientation:
    """A phone records which way up it was held; OpenCV alone ignores that.

    This is the first of the two things that went wrong on the first real
    photograph. It is a unit-tier test: Pillow and OpenCV only, no Tesseract.
    """

    def test_a_sideways_file_with_an_orientation_tag_decodes_upright(self):
        # 400 wide by 900 tall as stored, tagged 6, which means "the camera was
        # held rotated, turn this 90 degrees clockwise to display it".
        stored = Image.new("RGB", (400, 900), (255, 255, 255))
        image_bytes = jpeg_with_exif_orientation(stored, orientation=6)

        decoded = decode(image_bytes)

        assert decoded.exif_transposed is True
        # Applying the tag swaps the axes: the array is now 900 wide, 400 tall.
        height, width = decoded.pixels.shape[:2]
        assert (width, height) == (900, 400)

    def test_the_tag_is_applied_to_the_pixels_and_not_only_to_the_shape(self):
        """Orientation 2 is a horizontal mirror. It leaves the size alone."""
        stored = Image.new("RGB", (200, 100), (255, 255, 255))
        stored.paste((0, 0, 0), (0, 0, 20, 100))  # a black bar down the left edge
        decoded = decode(jpeg_with_exif_orientation(stored, orientation=2))

        assert decoded.exif_transposed is True
        assert decoded.pixels.shape[:2] == (100, 200)
        # The bar is on the right after mirroring. JPEG is lossy, so this reads
        # the mean of each edge rather than an exact value.
        assert decoded.pixels[:, :10].mean() > decoded.pixels[:, -10:].mean()

    def test_an_untagged_image_reports_that_nothing_was_applied(self):
        buffer = io.BytesIO()
        Image.new("RGB", (200, 100), (255, 255, 255)).save(buffer, format="PNG")
        assert decode(buffer.getvalue()).exif_transposed is False

    def test_bytes_opencv_can_read_but_pillow_cannot_still_decode(self, monkeypatch):
        """The Pillow path is an addition, not a replacement (A-3)."""
        buffer = io.BytesIO()
        Image.new("RGB", (60, 40), (255, 255, 255)).save(buffer, format="PNG")

        def refuse(*args, **kwargs):
            raise OSError("pretend Pillow cannot open this")

        monkeypatch.setattr(Image, "open", refuse)
        decoded = decode(buffer.getvalue())
        assert decoded.pixels.shape[:2] == (40, 60)
        assert decoded.exif_transposed is False


class TestRotateCardinal:
    def test_a_quarter_turn_clockwise_swaps_the_axes(self):
        image = np.zeros((40, 90, 3), dtype=np.uint8)
        assert rotate_cardinal(image, 90).shape[:2] == (90, 40)

    def test_zero_degrees_returns_the_same_array(self):
        image = np.zeros((40, 90, 3), dtype=np.uint8)
        assert rotate_cardinal(image, 0) is image

    @pytest.mark.parametrize("degrees", [90, 180, 270])
    def test_the_turn_is_undone_by_its_complement(self, degrees):
        image = np.arange(40 * 90, dtype=np.uint8).reshape(40, 90)
        turned = rotate_cardinal(image, degrees)
        assert np.array_equal(rotate_cardinal(turned, 360 - degrees), image)


@requires_tesseract
@requires_fonts
class TestCardinalOrientation:
    """The second thing that went wrong: a photograph genuinely taken sideways.

    Integration tier, because it runs Tesseract. `np.rot90` turns an image
    counter-clockwise, so an image built with k turns needs a clockwise
    correction of k * 90 degrees to come back upright, which is exactly the
    figure `detect_orientation` reports.
    """

    @pytest.mark.parametrize("turns", [0, 1, 2, 3])
    def test_the_correction_reported_is_the_one_the_fixture_needs(self, turns):
        upright = decode(render_png_bytes(SAMPLE_LABEL)).pixels
        sideways = np.ascontiguousarray(np.rot90(upright, turns))

        prepared = preprocess(DecodedImage(pixels=sideways), correct_orientation=True)

        assert prepared.orientation.method == "osd"
        assert prepared.orientation.rotation_degrees == turns * 90

    @pytest.mark.parametrize("turns", [1, 2, 3])
    def test_a_sideways_label_reads_its_fields_again(self, turns):
        """The failure this whole change exists for: the brand name came back
        as OCR shrapnel, and now it comes back as the brand name."""
        png = render_png_bytes(SAMPLE_LABEL)
        upright = decode(png).pixels
        sideways = np.ascontiguousarray(np.rot90(upright, turns))
        buffer = io.BytesIO()
        Image.fromarray(cv2.cvtColor(sideways, cv2.COLOR_BGR2RGB)).save(buffer, format="PNG")

        result = extract_text(buffer.getvalue())

        assert result.orientation.rotation_degrees == turns * 90
        # The brand is set across two lines on this artwork, so the words are
        # asserted rather than the joined string.
        assert "STONE'S" in result.text
        assert "THROW" in result.text
        assert "750 mL" in result.text

    def test_an_upright_label_is_left_alone_and_says_so(self, sample_label_png):
        result = extract_text(sample_label_png)
        assert result.orientation.rotation_degrees == 0
        assert result.orientation.exif_transposed is False
        assert result.orientation.method == "osd"

    def test_the_correction_can_be_turned_off(self, sample_label_png):
        result = extract_text(sample_label_png, correct_orientation=False)
        assert result.orientation.method == "disabled"
        assert result.orientation.rotation_degrees == 0

    def test_an_image_tesseract_cannot_judge_is_left_as_it_arrived(self):
        """No text to work from is not a failure; it is an unavailable answer."""
        blank = np.full((1200, 900), 255, dtype=np.uint8)
        degrees, _, method = detect_orientation(blank)
        assert method == "unavailable"
        assert degrees == 0


@requires_tesseract
@requires_fonts
class TestWhyOrientationUsesOsd:
    """The evidence for choosing OSD over reading the image four times.

    docs/adr/0003 and assumption A-15 both cite this. The alternative in the
    brief was to run OCR at each of the four cardinal rotations and keep the one
    with the highest mean word confidence. It does not work, and the reason is
    not that the threshold needs tuning: Tesseract's own layout analysis already
    detects and corrects text turned a quarter-turn clockwise, so the upright
    image and the clockwise-turned image produce the same words at the same
    confidence. A score that is identical on the two cases it has to separate
    cannot separate them.

    Asserted rather than written down, so that a future Tesseract release which
    changes this behaviour fails a test instead of leaving a stale claim in a
    document.
    """

    def test_mean_word_confidence_cannot_tell_upright_from_a_clockwise_turn(self, sample_label_png):
        upright = extract_text(sample_label_png, correct_orientation=False)

        turned = np.ascontiguousarray(np.rot90(decode(sample_label_png).pixels, 3))
        buffer = io.BytesIO()
        Image.fromarray(cv2.cvtColor(turned, cv2.COLOR_BGR2RGB)).save(buffer, format="PNG")
        clockwise = extract_text(buffer.getvalue(), correct_orientation=False)

        assert upright.mean_confidence > 80, "the fixture should read well upright"
        assert abs(clockwise.mean_confidence - upright.mean_confidence) < 1.0, (
            "if these ever diverge, best-of-four confidence becomes viable and "
            "the choice recorded in A-15 should be revisited"
        )
