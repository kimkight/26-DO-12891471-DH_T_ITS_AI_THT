# Requirements

Every requirement carries a priority (Must, Should, Could), a source tag, and
acceptance criteria. Nothing here is derived from anything other than the
assignment text, the recorded decisions D-1 through D-12, or regulation fetched
and quoted from eCFR.

Requirements are traced to stories and tests in
[TRACEABILITY_MATRIX.md](TRACEABILITY_MATRIX.md).

## 1. Reference: the Government Warning statement

Quoted verbatim from 27 CFR 16.21, retrieved from eCFR on 2026-08-20.
Source URL: https://www.ecfr.gov/current/title-27/section-16.21
Section last amended 2016-12-31 per the eCFR versioner API.

> § 16.21 Mandatory label information.
>
> There shall be stated on the brand label or separate front label, or on a back
> or side label, separate and apart from all other information, the following
> statement:
>
> GOVERNMENT WARNING: (1) According to the Surgeon General, women should not
> drink alcoholic beverages during pregnancy because of the risk of birth
> defects. (2) Consumption of alcoholic beverages impairs your ability to drive
> a car or operate machinery, and may cause health problems.

The typography rules are in 27 CFR 16.22, retrieved from the same source on the
same date. Source URL: https://www.ecfr.gov/current/title-27/section-16.22

> (a) Legibility. (1) All labels shall be so designed that the statement
> required by § 16.21 is readily legible under ordinary conditions, and such
> statement shall be on a contrasting background.
>
> (2) The first two words of the statement required by § 16.21, i.e.,
> "GOVERNMENT WARNING," shall appear in capital letters and in bold type. The
> remainder of the warning statement may not appear in bold type.

This confirms Jenny Park's account: "the 'GOVERNMENT WARNING:' part has to be in
all caps and bold." [Source: Jenny Park interview] The prototype checks
capitalization and does not check boldness; see FR-6 and OOS-4 in
[02_PROJECT_SCOPE.md](02_PROJECT_SCOPE.md).

## 2. Context: TTB label elements

The assignment lists these as common required elements, with the caveat that
"The exact requirements vary by beverage type (beer, wine, distilled spirits)."
[Source: Technical Requirements, Additional Context]

| Element | Extracted by the prototype? |
| --- | --- |
| Brand name | Yes, FR-1 |
| Class/type designation | Yes, FR-1 |
| Alcohol content (with some exceptions for certain wine/beer) | Yes, FR-1 |
| Net contents | Yes, FR-1 |
| Name and address of bottler/producer | No, OOS-6 |
| Country of origin for imports | No, OOS-6 |
| Government Health Warning Statement (mandatory on all alcohol beverages) | Yes, FR-1 and FR-5 |

The prototype encodes no beverage-type-specific rules, because the assignment
supplies none and inventing them is prohibited by the ground rules. See OOS-7.

## 3. Functional requirements

### FR-1 Verification by search: is the declared value on the label?

**Priority:** Must
**Source:** Technical Requirements, Sample Label section; author's session on the
deployed build, 2026-08-30

Read uploaded label artwork, and for each value the application declares, report
whether that value appears on the label and where. One label may be submitted as
more than one photograph of itself, because a label wraps a round bottle and no
single photograph shows all of it flat. See
[ADR 0007](adr/0007-multi-photo-single-label.md).

**This requirement was inverted on 2026-08-31, and the inversion is the point of
it.** It used to require extracting a value from the label and then comparing two
strings. Locating a value is a ranking over candidates, and every field-level
defect reported against a deployed build has been a failure of that ranking
rather than of the comparison or of the reading: the brand name reported as the
producer's tax identifier, and then the brand name and the class or type
designation both reported as "not found" on a document whose label text contained
`DEL MAGUEY` and `MEZCAL` exactly. The application already declares the answer, so
the tool searches for it. See [ADR 0015](adr/0015-verify-by-search.md) for the
measurements and the alternatives rejected.

**What a hit establishes, and what it does not.** A hit establishes that the
declared value appears on the label. It does **not** establish that it appears as
the brand, in the type size 27 CFR requires, or on the panel it is required on.
Type size and prominence are OOS-5 and are not checked at all. That limit is
stated on the screen, once, above the rows, and it is a weaker claim than the old
design implied and a far stronger one than "not found" about text the tool has
read.

**Acceptance criteria**
- Given the sample distilled spirits label, when it is submitted, then the
  system returns an outcome and its evidence for each of the five fields.
- Given a declared value that appears on the label, then the outcome is a match
  and the result names the column and the block it was found in, and shows the
  label's own printing of it.
- Given a declared value that does not appear on the label, then the field is
  reported as not found rather than reported as empty or silently omitted, and
  the closest text on the label is reported with its score so the call can be
  judged.
- Given a declared value that appears only inside a longer word, then it is not
  reported as a match: the search matches whole words.
- Given a class or type designation carrying a registry code the label does not
  print, for example `MEZCAL FB`, then the full value is searched for first and
  the code is left off only if that fails, and the result says the code was left
  off.
- Given a field the application did not supply, then there is nothing to search
  for and the existing extractor runs as the fallback, reporting not found rather
  than a guess where its heuristic cannot identify a value.
- Given a value on the screen, then the result states that a hit shows the value
  is on the label and not that it is on the label as the brand, in the required
  type size, or on the required panel.
- Extraction adds no outbound network call on the default path (see NFR-6).
- Given a photograph taken sideways, or one whose orientation is recorded only
  in its EXIF tag, then it is turned upright before it is read, and the result
  states what was turned and on what confidence. `(Assumption)` A-15.
- Given a warning set in a narrow column with printer's hyphens across line
  breaks, then the split words are rejoined before the body is compared, so the
  line breaking does not read as altered wording. `(Assumption)` A-15.
- Given between one and `TTB_MAX_LABEL_PHOTOS` photographs of one label, then
  each is read independently and a field is reported as found if any of them
  shows it, and the result names which photograph each value was read from.
  `(Assumption)` A-16.
- Given two photographs that both show one field, then the reading from the
  photograph that read it best is reported, judged by the same signal the field
  was located by. See [ADR 0007](adr/0007-multi-photo-single-label.md).
- Given one unreadable photograph among readable ones, then the readable ones
  still produce a result and the unreadable one is reported rather than hidden.
- Given more photographs than the configured limit, then the request is rejected
  with a message naming the limit, before any photograph is processed.
