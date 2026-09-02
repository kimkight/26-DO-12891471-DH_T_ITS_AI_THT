# Test Strategy

Testing is organized in five tiers. Each tier states what it covers, what it
deliberately does not, and how it is run.

**Current state:** every tier exists. Nothing below is described as passing
unless it has actually been run.

| Tier | Exists today | Blocked on |
| --- | --- | --- |
| Unit | Yes: `test_compare.py`, `test_warning.py`, `test_parse.py`, `test_ocr.py`, `test_samples.py`, `test_health.py` | Nothing |
| Integration | Yes: `test_api_validation.py`, `test_verify_integration.py`, `test_batch.py` | Nothing |
| Accuracy | Yes: `scripts/measure.py` over `samples/` | Real label artwork; the set is synthetic |
| Performance | Yes: single-label latency and a twelve-label batch, measured by the same script and by `test_batch.py` | A 300-label run, and any run on the deployed target |
| Accessibility | Yes: `frontend/tests/a11y.spec.ts` (axe-core plus a keyboard walk) and `frontend/src/__tests__/contrast.test.ts` | Nothing automated; the screen reader and greyscale rows in section 6 are manual by nature |
| Manual UAT | Checklist written, section 6 | Being run against the deployed URL |

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
| Validation, `test_api_validation.py` | Size and MIME type limits reject before any decoding happens (NFR-7). The batch file-count limit rejects before any file is processed (FR-8). |
| Image preprocessing, `test_ocr.py` | The long edge lands on the configured size and the aspect ratio holds; a rotated image comes back closer to upright, and an upright one is left alone. |
| EXIF orientation and cardinal turns, `test_ocr.py` | A file storing its pixels sideways with an orientation tag decodes upright, including the mirrored orientations that leave the size unchanged; an untagged file reports that nothing was applied; bytes Pillow cannot open still decode through OpenCV; a quarter-turn is undone by its complement (A-15). |
| Warning hyphenation, `test_warning.py` | A narrow column with printer's hyphens across line breaks matches the regulation; a dash used as punctuation is left alone; an altered word in the same column still fails; the capitalization check is unchanged (A-15, FR-5, FR-6). |
| Sample set integrity, `test_samples.py` | The sample warning text is the regulation's; each labelled defect is actually defective. |
| Photo list controls, `frontend/src/__tests__/multiPhoto.test.tsx` | Slots are added up to the cap and no further; the control is withdrawn rather than left to fail; each change is announced; removing a slot returns focus somewhere usable; one image part is sent per attached photograph and an empty slot is skipped (ADR 0007). |
| Photo notes, `frontend/src/__tests__/multiPhoto.test.tsx` | An untouched photograph produces no note; a turned one says how far it was turned; an EXIF-tagged one says the camera saved it sideways; an unreadable one says so in plain language (A-15, FR-9). |

**Deliberately not covered by this tier:** anything involving Tesseract, which
is slow and environment dependent, and therefore belongs in the integration and
accuracy tiers.

## 2. Integration tests

**Scope:** the HTTP contract end to end, in process, with real OCR against small
fixture images.

**Runner:** `pytest` with FastAPI's `TestClient`.

Label artwork is rendered by `samples/labelmaker.py` at test time rather than
committed, so no binary fixture enters the repository.

**The orientation strategy, and the measurement behind it.** Turning a sideways
photograph upright is a decision with two candidate implementations, so it was
measured rather than argued. Both were run over the twelve-label sample set at
all four cardinal rotations, forty-eight cases, on 2026-08-26 on a four-core
session runner with Tesseract 5.3.4:

| Strategy | Correct | Cost per image |
| --- | --- | --- |
| Tesseract orientation and script detection (OSD) | 46 of 48 | about 760 ms |
| Read at 0, 90, 180 and 270 and keep the highest mean word confidence | 7 of 48 | about 1,200 ms |

The second is not a tuning problem. Tesseract's layout analysis already detects
and corrects text turned a quarter-turn clockwise, so the upright image and the
clockwise-turned image produce identical output: 62 words at a mean confidence
of 95.4 either way on the sample label. A score equal on the two cases it has to
separate cannot separate them. `test_ocr.py::TestWhyOrientationUsesOsd` asserts
that equality, so a Tesseract release that changes the behaviour fails a test
rather than leaving this paragraph stale.

Both OSD misreads were on the sample with the least text on it, and both
reported an orientation confidence below 1.0 where every correct answer was
above 11. That figure is the floor, and until v1.1.0 it was only reported. See
"What v1.1.0 added below the floor" below.

