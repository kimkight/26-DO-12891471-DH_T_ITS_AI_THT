"""One sheet, several panels, and a line that belongs to exactly one of them.

The author submitted her mezcal COLA to the deployed build on 2026-08-30. The
orientation and colour work of the previous release had landed, the artwork read
at 89.6 against 37.9, and three fields were still wrong. All three were the same
defect, one layer downstream of the reading: the filed artwork is one flat sheet
carrying a left panel, a front panel, a right panel and a narrow strip of type
set at 90 degrees between them, and the reader was assembling its words into
lines across the full width of the sheet.

    ==================== ==========================================
    field                 read as
    ==================== ==========================================
    brand name            ``RFC: <the producer's tax identifier>``
    class or type         the producer's street address
    government warning    the statute with two lines of the left
                          panel spliced through the middle of it
    ==================== ==========================================

Two mechanisms produced that, and this module covers both, because a fix for
either one alone leaves the other standing.

**Words from two panels arriving on one line.** Where the panels' baselines
align, Tesseract's own layout analysis returns a line spanning the sheet.
``TestNoLineSpansTwoPanels`` renders three panels of aligned prose and asserts
that no assembled line carries words from two of them; it fails against the
build this release starts from, where four of six lines do.

**Panels arriving interleaved in reading order.** Even where every line belongs
to one panel, reading the sheet by vertical position alone alternates between
them, and the government warning is collected as a run of consecutive lines.
``TestTheWarningIsReadFromOnePanel`` puts the statute in one panel with decoy
words beside it and asserts an exact FR-5 match, which is what the interleaved
order cannot produce.

Requirements: FR-1 (locate the five fields, and report not found rather than a
guess), FR-5 (the warning compared for exact text), FR-10 (say what was done to
the image), NFR-1 (this adds no Tesseract read).

Every fixture is rendered at test time by ``samples/labelmaker.py``. No image is
committed, and no real applicant data appears anywhere here: the artwork that
found the defect is a real filing carrying a real company, a real tax identifier
and a real address, and it is evidence rather than a fixture
(docs/07_TEST_STRATEGY.md section 8).
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytesseract
import pytest
from pytesseract import Output

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from samples.labelmaker import (  # noqa: E402
    PanelLabelSpec,
    render_panels_png_bytes,
    render_png_bytes,
)
from samples.specs import SAMPLE_LABEL  # noqa: E402
from samples.warning_text import WARNING_STATEMENT  # noqa: E402

from app import timing  # noqa: E402
from app.ocr import _assemble_lines, _columns, decode, extract_text, preprocess  # noqa: E402
from app.parse import parse_fields  # noqa: E402
from tests.conftest import requires_fonts, requires_tesseract  # noqa: E402

# One word per panel that appears nowhere else on the sheet. A line carrying two
# of them came from two panels, which is a fact about the line rather than an
# impression of it, and that is the whole reason the fixture text is written
# this way rather than as anything readable.
PANEL_MARKERS = ("alpha", "bravo", "charlie")
STRIP_MARKERS = ("delta", "echo")
ALL_MARKERS = PANEL_MARKERS + STRIP_MARKERS

# Three panels of prose, set at the same size and leading so that their
# baselines line up across the sheet. That alignment is the condition under
# which Tesseract returns a line spanning two panels, and the fixture has to
# reproduce the mistake in order to prove it is handled.
PANEL_PROSE = (
    "Alpha ridge alpha meadow alpha harbour alpha lantern alpha compass "
    "alpha thicket alpha orchard alpha beacon.",
    "Bravo pillar bravo cinder bravo willow bravo pennant bravo hollow "
    "bravo saffron bravo cobble bravo tundra.",
    "Charlie basin charlie plinth charlie vellum charlie skylark charlie "
    "pumice charlie nutmeg charlie halyard charlie gantry.",
)

# The two strips in the gutters, set at 90 degrees, which is where the mezcal
# artwork prints the bottler's name and the producer's address.
STRIP_TEXT = (
    "Delta wharf delta sextant delta zephyr delta bramble delta cornice",
    "Echo trestle echo marram echo dovetail echo lintel echo gaskin",
)


def markers_in(text: str) -> set[str]:
    """Which panels' vocabulary one piece of text draws on."""
    lowered = text.lower()
    return {marker for marker in ALL_MARKERS if marker in lowered}