- Given a submission in which no photograph could be read, then no field reports
  a match and the message says that none of them could be read (see FR-9).

### FR-2 Comparison against application data

**Priority:** Must
**Source:** Sarah Chen interview; Technical Requirements

Accept application data for the same five fields and check it against the label.

**The application side is the question, not the answer** (FR-1,
[ADR 0015](adr/0015-verify-by-search.md)). What the applicant declared is what the
label is searched for; the label no longer has to volunteer a value first. That
makes an application value load-bearing in a way it was not: a field left blank is
a field with nothing to search for, and it falls back to the extractor and to the
not-compared outcome below.

**How the data arrives is FR-11's question, not this one.** The API takes the
five values and does not care whether they were read off an uploaded COLA
document or typed by the agent. On the interface the document is the primary
input and the typed fields sit behind a disclosure (US-24); on the batch path
nothing is typed at all (ADR 0009). This requirement is unchanged by either: it
is about what happens to the five values once they are here.

**Acceptance criteria**
- Given a label and its application data, when verification runs, then each of
  the five fields carries exactly one outcome.
- Given a declared value for a field, then that value is what the label is
  searched for, and the result reports whether it was found (FR-1).
- Given application data missing a field, then that field is reported as not
  compared, and this is distinguished from a mismatch. A field the agent never
  opened is such a field, so a collapsed disclosure is a legitimate submission
  rather than an incomplete one.

Sarah's description of the manual process this replaces: "Brand name matches?
Check. ABV is correct? Check. Government warning is there? Check."
[Source: Sarah Chen interview]

### FR-3 Three-outcome per-field result

**Priority:** Must
**Source:** Decision D-5; Dave Morrison interview

Each field returns one of: **match**, **needs human review**, or **mismatch**.

**The thresholds are unchanged by the FR-1 inversion, and that is deliberate.**
The score a search produces is a similarity between a declared value and a run of
label text, which is the same kind of quantity this requirement has always
classified. A second scale for it would leave two definitions of "close". See
[ADR 0015](adr/0015-verify-by-search.md), decision 1.

**Acceptance criteria**
- Given a field whose normalized similarity is at or above the match threshold,
  then the outcome is match.
- Given a field whose similarity falls between the review and match thresholds,
  then the outcome is needs human review.
- Given a field below the review threshold, then the outcome is mismatch.
- The result includes what was read off the label, the application value, and the
  score, so that an agent can judge the call rather than trust it. Where the
  field was decided by searching, what was read off the label is the label's own
  printing of the matched run, and the result also names where on the sheet it
  was found (FR-1, FR-10).
- Given a declared value not found on the label, then the closest text the label
  does carry is reported with its score, rather than the row saying only that
  nothing was found.

Dave's requirement in his own words: "Technically a mismatch? Sure. But it's
obviously the same thing. You need judgment." The middle outcome is how the tool
defers to that judgment instead of overriding it.
[Source: Dave Morrison interview]

### FR-4 Tolerance for case and punctuation differences

**Priority:** Must
**Source:** Dave Morrison interview; Decision D-5

Both sides are normalized for case, surrounding whitespace, and punctuation
before scoring, so that presentational differences do not read as substantive
ones. This governs the search FR-1 requires as well as any comparison of two
strings: the same `normalize_text` runs on the declared value and on every word
of the label reading.

**Acceptance criteria**
- Given label `STONE'S THROW` and application `Stone's Throw`, then the value is
  found on the label and the outcome is match or needs human review, and never
  mismatch.
- Given a match found this way, then the result shows the label's own casing
  beside the declared value, so an agent can see that the difference is
  presentational rather than being told that it is.
- Given a straight apostrophe against a typographic apostrophe in otherwise
  identical text, then the outcome is match.
- Given punctuation the reading invented, for example a comma inside a brand
  name, then the outcome is still match.
- Given two genuinely different brand names, then normalization does not cause
  them to be reported as a match.

This requirement applies to FR-1 fields other than the government warning. The
warning is governed by FR-5 and FR-6, which are deliberately stricter.

### FR-5 Government warning compared for exact text

**Priority:** Must
**Source:** Jenny Park interview; Decision D-5; 27 CFR 16.21

The government warning is compared for exact text after whitespace and letter
case normalization, against the text quoted in section 1.

**Unchanged by the FR-1 inversion of 2026-08-31.** This requirement already
searches the label for a known string; the string is fixed by 27 CFR 16.21 rather
than declared by the applicant, and the comparison is exact rather than fuzzy by
requirement. Nothing in [ADR 0015](adr/0015-verify-by-search.md) touches it, the
warning row carries no similarity score, and the near-miss routing below stands
exactly as it was.

**Acceptance criteria**
- Given a warning matching 27 CFR 16.21 exactly except for line breaks, runs of
  spaces and letter case, then the outcome is match.
- Given a warning with altered, added, or omitted words, then the outcome is
  mismatch, not needs human review, in whatever case the label sets it.
- Given no warning found on the label, then the outcome is mismatch and the
  result says the statement was not found.
- Fuzzy tolerance under FR-4 is not applied to the warning body.
- **Given a warning differing from 27 CFR 16.21 by at most
  `TTB_WARNING_NEAR_MISS_EDITS` single characters, then the outcome is needs
  human review, the exact character-level difference is shown, and the result
  states that this is not a match.** It is never a pass.
- Given a warning whose prefix fails the FR-6 capitalization check, then the
  outcome is mismatch whatever the size of any difference in the body.
- Given any difference at all, then the character-level difference is reported,
  because it is what an agent needs in order to judge either outcome.

**The comparison is exact, and a near miss is routed to a person rather than
auto-passed. This is not a fuzzy match, and the distinction has to be read as
load-bearing rather than as a hedge.** A fuzzy match would let a label through
on a similarity score. Nothing here lets anything through: a near miss is one of
the two **failing** outcomes, and what separates it from a mismatch is which
sentence the agent reads and whether they are handed the difference to look at.
The comparison that decides a match is unchanged and still requires identical
text after whitespace and case normalization.

**Why the distinction matters enough to be in the requirement.** The author's
own COLA artwork, read on 2026-08-29, OCRs the statement with exactly one
character wrong: `MPAIRS` for `IMPAIRS`. "The statement text does not match
27 CFR 16.21 word for word" is equally true of that and of a missing clause, and
the difference between those two is the whole of the agent's decision. Reporting
the first as a flat mismatch tells an agent their label is defective when the
truth is that the scan is imperfect, which is the tool overstating what it knows
in the direction OOS-8 and FR-6 exist to prevent. Loosening the comparison
instead would be the same error in the other direction. The threshold, the
reasoning behind the number, and the alternatives rejected are in
[ADR 0012](adr/0012-warning-near-miss.md).

