# TTB Label Verifier

[![ci](https://github.com/kimkight/26-DO-12891471-DH_T_ITS_AI_THT/actions/workflows/ci.yml/badge.svg?branch=develop)](https://github.com/kimkight/26-DO-12891471-DH_T_ITS_AI_THT/actions/workflows/ci.yml)

A prototype that compares the text on alcohol beverage label artwork against the
data submitted in the corresponding application, and returns a per-field verdict
of match, needs human review, or mismatch. It is built for compliance agents who
today check brand name, class and type, alcohol content, net contents, and the
government warning statement by eye, and it is designed around the constraint
that made a previous vendor pilot fail: results have to come back in about five
seconds, or agents go back to doing it manually.

**Author:** Kimberly D. Kight

> **Status: the prototype works, is deployed, and has been measured on the
> deployed target. Accuracy on real label artwork is still the open question.**
> Single-label and batch verification and the agent-facing interface are built,
> tested, and running on ECS Fargate behind an Application Load Balancer in
> `us-east-1`, deployed by image digest.
>
> The first measurements against the deployed URL were taken on 2026-08-28 and
> are in [Measured performance and accuracy](#measured-performance-and-accuracy)
> below. A single label image comes back in 1.5 seconds and a batch of 300
> finishes in under seven minutes, both through the load balancer. A COLA
> document submitted alone came back in **5.0 seconds** on 2026-08-30 against
> deploy #12, which is NFR-1's roughly five seconds **at the line rather than
> under it**. The extra second and a half over the 3.5 s the same document
> measured against deploy #11 is the 180-degree orientation check, and it is
> the reason the readings are right at all: it is a real trade and the section
> below states it rather than smoothing it over. What those runs did not
> settle is accuracy on real label artwork: three phone photographs of a round
> bottle still leave the brand and the class unreadable on curved glass, which is
> the residual [ADR 0007](docs/adr/0007-multi-photo-single-label.md) works around
> rather than solves. See [Status](#status) below for exactly what works and
> [Known limitations](#known-limitations) for what the measurements do not cover.

## Repository map

| Path | Contents |
| --- | --- |
| `backend/` | FastAPI application, Python 3.11. The verification engine and both endpoints. |
| `frontend/` | React and TypeScript, built with Vite. The agent-facing interface. |
| `docs/` | Charter, scope, requirements, stories, architecture, security, test strategy, SDLC process, deployment outline. |
| `docs/adr/` | Architecture decision records. |
| `samples/` | Twelve label specifications, the renderer that draws them, and the ground truth CSVs. Images are generated locally and git-ignored. |
| `scripts/` | `measure.py`, which runs the engine over the sample set and reports per-field accuracy and latency. |
| `infra/terraform/` | Terraform for the deployed stack: ECR, ECS on Fargate, ALB, CloudWatch Logs, IAM, and the GitHub OIDC deploy role. |
| `.github/` | CI and deployment workflows, issue and pull request templates, CODEOWNERS, Dependabot. |
| `Dockerfile` | Multi-stage build: frontend, then backend. Runs as a non-root user. |

## Quick start

Requires Docker with the Compose plugin.

```bash
git clone https://github.com/kimkight/26-DO-12891471-DH_T_ITS_AI_THT.git
cd 26-DO-12891471-DH_T_ITS_AI_THT
docker compose up -d --build
curl http://localhost:8000/api/health
```

Expected response:

```json
{"status":"ok","service":"TTB Label Verifier","version":"1.1.0","environment":"local"}
```

The interface is at <http://localhost:8000/>. The first tab checks one label:
choose a label image, attach the applicant's COLA document, and select **Check
this label**. The document is the normal way the application values arrive, and
the boxes for typing them yourself are behind **Or type the application
values**, which opens on its own when the document leaves a gap or cannot be
read. The second tab checks many at once,
taking the label images plus one COLA document for each, **paired by filename
stem**: `0001-stones-throw.png` goes with `0001-stones-throw.pdf`. The rule is
stated on the page, and the page says how many pairs it found before you submit.

To try it without artwork of your own, generate the sample set first:

```bash
python samples/generate_samples.py
```

That writes twelve labels into `samples/images/` and one COLA document per label
into `samples/applications/documents/`, already named to pair with them, which
is exactly what the batch tab expects.

Stop with `docker compose down`.

### Running the backend without Docker

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install --require-hashes -r requirements-dev.lock
pip install --no-deps -e .
pytest
uvicorn app.main:app --reload
```

### Running the frontend dev server

```bash
cd frontend
npm ci
npm run dev
```

The dev server proxies `/api` to `http://localhost:8000`, so run the backend
alongside it.

The frontend checks are `npm run lint`, `npm run test` (component tests) and
`npm run test:a11y` (axe-core against the built page, which needs `npm run
build` first and downloads Chromium on its first run).

## Approach

**Extraction runs locally.** OCR happens inside the container with Tesseract and
OpenCV, making no outbound network calls on the default path. This is not a
performance preference; the agency network "blocks outbound traffic to a lot of
domains," and a previous vendor pilot lost half its features to exactly that.
An optional vision-model fallback on Amazon Bedrock exists but is **off unless
explicitly enabled**. See
[ADR 0003](docs/adr/0003-local-ocr-default-bedrock-optional.md).

**Matching has three outcomes, not two.** Fields are compared with normalized
fuzzy matching and land on match, needs human review, or mismatch. The middle
outcome exists because a senior agent's governing example, `STONE'S THROW` on
the label against `Stone's Throw` in the application, is neither a clean match
nor a defensible rejection. Rather than encode that judgment call silently in a
threshold, the tool routes it to a person. See
[ADR 0004](docs/adr/0004-fuzzy-matching-with-review-band.md).

**The government warning is the exception.** It is compared for exact text after
whitespace normalization, with a separate check that the `GOVERNMENT WARNING:`
prefix is upper case. The reference text is quoted verbatim from 27 CFR 16.21,
fetched from eCFR and cited in
[docs/03_REQUIREMENTS.md](docs/03_REQUIREMENTS.md).

**A batch is one streaming request, not a job queue.** Up to 300 label images
and their 300 COLA documents go in a single submission; a bounded worker pool
reads them and each result is written to the response as it finishes, so
progress is visible while the batch runs and one unreadable image costs only its
own row. There is no job store, because nothing is persisted. See
[ADR 0006](docs/adr/0006-batch-execution-model.md).

**A batch takes what an importer actually files.** It used to take a CSV of
application data, keyed by image filename, assumed rather than stated by any
source. Nothing produces such a file: what an importer files with TTB is, per
application, a COLA form plus label images. So a batch is now the images plus
one COLA document each, paired by filename stem, read by the same parser the
single-label view uses. The CSV is gone rather than kept alongside. See
[ADR 0009](docs/adr/0009-batch-cola-documents.md).

**The interface is one screen, and it starts from the document.** The primary
task is on the landing page with nothing to navigate, every outcome is carried by
a word and a shape before it is carried by a colour, and the field needing a
human's attention is the one that looks unfinished. The agent checking a label is
normally holding the applicant's COLA document, so that document is the first
application-side thing on the page and the five boxes for typing the same values
sit behind a disclosure, opening when the agent asks or when the document leaves
a gap or cannot be read. The batch tab has worked this way since ADR 0009; the
single-label tab now does too. The requirement behind it is a stakeholder's, not a
designer's: "clean, obvious, no hunting for buttons," for a team where technology
comfort varies widely.

**It uses the government palette, and it says plainly that it is not an official
system.** Navy and a gold accent, because the tool is about federal label
compliance and a prototype with a brand of its own would answer the wrong
question about whether it belongs in this workflow. The surface around that
palette is a soft, modern one: white cards with generous radii and layered
shadows over a muted blue-grey field, a segmented pill control, soft-tinted
inputs, and the chosen photograph previewed inside a scan frame.

The line between reflecting a design language and impersonating an agency is
drawn at the seal and at claims of officialdom, and it is drawn in tests rather
than left to judgement. A banner is the first thing on every view: "Prototype
built for an employment assessment. Not an official TTB or Treasury system.
Nothing you upload is stored." The footer names the author and the assignment.
There is no TTB seal, no Treasury seal, no eagle, and no "official website of
the United States government" banner anywhere in the repository, and
`frontend/src/__tests__/branding.test.tsx` fails if one is added.

**The tool recommends; the agent decides.** Nothing here issues an approval or a
rejection, and every result carries the label value, the application value, and
the score so an agent can overrule it. The interface says so on screen, beneath
the results, rather than only in this file. See
[docs/06_SECURITY_AND_COMPLIANCE.md](docs/06_SECURITY_AND_COMPLIANCE.md)
section 6.

## Tools used

| Layer | Choice |
| --- | --- |
| Backend | Python 3.11, FastAPI, uvicorn |
| Frontend | React 19, TypeScript, Vite |
| Typeface | Inter, under the SIL Open Font License 1.1. Bundled as a variable font and served from the application's own origin, never fetched from a CDN, because NFR-3 applies to the page as well as to the API |
| OCR | Tesseract via pytesseract, OpenCV for preprocessing |
| Matching | rapidfuzz |
| Container | Docker, multi-stage, non-root |
| Frontend testing | Vitest, React Testing Library, axe-core run in Chromium by Playwright |
| CI | GitHub Actions: ruff, pytest, eslint, prettier, vitest, axe-core, pip-audit, npm audit, Syft SBOM |
| Target platform | AWS ECS on Fargate behind an ALB, image in ECR, `us-east-1` |

## Documentation

| Document | What it covers |
| --- | --- |
| [01 Project Charter](docs/01_PROJECT_CHARTER.md) | Purpose, background, stakeholders, success criteria, constraints, deliverables |
| [02 Project Scope](docs/02_PROJECT_SCOPE.md) | In scope, out of scope, stretch goals, Definition of Done |
| [03 Requirements](docs/03_REQUIREMENTS.md) | FR-1 to FR-10, NFR-1 to NFR-11, with acceptance criteria; verbatim 27 CFR 16.21 and 16.22 |
| [04 User Stories](docs/04_USER_STORIES.md) | 24 stories across 6 epics, with Given/When/Then criteria |
| [05 Architecture](docs/05_ARCHITECTURE.md) | Context and container diagrams, request flows, data handling, configuration, government-region portability |
| [06 Security and Compliance](docs/06_SECURITY_AND_COMPLIANCE.md) | Threat model, controls, FedRAMP posture, ATO readiness, AI governance |
| [07 Test Strategy](docs/07_TEST_STRATEGY.md) | Unit, integration, accuracy, performance, accessibility, and a manual UAT checklist |
| [08 SDLC Process](docs/08_SDLC_PROCESS.md) | Phases with entry and exit criteria, Git Flow, PR checklist, DoR and DoD, releases |
| [09 Deployment](docs/09_DEPLOYMENT.md) | The author's runbook: commands, variables, task sizing, cost, post-deploy verification, teardown |
| [Open Questions](docs/OPEN_QUESTIONS.md) | 21 questions, 8 still open, each recorded rather than guessed |
| [Assumptions](docs/ASSUMPTIONS.md) | 16 inferences, each with what would confirm or falsify it |
| [Traceability Matrix](docs/TRACEABILITY_MATRIX.md) | Stakeholder statement to requirement to story to issue to test |
| [ADRs](docs/adr/) | Cloud platform, compute, extraction path, matching strategy, branching, batch execution model, more than one photograph of one label, the COLA document as application input, what a batch is made of, the label artwork embedded in that document, one upload sorted by the server, the government warning near miss, and item 5's product type read off the rendered page |
| [Contributing](CONTRIBUTING.md) | Branching, commits, local setup, review expectations |
| [Security Policy](SECURITY.md) | Reporting, scope, data handling |
| [Changelog](CHANGELOG.md) | Keep a Changelog format |

## Status

**Every functional requirement is built and tested, the prototype is deployed,
and the first figures measured on the deployed target are below.**

| Capability | State |
| --- | --- |
| `GET /api/health` | Works |
| `POST /api/verify` (one label against its application data) | Works: everything for one label goes in one repeated `files` part, and the server decides what each file is from the file rather than from the part it arrived in. The older `image` and `application_document` parts still work and go through the same classifier. See [ADR 0011](docs/adr/0011-one-upload.md). |
| `POST /api/classify` (sort an upload, read the application side, compare nothing) | Works: what each uploaded file was taken to be and why, plus the application values, so the interface can show both before a check runs. |
| `POST /api/verify-batch` (many labels, each paired with its COLA document by filename stem) | Works: a bounded worker pool, results streamed as newline-delimited JSON, no job store. See [ADR 0006](docs/adr/0006-batch-execution-model.md) for the stream and [ADR 0009](docs/adr/0009-batch-cola-documents.md) for what a batch carries. |
| `POST /api/read-application` (read one COLA document, compare nothing) | Works: reads an uploaded TTB F 5100.31 or Public COLA Registry printout locally, including the label artwork embedded in it ([ADR 0010](docs/adr/0010-embedded-label-artwork.md)), so an agent can attach the application instead of retyping it. Not COLA system integration: no API call, no credential, no lookup. See [ADR 0008](docs/adr/0008-cola-form-as-application-input.md) and the note under OOS-1 in [docs/02_PROJECT_SCOPE.md](docs/02_PROJECT_SCOPE.md). |
| Field extraction from label artwork | Works: `backend/app/ocr.py`, `backend/app/parse.py` |
| Comparison against application data | Works: `backend/app/compare.py` |
| Government warning checks, text and capitalization | Works: `backend/app/warning.py`. The comparison is exact; a difference of one or two characters is routed to human review with the character-level difference shown rather than reported as a mismatch, and is never a pass ([ADR 0012](docs/adr/0012-warning-near-miss.md)). |
| Verification interface, one label | Works: one screen, **one file picker** taking the label application, photographs of the label, or any mix, with the server deciding what each file is and saying so per file ([ADR 0011](docs/adr/0011-one-upload.md)); after an upload has been read, a line per value that was found and a field only for the ones that were not; five result cards, and a note saying what was read and how |
| Verification interface, values that were read | Works: each is a read-only line with where it came from, typed or the application form or the label artwork inside it. If every value was read, no editable field is shown at all; one collapsed disclosure holds them. A gap takes focus and is announced |
| Verification interface, batch | Works: a second tab taking label images and their COLA documents, the pairing rule stated on the page and the pair count announced, progress driven by the stream, a sortable results table, and a results CSV built in the browser. One photograph per label; see ADR 0007 and ADR 0009 |
| Prototype disclosure | Works: a persistent banner on every view, an author attribution in the footer, and no seal, emblem, or officialdom claim anywhere. Enforced by `frontend/src/__tests__/branding.test.tsx` |
| Accessibility, WCAG 2.1 AA target | Checked in CI by axe-core against the built page, plus a keyboard walk and a contrast check on the palette. See the limitation below on what a clean run does and does not claim. |
| One bad image failing only its own row in a batch | Works; covered by tests |
| Container build, non-root, health probe | Works; verified in CI |
| CI: lint, tests, dependency audit, container build, SBOM | Works |
| Infrastructure as code | Works: `infra/terraform/` builds the ECR repository, ECS cluster and Fargate service, load balancer, log group, and IAM roles including a GitHub OIDC deploy role. Format-checked and validated in CI, and applied to an AWS account in `us-east-1`. |
| Deployment workflow | Works. `workflow_dispatch` or a published release; builds, pushes to ECR, and deploys the image digest through OIDC with no static keys. |
| Deployed URL | Deployed: ECS Fargate behind an Application Load Balancer in `us-east-1`. The runbook is [docs/09_DEPLOYMENT.md](docs/09_DEPLOYMENT.md); the author applies and deploys from her own machine, and **nothing merged deploys itself**. |
| Accuracy and latency measurements | Measured on the deployed target on 2026-08-28, build `sha-f66a4e2`, over the synthetic sample set. See [Measured performance and accuracy](#measured-performance-and-accuracy) and `docs/09_DEPLOYMENT.md` section 9. |
| Label artwork embedded in a COLA document | Works: every raster image above a size floor is lifted out of the PDF at its own resolution and read through the same OCR pipeline, filling values the text layer left empty and standing in as the label side when no photograph was uploaded. Checking artwork from an application against that application is a self-consistency check, and the response and the interface both say so ([ADR 0010](docs/adr/0010-embedded-label-artwork.md)). |
| Accuracy on real photographed labels | **Unmeasured, and the largest open technical risk.** Real photographs have been submitted; what they found is A-15, OQ-21, and the scope line in [docs/02_PROJECT_SCOPE.md](docs/02_PROJECT_SCOPE.md) section 6. A label wrapped on a round bottle is not a supported input. |
| Beverage type from item 5 | Works: `backend/app/product_type.py`. Item 5's three check boxes are located from their own captions on the rendered page and compared by luminance; the darkest is reported only when it clears a defended margin, and two close or none filled is not determined. Never compared against the label; it selects which numeric rule runs. See [ADR 0016](docs/adr/0016-product-type-from-the-page.md) |
| COLA document parsing on real applications | **Unverified.** The item map is read off the blank TTB F 5100.31 (04/2023) and the three extraction paths are exercised against documents generated at test time. No real filed application or Registry printout has been parsed, because committing one would put an applicant's record in the repository. See OQ-22 and A-17. |
| Bold type on the warning prefix | **Not checked**, deliberately (OOS-4). See below. |

Numbers are deliberately absent from this table and are in their own section
below, because a figure without the hardware, the date and the sample it came
from is not a measurement. The checklist that produced them is
`docs/09_DEPLOYMENT.md` section 9. `scripts/measure.py` prints the current
figures for whatever machine runs it, and each pull request that measured
something records its numbers with the hardware they came from.

Planned work is tracked as
[GitHub Issues](https://github.com/kimkight/26-DO-12891471-DH_T_ITS_AI_THT/issues),
one per user story.

## Measured performance and accuracy

**Where these came from.** Every figure below was measured by the author on
2026-08-28 against the deployed URL, build `sha-f66a4e2`, running on ECS Fargate
with 1 vCPU and 8 GiB of memory behind the Application Load Balancer in
`us-east-1`, and exercised from the author's browser. They are measurements, not
estimates or projections. Nothing here is scaled arithmetically from a smaller
run, and nothing here was taken on a session container. The runs are the ones
`docs/09_DEPLOYMENT.md` section 9 lists, and that section records the same
values against its checklist.

### Latency

| Submission | End to end | Inside the checker | What came back |
| --- | --- | --- | --- |
| One label: the synthetic 1200x1600 fixture rotated 90 degrees, submitted with a Public COLA Registry printout attached | **1.5 s** | 1.4 s | All five fields matched. The rotation was detected and reported. |
| One label: three real phone photographs of a round bottle, which is the hard case | **7.8 s** | Not recorded separately | Brand name and class or type stayed unreadable on that bottle's curved glass and were reported honestly as mismatch and not found. |
| One label: the author's own mezcal COLA document (382 KB PDF) submitted **alone**, so its embedded artwork is the label side | **5.0 s** | 4.9 s, and this figure measures the request | All five fields returned, and this time read correctly. Re-measured 2026-08-30 against **deploy #12**, build 1.1.0, two runs: 4999 and 4992 ms wall clock; `elapsed_ms` 4928 and 4918 ms; `ocr_passes` 1; `tesseract_reads` 4. This supersedes the 3468 / 3505 / 3543 ms taken against deploy #11 earlier the same day, which were the cost of reading this document wrongly. |
| A batch at the configured cap: 300 label images with their 300 paired COLA documents in one submission | **Approximately 6.5 to 7 minutes**, roughly **1.3 s per label** | Not recorded separately | 300 of 300 rows returned. Results streamed progressively through the load balancer: 83 labels complete at the 109 second mark, observed live. |

**NFR-1 is met on both single-label paths.** They are different paths and the
honest statement names both:

- **The image path meets NFR-1 at 1.5 s.** One photograph and its application
  document came back in 1.5 seconds end to end through the load balancer,
  against a target of roughly five seconds.
- **The application-document path meets it at 5.0 s, which is at the line
  rather than under it.** Re-measured 2026-08-30 against deploy #12, build
  1.1.0, with the author's own mezcal COLA PDF submitted alone: 4999 and
  4992 ms wall clock, with the response's own `elapsed_ms` at 4928 and 4918 ms,
  `ocr_passes` 1 and `tesseract_reads` 4. Not rounded down. The margin against
  the bar is what is left of about 70 ms, and the paragraph below says what
  consumed it and why that was worth paying.

**The instrumentation was wrong, and it was wrong in the flattering
direction.** On all three of those runs `elapsed_ms` and `ocr_ms` came back
within 2 ms of each other, because `elapsed_ms` was measuring the label-side OCR
span and calling itself the request. The interface then printed the wall clock,
subtracted that figure, and told the agent the remainder was "sending the image
and receiving the answer". Two controls from the same page and session bound
what the network could have been: `GET /api/health` round-tripped in 18 to
25 ms, and a POST of the identical 382 KB file to a path that processes nothing
took 68 to 111 ms. So about 3.5 seconds of real server work per request was both
missing from the instrumentation and mislabelled as network time.

**What the honest instrumentation then showed.** The picture chosen as the label
side was being read twice: once to fill the application values, and again as the
label side, through the identical pipeline for an identical result. Reusing that
read removes one full OCR pass, and reading stops once every value has been
found rather than continuing through pictures that cannot add anything. Measured
on a session container, which is not production hardware and is reported here
only as a before-and-after on the same machine:

| Document | Before | After | OCR passes |
| --- | --- | --- | --- |
| One embedded label image | 2.19 s | 1.12 s | 2 to 1 |
| Two embedded label images | 3.17 s | 1.15 s | 3 to 1 |

**And it was re-measured, twice.** The earlier edition of this section said the
6.8 s figure would stand until the same document was submitted to the same URL
on a build carrying the fix, because halving the OCR passes on a path whose
passes were about 3.3 seconds each *should* land near 3.5 seconds and "should"
is arithmetic rather than measurement. It was submitted, on 2026-08-30 against
deploy #11, three consecutive runs at 3468, 3505 and 3543 ms, with
`unaccounted_ms` at 1.3 ms, which is what says the phase breakdown beside it
measures the request rather than a part of it. It was submitted again the same
day against deploy #12, once the release that corrected the reading had landed,
and came back at 4999 and 4992 ms. The table above carries the second figure,
because it is the one taken against a build that reads this document correctly.
Both are in [09_DEPLOYMENT.md](docs/09_DEPLOYMENT.md) section 9.

**The fix that made the readings correct is what consumed the margin, and that
is the trade.** The 3.5 s figure was measured while the artwork OCR on this
document was still failing: the label was being turned 180 degrees on a
Tesseract verdict of 0.03 confidence and then flattened to grayscale, so
3.5 seconds was the cost of reading a wrongly turned, wrongly rendered image
and getting three of five fields wrong. v1.1.0 changed what is read, and the
figure moved: 5.0 seconds against deploy #12 on 2026-08-30. About 1.4 seconds
of that increase is the 180-degree check, which reads the image at both
candidate rotations and keeps the better-scoring one. It runs only when
Tesseract's own orientation confidence falls under `LOW_ORIENTATION_CONFIDENCE`,
which on this document it did at 0.03, and on the twelve sample labels it does
not run at all. It is the reason the OCR confidence on this artwork went from
37.9 to 89.6 and the reason the alcohol content and net contents are found.

Paying a second and a half of a five-second budget to stop reading a label
upside down is worth it. What it is not is free, and the honest statement is
that this path now sits at the bar rather than comfortably inside it. There is
a costed optimisation in [OQ-27](docs/OPEN_QUESTIONS.md#oq-27): the two
rotation candidates are read at full resolution, and reading them at half
resolution separated 62.2 from 25.0 on this artwork against 91.8 from 32.1 at
full, for about a third less time. It is measured on one image, so it is
recorded rather than built.

**The panel segmentation in this release does not move the figure**, because it
adds no Tesseract read: both the column split and the block grouping are
arithmetic on the word table the single existing pass already returns.
Confirmed on a session container, which is not production hardware and is
reported only as a before-and-after on one machine: the same document measured
a median of 3300 ms over five runs before the change and 3280 ms after it, with
`ocr_passes` 1 and `tesseract_reads` 4 on every run either side.
`test_panel_segmentation.py` asserts the read count rather than leaving it to
the measurement.

The earlier before-and-after for the colour arm, on the same machine and the
same terms: the same document shape with colour artwork measured
1512 / 1563 / 1547 ms before that change and 1526 / 1425 / 1587 ms after it, at
one OCR pass either way, because the colour read replaces two reads rather than
adding a third.

**The three-photograph case is over that target, and that is a measurement
rather than a failure to report.** 7.8 seconds for three photographs of one
bottle is outside NFR-1's roughly five seconds. `docs/09_DEPLOYMENT.md`
section 9 named this as the thinnest margin against NFR-1 anywhere in the
prototype before it was run, and the run confirmed it. Both levers are task
environment variables and neither needs a code change:
`TTB_MAX_LABEL_PHOTOS` and `TTB_CORRECT_ORIENTATION`.

**NFR-2, batch throughput with visible progress, is met.** The full 300-label
batch completed with no timeout and no lost work, and progress was visible
throughout rather than arriving in one block at the end. The 83-of-300 reading
at 109 seconds is the evidence that the load balancer did not buffer the stream,
which was the specific risk ADR 0006 recorded and the reason the check exists.

**Peak task memory for the batch window: memory utilization measurement
pending.** The CloudWatch `MemoryUtilization` figure for that window is being
retrieved and is not written here until it is in hand. It is the number that
would replace the two estimates in `docs/09_DEPLOYMENT.md` section 4.3 with a
measurement, and it is the one that says whether 8 GiB was the right size.

### Accuracy

**On the synthetic seeded set, 300 of 300 outcomes were correct.** The 300-label
batch returned 270 fully matching rows and 30 not matching, with 0 needing review
and 0 unreadable. The 30 mismatches were exactly the 30 seeded ABV defects in the
fixture set: every seeded defect was caught, and there were no false alarms.

**This is the self-built sample, not the real application population.** That
distinction is the last bullet of section 5 of
[docs/02_PROJECT_SCOPE.md](docs/02_PROJECT_SCOPE.md), and it is the whole
qualification on the figure above. Rendered text is easier to read than a
photographed bottle, so 300 of 300 is an upper bound on a synthetic set and says
nothing about a real filing. The three-photograph run in the latency table is
the counter-example measured on the same day: on real curved glass, two of the
five fields did not come back at all.

### Known limitations

- **A real photograph is not a rendered label, and v1.0.1 is what that cost.**
  A photograph of a flat, crisp Ketel One back label submitted to the deployed
  v1.0.0 build on 2026-08-28 returned no government warning and brand-name
  shrapnel from the fine print. The cause was not the artwork and not the EXIF
  orientation handling: it was the OpenCV adaptive threshold, which suits
  rendered type and destroys a soft-contrast photograph. Tesseract's orientation
  detection was being asked about the destroyed image, and on a photograph-like
  fixture it answered correctly in 0 of 48 cases against 44 of 48 on the plain
  grayscale. v1.0.1 asks it on the grayscale, and reads both the preprocessed
  and the plain image and keeps the better one. What that does not do is make
  the point below untrue. One label read correctly is not a measurement, and the
  same degraded fixture still leaves half the sample set unreadable.
- **And flat artwork is not a rendered label either, which is what v1.1.0
  cost.** The author's own mezcal COLA artwork, lifted out of the filed PDF and
  therefore flat, crisp and not a photograph at all, read as `AMoviy TS` against
  `DEL MAGUEY` on two consecutive deploys. Two causes, and both were a number
  that looked confident about text it had never seen. Tesseract answered the
  orientation with 180 degrees at a confidence of 0.03, and the floor that would
  have rejected that verdict had been in the code since v1.0.1 as a caption
  only; below it the verdict is now scored against its opposite. And converting
  a label printed in three tones to grayscale drops an entire ink class, which
  mean word confidence structurally cannot detect, because a word that was never
  read lowers no score: the read that lost `42% ALC BY VOL` outright scored
  89.9 against the colour read's 89.1. The colour image is now read too
  ([ADR 0014](docs/adr/0014-colour-as-an-ocr-candidate.md)). The same caution
  applies as above: this is one document, and per-field accuracy against real
  label artwork is still unmeasured.
- **A label wrapped on a round bottle is not a supported input, and the scope
  line is written down.** The author's mezcal test of 2026-08-29 established
  three things about that case, and they are evidence rather than opinion. The
  GOVERNMENT WARNING block is printed at 90 degrees to the body copy on the same
  label, so no single global rotation makes both upright and the best-of-four
  rotation net cannot succeed on both at once. A sweep of 4 rotations by 5 page
  segmentation modes over the isolated warning crop returned `4 AANDVW 1AG` at
  2.1 percent similarity to 27 CFR 16.21, which is a failure to read rather than
  a degraded read. And the real COLA for that product gives Brand `DEL MAGUEY`
  and Fanciful `VIDA` while the largest text on the label is "Vida Clasico", so
  even a perfect transcription could not attribute the brand under the type-size
  heuristic. Since v1.1.0 that heuristic declines rather than guessing on such a
  label and the field reports not found (FR-1), which turns a confident wrong
  answer into an honest absence and solves nothing about the attribution. **Bottle photography stays in the prototype as a
  best-effort path with honest failure reporting and is not claimed as a
  capability**; the input that works, and that every measured figure came from,
  is flat label artwork. The full statement, and what each of the four possible
  fixes would cost, is
  [docs/02_PROJECT_SCOPE.md](docs/02_PROJECT_SCOPE.md) section 6.
- **Accuracy has been measured against synthetic labels only.** `samples/`
  renders twelve labels from text with Pillow; `scripts/measure.py` scores the
  engine against them. Rendered text is far easier to read than a photographed
  bottle, so those figures set an upper bound and nothing more. Per-field
  accuracy against real label artwork is unmeasured and is the largest open
  technical risk in the prototype (ADR 0003). No accuracy target is claimed
  either; no source states one (OQ-8).
- **The latency and throughput figures are now from the deployed target, and
  one number is still missing.** The checklist in
  [docs/09_DEPLOYMENT.md](docs/09_DEPLOYMENT.md) section 9 was run on
  2026-08-28, including the question of whether the batch stream survives a load
  balancer unbuffered, which it does. The one box still open is the CloudWatch
  `MemoryUtilization` figure for the batch window, and the README says "memory
  utilization measurement pending" rather than a number until it is in hand.
- **NFR-1 is met on both single-label paths and is still missed on the
  three-photograph case, and the miss is published rather than redefined.** One
  label image with its application document measures 1.5 seconds against
  NFR-1's roughly five. A COLA document submitted alone measures 5.0 seconds,
  re-measured against deploy #12 on 2026-08-30, which is at the line rather
  than under it and is published as 5.0 rather than rounded down. It measured
  3.5 seconds against deploy #11 earlier the same day, 6.8 seconds earlier
  still, and until that day the instrumentation reported 3.2 seconds for it and
  told the agent the difference was the network. It was not the network; it was
  a picture being read twice. The measurement was fixed, the duplicate read
  removed, and the figure re-taken against the deployed URL rather than
  inferred. The rise from 3.5 to 5.0 is the 180-degree orientation check, which
  is what made this document's readings correct: a real trade, stated rather
  than smoothed over. Three photographs of a round bottle measured 7.8 seconds on the same
  hardware, which is over the bar and stays reported as over it. A prototype
  that reports missing its own acceptance criterion is worth more than one that
  quietly moves the criterion. It is recorded rather than tuned away, and both
  levers are task environment variables rather than code:
  `TTB_MAX_LABEL_PHOTOS` and `TTB_CORRECT_ORIENTATION`. No source states a batch
  latency target at all (OQ-6), so the batch figure is reported without one.
- **Capitalization is checked; boldness is not.** 27 CFR 16.22(a)(2) requires
  the warning prefix in "capital letters and in bold type." The prototype checks
  only capitals and must not imply otherwise. The API says so in every warning
  result and the interface repeats it verbatim on the warning card, so the gap
  is visible to the agent rather than only to a reader of this file.
- **A clean accessibility run is not a conformance claim.** axe-core finds a
  subset of WCAG failures, and no automated tool replaces testing with an actual
  screen reader. What the CI run holds is the regressions that are cheap to
  introduce and expensive to notice: an input that loses its label, a heading
  level skipped, a contrast pair broken by a token change. Whether Section 508
  applies to this prototype is unanswered (OQ-7), and that is what would turn
  NFR-5 from a target into an obligation.
- **The interface has one light palette and no dark mode.** Contrast is asserted
  against that palette, token by token, in
  `frontend/src/__tests__/contrast.test.ts`. A dark palette is a second palette
  to verify, not a toggle.
- **The visual design uses the government palette; it is not endorsed by,
  affiliated with, or issued by TTB or the Department of the Treasury.** That is
  stated on every view of the interface itself, not only here. Inter is used
  under the SIL Open Font License, which is a licensing question with a clear
  answer rather than a branding claim.
- **No authentication and no persistence** (Decision D-9). Consequently there is
  no audit record that a verification occurred. For batch, the same decision
  means a dropped connection loses the whole submission: there is no
  server-side copy of the results, so the stream is the only one. This is the
  strongest argument for the job model ADR 0006 records as its expected
  successor.
- **Container base images are pinned by tag, not digest.**
- **The container build is verified in CI**, not in a session. The backend
  suite, the frontend component tests and the accessibility run execute in
  both.

## License

All rights reserved. No license is granted.
