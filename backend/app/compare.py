"""Field comparison: normalization, fuzzy scoring, and the three outcomes.

Governing requirements: FR-3 (three outcomes at configured thresholds), FR-4
(case and punctuation tolerance), FR-7 (numeric comparison with a text
fallback), A-4 (the 95 and 80 defaults), A-12 (alcohol content), A-13 (net
contents). Decision reference: D-5, ADR 0004.

Two rules in this module differ from each other on purpose, and the difference
is sourced rather than chosen:

- An **alcohol content** value that cannot be parsed routes to needs human
  review, because A-12 says so explicitly: "If either value cannot be parsed as
  a number: needs human review, with the raw strings shown, falling back to text
  comparison as FR-7 already requires." The text score is computed and shown,
  but it does not decide the outcome.
- A **net contents** value that cannot be parsed falls back to the text outcome,
  because A-13 states no rule for it and FR-7's general criterion applies: "the
  system falls back to text comparison and says so, rather than reporting a
  false mismatch."
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from enum import StrEnum

from rapidfuzz import fuzz

from app.config import settings


class Outcome(StrEnum):
    """The outcome of one field comparison.

    ``MATCH``, ``NEEDS_REVIEW`` and ``MISMATCH`` are the three outcomes FR-3
    requires. ``NOT_COMPARED`` is required separately by FR-2: "Given
    application data missing a field, then that field is reported as not
    compared, and this is distinguished from a mismatch."
    """

    MATCH = "match"
    NEEDS_REVIEW = "needs_review"
    MISMATCH = "mismatch"
    NOT_COMPARED = "not_compared"


@dataclass(frozen=True)
class Comparison:
    """One field comparison, carrying the evidence as well as the verdict.

    FR-3 requires the score and both values in the result "so that an agent can
    judge the call rather than trust it".
    """

    outcome: Outcome
    score: float | None
    reason: str


# Typographic apostrophes and quotes, mapped to the straight forms. Dave's
# STONE'S THROW case arrives with either, depending on what produced the text.
_APOSTROPHES = {
    "‘": "'",
    "’": "'",
    "‚": "'",
    "‛": "'",
    "′": "'",
    "´": "'",
    "`": "'",
    "“": '"',
    "”": '"',
    "″": '"',
}
_WHITESPACE = re.compile(r"\s+")


def normalize_text(value: str) -> str:
    """Casefold, straighten apostrophes, drop punctuation, collapse whitespace.

    FR-4: "Text comparison normalizes case, surrounding whitespace, and
    punctuation before scoring, so that presentational differences do not read
    as substantive ones." Nothing here removes or reorders words, so two
    genuinely different names stay different (FR-4, third criterion).
    """
    text = unicodedata.normalize("NFKC", value)
    for source, target in _APOSTROPHES.items():
        text = text.replace(source, target)
    text = "".join(" " if unicodedata.category(ch).startswith("P") else ch for ch in text)
    return _WHITESPACE.sub(" ", text).strip().casefold()


def classify(score: float) -> Outcome:
    """Map a similarity score to one of the three outcomes (FR-3, A-4).

    The boundaries are inclusive at the bottom of each band: a score exactly at
    ``TTB_MATCH_THRESHOLD`` is a match, and a score exactly at
    ``TTB_REVIEW_THRESHOLD`` needs review.
    """
    if score >= settings.match_threshold:
        return Outcome.MATCH
    if score >= settings.review_threshold:
        return Outcome.NEEDS_REVIEW
    return Outcome.MISMATCH


def compare_text(label_value: str | None, application_value: str | None) -> Comparison:
    """Compare two free-text fields (FR-4)."""
    missing = _missing(label_value, application_value)
    if missing is not None:
        return missing

    normalized_label = normalize_text(label_value or "")
    normalized_application = normalize_text(application_value or "")
    if not normalized_label or not normalized_application:
        return Comparison(
            outcome=Outcome.NEEDS_REVIEW,
            score=None,
            reason="One of the two values is empty after normalization.",
        )

    score = fuzz.ratio(normalized_label, normalized_application)
    outcome = classify(score)
    return Comparison(
        outcome=outcome,
        score=round(score, 1),
        reason=(
            f"Normalized similarity {score:.1f} against a match threshold of "
            f"{settings.match_threshold} and a review threshold of "
            f"{settings.review_threshold}."
        ),
    )


# ---------------------------------------------------------------------------
# Alcohol content (FR-7, A-12)
# ---------------------------------------------------------------------------

_NUMBER = r"\d+(?:\.\d+)?"
_ABV_RANGE = re.compile(
    rf"({_NUMBER})\s*(?:%|percent)?\s*(?:to|-|–)\s*({_NUMBER})\s*(?:%|percent)",
    re.IGNORECASE,
)
_ABV_PERCENT = re.compile(rf"({_NUMBER})\s*(?:%|percent)", re.IGNORECASE)
_ABV_BARE = re.compile(rf"^\s*({_NUMBER})\s*$")
_PROOF = re.compile(rf"({_NUMBER})\s*proof", re.IGNORECASE)


@dataclass(frozen=True)
class AbvReading:
    """What could be read out of one alcohol content string."""

    percent: float | None
    proof: float | None
    range_low: float | None = None
    range_high: float | None = None

    @property
    def is_range(self) -> bool:
        return self.range_low is not None


def parse_abv(value: str | None) -> AbvReading:
    """Read an ABV percentage, and a proof value if one is stated.

    Accepts the percent forms (``45%``, ``45% Alc./Vol.``, ``ABV 45 percent``),
    a bare number (the application form's usual shape, per A-12), the proof form
    (``90 Proof``), and a range (``12 to 14% alc/vol``, permitted for wine under
    27 CFR 4.36).
    """
    if value is None:
        return AbvReading(percent=None, proof=None)

    proof_match = _PROOF.search(value)
    proof = float(proof_match.group(1)) if proof_match else None

    # The proof clause is removed before the percentage is read, so that
    # "45% Alc./Vol. (90 Proof)" does not offer 90 as a candidate percentage.
    without_proof = _PROOF.sub(" ", value)

    range_match = _ABV_RANGE.search(without_proof)
    if range_match:
        low = float(range_match.group(1))
        high = float(range_match.group(2))
        return AbvReading(percent=None, proof=proof, range_low=low, range_high=high)

    percent_match = _ABV_PERCENT.search(without_proof) or _ABV_BARE.search(without_proof)
    percent = float(percent_match.group(1)) if percent_match else None
    return AbvReading(percent=percent, proof=proof)


def compare_abv(label_value: str | None, application_value: str | None) -> Comparison:
    """Compare declared alcohol content values (FR-7, A-12).

    Order of the rules matters and follows A-12: an internal inconsistency on
    the label itself (proof that is not twice the ABV) routes to review even
    when the two declared percentages agree, because the label contradicts
    itself and that is a person's call.
    """
    missing = _missing(label_value, application_value)
    if missing is not None:
        return missing

    label = parse_abv(label_value)
    application = parse_abv(application_value)

    if label.is_range:
        return Comparison(
            outcome=Outcome.NEEDS_REVIEW,
            score=None,
            reason=(
                f"The label states a range, {label.range_low:g} to "
                f"{label.range_high:g} percent, and the application states "
                f"{application_value!r}. Ranges are permitted for wine under "
                "27 CFR 4.36; this prototype does not evaluate range semantics "
                "(A-12)."
            ),
        )

    if label.percent is None or application.percent is None:
        fallback = compare_text(label_value, application_value)
        return Comparison(
            outcome=Outcome.NEEDS_REVIEW,
            score=fallback.score,
            reason=(
                "Alcohol content could not be read as a number on "
                f"{'the label' if label.percent is None else 'the application'} "
                f"side: label {label_value!r}, application {application_value!r}. "
                "Fell back to text comparison, which scored "
                f"{'no score' if fallback.score is None else format(fallback.score, '.1f')}. "
                "A-12 routes an unparseable alcohol content to human review "
                "rather than to a text outcome."
            ),
        )

    if label.proof is not None:
        expected_proof = 2 * label.percent
        if abs(label.proof - expected_proof) > 1e-9:
            return Comparison(
                outcome=Outcome.NEEDS_REVIEW,
                score=None,
                reason=(
                    f"The label states {label.percent:g} percent alcohol and "
                    f"{label.proof:g} proof. 27 CFR 5.65 defines proof as twice "
                    f"the alcohol by volume, so {label.percent:g} percent should "
                    f"read {expected_proof:g} proof. The label contradicts "
                    "itself (A-12)."
                ),
            )

    difference = abs(label.percent - application.percent)
    if difference <= settings.abv_tolerance:
        proof_note = (
            f" The stated {label.proof:g} proof is twice the alcohol by volume, "
            "as 27 CFR 5.65 defines it."
            if label.proof is not None
            else ""
        )
        return Comparison(
            outcome=Outcome.MATCH,
            score=100.0,
            reason=(
                f"Label {label.percent:g} percent and application "
                f"{application.percent:g} percent are numerically equal."
                f"{proof_note}"
            ),
        )

    return Comparison(
        outcome=Outcome.MISMATCH,
        score=0.0,
        reason=(
            f"Label {label.percent:g} percent against application "
            f"{application.percent:g} percent, a difference of "
            f"{difference:g} percentage points. The configured tolerance is "
            f"{settings.abv_tolerance:g}. The tolerances in 27 CFR 5.65, 4.36 "
            "and 7.65 govern actual against labeled content and do not apply to "
            "two values the applicant declared (A-12)."
        ),
    )


# ---------------------------------------------------------------------------
# Net contents (FR-7, A-13)
# ---------------------------------------------------------------------------

_UNIT_ALIASES = {
    "ml": "mL",
    "mls": "mL",
    "milliliter": "mL",
    "milliliters": "mL",
    "millilitre": "mL",
    "millilitres": "mL",
    "l": "L",
    "liter": "L",
    "liters": "L",
    "litre": "L",
    "litres": "L",
    "floz": "fl oz",
    "fluidounce": "fl oz",
    "fluidounces": "fl oz",
}
_NET_CONTENTS = re.compile(
    rf"({_NUMBER})\s*"
    r"(fl\.?\s*oz\.?|fluid\s+ounces?|milli\s?lit(?:er|re)s?|lit(?:er|re)s?|ml|mls|l)\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class NetContentsReading:
    """A net contents value and its unit, or None where neither could be read."""

    value: float | None
    unit: str | None


def normalize_unit(unit: str) -> str:
    """Fold a unit spelling onto its canonical form (A-13).

    Only the spellings A-13 names are folded. No conversion between units
    happens anywhere in this module: "Given two values in different units, for
    example 750 mL against 25.4 fl oz, then the outcome is needs human review
    and no conversion is performed."
    """
    key = re.sub(r"[\s.]", "", unit).casefold()
    return _UNIT_ALIASES.get(key, unit.strip())


def parse_net_contents(value: str | None) -> NetContentsReading:
    """Read a net contents quantity and its unit."""
    if value is None:
        return NetContentsReading(value=None, unit=None)
    match = _NET_CONTENTS.search(value)
    if match:
        return NetContentsReading(value=float(match.group(1)), unit=normalize_unit(match.group(2)))
    bare = _ABV_BARE.search(value)
    if bare:
        return NetContentsReading(value=float(bare.group(1)), unit=None)
    return NetContentsReading(value=None, unit=None)


def compare_net_contents(label_value: str | None, application_value: str | None) -> Comparison:
    """Compare net contents values (FR-7, A-13)."""
    missing = _missing(label_value, application_value)
    if missing is not None:
        return missing

    label = parse_net_contents(label_value)
    application = parse_net_contents(application_value)

    if label.value is None or application.value is None:
        fallback = compare_text(label_value, application_value)
        return Comparison(
            outcome=fallback.outcome,
            score=fallback.score,
            reason=(
                "Net contents could not be read as a number on "
                f"{'the label' if label.value is None else 'the application'} "
                "side, so the values were compared as text instead (FR-7). "
                f"{fallback.reason}"
            ),
        )

    if label.unit is None or application.unit is None:
        side = "the label" if label.unit is None else "the application"
        return Comparison(
            outcome=Outcome.NEEDS_REVIEW,
            score=None,
            reason=(
                f"No unit was stated on {side} side: label {label_value!r}, "
                f"application {application_value!r}. A-13 compares numerically "
                "only when units match, and assuming a unit is the kind of "
                "silent step that manufactures a false match."
            ),
        )

    if label.unit != application.unit:
        return Comparison(
            outcome=Outcome.NEEDS_REVIEW,
            score=None,
            reason=(
                f"Different units: {label.value:g} {label.unit} on the label "
                f"against {application.value:g} {application.unit} in the "
                "application. No conversion is performed (A-13)."
            ),
        )

    if abs(label.value - application.value) < 1e-9:
        return Comparison(
            outcome=Outcome.MATCH,
            score=100.0,
            reason=(
                f"{label.value:g} {label.unit} on both sides. Standards of fill "
                "are not validated (A-13)."
            ),
        )

    return Comparison(
        outcome=Outcome.MISMATCH,
        score=0.0,
        reason=(
            f"Label {label.value:g} {label.unit} against application "
            f"{application.value:g} {application.unit}."
        ),
    )


def _missing(label_value: str | None, application_value: str | None) -> Comparison | None:
    """Return a not-compared or not-found comparison, or None to carry on.

    FR-1 requires an explicit "not found" for a field that could not be located
    on the label; FR-2 requires "not compared" for a field the application did
    not supply, distinguished from a mismatch. Neither may report a match
    (FR-9).
    """
    label_present = bool(label_value and label_value.strip())
    application_present = bool(application_value and application_value.strip())

    if not label_present and not application_present:
        return Comparison(
            outcome=Outcome.NOT_COMPARED,
            score=None,
            reason=(
                "Not found on the label, and the application supplied no value, "
                "so there was nothing to compare."
            ),
        )
    if not application_present:
        return Comparison(
            outcome=Outcome.NOT_COMPARED,
            score=None,
            reason="The application supplied no value for this field (FR-2).",
        )
    if not label_present:
        return Comparison(
            outcome=Outcome.MISMATCH,
            score=None,
            reason=(
                "This field was not found on the label. It is reported as not "
                "found rather than as empty or omitted (FR-1)."
            ),
        )
    return None