**Why letter case is normalized alongside whitespace, added 2026-08-31.**
27 CFR 16.21 fixes the *wording* of the statement. How it is set is 27 CFR
16.22(a)(2), and the only part of that this prototype checks is the prefix,
which FR-6 checks separately and still case-sensitively. Filed labels routinely
print the whole statement in capitals, and the author's own mezcal artwork is
one of them: once the panel segmentation of v1.1.0 stopped splicing a
neighbouring panel through it, the statement read as 283 characters in exactly
the order the regulation sets them, and the exact comparison still failed on 209
differences of which every single one was a capital letter. Reporting that as
altered wording tells an agent their label is defective about the one thing it
is demonstrably correct about, which is the same overstatement the near-miss
routing above exists to prevent.

Case is therefore presentational, exactly as line breaks and runs of spaces are,
and nothing else moves with it. An altered, added or omitted word fails in
either case; `backend/tests/test_warning.py` asserts that in both. The
difference an agent is shown is still the label's own text, because the fold is
length-preserving and the diff segments are sliced from what was printed.

Jenny's constraint: "It has to be exact. Like, word-for-word." She also notes
the failure modes she sees in practice: "people try to get creative with the
warning all the time. Smaller font, different wording, burying it in tiny text."
[Source: Jenny Park interview] Of those, this prototype detects different
wording only; font size and prominence are OOS-5. Nothing in the near-miss
routing weakens the first of those: a creative rewording is a difference of many
characters, and it is still a mismatch.

### FR-6 Government warning capitalization check

**Priority:** Must
**Source:** Jenny Park interview; Decision D-5; 27 CFR 16.22(a)(2)

Check separately that the `GOVERNMENT WARNING:` prefix appears in upper case.

**Acceptance criteria**
- Given a label reading `GOVERNMENT WARNING:`, then the capitalization check
  passes.
- Given a label reading `Government Warning:` in title case, then the
  capitalization check fails and the field does not report a match.
- The capitalization result is reported separately from the body text result, so
  an agent can see which rule failed.
- The result must not state or imply that bold type was verified. See OOS-4.

Jenny's case: "I caught one last month where they used 'Government Warning' in
title case instead of all caps. Rejected." [Source: Jenny Park interview]

### FR-7 Numeric comparison for numeric fields

**Priority:** Must
**Source:** Decision D-5

Alcohol content and net contents are compared numerically rather than as
strings.

**Acceptance criteria**
- Given label `45% Alc./Vol. (90 Proof)` and application `45`, then the alcohol
  content outcome is match.
- Given `45%` against `45.0%`, then the outcome is match.
- Given `750 mL` against `750ml`, then the net contents outcome is match.
- Given a numeric field that cannot be parsed as a number, then the system falls
  back to text comparison and says so, rather than reporting a false mismatch.

**Locating the alcohol content on the label.** A percent sign is not by itself
an alcohol content. A candidate counts only where the OCR line carrying the
number also carries an alcohol marker: `ALC`, `ALC.`, `VOL`, `VOLUME`, `ABV`,
`ALCOHOL` or `PROOF`, matched case-insensitively.

- Given a label whose only percent appears in marketing copy, for example
  "reduce our environmental impact by 7%", then the alcohol content is reported
  as not found rather than as `7%`.
- Given `12.5% ALC. BY VOL.`, `ALCOHOL 45% BY VOLUME`, `ABV 45%` or `90 PROOF`,
  then the alcohol content is extracted.
- Given OCR noise in the words around an intact marker, for example
  `12.5% AlC. 8Y VOL.`, then the line is still accepted; the marker has to
  survive OCR, the words around it do not.
- Given a marker on a line with no number, for example an `ALC./VOL.` that OCR
  split away from its figure, then the field is reported as not found rather
  than reported as `ALC./VOL.`.

This was written after the fact. The deployed prototype reported `7%` for a real
bottle on 2026-08-27, read from the back label's environmental copy, because any
percent token qualified. The residual risk is a line that genuinely carries both
an unrelated number and a marker word; it is narrower than the risk it replaces
and it is not claimed to be zero.

**Alcohol content (Assumption A-12).** The two declared values must be
numerically identical. The regulatory tolerances in 27 CFR 5.65, 4.36, and 7.65
govern actual against labeled alcohol content, which is a laboratory question,
and do not apply to a comparison of two values the applicant declared.

- Both values are normalized before comparison: "%", "Alc./Vol.", "ABV",
  "alc. by vol.", whitespace, and trailing zeros are stripped, so
  `45% Alc./Vol.`, `45.0%`, and `45` are the same number.
- Given a label that also states proof, then proof is cross-checked against
  2 x ABV (27 CFR 5.65 defines proof this way for spirits). Given a proof value
  that does not equal twice the ABV, then the outcome is needs human review with
  both numbers shown, because it indicates an internal inconsistency on the
  label itself.
- Given two normalized ABV numbers that are equal, then the outcome is match.
- Given normalized ABV numbers that differ by any nonzero amount, then the
  outcome is mismatch, with both values and the difference shown. No tolerance
  band is applied; `TTB_ABV_TOLERANCE` defaults to `0.0`.
- Given an ABV value on either side that cannot be parsed as a number, then the
  outcome is needs human review, with the raw strings shown, falling back to
  text comparison as above.
- Given a label stating a range (for example "12 to 14% alc/vol", permitted for
  wine under 27 CFR 4.36) and an application stating a single value, then the
  outcome is needs human review. The prototype does not evaluate range
  semantics.

**Net contents (Assumption A-13).** Values are compared numerically only when
units match after normalization (`mL`/`ml`/`milliliters`, `L`/`liters`,
`fl oz`/`fl. oz.`).

- Given two values in matching units, then they are compared numerically.
- Given two values in different units, for example `750 mL` against
  `25.4 fl oz`, then the outcome is needs human review and no conversion is
  performed.
- Standards of fill are not validated.

OQ-4 and OQ-5 are closed by assumptions A-12 and A-13 in
[ASSUMPTIONS.md](ASSUMPTIONS.md); the reasoning and the eCFR citations are in
[cloud_choice_and_abv_assumption.md](cloud_choice_and_abv_assumption.md)
section 2.

