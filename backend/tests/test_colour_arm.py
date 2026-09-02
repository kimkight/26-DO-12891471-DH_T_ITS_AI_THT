"""The colour image as a first-class OCR candidate (FR-1, v1.1.0).

The author submitted a mezcal COLA PDF to the deployed build on 2026-08-30 and
the label artwork inside it read as "AMoviy TS" against SIERRA VERDE, with the
government warning not found at all. Two things were wrong and this module
covers the second of them.

**Preprocessing to grayscale loses colour-dependent text.** Filed label artwork
is routinely printed in more than two tones: a dark warning on a light panel and
a light brand directly on a coloured ground, with a third ink somewhere between.
A threshold separates two luminance classes and not three, so one class
dissolves into the background. Nothing about the surviving text scores a point
lower for it, which is why the failure survived two deploys: the read that had
lost two of the five fields came back at 95.

That last sentence is also why ``EQUAL_CONFIDENCE_BAND`` exists, and the tests
at the bottom of this module are the ones that pin down what it may and may not
do. Mean word confidence ranks. It is allowed to be broken out of only by a tie.

Every fixture is rendered at test time by ``samples/labelmaker.py``. No image is
committed and no real applicant data appears anywhere here
(docs/07_TEST_STRATEGY.md section 8).
"""

from __future__ import annotations

import sys
from pathlib import Path

import cv2
import numpy as np
import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from samples.labelmaker import (  # noqa: E402
    ColourLabelSpec,
    render_colour,
    render_colour_png_bytes,
    render_png_bytes,
)
from samples.specs import SAMPLE_LABEL  # noqa: E402
from samples.warning_text import WARNING_STATEMENT  # noqa: E402

from app.ocr import (  # noqa: E402
    EQUAL_CONFIDENCE_BAND,
    PREPROCESS_SHORT_CIRCUIT_CONFIDENCE,
    OcrLine,
    _Arm,
    _rank,
    extract_text,
    has_colour,
    preprocess,
)
from tests.conftest import (  # noqa: E402
    photographic,
    png_bytes,
    requires_fonts,
    requires_tesseract,
    upright_rgb,
)

# What a compliant filing has to be readable for. Every one of these is printed
# on the fixture, and two of them are printed in the ink a grayscale conversion
# collapses into the ground behind it.
REQUIRED_ON_THE_LABEL = (
    "SIERRA VERDE",
    "SMALL BATCH MEZCAL",
    "42% ALC BY VOL",
    "750 ML",
    "GOVERNMENT WARNING",
)

# The two printed in that ink, named separately because they are the assertion
# that fails against v1.0.1 and the reason this module exists.
LOST_TO_GRAYSCALE = ("42% ALC BY VOL", "750 ML")


@pytest.fixture
def colour_label() -> bytes:
    """A label printed in three inks on one ground, upright."""
    return render_colour_png_bytes(ColourLabelSpec(warning=WARNING_STATEMENT))


def missing_from(text: str) -> list[str]:
    """Which of the required elements this read did not recover."""
    upper = text.upper()
    return [element for element in REQUIRED_ON_THE_LABEL if element not in upper]


