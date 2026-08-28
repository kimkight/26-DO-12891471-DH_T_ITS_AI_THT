"""The government warning statement: exact body text plus a capitalization check.

Governing requirements: FR-5 (the body is compared for exact text after
whitespace normalization, with no fuzzy tolerance), FR-6 (the
``GOVERNMENT WARNING:`` prefix carries a separate upper-case check, reported
independently, and the result must not imply that bold type was verified),
OOS-4 (bold type is out of scope). Decision reference: D-5, ADR 0004.

The statement is quoted verbatim from 27 CFR 16.21 as recorded in
docs/03_REQUIREMENTS.md section 1, retrieved from eCFR on 2026-08-20.

Why the prefix and the body are compared separately. FR-6 requires the
capitalization failure to be reportable as its own reason, which is UAT row 3:
a title-case ``Government Warning:`` must fail the capitalization check and name
capitalization as the reason. Comparing the prefix case-sensitively as part of
the body would report the same defect twice and blur which rule failed, so the
prefix is split off and the body is the remainder beginning at ``(1)``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

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

    This is the only normalization FR-5 permits on the warning body: line breaks
    and runs of spaces are presentational, and everything else is substantive.
    """
    return _WHITESPACE.sub(" ", text).strip()


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


@dataclass(frozen=True)
class WarningCheck:
    """The outcome of both warning checks, reported separately (FR-6)."""

    found: bool
    prefix_found: str | None
    prefix_is_upper_case: bool | None
    body_found: str | None
    body_matches: bool
    reason: str
    bold_type_checked: bool = False
    bold_type_note: str = BOLD_TYPE_NOTE

    @property
    def passes(self) -> bool:
        """True only when both the body and the capitalization check pass."""
        return self.found and self.body_matches and bool(self.prefix_is_upper_case)


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
    body_matches = body_found == expected_body

    reason = _reason_for(prefix_normalized, prefix_is_upper, body_matches)
    return WarningCheck(
        found=True,
        prefix_found=prefix_normalized,
        prefix_is_upper_case=prefix_is_upper,
        body_found=body_found,
        body_matches=body_matches,
        reason=reason,
    )


def _reason_for(prefix: str, prefix_is_upper: bool, body_matches: bool) -> str:
    """Name the rule that failed, so an agent can see which one it was (FR-6)."""
    if not prefix_is_upper and not body_matches:
        return (
            f"Two failures. The prefix reads {prefix!r} rather than "
            f"{WARNING_PREFIX!r}, which fails the capitalization check required "
            "by 27 CFR 16.22(a)(2), and the statement text does not match "
            "27 CFR 16.21 word for word."
        )
    if not prefix_is_upper:
        return (
            f"Capitalization. The prefix reads {prefix!r} rather than "
            f"{WARNING_PREFIX!r}. 27 CFR 16.22(a)(2) requires capital letters. "
            "The statement text itself matches 27 CFR 16.21."
        )
    if not body_matches:
        return (
            "The statement text does not match 27 CFR 16.21 word for word. "
            "The prefix capitalization is correct."
        )
    return (
        "The statement matches 27 CFR 16.21 word for word after whitespace "
        "normalization, and the prefix is in capital letters."
    )
