# Project Scope

Scope is drawn only from the assignment text and the recorded decisions. Where
a boundary is inferred rather than stated it is marked `(Assumption)` and listed
in [ASSUMPTIONS.md](ASSUMPTIONS.md).

## 1. In scope

### 1.1 Extraction

Extract the following fields from label artwork. The list is the subset of TTB
label elements that the assignment's sample label enumerates, plus the warning
statement. [Source: Technical Requirements, Sample Label section]

- Brand name, for example `OLD TOM DISTILLERY`
- Class or type designation, for example `Kentucky Straight Bourbon Whiskey`
- Alcohol content, for example `45% Alc./Vol. (90 Proof)`
- Net contents, for example `750 mL`
- Government Health Warning Statement

Extraction runs locally inside the container using Tesseract with OpenCV
preprocessing, with no outbound network calls on the default path.
[Source: Decision D-4; Marcus Williams interview]

### 1.2 Comparison

Compare each extracted field against the corresponding value supplied as
application data and return one of three outcomes per field: **match**,
**needs human review**, or **mismatch**. [Source: Decision D-5]

The three-outcome design exists because Dave Morrison's `STONE'S THROW` against
`Stone's Throw` case is neither a clean match nor a defensible rejection: "You
need judgment." [Source: Dave Morrison interview]

### 1.3 Government warning handling

The warning is compared for exact text after whitespace normalization, with a
separate check that the `GOVERNMENT WARNING:` prefix is upper case.
[Source: Decision D-5; Jenny Park interview]

The reference text is 27 CFR 16.21, quoted verbatim in
[03_REQUIREMENTS.md](03_REQUIREMENTS.md).

### 1.4 Batch verification

Accept multiple labels with their application data in one submission and return
a per-label, per-field result set. Sarah cites importers submitting "200, 300
label applications" at once. [Source: Sarah Chen interview]

### 1.5 Interface

A web interface simple enough for an agent with low technology comfort: "Clean,
obvious, no hunting for buttons." [Source: Sarah Chen interview]

### 1.6 Error handling

