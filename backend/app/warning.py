"""The government warning statement: exact body text plus a capitalization check.

Governing requirements: FR-5 (the body is compared for exact text after
whitespace and case normalization, with no fuzzy tolerance), FR-6 (the
``GOVERNMENT WARNING:`` prefix carries a separate upper-case check, reported
independently, and the result must not imply that bold type was verified),
OOS-4 (bold type is out of scope). Decision reference: D-5, ADR 0004.

The statement is quoted verbatim from 27 CFR 16.21 as recorded in
docs/03_REQUIREMENTS.md section 1, retrieved from eCFR on 2026-08-20.

**A near miss is routed to a person, not passed.** FR-5's exactness is not
loosened by anything here, and the distinction matters enough to state twice:
this is not a fuzzy match. The body still has to be identical to 27 CFR 16.21
after whitespace normalization to be reported as a match, and
``body_matches`` is still that comparison and nothing else. What changed on
2026-08-29 is what a *very* small difference is reported *as*. The author's own
COLA artwork OCRs the statement with exactly one character wrong, ``MPAIRS`` for
``IMPAIRS``, and calling that a mismatch tells an agent their label is defective
when the truth is that the scan is imperfect. A difference within
``TTB_WARNING_NEAR_MISS_EDITS`` characters is therefore reported as needing
human review, with the exact character-level difference shown so the agent can
see at a glance whether it is an artifact of reading or a real defect. Anything
beyond it is still a mismatch, and nothing is ever passed on a near miss. See
[ADR 0012](../../docs/adr/0012-warning-near-miss.md).

Why the prefix and the body are compared separately. FR-6 requires the
capitalization failure to be reportable as its own reason, which is UAT row 3:
a title-case ``Government Warning:`` must fail the capitalization check and name
capitalization as the reason. Comparing the prefix case-sensitively as part of
the body would report the same defect twice and blur which rule failed, so the
prefix is split off and the body is the remainder beginning at ``(1)``.
"""

from __future__ import annotations

import difflib
import re
from dataclasses import dataclass, field
from typing import Literal

from rapidfuzz.distance import Levenshtein

from app.config import settings

# Verbatim from 27 CFR 16.21, via docs/03_REQUIREMENTS.md section 1.
WARNING_PREFIX = "GOVERNMENT WARNING:"
WARNING_BODY = (
    "(1) According to the Surgeon General, women should not drink alcoholic "
    "beverages during pregnancy because of the risk of birth defects. "
    "(2) Consumption of alcoholic beverages impairs your ability to drive a car "
    "or operate machinery, and may cause health problems."
)
WARNING_STATEMENT = f"{WARNING_PREFIX} {WARNING_BODY}"

# What the result says about bold type, every time, so that no caller can report
# a warning outcome without it. 27 CFR 16.22(a)(2) also requires bold type; this
# prototype does not check it, and overstating what was checked is the failure
# mode UAT row 15 exists to catch.
BOLD_TYPE_NOTE = (
    "Bold type was not checked. 27 CFR 16.22(a)(2) requires the prefix in "
    "capital letters and in bold type; this prototype checks capitals only "
    "(OOS-4)."
)

_PREFIX_PATTERN = re.compile(r"government\s+warning\s*:?", re.IGNORECASE)
_WHITESPACE = re.compile(r"\s+")

# A word split across a line break by a printer's hyphen. The hyphen has to sit
# between two word characters, so a dash used as punctuation, which carries a
# space on both sides, is left alone. U+2010 and U+2011 are included because
# Tesseract reports whichever hyphen the typeface actually drew.
_LINE_BREAK_HYPHEN = re.compile(r"(?<=\w)[-\u2010\u2011]\s+(?=\w)")


def normalize_whitespace(text: str) -> str:
    """Collapse runs of whitespace, including line breaks, and strip the ends.

    Whitespace and letter case are the two normalizations FR-5 permits on the
    warning body; see ``fold_case`` for the second. Everything else is
    substantive.
    """
    return _WHITESPACE.sub(" ", text).strip()


def fold_case(text: str) -> str:
    """Flatten letter case, without moving a single character index.

    **Why case is normalized on the body (v1.1.0).** 27 CFR 16.21 fixes the
    *wording* of the statement; 27 CFR 16.22(a)(2) governs how it is set, and
    the only part of that this prototype checks is the prefix, which FR-6 checks
    separately and case-sensitively. Filed labels routinely set the whole
    statement in capitals, and the author's mezcal artwork is one of them: after
    the panel segmentation this release adds, its statement reads as 283
    characters in exactly the order the regulation sets them, and the exact
    comparison still failed on 209 differences of which every one was a capital
    letter. Reporting that as altered wording tells an agent their label is
    defective about the one thing it is demonstrably correct about.

    So case joins whitespace as presentational, and nothing else moves: an
    altered, added or omitted word still fails in either case, which
    tests/test_warning.py asserts in both.

    **Length-preserving, deliberately.** ``str.casefold`` is the right function
    for comparing two strings and the wrong one here, because it can return more
    characters than it was given, and ``body_diff`` slices the text as printed
    using indices taken from the folded text. Every character is lowered only
    where lowering it yields exactly one character, so the two stay index for
    index aligned and the diff an agent reads is still the label's own text.
    """
    return "".join(
        lowered if len(lowered := character.lower()) == 1 else character for character in text
    )


