# Project Charter: AI-Powered Alcohol Label Verification Prototype

| Field | Value |
| --- | --- |
| Author | Kimberly D. Kight |
| Status | Approved for prototype build |
| Version | 0.1.0 |
| Repository | `kimkight/26-DO-12891471-DH_T_ITS_AI_THT` |

## 1. Purpose

Build a working prototype that compares the text on alcohol beverage label
artwork against the data submitted in the corresponding application, and
returns a per-field verdict fast enough that a compliance agent will actually
use it.

The prototype is a standalone proof of concept. It is not a COLA integration
and it is not a production system. Its purpose is to demonstrate that the
routine matching portion of label review can be automated well enough to be
worth pursuing, and to inform future procurement decisions.
[Source: Marcus Williams interview]

## 2. Background

The following is drawn only from the discovery interviews supplied with the
assignment. Figures are quoted as the stakeholders gave them and are not
independently verified.

**Volume against capacity.** Sarah Chen, Deputy Director of Label Compliance,
states that "the TTB reviews about 150,000 label applications a year" handled by
"our team of 47 agents," down from "over 100 agents" before budget cuts. The
process has been "basically the same way since the COLA system went online in
2003." [Source: Sarah Chen interview]

**The work is mostly matching.** Sarah describes the review as: "An agent pulls
up an application, looks at the label artwork, and checks that what's on the
label matches what's in the application." She frames the automation case
directly: "a lot of what we do is just... matching. Like literally just making
sure the number on the form is the same as the number on the label. My agents
spend half their day doing what's essentially data entry verification."
A simple application takes "maybe 5-10 minutes." [Source: Sarah Chen interview]

**A prior pilot failed on latency.** A scanning vendor pilot was, in Sarah's
word, a "disaster": "The system would take 30, 40 seconds sometimes to process a
single label. Our agents just went back to doing it by eye because they could do
five labels in the time it took the machine to do one. If we can't get results
back in about 5 seconds, nobody's going to use it. We learned that the hard
way." This is the single most important constraint on the design.
[Source: Sarah Chen interview]

**The user base is not uniformly technical.** Sarah: "Dave's been here since the
Clinton administration and still prints his emails. Meanwhile, Jenny's fresh out
of college and probably could have built this tool herself." Her usability
benchmark is concrete: "We need something my mother could figure out; she's 73
and just learned to video call her grandkids last year." She adds that "half our
team is over 50" and asks for "Clean, obvious, no hunting for buttons."
[Source: Sarah Chen interview]

**Batch submission is an unmet need.** "During peak season, we get these big
importers who dump 200, 300 label applications on us at once. Right now we
literally have to process them one at a time." Sarah attributes the standing
request to "Janet from our Seattle office," who "has been asking about this for
years." [Source: Sarah Chen interview]

**The network blocks outbound traffic.** Marcus Williams, IT Systems
Administrator, warns that "our network blocks outbound traffic to a lot of
domains" and that during the scanning vendor pilot "half their features didn't
work because our firewall blocked connections to their ML endpoints." This is
why the default extraction path runs locally and makes no outbound calls
(Decision D-4). [Source: Marcus Williams interview]

**Matching needs judgment, not just equality.** Dave Morrison, a senior
compliance agent of 28 years, gives the governing example: "I had one last week
where the brand name was 'STONE'S THROW' on the label but 'Stone's Throw' in the
application. Technically a mismatch? Sure. But it's obviously the same thing.
You need judgment." He is open to tooling on one condition: "If something can
help me get through my queue faster, great. Just don't make my life harder in
the process." [Source: Dave Morrison interview]

**The warning statement is the strict field.** Jenny Park, a junior compliance
agent of eight months, explains that "the warning statement check is actually
trickier than it sounds. It has to be exact. Like, word-for-word, and the
'GOVERNMENT WARNING:' part has to be in all caps and bold." She reports a live
rejection: "I caught one last month where they used 'Government Warning' in
title case instead of all caps. Rejected." She also describes the manual state
of play: "I literally have a printed checklist on my desk that I go through for
every label." [Source: Jenny Park interview]

