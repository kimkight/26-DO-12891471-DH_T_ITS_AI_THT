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
the brand name is the largest text. Nothing in the assignment states a layout
rule, so inventing one is not available; type size is a property of the artwork
itself rather than an assumption about it. Where the heuristic fails, the field
reports not found rather than reporting a guess, which is what FR-1 requires.
The rate at which it fails is measured, not asserted: see scripts/measure.py.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.ocr import OcrLine
from app.warning import (
    WARNING_STATEMENT,
    WarningCheck,
    check_warning,
    join_line_break_hyphens,
    normalize_whitespace,
)

_NUMBER = r"\d+(?:\.\d+)?"
_ABV_LINE = re.compile(
    rf"{_NUMBER}\s*(?:%|percent)|{_NUMBER}\s*proof|alc\.?\s*(?:/|\s)?\s*vol|abv",
    re.IGNORECASE,
)
_NET_CONTENTS_LINE = re.compile(
    rf"{_NUMBER}\s*(fl\.?\s*oz\.?|fluid\s+ounces?|milli\s?lit(?:er|re)s?|lit(?:er|re)s?|ml|mls|l)\b",
    re.IGNORECASE,
)
_WARNING_PREFIX_LINE = re.compile(r"government\s+warning", re.IGNORECASE)


@dataclass(frozen=True)
class ParsedFields:
    """What was found on the label. ``None`` means not found, explicitly."""

    brand_name: str | None
    class_type: str | None
    alcohol_content: str | None
    net_contents: str | None
    warning: WarningCheck
    warning_text: str | None


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
    warning = check_warning(warning_text) if warning_text else check_warning("")

    abv_index = _first_match(lines, _ABV_LINE, skip=warning_indices)
    net_index = _first_match(lines, _NET_CONTENTS_LINE, skip=warning_indices)

    claimed = set(warning_indices)
    claimed.update(index for index in (abv_index, net_index) if index is not None)

    blocks = group_blocks(lines, claimed)
    brand = _largest(blocks)
    remaining = [block for block in blocks if block is not brand]
    class_type = _largest(remaining)

    return ParsedFields(
        brand_name=brand.text if brand else None,
        class_type=class_type.text if class_type else None,
        alcohol_content=_text_at(lines, abv_index),
        net_contents=_text_at(lines, net_index),
        warning=warning,
        warning_text=warning_text,
    )


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
    start = next(
        (index for index, line in enumerate(lines) if _WARNING_PREFIX_LINE.search(line.text)),
        None,
    )
    if start is None:
        return [], None

    target_length = len(normalize_whitespace(WARNING_STATEMENT))
    indices: list[int] = []
    collected: list[str] = []
    for index in range(start, len(lines)):
        indices.append(index)
        collected.append(lines[index].text)
        if len(join_line_break_hyphens(normalize_whitespace(" ".join(collected)))) >= target_length:
            break
    return indices, normalize_whitespace(" ".join(collected))


def _first_match(lines: list[OcrLine], pattern: re.Pattern[str], skip: list[int]) -> int | None:
    skipped = set(skip)
    return next(
        (
            index
            for index, line in enumerate(lines)
            if index not in skipped and pattern.search(line.text)
        ),
        None,
    )


@dataclass(frozen=True)
class TextBlock:
    """Adjacent lines set in the same type size, read as one piece of text.

    A brand name too long for one line is set across two, in one size, and is
    still one brand name. Grouping before ranking is what stops "STONE'S THROW"
    from being read as a brand of "STONE'S" and a class or type of "THROW".
    """

    text: str
    height: float
    top: int


def group_blocks(lines: list[OcrLine], claimed: set[int]) -> list[TextBlock]:
    """Group unclaimed adjacent lines of similar type size into blocks.

    Two lines join when they are adjacent on the label, their type sizes are
    within ``_SIZE_TOLERANCE`` of each other, and the vertical gap between them
    is no more than ``_GAP_LINES`` line heights. Lines with no size information,
    which is the plain-text path, never join: there is nothing to compare, and
    merging on position alone would join a brand name to whatever follows it.
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
    )


def _largest(blocks: list[TextBlock]) -> TextBlock | None:
    """The block with the largest type, ties broken by reading order."""
    if not blocks:
        return None
    return max(blocks, key=lambda block: (block.height, -block.top))


def _text_at(lines: list[OcrLine], index: int | None) -> str | None:
    if index is None:
        return None
    return lines[index].text.strip() or None
