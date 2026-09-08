# ADR 0024: A form with no text layer is read once, at check time, and the upload step says so

| | |
| --- | --- |
| Status | Accepted |
| Date | 2026-09-08 |
| Author | Kimberly D. Kight |
| Decision reference | Extends [ADR 0017](0017-read-the-artwork-once.md) from the pictures inside a document to its pages; bounded by [ADR 0023](0023-a-read-budget-per-document.md); NFR-1, FR-11, FR-13, NFR-6 |

## Context

A third real filed COLA, not committed to this repository, was put through
the deployed v1.5.0 build from the browser. It has no text layer at all. The
prefill request, `POST /api/classify`, which runs the moment the agent picks
the file, took **10322 ms**. `extraction_path` came back as `ocr`: all three
pages were rasterised and read through the label pipeline, in the upload
step, before the agent had clicked anything. The check was not reached.

Nothing showed the ten seconds. `POST /api/classify` logged counts only,
under the comment "NFR-6: counts only", and returned no duration. NFR-1 is
about "single-label verification"; no requirement bounded the upload step
and no instrument measured it.

**The same pages were about to be read again.** The check, `POST /api/verify`,
parses the document afresh with every read turned on, because nothing is
kept between requests (NFR-6, ADR 0017). On a scan that means rendering and
reading the same three pages a second time, so the agent's total for that
document would have been about ten seconds twice, plus the artwork. This is
the shape ADR 0017 found on 2026-09-01 for the pictures, one level up: an
expensive read in the prefill request that the check pays for again.

**What the prefill read was for.** FR-13: the values read off the
application go quiet in the interface before the agent types, and only the
gaps go loud. On a document with a text layer, the common case and both
committed filings, that read costs milliseconds and stays. On a scan it
costs ten seconds and is the slowest thing the product does.

## Decision

**`POST /api/classify` reads a PDF's text layer and stops. On a file with no
text layer it renders nothing and reads nothing**, counts the pages and the
pictures, and reports `extraction_path: "not_read"` with `pages_not_reached`
set to the page count. The one note on the document says the file has no
text to read and that its pages will be read as pictures when the label is
checked.

**The pages are read once, at check time**, under the read budget of ADR
0023, and their values fill the result exactly as they did before: the
`ocr` path, the same pipeline, the same precedence.

**A value the check is about to read is not a gap.** The interface already
treats the two artwork values that way (ADR 0017, `pendingFromArtwork`);
on a `not_read` document it treats all five that way. No box opens, focus
does not move, and the live region does not say a value was not found,
because nothing has been looked for yet. The upload card says the true
thing: none of the values were filled in, because the file has no text to
read, and its pages will be read when the label is checked.

**`POST /api/read-application` still reads everything**, as ADR 0017 left
it. It is the FR-11 route for a caller with no check behind it.

## What it costs the agent, in full

On a scan, the five boxes do not fill before the check. Under ADR 0017 an
agent with a text-layer filing saw three values fill at upload and two
arrive with the result; with a scan they now see none fill at upload and all
five arrive with the result. FR-13's "values that were read go quiet" holds
for the text-layer case unchanged and is deferred to the result on a scan.

The agent cannot correct a misread value before the first check on a scan.
On the third document the OCR path read the brand name as the form's own
field caption and ran the class or type into the next item's instruction
(OQ-41); under the old design those wrong values sat in the boxes for ten
seconds before the check and could be retyped first, and under this one they
arrive on the result as a confident mismatch, and the agent retypes them and
checks again. In wall-clock terms the two designs cost the same when a
correction is needed, about two page reads either way, and this one costs
one page read instead of two when none is. The defect that makes a
correction needed is OQ-41's to fix, not a reason to keep paying for the
pages twice.

The check on a scan is slower than it was, by the page reads that moved into
it. On the third document that is about ten seconds of page OCR inside the
check, which breaches NFR-1 on its own, and ADR 0023's budget is what bounds
it. NFR-1 is reported as partially met with this document named.

## Alternatives considered

### Alternative A: keep the page OCR in the upload step and bound it

Leave the values filling at upload and cap the page reads there under the
same budget. Rejected because the check still reads the pages again, so the
agent still waits for the same read twice, and a bound on each request is
not a bound on the submission; NFR-1's amendment of 2026-09-01 says exactly
that. A target met per request and missed per submission is a target
reported wrongly.

### Alternative B: read the pages once at upload and hand the reading to the check

Only possible with a store of the reading between two requests, keyed by
something derived from the applicant's file. That is the cache ADR 0017
refuses, for the reason it gives: NFR-6 is an acceptance criterion and a
promise printed on every screen. Not built.

### Alternative C: read one page at upload, the rest at check time

Fill what page 1 carries, defer the others. On TTB F 5100.31 the brand name
is item 6 on page 1 and the third document's brand came back wrong from that
page (OQ-41), so the value most likely to fill first is the one measured to
fill wrongly. A partial read that costs a third of ten seconds and still
gets re-read by the check is the same shape as the problem, smaller.

## Consequences

**Positive.** The upload step on a scan goes from about ten seconds to the
cost of opening the PDF; the batch tab's chip for a scanned PDF settles as
fast as it does for any other. One document is read once, whatever kind of
document it is. `POST /api/classify` now logs and returns `elapsed_ms` and
the phase breakdown, so this cannot be invisible again.

**Negative.** Five values instead of two arrive with the result rather than
before it, on a scan. The check on a scan carries the page reads and is
slower by that amount.

**Risks accepted.** An agent who wants the values before the check on a scan
types them, and FR-11's precedence makes the typed value win.

## References

- [ADR 0017](0017-read-the-artwork-once.md), the same decision for the pictures
- [ADR 0023](0023-a-read-budget-per-document.md), what bounds the read this moves
- FR-11, FR-13 and NFR-1 in [03_REQUIREMENTS.md](../03_REQUIREMENTS.md)
- OQ-41 in [OPEN_QUESTIONS.md](../OPEN_QUESTIONS.md), the wrong text the OCR path captured
- `backend/tests/test_classify_timing.py`
