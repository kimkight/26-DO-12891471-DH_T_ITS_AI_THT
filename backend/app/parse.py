"""Locate the five label fields inside the text OCR returned.

Governing requirements: FR-1 (extract brand name, class or type designation,
alcohol content, net contents, and the government warning, with an explicit
"not found" for any field that cannot be located), FR-5 and FR-6 (the warning,
delegated to app.warning), A-9 (extraction is limited to the sample label's five
fields).

**These are heuristics, and they are stated as such.** Alcohol content, net
contents and the warning are located by pattern, which is deterministic. Brand
name and class or type designation carry no pattern to match, so they are
located by type size: Tesseract reports a bounding box per word, and on a label
the brand name is usually the largest text. Nothing in the assignment states a
layout rule, so inventing one is not available; type size is a property of the
artwork itself rather than an assumption about it. Where the heuristic fails,
the field reports not found rather than reporting a guess, which is what FR-1
requires. The rate at which it fails is measured, not asserted: see
scripts/measure.py.

**"Usually" is doing real work in that paragraph, and the author's own filing
is where it stops being true.** Her COLA declares a brand name and a fanciful
name, while the largest text on the artwork is the fanciful name's own display
line. Type size does not identify the brand name on that
label, and no amount of tuning makes it. So the ranking has to be able to
decline, and ``_standout`` is where it does: see it for the two conditions a
candidate has to clear, and see FR-1 for why declining is the required answer
rather than a shortfall.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass, field

from app.ocr import OcrLine
from app.warning import (
    WARNING_STATEMENT,
    WarningCheck,
    check_warning,
    join_line_break_hyphens,
    normalize_whitespace,
)


@dataclass(frozen=True)
class TextRegion:
    """Which part of the segmented sheet one field was read from (FR-1, FR-10).

    ``column`` is the panel ``app.ocr`` cut the sheet into, numbered left to
    right from zero; ``block`` is Tesseract's own block inside it. Together they
    name one region, and a field that reports one was read entirely inside it,
    because no line and no block spans two.

    It exists so that an agent can see *where* a value came from and not only
    what it was. On a four-panel sheet a value read off the wrong panel looks,
    to anyone holding only the value, exactly like a value read badly, and those
    two need different things done about them.
    """

    column: int
    block: int


_NUMBER = r"\d+(?:\.\d+)?"

# An alcohol content candidate is a number that carries an alcohol marker on the
# same OCR line. A bare percent is not one.
#
# **This is a defect fix, and the defect was found on real artwork.** In the
# author's three-photograph bottle test on 2026-08-27 the deployed prototype
# reported the alcohol content as `7%`, read from a sentence of marketing copy
# on the back label about reducing environmental impact. The pattern accepted
# any percent token, so the first percent anywhere in the reading order won,
# whatever it was a percentage of. A label carrying a percentage of recycled
# glass, of grain in the mash bill, or of anything else printed before the
# alcohol statement produced a confident, wrong number.
#
# The rule now is FR-7's own vocabulary: the marker set is ALC, ALC., VOL, ABV,
# ALCOHOL and PROOF, matched case-insensitively. VOLUME is admitted with VOL
# because it is the same word spelled out, not a further term. The marker has to
# be a word of its own, so a garbled neighbouring word does not create one and
# does not destroy one either: "12.5% AlC. 8Y VOL." still matches on VOL even
# though Tesseract mangled two words around it, which is the OCR noise this has
# to survive.
#
# A number with no marker on its line, and a marker with no number on its line,
# are both not found. Reporting `ALC./VOL.` with no figure in it, which the old
# pattern did whenever OCR split the statement across two lines, is a guess
# dressed as a reading; FR-1 requires not found instead. The residual risk is a
# line that genuinely carries both an unrelated number and a marker word, which
# is narrower than the risk it replaces and is recorded in FR-7.
_ABV_MARKER = re.compile(r"\b(?:alcohol|alc|abv|vol(?:ume)?|proof)\b", re.IGNORECASE)
_ABV_NUMBER = re.compile(_NUMBER)


def is_alcohol_content_line(text: str) -> bool:
    """Whether one OCR line states an alcohol content (FR-1, FR-7)."""
    return bool(_ABV_MARKER.search(text) and _ABV_NUMBER.search(text))


_NET_CONTENTS_LINE = re.compile(
    rf"{_NUMBER}\s*(fl\.?\s*oz\.?|fluid\s+ounces?|milli\s?lit(?:er|re)s?|lit(?:er|re)s?|ml|mls|l)\b",
    re.IGNORECASE,
)
_WARNING_PREFIX_LINE = re.compile(r"government\s+warning", re.IGNORECASE)
# The two fallbacks for a prefix OCR damaged: WARNING on its own, and the
# body's opening. See ``app.warning.locate_warning`` for why, and for the
# measurement behind it.
_DAMAGED_PREFIX_LINE = re.compile(r"\bwarning\b", re.IGNORECASE)
_BODY_OPENING_LINE = re.compile(r"according\s+to\s+the|surgeon\s+general", re.IGNORECASE)
_BODY_CONTINUES_LINE = re.compile(
    r"surgeon\s+general|should\s+not\s+drink|birth\s+defects|alcoholic\s+beverages",
    re.IGNORECASE,
)
# A line with no letter in it cannot carry a word of the statement, so it is
# not part of the block even when it sits inside it: on a real filing the
# panel carrying the warning is overprinted with a run of digits from the
# printer's registration marks, which OCR returns as a line of its own.
_HAS_A_LETTER = re.compile(r"[^\W\d_]")


@dataclass(frozen=True)
class ParsedFields:
    """What was found on the label. ``None`` means not found, explicitly.

    ``confidence`` carries Tesseract's mean word confidence for the text each
    field was read from, keyed by field name, and 0.0 for a field that was not
    found. It exists for ADR 0007: when the same label is photographed more
    than once, two photographs can both show a field and disagree about it, and
    something has to decide which reading is reported. A per-field figure is the
    honest basis for that; the photograph's overall confidence is not, because a
    photograph can read the back of the label well and the front badly.

    ``prominence`` carries the glyph height in preprocessed pixels of the text
    the brand name and the class or type designation were read from, which is
    the signal those two are located by in the first place. It is comparable
    between photographs because every image is scaled to the same long edge
    before it is read, so a 96 point brand name and a 22 point producer line
    stay far apart whichever photograph each came from. It is what stops the
    small print on a back label outscoring the brand name on a front one when
    both are read confidently. The comparison does assume the two photographs
    frame the label at a similar distance; ADR 0007 records that.
    """

    brand_name: str | None
    class_type: str | None
    alcohol_content: str | None
    net_contents: str | None
    warning: WarningCheck
    warning_text: str | None
    confidence: dict[str, float] = field(default_factory=dict)
    prominence: dict[str, float] = field(default_factory=dict)
    region: dict[str, TextRegion] = field(default_factory=dict)
    # Field names the type-size ranking declined rather than failed to see: the
    # label carried candidates and none of them stood out (see ``_standout``).
    # Carried so the response can tell an agent which of the two happened. A
    # label with nothing on it and a label whose brand name the tool could not
    # identify are both "not found", and they are not the same finding.
    declined: frozenset[str] = frozenset()


def lines_from_text(text: str) -> list[OcrLine]:
    """Build line records from plain text, for callers that have no image.

    Height is zero for every line, which turns the type-size heuristic into a
    reading-order one. Unit tests use this path; the API does not.
    """
    return [
        OcrLine(text=stripped, confidence=0.0, height=0.0, top=index)
        for index, raw in enumerate(text.splitlines())
        if (stripped := raw.strip())
    ]


def parse_fields(lines: list[OcrLine]) -> ParsedFields:
    """Locate all five fields. Every field may independently be not found."""
    warning_indices, warning_text = _find_warning(lines)
    warning = (
        check_warning(
            warning_text,
            lines=[(lines[index].text, lines[index].confidence) for index in warning_indices],
        )
        if warning_text
        else check_warning("")
    )

    abv_index = _first_match(lines, is_alcohol_content_line, skip=warning_indices)
    net_index = _first_match(lines, _matcher(_NET_CONTENTS_LINE), skip=warning_indices)

    claimed = set(warning_indices)
    claimed.update(index for index in (abv_index, net_index) if index is not None)
    # Type set at 90 degrees is excluded from the ranking, not from the
    # reading. Its words are still in the text and still available to every
    # field located by pattern; what it cannot do is compete on type size,
    # because the number the ranking would use is not its type size. See
    # ``OcrLine.sideways``.
    claimed.update(index for index, line in enumerate(lines) if line.sideways)

    blocks = group_blocks(lines, claimed)
    brand = _standout(blocks)
    # A class or type designation is the second largest thing on the label, so
    # there has to be a largest for it to be second to. Where type size did not
    # find the brand name it has not found this either, and saying so twice is
    # the same answer given consistently rather than one field guessing on
    # evidence the other one rejected.
    remaining = [block for block in blocks if block is not brand] if brand else []
    class_type = _standout(remaining) if brand else None

    # Declined, not absent. Both report not found; only one of them means the
    # label had nothing to read. See ``ParsedFields.declined``.
    declined = frozenset(
        name
        for name, candidates, found in (
            ("brand_name", blocks, brand),
            ("class_type", remaining if brand else blocks, class_type),
        )
        if candidates and found is None
    )

    return ParsedFields(
        brand_name=brand.text if brand else None,
        class_type=class_type.text if class_type else None,
        alcohol_content=_text_at(lines, abv_index),
        net_contents=_text_at(lines, net_index),
        warning=warning,
        warning_text=warning_text,
        confidence={
            "brand_name": brand.confidence if brand else 0.0,
            "class_type": class_type.confidence if class_type else 0.0,
            "alcohol_content": _confidence_at(lines, abv_index),
            "net_contents": _confidence_at(lines, net_index),
            "government_warning": _mean_confidence(lines, warning_indices),
        },
        prominence={
            "brand_name": brand.height if brand else 0.0,
            "class_type": class_type.height if class_type else 0.0,
        },
        declined=declined,
        region={
            name: region
            for name, region in (
                ("brand_name", _region(brand)),
                ("class_type", _region(class_type)),
                ("alcohol_content", _region_at(lines, abv_index)),
                ("net_contents", _region_at(lines, net_index)),
                (
                    "government_warning",
                    _region_at(lines, warning_indices[0] if warning_indices else None),
                ),
            )
            if region is not None
        },
    )


def _region(block: TextBlock | None) -> TextRegion | None:
    """Where on the sheet a ranked block was set, or None if it was not found."""
    return None if block is None else TextRegion(column=block.column, block=block.block)


def _region_at(lines: list[OcrLine], index: int | None) -> TextRegion | None:
    """Where on the sheet a located line was set, or None if it was not found."""
    if index is None:
        return None
    return TextRegion(column=lines[index].column, block=lines[index].block)


def _find_warning(lines: list[OcrLine]) -> tuple[list[int], str | None]:
    """Return the indices of the warning lines and the statement as printed.

    Consumption starts at the line carrying the prefix and continues until the
    accumulated text is at least as long as 27 CFR 16.21's statement. Both ways
    of being wrong are safe: an omitted word makes the block over-run into the
    next line, an added word makes it stop short, and FR-5 requires a mismatch
    in either case.

    The length is measured after line-break hyphens are rejoined (A-15). A
    narrow hyphenated column carries two extra characters per split word, so
    measuring the printed text against the regulation's length stops collecting
    early and truncates the statement, which would report a compliant label as
    a mismatch for a reason that has nothing to do with its wording. What is
    returned is still the text as printed; only the stopping rule is joined.
    """
    start = _warning_start(lines)
    if start is None:
        return [], None

    target_length = len(normalize_whitespace(WARNING_STATEMENT))
    indices: list[int] = []
    collected: list[str] = []
    for index in range(start, len(lines)):
        if not _HAS_A_LETTER.search(lines[index].text):
            continue
        indices.append(index)
        collected.append(lines[index].text)
        if len(join_line_break_hyphens(normalize_whitespace(" ".join(collected)))) >= target_length:
            break
    return indices, normalize_whitespace(" ".join(collected))


def _warning_start(lines: list[OcrLine]) -> int | None:
    """The line the statement starts on: by its prefix, or by what survived of it.

    The prefix first, as always. Then a line carrying WARNING whose next two
    lines, joined, open the body, which is the prefix with GOVERNMENT damaged;
    the body has to follow so that another warning on the label, or the word
    on its own, is not taken for this one. Then the body's opening itself,
    for a prefix OCR lost entirely. What the fallbacks find is reported with
    its prefix illegible, never as a capitalization verdict (FR-6, ADR 0022).
    """
    for index, line in enumerate(lines):
        if _WARNING_PREFIX_LINE.search(line.text):
            return index
    for index, line in enumerate(lines):
        if _DAMAGED_PREFIX_LINE.search(line.text):
            window = " ".join(entry.text for entry in lines[index : index + 3])
            if _BODY_OPENING_LINE.search(window) and _BODY_CONTINUES_LINE.search(window):
                return index
    for index, line in enumerate(lines):
        if _BODY_OPENING_LINE.search(line.text):
            window = " ".join(entry.text for entry in lines[index : index + 3])
            if _BODY_CONTINUES_LINE.search(window):
                return index
    return None


def _matcher(pattern: re.Pattern[str]) -> Callable[[str], bool]:
    """Adapt a pattern to the predicate ``_first_match`` takes."""
    return lambda text: bool(pattern.search(text))


def _first_match(
    lines: list[OcrLine], matches: Callable[[str], bool], skip: list[int]
) -> int | None:
    """The first line the predicate accepts, ignoring lines already claimed.

    A predicate rather than a pattern because alcohol content is no longer one
    regular expression: it is a number and a marker on the same line, which two
    patterns express more clearly than one does.
    """
    skipped = set(skip)
    return next(
        (index for index, line in enumerate(lines) if index not in skipped and matches(line.text)),
        None,
    )


@dataclass(frozen=True)
class TextBlock:
    """Adjacent lines set in the same type size, read as one piece of text.

    A brand name too long for one line is set across two, in one size, and is
    still one brand name. Grouping before ranking is what stops "STONE'S THROW"
    from being read as a brand of "STONE'S" and a class or type of "THROW".

    ``column`` and ``block`` are where on the sheet it was set, carried through
    so the response can say which panel a field was read from (FR-1, FR-10).
    Every line in a block shares both, because a block that spanned two panels
    would be two pieces of text reported as one.
    """

    text: str
    height: float
    top: int
    confidence: float = 0.0
    column: int = 0
    block: int = 0


def group_blocks(lines: list[OcrLine], claimed: set[int]) -> list[TextBlock]:
    """Group unclaimed adjacent lines of similar type size into blocks.

    Two lines join when they are in the same region of the sheet, are adjacent
    on the label, their type sizes are within ``_SIZE_TOLERANCE`` of each other,
    and the vertical gap between them is no more than ``_GAP_LINES`` line
    heights. Lines with no size information, which is the plain-text path, never
    join: there is nothing to compare, and merging on position alone would join
    a brand name to whatever follows it.

    **Same region is the condition this release adds, and it is the same idea
    one level up.** ``app.ocr`` stops a line spanning two panels; this stops a
    block doing it. Without it the last line of one panel and the first line of
    the next are adjacent in reading order, and on the author's mezcal artwork
    that grouped the left panel's ``NOM-041X`` with a garbled fragment from the
    front panel into a single candidate for the brand name.
    """
    blocks: list[TextBlock] = []
    current: list[OcrLine] = []
    previous_index: int | None = None

    for index, line in enumerate(lines):
        if index in claimed:
            continue
        if (
            current
            and previous_index is not None
            and _joins(current[-1], line, index, previous_index)
        ):
            current.append(line)
        else:
            if current:
                blocks.append(_as_block(current))
            current = [line]
        previous_index = index

    if current:
        blocks.append(_as_block(current))
    return blocks


# Two lines set in the same point size can still report bounding boxes that
# differ by a fifth, because Tesseract measures the ink and not the type: a line
# containing a Q or a descender is taller than one that does not. The tolerance
# has to absorb that while still separating a 96 point brand name from a 48
# point class designation, which differ by half.
_SIZE_TOLERANCE = 0.25
_GAP_LINES = 2.5


def _joins(previous: OcrLine, line: OcrLine, index: int, previous_index: int) -> bool:
    if index != previous_index + 1:
        return False
    if (previous.column, previous.block) != (line.column, line.block):
        return False
    if previous.height <= 0 or line.height <= 0:
        return False
    tallest = max(previous.height, line.height)
    if abs(previous.height - line.height) / tallest > _SIZE_TOLERANCE:
        return False
    return (line.top - previous.top) <= _GAP_LINES * tallest


def _as_block(lines: list[OcrLine]) -> TextBlock:
    return TextBlock(
        text=" ".join(line.text for line in lines).strip(),
        height=max(line.height for line in lines),
        top=min(line.top for line in lines),
        confidence=round(sum(line.confidence for line in lines) / len(lines), 1),
        column=lines[0].column,
        block=lines[0].block,
    )


# How far clear of the next candidate the largest block has to be before type
# size is taken to have identified anything.
#
# **The ranking has to be able to decline, and this is where it does.** Ranking
# by type size answers "which is biggest" on any label whatever, including one
# where the two biggest things are the same size and one where the biggest thing
# is a misread. Reporting the winner of a photo finish as the brand name is a
# guess dressed as a reading, and FR-1 asks for not found instead.
#
# Measured as the ratio of the second candidate's type size to the first, over
# the twelve sample labels and the author's mezcal artwork:
#
# ==========================================  =============  ============
# label                                        second/first   third/second
# ==========================================  =============  ============
# the twelve sample labels                      0.46 - 0.64   0.40 - 0.51
# the author's mezcal artwork                          0.83          0.76
# ==========================================  =============  ============
#
# 0.70 is between the two clusters, and the whole of the space between them is
# 0.64 to 0.76. On every sample label the brand name is set at least half again
# the size of the class or type designation below it, which is what a label
# designer does and what this reads. On the mezcal artwork nothing separates:
# the tallest upright text on the sheet is a misread of a decorative element,
# the next is a misread of the fanciful name's display line, and they are within
# a sixth of each other. The honest answer there is that type size did not find
# the brand name, which is the truth: the COLA declares one brand and the
# artwork's own largest text is the fanciful name, so the heuristic is not
# merely inconclusive on that label, it is wrong on it.
_STANDOUT_RATIO = 0.70


def _standout(blocks: list[TextBlock]) -> TextBlock | None:
    """The block type size actually singles out, or None if it singles out none.

    Two conditions. The block has to be the largest, ties broken by reading
    order, which is the rule this has always used. And every other candidate has
    to be smaller than it by more than ``_STANDOUT_RATIO``, which is the rule
    this release adds and the reason the function can return None on a label
    that is full of text.

    A sole candidate stands out by default: there is nothing for it to be
    confused with. That is what keeps a label carrying only a brand name
    reading as a brand name.
    """
    if not blocks:
        return None
    leader = max(blocks, key=lambda block: (block.height, -block.top))
    others = [block for block in blocks if block is not leader]
    if not others:
        return leader
    if leader.height <= 0:
        # The plain-text path, which has no geometry at all. Reading order is
        # the only signal there and it is the one this has always used.
        return leader
    runner_up = max(block.height for block in others)
    return leader if runner_up <= _STANDOUT_RATIO * leader.height else None


def _text_at(lines: list[OcrLine], index: int | None) -> str | None:
    if index is None:
        return None
    return lines[index].text.strip() or None


def _confidence_at(lines: list[OcrLine], index: int | None) -> float:
    return 0.0 if index is None else lines[index].confidence


def _mean_confidence(lines: list[OcrLine], indices: list[int]) -> float:
    """Mean confidence over a run of lines, or 0.0 if the run is empty.

    Zero rather than None so that "not found" and "found but unreadable" order
    the same way when two photographs are compared: neither should beat a
    reading that actually exists.
    """
    if not indices:
        return 0.0
    return round(sum(lines[index].confidence for index in indices) / len(indices), 1)
