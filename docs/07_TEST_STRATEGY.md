# Test Strategy

Testing is organized in five tiers. Each tier states what it covers, what it
deliberately does not, and how it is run.

**Current state:** the unit, integration, accuracy and performance tiers exist
for the single-label path. Accessibility has nothing to test yet, because there
is no user interface. Nothing below is described as passing unless it has
actually been run.

| Tier | Exists today | Blocked on |
| --- | --- | --- |
| Unit | Yes: `test_compare.py`, `test_warning.py`, `test_parse.py`, `test_ocr.py`, `test_samples.py`, `test_health.py` | Nothing for the single-label path |
| Integration | Yes: `test_api_validation.py`, `test_verify_integration.py` | Batch, which needs FR-8 |
| Accuracy | Yes: `scripts/measure.py` over `samples/` | Real label artwork; the set is synthetic |
| Performance | Yes: single-label latency, measured by the same script | Batch throughput, which needs FR-8 |
| Accessibility | No | The verification UI |
| Manual UAT | Checklist written, section 6 | A user interface for rows 12, 13 and 14 |

The integration tier needs Tesseract, which is a system package rather than a
Python one. CI installs it; a checkout without it skips those tests rather than
failing them, so a green local run on a machine with no Tesseract is not
evidence that the OCR path works.

## 1. Unit tests

**Scope:** pure functions and single components, with no I/O.

**Runner:** `pytest` for the backend. Run in CI on every pull request.

**What the unit tier covers.** Every row below is implemented; the file that
implements it is named alongside.

| Area | Cases |
| --- | --- |
| Text normalization, `test_compare.py` | Case folding; whitespace collapse; straight against typographic apostrophes; punctuation stripping. The `STONE'S THROW` against `Stone's Throw` pair is a unit case before it is anything else (FR-4). |
| Outcome classification, `test_compare.py` | Scores at, just above, and just below each threshold. Boundary values are the point, not the middle of the band (FR-3). |
| Numeric parsing, `test_compare.py` | `45% Alc./Vol. (90 Proof)` yields 45; `750 mL` yields 750 with unit `mL`; `45` and `45.0` compare equal; an unparseable value falls back to text comparison (FR-7). |
| Government warning body, `test_warning.py` | Exact text from 27 CFR 16.21 after whitespace normalization matches; a single changed, added, or removed word does not (FR-5). |
| Warning capitalization, `test_warning.py` | `GOVERNMENT WARNING:` passes; `Government Warning:` fails; `government warning:` fails (FR-6). |
| Validation, `test_api_validation.py` | Size and MIME type limits reject before any decoding happens (NFR-7). The batch count limit is unbuilt with FR-8. |
| Image preprocessing, `test_ocr.py` | The long edge lands on the configured size and the aspect ratio holds; a rotated image comes back closer to upright, and an upright one is left alone. |
| Sample set integrity, `test_samples.py` | The sample warning text is the regulation's; each labelled defect is actually defective. |

**Deliberately not covered by this tier:** anything involving Tesseract, which
is slow and environment dependent, and therefore belongs in the integration and
accuracy tiers.

## 2. Integration tests

**Scope:** the HTTP contract end to end, in process, with real OCR against small
fixture images.

**Runner:** `pytest` with FastAPI's `TestClient`.

Label artwork is rendered by `samples/labelmaker.py` at test time rather than
committed, so no binary fixture enters the repository.

**Cases:**

- `POST /api/verify` with a clean label and matching application data returns
  200 with an outcome for each of the five fields. **Implemented.**
- The same endpoint with a corrupt file returns a 4xx and no field reporting a
  match (FR-9). **Implemented.**
- An oversized file is rejected before the body is read (NFR-7). **Implemented.**
- A disallowed MIME type is rejected before decoding (NFR-7). **Implemented.**
- An image with no text reads differently from fields that did not match (FR-9).
  **Implemented.**
- `POST /api/verify/batch` returns one identified result set per label (FR-8).
  **Not built.**
- A batch containing one unreadable image returns results for every other label
  in the batch (US-10). This is the single most important integration case,
  because it is the property that makes batch handling worth having.
  **Not built.**
- A batch exceeding the file-count limit is rejected before any file is
  processed (FR-8). **Not built.**
- With `TTB_ENABLE_BEDROCK_FALLBACK` unset, no outbound connection is attempted
  (NFR-3). **Implemented**, as UAT row 16: the test replaces the socket
  constructor so that any attempt to open an IP socket raises, proves the guard
  is live by opening one itself, and then asserts the verification still returns
  200 with `external_call_made` false. AF_UNIX is left alone, because asyncio
  builds its own self-pipe from a Unix socketpair and refusing that would break
  the event loop rather than test the application.
