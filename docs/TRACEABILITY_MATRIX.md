# Traceability Matrix

Every requirement traces back to a stakeholder statement and forward to a story,
an issue, and a test. A requirement with no source is invented; a requirement
with no test is unverifiable. This table is how both are caught.

The **Test** column is deliberately unfilled where no test exists yet. It is a
gap register, not decoration.

## 1. Stakeholder statement to requirement to story to test

| # | Stakeholder statement | Source | Requirement | Story | Issue | Test | ADR |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | "An agent pulls up an application, looks at the label artwork, and checks that what's on the label matches what's in the application." | Sarah Chen | FR-1, FR-2 | US-1 | [#1](https://github.com/kimkight/26-DO-12891471-DH_T_ITS_AI_THT/issues/1) | Not written | |
| 2 | "a lot of what we do is just... matching... My agents spend half their day doing what's essentially data entry verification." | Sarah Chen | FR-2 | US-1 | [#1](https://github.com/kimkight/26-DO-12891471-DH_T_ITS_AI_THT/issues/1) | Not written | |
| 3 | "You need judgment." | Dave Morrison | FR-3 | US-2 | [#2](https://github.com/kimkight/26-DO-12891471-DH_T_ITS_AI_THT/issues/2) | Not written | [0004](adr/0004-fuzzy-matching-with-review-band.md) |
| 4 | "Just don't make my life harder in the process." | Dave Morrison | FR-10 | US-2 | [#2](https://github.com/kimkight/26-DO-12891471-DH_T_ITS_AI_THT/issues/2) | Not written | [0004](adr/0004-fuzzy-matching-with-review-band.md) |
| 5 | "the brand name was 'STONE'S THROW' on the label but 'Stone's Throw' in the application... it's obviously the same thing." | Dave Morrison | FR-4 | US-3 | [#3](https://github.com/kimkight/26-DO-12891471-DH_T_ITS_AI_THT/issues/3) | Not written; UAT row 2 | [0004](adr/0004-fuzzy-matching-with-review-band.md) |
| 6 | "It has to be exact. Like, word-for-word." | Jenny Park | FR-5 | US-4 | [#4](https://github.com/kimkight/26-DO-12891471-DH_T_ITS_AI_THT/issues/4) | Not written; UAT rows 4, 5 | [0004](adr/0004-fuzzy-matching-with-review-band.md) |
| 7 | "I caught one last month where they used 'Government Warning' in title case instead of all caps. Rejected." | Jenny Park | FR-6 | US-5 | [#5](https://github.com/kimkight/26-DO-12891471-DH_T_ITS_AI_THT/issues/5) | Not written; UAT row 3 | [0004](adr/0004-fuzzy-matching-with-review-band.md) |
| 8 | "the 'GOVERNMENT WARNING:' part has to be in all caps and bold." Confirmed by 27 CFR 16.22(a)(2). | Jenny Park; eCFR | FR-6; OOS-4 | US-5 | [#5](https://github.com/kimkight/26-DO-12891471-DH_T_ITS_AI_THT/issues/5) | Not written; UAT row 15 | [0004](adr/0004-fuzzy-matching-with-review-band.md) |
| 9 | Sample label: "45% Alc./Vol. (90 Proof)", "750 mL" | Technical Requirements | FR-7 | US-6 | [#6](https://github.com/kimkight/26-DO-12891471-DH_T_ITS_AI_THT/issues/6) | Not written; UAT rows 7, 8, 18, 20 | |
| 9a | "ABV is correct? Check." Tolerances in 27 CFR 5.65, 4.36, 7.65 govern actual against labeled content, so none applies to two declared values. | Sarah Chen; eCFR | FR-7; A-12 | US-6 | [#6](https://github.com/kimkight/26-DO-12891471-DH_T_ITS_AI_THT/issues/6) | Not written; UAT rows 18, 19, 20, 21 | |
| 9b | Net contents in different units are not converted; standards of fill are not validated. | FR-7; A-13 | FR-7; A-13 | US-6 | [#6](https://github.com/kimkight/26-DO-12891471-DH_T_ITS_AI_THT/issues/6) | Not written; UAT row 22 | |
| 10 | "if an agent can't read the label they just reject it and ask for a better image." | Jenny Park | FR-9 | US-7 | [#7](https://github.com/kimkight/26-DO-12891471-DH_T_ITS_AI_THT/issues/7) | Not written; UAT row 6 | |
| 11 | "If we can't get results back in about 5 seconds, nobody's going to use it. We learned that the hard way." | Sarah Chen | NFR-1 | US-8 | [#8](https://github.com/kimkight/26-DO-12891471-DH_T_ITS_AI_THT/issues/8) | Not written; UAT row 11 | [0002](adr/0002-compute-ecs-fargate-not-app-runner.md) |
| 12 | "big importers who dump 200, 300 label applications on us at once... we literally have to process them one at a time." | Sarah Chen | FR-8 | US-9 | [#9](https://github.com/kimkight/26-DO-12891471-DH_T_ITS_AI_THT/issues/9) | Not written; UAT row 9 | |
| 13 | "Janet from our Seattle office has been asking about this for years." | Sarah Chen | FR-8 | US-9 | [#9](https://github.com/kimkight/26-DO-12891471-DH_T_ITS_AI_THT/issues/9) | Not written | |
| 14 | Batch resilience implied by the 300-label scenario | Sarah Chen | FR-8, FR-9 | US-10 | [#10](https://github.com/kimkight/26-DO-12891471-DH_T_ITS_AI_THT/issues/10) | Not written; UAT row 10 | |
| 15 | Batch scale implies visible progress | Sarah Chen | NFR-2 | US-11 | [#11](https://github.com/kimkight/26-DO-12891471-DH_T_ITS_AI_THT/issues/11) | Not written | |
| 16 | "We need something my mother could figure out; she's 73..." and "Clean, obvious, no hunting for buttons." | Sarah Chen | NFR-4 | US-12 | [#12](https://github.com/kimkight/26-DO-12891471-DH_T_ITS_AI_THT/issues/12) | Not written; UAT row 14 | |
| 17 | "The agents really vary in their tech comfort level... half our team is over 50." | Sarah Chen | NFR-4, NFR-5 | US-12, US-13 | [#12](https://github.com/kimkight/26-DO-12891471-DH_T_ITS_AI_THT/issues/12), [#13](https://github.com/kimkight/26-DO-12891471-DH_T_ITS_AI_THT/issues/13) | Not written; UAT rows 12, 13 | |
| 18 | "our network blocks outbound traffic to a lot of domains... half their features didn't work because our firewall blocked connections to their ML endpoints." | Marcus Williams | NFR-3 | US-14 | [#14](https://github.com/kimkight/26-DO-12891471-DH_T_ITS_AI_THT/issues/14) | Not written; UAT row 16 | [0003](adr/0003-local-ocr-default-bedrock-optional.md) |
| 19 | "We're not storing anything sensitive for this exercise." | Marcus Williams | NFR-6 | US-15 | [#15](https://github.com/kimkight/26-DO-12891471-DH_T_ITS_AI_THT/issues/15) | Not written; UAT row 17 | |
| 20 | "there's PII considerations, document retention policies, the usual federal compliance stuff." | Marcus Williams | NFR-6, NFR-7 | US-15, US-16 | [#15](https://github.com/kimkight/26-DO-12891471-DH_T_ITS_AI_THT/issues/15), [#16](https://github.com/kimkight/26-DO-12891471-DH_T_ITS_AI_THT/issues/16) | Not written | |
| 21 | "Deployed Application URL: Working prototype we can access and test." | Deliverables | NFR-9 | US-17 | [#17](https://github.com/kimkight/26-DO-12891471-DH_T_ITS_AI_THT/issues/17) | CI: container health probe | [0001](adr/0001-cloud-platform-aws.md), [0002](adr/0002-compute-ecs-fargate-not-app-runner.md) |
| 22 | "Code quality and organization" | Evaluation Criteria | NFR-8 | US-18 | [#18](https://github.com/kimkight/26-DO-12891471-DH_T_ITS_AI_THT/issues/18) | CI: `backend`, `frontend`, `audit`, `container` jobs | [0005](adr/0005-git-flow-branching.md) |
| 23 | "don't get me started on the FedRAMP certification process. Took 18 months just for the paperwork." | Marcus Williams | NFR-10 | US-19 | [#19](https://github.com/kimkight/26-DO-12891471-DH_T_ITS_AI_THT/issues/19) | Not written | [0001](adr/0001-cloud-platform-aws.md), [0002](adr/0002-compute-ecs-fargate-not-app-runner.md) |
| 24 | "We're on Azure now after the migration in 2019." | Marcus Williams | Recorded as OQ-1, not a requirement | | | | [0001](adr/0001-cloud-platform-aws.md) |
| 25 | "we're not looking to integrate with COLA directly." | Marcus Williams | OOS-1 | | | | |
| 26 | "README with setup and run instructions... Brief documentation of approach, tools used, assumptions made." | Deliverables | SC-5, SC-6 | US-20 | [#20](https://github.com/kimkight/26-DO-12891471-DH_T_ITS_AI_THT/issues/20) | Not written | |
| 27 | "Correctness and completeness of core requirements" | Evaluation Criteria | NFR-1, NFR-8 | US-21 | [#21](https://github.com/kimkight/26-DO-12891471-DH_T_ITS_AI_THT/issues/21) | Not written; accuracy tier | |
| 28 | "labels that are photographed at weird angles, or the lighting is bad, or there's glare... maybe out of scope for a prototype." | Jenny Park | SG-1, stretch | | | | [0003](adr/0003-local-ocr-default-bedrock-optional.md) |
| 29 | "I've seen a lot of these 'modernization' projects come and go." | Dave Morrison | Adoption risk; drives NFR-4 and FR-3 | US-12, US-2 | [#12](https://github.com/kimkight/26-DO-12891471-DH_T_ITS_AI_THT/issues/12), [#2](https://github.com/kimkight/26-DO-12891471-DH_T_ITS_AI_THT/issues/2) | UAT row 14 | [0004](adr/0004-fuzzy-matching-with-review-band.md) |

## 2. Requirement coverage

Every requirement maps to at least one story. No orphans.

| Requirement | Stories | Issues | Implemented | Tested |
| --- | --- | --- | --- | --- |
| FR-1 Field extraction | US-1 | #1 | No | No |
| FR-2 Comparison against application data | US-1 | #1 | No | No |
| FR-3 Three-outcome result | US-1, US-2 | #1, #2 | No | No |
| FR-4 Case and punctuation tolerance | US-3 | #3 | No | No |
| FR-5 Warning exact text | US-4 | #4 | No | No |
| FR-6 Warning capitalization | US-5 | #5 | No | No |
| FR-7 Numeric comparison, including the A-12 ABV rule and the A-13 net contents rule | US-6 | #6 | No | No |
| FR-8 Batch verification | US-9, US-10 | #9, #10 | No | No |
| FR-9 Error handling | US-7, US-10 | #7, #10 | No | No |
| FR-10 Result presentation | US-2 | #2 | No | No |
| NFR-1 About 5 seconds | US-8, US-21 | #8, #21 | No | No |
| NFR-2 Batch throughput | US-11 | #11 | No | No |
| NFR-3 No outbound calls | US-14 | #14 | Partial: default is off in config | No |
| NFR-4 Simplicity | US-12 | #12 | No | No |
| NFR-5 Accessibility | US-13 | #13 | No | No |
| NFR-6 No persistence | US-15 | #15 | Partial: no volumes, no datastore exists | No |
| NFR-7 Input validation | US-16 | #16 | Partial: limits defined, not enforced | No |
| NFR-8 Code quality gates | US-18 | #18 | **Yes** | CI |
| NFR-9 Deployability | US-17 | #17 | Partial: image builds, nothing deployed | CI container job |
| NFR-10 Government-region portability | US-19 | #19 | No: no infrastructure code exists | No |
| NFR-11 Environment configuration | US-15, US-17 | #15, #17 | **Yes** | No |

## 3. Coverage summary

| Measure | Count |
| --- | --- |
| Requirements defined | 21 (10 functional, 11 non-functional) |
| Requirements traced to a story | 21 of 21 |
| Requirements traced to a GitHub issue | 21 of 21 |
| Requirements fully implemented | 2 of 21 |
| Requirements with an automated test | 1 of 21 (NFR-8, by CI itself) |
| User stories | 21 |
| Stories with acceptance criteria | 21 of 21 |
| ADRs | 5 |

The gap between "traced" and "tested" is the honest state of this repository:
requirements and stories are complete, implementation is not started, and the
test suite covers only the health endpoint.

## 4. Open questions blocking requirements

| Open question | Blocks |
| --- | --- |
| OQ-6 batch latency and job model | FR-8, NFR-2, US-9, US-11 |
| OQ-7 Section 508 applicability | NFR-5 acceptance, US-13 |
| OQ-8 accuracy target | US-21 acceptance |
| OQ-9 threshold defaults | FR-3 tuning |
| OQ-13 deployment details | NFR-9, US-17 |
| OQ-16 batch application data format | FR-8, US-9 |

OQ-4 and OQ-5 no longer appear in this table. They are closed by assumptions
A-12 and A-13 in [ASSUMPTIONS.md](ASSUMPTIONS.md), and the rules they settle are
stated in the FR-7 acceptance criteria in
[03_REQUIREMENTS.md](03_REQUIREMENTS.md). OQ-1 is answered by
[ADR 0001](adr/0001-cloud-platform-aws.md) as the author's decision, not as a
stakeholder answer. Reasoning and sources for all three:
[cloud_choice_and_abv_assumption.md](cloud_choice_and_abv_assumption.md).

## 5. Maintenance

This file is updated in the same commit as any change to a requirement, story,
or test, per the pull request checklist in
[08_SDLC_PROCESS.md](08_SDLC_PROCESS.md) section 4. A traceability matrix
updated separately from the change it describes is already wrong.