Downscaling the image before the OSD call was measured and rejected: at a
900-pixel long edge accuracy fell to 38 of 48, and at 600 pixels to 22 of 48,
for 513 ms and 222 ms respectively.

**What that measurement missed, and what v1.0.1 changed.** Every figure above
was taken on artwork rendered by `samples/labelmaker.py`: crisp black type on a
flat white ground. A real photograph is not that, and on 2026-08-28 a
photograph of a Ketel One back label returned no government warning and
brand-name shrapnel from the bottom fine print. The two measurements below were
taken on 2026-08-29 on a session runner with Tesseract 5.3.4, over the same
twelve-label set degraded into a photograph-like fixture: contrast reduced to
0.18 with a lift of 30, a 2.0-pixel Gaussian blur, and Gaussian sensor noise at
sigma 4, all generated deterministically at test time from a fixed seed.

| Where OSD is asked | Correct, undegraded set | Correct, photograph-like set |
| --- | --- | --- |
| The adaptively thresholded image (v1.0.0) | 46 of 48 | 0 of 48 |
| The upright grayscale (v1.0.1) | 45 of 48 | 44 of 48 |

The two are level on rendered artwork and not remotely level on anything
resembling a photograph, because adaptive thresholding at a 31-pixel block on a
soft-contrast image produces noise rather than glyphs, and OSD cannot judge
noise. That is the whole of the reported blackout: the EXIF tag was applied
correctly, the threshold destroyed the image, OSD turned what was left the wrong
way, and the read came back empty.

**What v1.1.0 added below the floor.** The 46 of 48 above is untouched and above
the floor OSD still decides alone. What is added is that a verdict *below* the
floor stops being applied on trust. The author's mezcal COLA artwork produced
one on 2026-08-30: 180 degrees at a confidence of 0.03, applied, and the brand
read as `AMoviy TS`.

The four-rotation sweep rejected above is not what was added, and the difference
is the reason this is safe. That sweep loses because it cannot separate 0 from
90; below is the same score on the same artwork, over all four rotations:

| Image variant | rot 0 | rot 90 | rot 180 | rot 270 |
| --- | --- | --- | --- | --- |
| Colour | 257 words, 89.1 | 257 words, 89.7 | 254 words, 35.3 | 253 words, 35.5 |
| Grayscale | 106 words, 89.9 | 109 words, 88.4 | 107 words, 30.4 | 116 words, 31.9 |

0 against 90 is a difference of 0.6 and 1.5 points, which is nothing. 0 against
180 is more than fifty. So below the floor the verdict is scored against its
opposite alone, two rotations and never four, and a tie leaves Tesseract's
answer in place. `backend/tests/test_orientation_floor.py` asserts the
mechanism, both directions of override, and that a verdict at or above the floor
is not second-guessed at all.

**And what v1.1.0 added beside the grayscale: the colour image.** Every variant
in the tables above is grayscale, and none of them is the image the file holds.
On a label printed in more than two tones a threshold separates two luminance
classes and not three, so an ink class dissolves; and mean word confidence
cannot detect that, because a word that was never read contributes no confidence
to lower. On the author's artwork the grayscale read scored 89.9 against the
colour read's 89.1 while being the one that lost `42% ALC BY VOL` outright.

| Where the read is taken | Words | Mean confidence | `42% ALC BY VOL` |
| --- | --- | --- | --- |
| Colour, as the file holds it | 257 | 89.1 | read |
| Upright grayscale | 106 | 89.9 | not read |

The decision, the chroma measurement that decides which images pay for it, and
the one-point band that lets coverage break a tie on confidence, are
[ADR 0014](adr/0014-colour-as-an-ocr-candidate.md).
`backend/tests/test_colour_arm.py` carries the assertions, including the
regression guard that more words never beats a materially higher confidence.

**Preprocessing is compared against no preprocessing, per image.** The same
degradation shows that thresholding can be worse than nothing at the read as
well as at the orientation call. Over the twelve labels:

| Pass | Warning found, undegraded set | Warning found, photograph-like set |
| --- | --- | --- |
| v1.0.0, preprocessed only | 11 of 12 | 0 of 12 |
| v1.0.1, better of the two reads | 11 of 12 | 6 of 12 |

Eleven is the ceiling on the undegraded set, because `05-spirits-no-warning`
carries no warning to find. Six of twelve on the degraded set is not a
restoration of accuracy and is not offered as one: the fixture is deliberately
harsh, and half of it stays unreadable. What changed is that a read
preprocessing would have thrown away is now kept. On the sample label
specifically, the preprocessed read scores 0.0 and returns nothing where the
plain read scores 90.9 and returns all sixty-two words including the full
warning.