@requires_tesseract
@requires_fonts
class TestTheColourLabelIsReadWhole:
    """The defect, and the four orientations it has to survive."""

    def test_every_element_is_read_from_the_upright_label(self, colour_label):
        """All five, including the two a grayscale conversion drops.

        This is the assertion that fails against v1.0.1, where the plain
        grayscale read wins at 95.6 having already lost "42% ALC BY VOL" and
        "750 ML" and reported nothing about it.
        """
        result = extract_text(colour_label)

        assert missing_from(result.text) == []
        assert result.read_path.variant == "colour"

    @pytest.mark.parametrize(
        ("turned", "expected_correction"),
        [(0, 0), (90, 270), (180, 180), (270, 90)],
    )
    def test_the_turned_label_is_turned_back_and_read_whole(self, turned, expected_correction):
        """A label filed on its side reads the same, and says how it was turned.

        The correction reported is the inverse of the turn applied, which is
        what an agent needs in order to tell "we turned it and read it" from
        "we turned it the wrong way and read nothing". The 180 case is the one
        the deployed build got wrong.
        """
        submitted = render_colour_png_bytes(
            ColourLabelSpec(warning=WARNING_STATEMENT), turned_degrees=turned
        )

        result = extract_text(submitted)

        assert missing_from(result.text) == []
        assert result.orientation.rotation_degrees == expected_correction
        assert result.orientation.method == "osd"

    def test_the_grayscale_read_is_the_one_that_loses_the_two_fields(self, colour_label):
        """The defect itself, asserted directly on the arm that carries it.

        Without this the test above could pass for some unrelated reason and
        nobody would know the colour arm was what fixed it. What is asserted
        here is the mechanism: the plain grayscale image, read on its own,
        genuinely cannot see the two elements printed in the chroma ink.
        """
        prepared = preprocess(_decoded(colour_label))
        grayscale_text = _read_text(prepared.gray)
        colour_text = _read_text(prepared.colour)

        for element in LOST_TO_GRAYSCALE:
            assert element not in grayscale_text.upper()
            assert element in colour_text.upper()

    def test_what_each_arm_scored_is_reported(self, colour_label):
        """The choice is invisible in the result otherwise.

        An agent looking at a poor read is entitled to know which rendering
        produced it, and an operator reading latency is entitled to know which
        images paid for more than one read.
        """
        result = extract_text(colour_label)

        assert result.read_path.colour_confidence is not None
        assert result.read_path.decided_by == "short_circuit"


@requires_tesseract
@requires_fonts
class TestNothingPaysForThisThatCannotUseIt:
    """NFR-1. The arms are free on every image the sample set is built from."""

    def test_a_monochrome_label_takes_the_v1_0_1_path_unchanged(self):
        """One read, no colour arm, and the same variant v1.0.1 kept.

        The twelve sample labels are black on white. Reading them as colour
        would be reading the plain grayscale a second time under another name,
        for the price of a full Tesseract pass, and the accuracy tier would pay
        it twelve times over.
        """
        result = extract_text(render_png_bytes(SAMPLE_LABEL))

        assert result.read_path.colour_confidence is None
        assert result.read_path.variant == "preprocessed"
        assert result.read_path.decided_by == "short_circuit"

    def test_sensor_noise_is_not_colour(self):
        """A photograph of a black-and-white label is not a colour image.

        Its three channels differ in every pixel, because sensor noise is
        per-channel, so an exact channel comparison would call every photograph
        ever submitted a colour image and buy a Tesseract pass for each one.
        What is measured instead is chroma, and the fixture's noise does not
        reach the floor: 0.000 percent of its pixels against 84 percent of the
        colour label's.
        """
        photograph = png_bytes(photographic(upright_rgb(render_png_bytes(SAMPLE_LABEL))))

        result = extract_text(photograph)

        assert result.read_path.colour_confidence is None

    def test_the_colour_label_is_read_once_when_it_reads_cleanly(self, colour_label):
        """The common case costs one Tesseract read, not three.

        The untransformed pixels are read first on a coloured source, and a
        confident read of them ends the comparison. That is one read where the
        author's artwork pays two today.
        """
        result = extract_text(colour_label)

        assert result.read_path.colour_confidence >= PREPROCESS_SHORT_CIRCUIT_CONFIDENCE
        assert result.read_path.preprocessed_confidence == 0.0
        assert result.read_path.plain_confidence is None


