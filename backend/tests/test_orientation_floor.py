"""What happens when Tesseract admits it guessed the orientation (FR-1, A-15).

``LOW_ORIENTATION_CONFIDENCE`` has been in ``app.ocr`` since v1.0.1 and until
v1.1.0 it was only ever a caption. ``Orientation.low_confidence`` reported that
the floor had been breached, the response carried the caveat out to the agent,
and ``preprocess`` applied Tesseract's rotation regardless. On the author's
mezcal COLA artwork the verdict was 180 degrees at a confidence of 0.03, which
is the engine saying it has nothing to go on, and the label was turned upside
down on the strength of it and then read as "AMoviy TS".

**The refinement to ADR 0003, and why it is this narrow.** That decision
measured OSD against picking the rotation with the highest mean word confidence
over the twelve-label sample set at four rotations: 46 of 48 against 7 of 48.
Nothing here disputes it, and above the floor OSD still decides alone. What the
7 of 48 hides is which cases the score loses, and it loses the quarter-turns for
a reason that is a property of Tesseract rather than of any threshold: layout
analysis already corrects a quarter-turn, so an upright image and the same image
turned 90 degrees produce byte-identical output and identical scores. It
separates a turn from its opposite by fifty points and more.

So below the floor the verdict is scored against its opposite, on two rotations
and never four. These tests assert both halves: that the check runs and decides
where the engine gave up, and that it is never offered the pair it could not
decide.

Fixtures are rendered at test time and no real applicant data appears here
(docs/07_TEST_STRATEGY.md section 8).
"""

from __future__ import annotations

import io
import sys
from pathlib import Path

import pytest
from PIL import Image

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from samples.labelmaker import LabelSpec, render_png_bytes  # noqa: E402
from samples.specs import SAMPLE_LABEL  # noqa: E402

from app import ocr  # noqa: E402
from app.ocr import (  # noqa: E402
    CARDINAL_ROTATIONS,
    LOW_ORIENTATION_CONFIDENCE,
    decode,
    extract_text,
    preprocess,
)
from tests.conftest import requires_fonts, requires_tesseract  # noqa: E402

# A label whose content is almost all figures and abbreviations.
#
# Tesseract's orientation and script detection answers from the shape of the
# glyphs it can find, and there is very little here for it to judge from: it
# returns a verdict with a confidence of about 0.3, which is the same order as
# the 0.03 the author's own artwork produced. That is the whole point of the
# fixture. It is not contrived to make the engine wrong; it is contrived to make
# it say it is unsure, which is the condition this module is about.
SPARSE_NUMERIC_LABEL = LabelSpec(
    filename="sparse-numeric.png",
    brand_name="750 ML",
    class_type="42% ALC/VOL",
    alcohol_content="80 PROOF",
    net_contents="NO 08",
    warning=None,
    producer="EST 1995",
)

SPARSE_CONTENT = ("750 ML", "42% ALC/VOL", "80 PROOF")


def turned(image_bytes: bytes, degrees: int) -> bytes:
    """The same picture, turned clockwise. Pillow turns the other way."""
    if degrees % 360 == 0:
        return image_bytes
    image = Image.open(io.BytesIO(image_bytes)).convert("RGB").rotate(-degrees, expand=True)
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