- No image content and no extracted or application value reaches the logs
  (NFR-6). **Implemented**, as UAT row 17: distinctive values are searched for
  across every captured record, and the one record the verification path writes
  is held to an allow-list of `bytes_received`, `ocr_ms` and
  `beverage_type_supplied`, so a field added to it later has to be added there
  deliberately.

## 3. Accuracy tests

**Scope:** how often extraction and comparison are right, measured per field
against ground truth.

**Method:** run the full pipeline over the labeled sample set in `samples/`,
comparing output against `samples/expected.csv`.

**Metrics, reported per field** (brand name, class/type, alcohol content, net
contents, government warning):

| Metric | Definition in this context |
| --- | --- |
| Precision | Of the fields where the system reported a match, the fraction that ground truth agrees are matches. |
| Recall | Of the fields ground truth says are matches, the fraction the system reported as matches. |
| Review rate | The fraction routed to needs human review. Useful but not free: too high and the tool saves no time; too low and it is overconfident. |
| False match rate | Reported a match where ground truth says mismatch. **The most damaging error class**, because it causes an agent to skip a check. Tracked and reported separately. |

**Reporting rules:**

- Sample size and composition are stated alongside every number.
- Per-field results are published, not a single aggregate. An aggregate would
  hide a weak field behind strong ones.
- Weak results are published as readily as strong ones (US-21).

**No accuracy target is set here.** No source in the assignment states one, and a
threshold invented in this document would be unfalsifiable. Recorded as OQ-8 in
[OPEN_QUESTIONS.md](OPEN_QUESTIONS.md).

**How it is run:** `python samples/generate_samples.py` renders the set, then
`python scripts/measure.py` prints the table. The set is twelve synthetic labels
across spirits, wine and malt beverage, carrying the defects `samples/README.md`
lists.

**What the numbers do and do not measure.** Ground truth outcomes are computed
by running the same comparison rules over the values rendered onto the artwork,
so a disagreement is an extraction error: OCR misread a value, or `parse.py` put
it in the wrong field. The figures do not evaluate the comparison rules, which
are tested directly in `backend/tests/test_compare.py`. And the artwork is
rendered text, not photographed bottles: accuracy against real label artwork is
unmeasured and remains the largest open technical risk in the prototype
(ADR 0003).

## 4. Performance tests

**Scope:** end-to-end latency against the 5-second target (NFR-1).

This tier exists because latency, not accuracy, killed the last attempt: "The
system would take 30, 40 seconds sometimes to process a single label... If we
can't get results back in about 5 seconds, nobody's going to use it."
[Source: Sarah Chen interview]

**Method:**

1. Measure single-label end-to-end latency across the sample set, from request
   received to response returned.
2. Report the median, the 95th percentile, and the maximum. A median under
   target with a long tail still produces the experience Sarah describes.
3. Break the budget down by stage: validation, image preprocessing, OCR, and
   matching. Without the breakdown, a regression cannot be attributed.
4. State the hardware, the image dimensions, and the sample composition with
   every number. A latency figure without them is not a measurement.

**Latency budget**, as a working allocation to be validated by measurement, not
as a claim about current behaviour. These are planning figures; the split will
be revised once real numbers exist. `(Assumption)`

| Stage | Working allocation |
| --- | --- |
| Request handling and validation | under 100 ms |
| Image decode and preprocessing (OpenCV) | under 500 ms |
| OCR (Tesseract) | under 3,000 ms |
| Matching and response assembly | under 200 ms |
| Headroom | remainder of the 5,000 ms budget |

**Batch performance** is measured separately: total wall clock for 300 labels,
and per-label throughput. The assignment states no batch latency target; see
OQ-6.

## 5. Accessibility tests

**Target:** WCAG 2.1 Level AA (NFR-5).

**Method:**

| Check | How |
| --- | --- |
| Automated rule scan | An axe-based scan in CI over the main views. Catches contrast, missing labels, and landmark problems. |
| Keyboard only | Complete a full verification without a mouse. Every control reachable, focus visible, order logical. |
| Screen reader | Confirm results appearing after submission are announced, and that each field row reads as field, label value, application value, outcome. |
| Colour independence | Confirm each of the three outcomes is distinguishable in greyscale. Automated tools do not catch this; it needs a person to look. |
| Zoom and reflow | Usable at 200 percent zoom without horizontal scrolling. |

An automated scan is a floor, not a pass. The keyboard, screen reader, and
greyscale checks are manual and are part of the UAT checklist below.

**Section 508 applicability is not confirmed.** As a federal accessibility
obligation it would plausibly apply to a system used by agency staff, but no
source in this assignment states it, and the conclusion is not asserted here.
Recorded as OQ-7 in [OPEN_QUESTIONS.md](OPEN_QUESTIONS.md). WCAG 2.1 AA is
targeted regardless, per NFR-5.

## 6. Manual UAT checklist

Derived directly from the interview examples. Each row is a scenario a
stakeholder actually described, and each has a defined pass condition. Run
against a deployed build before the prototype is presented.

