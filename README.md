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

> **Status: the prototype works and is deployed. Accuracy on real label
> artwork is the open question.** Single-label and batch verification and the
> agent-facing interface are built, tested, and running on ECS Fargate behind
> an Application Load Balancer in `us-east-1`, deployed by image digest.
>
> Accuracy and latency are still measured on synthetic labels and on developer
> hardware, not on the deployed target. The first photograph of a real bottle
> submitted to the deployed prototype returned none of its five fields; two of
> the three causes are fixed and recorded as assumption A-15, and the third,
> that a label wrapping a round bottle is never flat in one photograph, is
> worked around by [ADR 0007](docs/adr/0007-multi-photo-single-label.md) rather
> than solved. See [Status](#status) below for exactly what works and
> [Known limitations](#known-limitations) for what the measurements do not
> cover.

## Repository map

| Path | Contents |
| --- | --- |
| `backend/` | FastAPI application, Python 3.11. The verification engine and both endpoints. |
| `frontend/` | React and TypeScript, built with Vite. The agent-facing interface. |
| `docs/` | Charter, scope, requirements, stories, architecture, security, test strategy, SDLC process, deployment outline. |
| `docs/adr/` | Architecture decision records. |
| `samples/` | Twelve label specifications, the renderer that draws them, and the ground truth CSVs. Images are generated locally and git-ignored. |
| `scripts/` | `measure.py`, which runs the engine over the sample set and reports per-field accuracy and latency. |
| `infra/` | Placeholder for Terraform. Not written. |
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
{"status":"ok","service":"TTB Label Verifier","version":"0.1.0","environment":"local"}
```

The interface is at <http://localhost:8000/>. The first tab checks one label:
choose a label image, attach the COLA document or type what the application
says, and select **Check this label**. The second tab checks many at once,
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

**The interface is one screen.** The primary task is on the landing page with
nothing to navigate, every outcome is carried by a word and a shape before it is
carried by a colour, and the field needing a human's attention is the one that
looks unfinished. The requirement behind it is a stakeholder's, not a
designer's: "clean, obvious, no hunting for buttons," for a team where technology
comfort varies widely.

**It is dressed in federal design language, and it says plainly that it is not
an official system.** Navy, a gold rule, Public Sans, and a grey field under
white panels, in the spirit of the U.S. Web Design System, because the tool is
about federal label compliance and a prototype that looked like a consumer app
would answer the wrong question about whether it belongs in this workflow.

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
| Typeface | Public Sans, the face the U.S. Web Design System commissioned, under the SIL Open Font License 1.1. Bundled as a variable font and served from the application's own origin, never fetched from a CDN, because NFR-3 applies to the page as well as to the API |
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
| [04 User Stories](docs/04_USER_STORIES.md) | 22 stories across 6 epics, with Given/When/Then criteria |
| [05 Architecture](docs/05_ARCHITECTURE.md) | Context and container diagrams, request flows, data handling, configuration, government-region portability |
| [06 Security and Compliance](docs/06_SECURITY_AND_COMPLIANCE.md) | Threat model, controls, FedRAMP posture, ATO readiness, AI governance |
| [07 Test Strategy](docs/07_TEST_STRATEGY.md) | Unit, integration, accuracy, performance, accessibility, and a manual UAT checklist |
| [08 SDLC Process](docs/08_SDLC_PROCESS.md) | Phases with entry and exit criteria, Git Flow, PR checklist, DoR and DoD, releases |
| [09 Deployment](docs/09_DEPLOYMENT.md) | The author's runbook: commands, variables, task sizing, cost, post-deploy verification, teardown |
| [Open Questions](docs/OPEN_QUESTIONS.md) | 21 questions, 8 still open, each recorded rather than guessed |
| [Assumptions](docs/ASSUMPTIONS.md) | 16 inferences, each with what would confirm or falsify it |
| [Traceability Matrix](docs/TRACEABILITY_MATRIX.md) | Stakeholder statement to requirement to story to issue to test |
| [ADRs](docs/adr/) | Cloud platform, compute, extraction path, matching strategy, branching, batch execution model, more than one photograph of one label |
| [Contributing](CONTRIBUTING.md) | Branching, commits, local setup, review expectations |
| [Security Policy](SECURITY.md) | Reporting, scope, data handling |
| [Changelog](CHANGELOG.md) | Keep a Changelog format |

## Status

**Every functional requirement is built and tested. Nothing is deployed, and no
figure in this repository was measured on a deployed target.**

| Capability | State |
| --- | --- |
| `GET /api/health` | Works |
| `POST /api/verify` (one label against its application data) | Works |
| `POST /api/verify-batch` (many labels, each paired with its COLA document by filename stem) | Works: a bounded worker pool, results streamed as newline-delimited JSON, no job store. See [ADR 0006](docs/adr/0006-batch-execution-model.md) for the stream and [ADR 0009](docs/adr/0009-batch-cola-documents.md) for what a batch carries. |
| `POST /api/read-application` (read a COLA document, compare nothing) | Works: reads an uploaded TTB F 5100.31 or Public COLA Registry printout locally, so an agent can attach the application instead of retyping it. Not COLA system integration: no API call, no credential, no lookup. See [ADR 0008](docs/adr/0008-cola-form-as-application-input.md) and the note under OOS-1 in [docs/02_PROJECT_SCOPE.md](docs/02_PROJECT_SCOPE.md). |
| Field extraction from label artwork | Works: `backend/app/ocr.py`, `backend/app/parse.py` |
| Comparison against application data | Works: `backend/app/compare.py` |
| Government warning checks, text and capitalization | Works: `backend/app/warning.py` |
| Verification interface, one label | Works: one screen, up to three photographs of the same label, the five application fields, an optional upload of the label application that fills those fields for confirmation, five result cards, and a note saying what was done to each photograph |
| Verification interface, batch | Works: a second tab taking label images and their COLA documents, the pairing rule stated on the page and the pair count announced, progress driven by the stream, a sortable results table, and a results CSV built in the browser. One photograph per label; see ADR 0007 and ADR 0009 |
| Prototype disclosure | Works: a persistent banner on every view, an author attribution in the footer, and no seal, emblem, or officialdom claim anywhere. Enforced by `frontend/src/__tests__/branding.test.tsx` |
| Accessibility, WCAG 2.1 AA target | Checked in CI by axe-core against the built page, plus a keyboard walk and a contrast check on the palette. See the limitation below on what a clean run does and does not claim. |
| One bad image failing only its own row in a batch | Works; covered by tests |
| Container build, non-root, health probe | Works; verified in CI |
| CI: lint, tests, dependency audit, container build, SBOM | Works |
| Infrastructure as code | Works: `infra/terraform/` builds the ECR repository, ECS cluster and Fargate service, load balancer, log group, and IAM roles including a GitHub OIDC deploy role. Format-checked and validated in CI, and applied to an AWS account in `us-east-1`. |
| Deployment workflow | Works. `workflow_dispatch` or a published release; builds, pushes to ECR, and deploys the image digest through OIDC with no static keys. |
| Deployed URL | Deployed: ECS Fargate behind an Application Load Balancer in `us-east-1`. The runbook is [docs/09_DEPLOYMENT.md](docs/09_DEPLOYMENT.md); the author applies and deploys from her own machine, and **nothing merged deploys itself**. |
| Accuracy and latency measurements | Measured over a synthetic sample set, on developer hardware, not on the deployed target; see below and `docs/09_DEPLOYMENT.md` section 9. |
| Accuracy on real photographed labels | **Unmeasured, and the largest open technical risk.** One real photograph has been submitted; what it found is A-15 and OQ-21. |
| COLA document parsing on real applications | **Unverified.** The item map is read off the blank TTB F 5100.31 (04/2023) and the three extraction paths are exercised against documents generated at test time. No real filed application or Registry printout has been parsed, because committing one would put an applicant's record in the repository. See OQ-22 and A-17. |
| Bold type on the warning prefix | **Not checked**, deliberately (OOS-4). See below. |

Numbers are deliberately absent from this table. Accuracy and latency figures
belong here once they have been measured on the target they describe, and the
target now exists but has not been measured. The checklist that turns that
around is `docs/09_DEPLOYMENT.md` section 9. `scripts/measure.py` prints the
current figures for whatever machine runs it, and each pull request that
measured something records its numbers with the hardware they came from.

Planned work is tracked as
[GitHub Issues](https://github.com/kimkight/26-DO-12891471-DH_T_ITS_AI_THT/issues),
one per user story.

### Known limitations

- **Accuracy has been measured against synthetic labels only.** `samples/`
  renders twelve labels from text with Pillow; `scripts/measure.py` scores the
  engine against them. Rendered text is far easier to read than a photographed
  bottle, so those figures set an upper bound and nothing more. Per-field
  accuracy against real label artwork is unmeasured and is the largest open
  technical risk in the prototype (ADR 0003). No accuracy target is claimed
  either; no source states one (OQ-8).
- **Nothing has been measured on a deployed target, and the infrastructure to
  create one now exists.** That is a change in what is possible, not in what is
  known. The checklist that would produce the first real numbers, including
  whether the batch stream survives a load balancer unbuffered, is
  [docs/09_DEPLOYMENT.md](docs/09_DEPLOYMENT.md) section 9. Nothing in this
  README moves until it has been run.
- **Latency figures come from a session container, not production hardware.**
  The 5-second target (NFR-1) is asserted in the integration test, which is the
  gate; the published numbers are measurements on whatever machine ran them and
  say so. The same applies to batch: throughput has been measured at twelve and
  one hundred labels, never at the 300 the configured limit allows, and never on
  a deployed target. Scaling from one to the other is arithmetic, not a
  measurement, and no source states a batch latency target anyway (OQ-6).
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
- **The visual design reflects federal design language; it is not endorsed by,
  affiliated with, or issued by TTB or the Department of the Treasury.** That is
  stated on every view of the interface itself, not only here. Public Sans is
  used under the SIL Open Font License, which is a licensing question with a
  clear answer rather than a branding claim.
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