### FR-8 Batch verification

**Priority:** Must
**Source:** Sarah Chen interview

Accept multiple labels with their application data in a single submission and
return per-label, per-field results.

**Acceptance criteria**
- Given a batch of labels with application data, when it is submitted, then the
  response contains a result set for every label in the batch.
- Given one unreadable image in a batch, then that label reports an error and
  every other label still returns results.
- Given a batch exceeding the configured file-count limit, then the request is
  rejected with a message naming the limit, before any file is processed.
- The result identifies which label each result belongs to.
- Given a batch submission, then it is one multipart request to
  `POST /api/verify-batch` carrying the label images plus one COLA document for
  each, and results stream back as newline-delimited JSON so progress is visible
  while the batch runs. See [ADR 0006](adr/0006-batch-execution-model.md) for
  the stream and [ADR 0009](adr/0009-batch-cola-documents.md) for what a batch
  is made of.
- Given an image whose stem matches no submitted document, or a document whose
  stem matches no submitted image, then that item reports an error on its own
  result line and the rest of the batch still returns results.
- Given a document that cannot be read, then that label reports an error naming
  the document, no field reports a match for it, and the rest of the batch still
  returns results.

**Batch submission contract.** [ADR 0009](adr/0009-batch-cola-documents.md).
Repeated `images` parts and repeated `application_documents` parts in one
request, **paired by filename stem**: `0001-stones-throw.png` pairs with
`0001-stones-throw.pdf`. The stem is the filename with its final extension
removed, compared without regard to case; only the final extension is removed,
so `0001-stones-throw.front.png` pairs with `0001-stones-throw.front.pdf`.

Each document is read by the FR-11 parser, and what it says is the application
side for that label. Every value on this path is parsed rather than typed, so
each row's result carries the parsed block and says per field whether the
document supplied the value or did not carry it. A value the document does not
carry is not compared, per FR-2, rather than guessed.

The beverage type for a row comes from its document, and where the document does
not state it the row says so. No comparison currently reads it: A-12's proof
cross-check keys off a proof statement the label carries and A-13's range
handling keys off a range in the value, so an unstated beverage type costs the
comparison nothing. It is carried because A-12 and A-13 name it as the class
that would decide which rule applies if a rule ever needed deciding.

**This replaces a CSV of application data.** `(Superseded)` A-14 assumed the
batch arrived as one CSV keyed by image filename, and recorded that no source
stated that format. Nothing an importer files with TTB produces such a file:
what they file is, per application, a COLA form plus label images, and FR-11 can
now read that form. The CSV path is removed rather than kept alongside; the
reasoning, including the alternatives rejected, is in
[ADR 0009](adr/0009-batch-cola-documents.md).

Sarah's case: "we get these big importers who dump 200, 300 label applications
on us at once. Right now we literally have to process them one at a time."
[Source: Sarah Chen interview] The default configured batch limit is 300 labels,
which is the top of the range she names, and it is enforced on the images and on
the documents alike, before anything is processed. `(Assumption)` A-1

**One photograph per label, and that is a stated limit rather than an oversight.**
FR-1 accepts up to `TTB_MAX_LABEL_PHOTOS` photographs of one label on the
single-label path ([ADR 0007](adr/0007-multi-photo-single-label.md)). The batch
path does not: a stem pairing several images to one document would need a rule
for a group only partly readable and an answer for what a per-row error means
when one photograph of three failed. None of that is difficult and none of it is
asked for by any source, so it is not invented here. Two images on one stem are
an error, not a multi-photograph label. An agent with a bulk submission of round
bottles has to check those labels one at a time on the single-label tab. The
limitation is asserted in
`backend/tests/test_multi_photo.py::TestTheBatchPathIsUnaffected` and
`backend/tests/test_batch.py::TestPairing` so it cannot change without being
noticed, and it is recorded in ADR 0007 under "Deliberately out of scope this
session".

### FR-9 Error handling for unreadable images

**Priority:** Must
**Source:** Jenny Park interview; Evaluation Criteria

An image that cannot be processed returns a clear message naming the problem.

**Acceptance criteria**
- Given a corrupt or undecodable file, then the response says the image could
  not be read and no field reports a match.
- Given an image from which no text is extracted, then the response distinguishes
  "no text found" from "fields did not match."
- Given a file whose type is not an allowed image MIME type, then it is rejected
  before decoding, with a message naming the accepted types.
- Given a file larger than the configured size limit, then it is rejected before
  reading, with a message naming the limit.
- Given a single-label submission in which no photograph could be read, then the
  message says that none of them could be read, which is distinct from one
  photograph being unreadable, and no field reports a match
  ([ADR 0007](adr/0007-multi-photo-single-label.md)).
- No error path returns a match outcome for any field.

Today's fallback behaviour sets the bar: "Right now if an agent can't read the
label they just reject it and ask for a better image." [Source: Jenny Park interview]

### FR-10 Result presentation

**Priority:** Must
**Source:** Sarah Chen interview; Jenny Park interview

Present per-field outcomes so an agent can act without re-reading the label.

**Acceptance criteria**
- Each field row shows the field name, the value found on the label, the value
  from the application, and the outcome.
- The three outcomes are distinguishable without relying on colour alone
  (see NFR-5).
- Fields needing human review are visually distinct from both matches and
  mismatches, because they are the ones requiring an agent's attention.

This replaces Jenny's "printed checklist on my desk that I go through for every
label." [Source: Jenny Park interview]

### FR-11 The label application as the input, with typing as the fallback

**Priority:** Should
**Source:** The author's own use of the deployed prototype, 2026-08-27:
"Why do I have to enter in all this information?"

Accept an uploaded copy of the applicant's label application, TTB Form 5100.31,
or of the Public COLA Registry detail page for an application, as **the** way
the application values arrive. Read it locally and offer what it says for the
agent's confirmation. Typing the same values stays available and is the
fallback rather than the default. See
[ADR 0008](adr/0008-cola-form-as-application-input.md) and assumption A-17.

**Which one is the default is a requirement, not a layout preference.** Written
first as "instead of typed", which framed typing as the normal path and the
document as the alternative. Walked through from the agent's chair the normal
case is the opposite: the agent is holding the COLA document, and then the five
values are something to confirm rather than something to enter. The single-label
view puts the document directly after the photographs and the typed fields
behind a disclosure that opens in exactly three cases (US-24); the batch path
takes documents only (ADR 0009). What each value means, and which one wins, is
unchanged.

