# Assumptions

Everything inferred rather than stated by a source. Each entry says what was
assumed, why, what it affects, and how it would be confirmed or falsified.

The rule this list enforces: an assumption that is not written down becomes
indistinguishable from a fact within one revision, and there is no way to find
it again afterwards.

Assumptions are marked `(Assumption)` where they appear in other documents.

| ID | Assumption | Affects | Risk if wrong |
| --- | --- | --- | --- |
| [A-1](#a-1) | Batch limit of 300 files | FR-8, NFR-2 | Low |
| [A-2](#a-2) | Upload size limit of 10 MB per file | NFR-7 | Low |
| [A-3](#a-3) | Accepted image types | FR-1, NFR-7 | Low |
| [A-4](#a-4) | Match and review threshold defaults of 95 and 80 | FR-3 | Medium |
| [A-5](#a-5) | Latency budget allocation across stages | NFR-1 | Low |
| [A-6](#a-6) | Type size and contrast checks are out of scope | OOS-5 | Low |
| [A-7](#a-7) | "About 5 seconds" is a per-label target | NFR-1 | Medium |
| [A-8](#a-8) | The agent supplies application data manually | FR-2 | Medium |
| [A-9](#a-9) | Extraction is limited to the sample label's five fields | FR-1, OOS-6 | Medium |
| [A-10](#a-10) | Frontend dependency versions | Build | Low |
| [A-11](#a-11) | English-only OCR is sufficient | FR-1 | Low |

---

## A-1
**A batch is limited to 300 files by default.**

Sarah Chen describes importers who "dump 200, 300 label applications on us at
once." [Source: Sarah Chen interview] She states a range, not a limit. The
default `TTB_MAX_BATCH_FILES=300` takes the top of the range she names.

**Confirmed or falsified by:** asking Sarah or Janet what the real maximum is.
**Risk if wrong:** low. It is configurable, and the limit is enforced with a
message that names it.

## A-2
**A single upload is limited to 10 MB.**

No source states a file size limit. NFR-7 requires one, because accepting
arbitrarily large uploads is a denial-of-service path. 10 MB comfortably holds a
high-resolution label photograph.

**Confirmed or falsified by:** measuring the file sizes agents actually submit.
**Risk if wrong:** low. Configurable, and rejections name the limit.

## A-3
**Accepted image types are JPEG, PNG, WebP, and TIFF.**

No source lists accepted formats. These cover photographs, screenshots, and the
scanned artwork typical of document workflows. PDF is deliberately excluded,
since it would require a rendering step the prototype does not have.

**Confirmed or falsified by:** asking what formats arrive with real applications.
Whether PDF artwork is common is a specific question worth asking.
**Risk if wrong:** low, unless PDF turns out to be common, in which case it is a
scope addition rather than a defect.

## A-4
**The match threshold is 95 and the review threshold is 80.**

Decision D-5 requires three outcomes but sets no thresholds. These are starting
points for tuning, not derived values, and no measurement supports them.

**Confirmed or falsified by:** measuring score distributions across the labeled
sample set, then reviewing the resulting outcomes with compliance agents. Tracked
as OQ-9.
**Risk if wrong:** medium. Set too high and Dave's `STONE'S THROW` case lands in
review instead of matching. Set too low and real discrepancies pass as matches,
which is the more damaging direction.

## A-5
**The latency budget splits as validation under 100 ms, preprocessing under
500 ms, OCR under 3,000 ms, and matching under 200 ms.**

NFR-1 sets about 5 seconds end to end. [Source: Sarah Chen interview] The split
across stages is a working allocation for planning, with OCR assumed to dominate
because it is the CPU-bound stage.

**Confirmed or falsified by:** stage-level measurement in the performance tier.
**Risk if wrong:** low. It is a planning aid, not a requirement. Only the 5-second
total is a requirement.

## A-6
**Type size, characters per inch, and contrasting background checks are out of
scope.**

27 CFR 16.22 sets minimum type sizes keyed to container volume, maximum
characters per inch, and a contrasting background requirement. Excluding them
(OOS-5) is an inference, not a stated decision.

The basis: these are physical measurements relative to a known container size
and print dimensions. The system receives an image with no scale reference and
no container size, so it cannot measure millimetres. Decision D-5 also defines
warning checking as exact text plus capitalization, with no mention of
typography.

**Confirmed or falsified by:** confirming with Sarah or Jenny that these remain
manual checks.
**Risk if wrong:** low for the prototype. It would be a significant scope
addition, not a defect.

## A-7
**"About 5 seconds" is a per-label target, not a per-submission target.**

Sarah's statement is about single-label processing, in contrast with a vendor
system that took "30, 40 seconds sometimes to process a single label."
[Source: Sarah Chen interview] She does not state a batch target.

**Confirmed or falsified by:** asking Sarah what an acceptable wait is for a
300-label batch. Tracked as OQ-6.
**Risk if wrong:** medium. If 5 seconds were expected for an entire batch, the
architecture would need an asynchronous job model rather than a synchronous
request.

## A-8
**The agent supplies application data by entering it, rather than the system
retrieving it.**

There is no COLA integration, so nothing can fetch application data
automatically. [Source: Marcus Williams interview] It follows that the data must
be supplied with the request, but no source states how.

**Confirmed or falsified by:** asking Sarah or Janet, particularly for the batch
case. Tracked as OQ-16.
**Risk if wrong:** medium for batch. Manual entry for 300 labels is not
plausible, so the batch path likely needs a structured file.

## A-9
**Extraction covers the five fields in the sample label, and not bottler name,
address, or country of origin.**

The assignment lists seven common label elements, then gives a sample label with
five fields and says the app "should handle labels containing information like
the example below."
[Source: Technical Requirements, Additional Context and Sample Label sections]
Treating the sample's field list as the extraction scope (OOS-6) is an
inference.

**Confirmed or falsified by:** asking whether bottler name and address and
country of origin are expected in the prototype.
**Risk if wrong:** medium. It would mean two additional fields, which is
additive work rather than rework. It is listed as stretch goal SG-3.

## A-10
**Frontend dependency versions in `frontend/package.json` are correct and
mutually compatible.**

They were hand-written to match the standard Vite React TypeScript template,
because `npm create vite@latest` could not run: `registry.npmjs.org` returned
403 in the build session (OQ-15). No install or build has verified them.

**Confirmed or falsified by:** the `frontend` job in CI, which runs
`npm install`, `eslint`, `prettier --check`, `tsc -b`, and `vite build`.
**Risk if wrong:** low. A version or configuration mismatch fails CI loudly and
is fixed in one commit.

## A-11
**English-only OCR is sufficient.**

The build instruction is explicit: do not install OCR models beyond English. All
example content in the assignment is English.

Worth noting, without drawing a conclusion: the assignment mentions "Country of
origin for imports," and imported labels can carry non-English text. Whether
non-English labels must be read is not stated.

**Confirmed or falsified by:** asking whether non-English labels reach this
workflow.
**Risk if wrong:** low for the prototype, since it is an explicit instruction.
