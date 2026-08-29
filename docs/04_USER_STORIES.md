# User Stories

Personas are limited to those appearing in the discovery interviews:

| Persona | Drawn from | Notes |
| --- | --- | --- |
| Compliance agent | Dave Morrison, 28 years; Jenny Park, 8 months | The primary user. Spans the full range of technology comfort Sarah describes. |
| Deputy Director of Label Compliance | Sarah Chen | Accountable for throughput and adoption. |
| IT systems administrator | Marcus Williams | Owns the technical and security boundary. |
| Batch submitter context | Janet, Seattle office, via Sarah | Not interviewed directly. The batch need is attributed to her through Sarah. |

Story points are intentionally left blank; they are set at refinement
(see [08_SDLC_PROCESS.md](08_SDLC_PROCESS.md)).

The `Issue` column is filled in from the GitHub Issues created from this file.

---

## Epic A: Single label verification

### US-1 Verify a single label against its application data

| | |
| --- | --- |
| Epic | Single label verification |
| Priority | Must |
| Requirements | FR-1, FR-2, FR-3 |
| Points | |
| Issue | #1 |
| Source | Sarah Chen interview |

**As a** compliance agent,
**I want** to upload a label image together with the application data,
**so that** I can see whether the label agrees with the application without
checking every field by eye.

**Acceptance criteria**

```
Given a label image and application data for brand name, class/type,
      alcohol content, net contents, and government warning
When  I submit them for verification
Then  I receive one outcome for each of the five fields
And   each outcome is one of match, needs human review, or mismatch
```

```
Given a field the system could not find on the label
When  results are returned
Then  that field is reported as not found
And   it is not reported as a match
```

Sarah describes the manual task this replaces: "An agent pulls up an
application, looks at the label artwork, and checks that what's on the label
matches what's in the application." [Source: Sarah Chen interview]

### US-2 See what was found next to what was expected

| | |
| --- | --- |
| Epic | Single label verification |
| Priority | Must |
| Requirements | FR-3, FR-10 |
| Points | |
| Issue | #2 |
| Source | Dave Morrison interview |

**As a** compliance agent,
**I want** each result to show the value found on the label beside the value
from the application,
**so that** I can exercise my own judgment instead of trusting a verdict I
cannot inspect.

**Acceptance criteria**

```
Given a completed verification
When  I view the results
Then  each field row shows the field name, the label value, the application
      value, and the outcome
```

```
Given a field with an outcome of needs human review
When  I view the results
Then  that row is visually distinct from both matches and mismatches
```

Dave's condition for adopting any tool: "Just don't make my life harder in the
process." A verdict without its evidence would make the work harder, not easier.
[Source: Dave Morrison interview]

### US-3 Tolerate differences of case and punctuation

| | |
| --- | --- |
| Epic | Single label verification |
| Priority | Must |
| Requirements | FR-4 |
| Points | |
| Issue | #3 |
| Source | Dave Morrison interview |

**As a** compliance agent,
**I want** presentational differences such as capitalization to not be treated
as substantive mismatches,
**so that** I am not sent to review pairs that are obviously the same thing.

**Acceptance criteria**

```
Given a label reading STONE'S THROW and an application reading Stone's Throw
When  verification runs
Then  the brand name outcome is match or needs human review
And   the outcome is never mismatch
```

```
Given two genuinely different brand names
When  verification runs
Then  normalization does not cause them to be reported as a match
```

Dave's case verbatim: "the brand name was 'STONE'S THROW' on the label but
'Stone's Throw' in the application. Technically a mismatch? Sure. But it's
obviously the same thing. You need judgment." [Source: Dave Morrison interview]

### US-4 Check the government warning word for word

| | |
| --- | --- |
| Epic | Single label verification |
| Priority | Must |
| Requirements | FR-5 |
| Points | |
| Issue | #4 |
| Source | Jenny Park interview |

**As a** compliance agent,
**I want** the government warning compared exactly against the required text,
**so that** altered wording is caught rather than passed as close enough.

