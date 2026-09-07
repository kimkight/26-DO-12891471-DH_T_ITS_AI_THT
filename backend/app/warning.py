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
from collections.abc import Sequence
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

# The statement located without its prefix intact (ADR 0022, 2026-09-06).
#
# **Measured on a real filing.** The bourbon's warning panel reads at 86.8 and
# the body comes back nearly complete, but printer registration marks run
# through the first word of the prefix, so GOVERNMENT reads as a garble and
# WARNING survives. Located by the prefix alone, that statement is reported as
# absent, which tells an agent the label has no warning when it plainly has
# one. So the prefix is the first thing looked for and not the only thing: a
# WARNING with the body opening within a few characters of it is the prefix
# with its first word damaged, and the body's own opening, which no other text
# on a label prints, locates the statement when even WARNING is gone. Either
# way the prefix is recorded as illegible rather than as anything else: its
# capitalization is not checked, because it was not read, and a checked
# capitalization is what FR-6 requires before the row can pass.
_DAMAGED_PREFIX_PATTERN = re.compile(r"\bwarning\s*:?", re.IGNORECASE)
# "According to the" rather than the whole clause, because on the measured read
# the word after it is a garble too; and the statement has to go on as the
# statement does within a few lines (``_BODY_CONTINUES``), so that those three
# words in a producer's story on a back label are not taken for it.
_BODY_OPENING = re.compile(
    r"(?:\(\s*1\s*\)\s*)?according\s+to\s+the|surgeon\s+general", re.IGNORECASE
)
_BODY_CONTINUES = re.compile(
    r"surgeon\s+general|should\s+not\s+drink|birth\s+defects|alcoholic\s+beverages",
    re.IGNORECASE,
)
_PREFIX_TO_BODY_CHARS = 40
_OPENING_TO_CONTINUATION_CHARS = 160

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
class LocatedWarning:
    """Where the statement starts in a run of label text, and how it was found."""

    prefix: str | None
    remainder: str
    # False when the prefix was not read as GOVERNMENT WARNING: either its first
    # word is a garble with WARNING intact, or the statement was found by its
    # body's opening alone. ``prefix`` then holds whatever was printed before
    # the body on that line, or None when nothing readable was.
    prefix_legible: bool


@dataclass(frozen=True)
class WarningCheck:
    """The outcome of both warning checks, reported separately (FR-6).

    ``body_matches`` is the FR-5 comparison: identical after whitespace and
    case normalization, or not. ``body_edit_distance`` and ``near_miss``
    are about what a difference is *reported* as, and neither can turn a
    mismatch into a match.

    ``uncertifiable`` is the third thing a difference can be reported as
    (ADR 0022), and it cannot turn a mismatch into a match either: the
    statement is on the label, it does not match, and every line of it that
    differs from the regulation was read below ``TTB_WARNING_LEGIBLE_CONFIDENCE``,
    so the difference belongs to the reading as far as the tool can tell and
    is not certified either way. A line that differs and was read confidently
    is the label's, and the outcome is the mismatch it always was.
    """

    found: bool
    prefix_found: str | None
    prefix_is_upper_case: bool | None
    body_found: str | None
    body_matches: bool
    reason: str
    bold_type_checked: bool = False
    bold_type_note: str = BOLD_TYPE_NOTE
    # Whether the prefix was read as GOVERNMENT WARNING at all. False when the
    # statement was located by WARNING alone or by its body's opening; the
    # capitalization check then has nothing it read to check.
    prefix_legible: bool = True
    # How many lines of the located statement are not a run of the regulation's
    # text, and how many of those were read below the legibility floor. Both
    # zero where no per-line confidence was supplied.
    differing_lines: int = 0
    illegible_lines: int = 0
    # Whether the difference is reported as uncertifiable rather than as a
    # mismatch: see the class docstring. Never true when the body matches and
    # the prefix is legible, and never true for a near miss, which has its own
    # outcome.
    uncertifiable: bool = False
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


def locate_warning(text: str) -> LocatedWarning | None:
    """Return the prefix as printed and the text following it, or None.

    The search is case-insensitive because a title-case prefix has to be found
    in order to be reported as a capitalization failure (FR-6). Finding it is
    not the same as accepting it.

    The prefix is looked for first. Failing that, the body's opening is looked
    for, and a WARNING within ``_PREFIX_TO_BODY_CHARS`` before it is taken as
    the prefix with its first word damaged; failing that too, the statement
    starts at the opening and the prefix is whatever else that line printed
    before it, or nothing. In both fallbacks ``prefix_legible`` is False.
    """
    match = _PREFIX_PATTERN.search(text)
    if match is not None:
        return LocatedWarning(match.group(0), text[match.end() :], prefix_legible=True)

    opening = _BODY_OPENING.search(text)
    if opening is None:
        return None
    continues = _BODY_CONTINUES.search(text, opening.end())
    if continues is None or continues.start() - opening.end() > _OPENING_TO_CONTINUATION_CHARS:
        return None
    line_start = text.rfind("\n", 0, opening.start()) + 1
    damaged = None
    for candidate in _DAMAGED_PREFIX_PATTERN.finditer(text, line_start, opening.start()):
        damaged = candidate
    if damaged is not None and opening.start() - damaged.end() <= _PREFIX_TO_BODY_CHARS:
        return LocatedWarning(
            text[line_start : damaged.end()], text[damaged.end() :], prefix_legible=False
        )
    before = text[line_start : opening.start()].strip() or None
    return LocatedWarning(before, text[opening.start() :], prefix_legible=False)