| # | Scenario | Pass condition | Source |
| --- | --- | --- | --- |
| 1 | A clean label matching its application data on all five fields | Every field reports match | Sarah Chen interview |
| 2 | Label `STONE'S THROW`, application `Stone's Throw` | Brand name reports match or needs human review. **A hard mismatch is a failure of this test.** | Dave Morrison interview |
| 3 | Warning rendered `Government Warning:` in title case | Capitalization check fails; the warning field does not report a match; the result names capitalization as the reason | Jenny Park interview |
| 4 | Warning with one word altered | Warning body reports mismatch, not needs human review | Jenny Park interview |
| 5 | Label with no warning statement at all | Warning reports mismatch and states the statement was not found | 27 CFR 16.21; FR-5 |
| 6 | Unreadable or corrupt image | A clear message that the image could not be read. **No field reports a match.** Distinct from "fields did not match". | Jenny Park interview |
| 7 | Alcohol content `45% Alc./Vol. (90 Proof)` against application `45` | Match | Technical Requirements, Sample Label |
| 8 | Net contents `750 mL` against `750ml` | Match | FR-7 |
| 9 | A batch of several labels submitted together | One identified result set per label | Sarah Chen interview |
| 10 | A batch with one unreadable image among good ones | That label errors; all others return results | Sarah Chen interview |
| 11 | Time a single verification with a stopwatch | About 5 seconds or less | Sarah Chen interview |
| 12 | Complete a verification using only the keyboard | Possible, with visible focus throughout | NFR-5 |
| 13 | View results in greyscale | All three outcomes distinguishable without colour | NFR-5 |
| 14 | First-use walkthrough with someone who has not seen the tool | They complete a verification without being told where to click | Sarah Chen interview |
| 15 | Inspect the warning result wording | It does not state or imply that bold type was checked | OOS-4; FR-6 |
| 16 | Run a verification with egress blocked | Completes successfully | Marcus Williams interview; NFR-3 |
| 17 | Inspect logs after a verification | No image content and no extracted field values | NFR-6 |

Rows 16 and 17 are also automated, in `backend/tests/test_verify_integration.py`.
They stay on the manual checklist because the automated versions test the
application process, and the row is about the deployed system: the automated
egress test blocks sockets inside one Python process, and the automated log test
reads records the application emitted rather than what CloudWatch received.
| 18 | Alcohol content `45` against application `45.0%` | Match | FR-7; A-12 |
| 19 | Alcohol content `45` against application `45.1` | Mismatch, with both values and the difference shown. **A match or a needs-human-review outcome is a failure of this test.** | FR-7; A-12 |
| 20 | Label stating `45% Alc./Vol. (90 Proof)` against application `45` | Proof cross-check passes, because 90 equals 2 x 45; the alcohol content outcome is match | FR-7; A-12; 27 CFR 5.65 |
| 21 | Label stating `45% Alc./Vol. (92 Proof)` against application `45` | Needs human review, with both numbers shown, because 92 does not equal 2 x 45 | FR-7; A-12; 27 CFR 5.65 |
| 22 | Net contents `750 mL` against application `25.4 fl oz` | Needs human review. **No conversion is performed and no match is reported.** | FR-7; A-13 |

Row 14 is Sarah's actual acceptance test, restated as a procedure: something
her mother, "73 and just learned to video call her grandkids," could figure out.
[Source: Sarah Chen interview] Row 15 exists because overstating what was
checked is the failure mode most likely to cause real harm.

## 7. What runs in CI

Defined in `.github/workflows/ci.yml`. All jobs gate the aggregate `ci` check.

| Job | Contents |
| --- | --- |
| `backend` | Installs Tesseract and a TrueType font, then `ruff check`, `ruff format --check` over `backend/`, `samples/` and `scripts/`, and `pytest` with coverage |
| `frontend` | `eslint`, `prettier --check`, `tsc -b`, `vite build` |
| `audit` | `pip-audit --strict`, `npm audit --audit-level=high` |
| `container` | Docker build, health endpoint probe against the running container, non-root user assertion, SBOM generation and upload |
| `ci` | Aggregate gate; fails if any job above failed or was cancelled |

The accuracy and performance tiers run as scripts rather than as CI gates.
`scripts/measure.py` is run by hand and its output is quoted in the pull request
that changes the engine, because a runner's timings vary enough that gating on
them would produce failures that say nothing about the change. The single-label
latency assertion in `test_verify_integration.py` does gate, against the
5-second target rather than against a tighter number.

The accessibility tier is **not** in CI, because there is no UI to scan.

## 8. Test data policy

- No real application data and no personal data in any fixture (NFR-6).
- Sample label artwork is generated or sourced by the contributor and is
  git-ignored; see `samples/README.md` for why.
- Ground truth lives in `samples/expected.csv` and is version controlled once it
  exists, because accuracy numbers are meaningless without a fixed reference.
