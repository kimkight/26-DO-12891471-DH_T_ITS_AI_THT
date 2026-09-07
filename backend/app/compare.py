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

    ``PRESENT`` is the outcome of a **presence check**, which is a one-sided
    finding and a passing one (FR-15, [ADR 0018](../../docs/adr/0018-presence-checks.md)).
    27 CFR requires alcohol content and net contents to appear on the label. Where
    the application declares neither, that requirement is still answerable, and
    the answer is about the label alone: either it carries the element or it does
    not. A label that carries it has been shown to satisfy a real regulatory
    requirement, and reporting that as "not compared" throws away a true positive
    finding because the form happened to be silent.

    ``ARTWORK_DERIVED`` is the fifth, and it is not a verdict about agreement at
    all (FR-14, ADR 0013). It marks a row whose application value was read off
    the same label artwork that supplied the label side, so the two strings
    being compared are one reading of one picture. Such a comparison can only
    ever agree, and a match chip on it would be structurally incapable of saying
    anything else. It is decided in ``app.verify`` rather than here, because
    this module compares two strings and has no idea where either came from.

    **The two are not alternatives, and ADR 0018 narrows the second.** A
    presence check is not a comparison at all, so it has nothing to be circular
    about; the artwork-derived state stays for what it was built for, a value
    read off the artwork and then compared against that same artwork, which
    after ADR 0018 is a case the presence fields never reach.

    ``NOT_CERTIFIED`` is the seventh, and it belongs to the government warning
    alone (FR-5, [ADR 0022](../../docs/adr/0022-warning-present-not-certified.md)).
    The statement is on the label, it does not match 27 CFR 16.21, and every
    line of it that differs was read below the legibility floor, so the tool
    cannot attribute the difference to the label rather than to the reading.
    It is a failing outcome, like a near miss and unlike it: a near miss is a
    difference too small to attribute, this is a read too damaged to. Neither
    passes anything, and a difference read confidently is still a mismatch.
    """

    MATCH = "match"
    NEEDS_REVIEW = "needs_review"
    MISMATCH = "mismatch"
    NOT_COMPARED = "not_compared"
    PRESENT = "present"
    ARTWORK_DERIVED = "artwork_derived"
    NOT_CERTIFIED = "not_certified"


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

# A decimal point inside the proof figure that OCR read as something else.
#
# **Measured on a real filing, 2026-09-06.** The alcohol statement on one
# panel of a filed bourbon label prints the proof to one decimal place, as
# 27 CFR 5.65(b)(1)(i) permits beside the mandatory percentage. Read through
# the pipeline, the point came back as a dash from one Tesseract segmentation
# mode and as a degree sign from another, so the proof pattern below read the
# single digit after it as the whole proof, and the A-12 cross-check then
# reported a label that agrees with itself exactly as contradicting itself.
#
# The repair is narrow on purpose: one of these four characters, between a
# run of digits and exactly one digit, immediately before the word PROOF. A
# range of percentages uses the same dash and is untouched, because it is not
# followed by PROOF and carries more than one digit after the separator.
_PROOF_DECIMAL_MISREAD = re.compile(
    r"(\d+)[\-\u2013\u00b0\u00b7,](\d)(?=\s*proof\b)", re.IGNORECASE
)

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

    value = _PROOF_DECIMAL_MISREAD.sub(r"\1.\2", value)
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


# --------------------------------------------------------------------------
# Two checks that read the label on its own (FR-14, ADR 0013).
#
# Everything else in this module compares the label against the application.
# These two do not, and that is the point of them: they are the part of the
# check that stays meaningful when both sides of a row came out of the same
# picture. See ``app.verify`` for where that happens and what it is called.
# --------------------------------------------------------------------------

# 27 CFR requires alcohol content and net contents on the label whatever the
# application form says, so a label that does not carry one is a finding in its
# own right rather than a field there was nothing to compare. All three
# sections fetched from eCFR on 2026-08-30.
#
# The carve-outs are real and they are quoted rather than smoothed over,
# because an agent reading a finding needs to know when it is not a defect:
#
# - 27 CFR 5.63(b)(2) requires distilled spirits containers to bear net
#   contents "(which may be blown, embossed, or molded into the container as
#   part of the process of manufacturing the container)".
# - 27 CFR 7.63(a)(5) says the same for malt beverages, and 7.63(a)(3) requires
#   alcohol content on a malt beverage only "for malt beverages that contain any
#   alcohol derived from added nonbeverage flavors or other added nonbeverage
#   ingredients (other than hops extract) containing alcohol".
# - 27 CFR 4.32(b)(2) and (b)(3) require net contents and alcohol content on a
#   label affixed to a wine container, with no container carve-out.
#
# So absence is reported, and the reason says what would make it innocent. The
# tool recommends and the agent judges (FR-3); it does not conclude a violation
# from a picture.
_PRESENCE_RULES = {
    "alcohol_content": (
        "Alcohol content was not found on the label. 27 CFR 5.63(a)(3) requires "
        "it on a distilled spirits label and 27 CFR 4.32(b)(3) on a wine label, "
        "whatever the application form says, so this is reported as a finding "
        "rather than as nothing to compare. 27 CFR 7.63(a)(3) requires it on a "
        "malt beverage only where alcohol is derived from added nonbeverage "
        "ingredients, and 27 CFR 4.36(a) lets a wine of 14 percent or less "
        "carry \u201ctable\u201d or \u201clight\u201d wine in place of a figure, so check "
        "the product type before treating it as a defect."
    ),
    "net_contents": (
        "Net contents was not found on the label. 27 CFR 5.63(b)(2) and "
        "27 CFR 7.63(a)(5) require it on distilled spirits and malt beverage "
        "containers and 27 CFR 4.32(b)(2) on a wine label, whatever the "
        "application form says, so this is reported as a finding rather than as "
        "nothing to compare. Every panel that was read was searched for it. "
        "Both spirits and malt beverage sections allow it to be \u201cblown, "
        "embossed, or molded into the container\u201d, and 27 CFR 4.37(c) allows "
        "the same for wine, which a picture of a flat label cannot show, so "
        "check the container before treating it as a defect."
    ),
}


# What a presence check says when it passes (FR-15, ADR 0018).
#
# **This is a positive finding, not a consolation prize.** The row establishes
# something real: the label carries an element 27 CFR requires it to carry. That
# is exactly what an agent checking a filing has to establish, and it is
# established whether or not the application form repeats the value, because the
# requirement is on the label rather than on the form.
#
# The wording says which of the two it is, so the row cannot be misread as a
# comparison that happened to agree. The citations are the same ones
# ``_PRESENCE_RULES`` names for absence, because presence and absence are the
# two answers to one question and an agent should see the same rule cited either
# way.
_PRESENCE_PASSES = {
    "alcohol_content": (
        "Alcohol content is on the label: {value}. 27 CFR 5.63(a)(3) requires it "
        "on a distilled spirits label and 27 CFR 4.32(b)(3) on a wine label, and "
        "the label carries it. The application declared no value, so this is a "
        "check that the required element is present rather than a comparison of "
        "two values."
    ),
    "net_contents": (
        "Net contents is on the label: {value}. 27 CFR 5.63(b)(2) and "
        "27 CFR 7.63(a)(5) require it on distilled spirits and malt beverage "
        "containers and 27 CFR 4.32(b)(2) on a wine label, and the label carries "
        "it. The application declared no value, so this is a check that the "
        "required element is present rather than a comparison of two values."
    ),
}


def present_on_label(name: str, label_value: str) -> Comparison | None:
    """The passing presence finding, where the application declared nothing.

    **The row this replaces printed "not compared", and that was the design
    mistake** (FR-15, ADR 0018). A label carrying ``42% ALC BY VOL`` has been
    shown to satisfy 27 CFR 5.63(a)(3). Reporting nothing because the form was
    silent discards a true finding about the label, which is the thing the agent
    is checking.

    It carries no score. A score is a similarity between two strings and there
    is only one string here; printing 100 beside a one-sided finding would be
    inventing an agreement that was never tested.

    Returns None for a field with no presence rule, which is every field whose
    presence on the label is not something this tool can assert from 27 CFR.
    """
    template = _PRESENCE_PASSES.get(name)
    if template is None:
        return None
    return Comparison(
        outcome=Outcome.PRESENT, score=None, reason=template.format(value=label_value.strip())
    )


def missing_from_label(name: str, label_value: str | None) -> Comparison | None:
    """The regulatory presence finding, or None where the label carries it.

    **This is the half of the check that is never circular** (FR-14, ADR 0013).
    Whether the label carries a mandatory element is a question about the label
    alone. It is answerable from artwork lifted out of an application document
    exactly as well as from a photograph of a bottle, and it stays a real result
    when the comparison beside it has become a comparison of a value with
    itself.

    Returns a mismatch rather than a review, because it is the same answer FR-1
    already gives a field that could not be located on the label, and one defect
    reported two ways depending on what the form happened to say would be
    incoherent. What the reason carries is the two carve-outs above, so the
    agent can tell a finding from a violation.
    """
    if label_value and label_value.strip():
        return None
    reason = _PRESENCE_RULES.get(name)
    if reason is None:
        return None
    return Comparison(outcome=Outcome.MISMATCH, score=None, reason=reason)


def label_contradicts_itself(label_value: str | None) -> Comparison | None:
    """The A-12 proof cross-check, applied within the label (FR-7, FR-14).

    A label stating both a percentage and a proof states the same number twice,
    and 27 CFR 5.65 fixes the relation between them. Whether they agree is a
    property of that label on its own: it needs no application value, it is not
    weakened by the application being silent, and it cannot be manufactured by
    reading one picture twice. It is therefore the one genuinely non-circular
    comparison available on a row whose two sides came out of the same artwork
    (ADR 0013).

    **It is run before the application side is considered at all**, which is the
    only change to the rule. FR-7 and A-12 already required this cross-check and
    already fixed its outcome as needs human review "because it indicates an
    internal inconsistency on the label itself"; what they did not say was what
    to do when there is no application value beside it, and the answer used to be
    that the row reported "not compared" and the contradiction went unmentioned.

    Returns None where the label states no proof, or states one that agrees.
    """
    if label_value is None:
        return None
    reading = parse_abv(label_value)
    if reading.proof is None or reading.percent is None:
        return None
    expected_proof = 2 * reading.percent
    if abs(reading.proof - expected_proof) <= 1e-9:
        return None
    return Comparison(
        outcome=Outcome.NEEDS_REVIEW,
        score=None,
        reason=(
            f"The label states {reading.percent:g} percent alcohol and "
            f"{reading.proof:g} proof. 27 CFR 5.65 defines proof as twice the "
            f"alcohol by volume, so {reading.percent:g} percent should read "
            f"{expected_proof:g} proof. The label contradicts itself (A-12). "
            "This is a reading of the label on its own, so it holds whatever "
            "the application says and whether or not it says anything."
        ),
    )


def compare_abv(label_value: str | None, application_value: str | None) -> Comparison:
    """Compare declared alcohol content values (FR-7, A-12).

    Order of the rules matters and follows A-12: an internal inconsistency on
    the label itself (proof that is not twice the ABV) routes to review even
    when the two declared percentages agree, because the label contradicts
    itself and that is a person's call.

    **The label-only checks run first** (FR-14, FR-15, ADR 0013, ADR 0018).
    Whether the label carries alcohol content at all, whether the percentage and
    the proof it prints agree with each other, and, where the application
    declared nothing, whether the required element is present, are all questions
    about the label. Running them before the application side is considered is
    what keeps them answerable when the application supplied nothing, and what
    keeps the contradiction from being swallowed by a row that reports "not
    compared".

    **Order within them matters.** A label that contradicts itself is reported as
    the review A-12 makes it, even where the application is silent and the
    presence check below would otherwise pass the row. A contradiction is a
    defect on the label, and a presence check that reported "the element is
    there" over the top of it would be answering a narrower question than the one
    the tool had already answered.
    """
    absent = missing_from_label("alcohol_content", label_value)
    if absent is not None:
        return absent

    contradiction = label_contradicts_itself(label_value)
    if contradiction is not None:
        return contradiction

    # The label carries it and the application declared nothing, so there is a
    # real finding to report and it is not a comparison (FR-15, ADR 0018).
    # ``label_value`` is non-empty by the guard above.
    if not (application_value and application_value.strip()):
        present = present_on_label("alcohol_content", label_value or "")
        if present is not None:
            return present

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

    # The proof cross-check is not repeated here. It ran above, on the label
    # alone, and anything reaching this line has already passed it.

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
    # A bare ounce on a beverage label is a fluid ounce: 27 CFR 7.70(a) states
    # malt beverage net contents in fluid ounces and there is no other ounce a
    # volume could be stated in. Folded onto the same unit so that "12 OZ" and
    # "12 FL OZ" compare as the quantity they both are (A-13).
    "oz": "fl oz",
    "cl": "cL",
    "centiliter": "cL",
    "centiliters": "cL",
    "centilitre": "cL",
    "centilitres": "cL",
    "pint": "pint",
    "pints": "pint",
    "pt": "pint",
    "quart": "quart",
    "quarts": "quart",
    "qt": "quart",
    "gallon": "gallon",
    "gallons": "gallon",
    "gal": "gallon",
}

# The unit spellings a net contents statement is located and read by. Shared
# with ``app.parse``, which locates the line, so that the line found and the
# value read off it cannot disagree about what a unit is.
#
# **Measured, not assumed (2026-09-06).** The label artwork of nine approved
# applications in TTB's Public COLA Registry, across six beverage classes,
# prints net contents in six shapes: metric with a space before the unit and
# without one; metric followed by the estimated-quantity sign; metric behind a
# "CONT." prefix with the sign after it; metric fused to a lot code on the same
# line; and US customary, as one pint. A pattern that assumed a number
# followed by ML read about half of them, and nothing had noticed because the
# one filing the matcher was calibrated to prints 750 ML. This is the alcohol
# content defect of the same date found before it cost anything.
#
# The spellings come from the regulation rather than from the nine labels.
# 27 CFR 5.70(a): "liter" may be spelled "litre" or abbreviated "L", and
# "milliliters" may be abbreviated "ml.", "mL." or "ML."; equivalents "such as
# centiliters" may appear beside the metric statement. 27 CFR 7.70(a) states
# malt beverage net contents in fluid ounces, fractions of a pint, pints,
# quarts and gallons. 27 CFR 4.37(a) and (b) state wine net contents in liters
# and milliliters, with an optional equivalent in fluid ounces. A number has to
# sit against one of these; a number on its own is never a net contents.
NET_CONTENTS_UNIT = (
    r"(?:fl\.?\s*oz\.?|fluid\s+ounces?|oz\.?"
    r"|milli\s?lit(?:er|re)s?|centi\s?lit(?:er|re)s?|lit(?:er|re)s?|ml|mls|cl|l"
    r"|pints?|pt\.?|quarts?|qt\.?|gallons?|gal\.?)"
)
_NET_CONTENTS = re.compile(rf"({_NUMBER})\s*({NET_CONTENTS_UNIT})\b", re.IGNORECASE)


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
    """Compare net contents values (FR-7, A-13).

    The presence rules run first, for the reason they do in ``compare_abv``:
    27 CFR requires net contents on the label whatever the form says, so both
    answers to that question are real findings. A label that does not carry it
    is a mismatch (FR-14, ADR 0013); a label that carries it against a silent
    application is a passing presence check (FR-15, ADR 0018). Only where the
    application declares a value is there a comparison to make.
    """
    absent = missing_from_label("net_contents", label_value)
    if absent is not None:
        return absent

    # As in ``compare_abv``: the label carries it, the application declared
    # nothing, and that is a passing presence check rather than nothing to
    # report (FR-15, ADR 0018).
    if not (application_value and application_value.strip()):
        present = present_on_label("net_contents", label_value or "")
        if present is not None:
            return present

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
