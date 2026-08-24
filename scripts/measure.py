#!/usr/bin/env python3
"""Run the verification engine over the sample set and report what it did.

Run from the repository root, after samples/generate_samples.py:

    python scripts/measure.py

Prints a Markdown table of per-field precision, recall, review rate, false match
rate, and latency, following the metric definitions in
docs/07_TEST_STRATEGY.md section 3. Nothing is written to docs/: a number
belongs in a document once it has been measured on hardware the document
describes, and a session container is not that.

**What ground truth means here, stated because it bounds what these numbers
show.** The ground truth outcome for each field is computed by running the same
comparison rules over the values in samples/expected.csv, which are the values
actually rendered onto the artwork. So a disagreement between ground truth and
the pipeline is an **extraction** error: OCR misread the value, or app/parse.py
put it in the wrong field. These numbers do not evaluate the comparison rules
themselves, which are tested directly in backend/tests/test_compare.py. Reading
them as an accuracy figure for the whole tool would overstate what was measured.

The sample set is twelve synthetic labels rendered by Pillow. It is not real
label artwork, and per-field accuracy against real artwork is unmeasured and
remains the largest open technical risk in the prototype (ADR 0003).
"""

from __future__ import annotations

import csv
import statistics
import sys
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
for path in (REPO_ROOT, REPO_ROOT / "backend"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from samples.generate_samples import (  # noqa: E402
    APPLICATIONS_CSV,
    EXPECTED_CSV,
    IMAGES_DIR,
)
from samples.generate_samples import main as generate  # noqa: E402

from app.compare import Outcome  # noqa: E402
from app.ocr import extract_text  # noqa: E402
from app.parse import lines_from_text, parse_fields  # noqa: E402
from app.verify import build_result  # noqa: E402
from app.warning import check_warning  # noqa: E402

COMPARED_FIELDS = ("brand_name", "class_type", "alcohol_content", "net_contents")
ALL_FIELDS = (*COMPARED_FIELDS, "government_warning")


@dataclass
class FieldTally:
    reported_match: int = 0
    reported_match_and_true: int = 0
    true_match: int = 0
    true_match_reported: int = 0
    reported_review: int = 0
    false_match: int = 0
    total: int = 0

    def rate(self, numerator: int, denominator: int) -> str:
        if denominator == 0:
            return "n/a"
        return f"{numerator / denominator * 100:.1f}% ({numerator}/{denominator})"


def load_rows() -> list[dict[str, str]]:
    with EXPECTED_CSV.open(encoding="utf-8") as handle:
        expected = {row["image_filename"]: row for row in csv.DictReader(handle)}
    with APPLICATIONS_CSV.open(encoding="utf-8") as handle:
        applications = {row["filename"]: row for row in csv.DictReader(handle)}
    return [
        {"expected": expected[name], "application": applications[name], "filename": name}
        for name in sorted(expected)
        if name in applications
    ]


def truth_for(expected: dict[str, str], application: dict[str, str]) -> dict[str, Outcome]:
    """The outcome the rules give when extraction is perfect.

    Built by feeding the rendered values straight into the same parser and the
    same comparison functions the API uses, so the only difference between this
    and the measured run is what OCR read off the pixels.
    """
    truth_lines = lines_from_text(
        "\n".join(
            value
            for value in (
                expected["brand_name"],
                expected["class_type"],
                expected["alcohol_content"],
                expected["net_contents"],
                expected["government_warning"],
            )
            if value
        )
    )
    parsed = parse_fields(truth_lines)
    # The values are taken from the CSV rather than from the parse, so a
    # heuristic error here cannot contaminate the ground truth.
    result = build_result(
        parsed=_replace_values(parsed, expected),
        application={field: application.get(field, "") for field in COMPARED_FIELDS},
        ocr_confidence=100.0,
        ocr_ms=0.0,
    )
    outcomes = {field.name: field.outcome for field in result.fields}
    warning = check_warning(expected["government_warning"])
    outcomes["government_warning"] = Outcome.MATCH if warning.passes else Outcome.MISMATCH
    return outcomes


def _replace_values(parsed, expected: dict[str, str]):
    from dataclasses import replace

    return replace(
        parsed,
        brand_name=expected["brand_name"] or None,
        class_type=expected["class_type"] or None,
        alcohol_content=expected["alcohol_content"] or None,
        net_contents=expected["net_contents"] or None,
    )


def measure() -> tuple[dict[str, FieldTally], list[float], list[float], int]:
    tallies = {field: FieldTally() for field in ALL_FIELDS}
    latencies: list[float] = []
    confidences: list[float] = []
    rows = load_rows()

    for row in rows:
        image_path = IMAGES_DIR / row["filename"]
        ocr = extract_text(image_path.read_bytes())
        parsed = parse_fields(ocr.lines)
        result = build_result(
            parsed=parsed,
            application={field: row["application"].get(field, "") for field in COMPARED_FIELDS},
            ocr_confidence=ocr.mean_confidence,
            ocr_ms=ocr.elapsed_ms,
        )
        latencies.append(ocr.elapsed_ms)
        confidences.append(ocr.mean_confidence)

        truth = truth_for(row["expected"], row["application"])
        for field in result.fields:
            tally = tallies[field.name]
            true_outcome = truth[field.name]
            tally.total += 1
            if field.outcome is Outcome.MATCH:
                tally.reported_match += 1
                if true_outcome is Outcome.MATCH:
                    tally.reported_match_and_true += 1
                if true_outcome is Outcome.MISMATCH:
                    tally.false_match += 1
            if field.outcome is Outcome.NEEDS_REVIEW:
                tally.reported_review += 1
            if true_outcome is Outcome.MATCH:
                tally.true_match += 1
                if field.outcome is Outcome.MATCH:
                    tally.true_match_reported += 1

    return tallies, latencies, confidences, len(rows)


def report() -> str:
    if not IMAGES_DIR.is_dir() or not any(IMAGES_DIR.glob("*.png")):
        generate()

    tallies, latencies, confidences, count = measure()
    lines = [
        f"Sample set: {count} synthetic labels rendered by `samples/generate_samples.py` "
        "(spirits, wine, malt beverage; defects: title-case warning, altered warning "
        "wording, no warning, wrong ABV, missing net contents, inconsistent proof, "
        "cross-unit net contents, one rotated image, one low-contrast image).",
        "",
        "| Field | Precision | Recall | Review rate | False match rate |",
        "| --- | --- | --- | --- | --- |",
    ]
    for name in ALL_FIELDS:
        tally = tallies[name]
        lines.append(
            f"| {name} "
            f"| {tally.rate(tally.reported_match_and_true, tally.reported_match)} "
            f"| {tally.rate(tally.true_match_reported, tally.true_match)} "
            f"| {tally.rate(tally.reported_review, tally.total)} "
            f"| {tally.rate(tally.false_match, tally.reported_match)} |"
        )

    lines += [
        "",
        "| Latency, decode plus preprocessing plus OCR | Value |",
        "| --- | --- |",
        f"| Mean | {statistics.mean(latencies):.0f} ms |",
        f"| Median | {statistics.median(latencies):.0f} ms |",
        f"| Maximum | {max(latencies):.0f} ms |",
        f"| Mean OCR word confidence | {statistics.mean(confidences):.1f} |",
        "",
        "Precision here is defined as in `docs/07_TEST_STRATEGY.md` section 3: of the "
        "fields the system reported as a match, the fraction ground truth agrees are "
        "matches. Ground truth is computed by running the same comparison rules over "
        "the values rendered onto the artwork, so these figures measure extraction "
        "error, not the comparison rules. No accuracy target is set; none is stated by "
        "any source (OQ-8).",
    ]
    return "\n".join(lines)


if __name__ == "__main__":
    print(report())