def _legibility(lines: Sequence[tuple[str, float]]) -> tuple[int, int]:
    """How many lines of the located statement differ, and how many of those read poorly.

    A line is a run of the regulation's text, or it is not. The test is a
    substring test on the folded, whitespace-normalized line against the
    folded statement, with a line-break hyphen taken off the end first (A-15),
    so a compliant statement set in a narrow column has no differing lines at
    all, and neither does a line OCR cut mid-word. A line that is not a run of
    the statement carries a garbled word, an inserted token, or an altered
    word, and which of those it is the tool cannot tell from the text. What it
    can tell is how confidently the engine read the line: below the floor the
    difference is the reading's as far as the evidence goes, at or above it the
    difference is the label's.

    A line with no letter in it is not counted either way. The statement's
    words are all letters, so a run of digits or marks cannot be one of them
    and cannot hide an altered one; ``app.parse`` leaves such lines out of the
    block for the same reason.

    A confidence of exactly zero means no reading happened, which is the
    plain-text path, and a line with no reading behind it is never called
    illegible: there is no evidence it was misread, and the stricter outcome
    stands.
    """
    folded_statement = fold_case(normalize_whitespace(WARNING_STATEMENT))
    differing = illegible = 0
    for text, confidence in lines:
        probe = fold_case(normalize_whitespace(text)).rstrip("-\u2010\u2011").strip()
        if not any(character.isalpha() for character in probe):
            continue
        if probe in folded_statement:
            continue
        differing += 1
        if 0 < confidence < settings.warning_legible_confidence:
            illegible += 1
    return differing, illegible


def check_warning(text: str, lines: Sequence[tuple[str, float]] | None = None) -> WarningCheck:
    """Check extracted label text against 27 CFR 16.21.

    Returns a mismatch rather than a review outcome for every failure, because
    FR-5 excludes fuzzy tolerance on this field: "Given a warning with altered,
    added, or omitted words, then the outcome is mismatch, not needs human
    review."

    ``lines`` is the located statement line by line with each line's OCR
    confidence, where the caller has one. It decides nothing about whether the
    statement matches; it decides only whether a statement that does not match
    is reported as a mismatch or as uncertifiable (ADR 0022), and a caller with
    no per-line reading gets the mismatch.
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

    prefix_as_printed, remainder = located.prefix, located.remainder
    # The join is applied here, after the prefix has been taken off, so that
    # what is reported as printed is what was printed and the capitalization
    # check reads the same characters it always did (FR-6, A-15).
    remainder = join_line_break_hyphens(remainder)
    prefix_normalized = (
        normalize_whitespace(prefix_as_printed) if prefix_as_printed is not None else None
    )
    # The colon is part of the required prefix but its absence is a wording
    # question, not a capitalization one, so the capitalization check reads the
    # letters only. A prefix that was not read as GOVERNMENT WARNING is not
    # checked: its capitalization is unknown, not failed (FR-6).
    if located.prefix_legible and prefix_normalized is not None:
        prefix_letters = prefix_normalized.rstrip(":").strip()
        prefix_is_upper: bool | None = prefix_letters == prefix_letters.upper()
    else:
        prefix_is_upper = None

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

    differing, illegible = _legibility(lines) if lines else (0, 0)
    # Uncertifiable only where the row cannot pass anyway and every line that
    # differs was read poorly; a near miss keeps its own outcome.
    uncertifiable = (
        (not body_matches or not located.prefix_legible)
        and not near_miss
        and differing > 0
        and illegible == differing
    )

    reason = _reason_for(
        prefix_normalized,
        prefix_is_upper,
        body_matches,
        distance,
        near_miss,
        prefix_legible=located.prefix_legible,
        uncertifiable=uncertifiable,
        differing=differing,
    )
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
        prefix_legible=located.prefix_legible,
        differing_lines=differing,
        illegible_lines=illegible,
        uncertifiable=uncertifiable,
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


def _uncertifiable_reason(differing: int, prefix_legible: bool) -> str:
    """What a difference read too poorly to attribute is reported as (ADR 0022).

    It says the statement is there, it says how much of it the engine could
    not read well, and it says what is being asked of the person. It does not
    say the statement is compliant and it does not say it is defective; the
    read cannot support either, and the outcome is not a pass.
    """
    lines = "line" if differing == 1 else "lines"
    prefix_note = (
        " The prefix was not read as 'GOVERNMENT WARNING:', so its capitalization "
        "was not checked either."
        if not prefix_legible
        else ""
    )
    return (
        "The government warning is on the label, and it reads correctly wherever "
        f"it was read well. {differing} {lines} of it differ from 27 CFR 16.21, and "
        f"every one of them was read below {settings.warning_legible_confidence:g} "
        "confidence, so the tool cannot tell a damaged read from a defect on the "
        "label. This is not a match and it is not certified word for word: check "
        f"the label itself.{prefix_note}"
    )


def _reason_for(
    prefix: str | None,
    prefix_is_upper: bool | None,
    body_matches: bool,
    distance: int = 0,
    near_miss: bool = False,
    *,
    prefix_legible: bool = True,
    uncertifiable: bool = False,
    differing: int = 0,
) -> str:
    """Name the rule that failed, so an agent can see which one it was (FR-6)."""
    if uncertifiable:
        return _uncertifiable_reason(differing, prefix_legible)
    if not prefix_legible:
        printed = f"it reads {prefix!r}" if prefix else "nothing readable precedes the statement"
        prefix_detail = (
            f"The prefix was not read as {WARNING_PREFIX!r}: {printed}. Its "
            "capitalization could not be checked (27 CFR 16.22(a)(2))."
        )
        body_detail = (
            "The statement text matches 27 CFR 16.21 word for word."
            if body_matches
            else _near_miss_reason(distance)
            if near_miss
            else "The statement text does not match 27 CFR 16.21 word for word."
        )
        return f"{prefix_detail} {body_detail}"
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