An image that cannot be read produces a clear, actionable message rather than a
silent failure or a false match. Today an agent who cannot read a label "just
reject[s] it and ask[s] for a better image"; the tool must not be worse than
that. [Source: Jenny Park interview; Evaluation Criteria, "User experience and
error handling"]

### 1.7 Deployment

A working prototype deployed to a URL that reviewers can access and test, on
AWS commercial `us-east-1`. [Source: Deliverables; Decision D-1]

### 1.8 Documentation

README with setup and run instructions, plus documentation of approach, tools
used, and assumptions made. [Source: Deliverables]

## 2. Out of scope

| ID | Excluded | Why | Source |
| --- | --- | --- | --- |
| OOS-1 | COLA system integration | "We're not looking to integrate with COLA directly; that's a whole different beast with its own authorization requirements." Treated as "a standalone proof-of-concept." **See the note below on what this does and does not exclude.** | Marcus Williams interview |
| OOS-2 | Authentication and authorization | No authentication in the prototype. Production would require it; the path is described in [06_SECURITY_AND_COMPLIANCE.md](06_SECURITY_AND_COMPLIANCE.md). | Decision D-9 |
| OOS-3 | Persistent storage of images or form data | Nothing is retained beyond the request lifecycle. "We're not storing anything sensitive for this exercise." | Decision D-9; Marcus Williams interview |
| OOS-4 | Any claim about bold typeface detection | Jenny states the prefix must be "all caps and bold," and 27 CFR 16.22(a)(2) confirms bold type is required. The prototype checks capitalization only. It must not report or imply that it has verified boldness. | Decision D-5; Jenny Park interview; 27 CFR 16.22(a)(2) |
| OOS-5 | Type size, characters-per-inch, and contrasting-background checks | 27 CFR 16.22 sets minimum type sizes, maximum characters per inch, and a contrasting-background requirement. These are physical measurements against a known container size, which the prototype does not receive. | 27 CFR 16.22; scope inference `(Assumption)` |
| OOS-6 | Label elements beyond the five extracted | The assignment lists bottler name and address and country of origin among common elements but does not include them in the sample label field list. Extraction is limited to the sample's fields. | Technical Requirements, Sample Label section |
| OOS-7 | Beverage-type-specific rule engines | The assignment states "The exact requirements vary by beverage type (beer, wine, distilled spirits)" but supplies rules for none of them. Encoding them would require inventing regulation. | Technical Requirements, Additional Context |
| OOS-8 | Determining whether a label is compliant overall | The tool reports per-field agreement between label and application. It does not issue an approval decision. The agent decides. | Decision D-9; Dave Morrison interview |
| OOS-9 | Production deployment to a government region on either platform | This assignment deploys to AWS commercial `us-east-1` by the author's choice. The build stays cloud-portable, but neither AWS GovCloud (US) nor the agency's Azure platform is exercised. | Decision D-11 |

### Note on OOS-1: what it excludes, and what it does not

OOS-1 excludes integrating with the COLA system. Read as Marcus Williams stated
it, that means:

- no calls to any COLA or COLAs Online API,
- no COLAs Online authorization, credentials, accounts or sessions,
- no lookups against the TTB Public COLA Registry from the application, by API
  or by scraping.

**It does not exclude accepting an uploaded copy of a completed label
application.** FR-11 accepts one: the agent attaches the applicant's
TTB Form 5100.31, or the Registry printout for it, and the tool reads the file.
That is document parsing, in the same sense that reading a label photograph is
document parsing. It needs no credential, contacts nothing, and is the same kind
of act as the upload the tool already accepts.

The distinction matters because it is what Marcus's objection is actually about.
The "whole different beast" he names is the authorization requirement, and an
uploaded file has none. NFR-3 holds: the default path still makes no outbound
call. NFR-6 holds: the document is read in memory and released with the request.

A future version that looked an application **up** rather than being handed one
would be the excluded thing, and would need Marcus's decision rather than an
ADR. See [ADR 0008](adr/0008-cola-form-as-application-input.md).

## 3. Stretch goals

Attempted only if the committed scope is complete and working. "A working core
application with clean code is preferred over ambitious but incomplete
features." [Source: Technical Requirements]

| ID | Stretch goal | Source |
| --- | --- | --- |
| SG-1 | Handle imperfect images: photographs at an angle, poor lighting, or glare on the bottle. Jenny raises it and immediately qualifies it: "this is maybe out of scope for a prototype." | Jenny Park interview |
| SG-2 | Optional vision-model fallback on Amazon Bedrock for images local OCR cannot read, off by default and enabled only by environment variable. | Decision D-4 |
| SG-3 | Extraction of the remaining common label elements listed in the assignment: bottler name and address, country of origin. | Technical Requirements, Additional Context |

**What SG-1 now covers, and what it still does not.** Part of SG-1 was taken on
after the first real-artwork test: a photograph taken sideways is turned upright
before it is read, the EXIF orientation tag a phone writes is honoured, and the
existing small-angle deskew still runs after the turn. See assumption A-15.

The rest of SG-1 is still out. A label wraps a round bottle, so no single
photograph shows it flat: the far edges compress and the text distorts.
Correcting that needs perspective or cylinder dewarping with an estimated
radius, and **it is not attempted**. It is the ADR 0003 risk, that local OCR
reads real photographed artwork worse than a cloud service would, and it is
unmeasured. What was done instead is to accept up to three photographs of the
same label, so an agent can photograph the parts of it that a single frame
cannot show flat; see [ADR 0007](adr/0007-multi-photo-single-label.md). That
lets an agent work around the distortion rather than correcting it, and the
difference is stated here so the two are not confused. Glare and poor lighting
are still handled only by the adaptive threshold that was already there.

**Section 6 below is the judged scope line on this**, with the evidence from the
author's mezcal test of 2026-08-29: what the extraction works on, what it does
not work on reliably, and what it would take to change that. Bottle photography
stays as a best-effort path and is not claimed as a supported capability.

## 4. Definition of Done for the prototype

The prototype is done when every item below is true. Each is verifiable; none
is a matter of opinion.

**Function**

1. A single label plus its application data returns per-field outcomes of match,
   needs human review, or mismatch for all five fields in section 1.1.
2. A batch submission returns the same per-field outcomes for every label in the
   batch, with per-label failures isolated so one bad image does not fail the
   batch.
3. A government warning in title case is not reported as a match. [Source: Jenny Park interview]
4. `STONE'S THROW` against `Stone's Throw` is reported as match or needs human
   review, never as a hard mismatch. [Source: Dave Morrison interview]
5. Alcohol content and net contents are compared numerically, so that `45%` and
   `45.0%` agree. [Source: Decision D-5]
6. An unreadable image returns a clear message naming the problem, and the rest
   of the submission still processes.

**Performance**

7. Single-label end-to-end latency is measured and reported against the
   5-second target, on stated hardware with a stated sample. [Source: Sarah Chen interview]

**Quality**

8. CI passes on `develop`: lint, tests, dependency audit, container build, and
   SBOM generation. [Source: Decision D-8]
9. Accuracy is measured per field against the labeled sample set with ground
   truth, and the numbers are published in the README. Measured, not asserted.
10. The container runs as a non-root user and the default path makes no
    outbound network calls.

**Delivery**

11. The prototype is reachable at a URL the reviewers can test. [Source: Deliverables]
12. README documents setup, run instructions, approach, tools, assumptions, and
    known limitations. [Source: Deliverables]
13. Every open question is either resolved in the documentation or listed in
    [OPEN_QUESTIONS.md](OPEN_QUESTIONS.md). No question is answered by guessing.

## 5. Explicitly deferred, not forgotten

These are consequences of prototype scope that a production system would have to
close. They are stated here so that no reader mistakes the prototype's silence
for a claim of adequacy.

- No authentication means no accountability trail for who ran a verification.
- No persistence means no audit record that a verification occurred.
- Capitalization checking is not boldness checking, and the regulation requires
  both.
- Accuracy measured on a self-built sample set is not accuracy measured on the
  real application population.

## 6. What the extraction works on, and what it does not

The author asked, in plain words: **"Should I even be contemplating a label on a
bottle, or is everything coming through COLA?"** This section is the answer, with
the evidence, so that a reviewer reads a judged scope line rather than finding a
gap.

### 6.1 The input that works: flat label artwork

Two things count as flat label artwork, and the pipeline handles both:

- **The images filed with the COLA application.** An applicant affixes the label
  artwork to TTB F 5100.31, so a filed application carries pictures of the
  labels. Those pictures are flat by construction: they are the artwork, not a
  photograph of a bottle.
  [ADR 0010](adr/0010-embedded-label-artwork.md) extracts and reads them.
- **Photographs of a flat label**, or of a label lying flat: a label sheet, a
  proof, a label peeled off or not yet applied.

**The measured performance in [09_DEPLOYMENT.md](09_DEPLOYMENT.md) section 9 was
obtained on that input**, and on nothing else. One label with its COLA document
returned in 1.5 seconds end to end through the load balancer with all five
fields matched, and 300 labels with 300 paired documents completed in roughly
6.5 to 7 minutes with every seeded defect caught and no false alarms. Both runs
used synthetic flat artwork rendered by `samples/labelmaker.py`. Every accuracy
figure in the README carries the same qualification.

### 6.2 The input that does not work reliably: a label wrapped on a round bottle

A photograph of a label still on a cylindrical bottle is not a supported input.
Three findings from the author's mezcal test of 2026-08-29, stated as evidence
rather than as opinion:

**1. The blocks are set at right angles to each other.** On that bottle the
GOVERNMENT WARNING block is printed at 90 degrees to the body copy, confirmed
visually in a crop of the photograph. No single global rotation can bring both
upright: turning the image to read the warning lays the brand and class on their
side, and turning it to read those does the same to the warning. The best-of-four
cardinal rotation net described in assumption A-15 chooses one orientation for
the whole image, so it **cannot** succeed on both blocks of that label at once,
whatever it chooses. The fix is a per-text-block orientation pass, and **it is
not built**.

**2. Baselines curve around the cylinder.** A sweep of 4 rotations by 5 page
segmentation modes, 20 reads, over the isolated warning crop produced
`4 AANDVW 1AG` as its best result, at a similarity of **2.1 percent** against
27 CFR 16.21. That is not a degraded read; it is a failure to read at all.
Tesseract has no model for text on a curved baseline, and no rotation or
threshold setting substitutes for one. This is the SG-1 dewarp problem in its
original form, unchanged and unsolved, and it is the
[ADR 0003](adr/0003-local-ocr-default-bedrock-optional.md) accuracy risk
realized for the third time.

**3. Even with perfect OCR, the semantics do not fall out of the pixels.** The
real COLA for that product gives the brand name as `DEL MAGUEY` and the fanciful
name as `VIDA`. The largest text on the label is `Vida Clasico`. `parse.py`
locates the brand name by type size, because no source states a layout rule and
type size is a property of the artwork rather than an assumption about it; on
this real product that heuristic cannot get the right answer, and it could not
get it from a perfect transcription either. Reading the pixels correctly and
attributing them correctly are two different problems, and only the first is an
OCR problem.

**What changed in v1.1.0 is not that, and the distinction matters.** The
ranking now declines rather than guessing: where the largest text is not clear
of the next largest by `_STANDOUT_RATIO`, the field reports not found, which is
what FR-1 asks for. On this artwork it declines. That converts a confident wrong
answer into an honest absence, which is a real improvement and is not a solution
to the attribution problem stated above. Nothing here reads a brand name off
this label, and nothing in this prototype will until a source states a layout
rule or the application's own text supplies it, which on the document path it
does.

### 6.3 The scope decision

**Bottle photography stays in the prototype as a best-effort path with honest
failure reporting. It is not claimed as a supported capability.**

- **It is not removed**, because an agent standing at a bottling line has
  nothing else. [ADR 0007](adr/0007-multi-photo-single-label.md) exists for
  exactly that agent: several photographs of one label, merged, so they can work
  around the distortion rather than being blocked by it. When it fails it fails
  visibly, which is what FR-1 and FR-9 require: a field that cannot be located
  reports not found rather than a guess, and an image that cannot be read
  returns a message naming the problem.
- **It is not promised**, because the evidence in 6.2 says that would be a false
  promise. No performance or accuracy figure in this repository was measured on
  a curved bottle photograph, and none is claimed for one.

This is a scope line, not a defect. What changed on 2026-08-29 is that the
application document turned out to carry its own flat artwork
([ADR 0010](adr/0010-embedded-label-artwork.md)), so the input that works is
also the input an agent most often has. The bottle is the fallback, not the
path.

### 6.4 What would make it work, and what each would cost

Named so that a reviewer sees the road as well as the wall. None of these is
built.

| Approach | What it solves | What it costs |
| --- | --- | --- |
| **Per-text-block orientation detection** | Finding 1: two blocks at right angles to each other. Detect and rotate each block rather than the whole image | Layout analysis before recognition, and a rule for reassembling blocks read at different orientations into one reading order. Does nothing for finding 2 |
| **Cylindrical dewarp from the label's edges** | Finding 2: curved baselines. Estimate the cylinder from the label's top and bottom edges and unwrap it | Edge detection robust to glare and to labels whose edges are not visible, plus an estimated radius. It is the SG-1 problem stated as an implementation |
| **Multi-photo stitching around the bottle** | Findings 1 and 2 together, by reconstructing the flat label from several overlapping views | Feature matching and blending across photographs taken by hand. **ADR 0007 exists; stitching does not.** ADR 0007 merges *fields* read independently from several photographs; it does not merge the photographs |
| **A vision model that reads curved and skewed text directly** | All three findings, including finding 3, since a model can be asked which text is the brand rather than being told to take the largest | This is **SG-2**, the Bedrock fallback, and it carries the FedRAMP status, egress and data-handling questions already recorded in [ADR 0003](adr/0003-local-ocr-default-bedrock-optional.md) and in [06_SECURITY_AND_COMPLIANCE.md](06_SECURITY_AND_COMPLIANCE.md) section 6.3. It also reintroduces the fabricated-value risk that ADR 0003 keeps out by default |

### 6.5 The two TTB statements this section rests on, quoted

Neither is paraphrased, and neither is stretched beyond what it says.

**On what is filed: labels, not containers.** TTB F 5100.31 (04/2023), item 15,
transcribed from the form downloaded during development from
`https://www.ttb.gov/system/files/images/pdfs/forms/f510031.pdf` (see assumption
[A-17](ASSUMPTIONS.md#a-17)):

> 15. SHOW ANY INFORMATION THAT IS BLOWN, BRANDED, OR EMBOSSED ON THE CONTAINER
> (e.g., net contents) ONLY IF IT DOES NOT APPEAR ON THE LABELS AFFIXED BELOW.

**What it says:** the form's own baseline is the labels affixed to the
application, and the container is the exception the applicant reports only where
something appears on the container and not on those labels. **What it does not
say:** it does not say a container photograph is unacceptable evidence, and it
does not say anything about how a label should be photographed. It is quoted
here because it establishes that the artefact TTB works from is the label as
filed, which is the input 6.1 describes.

**On legibility, which is measured against the container and is out of scope.**
27 CFR 16.22(a), retrieved from eCFR on 2026-08-20, quoted verbatim in
[03_REQUIREMENTS.md](03_REQUIREMENTS.md) section 1. Source URL:
`https://www.ecfr.gov/current/title-27/section-16.22`

> (a) Legibility. (1) All labels shall be so designed that the statement
> required by § 16.21 is readily legible under ordinary conditions, and such
> statement shall be on a contrasting background.

**What it says:** legibility and contrast are requirements on the label as
designed. **What it does not say:** it does not state a type size in this
paragraph, and it does not say how either is to be verified. The type sizes are
elsewhere in § 16.22 and are keyed to container volume, which is why **OOS-5**
excludes type size, characters per inch and contrasting-background checks: they
are physical measurements against a known container size, and this system
receives an image with no scale reference and no container size. A bottle
photograph does not change that. It carries no scale either, and reading a
millimetre off a photograph of unknown distance is not a measurement.

### 6.6 What this section changes

Nothing in the code, and no capability is claimed that was not claimed before.
It records a scope decision and the evidence for it. The stretch goal SG-1 is
unchanged: still a stretch goal, still partly taken on for orientation, still
not attempted for dewarping.