def join_line_break_hyphens(text: str) -> str:
    """Rejoin words a printer's hyphen split across a line break (A-15).

    A real bottle sets the warning in a column a few words wide, and the setter
    hyphenates to fill it: the label photographed in the first real-artwork test
    printed ``AC-`` / ``CORDING``, ``GEN-`` / ``ERAL`` and ``CONSUMP-`` /
    ``TION``. 27 CFR 16.21 fixes the wording of the statement, not where the
    lines break, so treating those splits as altered wording would report a
    compliant label as a mismatch on a typesetting decision.

    Applied to the label side only, and only to the body, which is what keeps it
    from weakening anything. It is not applied to the regulation constant, so a
    genuinely hyphenated word in the required text would still fail; and it is
    not applied before the prefix is located, so ``Government Warning:`` still
    fails the capitalization check exactly as it did (FR-6).

    Safe on this text specifically because 27 CFR 16.21 contains no hyphen at
    all: every hyphen inside a located statement is either a line-break hyphen,
    which this removes correctly, or an inserted word difference, which FR-5
    requires to be reported as a mismatch either way.
    """
    return _LINE_BREAK_HYPHEN.sub("", text)


# One run of the character-level comparison between the statement as printed and
# the statement as the regulation fixes it.
#
# ``kind`` reads from the label's point of view, because that is what the agent
# is looking at: ``same`` is text the two agree on, ``added`` is text on the
# label that the regulation does not have, and ``missing`` is text the
# regulation requires that the label does not show.
DiffKind = Literal["same", "added", "missing"]


@dataclass(frozen=True)
class DiffSegment:
    """One run of characters, and whether the two texts agree about it."""

    kind: DiffKind
    text: str


@dataclass(frozen=True)
class WarningCheck:
    """The outcome of both warning checks, reported separately (FR-6).

    ``body_matches`` is the FR-5 comparison: identical after whitespace and
    case normalization, or not. ``body_edit_distance`` and ``near_miss``
    are about what a difference is *reported* as, and neither can turn a
    mismatch into a match.
    """

    found: bool
    prefix_found: str | None
    prefix_is_upper_case: bool | None
    body_found: str | None
    body_matches: bool
    reason: str
    bold_type_checked: bool = False
    bold_type_note: str = BOLD_TYPE_NOTE
    # How many single-character edits separate the statement as printed from the
    # statement the regulation fixes. 0 when they match; None when no statement
    # was found, because there is nothing to measure a distance from.
    body_edit_distance: int | None = None
    # Whether that distance is small enough to be worth a person's judgement
    # rather than a flat mismatch. Never true when the body matches exactly.
    near_miss: bool = False
    # The character-level difference, for the agent to look at. Empty when the
    # body matches, and when nothing was found.
    body_diff: list[DiffSegment] = field(default_factory=list)

    @property
    def passes(self) -> bool:
        """True only when both the body and the capitalization check pass.

        Unchanged by the near-miss routing, deliberately: a near miss does not
        pass, it is routed to a person. ``app.verify`` reads ``near_miss`` to
        decide between the two failing outcomes.
        """
        return self.found and self.body_matches and bool(self.prefix_is_upper_case)


def body_diff(found: str, expected: str) -> list[DiffSegment]:
    """The character-level difference between two normalized statements.

    Character level rather than word level, because the differences worth
    telling apart here are inside words: ``MPAIRS`` against ``IMPAIRS`` is one
    missing character, and a word-level diff would report the whole word as
    changed and hide which kind of difference it was.

    ``autojunk`` is off. ``SequenceMatcher`` otherwise treats any character
    appearing in more than 1 percent of a long sequence as junk, which over a
    232-character sentence means the spaces and most vowels, and the resulting
    diff is unreadable.

    Matched on the case-folded pair and sliced from the originals, so a label
    setting the statement in capitals produces no difference to read while the
    text an agent is shown is still the text the label prints. ``fold_case``
    preserves length precisely so that those indices mean the same thing in
    both.
    """
    matcher = difflib.SequenceMatcher(None, fold_case(found), fold_case(expected), autojunk=False)
    segments: list[DiffSegment] = []
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            segments.append(DiffSegment(kind="same", text=found[i1:i2]))
            continue
        if found[i1:i2]:
            segments.append(DiffSegment(kind="added", text=found[i1:i2]))
        if expected[j1:j2]:
            segments.append(DiffSegment(kind="missing", text=expected[j1:j2]))
    return segments