**Acceptance criteria**

```
Given a warning matching 27 CFR 16.21 except for line breaks and runs of spaces
When  verification runs
Then  the warning body outcome is match
```

```
Given a warning with any word added, removed, or changed
When  verification runs
Then  the outcome is mismatch
And   the outcome is not needs human review
```

```
Given no warning statement is found on the label
When  verification runs
Then  the outcome is mismatch and the result states the statement was not found
```

Jenny: "It has to be exact. Like, word-for-word." She names the pattern she
sees: "people try to get creative with the warning all the time... different
wording." [Source: Jenny Park interview]

### US-5 Catch a warning that is not in capital letters

| | |
| --- | --- |
| Epic | Single label verification |
| Priority | Must |
| Requirements | FR-6 |
| Points | |
| Issue | #5 |
| Source | Jenny Park interview |

**As a** compliance agent,
**I want** the `GOVERNMENT WARNING:` prefix checked for capitalization
separately from the warning body,
**so that** a title-case warning is caught and I can see which rule failed.

**Acceptance criteria**

```
Given a label reading Government Warning: in title case
When  verification runs
Then  the capitalization check fails
And   the warning field does not report a match
```

```
Given a label reading GOVERNMENT WARNING: in capitals
When  verification runs
Then  the capitalization check passes
```

```
Given any verification result
When  the warning field is displayed
Then  the result does not state or imply that bold type was verified
```

Jenny's real case: "I caught one last month where they used 'Government Warning'
in title case instead of all caps. Rejected." [Source: Jenny Park interview]

The rule is confirmed by 27 CFR 16.22(a)(2), which requires the first two words
in "capital letters and in bold type." The prototype checks capitals only; the
bold requirement is out of scope and must not be implied as checked
(see OOS-4 in [02_PROJECT_SCOPE.md](02_PROJECT_SCOPE.md)).

### US-6 Compare alcohol content and net contents as numbers

| | |
| --- | --- |
| Epic | Single label verification |
| Priority | Must |
| Requirements | FR-7 |
| Points | |
| Issue | #6 |
| Source | Decision D-5 |

**As a** compliance agent,
**I want** numeric fields compared numerically rather than as text,
**so that** the same value written differently is not reported as a mismatch.

**Acceptance criteria**

```
Given a label reading 45% Alc./Vol. (90 Proof) and an application reading 45
When  verification runs
Then  the alcohol content outcome is match
```

```
Given a label reading 750 mL and an application reading 750ml
When  verification runs
Then  the net contents outcome is match
```

```
Given a numeric field that cannot be parsed as a number
When  verification runs
Then  the system falls back to text comparison and says so in the result
```

The sample label's alcohol content is given as `45% Alc./Vol. (90 Proof)` and
net contents as `750 mL`. [Source: Technical Requirements, Sample Label section]

### US-7 Get a clear message when a label cannot be read

| | |
| --- | --- |
| Epic | Single label verification |
| Priority | Must |
| Requirements | FR-9 |
| Points | |
| Issue | #7 |
| Source | Jenny Park interview |

**As a** compliance agent,
**I want** an unreadable image to tell me plainly that it could not be read,
**so that** I can request a better image instead of acting on a wrong result.

**Acceptance criteria**

```
Given a corrupt or undecodable image file
When  I submit it
Then  the response states the image could not be read
And   no field reports a match
```

```
Given an image from which no text is extracted
When  results are returned
Then  the message distinguishes no text found from fields did not match
```

```
Given a file that is not an allowed image type, or is over the size limit
When  I submit it
Then  it is rejected before decoding, with a message naming the limit or the
      accepted types
```

Today's behaviour is the bar to clear: "Right now if an agent can't read the
label they just reject it and ask for a better image."
[Source: Jenny Park interview]

### US-8 Get results back in about five seconds