class TestWhatCountsAsColour:
    """``has_colour``, on the pixels rather than through the pipeline."""

    def test_a_two_dimensional_array_has_no_colour(self):
        assert has_colour(np.zeros((10, 10), dtype=np.uint8)) is False

    def test_three_identical_channels_have_no_colour(self):
        gray = np.random.default_rng(20260830).integers(0, 255, (64, 64), dtype=np.uint8)
        assert has_colour(cv2.merge([gray, gray, gray])) is False

    @requires_fonts
    def test_the_colour_label_has_colour(self):
        pixels = np.asarray(render_colour(ColourLabelSpec(warning=WARNING_STATEMENT)))
        assert has_colour(pixels) is True

    @requires_fonts
    def test_a_stray_coloured_mark_on_a_white_label_does_not(self):
        """One small red seal is not a reason to read the whole label twice.

        The share floor is a percent of the image, and a mark that small has no
        text in it to lose.
        """
        pixels = np.asarray(upright_rgb(render_png_bytes(SAMPLE_LABEL))).copy()
        pixels[:60, :60] = (200, 40, 40)
        assert has_colour(pixels) is False


class TestMeanWordConfidenceIsTheRankingSignal:
    """The regression guard, and the one exception it is allowed.

    Ranking by how many words an arm read rather than by how confident it was
    would be an easy and wrong simplification of this code: it would hand every
    comparison to whichever rendering hallucinated the most text. What the band
    permits is narrower than that, and these are the assertions that keep it
    narrow.
    """

    def test_more_words_never_beats_a_materially_higher_confidence(self):
        """A verbose, unconfident read loses to a terse, confident one.

        This is the rule v1.0.1 set and nothing in v1.1.0 changes it.
        """
        confident = _arm("preprocessed", confidence=95.0, words=10)
        verbose = _arm("colour", confidence=60.0, words=200)

        winner, decided_by = _rank([confident, verbose])

        assert winner is confident
        assert decided_by == "confidence"

    def test_the_gap_that_settles_it_is_only_just_outside_the_band(self):
        """Just outside the band is still confidence deciding, not coverage."""
        leader = _arm("preprocessed", confidence=95.0, words=10)
        fuller = _arm("colour", confidence=95.0 - EQUAL_CONFIDENCE_BAND - 0.1, words=200)

        winner, decided_by = _rank([leader, fuller])

        assert winner is leader
        assert decided_by == "confidence"

    def test_a_tie_on_confidence_is_broken_by_what_was_recovered(self):
        """The case mean confidence cannot decide, and the reason it cannot.

        These are the author's own figures: the colour image read 257 words at
        89.1 and the grayscale 106 at 89.9, and the grayscale is the one that
        lost "42% ALC BY VOL" entirely. A word that was never read lowers no
        score, so on this signal the two reads are the same read.
        """
        grayscale = _arm("plain", confidence=89.9, words=106)
        colour = _arm("colour", confidence=89.1, words=257)

        winner, decided_by = _rank([grayscale, colour])

        assert winner is colour
        assert decided_by == "coverage"

    def test_equally_confident_and_equally_full_is_still_confidence(self):
        """Coverage is claimed only where coverage actually decided something."""
        first = _arm("preprocessed", confidence=95.0, words=40)
        second = _arm("colour", confidence=94.9, words=40)

        winner, decided_by = _rank([first, second])

        assert winner is first
        assert decided_by == "confidence"

    def test_one_arm_is_a_short_circuit_and_says_so(self):
        arm = _arm("preprocessed", confidence=96.0, words=40)

        winner, decided_by = _rank([arm])

        assert winner is arm
        assert decided_by == "short_circuit"


def _arm(variant: str, *, confidence: float, words: int) -> _Arm:
    """One arm with a stated confidence and a stated amount of text."""
    return _Arm(
        variant=variant,
        lines=[OcrLine(text=" ".join(["word"] * words), confidence=confidence, height=20.0, top=0)],
        confidence=confidence,
    )


def _decoded(image_bytes: bytes):
    from app.ocr import decode

    return decode(image_bytes)


def _read_text(image) -> str:
    from app.ocr import _read

    lines, _, _ = _read(image)
    return "\n".join(line.text for line in lines)