The choice between the two is by mean word confidence, which is the ranking
A-15 rejected for rotation. The two cases are not the same. Tesseract's layout
analysis silently corrects a quarter-turn, so it returns identical scores for
the two rotations that have to be told apart; it does nothing of the kind for
thresholding, so the two images score differently and the score separates them.
The threshold for skipping the second read is 85, set from the measurement: over
the sample set every label where preprocessing was the right choice scored 95.1
or better, the one where it was not scored 41.4, and over the degraded set the
highest a losing preprocessed read reached was 68.4.

**Cases:**

- `POST /api/verify` with a clean label and matching application data returns
  200 with an outcome for each of the five fields. **Implemented.**
- The same endpoint with a corrupt file returns a 4xx and no field reporting a
  match (FR-9). **Implemented.**
- An oversized file is rejected before the body is read (NFR-7). **Implemented.**
- A disallowed MIME type is rejected before decoding (NFR-7). **Implemented.**
- An image with no text reads differently from fields that did not match (FR-9).
  **Implemented.**
- `POST /api/verify-batch` returns one identified result set per label (FR-8).
  **Implemented**, in `test_batch.py`.
- A batch containing one unreadable image returns results for every other label
  in the batch (US-10). This is the single most important integration case,
  because it is the property that makes batch handling worth having.
  **Implemented**, in `test_batch.py::TestOneBadImageDoesNotFailTheBatch`.
- A batch exceeding the file-count limit is rejected before any file is
  processed (FR-8). **Implemented**, in `test_batch.py::TestOverCount`.
- With the default configuration, no outbound connection is attempted (there is no setting that opens one; the fallback ADR 0003 designed was not built)
  (NFR-3). **Implemented**, as UAT row 16: the test replaces the socket
  constructor so that any attempt to open an IP socket raises, proves the guard
  is live by opening one itself, and then asserts the verification still returns
  200 with `external_call_made` false. AF_UNIX is left alone, because asyncio
  builds its own self-pipe from a Unix socketpair and refusing that would break
  the event loop rather than test the application.
- A photograph turned a quarter-turn, half-turn or three-quarter-turn returns
  the same field outcomes as the upright one, and the response states the turn
  that was applied (A-15). **Implemented**, as UAT row 23, in
  `test_verify_integration.py::TestASidewaysPhotograph`.
- A photograph whose turn is recorded only in its EXIF orientation tag, with the
  pixels stored sideways, reads the same as an upright one (A-15).
  **Implemented**, as UAT row 24.
- A legible label stored under each of the eight EXIF orientation values, with
  the pixels stored the way a camera writing that value stores them, returns the
  same field outcomes and finds the government warning. **Implemented**, as UAT
  row 54, in `test_verify_integration.py::TestTheKetelOneHotfix` and at the unit
  tier in `test_ocr.py::TestEveryExifOrientationReadsItsLabel`. The decode is
  additionally compared pixel for pixel against the upright original in
  `test_ocr.py::TestExifOrientation`, so the delegation to
  `PIL.ImageOps.exif_transpose` is proved rather than assumed.
- A file whose EXIF tag lies about its own pixels, tag sideways and pixels
  upright, is rescued by the quarter-turn check and the response reports the
  disagreement. **Implemented**, as UAT row 55, in the same two classes. This is
  what makes the check run whether or not a tag was applied.
- A photograph-like image where the plain read beats the preprocessed one keeps
  the plain read, and says so in `read_path`. **Implemented**, as UAT row 56, in
  `test_verify_integration.py::TestTheKetelOneHotfix` and
  `test_ocr.py::TestPreprocessingHasToEarnItsRead`, which also asserts that the
  preprocessed image alone would have lost the warning.
- A warning set in a narrow column with printer's hyphens across line breaks
  reports a match, and the same column with one word altered still reports a
  mismatch (A-15, FR-5). **Implemented**, as UAT row 25, in
  `test_verify_integration.py::TestAHyphenatedWarningColumn`.
- Two photographs of one label whose fields are split between them return a
  complete result, and each field names the photograph it came from (ADR 0007).
  **Implemented**, as UAT row 26, in
  `test_multi_photo.py::TestFieldsSplitAcrossTwoPhotographs`.
- One unreadable photograph among good ones does not fail the submission, and is
  reported rather than hidden (ADR 0007, FR-9). **Implemented**, as UAT row 27,
  in `test_multi_photo.py::TestOneUnreadablePhotographAmongGood`.
- A submission where no photograph could be read returns its own error code and
  no field outcomes (FR-9). **Implemented**, in
  `test_multi_photo.py::TestAllPhotographsUnreadable`.