| | |
| --- | --- |
| Epic | Single label verification |
| Priority | Must |
| Requirements | NFR-1 |
| Points | |
| Issue | #8 |
| Source | Sarah Chen interview |

**As a** Deputy Director of Label Compliance,
**I want** single-label results in about five seconds,
**so that** agents use the tool instead of reverting to checking by eye.

**Acceptance criteria**

```
Given a single label submitted for verification
When  the measurement harness runs against the sample set
Then  end-to-end latency is recorded and reported against the 5-second target
And   the hardware and sample set used are stated alongside the number
```

```
Given the measured latency exceeds the target
When  results are published
Then  the shortfall is reported rather than omitted
```

This is the failure mode of the previous pilot: "The system would take 30, 40
seconds sometimes... If we can't get results back in about 5 seconds, nobody's
going to use it. We learned that the hard way." [Source: Sarah Chen interview]

---

## Epic B: Batch verification

### US-9 Submit many labels at once

| | |
| --- | --- |
| Epic | Batch verification |
| Priority | Must |
| Requirements | FR-8, FR-11 |
| Points | |
| Issue | #9, and [#70](https://github.com/kimkight/26-DO-12891471-DH_T_ITS_AI_THT/issues/70) for the change of contract |
| Source | Sarah Chen interview; the author's question, 2026-08-28 |

**As a** compliance agent handling a bulk importer submission,
**I want** to upload many labels together with the COLA document for each,
**so that** I am not processing a 300-application drop one at a time, and I am
not retyping 300 applications into a spreadsheet to do it.

**Acceptance criteria**

```
Given label images and one COLA document for each, named to match
When  I submit the batch
Then  the response contains a result set for every label in the batch
And   each result identifies which label it belongs to
And   each result's application values are the ones its document carried
```

```
Given an image whose name matches no document, or a document matching no image
When  I submit the batch
Then  that item reports an error on its own result line
And   every other label still returns results
```

```
Given a document that cannot be read
When  I submit the batch
Then  that label reports an error naming the document
And   no field reports a match for it
And   every other label still returns results
```

```
Given a batch larger than the configured file limit
When  I submit it
Then  the request is rejected before any file is processed
And   the message names the limit
```

```
Given I am on the batch view
When  I look at it before choosing anything
Then  the naming rule that pairs an image with a document is stated on screen
```

**What changed, and why.** This story asked for "many labels with their
application data" from the beginning, and until 2026-08-28 that application data
was one CSV keyed on image filename, assumed as A-14 and stated by no source.
The author asked where such a CSV would come from. Nothing an importer files
produces one; what they file is, per application, a COLA form plus label images,
and FR-11 reads that form. The CSV is removed, not kept alongside. See
[ADR 0009](adr/0009-batch-cola-documents.md), which also records the pairing
rule: `0001-stones-throw.png` goes with `0001-stones-throw.pdf`.

Sarah: "during peak season, we get these big importers who dump 200, 300 label
applications on us at once. Right now we literally have to process them one at a
time. If there was some way to handle batch uploads, that would be huge."
She attributes the standing request to "Janet from our Seattle office," who "has
been asking about this for years." [Source: Sarah Chen interview]

### US-10 Keep one bad image from failing the whole batch

| | |
| --- | --- |
| Epic | Batch verification |
| Priority | Must |
| Requirements | FR-8, FR-9 |
| Points | |
| Issue | #10 |
| Source | Sarah Chen interview |

**As a** compliance agent,
**I want** a single unreadable label to fail on its own,
**so that** I do not lose the results for the other 299 labels.

**Acceptance criteria**

```
Given a batch containing one unreadable image
When  the batch is processed
Then  that label reports an error
And   every other label in the batch still returns results
```

### US-11 See that a large batch is progressing

| | |
| --- | --- |
| Epic | Batch verification |
| Priority | Should |
| Requirements | NFR-2 |
| Points | |
| Issue | #11 |
| Source | Sarah Chen interview |

**As a** compliance agent,
**I want** to see that a large batch is still working,
**so that** I do not assume the page has frozen and start over.