@pytest.fixture(scope="module")
def panel_sheet() -> bytes:
    """Three panels of aligned prose with a strip at 90 degrees between each."""
    return render_panels_png_bytes(PanelLabelSpec(panels=PANEL_PROSE, strips=STRIP_TEXT))


@pytest.fixture(scope="module")
def warning_sheet() -> bytes:
    """The statute in the right panel, with two panels of decoys beside it."""
    return render_panels_png_bytes(
        PanelLabelSpec(
            panels=(PANEL_PROSE[0], PANEL_PROSE[1], ""),
            strips=STRIP_TEXT,
            warning_panel=2,
            warning=WARNING_STATEMENT,
        )
    )


@requires_tesseract
@requires_fonts
class TestNoLineSpansTwoPanels:
    """The invariant the whole change exists to establish."""

    def test_no_assembled_line_carries_words_from_two_panels(self, panel_sheet):
        """The defect itself, asserted on the thing it produced.

        Against the build this release starts from, four of the six lines this
        sheet reads as carry words from two panels or from three.
        """
        result = extract_text(panel_sheet)

        crossed = [line.text for line in result.lines if len(markers_in(line.text)) > 1]
        assert crossed == []

    def test_each_panel_is_read_through_before_the_next_one_starts(self, panel_sheet):
        """And the panels arrive whole rather than interleaved by height.

        This is the second mechanism, and it is the one the government warning
        falls to: the statement is collected as a run of consecutive lines, so a
        reading order that alternates between panels splices whatever the other
        panels print at the same height into the middle of it.
        """
        result = extract_text(panel_sheet)

        sequence = [
            next(iter(found)) for line in result.lines if len(found := markers_in(line.text)) == 1
        ]
        runs = [
            marker
            for index, marker in enumerate(sequence)
            if index == 0 or marker != sequence[index - 1]
        ]
        assert len(runs) == len(set(runs)), f"a panel was returned to after leaving it: {runs}"

    def test_every_panel_and_every_strip_is_found(self, panel_sheet):
        """Nothing is dropped between the columns.

        The cut covers the whole width with no gaps, so a word cannot fall
        between two columns. Asserted rather than argued, because "no line
        crosses a panel" is also true of a reader that lost four of them.
        """
        result = extract_text(panel_sheet)

        found = set().union(*(markers_in(line.text) for line in result.lines))
        assert found == set(ALL_MARKERS)

    def test_the_sheet_reports_how_it_was_cut(self, panel_sheet):
        """FR-10: an agent can see the sheet was read as panels, and as how many.

        Three panels and two strips is five columns, and the bounds cover the
        image from edge to edge.
        """
        result = extract_text(panel_sheet)

        assert result.segmentation.columns == 5
        assert result.segmentation.column_bounds[0][0] == 0
        for left, right in zip(
            result.segmentation.column_bounds, result.segmentation.column_bounds[1:], strict=False
        ):
            assert left[1] == right[0], "the columns leave a gap a word could fall into"

    def test_the_strips_are_marked_as_type_set_at_ninety_degrees(self, panel_sheet):
        """Which is what stops them competing for the brand name (FR-1).

        A word set sideways reports a box about one cap-height wide and one word
        long, so its height measures its length. On the author's artwork that
        made the producer's tax identifier the tallest text on the sheet.
        """
        result = extract_text(panel_sheet)

        sideways = {
            marker for line in result.lines if line.sideways for marker in markers_in(line.text)
        }
        assert sideways == set(STRIP_MARKERS)