- More photographs than the cap are refused before any is processed, with the
  limit named (NFR-7). **Implemented**, in
  `test_multi_photo.py::TestThePhotographCap`.
- A single photograph behaves exactly as it did before ADR 0007. **Implemented**,
  in `test_multi_photo.py::TestOnePhotographIsUnchanged`, which is the test that
  makes the rest of this section safe to add.
- No image content and no extracted or application value reaches the logs
  (NFR-6). **Implemented**, as UAT row 17: distinctive values are searched for
  across every captured record, and the one record the verification path writes
  is held to an allow-list of `bytes_received`, `ocr_ms` and
  `beverage_type_supplied`, so a field added to it later has to be added there
  deliberately.

### A sheet of several panels, and a line that belongs to one of them

`backend/tests/test_panel_segmentation.py`, against a three-panel sheet with a
strip of type set at 90 degrees in each gutter, rendered at test time. Each
panel carries a vocabulary that appears nowhere else on the sheet, so "this line
came from two panels" is a fact about the line rather than an impression of it.

- No assembled line carries words from two panels, and no panel is returned to
  after leaving it in reading order. The two are asserted separately because
  they are two mechanisms: Tesseract returning a line that spans the sheet, and
  a reading order that alternates between panels. Four of the six lines this
  fixture reads as fail the first against the build this release starts from.
- The government warning, printed in one panel with two panels of decoys beside
  it, matches 27 CFR 16.21 exactly rather than nearly. The same fixture scores
  213 edits against the previous build.
- The strips are marked as type set at 90 degrees, which is what keeps them out
  of the type-size ranking that locates the brand name.
- **A single-panel label is byte-identical.** Asserted against the previous
  grouping rule reproduced in four lines inside the test rather than against a
  stored expectation, because a stored expectation only proves the output has
  not changed since somebody wrote it down.
- **The segmentation adds no Tesseract read** (NFR-1). Asserted twice: that
  assembling lines from a word table reads nothing at all, and that a
  multi-panel sheet costs exactly the reads its own reported read path names.
- One class in that module is built from a word table rather than from pixels,
  and says so. Tesseract does not return a line spanning two panels on clean
  synthetic artwork at any geometry tried, and it did so repeatedly on the
  author's filing where the blocks spanned x 44 to 1526 of a 1600 pixel sheet. A
  fixture that cannot reproduce the mistake cannot prove it is handled, so the
  mistake is stated directly.

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
| Orientation detection (Tesseract OSD) | under 1,000 ms |
| OCR (Tesseract) | under 3,000 ms |
| Matching and response assembly | under 200 ms |
| Headroom | remainder of the 5,000 ms budget |

Orientation detection is a second pass over the image and it roughly doubles the
per-label cost: single-label verification measured 1.3 s end to end on a session
runner with it on, against 0.5 s before it existed. Both are inside NFR-1's
target and the turned case is asserted against that target in
`test_verify_integration.py`. It is a real cost on the batch path, where it is
paid once per row, and `TTB_CORRECT_ORIENTATION=false` turns it off for a
submission known to be upright. No batch latency target exists (OQ-6).

**The second read costs what it costs, and only when it runs (v1.0.1).** The
plain read is skipped when the preprocessed one scores 85 or better, which is
eleven of the twelve sample labels. Median per-label figures over the sample
set, same session runner, `extract_text` end to end including decode:

| Set | v1.0.0 | v1.0.1 | Labels taking a second read |
| --- | --- | --- | --- |
| Twelve labels as rendered | 1,086 ms | 1,153 ms | 1 of 12 |
| The same set, photograph-like | 383 ms | 1,589 ms | 12 of 12 |

The first row is the ordinary case and it is roughly unchanged: one label pays
the second read and the rest short-circuit. The second row is the honest cost
when preprocessing loses on every image, about 1.5 times rather than exactly
double, because decode, scaling and the orientation call are done once and
shared, and because the plain read of a degraded image is itself cheaper.
v1.0.0's 383 ms on that row is not a good number: it is the cost of returning
nothing. Both figures are inside NFR-1. The cost is paid once per row on the
batch path, and `TTB_CORRECT_ORIENTATION=false` does not turn it off, because it
is a read rather than an orientation call.

**More than one photograph multiplies that figure**, and it was measured rather
than extrapolated. ADR 0007 accepts up to three photographs of one label, read
one after another. Median of three runs each, same session runner, same sample
label, through `POST /api/verify`:

| Photographs | End to end | NFR-1 target |
| --- | --- | --- |
| 1 | 1.24 s | about 5 s |
| 2 | 2.49 s | about 5 s |
| 3 | 3.83 s | about 5 s |