**Acceptance criteria**

```
Given a batch of 300 labels
When  processing is under way
Then  progress is visible rather than presenting as a frozen page
```

```
Given a long-running batch
When  processing completes
Then  results are returned without a request timeout discarding completed work
```

---

## Epic C: Usability and accessibility

### US-12 Verify a label without hunting for anything

| | |
| --- | --- |
| Epic | Usability and accessibility |
| Priority | Must |
| Requirements | NFR-4 |
| Points | |
| Issue | #12 |
| Source | Sarah Chen interview |

**As a** compliance agent with low technology comfort,
**I want** the main task available immediately on the landing page,
**so that** I can do my job without learning a new system.

**Acceptance criteria**

```
Given I open the application
When  the landing page loads
Then  I can verify one label without navigating anywhere first
```

```
Given any step in the primary task
When  I read the on-screen text
Then  it uses no terminology beyond what label review already uses
```

Sarah's benchmark: "We need something my mother could figure out; she's 73 and
just learned to video call her grandkids last year." And: "Clean, obvious, no
hunting for buttons." [Source: Sarah Chen interview]

### US-13 Use the tool with a keyboard and a screen reader

| | |
| --- | --- |
| Epic | Usability and accessibility |
| Priority | Must |
| Requirements | NFR-5 |
| Points | |
| Issue | #13 |
| Source | Sarah Chen interview |

**As a** compliance agent using assistive technology,
**I want** the interface to meet WCAG 2.1 Level AA,
**so that** I can do the same work as everyone else.

**Acceptance criteria**

```
Given a results table
When  outcomes are displayed
Then  each outcome is conveyed by text and shape, not by colour alone
```

```
Given any interactive control
When  I navigate with the keyboard
Then  the control is reachable and its focus is visible
```

```
Given results appear after submission
When  the update happens
Then  it is announced to assistive technology
```

Sarah states "half our team is over 50" with a wide range of technology comfort.
[Source: Sarah Chen interview] Section 508 applicability is unconfirmed; see
OQ-7 in [OPEN_QUESTIONS.md](OPEN_QUESTIONS.md).

---

### US-24 Start from the application document, not from five empty boxes

