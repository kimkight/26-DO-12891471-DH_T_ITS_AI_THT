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
| OOS-1 | COLA system integration | "We're not looking to integrate with COLA directly; that's a whole different beast with its own authorization requirements." Treated as "a standalone proof-of-concept." | Marcus Williams interview |
| OOS-2 | Authentication and authorization | No authentication in the prototype. Production would require it; the path is described in [06_SECURITY_AND_COMPLIANCE.md](06_SECURITY_AND_COMPLIANCE.md). | Decision D-9 |
| OOS-3 | Persistent storage of images or form data | Nothing is retained beyond the request lifecycle. "We're not storing anything sensitive for this exercise." | Decision D-9; Marcus Williams interview |
| OOS-4 | Any claim about bold typeface detection | Jenny states the prefix must be "all caps and bold," and 27 CFR 16.22(a)(2) confirms bold type is required. The prototype checks capitalization only. It must not report or imply that it has verified boldness. | Decision D-5; Jenny Park interview; 27 CFR 16.22(a)(2) |
| OOS-5 | Type size, characters-per-inch, and contrasting-background checks | 27 CFR 16.22 sets minimum type sizes, maximum characters per inch, and a contrasting-background requirement. These are physical measurements against a known container size, which the prototype does not receive. | 27 CFR 16.22; scope inference `(Assumption)` |
| OOS-6 | Label elements beyond the five extracted | The assignment lists bottler name and address and country of origin among common elements but does not include them in the sample label field list. Extraction is limited to the sample's fields. | Technical Requirements, Sample Label section |
| OOS-7 | Beverage-type-specific rule engines | The assignment states "The exact requirements vary by beverage type (beer, wine, distilled spirits)" but supplies rules for none of them. Encoding them would require inventing regulation. | Technical Requirements, Additional Context |
| OOS-8 | Determining whether a label is compliant overall | The tool reports per-field agreement between label and application. It does not issue an approval decision. The agent decides. | Decision D-9; Dave Morrison interview |
| OOS-9 | Production deployment to AWS GovCloud (US) | This assignment deploys to commercial `us-east-1`. The build stays portable but GovCloud is not exercised. | Decision D-11 |

## 3. Stretch goals

Attempted only if the committed scope is complete and working. "A working core
application with clean code is preferred over ambitious but incomplete
features." [Source: Technical Requirements]

| ID | Stretch goal | Source |
| --- | --- | --- |
| SG-1 | Handle imperfect images: photographs at an angle, poor lighting, or glare on the bottle. Jenny raises it and immediately qualifies it: "this is maybe out of scope for a prototype." | Jenny Park interview |
| SG-2 | Optional vision-model fallback on Amazon Bedrock for images local OCR cannot read, off by default and enabled only by environment variable. | Decision D-4 |
| SG-3 | Extraction of the remaining common label elements listed in the assignment: bottler name and address, country of origin. | Technical Requirements, Additional Context |

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