**This is not the COLA system integration OOS-1 excludes.** OOS-1 rules out API
calls, COLAs Online authorization and registry lookups from the application.
Accepting a document the agent already holds is document parsing: it needs no
credential and opens no socket, and NFR-3 and NFR-6 apply to it exactly as they
apply to a label image. The note under OOS-1 in
[02_PROJECT_SCOPE.md](02_PROJECT_SCOPE.md) records the same distinction.

**Acceptance criteria**
- Given a COLA document uploaded on the single-label path, then the values it
  carries are extracted and reported as a block distinct from the comparison,
  each value marked found or not found.
- Given a digitally generated document, for example COLAs Online output or a
  Registry printout, then extraction reads the file's own content rather than
  recognizing pixels, and reports which path was used.
- Given a filled-in copy of the fillable form, then the values are read from its
  form fields, which is where they are, rather than from the blank template's
  text.
- Given a scan or a photograph of a printed form, then it is read through the
  same local OCR pipeline label artwork is read through, and the response says
  so.
- Given a value that is not an item on the form, then it is reported as not
  found **with the reason**, rather than reported as a bare absence. On
  TTB F 5100.31 (04/2023) the class or type designation and the alcohol content
  are not items at all, and the net contents is item 15 only when it is blown,
  branded or embossed on the container and does not appear on the labels.
- Given a document that names all three of item 5's product types in its text,
  then the text alone does not settle the beverage type, because a text layer
  prints the caption of an unticked box exactly as it prints the caption of a
  ticked one.
- Given item 5's three check boxes on a rendered page, then the darkest is
  reported as ticked **only when it is clearly separated from the other two by
  the configured margin**, and the result reports what was measured. See
  [ADR 0016](adr/0016-product-type-from-the-page.md).
- Given two boxes too close to separate, or no box filled, then the beverage type
  is reported as not determined and the agent chooses, and the result says the
  boxes were sampled rather than that the document did not name a type.
- Given a document whose form fields state the product type, then that value is
  used and the boxes are not sampled at all.
- Given a value read from a ticked box, then it is surfaced for confirmation and
  stays editable like every other parsed value, and it is marked as read from the
  box rather than from the form's text.
- The check boxes are located from their own captions and never from a pixel
  coordinate, because the form has editions and renders at different scales.
- Given a field the agent typed and a document that also carries it, then the
  typed value is used and the response says the value was typed. A blank field
  is not a correction and the parsed value stands.
- Given any parsed value, then it is presented in an editable field before a
  verification runs, marked as read from the application form, and the
  verification uses what is in the field.
- Given the single-label view on load, then the application document upload is
  the application-side input on screen and the typed fields are collapsed. They
  open when the agent opens them, when a parsed document leaves any value not
  found, or when a document fails to parse; a document that supplies every
  value opens nothing, because there is nothing left to enter (US-24, NFR-4).
- Given the beverage type, then it is never compared against the label. It
  states which numeric rule to expect and nothing else, it is filled from the
  document where the document states it, and the rule that actually ran is named
  in the field result's own reason (A-12, A-13).
- Given an empty or unreadable document, then the response names the problem,
  carries no field outcomes at all, and the typed path remains available (FR-9).
- Given a document of a type that is not accepted, then it is refused before
  anything is decoded, with the accepted types named (NFR-7).
- No outbound network call is made to read the document (NFR-3), and nothing
  about it is persisted or logged beyond a byte count and the path used (NFR-6).
- Given a document carrying embedded raster images at or above the size floor,
  then each is read through the same local OCR pipeline label artwork is read
  through, and what it says fills any application value the document's text
  layer left empty (ADR 0010).
- Given a value present in both the text layer and the embedded artwork, then
  the text-layer value is used. The precedence, end to end, is: typed by the
  agent, then the document's text layer or form fields, then the embedded
  artwork, then absent, and the response says which of the four supplied each
  value.
- Given a document carrying no embedded images, or none above the size floor,
  then it behaves exactly as it did before: the values the text layer does not
  carry are reported as not found, with the reason.
- Given an agent who uploaded the application and no photograph, and a document
  whose embedded artwork could be read, then the largest such image is the label
  side of the check, and the response says so.
- Given the same submission with no readable artwork in the document, then the
  verification does not run, the response names the missing piece and offers the
  photograph upload, and no field reports an outcome. This is an FR-9 message
  rather than a validation error on a form field.

**The artwork path is a self-consistency check, and the requirement says so.**
Where the label being checked came out of the application document, what has
been established is that the artwork on file carries the mandatory elements and
that it agrees with the typed form data. Nothing has been established about a
physical bottle. Verifying the bottle against the filing still needs a
photograph of that bottle, and the response and the interface both state this
whenever it applies. The distinction is a requirement rather than a caveat,
because a green result read as "this product is compliant" would be the tool
overstating what it checked, which is the failure OOS-8 and FR-6 both exist to
prevent.

**On the batch path, this is how every value arrives.** Written when it was not:
the batch kept the CSV contract in A-14, and per-row COLA documents were called
a possible future extension. [ADR 0009](adr/0009-batch-cola-documents.md) built
them on 2026-08-28 and removed the CSV. A batch row is one label image paired
with one COLA document by filename stem, nothing is typed, and each row's result
carries the parsed block and the per-field source exactly as a single-label
submission with an attached document does. A row's document now fills values
from its own embedded artwork too; the row still requires its label image,
because batch rows are enumerated from the images so that the stream can report
a total before any document is read (ADR 0010, "Effect on the batch path").

### FR-12 One upload, sorted by the tool rather than by the agent

**Priority:** Should
**Source:** The author's own use of the deployed prototype, 2026-08-29: "if COLA
is uploaded, I don't also need an image", and "these should be combined; just
one upload; simplify the interface. You should be able to upload (pdfs or
images)."

Accept everything submitted for one label through one control, taking PDFs and
images in any mix, and decide what each file is from the file itself rather than
from which control it arrived in. Report that decision per file. See
[ADR 0011](adr/0011-one-upload.md).

**The classification rule, stated so it can be checked rather than trusted.**

1. A file whose bytes begin with `%PDF`, or which declares `application/pdf`, is
   the application side. The bytes decide; the declared type is the fallback,
   because a browser labels a file from its extension and an agent can rename
   it. Nothing is decoded to reach this answer.
