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

### FR-1 Field extraction from label artwork

**Priority:** Must
**Source:** Technical Requirements, Sample Label section

Extract brand name, class/type designation, alcohol content, net contents, and
the government warning statement from uploaded label artwork. One label may be
submitted as more than one photograph of itself, because a label wraps a round
bottle and no single photograph shows all of it flat. See
[ADR 0007](adr/0007-multi-photo-single-label.md).

**Acceptance criteria**
- Given the sample distilled spirits label, when it is submitted, then the
  system returns a value or an explicit "not found" for each of the five fields.
- Given a field that cannot be located, then the field is reported as not found
  rather than reported as empty or silently omitted.
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

Accept application data for the same five fields and compare it against what was
extracted from the label.

**Acceptance criteria**
- Given a label and its application data, when verification runs, then each of
  the five fields carries exactly one outcome.
- Given application data missing a field, then that field is reported as not
  compared, and this is distinguished from a mismatch.

Sarah's description of the manual process this replaces: "Brand name matches?
Check. ABV is correct? Check. Government warning is there? Check."
[Source: Sarah Chen interview]

### FR-3 Three-outcome per-field result

**Priority:** Must
**Source:** Decision D-5; Dave Morrison interview

Each field returns one of: **match**, **needs human review**, or **mismatch**.

**Acceptance criteria**
- Given a field whose normalized similarity is at or above the match threshold,
  then the outcome is match.
- Given a field whose similarity falls between the review and match thresholds,
  then the outcome is needs human review.
- Given a field below the review threshold, then the outcome is mismatch.
- The result includes the extracted value, the application value, and the score,
  so that an agent can judge the call rather than trust it.

Dave's requirement in his own words: "Technically a mismatch? Sure. But it's
obviously the same thing. You need judgment." The middle outcome is how the tool
defers to that judgment instead of overriding it.
[Source: Dave Morrison interview]

### FR-4 Tolerance for case and punctuation differences

**Priority:** Must
**Source:** Dave Morrison interview; Decision D-5

Text comparison normalizes case, surrounding whitespace, and punctuation before
scoring, so that presentational differences do not read as substantive ones.

**Acceptance criteria**
- Given label `STONE'S THROW` and application `Stone's Throw`, then the outcome
  is match or needs human review, and never mismatch.
- Given a straight apostrophe against a typographic apostrophe in otherwise
  identical text, then the outcome is match.
- Given two genuinely different brand names, then normalization does not cause
  them to be reported as a match.

This requirement applies to FR-1 fields other than the government warning. The
warning is governed by FR-5 and FR-6, which are deliberately stricter.

### FR-5 Government warning compared for exact text

**Priority:** Must
**Source:** Jenny Park interview; Decision D-5; 27 CFR 16.21

The government warning is compared for exact text after whitespace
normalization, against the text quoted in section 1.

**Acceptance criteria**
- Given a warning matching 27 CFR 16.21 exactly except for line breaks and
  runs of spaces, then the outcome is match.
- Given a warning with altered, added, or omitted words, then the outcome is
  mismatch, not needs human review.
- Given no warning found on the label, then the outcome is mismatch and the
  result says the statement was not found.
- Fuzzy tolerance under FR-4 is not applied to the warning body.

Jenny's constraint: "It has to be exact. Like, word-for-word." She also notes
the failure modes she sees in practice: "people try to get creative with the
warning all the time. Smaller font, different wording, burying it in tiny text."
[Source: Jenny Park interview] Of those, this prototype detects different
wording only; font size and prominence are OOS-5.

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

### FR-11 The label application accepted as an input, instead of typed

**Priority:** Should
**Source:** The author's own use of the deployed prototype, 2026-08-27:
"Why do I have to enter in all this information?"

Accept an uploaded copy of the applicant's label application, TTB Form 5100.31,
or of the Public COLA Registry detail page for an application, as an alternative
to typing the same values. Read it locally and offer what it says for the
agent's confirmation. See
[ADR 0008](adr/0008-cola-form-as-application-input.md) and assumption A-17.

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
- Given a document that names all three of item 5's product types, then the
  beverage type is reported as not found, because a ticked box cannot be read
  from a document's text.
- Given a field the agent typed and a document that also carries it, then the
  typed value is used and the response says the value was typed. A blank field
  is not a correction and the parsed value stands.
- Given any parsed value, then it is presented in an editable field before a
  verification runs, marked as read from the application form, and the
  verification uses what is in the field.
- Given an empty or unreadable document, then the response names the problem,
  carries no field outcomes at all, and the typed path remains available (FR-9).
- Given a document of a type that is not accepted, then it is refused before
  anything is decoded, with the accepted types named (NFR-7).
- No outbound network call is made to read the document (NFR-3), and nothing
  about it is persisted or logged beyond a byte count and the path used (NFR-6).

**On the batch path, this is how every value arrives.** Written when it was not:
the batch kept the CSV contract in A-14, and per-row COLA documents were called
a possible future extension. [ADR 0009](adr/0009-batch-cola-documents.md) built
them on 2026-08-28 and removed the CSV. A batch row is one label image paired
with one COLA document by filename stem, nothing is typed, and each row's result
carries the parsed block and the per-field source exactly as a single-label
submission with an attached document does.

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
- No step requires terminology not already used in label review.
- Sarah's benchmark: something a 73-year-old first-time user "could figure out."
  "Clean, obvious, no hunting for buttons."

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