Jenny's description of the rule is confirmed by regulation. 27 CFR 16.22(a)(2)
provides: "The first two words of the statement required by § 16.21, i.e.,
'GOVERNMENT WARNING,' shall appear in capital letters and in bold type. The
remainder of the warning statement may not appear in bold type."
[Source: eCFR, 27 CFR 16.22, retrieved 2026-08-20,
https://www.ecfr.gov/current/title-27/section-16.22]

**Institutional skepticism is a real risk.** Dave: "I've seen a lot of these
'modernization' projects come and go. Remember the automated phone system they
put in back in 2008? Supposed to reduce call volume. We ended up with more calls
because nobody could figure out how to navigate it." Adoption, not accuracy
alone, decides whether this succeeds. [Source: Dave Morrison interview]

## 3. Stakeholders

| Name | Role | Stated concerns | Implication for this build |
| --- | --- | --- | --- |
| Sarah Chen | Deputy Director of Label Compliance | Throughput against a shrinking team; "If we can't get results back in about 5 seconds, nobody's going to use it"; "We need something my mother could figure out"; batch upload of "200, 300 label applications" at once | Owns the success criteria. Latency and simplicity are acceptance gates, not preferences. |
| Marcus Williams | IT Systems Administrator | "Our network blocks outbound traffic to a lot of domains"; no COLA integration because "that's a whole different beast with its own authorization requirements"; "for a prototype? Just don't do anything crazy. We're not storing anything sensitive" | Sets the technical boundary. Drives the offline-by-default extraction path and the no-persistence decision. |
| Dave Morrison | Senior Compliance Agent, 28 years | "You need judgment"; the `STONE'S THROW` against `Stone's Throw` case; "Just don't make my life harder in the process"; scarred by past modernization failures | The reason for a three-outcome verdict with a human-review band rather than pass or fail. Represents adoption risk. |
| Jenny Park | Junior Compliance Agent, 8 months | The warning "has to be exact... word-for-word," with "GOVERNMENT WARNING:" in all caps and bold; caught a title-case warning and rejected it; wishes imperfect photographs could be handled, "maybe out of scope for a prototype" | Source of the strict warning rule and of the imperfect-image stretch goal. |
| Janet (Seattle office) | Compliance staff, Seattle office | Has "been asking about" batch handling "for years" | Named only through Sarah. Not interviewed directly; the batch requirement is attributed to her via Sarah. |

## 4. Success criteria

Only criteria stated in the assignment are listed. Each is testable.

| ID | Criterion | Source |
| --- | --- | --- |
| SC-1 | Results return in about 5 seconds. | Sarah Chen interview |
| SC-2 | Usable by agents with low technology comfort; "clean, obvious, no hunting for buttons." | Sarah Chen interview |
| SC-3 | Handles batch submission rather than one label at a time. | Sarah Chen interview |
| SC-4 | A working prototype is deployed at a URL the reviewers can access and test. | Deliverables |
| SC-5 | Clean, well organized code. "A working core application with clean code is preferred over ambitious but incomplete features." | Evaluation Criteria; Technical Requirements |
| SC-6 | Documentation of approach, tools used, and assumptions made. | Deliverables |

## 5. Constraints

| ID | Constraint | Source |
| --- | --- | --- |
| C-1 | The agency network blocks outbound traffic to many domains. The default path must not depend on external calls. | Marcus Williams interview |
| C-2 | No COLA integration. This is a standalone proof of concept. | Marcus Williams interview |
| C-3 | No sensitive data is stored. "We're not storing anything sensitive for this exercise." | Marcus Williams interview |
| C-4 | The exercise is time constrained. "A working core application with clean code is preferred over ambitious but incomplete features." | Technical Requirements |
| C-5 | Results must return in about 5 seconds or the tool will not be adopted. | Sarah Chen interview |
| C-6 | The intended production environment is AWS GovCloud (US); this assignment deploys to AWS commercial `us-east-1`. The build must not foreclose the GovCloud path. | Decision D-11 |

## 6. Deliverables

Exactly the two the assignment lists. [Source: Deliverables]

1. **Source code repository**, containing all source code, a README with setup
   and run instructions, and brief documentation of approach, tools used, and
   assumptions made.
2. **Deployed application URL**, a working prototype the reviewers can access
   and test.

## 7. Evaluation criteria

Exactly the six the assignment lists. [Source: Evaluation Criteria]

1. Correctness and completeness of core requirements.
2. Code quality and organization.
3. Appropriate technical choices for the scope.
4. User experience and error handling.
5. Attention to requirements.
6. Creative problem-solving.

## 8. Target environment

The prototype deploys to **AWS commercial `us-east-1`**. The agency's intended
production environment is **AWS GovCloud (US)**. The infrastructure code is
written so that the same modules target GovCloud without redesign: no hardcoded
partition, region, or account identifiers, and no dependency on a service absent
from GovCloud. [Source: Decision D-1; Decision D-11]

Marcus notes the agency is "on Azure now after the migration in 2019."
[Source: Marcus Williams interview] The prototype nonetheless targets AWS per
Decision D-1. Nothing in this assignment states which cloud the eventual
production system would use, and no inference is drawn here; the discrepancy is
recorded as OQ-1 in [OPEN_QUESTIONS.md](OPEN_QUESTIONS.md).

## 9. Out of scope for the charter

Scope boundaries are defined in [02_PROJECT_SCOPE.md](02_PROJECT_SCOPE.md).
Decisions already taken, with alternatives and consequences, are recorded as
ADRs under [adr/](adr/).
