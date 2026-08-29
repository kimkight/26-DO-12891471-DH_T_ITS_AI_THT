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
| [A-14](#a-14) | ~~Batch application data arrives as one CSV keyed by image filename~~ **Superseded** by [ADR 0009](adr/0009-batch-cola-documents.md) | FR-8, US-9 | Was medium; it was wrong |
| [A-15](#a-15) | A printer's hyphen across a line break is presentation, not altered warning wording | FR-5, FR-1 | Low |
| [A-16](#a-16) | Three photographs of one label is enough, and no source states a number | FR-1, US-22 | Low |
| [A-17](#a-17) | The COLA form field map, and that three of the five compared values are not items on the form | FR-11, US-23 | Medium |

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
`npm ci`, `eslint`, `prettier --check`, `tsc -b`, and `vite build`. Partly
confirmed already: `frontend/package-lock.json` exists (OQ-3), so npm did
resolve the declared versions into one tree. That does not confirm the build.
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

## A-14
**Status: superseded on 2026-08-28 by
[ADR 0009](adr/0009-batch-cola-documents.md).** A batch submission is label
images plus COLA documents paired by filename stem. There is no CSV. The
assumption is kept here in full, below the line, because the reason it existed
is the reason the replacement is short, and deleting it would leave the batch
contract looking like something that was always obvious.

**What was wrong with it.** Not the column set, and not the keying on filename.
What was wrong is the premise: that a CSV of application data exists anywhere.
Nothing an importer files with TTB produces one. What they file is, per
application, a COLA form plus label images. To use the batch path an agent would
have had to type 300 rows of the data they were trying not to type, which is the
work FR-11 exists to remove. A-14 named exactly what would falsify it, "asking
Sarah Chen or Janet what an importer actually sends today", and the answer
turned out to be available without asking, in the shape of the form FR-11 now
reads.

**What survives it.** The reasoning about identifiers. Filename is still the
only identifier present on both sides of a submission, so the pairing is still
keyed on it; ADR 0009 pairs on the stem rather than the whole name so that an
image and a document can be the same label under different extensions. The
`beverage_type` reasoning survives too, and is now answered rather than assumed:
the document supplies it where it states one, and where it does not the row says
so.

---

*The assumption as originally recorded, 2026-08-24:*

**Batch application data arrives as one CSV keyed by image filename, with the
columns `filename`, `brand_name`, `class_type`, `alcohol_content`,
`net_contents`, and `beverage_type`.**

FR-8 requires batch submission of labels "with their application data" but no
source states the format. For a single label the agent types the values (A-8);
for 300 labels that is not plausible. Sarah Chen names the volume, "200, 300
label applications... at once," and Janet in the Seattle office as the original
requester, but neither is quoted on how the data would arrive.
[Source: Sarah Chen interview]

Two things make a CSV keyed by filename the least invented option available:

- The repository already uses that shape. `samples/expected.csv` keys ground
  truth on image filename for the accuracy tier, so the batch input mirrors a
  convention the test strategy already committed to.
- Filename is the only identifier that exists on both sides of the submission.
  There is no application number in the extracted fields (FR-1), no persistence
  to hold a mapping (D-9), and no authentication to scope one (OOS-2).

`beverage_type` is in the column set because A-12 and A-13 depend on it: the
proof cross-check applies to distilled spirits, and range handling for wine
cites 27 CFR 4.36. Without the beverage class the tool would have to infer which
rule applies, and inference is the failure mode A-12 exists to prevent. That
column is the one part of this assumption that adds a field the agent would not
otherwise supply, so it is the part most likely to be wrong.

Recorded in the FR-8 acceptance criteria in
[03_REQUIREMENTS.md](03_REQUIREMENTS.md), in
[ADR 0006](adr/0006-batch-execution-model.md), and in
[samples/README.md](../samples/README.md).

**Confirmed or falsified by:** asking Sarah Chen or Janet what an importer
actually sends today, or whether COLAs Online exports application data in a
fixed layout. If it does, that layout wins and this assumption is discarded.
**Risk if wrong:** medium. It is one input adapter, and the verification core
does not depend on the format, so the blast radius is a parser and a document.
The cost of being wrong is rework on FR-8 and US-9 rather than a redesign.

*End of the superseded entry. The risk assessment held: it was one input
adapter, and replacing it cost a parser call, a route signature and a document
rather than a redesign.*

## A-15
**A word split across a line break by a printer's hyphen is presentation, and
is rejoined before the government warning is compared. Cardinal orientation is
corrected using Tesseract's orientation and script detection.**

Two assumptions from one piece of evidence, recorded together because they come
from the same photograph and are falsified by the same thing: looking at more
real labels.

### The hyphenation rule

The first real-artwork test, run by the author against the deployed URL on
2026-08-26, submitted a photograph of a commercial wine bottle. The label
carried the full government warning and the engine reported it as a mismatch.
The label sets the statement in a column a few words wide and the setter
hyphenated to fill it, so the artwork reads `AC-` / `CORDING`, `GEN-` / `ERAL`
and `CONSUMP-` / `TION` across three line breaks.

27 CFR 16.21 fixes the wording of the statement. It says nothing about where
the lines break, and 27 CFR 16.22 governs legibility and the bold prefix rather
than line breaking. So a hyphen introduced to fill a column is a typesetting
decision, not a word difference, and reporting it as altered wording reports a
compliant label as defective. `app/warning.py` therefore removes a hyphen that
sits between two word characters and is followed by whitespace, before the body
is compared.

**What keeps this from weakening FR-5.** It is applied to the label side only,
never to the constant quoted from the regulation. It is applied after the
`GOVERNMENT WARNING:` prefix has been taken off, so the capitalization check
(FR-6) reads exactly the characters it read before and a title-case prefix
still fails. And it is safe on this text specifically because 27 CFR 16.21
contains no hyphen at all: every hyphen inside a located statement is either a
line-break hyphen, which this removes correctly, or an inserted word
difference, which FR-5 requires to be reported as a mismatch either way. A dash
used as punctuation carries a space on both sides and is left alone.

The same join is applied to the stopping rule in `app/parse.py` that decides
how many lines the statement occupies. A hyphenated column carries two extra
characters per split word, so measuring the printed text against the
regulation's length stopped collecting early and truncated the statement, which
would have produced a mismatch for a reason unrelated to the wording.

### The orientation rule

The same photograph was taken sideways, and phone photographs also record the
camera's orientation in EXIF tag 0x0112 rather than turning the pixels, which
`cv2.imdecode` ignores. Both are corrected: the EXIF transform is applied
through Pillow before OpenCV sees a pixel, and a cardinal quarter-turn is
detected with Tesseract's orientation and script detection (OSD).

**OSD rather than reading the image four times and keeping the highest mean
word confidence.** Both were measured over the twelve-label sample set at all
four cardinal rotations, forty-eight cases, on 2026-08-26 on a session runner:

| Strategy | Correct | Cost |
| --- | --- | --- |
| Tesseract OSD | 46 of 48 | about 760 ms per image |
| Highest mean word confidence of four rotations | 7 of 48 | about 1,200 ms per image |

The second one does not fail for want of tuning. Tesseract's own layout
analysis already detects and corrects text turned a quarter-turn clockwise, so
an upright image and the same image turned clockwise produce identical output:
on the sample label, 62 words and a mean confidence of 95.4 either way. A score
that is equal on the two cases it has to separate cannot separate them at any
threshold. That is asserted in
`backend/tests/test_ocr.py::TestWhyOrientationUsesOsd` rather than only written
here, so a future Tesseract release that changes the behaviour fails a test
instead of leaving a stale claim in a document.

Both OSD misreads were on the sample carrying the least text, and both reported
an orientation confidence below 1.0 where every correct answer reported above
11. The confidence is carried out to the response rather than used to override
the answer, because there is nothing better to fall back to.

**What is deliberately not attempted:** perspective and cylinder dewarping. The
label wraps a round bottle, so no single photograph shows it flat and the far
edges compress. That is SG-1, which Jenny Park raised and immediately qualified
as "maybe out of scope for a prototype," and it is the ADR 0003 risk that
Tesseract reads real photographs worse than a cloud service would. Correcting
it needs either a cylindrical unwrap with an estimated radius or a second
photograph of the same label; the second is what
[ADR 0007](adr/0007-multi-photo-single-label.md) does instead. Recorded here so
that the orientation fix is not mistaken for a general imperfect-image fix.

### What v1.0.1 corrected in the orientation rule

The 2026-08-26 measurement above was taken entirely on artwork rendered by
`samples/labelmaker.py`, and it recorded which strategy to use without recording
which image to ask. Both were asked of the adaptively thresholded image, and on
rendered type that is invisible. The 2026-08-28 Ketel One submission made it
visible. Re-measured on 2026-08-29 over the same twelve labels degraded into a
photograph-like fixture, at all four cardinal rotations:

| Image OSD is asked about | Correct, rendered artwork | Correct, photograph-like |
| --- | --- | --- |
| Adaptively thresholded (v1.0.0) | 46 of 48 | 0 of 48 |
| Upright grayscale (v1.0.1) | 45 of 48 | 44 of 48 |

The choice of OSD over best-of-four stands, and the reasoning above is
unchanged. What changed is that OSD is asked about the grayscale. The wider
lesson is the one recorded here rather than only in the changelog: a measurement
taken on rendered artwork does not transfer to photographs, and every figure in
this assumption was taken that way.

Two further things follow, and both are in the code rather than only written
down. The quarter-turn check runs whether or not an EXIF tag was applied, so a
tag that lies about its own pixels is caught by the same net; the EXIF transform
itself was correct at v1.0.0 and is now asserted against all eight orientation
values rather than one. And preprocessing is no longer trusted to be an
improvement: both the preprocessed and the plain upright grayscale are read, and
the higher-scoring result is kept, with the choice reported in `read_path`.

**Confirmed or falsified by:** running the engine over a set of real
photographed labels rather than one. One bottle establishes that hyphenated
columns occur; it does not establish how they are typically set, whether other
label elements are hyphenated the same way, or how often OSD is wrong on real
artwork. What would falsify the hyphenation rule specifically is a real label
whose warning contains a hyphen that belongs to the word.
**Risk if wrong:** low for the hyphenation rule. It can only turn a mismatch
into a match on text that is otherwise word-for-word identical to the
regulation, and the case it covers was observed on a commercial label. Low to
medium for the orientation rule: a wrong turn produces unreadable text and
fields reported as not found (FR-1), which is a visible failure rather than a
false match, and the response says what was turned and how confidently.

**Traceability:** Source: the author's first real-artwork test against the
deployed URL, 2026-08-26; 27 CFR 16.21 and 16.22 (fetched 2026-08-20);
[02_PROJECT_SCOPE.md](02_PROJECT_SCOPE.md) SG-1;
[ADR 0003](adr/0003-local-ocr-default-bedrock-optional.md). Affects FR-1 and
FR-5. Tested by `backend/tests/test_ocr.py::TestExifOrientation`,
`TestCardinalOrientation`, `TestWhyOrientationUsesOsd`,
`TestEveryExifOrientationReadsItsLabel`, `TestATagThatLiesAboutItsPixels`,
`TestPreprocessingHasToEarnItsRead`, `TestWhyOrientationIsJudgedOnTheGrayscale`,
`backend/tests/test_warning.py::TestHyphenationAcrossLineBreaks`,
`backend/tests/test_verify_integration.py::TestASidewaysPhotograph`,
`TestAHyphenatedWarningColumn`, `TestTheKetelOneHotfix`; UAT rows 23, 24, 25 and
54 to 57. Opens OQ-20. Revised on 2026-08-29 by the v1.0.1 hotfix; see the
subsection above.

## A-16
**Three photographs of one label is the cap, and every photograph in a
submission is of the same label.**

[ADR 0007](adr/0007-multi-photo-single-label.md) accepts up to three
photographs of one label because a label wraps a round bottle and no single
photograph shows all of it flat. Two things in that are assumed.

**The number.** No source states how many photographs an agent would take, or
whether they take more than one today. Sarah Chen describes an agent who "pulls
up an application, looks at the label artwork", singular.
[Source: Sarah Chen interview] Three is chosen because it is what the geometry
asks for rather than what a stakeholder asked for: a front, a back, and the
seam between them. It is `TTB_MAX_LABEL_PHOTOS`, so it changes without a code
change, and a submission over it is refused with the limit named (NFR-7).

**That the photographs are of the same label.** The API cannot tell. Nothing
compares one photograph against another to confirm they show one bottle, and
three photographs of three different labels would be merged into one result as
readily as three of one. That is not a check the prototype can make honestly:
it would mean deciding that two photographs are "the same label" from their
text, which is precisely the judgement the tool defers to an agent everywhere
else (FR-3, Dave Morrison's "you need judgment"). What is done instead is
disclosure: the response says which photograph each field was read from, so a
submission that mixed two labels produces a result whose provenance is visible
rather than one that silently looks coherent.

**Confirmed or falsified by:** asking Sarah Chen or a compliance agent how they
photograph a bottle today, and whether an application already arrives with
several images. If applications carry a fixed number of views, that number wins
and this assumption is discarded.
**Risk if wrong:** low. A cap that is too low is one environment variable. A cap
that is too high costs latency on a path already measured against NFR-1. The
same-label assumption's failure mode is an agent's own mistake, made visible by
the per-field attribution rather than hidden by it.

**Traceability:** Source: the author's first real-artwork test against the
deployed URL, 2026-08-26; 27 CFR 16.21 (the warning may be on a back or side
label); Jenny Park interview (SG-1). Recorded in
[ADR 0007](adr/0007-multi-photo-single-label.md) and in the FR-1 acceptance
criteria. Tested by `backend/tests/test_multi_photo.py::TestThePhotographCap`
and `frontend/src/__tests__/multiPhoto.test.tsx`; UAT rows 26, 27, 28.

## A-17
**The COLA document field map, and the fact that three of the five values this
tool compares are not items on the form at all.**

[ADR 0008](adr/0008-cola-form-as-application-input.md) accepts an uploaded copy
of the label application as an alternative to typing the same values. The map
below was read off the blank form, downloaded once during development from
`https://www.ttb.gov/system/files/images/pdfs/forms/f510031.pdf`. **Edition:
TTB F 5100.31 (04/2023), OMB No. 1513-0020.** It was not recalled and it was not
inferred from the requirement text. Nothing is fetched at runtime.

**The map, item by item.**

| This tool's field | Source on the form | AcroForm field name on the downloaded PDF |
| --- | --- | --- |
| Brand name | Item 6, "BRAND NAME (Required)" | `6. BRAND NAME (Required)` |
| Fanciful name (carried, not compared) | Item 7, "FANCIFUL NAME (If any)" | `7. FANCIFUL NAME (If any)` |
| Beverage type | Item 5, "TYPE OF PRODUCT (Required)": WINE, DISTILLED SPIRITS, MALT BEVERAGES | `Check Box22`, one radio group, export values `Wine`, `Spirits`, `Malt` |
| Class or type designation | **Not an item.** On the labels affixed to the application; on a Public COLA Registry printout as `CLASS/TYPE`, or, as the author observed on 2026-08-28, as `Class/Type Description` | none |
| Class or type code (recorded, not compared) | **Not an item.** On a Registry printout, printed before the description, either joined to it by a dash or on its own `Class/Type Code` line | none |
| Alcohol content | **Not an item.** On the labels affixed to the application; on a Registry printout as `ALCOHOL CONTENT` | none |
| Net contents | Item 15 **only** when blown, branded or embossed on the container and not on the labels; otherwise on the labels, and on a Registry printout as `NET CONTENTS` | `15.  SHOW ANY INFORMATION THAT IS BLOWN, BRANDED, OR EMBOSSED ON THE CONTAINER (e.g., net contents) ONLY IF IT DOES NOT APPEAR ON THE LABELS` |

Related items exist and are deliberately not read: item 1 (representative ID),
item 2 (plant registry, basic permit or brewer's notice number), item 3 (source
of product), item 4 (serial number), item 8 and 8a (applicant name and
addresses), items 9 through 13, item 14 (type of application), items 16 through
18 (date, signature, printed name) and items 19 and 20 (the TTB certificate
block). Several carry personal data or permit numbers, none is compared against
a label, and reading them would put values into a response that has no use for
them (NFR-6, OOS-6).

**What is assumed rather than read.**

1. **That item 15 must not be read as a net contents statement.** The box holds
   whatever is blown, branded or embossed on the container; net contents is the
   form's example, not the box's meaning. Taking its contents as a net contents
   statement would report a guess as a reading. The parser leaves it and says
   the value has to be entered.
2. **That a Registry printout labels its rows `BRAND NAME`, `FANCIFUL NAME`,
   `CLASS/TYPE`, `ALCOHOL CONTENT` and `NET CONTENTS`.** This is the weakest
   link in the map, and part of it has since been corrected by evidence. The
   blank form was downloaded and read; a Registry detail page was not, because
   the only real ones are real applicants' records and the no-personal-data rule
   forbids committing one as a fixture. The parser matches those captions
   case-insensitively, tolerantly, and at the start of a line. Tracked as OQ-22.

   **What the evidence corrected, 2026-08-28.** A printout the author put
   through the deployed prototype captions the class or type
   `Class/Type Description:`, and prints the code on a separate
   `Class/Type Code:` line rather than joined to the description by a dash. The
   parser's tolerant caption matching made that worse rather than safer: it
   matched the `Class/Type` prefix and kept `Description:` as the head of the
   value, so the class or type compared against the label was
   `Description: Kentucky Straight Bourbon Whiskey`. The reader now removes a
   residual caption word left at the front of a value, and reads a separate code
   line. What this shows about the assumption is that a caption which *partly*
   matches is the dangerous case, not the one that does not match at all; the
   risk paragraph below is corrected accordingly.
3. **That a class or type printed as `141 - BOURBON WHISKY` is a code followed
   by a description.** The description is what is compared; the code is
   recorded and reported and compared against nothing.
4. **That a document naming exactly one of the three product types is stating
   it.** A form that names all three is offering a choice and has said nothing,
   which is what an unticked checkbox looks like in a text layer.
5. **That the edition matters and other editions exist.** The map is verified
   against 04/2023 only. An earlier edition may number its items differently,
   and the form itself says previous editions are obsolete without saying what
   they contained. Tracked as OQ-22.

**Confirmed or falsified by:** running the parser against a real filed
application and a real Registry printout, which the author could not do without
using an applicant's record. Ask Sarah Chen or Jenny Park which of the two
documents an agent actually has in front of them, and on which editions.

**Risk if wrong:** medium. A caption that does not match at all means the value
reads as not found and the agent types it, which is where they started. A
caption that matches *in part* is the worse case, and it is not hypothetical:
2026-08-28 produced a prefilled value carrying a caption word, which an agent
who accepted the prefill would have compared against the label. In both cases
every parsed value is shown for confirmation in an editable field before the
check runs (ADR 0008), so the agent can see and correct it; that is the control,
and it is a control that depends on the agent reading what was prefilled.