@requires_tesseract
@requires_fonts
class TestTheWarningIsReadFromOnePanel:
    """FR-5, on a sheet where the neighbouring panels are printing decoys."""

    def test_the_statement_matches_the_regulation_exactly(self, warning_sheet):
        """An exact match, not a near miss.

        Against the build this release starts from, the same fixture reads the
        statement with two panels of unrelated words spliced through it and
        scores 213 edits against 27 CFR 16.21.
        """
        parsed = parse_fields(extract_text(warning_sheet).lines)

        assert parsed.warning.found
        assert parsed.warning.body_matches
        assert parsed.warning.body_edit_distance == 0
        assert parsed.warning.near_miss is False

    def test_no_decoy_word_reaches_the_statement(self, warning_sheet):
        """Stated separately from the match, because it is the failure mode.

        A match already implies this. It is asserted on its own so that a future
        change which loosened the comparison could not quietly take this with
        it: the statement has to contain no word from another panel whatever the
        comparison then says about it.
        """
        parsed = parse_fields(extract_text(warning_sheet).lines)

        assert markers_in(parsed.warning_text or "") == set()

    def test_the_response_says_which_panel_it_came_from(self, warning_sheet):
        """FR-10 again, per field this time.

        A value read off the wrong panel and a value read badly look the same to
        anyone holding only the value, and they need different things done about
        them.
        """
        parsed = parse_fields(extract_text(warning_sheet).lines)

        region = parsed.region["government_warning"]
        assert region.column == 4, "the statute is in the rightmost of five columns"


@requires_tesseract
@requires_fonts
class TestASinglePanelLabelIsUnaffected:
    """The other half of the contract: nothing that read correctly moves."""

    def test_one_column_spanning_the_whole_sheet(self):
        """A label with no gutter is not cut, and the response says so."""
        result = extract_text(render_png_bytes(SAMPLE_LABEL))

        assert result.segmentation.columns == 1
        assert result.segmentation.column_bounds[0][0] == 0
        assert {line.column for line in result.lines} == {0}

    def test_the_lines_are_the_lines_the_previous_build_assembled(self):
        """Byte-identical, and asserted against the previous rule rather than a copy.

        The rule this release replaces is reproduced here in four lines: group
        the words by Tesseract's page, block, paragraph and line, and order the
        groups by vertical position. On a sheet that is one column the new rule
        has to agree with it exactly, and a stored expectation would only prove
        that the output had not changed since somebody wrote the expectation
        down.
        """
        prepared = preprocess(decode(render_png_bytes(SAMPLE_LABEL)))
        image = prepared.colour if prepared.colour is not None else prepared.binary
        data = pytesseract.image_to_data(image, lang="eng", output_type=Output.DICT)

        grouped: dict[tuple[int, int, int, int], list[int]] = {}
        for index, word in enumerate(data["text"]):
            if not str(word).strip() or float(data["conf"][index]) < 0:
                continue
            key = (
                data["page_num"][index],
                data["block_num"][index],
                data["par_num"][index],
                data["line_num"][index],
            )
            grouped.setdefault(key, []).append(index)
        previous = [
            " ".join(str(data["text"][i]).strip() for i in grouped[key])
            for key in sorted(
                grouped, key=lambda k: (k[0], min(data["top"][i] for i in grouped[k]))
            )
        ]

        lines, _, segmentation = _assemble_lines(data, width=int(image.shape[1]))
        assert segmentation.columns == 1
        assert [line.text for line in lines] == previous