def locate_warning(text: str) -> tuple[str, str] | None:
    """Return the prefix as printed and the text following it, or None.

    The search is case-insensitive because a title-case prefix has to be found
    in order to be reported as a capitalization failure (FR-6). Finding it is
    not the same as accepting it.
    """
    match = _PREFIX_PATTERN.search(text)
    if match is None:
        return None
    return match.group(0), text[match.end() :]


def check_warning(text: str) -> WarningCheck:
    """Check extracted label text against 27 CFR 16.21.

    Returns a mismatch rather than a review outcome for every failure, because
    FR-5 excludes fuzzy tolerance on this field: "Given a warning with altered,
    added, or omitted words, then the outcome is mismatch, not needs human
    review."
    """
    located = locate_warning(text)
    if located is None:
        return WarningCheck(
            found=False,
            prefix_found=None,
            prefix_is_upper_case=None,
            body_found=None,
            body_matches=False,
            reason=(
                "The government warning statement was not found on the label. "
                "27 CFR 16.21 requires it on all alcohol beverage labels."
            ),
        )

    prefix_as_printed, remainder = located
    # The join is applied here, after the prefix has been taken off, so that
    # what is reported as printed is what was printed and the capitalization
    # check reads the same characters it always did (FR-6, A-15).
    remainder = join_line_break_hyphens(remainder)
    prefix_normalized = normalize_whitespace(prefix_as_printed)
    # The colon is part of the required prefix but its absence is a wording
    # question, not a capitalization one, so the capitalization check reads the
    # letters only.
    prefix_letters = prefix_normalized.rstrip(":").strip()
    prefix_is_upper = prefix_letters == prefix_letters.upper()

    body_found = normalize_whitespace(remainder)
    expected_body = normalize_whitespace(WARNING_BODY)
    # Compared on the folded pair and reported as printed. FR-5's exactness is
    # untouched: the two normalizations are whitespace and case, and every
    # difference of wording still fails.
    body_matches = fold_case(body_found) == fold_case(expected_body)

    # Measured only when the exact comparison has already failed, so nothing
    # about a matching statement depends on it.
    distance = (
        0 if body_matches else Levenshtein.distance(fold_case(body_found), fold_case(expected_body))
    )
    near_miss = not body_matches and distance <= settings.warning_near_miss_edits
    diff = [] if body_matches else body_diff(body_found, expected_body)

    reason = _reason_for(prefix_normalized, prefix_is_upper, body_matches, distance, near_miss)
    return WarningCheck(
        found=True,
        prefix_found=prefix_normalized,
        prefix_is_upper_case=prefix_is_upper,
        body_found=body_found,
        body_matches=body_matches,
        reason=reason,
        body_edit_distance=distance,
        near_miss=near_miss,
        body_diff=diff,
    )


def _near_miss_reason(distance: int) -> str:
    """What a difference of one or two characters is reported as, and why.

    It names the number of characters and it names the judgement being asked
    for. It does not say the statement is compliant, and it does not say it is
    defective: the point of routing this to a person is that the tool cannot
    tell an OCR artifact from a real defect at this size, and pretending
    otherwise in either direction would be the tool overstating what it knows.
    """
    characters = "character" if distance == 1 else "characters"
    return (
        f"The statement differs from 27 CFR 16.21 by {distance} {characters}. "
        "That is small enough to be a reading error rather than a defect on the "
        "label, so this is for you to judge rather than for the tool to call. "
        "The exact difference is shown; check it against the label itself. This "
        "is not a match: the comparison is exact and the text is not identical."
    )


def _reason_for(
    prefix: str,
    prefix_is_upper: bool,
    body_matches: bool,
    distance: int = 0,
    near_miss: bool = False,
) -> str:
    """Name the rule that failed, so an agent can see which one it was (FR-6)."""
    body_detail = (
        _near_miss_reason(distance)
        if near_miss
        else "The statement text does not match 27 CFR 16.21 word for word."
    )
    if not prefix_is_upper and not body_matches:
        return (
            f"Two failures. The prefix reads {prefix!r} rather than "
            f"{WARNING_PREFIX!r}, which fails the capitalization check required "
            f"by 27 CFR 16.22(a)(2). {body_detail}"
        )
    if not prefix_is_upper:
        return (
            f"Capitalization. The prefix reads {prefix!r} rather than "
            f"{WARNING_PREFIX!r}. 27 CFR 16.22(a)(2) requires capital letters. "
            "The statement text itself matches 27 CFR 16.21."
        )
    if not body_matches:
        return f"{body_detail} The prefix capitalization is correct."
    return (
        "The statement matches 27 CFR 16.21 word for word after whitespace and "
        "case normalization, and the prefix is in capital letters."
    )