| | |
| --- | --- |
| Epic | Usability and accessibility |
| Priority | Should |
| Requirements | FR-11, FR-2, FR-9, NFR-4, NFR-5 |
| Points | |
| Issue | [#74](https://github.com/kimkight/26-DO-12891471-DH_T_ITS_AI_THT/issues/74) |
| Source | The author's own use of the deployed prototype, 2026-08-28 |

**As a** compliance agent who is holding the applicant's COLA document when I
sit down to check a label,
**I want** the tool to start from that document rather than from five empty text
boxes,
**so that** I spend my attention confirming what the application says instead of
copying it.

**Acceptance criteria**

```
Given the single-label view on load
When  I look at it
Then  the application document upload is the application-side input on screen
And   it comes directly after the photo picker
And   it is not worded as the alternative to typing
And   the five typed fields are collapsed behind "Or type the application values"
```

```
Given no application document at hand
When  I open "Or type the application values"
Then  the five fields appear and I can type them
```

```
Given a document that was read and left gaps
When  the read finishes
Then  the fields open on their own
And   the values it did carry are filled in and marked as read from the form
And   the gaps are empty and waiting
And   the expansion is announced
```

```
Given a document that could not be read
When  the read fails
Then  the message names the problem
And   the fields open as the fallback
And   the expansion is announced
```

```
Given a document that carried every value
When  the read finishes
Then  nothing opens, because there is nothing left for me to enter
```

```
Given a value read off the document and the same value typed by me
When  I run the check
Then  my typed value is used, exactly as before
```

```
Given the beverage type
When  I look for it
Then  it is inside the disclosure and not the first field I meet
And   it says it is not compared against the label
```

```
Given a keyboard alone
When  I reach the disclosure
Then  it is reachable with visible focus
And   its expanded or collapsed state is announced correctly
```

The question this story exists for is the author's, from using the deployed
prototype: when would the typed fields actually be used? Walked through from the
agent's chair, the answer is almost never as a starting point. US-23 built the
upload and left the layout saying the opposite of what US-23 had learned: five
empty boxes first, and the document offered "instead". This story inverts that.
The flow the empty state now describes is the flow the batch tab has told from
the day ADR 0009 landed: photographs, then the application, then check.

**Three expansion cases, and only three.** The agent opens the disclosure; a
parsed document leaves gaps; a document fails to parse. A document that supplies
everything opens nothing, because there is nothing left to enter and the upload's
own summary already says what it read. Nothing ever closes the disclosure except
the agent, and no expansion moves focus: the parse can return while the agent is
reading something else, so it is announced to a live region instead.

Gaps are the normal case rather than the exceptional one. TTB F 5100.31
(04/2023) has no box for the class or type designation or the alcohol content at
all, and carries the net contents only when it is blown, branded or embossed on
the container (A-17). So the second expansion case is what an agent attaching the
form proper will meet every time, and the fields appear with the parsed values in
place and the gaps empty.

**Nothing about precedence changes.** FR-11's rule stands: a value the agent
typed wins over the same value read off the document, and the response says which
it was. There is no API change in this story.

**Beverage type is demoted rather than removed.** It is never compared. It says
which numeric rule to expect, the A-12 proof cross-check for spirits or A-13
range handling for wine, and nothing else. In the engine those rules key off the
value rather than off this control: the proof cross-check fires when the label
itself states a proof, and range handling fires when the value carries a range.
The rule that actually ran is named in the field result's own reason, which is
the honest place for it, so the control fills from the document when the document
states it and otherwise sits at the bottom of the disclosure.

---

## Epic D: Platform, security, and deployment

### US-14 Work behind a firewall that blocks outbound traffic

| | |
| --- | --- |
| Epic | Platform, security, and deployment |
| Priority | Must |
| Requirements | NFR-3 |
| Points | |
| Issue | #14 |
| Source | Marcus Williams interview |

**As an** IT systems administrator,
**I want** the default path to make no outbound network calls,
**so that** the tool does not fail the way the last vendor's did.

**Acceptance criteria**

```
Given default configuration and blocked egress
When  a label is verified
Then  verification completes successfully
```

```
Given the Bedrock fallback environment variable is unset
When  the application starts
Then  the fallback is disabled
```

```
Given the fallback is enabled and used
When  results are returned
Then  the result shows that an external call was involved
```

Marcus: "our network blocks outbound traffic to a lot of domains... During the
scanning vendor pilot, half their features didn't work because our firewall
blocked connections to their ML endpoints. Classic."
[Source: Marcus Williams interview]

### US-15 Retain nothing that was uploaded

| | |
| --- | --- |
| Epic | Platform, security, and deployment |
| Priority | Must |
| Requirements | NFR-6 |
| Points | |
| Issue | #15 |
| Source | Marcus Williams interview |

**As an** IT systems administrator,
**I want** no uploaded image or form data retained beyond the request,
**so that** the prototype raises no retention or privacy question.

**Acceptance criteria**

```
Given a completed verification
When  the response has been returned
Then  no image or form field has been written to disk, database, object
      storage, or cache
```

```
Given application logs for a verification
When  they are inspected
Then  they contain no image content and no extracted field value
```

Marcus: "there's PII considerations, document retention policies, the usual
federal compliance stuff. But for a prototype? Just don't do anything crazy.
We're not storing anything sensitive for this exercise."
[Source: Marcus Williams interview]

### US-16 Reject bad uploads before processing them

| | |
| --- | --- |
| Epic | Platform, security, and deployment |
| Priority | Must |
| Requirements | NFR-7 |
| Points | |
| Issue | #16 |
| Source | Decision D-9 |

**As an** IT systems administrator,
**I want** size, type, and count limits enforced before any file is decoded,
**so that** a malformed or oversized upload cannot exhaust the service.

**Acceptance criteria**

```
Given a file larger than the configured size limit
When  it is submitted
Then  it is rejected before the body is read into memory
And   the message names the limit
```

```
Given a file whose MIME type is not in the allowed list
When  it is submitted
Then  it is rejected before decoding
And   the message names the accepted types
```

### US-17 Reach a working prototype at a URL

| | |
| --- | --- |
| Epic | Platform, security, and deployment |
| Priority | Must |
| Requirements | NFR-9 |
| Points | |
| Issue | #17 |
| Source | Deliverables |

**As a** reviewer,
**I want** a deployed URL I can open and test,
**so that** I can evaluate the working prototype rather than only the code.

**Acceptance criteria**

```
Given the deployed URL
When  I open it
Then  the application loads and I can run a verification
```

```
Given the deployed service
When  the load balancer probes it
Then  GET /api/health returns 200
```

The assignment requires a "Deployed Application URL: Working prototype we can
access and test." [Source: Deliverables]

### US-18 Keep quality gates automatic

| | |
| --- | --- |
| Epic | Platform, security, and deployment |
| Priority | Must |
| Requirements | NFR-8 |
| Points | |
| Issue | #18 |
| Source | Decision D-8 |

**As an** IT systems administrator,
**I want** lint, tests, dependency audit, container build, and SBOM generation
to run on every pull request,
**so that** quality and supply-chain checks do not depend on anyone remembering.

**Acceptance criteria**

```
Given a pull request to develop or main
When  CI runs
Then  backend lint and tests, frontend lint and build, dependency audit,
      container build, and SBOM generation all execute
```

```
Given any of those checks fails
When  the pull request is viewed
Then  the ci status check reports failure
```

### US-19 Keep the government-region path open

| | |
| --- | --- |
| Epic | Platform, security, and deployment |
| Priority | Should |
| Requirements | NFR-10 |
| Points | |
| Issue | #19 |
| Source | Decision D-11 |

**As an** IT systems administrator,
**I want** the infrastructure code to target a FedRAMP-authorized government
region without redesign,
**so that** the prototype does not have to be rebuilt to move toward production.
Decision D-11 presumes the agency's platform, Azure per the interview, as the
eventual target; that path runs the same container image and needs an Azure
provider module for the Terraform. See
[adr/0001-cloud-platform-aws.md](adr/0001-cloud-platform-aws.md).

**Acceptance criteria**

```
Given the infrastructure code
When  it is reviewed
Then  it contains no hardcoded partition, region, or account identifier
And   ARNs are derived from partition and region data sources
```

```
Given the set of AWS services used
When  the GovCloud target is prepared
Then  availability of each service in GovCloud is confirmed against AWS
      documentation rather than assumed
```

Marcus on the compliance overhead this anticipates: "don't get me started on the
FedRAMP certification process. Took 18 months just for the paperwork."
[Source: Marcus Williams interview]

---

## Epic E: Documentation

### US-20 Understand how to run it and what it assumes

| | |
| --- | --- |
| Epic | Documentation |
| Priority | Must |
| Requirements | SC-5, SC-6 |
| Points | |
| Issue | #20 |
| Source | Deliverables |

**As a** reviewer,
**I want** setup and run instructions plus a statement of approach, tools, and
assumptions,
**so that** I can run the prototype and understand the decisions behind it.

**Acceptance criteria**

```
Given a clean checkout
When  I follow the README quick start
Then  the application runs and the health endpoint responds
```

```
Given the documentation
When  I look for approach, tools used, and assumptions made
Then  each is documented, and anything inferred is marked as an assumption
```

The assignment asks for "Brief documentation of approach, tools used,
assumptions made." [Source: Deliverables]

### US-21 See measured accuracy rather than claimed accuracy

| | |
| --- | --- |
| Epic | Documentation |
| Priority | Must |
| Requirements | NFR-1, NFR-8 |
| Points | |
| Issue | #21 |
| Source | Evaluation Criteria |

**As a** reviewer,
**I want** per-field accuracy and latency measured against a labeled sample set,
**so that** I can judge the prototype on evidence rather than assertion.

**Acceptance criteria**

```
Given the labeled sample set with ground truth
When  the accuracy suite runs
Then  per-field precision and recall are reported
And   the sample size and its composition are stated
```

```
Given the published results
When  a field performs poorly
Then  the weakness is reported rather than omitted
```

No accuracy target is stated in any source, so none is invented here; see OQ-8
in [OPEN_QUESTIONS.md](OPEN_QUESTIONS.md).

## Epic F: Real label artwork

### US-22 Check a label that one photograph cannot show

| | |
| --- | --- |
| Epic | Real label artwork |
| Priority | Should |
| Requirements | FR-1, FR-9 |
| Points | |
| Issue | [#61](https://github.com/kimkight/26-DO-12891471-DH_T_ITS_AI_THT/issues/61) |
| Source | The author's first real-artwork test against the deployed prototype, 2026-08-26; Jenny Park interview (SG-1); 27 CFR 16.21 |

Numbered #61 rather than #22 because GitHub draws issue and pull request numbers
from one sequence, and this repository had reached 60 by the time this story was
written. US-1 to US-21 map to issues #1 to #21; this one does not follow that
pattern and the break is recorded here rather than left to look like an error.

**As a** compliance agent checking a label on a round bottle,
**I want** to attach more than one photograph of the same label,
**so that** the fields that curve out of one frame can still be checked.

**Acceptance criteria**

```
Given a label whose fields are split between two photographs of it
When  I attach both and check the label
Then  every field found on either photograph is reported as found
And   the result names which photograph each value was read from
```

```
Given one unreadable photograph among readable ones
When  I check the label
Then  the readable photographs still produce a result
And   the unreadable one is reported rather than hidden
```

```
Given a submission in which no photograph could be read
When  I check the label
Then  no field reports a match
And   the message says that none of the photographs could be read
```

```
Given I have attached the maximum number of photographs
When  I look for the control that adds another
Then  it is no longer offered, and the interface says why
```

```
Given I attach only one photograph
When  I check the label
Then  the check behaves exactly as it did before this capability existed
```

The case this exists for, in the words of the test that found it: a photograph
of a real wine bottle was submitted to the deployed prototype and none of the
five fields came back. Two of the three causes were preprocessing and are fixed
under A-15. The third is that the label wraps the bottle, so no single
photograph shows it flat. Jenny Park raised exactly this and qualified it:
"labels that are photographed at weird angles... this is maybe out of scope for
a prototype." [Source: Jenny Park interview] 27 CFR 16.21 compounds it by
allowing the government warning to be "on a back or side label", so the required
elements need not all be on one face.

The decision, the alternatives rejected, and what is deliberately left out is
[ADR 0007](adr/0007-multi-photo-single-label.md). The number of photographs is
assumption A-16. Cylinder dewarping is not attempted; see OQ-21.

### US-23 Upload the label application instead of typing it

| | |
| --- | --- |
| Epic | Real label artwork |
| Priority | Should |
| Requirements | FR-11, FR-2, FR-3, FR-9 |
| Points | |
| Issue | [#65](https://github.com/kimkight/26-DO-12891471-DH_T_ITS_AI_THT/issues/65) |
| Source | The author's own use of the deployed prototype, 2026-08-27 |

Numbered #65 rather than #23 for the reason given under US-22: GitHub draws
issue and pull request numbers from one sequence, and this repository was past
64 by the time this story was written.

**As a** compliance agent who already has the applicant's label application in
front of me,
**I want** to attach that document instead of retyping what it says,
**so that** I spend my attention on judging the label rather than on data entry.

**Acceptance criteria**

```
Given a COLA document, a PDF or an image of one
When  I attach it on the single-label view
Then  the values it carries are put into the same fields I would have typed into
And   each filled field is marked as read from the application form
And   every filled field is still editable
```

```
Given a value the document does not carry
When  the document has been read
Then  that field is left for me to fill in
And   the interface says why the form does not carry it
```

```
Given a field I have typed and a document that also carries it
When  I run the check
Then  my typed value is used
And   the response says that value was typed rather than parsed
```

```
Given a filled-in copy of the fillable form
When  I attach it
Then  the values are read from its form fields, which is where they are
And   item 5's ticked box gives the beverage type
```

```
Given a scan or a photograph of a printed form
When  I attach it
Then  it is read through the same local OCR the tool reads labels with
And   the response says it was read that way
```

```
Given an empty or unreadable document
When  I attach it
Then  the message names the problem
And   no field reports a match
And   I can still type the values in myself
```

```
Given I attach nothing
When  I run the check
Then  it behaves exactly as it did before this capability existed
```

The question this story exists for is the author's own, while using the
deployed prototype: why enter all this information, when the applicant already
submitted it? The values the form asks for are on TTB Form 5100.31, the COLA
application, and on the Public COLA Registry detail page for an approved one.

**This is not the COLA system integration OOS-1 excludes.** Nothing here calls
an API, holds a credential or looks anything up. It reads a file the agent
already has. The note under OOS-1 in
[02_PROJECT_SCOPE.md](02_PROJECT_SCOPE.md) records the distinction, and
[ADR 0008](adr/0008-cola-form-as-application-input.md) records the decision, the
alternatives rejected, and what the form does not carry. The field map is
assumption A-17; what has not been verified against a real document is OQ-22.

---

### US-25 One upload, and the tool works out what I gave it

| | |
| --- | --- |
| Epic | Usability and accessibility |
| Priority | Should |
| Requirements | FR-12, FR-11, FR-1, FR-9, NFR-4, NFR-5 |
| Points | |
| Issue | [#74](https://github.com/kimkight/26-DO-12891471-DH_T_ITS_AI_THT/issues/74) |
| Source | The author's own use of the deployed prototype, 2026-08-29 |

**As a** compliance agent holding a COLA document, or a photo of a label, or
both,
**I want** one place to put them,
**So that** I am not asked to sort my own files before the tool has looked at
any of them.

**Acceptance criteria**

```
Given one file picker on the single-label view
When  I look at it
Then  it says it takes the label application, a photo of the label, or both
And   it accepts PDFs and images, one file or several
```

```
Given I upload only the applicant's COLA document
When  I run the check
Then  the check runs, against the label artwork inside that document
And   nothing asks me for a photo of a bottle I do not have
```

```
Given I upload a COLA document and a photo of the label
When  I look at the list of what I uploaded
Then  each file says what it was taken to be
And   a wrong call is something I can see and correct, not something silent
```

```
Given I upload only a COLA document that carries no label artwork
When  I run the check
Then  the check does not run
And   the message names what is missing and offers me the photo upload
And   no field reports a match
```

```
Given I am working from the keyboard, or with a screen reader
When  I add a file
Then  the control is one labelled file input I can reach and operate
And   the file is announced with what it was taken to be
```

The author's words on 2026-08-29, having been blocked from submitting a COLA
document because a label image was also required: "if COLA is uploaded, I don't
also need an image", and "these should be combined; just one upload; simplify
the interface. You should be able to upload (pdfs or images)."

**Why the tool does the sorting rather than the agent.** Two pickers asked an
agent to classify their own files before the tool had read any of them, and a
file put in the wrong one was read as the wrong thing: a COLA PDF dropped into
the photo picker was read as label artwork. The box is a guess about intent; the
file is the fact. The rule, and the cases where it can still be wrong, are in
[ADR 0011](adr/0011-one-upload.md); the label side that makes an
application-only submission possible at all is
[ADR 0010](adr/0010-embedded-label-artwork.md).