Three photographs is inside the target with about a second to spare on this
hardware, and on slower hardware it may not be. That margin is the reason the
three-photograph case is **measured and printed rather than asserted**:
`test_multi_photo.py` prints the figure so a reviewer sees it, and does not gate
on it, for the reason section 7 gives for the whole performance tier. A runner's
timings vary enough that gating this close to the line would produce failures
that say nothing about the change. The single-photograph assertion still gates,
because it has four seconds of headroom.

Two things bound the cost rather than one: `TTB_MAX_LABEL_PHOTOS`, and the fact
that the ordinary case is one photograph, which is what the interface starts
with. Measuring a three-photograph submission on the deployed target is on the
section 9 checklist in [09_DEPLOYMENT.md](09_DEPLOYMENT.md); no figure from that
hardware exists yet.

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
| 23 | A photograph of a label taken sideways, submitted through the interface | Every field that a clean upright photograph finds is still found; the result states that the photograph was turned and by how much | First real-artwork test, 2026-08-26; A-15 |
| 24 | A phone photograph whose only turn is in its EXIF orientation tag, with the pixels stored sideways | Read the same as an upright photograph; the result states that the EXIF orientation was applied | First real-artwork test, 2026-08-26; A-15 |
| 25 | A label whose warning is set in a narrow column with printer's hyphens across line breaks | The warning reports match. **A mismatch is a failure of this test.** An altered word in the same column still reports mismatch | First real-artwork test, 2026-08-26; A-15; FR-5 |
| 26 | A round bottle photographed twice, front and back, with the fields split between them | Every field found on either photograph is reported as found, and each result names the photograph it was read from | ADR 0007; A-16 |
| 27 | One unreadable photograph attached alongside a good one | The good photograph still produces a result, and the unreadable one is listed as unreadable rather than omitted | ADR 0007; FR-9 |
| 28 | Attach photographs up to the limit, then look for the control that adds another | The control is no longer offered and the interface says why. **Reaching the API's refusal is a failure of this test.** | ADR 0007; NFR-4 |
| 29 | Attach two photographs and check a label using only the keyboard | Every add and remove control is reachable, focus stays visible, and each change to the photo list is announced | ADR 0007; NFR-5 |
| 30 | A bottle whose back label carries a percentage in marketing copy, for example "reduce our environmental impact by 7%", and whose alcohol statement is on the front | The alcohol content reports the front label's statement, or not found. **Reporting the marketing percentage is a failure of this test.** | Deployed-target test, 2026-08-27; FR-1; FR-7 |
| 31 | Attach a Public COLA Registry printout on the single-label view | The brand name, class or type designation, alcohol content and net contents appear in the application fields, each marked as read from the application form, before any check is run | FR-11; ADR 0008 |
| 32 | Attach a filled-in copy of TTB F 5100.31 | The brand name and fanciful name are read from the form's own fields, and the ticked product-type box gives the beverage type. **The class or type designation, alcohol content and net contents are reported as not found, with the reason: they are not items on the form.** | FR-11; A-17 |
| 33 | Attach a document, correct one filled field by hand, then run the check | The corrected value is what is compared, and the result says that value was typed. The parsed block still shows what the document said. | FR-11; ADR 0008 |
| 34 | Attach a photograph or scan of a printed form | It is read through the same local OCR the tool reads labels with, and the interface says so. **Values OCR could not read are reported as not found rather than approximated.** | FR-11; FR-1 |
| 35 | Attach a file that is not a readable application, for example an empty PDF | The message names the problem, no field reports a match, and the typed fields are still usable | FR-11; FR-9 |
| 36 | Attach a Public COLA Registry printout whose class or type is captioned `Class/Type Description:` | The class or type field holds the designation alone, for example `Kentucky Straight Bourbon Whiskey`. **A value beginning `Description:` is a failure of this test.** Where the printout also carries a `Class/Type Code:` line, the code is still reported beside the designation | Deployed-target test, 2026-08-28; FR-11; A-17 |
| 37 | A batch of two labels, each with a COLA document named to match its image | Both labels return a result, and each result's application values are the ones its own document carried | ADR 0009; FR-8; FR-11 |
| 38 | The same batch with one image renamed so nothing matches it | That image reports an error naming the file, and the other label still returns a result. **A whole-batch failure is a failure of this test.** | ADR 0009; FR-8; FR-9 |
| 39 | The same batch with one document replaced by a file that cannot be read | That label reports an error naming the document, no field reports a match for it, and the other label still returns a result | ADR 0009; FR-9 |
| 40 | Open the batch view and look at it before choosing any files | The naming rule that pairs an image with a document is on screen, not behind a disclosure. After choosing files, the count of pairs is shown and announced | ADR 0009; NFR-4; NFR-5 |
| 41 | Choose a label photograph on the single-label view | The photograph itself appears inside the scan frame, at a size that makes the bottle recognizable. **A frame showing only the filename is a failure of this test.** | Restyle, 2026-08-28; NFR-4 |
| 42 | Read one field result | The outcome chip leads the row, before the field name, and the two values read as label on the left and value on the right. Every outcome is still a word and a shape, not a colour | Restyle, 2026-08-28; FR-10; NFR-5 |
| 43 | Move between the two views using only the keyboard | The segmented pill control is reached with one Tab, moved between with the arrow keys, and the selected segment is visibly filled and announced as selected. **Reaching it with two Tab stops, or an unclear active segment, is a failure of this test.** | Restyle, 2026-08-28; NFR-5 |
| 44 | View the restyled page in greyscale | The active pill, the needs-review card and every outcome chip are still distinguishable, because each is carried by fill, weight or shape as well as by hue | Restyle, 2026-08-28; NFR-5 |
| 45 | Load the page with the network blocked to everything but this origin | The page renders in Inter, from this origin. **A request to any font CDN is a failure of this test.** | Restyle, 2026-08-28; NFR-3 |
| 46 | Open the single-label view and look at it before choosing anything | The photo picker and the application document upload are on screen, in that order, and the five typed fields are not. The upload is not worded as the alternative to typing. **Five empty text boxes greeting the agent is a failure of this test.** | US-24; NFR-4; FR-11 |
| 47 | Expansion case 1: with no document at hand, open `Or type the application values` | The five fields appear, reachable and operable from the keyboard alone, with visible focus, and the control reports itself as expanded. Pressing it again collapses them | US-24; NFR-5 |
| 48 | Expansion case 2: attach a filled-in TTB F 5100.31, which carries no class or type, alcohol content or net contents boxes | The fields open on their own, with the brand name filled and marked as read from the application form and the three gaps empty. The expansion is announced. **Leaving the gaps behind a collapsed disclosure is a failure of this test.** | US-24; A-17; NFR-5 |
| 49 | Expansion case 3: attach a file that is not a readable application, for example an empty PDF | The FR-9 message names the problem, the fields open as the fallback, and the expansion is announced. Nothing is filled in from the document | US-24; FR-9 |
| 50 | Attach a Public COLA Registry printout that carries every value | Nothing opens, because nothing is left to enter. The upload's own summary says what it read and points at the disclosure. **An expansion here is a failure of this test.** | US-24 |
| 51 | Attach a document, then open the disclosure and correct one filled value | The corrected value is what is compared, and the result says that value was typed. FR-11's precedence is unchanged by the disclosure | US-24; FR-11 |
| 52 | Look for the beverage type | It is inside the disclosure, after the four text fields, and says it is not compared against the label. **Meeting it as the first field is a failure of this test.** | US-24; A-12; A-13 |
| 53 | Open the batch view after doing all of the above | It is unchanged: documents only, no typing, the pairing rule on screen | US-24; ADR 0009 |
| 54 | Re-submit the 2026-08-28 Ketel One back label photograph, the one the interface flagged as saved sideways by the camera | The government warning is found and reports match, and the net contents report `750 mL`. **A not-found government warning on a label whose warning is legible in the photograph is a failure of this test.** The brand name is not part of this row; see row 57 | Deployed-target evidence, 2026-08-28; FR-1; FR-6; A-15 |
| 55 | Submit the same label as an upright screenshot with no EXIF tag, and again as identical pixels turned 90 degrees counter-clockwise carrying EXIF orientation 6 | Both are read, and the second returns the same field outcomes as the first. **Any text found on one and not the other is a failure of this test.** The result reports the tag that was found, whether it was applied, and any further turn the confidence check chose | Deployed-target evidence, 2026-08-28; A-15 |
| 56 | Submit a photograph whose EXIF tag disagrees with its pixels, for example an upright image saved with orientation 6 by an editor that turned the pixels and left the tag | The label still reads, because the quarter-turn check runs whether or not a tag was applied. The result shows the disagreement: a tag was found and applied, and a further turn was needed | Deployed-target evidence, 2026-08-28; A-15 |
| 57 | Submit a front label whose brand is set in a blackletter logotype | The brand reports not found rather than a misreading of the logotype. **Reporting shrapnel from nearby fine print as the brand name is a failure of this test.** Out of scope to solve: see SG-1 and the v1.0.1 changelog entry | Deployed-target evidence, 2026-08-28; FR-1; OOS |