class TestALineNeverSpansABlock:
    """The half of the fix that is Tesseract's own layout analysis, kept.

    Built from a word table rather than from pixels, deliberately. Tesseract
    does not make this mistake on clean synthetic artwork at any panel geometry
    tried, and it made it repeatedly on the author's filing, where the blocks
    spanned x 44 to 1526 of a 1600 pixel sheet. A fixture that cannot reproduce
    the mistake cannot prove it is handled, so the mistake is stated directly:
    one Tesseract line, two panels, and the assertion is that it comes back as
    two lines.

    No Tesseract, no fonts and no image, so this one runs in the unit tier.
    """

    @staticmethod
    def words(entries: list[tuple[int, int, int, str]]) -> dict:
        """A word table in the shape ``image_to_data`` returns, from left, block, line, text."""
        table: dict[str, list] = {
            key: [] for key in ("text", "conf", "left", "top", "width", "height")
        }
        table.update({"page_num": [], "block_num": [], "par_num": [], "line_num": []})
        for left, block, line, text in entries:
            table["text"].append(text)
            table["conf"].append(90.0)
            table["left"].append(left)
            table["top"].append(100 + 30 * line)
            table["width"].append(10 * len(text))
            table["height"].append(20)
            table["page_num"].append(1)
            table["block_num"].append(block)
            table["par_num"].append(1)
            table["line_num"].append(line)
        return table

    def test_one_tesseract_line_across_two_panels_becomes_two_lines(self):
        data = self.words(
            [
                (100, 1, 1, "HECHO"),
                (180, 1, 1, "EN"),
                (230, 1, 1, "MEXICO"),
                (900, 1, 1, "long,"),
                (980, 1, 1, "smooth"),
                (1060, 1, 1, "finish."),
            ]
        )

        lines, _, segmentation = _assemble_lines(data, width=1600)

        assert segmentation.columns == 2
        assert [line.text for line in lines] == ["HECHO EN MEXICO", "long, smooth finish."]

    def test_two_blocks_at_one_height_are_never_joined(self):
        """Tesseract's own block numbers are respected, as they always were."""
        data = self.words([(100, 1, 1, "PRODUCTO"), (140, 2, 1, "DE")])

        lines, _, _ = _assemble_lines(data, width=1600)

        assert [line.text for line in lines] == ["PRODUCTO", "DE"]

    def test_a_word_space_in_display_type_is_not_a_gutter(self):
        """Sample label 05 sets ``LANTERN HILL`` in 75 pixel type with a 53 pixel
        word space in it, which is 4.97 percent of that label's width: wider, as
        a share, than two of the three real gutters on the author's artwork. The
        type either side of the blank is what says it is a word space.
        """
        data = {
            "text": ["LANTERN", "HILL"],
            "conf": [95.0, 95.0],
            "left": [80, 655],
            "top": [100, 100],
            "width": [522, 242],
            "height": [75, 75],
            "page_num": [1, 1],
            "block_num": [1, 1],
            "par_num": [1, 1],
            "line_num": [1, 1],
        }

        assert _columns(data, [0, 1], 1067) == [(0, 1067)]

        lines, _, _ = _assemble_lines(data, width=1067)
        assert [line.text for line in lines] == ["LANTERN HILL"]


@requires_tesseract
@requires_fonts
class TestSegmentationCostsNoTesseractRead:
    """NFR-1. Both segmentations are arithmetic on a table that already exists.

    The column split and the block grouping run over the word boxes the single
    ``image_to_data`` call already returned. Neither crops the image, neither
    changes the page segmentation mode, and neither reads anything a second
    time, so a sheet of five panels costs exactly what a sheet of one costs.
    """

    def test_assembling_lines_reads_nothing(self):
        data = TestALineNeverSpansABlock.words([(100, 1, 1, "one"), (900, 1, 1, "two")])

        with timing.recording() as recorded:
            _assemble_lines(data, width=1600)

        assert recorded.tesseract_reads == 0

    def test_a_multi_panel_sheet_costs_the_reads_its_read_path_names(self, panel_sheet):
        """One for the orientation call, one per arm, and nothing else.

        Stated as an equation over what the response itself reports rather than
        as a constant, so that a future change to the number of arms updates
        both halves at once and a segmentation that quietly read again does not.
        """
        with timing.recording() as recorded:
            result = extract_text(panel_sheet)

        arms = 1 + sum(
            score is not None
            for score in (result.read_path.plain_confidence, result.read_path.colour_confidence)
        )
        # The orientation call, plus the two scored rotations where its own
        # confidence fell under the floor and the second opinion ran.
        orientation = 1 + (2 if result.orientation.method == "osd_180_check" else 0)
        assert recorded.tesseract_reads == orientation + arms
