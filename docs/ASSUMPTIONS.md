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
| [A-12](#a-12) | Alcohol content must be numerically identical; no tolerance band | FR-7 | Medium |
| [A-13](#a-13) | Net contents compared only when units match; no conversion | FR-7 | Low |

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

## A-12
**Alcohol content on the label and in the application must be numerically
identical.**

- Normalize both values before comparison: strip "%", "Alc./Vol.", "ABV",
  "alc. by vol.", whitespace, and trailing zeros, so `45% Alc./Vol.`, `45.0%`,
  and `45` are the same number.
- If the label also states proof, cross-check that proof equals 2 x ABV
  (27 CFR 5.65 defines proof this way for spirits). A proof value that does not
  equal twice the ABV is reported as **needs human review** with both numbers
  shown, because it indicates an internal inconsistency on the label itself.
- If the two normalized ABV numbers are equal: **match**.
- If they differ by any nonzero amount: **mismatch**, with both values and the
  difference shown. No tolerance band is applied. The agent can overrule; the
  tool does not.
- If either value cannot be parsed as a number: **needs human review**, with the
  raw strings shown, falling back to text comparison as FR-7 already requires.
- Range statements (for example "12 to 14% alc/vol", permitted for wine under
  27 CFR 4.36): if the label states a range and the application states a single
  value, **needs human review**. The prototype does not evaluate range
  semantics.

**Why the regulatory tolerances do not apply.** 27 CFR 5.65 allows "a tolerance
of plus or minus 0.3 percentage points... for actual alcohol content that is
above or below the labeled alcohol content"
(<https://www.ecfr.gov/current/title-27/section-5.65>); 27 CFR 4.36 allows 1
percent for wines over 14 percent ABV and 1.5 percent for wines at 14 percent or
less, "either above or below" the stated percentage
(<https://www.ecfr.gov/current/title-27/section-4.36>); 27 CFR 7.65 permits "a
tolerance of 0.3 percentage points... either above or below the stated alcohol
content, for malt beverages containing 0.5 percent or more alcohol by volume"
(<https://www.ecfr.gov/current/title-27/section-7.65>). All three fetched from
eCFR on 2026-08-20. Every one of those tolerances governs the difference between
the **actual** alcohol content of the liquid and the **labeled** content, which
is a laboratory question. This tool compares two **declared** values: what the
applicant wrote on the label artwork and what the applicant typed into the
application form. Both are the applicant's own statements of the same number.
There is no regulatory basis for allowing them to differ, and Sarah's
description of the check is "ABV is correct? Check," meaning the number on the
form is the number on the label.

**Why this is the conservative choice:** the only failure that harms the process
is a false match, where the tool tells an agent two different numbers agree.
Requiring exact equality makes a false match on this field impossible except
through an OCR misread, and OCR confidence is shown alongside the value. The
cost is false mismatches on OCR errors like `45` read as `46`, which land in
front of an agent with both values visible, which is today's manual check
anyway.

**What would change it:** a compliance agent or Sarah Chen stating that
applications and labels are routinely accepted with small ABV differences. No
source says so. Configurable `TTB_ABV_TOLERANCE` defaults to 0.0 so the
behaviour can change without a code change if that answer arrives.

**Confirmed or falsified by:** a compliance agent or Sarah Chen stating that
applications and labels are routinely accepted with small ABV differences.
**Risk if wrong:** medium. The failure mode is false mismatches, which cost
agent time rather than allowing a bad label through, and `TTB_ABV_TOLERANCE`
changes the behaviour without a code change.

**Traceability:** Source: Sarah Chen interview ("ABV is correct? Check");
27 CFR 5.65, 4.36, 7.65 (fetched 2026-08-20) for why regulatory tolerances are
out of scope; Decision D-5 (numeric comparison);
[cloud_choice_and_abv_assumption.md](cloud_choice_and_abv_assumption.md)
section 2. Marks OQ-4 as closed by assumption A-12.

## A-13
**Net contents are compared numerically only when units match after
normalization.**

Compare numerically only when units match after normalization (`mL`/`ml`/
`milliliters`, `L`/`liters`, `fl oz`/`fl. oz.`). Different units: **needs human
review**, no conversion performed. Standards of fill are not validated.

The reasoning is A-12's: a conversion the tool performs silently is a place a
false match can be manufactured, and `750 mL` against `25.4 fl oz` is a question
an agent can settle in a second with both values in front of them.

**Confirmed or falsified by:** Sarah Chen or a compliance agent stating that
cross-unit net contents are routinely accepted, and whether standards of fill
should be validated.
**Risk if wrong:** low. The failure mode is a review outcome where a match was
possible, which costs agent time only.

**Traceability:** Source: FR-7; Decision D-5;
[cloud_choice_and_abv_assumption.md](cloud_choice_and_abv_assumption.md)
section 2. Marks OQ-5 as closed by assumption A-13.