2. An image is read once through the local OCR pipeline. If its text carries a
   COLA form or Public COLA Registry marker, or the application parser finds at
   least one mapped caption value in it, it is the application side. Otherwise
   it is a label side.
3. An image that cannot be decoded is a label side, carrying its error, because
   FR-9's message for an unreadable photograph is the one an agent can act on.

**The label image requirement is removed as a hard gate.** Before
[ADR 0010](adr/0010-embedded-label-artwork.md) there was nothing to check an
application against without a photograph, so requiring one was honest. There now
is: a filed application carries the label artwork inside it. Three submissions
are valid, and each completes: the application document alone, a label
photograph plus typed values, or both.

**Acceptance criteria**
- Given one control on the single-label view, then it accepts PDFs and images,
  one file or several, in any mix, and its copy says so.
- Given a file submitted through it, then the server classifies it by the rule
  above and the response reports, per file, what it was taken to be and why.
- Given a COLA document submitted through a control intended for photographs, or
  a photograph submitted through one intended for the application, then each is
  still classified by the file and used on the correct side.
- Given anything uploaded, then the check is enabled. No submission is blocked
  for want of a label photograph.
- Given an application document alone whose embedded artwork could be read, then
  the check runs against that artwork (ADR 0010).
- Given an application document alone with no artwork that could be read, then
  the verification does not run, the response names the missing piece and offers
  the photograph upload, and no field reports an outcome. This is an FR-9
  message, not a validation error on a form field.
- Given more files of one side than the check accepts, then the request is
  refused with a message naming the limit, before anything is compared.
- Given the control, then it is one labelled element, keyboard reachable, with
  drag and drop offered on top of a keyboard-operable alternative rather than
  instead of one, and each accepted file is announced to a live region together
  with what it was taken to be (NFR-5).

**The API contract, and where it is recorded.** `POST /api/verify` takes one
repeated `files` part. The older `image` and `application_document` parts remain
accepted and are routed through the same classifier, so a caller written against
v1.0 keeps working. `POST /api/classify` sorts an upload and reads the
application side without comparing anything, which is what lets the interface
show the classification and the parsed values before a check runs. The batch
path keeps `images` and `application_documents` unchanged, because ADR 0009
pairs by filename stem and a batch is already sorted; ADR 0011 records why the
two paths differ.

### FR-13 The values that were read go quiet; the ones that were not go loud

**Priority:** Should
**Source:** The author's own use of the deployed prototype, 2026-08-29:
"Collapse the form fields and only expand if there is something that isn't read
in from the application or picture."

Once an upload has been read, show each value that was found as a compact
read-only line and each value that was not as a field, and put nothing else in
the agent's way. US-24 collapsed the five typed fields behind a disclosure,
which fixed what greets an agent on load; this is about what happens after
something has been processed.

**Why it is a requirement rather than a layout preference.** Five text boxes
shown after a document has already answered four of them is a form asking an
agent to re-read work the tool has done, and NFR-4's benchmark is an agent who
should not have to read past anything. It is also the shape that makes the gaps
findable: three of the five values are not items on TTB F 5100.31 at all (A-17),
so a gap is the ordinary outcome rather than an error, and an agent has to be
able to see which one at a glance.

**Acceptance criteria**
- Given an upload that supplied a value, then that value is shown as one line
  carrying the value and where it came from: typed by the agent, the application
  form, or the label artwork inside the application. It is not shown as an
  editable box.
- Given an upload that did not supply a compared value, then that value is shown
  as an editable field, visible, not behind a disclosure.
- Given an upload that supplied every compared value, then no editable field is
  shown at all; one collapsed disclosure holds them.
- Given at least one gap, then focus moves to the first missing field, the view
  scrolls to it, and a live region says which value is missing and what to do
  about it: enter it, or upload a clearer image.
