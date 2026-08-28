# Traceability Matrix

Every requirement traces back to a stakeholder statement and forward to a story,
an issue, and a test. A requirement with no source is invented; a requirement
with no test is unverifiable. This table is how both are caught.

The **Test** column is deliberately unfilled where no test exists yet. It is a
gap register, not decoration.

## 1. Stakeholder statement to requirement to story to test

| # | Stakeholder statement | Source | Requirement | Story | Issue | Test | ADR |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | "An agent pulls up an application, looks at the label artwork, and checks that what's on the label matches what's in the application." | Sarah Chen | FR-1, FR-2 | US-1 | [#1](https://github.com/kimkight/26-DO-12891471-DH_T_ITS_AI_THT/issues/1) | `backend/tests/test_parse.py`, `test_verify_integration.py` | |
| 2 | "a lot of what we do is just... matching... My agents spend half their day doing what's essentially data entry verification." | Sarah Chen | FR-2 | US-1 | [#1](https://github.com/kimkight/26-DO-12891471-DH_T_ITS_AI_THT/issues/1) | `backend/tests/test_compare.py`, `test_verify_integration.py` | |
| 3 | "You need judgment." | Dave Morrison | FR-3 | US-2 | [#2](https://github.com/kimkight/26-DO-12891471-DH_T_ITS_AI_THT/issues/2) | `backend/tests/test_compare.py::TestOutcomeClassification` | [0004](adr/0004-fuzzy-matching-with-review-band.md) |
| 4 | "Just don't make my life harder in the process." | Dave Morrison | FR-10 | US-2 | [#2](https://github.com/kimkight/26-DO-12891471-DH_T_ITS_AI_THT/issues/2) | `frontend/src/__tests__/outcomes.test.tsx` | [0004](adr/0004-fuzzy-matching-with-review-band.md) |
| 5 | "the brand name was 'STONE'S THROW' on the label but 'Stone's Throw' in the application... it's obviously the same thing." | Dave Morrison | FR-4 | US-3 | [#3](https://github.com/kimkight/26-DO-12891471-DH_T_ITS_AI_THT/issues/3) | `backend/tests/test_compare.py::TestBrandName`, `test_verify_integration.py`; UAT row 2 | [0004](adr/0004-fuzzy-matching-with-review-band.md) |
| 6 | "It has to be exact. Like, word-for-word." | Jenny Park | FR-5 | US-4 | [#4](https://github.com/kimkight/26-DO-12891471-DH_T_ITS_AI_THT/issues/4) | `backend/tests/test_warning.py::TestWarningBody`; UAT rows 4, 5 | [0004](adr/0004-fuzzy-matching-with-review-band.md) |
| 7 | "I caught one last month where they used 'Government Warning' in title case instead of all caps. Rejected." | Jenny Park | FR-6 | US-5 | [#5](https://github.com/kimkight/26-DO-12891471-DH_T_ITS_AI_THT/issues/5) | `backend/tests/test_warning.py::TestWarningCapitalization`; UAT row 3 | [0004](adr/0004-fuzzy-matching-with-review-band.md) |
| 8 | "the 'GOVERNMENT WARNING:' part has to be in all caps and bold." Confirmed by 27 CFR 16.22(a)(2). | Jenny Park; eCFR | FR-6; OOS-4 | US-5 | [#5](https://github.com/kimkight/26-DO-12891471-DH_T_ITS_AI_THT/issues/5) | `backend/tests/test_warning.py::TestBoldTypeIsNeverClaimed`; UAT row 15 | [0004](adr/0004-fuzzy-matching-with-review-band.md) |
| 9 | Sample label: "45% Alc./Vol. (90 Proof)", "750 mL" | Technical Requirements | FR-7 | US-6 | [#6](https://github.com/kimkight/26-DO-12891471-DH_T_ITS_AI_THT/issues/6) | `backend/tests/test_compare.py::TestAlcoholContentComparison`, `TestNetContents`; UAT rows 7, 8, 18, 20 | |
| 9a | "ABV is correct? Check." Tolerances in 27 CFR 5.65, 4.36, 7.65 govern actual against labeled content, so none applies to two declared values. | Sarah Chen; eCFR | FR-7; A-12 | US-6 | [#6](https://github.com/kimkight/26-DO-12891471-DH_T_ITS_AI_THT/issues/6) | `backend/tests/test_compare.py::TestAlcoholContentComparison`; UAT rows 18, 19, 20, 21 | |
| 9b | Net contents in different units are not converted; standards of fill are not validated. | FR-7; A-13 | FR-7; A-13 | US-6 | [#6](https://github.com/kimkight/26-DO-12891471-DH_T_ITS_AI_THT/issues/6) | `backend/tests/test_compare.py::TestNetContents`; UAT row 22 | |
| 10 | "if an agent can't read the label they just reject it and ask for a better image." | Jenny Park | FR-9 | US-7 | [#7](https://github.com/kimkight/26-DO-12891471-DH_T_ITS_AI_THT/issues/7) | `backend/tests/test_api_validation.py`; UAT row 6 | |
| 11 | "If we can't get results back in about 5 seconds, nobody's going to use it. We learned that the hard way." | Sarah Chen | NFR-1 | US-8 | [#8](https://github.com/kimkight/26-DO-12891471-DH_T_ITS_AI_THT/issues/8) | `backend/tests/test_verify_integration.py`, `scripts/measure.py`; UAT row 11 | [0002](adr/0002-compute-ecs-fargate-not-app-runner.md) |
| 12 | "big importers who dump 200, 300 label applications on us at once... we literally have to process them one at a time." | Sarah Chen | FR-8 | US-9 | [#9](https://github.com/kimkight/26-DO-12891471-DH_T_ITS_AI_THT/issues/9) | `backend/tests/test_batch.py::TestOverCount`, `TestEveryLineIdentifiesItsLabel`, `TestTheGeneratedSampleSet`; UAT row 9 | [0006](adr/0006-batch-execution-model.md) |
| 13 | "Janet from our Seattle office has been asking about this for years." | Sarah Chen | FR-8; ~~A-14~~ superseded by ADR 0009 | US-9 | [#9](https://github.com/kimkight/26-DO-12891471-DH_T_ITS_AI_THT/issues/9), [#70](https://github.com/kimkight/26-DO-12891471-DH_T_ITS_AI_THT/issues/70) | `backend/tests/test_batch.py::TestPairing`, `TestUnusableSubmissions`, `TestThePairingRule` | [0006](adr/0006-batch-execution-model.md), [0009](adr/0009-batch-cola-documents.md) |
| 14 | Batch resilience implied by the 300-label scenario | Sarah Chen | FR-8, FR-9 | US-10 | [#10](https://github.com/kimkight/26-DO-12891471-DH_T_ITS_AI_THT/issues/10) | `backend/tests/test_batch.py::TestOneBadItemDoesNotFailTheBatch`; UAT rows 10, 38, 39 | [0006](adr/0006-batch-execution-model.md), [0009](adr/0009-batch-cola-documents.md) |
| 15 | Batch scale implies visible progress | Sarah Chen | NFR-2 | US-11 | [#11](https://github.com/kimkight/26-DO-12891471-DH_T_ITS_AI_THT/issues/11) | `backend/tests/test_batch.py::TestEveryLineIdentifiesItsLabel` (the NDJSON framing and the index and total each line carries) | [0006](adr/0006-batch-execution-model.md) |
| 16 | "We need something my mother could figure out; she's 73..." and "Clean, obvious, no hunting for buttons." | Sarah Chen | NFR-4 | US-12 | [#12](https://github.com/kimkight/26-DO-12891471-DH_T_ITS_AI_THT/issues/12) | `frontend/tests/a11y.spec.ts` (the primary task is on the landing page), `frontend/src/__tests__/liveRegion.test.tsx`; UAT row 14 | |
| 17 | "The agents really vary in their tech comfort level... half our team is over 50." | Sarah Chen | NFR-4, NFR-5 | US-12, US-13 | [#12](https://github.com/kimkight/26-DO-12891471-DH_T_ITS_AI_THT/issues/12), [#13](https://github.com/kimkight/26-DO-12891471-DH_T_ITS_AI_THT/issues/13) | `frontend/tests/a11y.spec.ts` (axe-core and the keyboard walk), `frontend/src/__tests__/contrast.test.ts`; UAT rows 12, 13 | |
| 18 | "our network blocks outbound traffic to a lot of domains... half their features didn't work because our firewall blocked connections to their ML endpoints." | Marcus Williams | NFR-3 | US-14 | [#14](https://github.com/kimkight/26-DO-12891471-DH_T_ITS_AI_THT/issues/14) | `backend/tests/test_verify_integration.py::TestEgressBlocked`; UAT row 16 | [0003](adr/0003-local-ocr-default-bedrock-optional.md) |
| 19 | "We're not storing anything sensitive for this exercise." | Marcus Williams | NFR-6 | US-15 | [#15](https://github.com/kimkight/26-DO-12891471-DH_T_ITS_AI_THT/issues/15) | `backend/tests/test_verify_integration.py::TestNothingIsPersisted`, `TestNothingSensitiveReachesTheLogs`; UAT row 17 | |
| 20 | "there's PII considerations, document retention policies, the usual federal compliance stuff." | Marcus Williams | NFR-6, NFR-7 | US-15, US-16 | [#15](https://github.com/kimkight/26-DO-12891471-DH_T_ITS_AI_THT/issues/15), [#16](https://github.com/kimkight/26-DO-12891471-DH_T_ITS_AI_THT/issues/16) | `backend/tests/test_verify_integration.py::TestNothingSensitiveReachesTheLogs`, `backend/tests/test_api_validation.py` | |
| 21 | "Deployed Application URL: Working prototype we can access and test." | Deliverables | NFR-9 | US-17 | [#17](https://github.com/kimkight/26-DO-12891471-DH_T_ITS_AI_THT/issues/17) | CI: container health probe; `terraform fmt -check` and `terraform validate` over `infra/terraform/`. Applied to an AWS account and deployed: ECS Fargate behind an ALB in `us-east-1`, deployed by image digest by `.github/workflows/deploy.yml`, run 3 green | [0001](adr/0001-cloud-platform-aws.md), [0002](adr/0002-compute-ecs-fargate-not-app-runner.md) |
| 22 | "Code quality and organization" | Evaluation Criteria | NFR-8 | US-18 | [#18](https://github.com/kimkight/26-DO-12891471-DH_T_ITS_AI_THT/issues/18) | CI: `backend`, `frontend`, `audit`, `container` jobs | [0005](adr/0005-git-flow-branching.md) |
| 23 | "don't get me started on the FedRAMP certification process. Took 18 months just for the paperwork." | Marcus Williams | NFR-10 | US-19 | [#19](https://github.com/kimkight/26-DO-12891471-DH_T_ITS_AI_THT/issues/19) | Not written: no test can demonstrate portability without applying in a second region | [0001](adr/0001-cloud-platform-aws.md), [0002](adr/0002-compute-ecs-fargate-not-app-runner.md) |
| 24 | "We're on Azure now after the migration in 2019." | Marcus Williams | Recorded as OQ-1, not a requirement | | | | [0001](adr/0001-cloud-platform-aws.md) |
| 25 | "we're not looking to integrate with COLA directly." | Marcus Williams | OOS-1 | | | | |
| 26 | "README with setup and run instructions... Brief documentation of approach, tools used, assumptions made." | Deliverables | SC-5, SC-6 | US-20 | [#20](https://github.com/kimkight/26-DO-12891471-DH_T_ITS_AI_THT/issues/20) | Not written | |
| 27 | "Correctness and completeness of core requirements" | Evaluation Criteria | NFR-1, NFR-8 | US-21 | [#21](https://github.com/kimkight/26-DO-12891471-DH_T_ITS_AI_THT/issues/21) | Not written; accuracy tier | |
| 28 | "labels that are photographed at weird angles, or the lighting is bad, or there's glare... maybe out of scope for a prototype." | Jenny Park | SG-1, stretch | | | `backend/tests/test_ocr.py::TestExifOrientation`, `TestCardinalOrientation`, `TestWhyOrientationUsesOsd`; UAT rows 23, 24 | [0003](adr/0003-local-ocr-default-bedrock-optional.md) |
| 28a | First real-artwork test, 2026-08-26: a photograph of a real bottle returned none of the five fields. Sideways, EXIF-tagged, and a warning hyphenated across a narrow column. | Author's own test against the deployed URL | FR-1, FR-5; A-15 | US-1, US-4 | [#1](https://github.com/kimkight/26-DO-12891471-DH_T_ITS_AI_THT/issues/1), [#4](https://github.com/kimkight/26-DO-12891471-DH_T_ITS_AI_THT/issues/4) | `backend/tests/test_warning.py::TestHyphenationAcrossLineBreaks`, `backend/tests/test_verify_integration.py::TestASidewaysPhotograph`, `TestAHyphenatedWarningColumn`, `backend/tests/test_samples.py::TestTheHyphenatedColumnIsTheRegulationsText`; UAT rows 23, 24, 25 | [0003](adr/0003-local-ocr-default-bedrock-optional.md) |
| 28b | "labels that are photographed at weird angles" plus 27 CFR 16.21 allowing the warning on "a back or side label": a label wraps a round bottle, so no one photograph shows it flat. | Jenny Park; eCFR; the author's first real-artwork test | FR-1, FR-9; A-16 | US-22 | [#61](https://github.com/kimkight/26-DO-12891471-DH_T_ITS_AI_THT/issues/61) | `backend/tests/test_multi_photo.py` (all eight classes), `frontend/src/__tests__/multiPhoto.test.tsx`, `frontend/tests/a11y.spec.ts` (the photo controls by keyboard, and axe over a two-photo result); UAT rows 26, 27, 28, 29 | [0007](adr/0007-multi-photo-single-label.md) |
| 28c | Deployed-target test, 2026-08-27: a three-photograph bottle check reported the alcohol content as `7%`, read from marketing copy on the back label about reducing environmental impact. | Author's own test against the deployed URL | FR-1, FR-7 | US-1, US-6 | [#6](https://github.com/kimkight/26-DO-12891471-DH_T_ITS_AI_THT/issues/6) | `backend/tests/test_parse.py::TestAlcoholContentNeedsAnAlcoholMarker`; UAT row 30 | |
| 28d | "Why do I have to enter in all this information?" The values the form asks an agent to type are the values the applicant already submitted on TTB F 5100.31. | The author's own use of the deployed prototype, 2026-08-27 | FR-11; A-17; OOS-1 (boundary recorded, not narrowed) | US-23 | [#65](https://github.com/kimkight/26-DO-12891471-DH_T_ITS_AI_THT/issues/65) | `backend/tests/test_application_form.py` (all six classes), `backend/tests/test_cola_document_api.py`, `frontend/src/__tests__/applicationUpload.test.tsx`, `frontend/tests/a11y.spec.ts` (the upload by keyboard and axe over a filled form); UAT rows 31 to 35 | [0008](adr/0008-cola-form-as-application-input.md) |
| 28e | Deployed-target test, 2026-08-28: a Registry printout captioned `Class/Type Description:` gave the class or type as `Description: Kentucky Straight Bourbon Whiskey`. The caption pattern matched `Class/Type` and left the rest of the caption in the value. | Author's own test against the deployed URL | FR-11; A-17 | US-23 | [#65](https://github.com/kimkight/26-DO-12891471-DH_T_ITS_AI_THT/issues/65) | `backend/tests/test_application_form.py::TestARegistryPrintoutWithDescriptiveCaptions`, `::TestCaptionResidueInGeneral`; UAT row 36 | [0008](adr/0008-cola-form-as-application-input.md) |
| 28f | "Why are we assuming the batch is a CSV? Where would these CSVs even come from?" A-14 answered it: "No source states this format; it is assumed." What an importer files is a COLA form plus label images, and FR-11 can read that form. | The author's own question, 2026-08-28 | FR-8 (contract rewritten); FR-11; A-14 superseded | US-9 | [#70](https://github.com/kimkight/26-DO-12891471-DH_T_ITS_AI_THT/issues/70) | `backend/tests/test_batch.py` (all seven classes), `backend/tests/test_multi_photo.py::TestTheBatchPathIsUnaffected`, `frontend/src/__tests__/batchTable.test.tsx`, `frontend/tests/a11y.spec.ts`; UAT rows 37 to 40 | [0009](adr/0009-batch-cola-documents.md) |
| 28g | The author's review of the deployed page, 2026-08-28: it reads as a published form rather than as a working instrument. Reference vocabulary transcribed from a product walked through the same day, with the government palette substituted for its colours. | Author's own review | FR-10, NFR-4, NFR-5 (presentation; no requirement changed) | US-2, US-12, US-13 | [#2](https://github.com/kimkight/26-DO-12891471-DH_T_ITS_AI_THT/issues/2), [#12](https://github.com/kimkight/26-DO-12891471-DH_T_ITS_AI_THT/issues/12) | `frontend/src/__tests__/contrast.test.ts` (the palette, against the new tokens), `branding.test.tsx`, `outcomes.test.tsx`, `frontend/tests/a11y.spec.ts` (axe, the keyboard walk, the scan frame, the bundled font); UAT rows 41 to 45 | |
| 29 | "I've seen a lot of these 'modernization' projects come and go." | Dave Morrison | Adoption risk; drives NFR-4 and FR-3 | US-12, US-2 | [#12](https://github.com/kimkight/26-DO-12891471-DH_T_ITS_AI_THT/issues/12), [#2](https://github.com/kimkight/26-DO-12891471-DH_T_ITS_AI_THT/issues/2) | UAT row 14 | [0004](adr/0004-fuzzy-matching-with-review-band.md) |

## 2. Requirement coverage

Every requirement maps to at least one story. No orphans.

| Requirement | Stories | Issues | Implemented | Tested |
| --- | --- | --- | --- | --- |
| FR-1 Field extraction, including the A-15 orientation rule and the A-16 multi-photograph rule | US-1, US-22 | #1, #61 | **Yes**: `app/ocr.py`, `app/parse.py`, `app/verify.py` `verify_photos` | **Yes**: `test_parse.py`, `test_ocr.py`, `test_verify_integration.py`, `test_multi_photo.py` |
| FR-2 Comparison against application data | US-1 | #1 | **Yes**: `app/api.py` `build_result` | **Yes**: `test_compare.py`, `test_verify_integration.py` |
| FR-3 Three-outcome result | US-1, US-2 | #1, #2 | **Yes**: `app/compare.py`, `app/schemas.py` | **Yes**: `test_compare.py::TestOutcomeClassification` |
| FR-4 Case and punctuation tolerance | US-3 | #3 | **Yes**: `app/compare.py` `normalize_text` | **Yes**: `test_compare.py::TestNormalization`, `TestBrandName` |
| FR-5 Warning exact text, including the A-15 hyphenation rule | US-4 | #4 | **Yes**: `app/warning.py` | **Yes**: `test_warning.py::TestWarningBody`, `TestHyphenationAcrossLineBreaks` |
| FR-6 Warning capitalization | US-5 | #5 | **Yes**: `app/warning.py` | **Yes**: `test_warning.py::TestWarningCapitalization`, `TestBoldTypeIsNeverClaimed` |
| FR-7 Numeric comparison, including the A-12 ABV rule, the A-13 net contents rule, and the alcohol-marker rule for locating the ABV on the label | US-6 | #6 | **Yes**: `app/compare.py` `compare_abv`, `compare_net_contents`; `app/parse.py` `is_alcohol_content_line` | **Yes**: `test_compare.py::TestAlcoholContentComparison`, `TestNetContents`, `test_parse.py::TestAlcoholContentNeedsAnAlcoholMarker` |
| FR-8 Batch verification, label images paired with COLA documents by filename stem (ADR 0009) | US-9, US-10 | #9, #10, #70 | **Yes**: `app/batch.py` (`pairing_stem`, `collect_documents`, the per-row pairing errors), `app/api.py` `verify_batch`, and the pairing rule stated and counted in `frontend/src/lib/pairing.ts` and `BatchTab.tsx`. One photograph per label: ADR 0007 does not extend to the batch path, and the FR-8 notes say why | **Yes**: `test_batch.py`, 34 tests, plus `test_multi_photo.py::TestTheBatchPathIsUnaffected` and the batch assertions in `frontend/tests/a11y.spec.ts` |
| FR-9 Error handling | US-7, US-10, US-22 | #7, #10, #61 | **Yes**: single label in `app/api.py`, per row in `app/batch.py`, per photograph in `app/verify.py`, and every rejection in one shape via the handlers in `app/main.py` | **Yes**: `test_api_validation.py`, `test_batch.py`, `test_multi_photo.py` |
| FR-10 Result presentation | US-2, US-22 | #2, #61 | **Yes**: `frontend/src/components/`, five result cards with value, value, outcome and reason, plus a per-photograph note and the photograph each value was read from | **Yes**: `outcomes.test.tsx`, `batchTable.test.tsx`, `multiPhoto.test.tsx` |
| FR-11 The label application as the input, with typing as the fallback, including the A-17 field map | US-23, US-24, US-9 | #65, #74, #70 | **Yes**: `app/application_form.py`, `POST /api/read-application` and the optional `application_document` part on `POST /api/verify`, plus the upload and per-field marks in `frontend/src/components/ApplicationUpload.tsx` and `SingleLabelTab.tsx`. **And on the batch path**, where every row's application values are read off that row's paired COLA document (ADR 0009) | **Yes**: `test_application_form.py` (including `TestARegistryPrintoutWithDescriptiveCaptions` and `TestCaptionResidueInGeneral`), `test_cola_document_api.py`, `test_batch.py::TestWhatTheDocumentSupplied` (the batch path, ADR 0009), `applicationUpload.test.tsx`, `applicationFirst.test.tsx` (the collapsed default and the three expansion cases), `a11y.spec.ts`. **Against documents generated at test time only**: no real filed application or Registry printout has been parsed (OQ-22) |
| NFR-1 About 5 seconds | US-8, US-21 | #8, #21 | **Yes**: measured end to end and reported in the response. **Measured on the deployed target 2026-08-28**, build `sha-f66a4e2`, 1 vCPU and 8 GiB on Fargate behind the ALB: one label with its COLA document, 1.5 s end to end and 1.4 s inside the checker, which meets the roughly five second target with margin. Three photographs of one round bottle measured 7.8 s on the same day, which is over it; recorded rather than tuned away, `docs/09_DEPLOYMENT.md` section 9 | **Yes**: `test_verify_integration.py`, `scripts/measure.py` |
| NFR-2 Batch throughput | US-11 | #11 | **Yes**: bounded pool, NDJSON stream, per-row errors, no job store. **Measured at the cap on the deployed target 2026-08-28**: 300 labels with 300 paired COLA documents in one submission finished in approximately 6.5 to 7 minutes, roughly 1.3 s per label, 300 of 300 rows returned, no timeout and no lost work. Progress was visible throughout, 83 rows complete at the 109 second mark observed live, so the ALB did not buffer the stream | Partial: `test_batch.py` covers per-row isolation and the progress fields. The 300-label run is a measurement recorded in `docs/09_DEPLOYMENT.md` section 9, not an automated test. |
| NFR-3 No outbound calls | US-14 | #14 | **Yes**: local OCR only; `external_call_made` on every response | **Yes**: `test_verify_integration.py` |
| NFR-4 Simplicity | US-12, US-24 | #12, #74 | **Yes**: one screen, primary task on the landing page, plain-language errors, and the application document rather than five empty boxes as the first application-side input, with the typed fields behind a disclosure | **Yes**: `a11y.spec.ts`, `liveRegion.test.tsx`, `applicationFirst.test.tsx` |
| NFR-5 Accessibility | US-13, US-24 | #13, #74 | **Yes**: labelled inputs, keyboard reachable, visible focus, verified contrast, live region; the disclosure reports its expanded state and its auto-expansion is announced | **Yes**: axe-core against the built page in CI, collapsed and expanded, plus `contrast.test.ts`, a keyboard walk and `applicationFirst.test.tsx` |
| NFR-6 No persistence | US-15 | #15 | **Yes**: in-memory only, multipart spool threshold raised so no upload reaches disk | **Yes**: `test_verify_integration.py::TestNothingIsPersisted` |
| NFR-7 Input validation | US-16 | #16 | **Yes**: size in middleware before the body is read, MIME before decoding | **Yes**: `test_api_validation.py` |
| NFR-8 Code quality gates | US-18 | #18 | **Yes** | CI |
| NFR-9 Deployability | US-17 | #17 | **Yes**: `infra/terraform/` builds the ECR repository, ECS cluster and Fargate service, ALB, log group and IAM roles; it has been applied to an AWS account and `.github/workflows/deploy.yml` deploys by image digest, run 3 green. The prototype is reachable at the load balancer's address. | CI container job; `infrastructure format and validate` job (`terraform fmt -check`, `terraform validate`); the deploy workflow's own health check |
| NFR-10 Government-region portability | US-19 | #19 | Partial, and honestly partial: the Terraform follows the portability rules (partition from `data.aws_partition`, availability zones from a data source, no hardcoded account or region) in `infra/terraform/providers.tf` and `iam.tf`, and only FedRAMP in-scope services are used. It now applies cleanly in one commercial region, `us-east-1`. **Portability is still argued rather than demonstrated: no apply has been run in a government region.** An Azure target would need a provider module this repository does not contain. | No. One commercial apply is evidence the configuration is applyable, not that it is portable |
| NFR-11 Environment configuration | US-15, US-17 | #15, #17 | **Yes** | No |

## 3. Coverage summary

| Measure | Count |
| --- | --- |
| Requirements defined | 22 (11 functional, 11 non-functional) |
| Requirements traced to a story | 22 of 22 |
| Requirements traced to a GitHub issue | 22 of 22 |
| Requirements fully implemented | 21 of 22 |
| Requirements with an automated test | 19 of 22 |
| User stories | 24 |
| Stories with acceptance criteria | 24 of 24 |
| ADRs | 9 |

The two counts are read off the section 2 table by one rule each, so they can be
checked rather than taken. "Fully implemented" counts rows whose Implemented
column says **Yes**; the one that does not is NFR-10, which is portability
argued rather than demonstrated. "With an automated test" counts rows whose
Tested column names a test or a CI job; the three that do not are NFR-2, which
is covered only in part, and NFR-10 and NFR-11, which have none.

The gap between "traced" and "tested" is the honest state of this repository.
The verification engine, single label and batch (FR-1 through FR-9 and FR-11,
NFR-1, NFR-2, NFR-3, NFR-6, NFR-7), is built and covered by 264 backend tests.
The agent-facing interface (FR-10, FR-11, NFR-4, NFR-5) is built and covered by
174 component tests, a computed-contrast test over the palette, and an axe-core
run with a keyboard walk against the built page in CI. It is deployed: ECS Fargate behind an
Application Load Balancer in `us-east-1`, deployed by image digest.

What deployment did not settle is accuracy on real artwork. The first
photograph of a real bottle submitted to the deployed prototype returned none
of its five fields. Two of the three causes are fixed and recorded as
assumption A-15; the third, that a label wrapping a round bottle is never flat
in one photograph, is not corrected, and is recorded as OQ-21.
[ADR 0007](adr/0007-multi-photo-single-label.md) works around it by accepting up
to three photographs of one label rather than modelling the geometry of one, and
that distinction is stated there rather than blurred.

**Both limits on the NFR-2 claim are closed by measurement.** A 300-label
batch has now been run at the configured cap, on the deployed target rather than
on a session runner, so the scaling to 300 is a measurement rather than
arithmetic. And the second NFR-2 criterion, that progress is observable rather
than presenting as a frozen page, is met end to end and was watched end to end:
the stream carries the position and the total on every line, the batch tab
renders them as a progress indicator driven by the stream rather than by an
animation, and 83 of 300 rows were complete at the 109 second mark of the live
run.

Accuracy and latency have been measured over the synthetic sample set, now on
the deployed target, not over real label artwork. Per-field accuracy against
real artwork remains unmeasured and is the largest open technical risk in the
prototype (ADR 0003). The one real-artwork submission on 2026-08-28 is the
evidence for that rather than against it: three phone photographs of a round
bottle left the brand name and the class or type unreadable.

### Definition of Done, the two items that are measurements

The prototype-level Definition of Done is section 4 of
[02_PROJECT_SCOPE.md](02_PROJECT_SCOPE.md). Two of its items are satisfied by a
measurement rather than by code, so they are traced here with the run that
satisfied them.

| DoD item | State | Evidence |
| --- | --- | --- |
| 7. Single-label end-to-end latency is measured and reported against the 5-second target, on stated hardware with a stated sample | **Met.** 1.5 s end to end and 1.4 s inside the checker for one label with its COLA document | Measured 2026-08-28 on the deployed target, build `sha-f66a4e2`, 1 vCPU and 8 GiB on Fargate behind the ALB in `us-east-1`, over the synthetic 1200x1600 fixture rotated 90 degrees. Reported in the README under Measured performance and accuracy and recorded in [09_DEPLOYMENT.md](09_DEPLOYMENT.md) section 9. The three-photograph case, 7.8 s, is reported alongside it because it is over the target |
| 9. Accuracy is measured per field against the labeled sample set with ground truth, and the numbers are published in the README. Measured, not asserted | **Met on the self-built sample, and the README says so in those words.** 300 of 300 outcomes correct: 270 matching, 30 not matching, 0 needing review, 0 unreadable, where the 30 were exactly the 30 seeded ABV defects. Every seeded defect caught, no false alarms | Measured 2026-08-28 on the deployed target in the 300-label batch run. Published in the README under Measured performance and accuracy, with the qualification that a self-built sample is not the real application population, per section 5 of [02_PROJECT_SCOPE.md](02_PROJECT_SCOPE.md) |

## 4. Open questions blocking requirements

| Open question | Blocks |
| --- | --- |
| OQ-7 Section 508 applicability | NFR-5 acceptance, US-13 |
| OQ-8 accuracy target | US-21 acceptance |
| OQ-9 threshold defaults | FR-3 tuning |

OQ-6 and OQ-16 no longer appear in this table. Both were closed by
[ADR 0006](adr/0006-batch-execution-model.md): OQ-6 by the decision that batch
verification is a single synchronous streaming request with a bounded worker
pool and no job store, and OQ-16 by the CSV contract recorded as assumption
A-14. Note what OQ-6 could not be given: no source states a batch latency
target, so the ADR optimizes for the properties NFR-2 does state, which are not
losing completed work and showing visible progress.

**OQ-16 was closed by an assumption, and the assumption was wrong.**
[ADR 0009](adr/0009-batch-cola-documents.md) supersedes A-14 on 2026-08-28: a
batch is label images plus one COLA document per label, paired by filename stem,
and the CSV is removed. OQ-16 stays closed, by a document that exists rather
than a format that did not. What remains genuinely open is what an importer's
bulk submission looks like as files on a disk, and whether pairing on a name is
what an agent would expect; that is recorded in
[OPEN_QUESTIONS.md](OPEN_QUESTIONS.md).

OQ-13 no longer appears in this table either. It was closed on 2026-08-24 by
the author's deployment decisions, and item 6, ECS task sizing, was the item
that interacted with the streaming design: the task is 1 vCPU and 8 GiB, the
batch caps are set to what that memory holds, and the load balancer's idle
timeout is set above a full batch's duration. The arithmetic is
[09_DEPLOYMENT.md](09_DEPLOYMENT.md) section 4. NFR-9's acceptance is now met:
the infrastructure has been applied and the prototype is reachable.

OQ-4 and OQ-5 no longer appear in this table. They are closed by assumptions
A-12 and A-13 in [ASSUMPTIONS.md](ASSUMPTIONS.md), and the rules they settle are
stated in the FR-7 acceptance criteria in
[03_REQUIREMENTS.md](03_REQUIREMENTS.md). OQ-1 is answered by
[ADR 0001](adr/0001-cloud-platform-aws.md) as the author's decision, not as a
stakeholder answer. Reasoning and sources for all three:
[cloud_choice_and_abv_assumption.md](cloud_choice_and_abv_assumption.md).

OQ-22 is opened by this session rather than closed by it. FR-11 reads the
applicant's label application instead of asking an agent to retype it, and the
item map it uses is read off the blank TTB F 5100.31 (04/2023) rather than
recalled. What has not been done is running the parser over a real filed
application or a real Public COLA Registry printout, because both are real
applicants' records and the no-personal-data rule forbids committing one as a
fixture. It blocks nothing: every parsed value is shown for confirmation in an
editable field before a check runs, so an unrecognized caption costs an agent
the typing they were already doing.

## 5. Maintenance

This file is updated in the same commit as any change to a requirement, story,
or test, per the pull request checklist in
[08_SDLC_PROCESS.md](08_SDLC_PROCESS.md) section 4. A traceability matrix
updated separately from the change it describes is already wrong.