| 58 | Upload the author's own mezcal COLA PDF and nothing else: no photograph, no typed values | All five compared fields reconcile, from that one file. The brand name and the class or type come from the document's text; the alcohol content and the net contents come from the label artwork embedded in it, and each field says which. **Two of five reconciling, which is what v1.0.1 returned, is a failure of this test.** | The author's evidence, 2026-08-29; FR-11; ADR 0010; A-17 |
| 59 | Read the result of row 58 | It states, once, that the label checked was the artwork inside the application rather than a photo of a bottle, and that checking the bottle still needs a photo of the bottle. **A result that reads as a check of the product is a failure of this test.** | The author's evidence, 2026-08-29; ADR 0010; OOS-8 |
| 60 | Upload a COLA document whose only embedded pictures are a seal, a barcode and a signature block | The artwork values report not found with the reasons A-17 gives, nothing crashes, and the submission is refused with a message naming the missing piece and offering the photo upload. **A field outcome on that refusal is a failure of this test.** | The author's evidence, 2026-08-29; ADR 0010; FR-9 |

| 61 | Upload the mezcal COLA PDF and a photo of the label together, through the one picker | Each file is listed with what it was taken to be: the PDF as the label application, the photo as the label picture. The check runs against the photo, with the document as the application side | The author's evidence, 2026-08-29; FR-12; ADR 0011 |
| 62 | Deliberately put the COLA PDF where a photo would have gone, and the photo where the application would have gone | Both are still used on the correct side, because the classification is made from the file rather than from the control. **A COLA form read as label artwork is a failure of this test.** | The author's evidence, 2026-08-29; FR-12 |
| 63 | Work the upload from the keyboard alone, with a screen reader | One labelled control, reachable by Tab and operable by Enter or Space; each accepted file announced with what it was taken to be; drag and drop offered on top of that rather than instead of it | FR-12; NFR-5 |