- Given any value that was read, then it remains editable behind that same
  disclosure, and a value the agent types is used instead of the one that was
  read (FR-11's precedence, unchanged).
- Given the beverage type, then it is stated on its own line: read where the
  document stated it in text, and otherwise reported as not read from the form,
  because the product-type boxes are check marks and a text layer cannot report
  which one is ticked (ADR 0008). Its selector is inline. It is never compared,
  so it never takes focus and it is never counted as a gap in the check.
- Given nothing uploaded yet, then the view is exactly what US-24 specified:
  one collapsed disclosure over the five fields, and no summary lines.
- The result panel is unchanged. This requirement is about the input side.

**Three sources, not four.** A value on the application side comes from the
agent, from the document's text, or from label artwork embedded in that
document (ADR 0010). It never comes from a photograph of the label: that is the
other side of the comparison, and taking the application value off the label
would mean comparing the label against itself.

## 4. Non-functional requirements

### NFR-1 Response time of about 5 seconds

**Priority:** Must
**Source:** Sarah Chen interview

Single-label verification returns in about 5 seconds.

**Acceptance criteria**
- Measured end-to-end latency for a single label is reported against a 5-second
  target, with the hardware and sample set stated.
- The measurement is published in the README. It is measured, not asserted.
- If the target is not met, the shortfall is reported rather than omitted.
- The phase breakdown is in the API response, where an operator and the
  deployment runbook can read it.
- **It is not on the screen.** Amended 2026-08-31 on the author's instruction:
  "I don't need the time listed on the screen think about what a regular
  application looks like do not put all these extra words on the screen that
  should not be there." An agent checking a label is not measuring the tool, and
  a latency figure above their results is the tool talking about itself in the
  middle of their work (NFR-4). Nothing about the measurement changes; only
  where it is read.
- **What is measured is what the agent waits for, across every request one
  submission makes.** Added 2026-09-01 from the author's measurement of the
  deployed build: a COLA document submitted alone cost `POST /api/classify` at
  5492 and 5410 ms and then `POST /api/verify` at 5331 to 5498 ms, about eleven
  seconds for one document, while each request on its own was inside the target.
  A target met per request and missed per submission is a target reported
  wrongly. So no picture is read in more than one request for one submission
  ([ADR 0017](adr/0017-read-the-artwork-once.md)).
- **The saving is never bought with a store.** A cache of parsed documents would
  breach NFR-6, which is an acceptance criterion of this system and a promise
  printed on every screen of the interface. Recorded on FR-1 and NFR-1 alike so
  that it is not rediscovered as a good idea.

This is the requirement that killed the previous pilot: "The system would take
30, 40 seconds sometimes to process a single label... If we can't get results
back in about 5 seconds, nobody's going to use it. We learned that the hard
way." [Source: Sarah Chen interview]

The target applies per label. Whether a 300-label batch is expected to complete
within any particular wall-clock time is not stated in the assignment; see OQ-6.

### NFR-2 Batch throughput

**Priority:** Should
**Source:** Sarah Chen interview

Batch processing handles the stated volume without failing the whole submission.

**Acceptance criteria**
- A batch of 300 labels completes or reports per-label errors, without a
  request timeout that discards completed work.
- Batch progress is observable to the user rather than presenting as a frozen
  page.

### NFR-3 No outbound network calls on the default path

**Priority:** Must
**Source:** Marcus Williams interview; Decision D-4

The default extraction path makes no outbound network calls.

**Acceptance criteria**
- With default configuration, verification completes with egress blocked.
- The Bedrock fallback is off unless `TTB_ENABLE_BEDROCK_FALLBACK` is explicitly
  set to true.
- Enabling the fallback is visible in the response, so a user knows whether a
  result involved an external call.

Marcus's warning: "our network blocks outbound traffic to a lot of domains...
During the scanning vendor pilot, half their features didn't work because our
firewall blocked connections to their ML endpoints." [Source: Marcus Williams interview]

### NFR-4 Simplicity of the interface

**Priority:** Must
**Source:** Sarah Chen interview

The interface is usable by an agent with low technology comfort.

**Acceptance criteria**
- The primary task, verify one label, is reachable from the landing page with no
  navigation.
- The path to it carries the fewest inputs that can complete it: photographs,
  the application document, the check. Values the document supplies are not
  asked for again, and the boxes for typing them are behind a disclosure rather
  than in the way (US-24).
- No step requires terminology not already used in label review.
- Sarah's benchmark: something a 73-year-old first-time user "could figure out."
  "Clean, obvious, no hunting for buttons."

**A disclosure is not navigation.** The first criterion is about reaching the
task, and the task is still on the landing page with nothing to click through:
the photograph picker, the application upload and the check button are all on
screen on load. What moved behind the disclosure is a fallback for the case
where the agent does not have the document, and NFR-4 is better served by five
fewer boxes in front of the primary path than it was by having them there.

**A word budget, asserted (2026-08-31).** The panel accumulated wordiness one
honest sentence at a time: every paragraph added over four sessions was true and
was added for a reason, and the sum of them was 584 words on the author's own
submission and 159 on a single row of it. A rule saying "keep it short" is obeyed
by whoever reads it and by nobody who does not, so the ceiling is a number in a
test. `frontend/src/__tests__/quietScreen.test.tsx` holds it, and
`frontend/tests/a11y.spec.ts` holds the author's own target: the single-label
result for a clean document fits one screen at 1280 by 800 without scrolling.

- One sentence per row, at most. Where a chip or a value's own label already says
  something, the row does not say it again in prose.
- One notice per screen, said once where it is first relevant, rather than in the
  upload card and the results header and every affected row.
- Cutting words is not licence to drop the assessment-prototype banner, the
  author attribution, an FR-9 message that names a real problem, or the sentence
  that says who decides. Those are asserted separately and stay.

### NFR-5 Accessibility

**Priority:** Must
**Source:** Sarah Chen interview; Decision D-3

The interface targets WCAG 2.1 Level AA.

**Acceptance criteria**
- Outcomes are conveyed by text and shape, not by colour alone.
- All interactive controls are keyboard reachable and have visible focus.
- Form inputs have programmatically associated labels.
- Text contrast meets 4.5:1 for body text.
- Results appearing after submission are announced to assistive technology.

Sarah states "half our team is over 50" and describes a wide range of technology
comfort. [Source: Sarah Chen interview] The applicability of Section 508 to this
prototype is not stated in the assignment and must be confirmed; see OQ-7.

### NFR-6 No persistence of uploaded content

**Priority:** Must
**Source:** Decision D-9; Marcus Williams interview

No uploaded image or form data is retained beyond the request lifecycle.

**Acceptance criteria**
- No image or form field is written to disk, database, object storage, or cache.
- No image content or extracted field value appears in application logs.
- The container mounts no volume for uploaded content.
- The limitation and its production path are documented.

Marcus: "We're not storing anything sensitive for this exercise."
[Source: Marcus Williams interview]

### NFR-7 Input validation

**Priority:** Must
**Source:** Decision D-9; Evaluation Criteria

Uploads are validated before processing.

**Acceptance criteria**
- File size is checked against `TTB_MAX_UPLOAD_BYTES` before the body is read
  into memory.
- MIME type is checked against the allowed list before decoding.
- Batch file count is checked against `TTB_MAX_BATCH_FILES` before processing.
- Rejections name the limit that was exceeded.

### NFR-8 Code quality and organization

**Priority:** Must
**Source:** Evaluation Criteria; Decision D-8

**Acceptance criteria**
- Lint and format checks pass in CI for both backend and frontend.
- Tests run in CI and pass.
- A dependency audit runs in CI for both ecosystems.
- An SBOM is generated for the container image and retained as a build artifact.

### NFR-9 Deployability

**Priority:** Must
**Source:** Deliverables; Decisions D-1, D-2

**Acceptance criteria**
- The application builds into a single container image.
- The image runs as a non-root user.
- The image exposes `GET /api/health` for load balancer health checks.
- The same image runs locally under docker-compose and on ECS with Fargate.

### NFR-10 Portability to a FedRAMP-authorized government region (AWS GovCloud or Azure Government)

**Priority:** Should
**Source:** Decision D-11

Infrastructure code targets a FedRAMP-authorized government region without
redesign. Decision D-11 presumes the agency's platform, Azure per the interview,
as the eventual production target; moving there runs the same container image
and needs an Azure provider module for the Terraform. See
[ADR 0001](adr/0001-cloud-platform-aws.md) and
[cloud_choice_and_abv_assumption.md](cloud_choice_and_abv_assumption.md)
section 1.

**Acceptance criteria**
- No hardcoded partition, region, or account identifier in infrastructure code.
- ARNs are derived from partition and region data sources.
- Only services available in GovCloud are used; availability is confirmed at
  deployment time rather than asserted here.

### NFR-11 Configuration through environment variables

**Priority:** Must
**Source:** Decision D-4; Decision D-9

**Acceptance criteria**
- No credential or environment-specific value is committed to the repository.
- `.env.example` documents every variable the application reads.
- Deployed environments receive configuration through the task definition rather
  than a committed file.

### FR-14 A value read off the artwork is filled in, and never called a match

**Priority:** Must
**Source:** The author's decision of 2026-08-30, taken against the discovery
record; Sarah Chen interview ("spend half their day doing what's essentially
data entry verification"); SC-3 and the batch path; Dave Morrison and Jenny Park
interviews for why the result may not overstate itself. See
[ADR 0013](adr/0013-artwork-derived-values.md).

Fill the alcohol content and the net contents from the label artwork embedded in
an uploaded COLA document when the application form does not state them, which is
the ordinary case because neither is an item on TTB F 5100.31 (A-17). Report a
value filled that way, and compared against the same artwork standing in as the
label side, as **read from the artwork** rather than as verified.

**Why both halves are required.** Asking an agent to hand-type a value the tool
has already read puts back the data entry the tool exists to remove, and on the
batch path there is no agent present to type it at all. But a comparison of a
value against the picture it was read from always agrees, so a match reported
there is structurally incapable of ever saying anything else. It is a signal with
no information in it, presented in the shape of four signals that carry
information.

**Acceptance criteria**
- Given a COLA document stating no alcohol content and no net contents, and
  carrying label artwork that states both, then both values are filled from the
  artwork and reported with their source.
- Given such a value compared against that same artwork as the label side, then
  the outcome is `artwork_derived`, it carries no score, and it is not a match.
- Given a result containing such rows, then the summary line counts only the
  rows that could have disagreed and names the rest, in the shape "3 of 3
  verifiable fields match; 2 read from the artwork only". Where no row is
  artwork-derived the line is unqualified.
- Given the `artwork_derived` state, then it is carried by a word and a
  silhouette that no other outcome uses, before any colour (NFR-5).
- Given such a row, then it states its source on the row itself, as "Label
  artwork (same source as the label)", rather than in a footnote elsewhere on
  the page.
- Given an agent who also uploaded a photograph of the label, then the same
  value is compared against that photograph, which is independent evidence, and
  is reported as an ordinary match, review or mismatch.
- Given a typed value or a value the document's own text states, then it wins
  over the artwork and is compared normally. FR-11's precedence is unchanged.
- Given label artwork that does not carry the alcohol content or the net
  contents, then the absence is reported as a finding rather than as not
  compared, because 27 CFR requires both on the label whatever the form says,
  and the reason names the section and its carve-outs.
- Given label artwork for a spirit stating both a percentage and a proof that do
  not agree, then the FR-7 cross-check reports it whether or not the application
  stated anything, and it is never reported as `artwork_derived`.
- Given a batch row, then every rule above applies to it unchanged. A batch row
  pairs a document with a label image (ADR 0009), so its label side is always an
  independent photograph and no batch row is artwork-derived.

**Amended 2026-09-01 by FR-15 and [ADR 0018](adr/0018-presence-checks.md).** The
alcohol content and the net contents are no longer compared at all where the
application declares neither, so they no longer reach the `artwork_derived`
state and the summary line no longer holds them out of its count. Two criteria
above are superseded by FR-15's, and they are the two the amendment is about:
the second, which made such a row `artwork_derived`, and the third, which
counted the rest. Everything else stands, including the state itself, its word
and silhouette, its exclusion from the count, and the absence finding.

The state narrows to what it was built for: a value read off the artwork,
compared against that same artwork, on a field FR-15 does not cover. It should
be rare, and on the author's own filing it does not arise.

### FR-15 A required element found on the label is a passing presence check

**Priority:** Must
**Source:** The author, using the deployed build, 2026-09-01: "Alcohol content
and net content needs to also say 'match' or 'Contains' in green when these
items are found on the artwork (that is the requirement right? to have the
volume and alcohol content listed?)"; 27 CFR 5.63, 4.32 and 7.63 as quoted in
FR-14 and in `backend/app/compare.py`. See
[ADR 0018](adr/0018-presence-checks.md).

Where the application declares no value for alcohol content or net contents, the
row is a **presence check**: a one-sided finding about the label alone, reported
as passing when the label carries the element 27 CFR requires.

**Why this is not the circular thing FR-14 forbids.** FR-14 was right that
comparing a value against the picture it was read from establishes nothing. It
was wrong to conclude that nothing had been established. The label carries an
element the regulation requires; that is a real, positive finding, answerable
from a picture alone, and it is the question the agent is checking. What was
circular was presenting it as a comparison and printing the same string in two
columns.

**Acceptance criteria**
- Given a label that carries alcohol content or net contents and an application
  that declares no value for it, then the row reports the outcome `present`, it
  carries the label's value, and it carries no score.
- Given such a row, then it has no application side at all: not the value, not a
  "not supplied" placeholder, and no source chip. There is nothing on that side.
- Given such a row, then its reason cites the section of 27 CFR the finding
  answers.
- Given the `present` outcome, then it is presented as a pass, in the same
  colour as a match, and is distinguished from a match by its word and by a
  silhouette no other outcome uses. Colour is never the only carrier (NFR-5).
- Given a result containing presence checks, then the summary line counts them
  alongside comparisons, in the shape "5 of 5 checks passed".
- Given an application that does declare the value, by typing or from a form
  edition that carries it, then the row is a two-sided comparison reporting
  match, needs human review or does not match exactly as FR-3 and FR-7 require.
  FR-11's precedence is unchanged.
- Given a label that does not carry the element, then the absence is reported as
  a finding naming the regulation, as FR-14 already requires. Presence and
  absence are the two answers to one question, and the same section is cited
  either way.
- Given a label for a spirit whose stated percentage and proof do not agree,
  then the FR-7 cross-check reports it as needs human review, and the presence
  check does not overrule it. A contradiction on the label is the more specific
  finding.
- Given a batch row whose paired document declares neither value, then the same
  rules apply to it unchanged.

## 5. Requirements deliberately not written

The following were considered and excluded because writing them would require
inventing content the sources do not supply. Each is recorded so that the
absence is visible rather than accidental.

- Beverage-type-specific validation rules for beer, wine, and distilled spirits.
  The assignment states requirements vary by type but supplies none. See OOS-7.
- Bold typeface detection for the warning prefix, required by 27 CFR 16.22(a)(2)
  but out of scope per Decision D-5. See OOS-4.
- Type size, characters per inch, and contrasting background checks under
  27 CFR 16.22. See OOS-5.
- Any accuracy target expressed as a percentage. No source states one; a target
  invented here would be unfalsifiable. See OQ-8.
