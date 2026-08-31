#!/usr/bin/env python3
"""Run the verification engine over the sample set and report what it did.

Run from the repository root, after samples/generate_samples.py:

    python scripts/measure.py                          # accuracy, in process
    python scripts/measure.py --batch --url "$URL"     # a batch, over HTTP
    python scripts/measure.py --batch --url "$URL" --copies 25   # 300 labels

Prints a Markdown table of per-field precision, recall, review rate, false match
rate, and latency, following the metric definitions in
docs/07_TEST_STRATEGY.md section 3. Nothing is written to docs/: a number
belongs in a document once it has been measured on hardware the document
describes, and a session container is not that.

**Two modes, and they measure different things.** The default imports the
engine and runs it in this process, so what it reports is extraction accuracy
with no network in it. `--batch --url` submits a real batch to a deployed
service and reports what came back and when, which is what
docs/09_DEPLOYMENT.md section 9 asks for and what the in-process mode cannot
answer. Say which one produced a figure whenever one is recorded.

**The batch mode follows the ADR 0009 contract**: label images plus one COLA
document each, paired by filename stem, sent as repeated `images` and
`application_documents` parts. There is no CSV. `--copies` repeats the sample
set under fresh stems so that the full 300-label batch section 9 asks for can
actually be sent from a twelve-label sample set.

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

import argparse
import csv
import json
import statistics
import sys
import time
import urllib.error
import urllib.request
import uuid
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
for path in (REPO_ROOT, REPO_ROOT / "backend"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from samples.generate_samples import (  # noqa: E402
    APPLICATIONS_CSV,
    DOCUMENTS_DIR,
    EXPECTED_CSV,
    IMAGES_DIR,
)
from samples.generate_samples import main as generate  # noqa: E402

from app.compare import Outcome  # noqa: E402
from app.ocr import extract_text  # noqa: E402
from app.parse import lines_from_text, parse_fields  # noqa: E402
from app.search import label_units  # noqa: E402
from app.verify import Sheet, build_result  # noqa: E402
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
        # The ground truth is searched too, so that the two runs differ only in
        # what OCR read off the pixels and not in which comparison ran.
        sheets=[Sheet(index=1, units=label_units(truth_lines))],
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
            # The reading, so this measures the path the API takes (ADR 0015).
            # Without it every field would fall back to the extractor and the
            # accuracy reported here would be for code an agent never runs.
            sheets=[Sheet(index=1, units=label_units(ocr.lines))],
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


# --------------------------------------------------------------------------
# Batch mode: the ADR 0009 contract, against a deployed service.
# --------------------------------------------------------------------------

BOUNDARY = f"----ttb-measure-{uuid.uuid4().hex}"

# What each side of a pair is sent as. Images are PNG because that is what
# samples/generate_samples.py renders; documents are the PDFs it writes
# alongside them.
IMAGE_TYPE = "image/png"
DOCUMENT_TYPE = "application/pdf"


def batch_parts(copies: int) -> list[tuple[str, str, str, bytes]]:
    """Every part of one batch submission, as (field, filename, type, bytes).

    Each copy after the first gets a fresh stem on both sides of the pair, so
    the pairing still holds and no two labels collide. That is what lets a
    twelve-label sample set stand in for the 300-label batch at the configured
    cap; it measures throughput and memory, not accuracy, and the labels being
    repeated does not change either.
    """
    if not IMAGES_DIR.is_dir() or not any(IMAGES_DIR.glob("*.png")):
        generate()

    parts: list[tuple[str, str, str, bytes]] = []
    for copy in range(copies):
        suffix = "" if copy == 0 else f"-copy{copy + 1:03d}"
        for image_path in sorted(IMAGES_DIR.glob("*.png")):
            document_path = DOCUMENTS_DIR / f"{image_path.stem}.pdf"
            if not document_path.is_file():
                raise SystemExit(
                    f"No COLA document for {image_path.name}. Run "
                    "samples/generate_samples.py, which writes one per label."
                )
            stem = f"{image_path.stem}{suffix}"
            parts.append(("images", f"{stem}.png", IMAGE_TYPE, image_path.read_bytes()))
            parts.append(
                (
                    "application_documents",
                    f"{stem}.pdf",
                    DOCUMENT_TYPE,
                    document_path.read_bytes(),
                )
            )
    return parts


def multipart_body(parts: list[tuple[str, str, str, bytes]]) -> bytes:
    """Encode the parts by hand, so this script needs no HTTP dependency.

    The runtime lock file carries no HTTP client and this script is run by an
    author against a deployed URL; adding a dependency for one measurement
    would be a worse trade than forty lines of encoding.
    """
    chunks: list[bytes] = []
    for field, filename, content_type, content in parts:
        chunks.append(f"--{BOUNDARY}\r\n".encode())
        chunks.append(
            f'Content-Disposition: form-data; name="{field}"; filename="{filename}"\r\n'.encode()
        )
        chunks.append(f"Content-Type: {content_type}\r\n\r\n".encode())
        chunks.append(content)
        chunks.append(b"\r\n")
    chunks.append(f"--{BOUNDARY}--\r\n".encode())
    return b"".join(chunks)


def run_batch(url: str, copies: int) -> str:
    """Submit one batch and report what came back, and when.

    The arrival time of every line is recorded, because whether the response
    streamed is the question docs/09_DEPLOYMENT.md section 8.4 cannot answer
    from a total. If every line lands at the same moment, something between the
    application and here buffered the whole response and NFR-2 is not met on
    the deployed path however green the tests are.
    """
    parts = batch_parts(copies)
    labels = sum(1 for field, *_ in parts if field == "images")
    body = multipart_body(parts)

    request = urllib.request.Request(  # noqa: S310
        url.rstrip("/") + "/api/verify-batch",
        data=body,
        method="POST",
        headers={
            "Content-Type": f"multipart/form-data; boundary={BOUNDARY}",
            "Content-Length": str(len(body)),
        },
    )

    arrivals: list[float] = []
    statuses: dict[str, int] = {}
    codes: dict[str, int] = {}
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(request) as response:  # noqa: S310
            for raw in response:
                line = raw.decode("utf-8").strip()
                if not line:
                    continue
                arrivals.append(time.perf_counter() - started)
                record = json.loads(line)
                status = record.get("status", "unknown")
                statuses[status] = statuses.get(status, 0) + 1
                if status == "error":
                    code = (record.get("error") or {}).get("code", "unknown")
                    codes[code] = codes.get(code, 0) + 1
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", "replace")[:500]
        raise SystemExit(f"The service refused the batch: HTTP {error.code}. {detail}") from error
    except urllib.error.URLError as error:
        raise SystemExit(f"Could not reach {url}: {error.reason}") from error

    elapsed = time.perf_counter() - started
    if not arrivals:
        raise SystemExit("The response carried no lines at all.")

    lines = [
        f"Batch of {labels} labels, each with its own COLA document, submitted to "
        f"{url} as one multipart request (ADR 0009). Envelope: "
        f"{len(body) / 1_048_576:.1f} MiB.",
        "",
        "| Measurement | Value |",
        "| --- | --- |",
        f"| Lines received | {len(arrivals)} |",
        f"| Total wall clock | {elapsed:.1f} s |",
        f"| Per label | {elapsed / labels:.2f} s |",
        f"| First line arrived after | {arrivals[0]:.2f} s |",
        f"| Last line arrived after | {arrivals[-1]:.2f} s |",
        f"| Spread between first and last line | {arrivals[-1] - arrivals[0]:.2f} s |",
        "",
        "| Line status | Count |",
        "| --- | --- |",
    ]
    lines += [f"| {status} | {count} |" for status, count in sorted(statuses.items())]
    if codes:
        lines += ["", "| Error code | Count |", "| --- | --- |"]
        lines += [f"| {code} | {count} |" for code, count in sorted(codes.items())]
    lines += [
        "",
        "**Read the spread.** It is the streaming check from "
        "docs/09_DEPLOYMENT.md section 8.4, in one number: a spread near zero "
        "means the whole response arrived at once, which is a buffering "
        "intermediary rather than a fast service, and NFR-2 is not met on the "
        "deployed path. The peak task memory this run cost is not here and "
        "cannot be: read it from the CloudWatch MemoryUtilization metric for "
        "the task, as section 9 requires.",
    ]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--batch",
        action="store_true",
        help="Submit a batch to a deployed service instead of measuring accuracy in process.",
    )
    parser.add_argument("--url", help="Base URL of the deployed service, for --batch.")
    parser.add_argument(
        "--copies",
        type=int,
        default=1,
        help=(
            "Repeat the sample set this many times under fresh filename stems. "
            "25 copies of the twelve-label set is the 300-label batch at the "
            "configured cap."
        ),
    )
    arguments = parser.parse_args()

    if not arguments.batch:
        print(report())
        return 0
    if not arguments.url:
        parser.error("--batch needs --url, the base URL of the deployed service")
    if arguments.copies < 1:
        parser.error("--copies has to be at least 1")
    print(run_batch(arguments.url, arguments.copies))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