| 64 | Upload a document that answers every compared value, then look at the fields section | Every value is one read-only line saying what it is and where it came from. **A single editable box on screen is a failure of this test.** One collapsed control, "Review the values", holds the boxes for an agent who disagrees with one | The author's evidence, 2026-08-29; FR-13; US-26 |
| 65 | Upload a document that answers all but one, without touching the keyboard | Exactly one editable field is on screen, the cursor is in it, and a screen reader says which value is missing and that it can be entered or a clearer image uploaded | The author's evidence, 2026-08-29; FR-13; NFR-5 |
| 66 | Load the page and look at it before uploading anything | Unchanged from Session 10: one collapsed disclosure over the five boxes, and no summaries of values that do not exist yet | FR-13; US-24 |

| 67 | Submit the mezcal COLA PDF alone and read the government warning card | The outcome is needs human review, not "does not match". The card names the number of characters, shows the exact difference with the missing character struck through, and says in words that this is not a match | The author's evidence, 2026-08-29; FR-5; ADR 0012 |
| 68 | Submit a label whose warning is missing the clause "or operate machinery" | The outcome is a mismatch. **Needs human review on a missing clause is a failure of this test.** The difference is still shown, because it is evidence either way | FR-5; ADR 0012 |
| 69 | Submit a label whose warning is word for word correct and whose prefix reads "Government Warning:" | The outcome is a mismatch, and the reason names capitalization. **A capitalization failure routed to needs human review is a failure of this test**: it is a defect a person caught on a real submission, not something OCR produces from a compliant label | Jenny Park interview; FR-6; ADR 0012 |

Rows 67 to 69 come from the author's first problem report of 2026-08-29 read
through to its consequence. The artwork embedded in their filing reads the
statement with one character wrong, and rows 68 and 69 are the two ways the
routing must not overreach: a real wording difference and a real capitalization
defect both stay mismatches.

Rows 64 to 66 come from the author's design instruction of 2026-08-29:
"Collapse the form fields and only expand if there is something that isn't read
in from the application or picture." Row 66 is the regression half: US-24's
behaviour before an upload is what it was, and this row exists so that making
the fields quieter afterwards cannot make them louder beforehand.

Rows 61 to 63 come from the author's third report of 2026-08-29, the design
instruction: "these should be combined; just one upload; simplify the interface.
You should be able to upload (pdfs or images)." Row 62 is the one worth running
adversarially, because it is the failure the two pickers actually produced: a
file put in the wrong box was read as the wrong thing, silently.

