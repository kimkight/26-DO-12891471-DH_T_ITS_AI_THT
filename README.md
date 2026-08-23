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

> **Status: scaffold only.** The application logic is **not implemented**. Only
> `GET /api/health` exists. See [Status](#status) below for exactly what works.

## Repository map

| Path | Contents |
| --- | --- |
| `backend/` | FastAPI application, Python 3.11. Health endpoint only. |
| `frontend/` | React and TypeScript, built with Vite. Placeholder shell. |
| `docs/` | Charter, scope, requirements, stories, architecture, security, test strategy, SDLC process, deployment outline. |
| `docs/adr/` | Architecture decision records. |
| `samples/` | Where labeled test images and ground truth will live. Empty today. |
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

The frontend shell is at <http://localhost:8000/> and shows the backend status.
It does not verify labels, because that logic does not exist yet.

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

**The tool recommends; the agent decides.** Nothing here issues an approval or a
rejection, and every result carries the label value, the application value, and
the score so an agent can overrule it. See
[docs/06_SECURITY_AND_COMPLIANCE.md](docs/06_SECURITY_AND_COMPLIANCE.md)
section 6.

## Tools used

| Layer | Choice |
| --- | --- |
| Backend | Python 3.11, FastAPI, uvicorn |
| Frontend | React 19, TypeScript, Vite |
| OCR | Tesseract via pytesseract, OpenCV for preprocessing |
| Matching | rapidfuzz |
| Container | Docker, multi-stage, non-root |
| CI | GitHub Actions: ruff, pytest, eslint, prettier, pip-audit, npm audit, Syft SBOM |
| Target platform | AWS ECS on Fargate behind an ALB, image in ECR, `us-east-1` |

## Documentation

| Document | What it covers |
| --- | --- |
| [01 Project Charter](docs/01_PROJECT_CHARTER.md) | Purpose, background, stakeholders, success criteria, constraints, deliverables |
| [02 Project Scope](docs/02_PROJECT_SCOPE.md) | In scope, out of scope, stretch goals, Definition of Done |
| [03 Requirements](docs/03_REQUIREMENTS.md) | FR-1 to FR-10, NFR-1 to NFR-11, with acceptance criteria; verbatim 27 CFR 16.21 and 16.22 |
| [04 User Stories](docs/04_USER_STORIES.md) | 21 stories across 5 epics, with Given/When/Then criteria |
| [05 Architecture](docs/05_ARCHITECTURE.md) | Context and container diagrams, request flows, data handling, configuration, government-region portability |
| [06 Security and Compliance](docs/06_SECURITY_AND_COMPLIANCE.md) | Threat model, controls, FedRAMP posture, ATO readiness, AI governance |
| [07 Test Strategy](docs/07_TEST_STRATEGY.md) | Unit, integration, accuracy, performance, accessibility, and a manual UAT checklist |
| [08 SDLC Process](docs/08_SDLC_PROCESS.md) | Phases with entry and exit criteria, Git Flow, PR checklist, DoR and DoD, releases |
| [09 Deployment](docs/09_DEPLOYMENT.md) | Outline only; infrastructure is a later task |
| [Open Questions](docs/OPEN_QUESTIONS.md) | 18 questions, 6 still open, each recorded rather than guessed |
| [Assumptions](docs/ASSUMPTIONS.md) | 14 inferences, each with what would confirm or falsify it |
| [Traceability Matrix](docs/TRACEABILITY_MATRIX.md) | Stakeholder statement to requirement to story to issue to test |
| [ADRs](docs/adr/) | Cloud platform, compute, extraction path, matching strategy, branching |
| [Contributing](CONTRIBUTING.md) | Branching, commits, local setup, review expectations |
| [Security Policy](SECURITY.md) | Reporting, scope, data handling |
| [Changelog](CHANGELOG.md) | Keep a Changelog format |

## Status

**The single-label verification engine works over HTTP. There is no user
interface for it.**

| Capability | State |
| --- | --- |
| `GET /api/health` | Works |
| `POST /api/verify` (one label against its application data) | Works |
| Field extraction from label artwork | Works: `backend/app/ocr.py`, `backend/app/parse.py` |
| Comparison against application data | Works: `backend/app/compare.py` |
| Government warning checks, text and capitalization | Works: `backend/app/warning.py` |
| Frontend shell showing backend status | Works |
| Container build, non-root, health probe | Works; verified in CI |
| CI: lint, tests, dependency audit, container build, SBOM | Works |
| Verification user interface | **Not implemented.** The engine is reachable over HTTP only, so FR-10, NFR-4 and NFR-5 are untested. |
| Batch verification | **Not implemented.** Designed in ADR 0006. |
| Deployed URL | **Not deployed.** No AWS infrastructure exists. |
| Accuracy and latency measurements | Measured over a synthetic sample set only; see below. |

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
- **Latency figures come from a session container, not production hardware.**
  The 5-second target (NFR-1) is asserted in the integration test, which is the
  gate; the published numbers are measurements on whatever machine ran them and
  say so.
- **Capitalization is checked; boldness is not.** 27 CFR 16.22(a)(2) requires
  the warning prefix in "capital letters and in bold type." The prototype checks
  only capitals and must not imply otherwise.
- **No authentication and no persistence** (Decision D-9). Consequently there is
  no audit record that a verification occurred.
- **Container base images are pinned by tag, not digest.**
- **The frontend build and the container build are verified in CI**, not in a
  session. The backend test suite now runs in both.

## License

All rights reserved. No license is granted.