@requires_tesseract
@requires_fonts
class TestAGuessedVerdictIsScoredRatherThanApplied:
    """The end-to-end behaviour, on an image the engine is genuinely unsure of."""

    @pytest.mark.parametrize("submitted_turn", [0, 180])
    def test_the_check_runs_and_its_working_is_reported(self, submitted_turn):
        """Both readings go out: what the engine said, and what was scored.

        An agent cannot audit a rotation they cannot see. The response carries
        the engine's own verdict and its confidence, the floor that verdict fell
        under, what each of the two candidate rotations scored, and which was
        kept.
        """
        submitted = turned(render_png_bytes(SPARSE_NUMERIC_LABEL), submitted_turn)

        result = extract_text(submitted)
        orientation = result.orientation

        assert orientation.method == "osd_180_check"
        assert orientation.low_confidence is True
        assert orientation.confidence < LOW_ORIENTATION_CONFIDENCE

        check = orientation.check
        assert check is not None
        assert check.floor == LOW_ORIENTATION_CONFIDENCE
        assert check.osd_confidence == orientation.confidence
        assert len(check.candidates) == 2
        assert check.chosen_rotation_degrees == orientation.rotation_degrees

    @pytest.mark.parametrize("submitted_turn", [0, 180])
    def test_the_rotation_kept_is_the_one_that_read_better(self, submitted_turn):
        """Whichever way the engine guessed, the better-scoring turn is applied.

        Stated this way rather than as "the engine was wrong and was overruled"
        on purpose: which way a guess falls is not a property of this code, and
        a test that asserted it would be asserting a Tesseract build. What is a
        property of this code is that the kept rotation is the higher-scoring
        one.
        """
        submitted = turned(render_png_bytes(SPARSE_NUMERIC_LABEL), submitted_turn)

        result = extract_text(submitted)
        check = result.orientation.check

        best = max(check.candidates, key=lambda candidate: candidate.confidence)
        assert check.chosen_rotation_degrees == best.rotation_degrees

    @pytest.mark.parametrize("submitted_turn", [0, 180])
    def test_the_label_reads_upright_either_way_up_it_was_filed(self, submitted_turn):
        """The outcome the agent cares about, on the axis OSD failed on."""
        submitted = turned(render_png_bytes(SPARSE_NUMERIC_LABEL), submitted_turn)

        text = extract_text(submitted).text.upper()

        for element in SPARSE_CONTENT:
            assert element in text

    def test_the_two_candidates_are_a_turn_and_its_opposite(self):
        """Never a quarter-turn pair, which is the whole of the ADR 0003 point.

        A score that returns identical figures for 0 and 90 cannot choose
        between them. Offering it that pair would be reintroducing the sweep
        that decision measured and rejected.
        """
        submitted = render_png_bytes(SPARSE_NUMERIC_LABEL)

        check = extract_text(submitted).orientation.check

        first, second = (candidate.rotation_degrees for candidate in check.candidates)
        assert first in CARDINAL_ROTATIONS
        assert second == (first + 180) % 360


@requires_tesseract
@requires_fonts
class TestTheOverrideItself:
    """A wrong verdict below the floor is discarded, with the engine stubbed.

    Stubbed rather than coaxed out of a fixture. Whether a given Tesseract build
    guesses a given picture upside down is not behaviour this repository owns,
    and a test that depended on it would be a test of the installed engine. What
    this repository owns is what happens to a low-confidence verdict, and that
    is what is asserted here.
    """

    def test_a_wrong_low_confidence_verdict_is_replaced(self, monkeypatch):
        """The author's case: 180 degrees claimed at almost no confidence."""
        monkeypatch.setattr(ocr, "detect_orientation", lambda _: (180, 0.03, "osd"))

        prepared = preprocess(decode(render_png_bytes(SAMPLE_LABEL)))
        check = prepared.orientation.check

        assert check.osd_rotation_degrees == 180
        assert check.osd_confidence == 0.03
        assert check.overrode_osd is True
        assert check.chosen_rotation_degrees == 0
        assert prepared.orientation.rotation_degrees == 0

    def test_a_right_low_confidence_verdict_survives_the_check(self, monkeypatch):
        """A guess that happens to be right is confirmed, not disturbed."""
        monkeypatch.setattr(ocr, "detect_orientation", lambda _: (0, 0.03, "osd"))

        prepared = preprocess(decode(render_png_bytes(SAMPLE_LABEL)))
        check = prepared.orientation.check

        assert check.overrode_osd is False
        assert prepared.orientation.rotation_degrees == 0

    def test_a_confident_verdict_is_not_second_guessed(self, monkeypatch):
        """ADR 0003's 46 of 48 is untouched, and this is what protects it.

        A verdict at or above the floor is applied exactly as it was before
        v1.1.0, wrong or right, and no second opinion is taken or reported.
        """
        monkeypatch.setattr(
            ocr, "detect_orientation", lambda _: (180, LOW_ORIENTATION_CONFIDENCE, "osd")
        )

        prepared = preprocess(decode(render_png_bytes(SAMPLE_LABEL)))

        assert prepared.orientation.method == "osd"
        assert prepared.orientation.check is None
        assert prepared.orientation.rotation_degrees == 180

    def test_a_verdict_the_engine_could_not_give_is_not_scored(self, monkeypatch):
        """An unavailable verdict is not a low-confidence answer, it is no answer.

        There is nothing to take a second opinion on, and scoring two rotations
        would be running the sweep ADR 0003 rejected under another name.
        """
        monkeypatch.setattr(ocr, "detect_orientation", lambda _: (0, None, "unavailable"))

        prepared = preprocess(decode(render_png_bytes(SAMPLE_LABEL)))

        assert prepared.orientation.method == "unavailable"
        assert prepared.orientation.check is None