Rows 58 to 60 come from the author's second problem report of 2026-08-29 and
are the first of the two problems reported that day. The document was a real
TTB Form 5100.31, OMB No. 1513-0020, three pages, and the deployed v1.0.1 build
reconciled two of its five fields. The values were not missing from the file:
the alcohol content and the net contents were printed on the flat label artwork
embedded on page 3 at 1750 by 1150 pixels, which the parser never looked at.
Row 60 is the honest other half, because a filing that embeds only furniture has
to fail visibly rather than by reporting a label side that is a signature block.

Rows 54 to 57 come from one submission, on 2026-08-28, of a photograph of a
Ketel One vodka back label: crisp, flat, the full government warning in clear
capitals, and `750 mL`. The deployed v1.0.0 build returned the brand as `Sal.`,
the class as shrapnel from the bottom fine print, net contents not found, and
the government warning not found. Rows 54 to 56 are what v1.0.1 fixes. Row 57 is
what it does not: a brand set in a blackletter logotype is not something OCR
reads, and the front label carries the brand in plain type, which is what
ADR 0007's multi-photo path is for. The row exists so the limit is tested rather
than assumed.

Row 14 is Sarah's actual acceptance test, restated as a procedure: something
her mother, "73 and just learned to video call her grandkids," could figure out.
[Source: Sarah Chen interview] Row 15 exists because overstating what was
checked is the failure mode most likely to cause real harm.

## 7. What runs in CI

Defined in `.github/workflows/ci.yml`. All jobs gate the aggregate `ci` check.

| Job | Contents |
| --- | --- |
| `backend` | Installs Tesseract and a TrueType font, then `ruff check`, `ruff format --check` over `backend/`, `samples/` and `scripts/`, and `pytest` with coverage |
| `frontend` | `eslint`, `prettier --check`, `tsc -b`, `vite build`, `vitest run`, then Chromium and `frontend/tests/a11y.spec.ts`: axe-core over the landing page, the batch tab and a rendered result set, plus a keyboard walk and a focus-visibility assertion. The report is uploaded on failure |
| `infra` | `terraform fmt -check -recursive` and `terraform validate` over `infra/terraform/` |
| `audit` | `pip-audit --strict`, `npm audit --audit-level=high` |
| `container` | Docker build, health endpoint probe against the running container, non-root user assertion, SBOM generation and upload |
| `ci` | Aggregate gate; fails if any job above failed or was cancelled |


The accuracy and performance tiers run as scripts rather than as CI gates.
`scripts/measure.py` is run by hand and its output is quoted in the pull request
that changes the engine, because a runner's timings vary enough that gating on
them would produce failures that say nothing about the change. The single-label
latency assertion in `test_verify_integration.py` does gate, against the
5-second target rather than against a tighter number.

The accessibility tier **is** in CI. What it does not cover, and what section 5
says is manual by nature, is the screen reader pass and the greyscale check.

## 8. Test data policy

- No real application data and no personal data in any fixture (NFR-6). This
  covers COLA documents as well as labels: `samples/formmaker.py` generates a
  filled TTB F 5100.31 and a Registry printout at test time, with invented
  values and permit and serial numbers deliberately not in a format TTB
  issues. No real filed application is committed, and none has been parsed;
  that limit is OQ-22.
- Sample label artwork is generated or sourced by the contributor and is
  git-ignored; see `samples/README.md` for why. That includes the multi-panel
  sheets `samples/labelmaker.py` renders for the segmentation tier: the panel
  text is nonsense vocabulary chosen so that a crossed line is detectable, and
  it is generated at test time like everything else.
- **A real filing is evidence, not a fixture.** The defect the panel
  segmentation fixes was found on the author's own mezcal COLA, which carries a
  real company, a real tax identifier and a real address. Every measurement in
  `app/ocr.py`, in the CHANGELOG and in this document was taken on it, and none
  of it is committed: not to `tests/`, not to `docs/`, not as an encoded blob,
  and not in a pull request description. What is committed is the synthetic
  fixture that reproduces the same defect.
- **No extracted image is logged or kept, and a signature is not read at
  all.** A filed application carries the applicant's handwritten signature,
  which is the most personal artefact on the form. Nothing keeps an embedded
  image past the request or puts one in a log line at any point; a picture that
  is read reaches the OCR engine through the temporary file `pytesseract`
  writes and deletes before it returns (NFR-6 as reworded in v1.3.0), and a
  rejected one is never decoded. The
  rejection record the response carries holds a page number, two dimensions and
  a named reason and nothing else, asserted on the record's fields in
  `backend/tests/test_embedded_artwork.py` rather than on one instance of it.
  The signature-shaped fixtures in that module are strokes drawn from
  arithmetic; no signature, real or imitated, is committed.
- Ground truth lives in `samples/expected.csv` and is version controlled once it
  exists, because accuracy numbers are meaningless without a fixed reference.
