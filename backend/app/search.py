"""Verification by search: ask whether a declared value appears on the label.

Governing requirements: FR-1 (what the tool reports about a field on the label),
FR-2 (the application's values are what the label is checked against), FR-3 (the
three outcomes, at the thresholds A-4 sets), FR-4 (case and punctuation
tolerance). Decision reference: [ADR 0015](../../docs/adr/0015-verify-by-search.md).

**This module exists because extraction is the fragile half and the task never
needed it.** Until v1.1.0 the tool located a value on the label, by type size for
the brand name and the class or type designation, and then compared two strings.
Locating is a ranking over candidates, and a ranking can be wrong or can decline;
comparing is only ever as good as what the ranking handed it. Every field-level
failure reported against the deployed prototype was a failure of the first step:

* the brand name reported as not found, because on the author's mezcal artwork
  the largest upright text is a misread of ``Vida Clasico`` and nothing on the
  sheet stands clear of it (``app.parse._standout``);
* the class or type designation reported as not found for the same reason, one
  rank down;
* before Session 16, the brand name reported as the producer's tax identifier,
  because the ranking picked a vertical strip in the gutter.

On that same document the application states ``DEL MAGUEY`` and the label text
the pipeline had already read contains ``DEL MAGUEY``, exactly. The tool said
"not found" about a string it was holding.

**So the question is inverted.** The application declares the answer, so the
check is not "what is the brand name on this label" but "does ``DEL MAGUEY``
appear on this label". That question has a reliable answer even when the reading
is imperfect, because a search for a known target degrades gracefully: a
character misread costs a few points of similarity, where a ranking that
declines costs the whole field.

**What a hit establishes, and what it does not.** A hit establishes that the
declared text appears on the label. It does not establish that it appears *as*
the brand name, in the type size 27 CFR requires, or on the panel it is required
on. Type size and placement are OOS-5 and are not checked by this prototype at
all. That is a weaker claim than locating-then-comparing pretended to make, and
it is a far stronger one than "not found" about text the tool has read. It is
stated on the screen and in FR-1 rather than left to this docstring.

Nothing here scores the government warning. FR-5 is a search for a fixed
statutory string already, it is exact rather than fuzzy by requirement, and it
returns an exact match on the author's document. It is untouched; see
``app.warning``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from rapidfuzz import fuzz

from app.compare import Comparison, Outcome, classify, normalize_text
from app.config import settings
from app.ocr import OcrLine
from app.parse import TextRegion

# A window may be one word shorter or one word longer than the declared value.
#
# Both directions are OCR artifacts rather than tolerances of meaning. A space
# recognized inside a word splits one word into two, so the label carries one
# more token than the application does; a space missed between two words joins
# them, so it carries one fewer. Beyond one token in either direction the window
# is a different phrase, and letting it compete would let a long enough block of
# text score against anything.
_WINDOW_SLACK = 1


@dataclass(frozen=True)
class LabelUnit:
    """One region of the label, as one searchable piece of text.

    A unit is every line the reading put in one region of the sheet, joined in
    reading order. ``app.ocr`` guarantees that no line spans two regions, so a
    unit is one panel's worth of one Tesseract block and a hit inside it can be
    reported as a place: "found in column 0, block 3" (FR-1, FR-10).

    Joining the lines rather than searching them one at a time is what finds a
    brand name set across two lines. ``STONE'S`` above ``THROW`` is two lines and
    one brand, and a search that only ever looked at a line would find neither.

    ``words`` carries each word twice: as printed, and normalized. The printed
    form is what the row shows the agent, so ``Stone's Throw`` is reported in the
    label's own casing beside the application's ``STONE'S THROW``; the normalized
    form is what is scored. Keeping them side by side is what makes the two
    consistent, rather than normalizing twice and hoping the tokenizations agree.
    """

    region: TextRegion
    words: tuple[tuple[str, str], ...]

    @property
    def normalized(self) -> str:
        return " ".join(normalized for _, normalized in self.words)


@dataclass(frozen=True)
class SearchHit:
    """Where a declared value was found on the label, and how well.

    ``text`` is the label's own printing of the matched run, not the declared
    value echoed back. That distinction is the whole of what the row shows: an
    agent looking at ``Stone's Throw`` beside ``STONE'S THROW`` can see at a
    glance that the difference is case, which is the FR-4 case Dave Morrison
    described, and they can see it without being told.
    """

    text: str
    score: float
    region: TextRegion


def label_units(lines: list[OcrLine]) -> list[LabelUnit]:
    """Group a reading's lines into one searchable unit per region of the sheet.

    Order is preserved: regions come out in the order their first line was read,
    and lines are joined in the order they were read within a region. On a
    single-panel label that is one unit holding the whole reading, which is what
    every label that is not a four-panel flat sheet produces.
    """
    order: list[TextRegion] = []
    collected: dict[TextRegion, list[tuple[str, str]]] = {}
    for line in lines:
        region = TextRegion(column=line.column, block=line.block)
        if region not in collected:
            collected[region] = []
            order.append(region)
        collected[region].extend(_words(line.text))
    return [
        LabelUnit(region=region, words=tuple(collected[region]))
        for region in order
        if collected[region]
    ]


def _words(text: str) -> list[tuple[str, str]]:
    """Split one line into (as printed, normalized) pairs, dropping empties.

    A word whose every character is punctuation normalizes to nothing. It is
    dropped rather than kept as an empty token, so that a stray bullet or rule
    between two words does not push them out of one window.
    """
    pairs = [(word, normalize_text(word)) for word in text.split()]
    return [(printed, normalized) for printed, normalized in pairs if normalized]


def find_on_label(declared: str, units: list[LabelUnit]) -> SearchHit | None:
    """The best place the declared value appears on the label, or None.

    Two passes, and the first is why this is not simply fuzzy matching.

    **Exact containment, on word boundaries, scores 100.** Where the normalized
    declared value appears as a run of whole words inside a unit, that is the
    answer and no similarity is computed: ``DEL MAGUEY`` is on the label, and a
    score would only invite the reader to wonder how nearly. Word boundaries are
    what keeps ``VIDA`` from being found inside ``INDIVIDUAL``: a value that
    appears only inside a longer word has not been found, because a label reading
    ``INDIVIDUAL`` does not carry the brand ``VIDA``.

    **Otherwise the best window is scored.** Windows are runs of words the length
    of the declared value, give or take ``_WINDOW_SLACK`` for a space OCR
    invented or dropped, and each is scored with the same ``fuzz.ratio``
    ``compare_text`` uses. Scoring windows rather than whole units is what stops
    a long panel diluting a real hit: the brand name in the middle of forty words
    of body copy scores as itself rather than as one fortieth of a paragraph.

    Ties go to the earliest unit and the earliest window inside it, so the result
    does not depend on iteration order.
    """
    needle = [normalized for _, normalized in _words(declared)]
    if not needle:
        return None

    best: SearchHit | None = None
    joined = " ".join(needle)
    for unit in units:
        exact = _exact(unit, needle)
        if exact is not None:
            return exact
        for start, length in _windows(len(unit.words), len(needle)):
            window = unit.words[start : start + length]
            score = fuzz.ratio(" ".join(normalized for _, normalized in window), joined)
            if best is None or score > best.score:
                best = SearchHit(
                    text=" ".join(printed for printed, _ in window),
                    score=round(score, 1),
                    region=unit.region,
                )
    return best


def _exact(unit: LabelUnit, needle: list[str]) -> SearchHit | None:
    """The first whole-word run in this unit equal to the declared words."""
    words = [normalized for _, normalized in unit.words]
    for start in range(len(words) - len(needle) + 1):
        if words[start : start + len(needle)] == needle:
            return SearchHit(
                text=" ".join(printed for printed, _ in unit.words[start : start + len(needle)]),
                score=100.0,
                region=unit.region,
            )
    return None


def _windows(available: int, wanted: int) -> list[tuple[int, int]]:
    """Every (start, length) window worth scoring, longest lengths last.

    Lengths run from one word shorter to one word longer than the declared
    value, clamped to at least one word and to what the unit actually holds.
    """
    lengths = sorted(
        {
            length
            for offset in range(-_WINDOW_SLACK, _WINDOW_SLACK + 1)
            if 1 <= (length := wanted + offset) <= available
        }
    )
    return [(start, length) for length in lengths for start in range(available - length + 1)]


# A registry code printed after the class or type description. On the author's
# own filing the application states ``MEZCAL FB``: ``MEZCAL`` is what the label
# prints and ``FB`` is a code the registry carries beside it. Searching a label
# for ``MEZCAL FB`` asks it to print a code no label prints.
#
# One to three characters, upper case letters or digits, at the end, with
# something left in front of it. Short and upper case because that is what a
# code looks like and what a word does not; the leading numeric form
# (``141 - BOURBON WHISKY``) is already split off by
# ``app.application_form._CODED_CLASS_TYPE`` before a value reaches here.
_TRAILING_CODE = re.compile(r"^(?P<value>.*\S)\s+(?P<code>[A-Z0-9]{1,3})\s*$")


def without_trailing_code(declared: str) -> tuple[str, str | None]:
    """The declared class or type with a trailing registry code taken off.

    Returns the value to search for and the code that was removed, or the value
    unchanged and None. **The caller searches for the full value first and only
    falls back to this**, so stripping can never lose a match: a designation that
    genuinely ends in a short upper-case token is found before this is reached.
    """
    match = _TRAILING_CODE.match(declared.strip())
    if match is None:
        return declared, None
    return match.group("value"), match.group("code")


# What a row says about the limit of a hit, in one sentence.
#
# **The sentence is the requirement, not a caveat on it.** FR-1 used to promise
# that the tool had identified the brand name on the label. It never could; type
# size was a heuristic and it declined on the first real label the author tried.
# What is promised now is exactly what a search establishes, and the second half
# of the sentence is the half that keeps it honest.
PRESENCE_LIMIT = (
    "This shows the declared value appears on the label. It does not show it "
    "appears as the brand, in the required type size, or on the required panel "
    "(OOS-5)."
)


def verify_presence(
    field_label: str,
    declared: str,
    units: list[LabelUnit],
    *,
    strip_trailing_code: bool = False,
) -> tuple[Comparison, SearchHit | None]:
    """Check one declared value against the label by searching for it (FR-1).

    The outcome comes from ``app.compare.classify``, which is A-4's thresholds
    unchanged: at or above the match threshold is a match, the band below it is
    needs human review, and below that the value was not found on the label. No
    new number is introduced, because a similarity between a declared value and a
    run of label text is the same kind of quantity FR-3 already classifies and
    inventing a second scale for it would leave two definitions of "close".

    ``strip_trailing_code`` is the class or type case. The full value is searched
    for first, so nothing is stripped from a designation that really ends that
    way; only when the full value fails does the code come off and the search run
    again, and the row says that it did.
    """
    hit = find_on_label(declared, units)
    # What was actually searched for, which is the declared value unless a
    # registry code came off it. Carried separately so the reason names the
    # string that was looked for rather than the one the form printed.
    sought = declared
    note = ""
    if strip_trailing_code and (hit is None or hit.score < settings.match_threshold):
        shortened, code = without_trailing_code(declared)
        if code is not None:
            retried = find_on_label(shortened, units)
            if retried is not None and (hit is None or retried.score > hit.score):
                hit = retried
                sought = shortened
                note = (
                    f" The application states {declared!r}; {code!r} is a registry "
                    f"code rather than label text, so it was left off the search."
                )

    if hit is None:
        return (
            Comparison(
                outcome=Outcome.MISMATCH,
                score=None,
                reason=(
                    f"{field_label} was searched for on the label and no text was "
                    "read to search. It is reported as not found rather than as "
                    "empty or omitted (FR-1)."
                ),
            ),
            None,
        )

    outcome = classify(hit.score)
    where = f"column {hit.region.column}, block {hit.region.block}"
    if outcome is Outcome.MATCH:
        reason = (
            f"{sought!r} was found on the label, in {where}, printed as "
            f"{hit.text!r}.{note} {PRESENCE_LIMIT}"
        )
    elif outcome is Outcome.NEEDS_REVIEW:
        reason = (
            f"The closest text on the label to {sought!r} is {hit.text!r}, in "
            f"{where}, scoring {hit.score:.1f} against a match threshold of "
            f"{settings.match_threshold}.{note} That is close enough to be a "
            "reading error and not close enough to call a match, so it is a "
            "person's call (FR-3)."
        )
    else:
        reason = (
            f"{sought!r} was not found on the label. The closest text read "
            f"anywhere on it is {hit.text!r}, in {where}, scoring {hit.score:.1f} "
            f"against a review threshold of {settings.review_threshold}.{note} "
            "It is reported as not found rather than as a guess (FR-1)."
        )
    return Comparison(outcome=outcome, score=hit.score, reason=reason), hit
