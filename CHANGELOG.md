# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- `frontend/package-lock.json` (npm 10.9.7, Node 22.22.2) and
  `backend/requirements.lock` (pip-compile 7.6.1, Python 3.11, generated with
  `--allow-unsafe --strip-extras --generate-hashes` over the ocr, matching and
  dev extras). Both were generated outside a session, because the session egress
  policy still denies PyPI and npm (OQ-15), and both audit clean.
- A "Regenerating lock files" section in `CONTRIBUTING.md` with the exact
  regeneration commands and the rule that `backend/pyproject.toml` keeps
  minimum-version floors while the lock file is regenerated and never
  hand-edited.
- OQ-18, recording that the session git proxy rejects pushes to `refs/tags/*`
  with HTTP 403 while accepting pushes to `refs/heads/*`, and that tags and
  releases are therefore created through the GitHub Releases web interface.
  v0.1.0 was created that way, tagged at `79d5ac7` on `main`.
- A header on `docs/cloud_choice_and_abv_assumption.md` marking it as the source
  record for ADR 0001, A-12, and A-13, and as not maintained going forward.

### Changed

- OQ-3 closed. Builds now install from the committed lock files rather than
  resolving afresh. CI installs the backend with `pip install -r
  requirements.lock` followed by `pip install --no-deps -e .`, and the frontend
  with `npm ci`. `pip-audit` audits the lock file directly
  (`pip-audit -r backend/requirements.lock --no-deps`) instead of scanning an
  installed environment. The Dockerfile uses `npm ci` and
  `pip install --require-hashes -r requirements.lock`, so every artifact in the
  image is verified against the digest recorded at resolution time, and the
  comments marking the switch as pending are removed. The "No frontend
  lockfile" limitation is removed from the README.
- Known issue, recorded in OQ-3: `frontend/package-lock.json` was generated
  before pull requests #32, #34 and #35 raised three devDependency ranges, so
  `npm ci` rejects it until it is regenerated. `backend/requirements.lock`
  satisfies every floor in `backend/pyproject.toml`.
- OQ-15 re-checked from a new session on 2026-08-22 and left open. PyPI and npm
  still return `403 host_not_allowed`, and Tesseract and a Docker daemon are
  still absent, so the recorded environment fix has not taken effect for
  sessions.
- OQ-12 closed. Branch protection rules were declared on `main` and `develop` on
  2026-08-21: pull request required, the `ci` status check required, approvals
  not required, force pushes and deletions blocked. GitHub shows them as "Not
  enforced" because the repository is private on a Free plan.
- OQ-14 closed. The Project board "TTB Label Verifier" exists at
  <https://github.com/users/kimkight/projects/1>, a user-owned project linked to
  this repository, with issues #1 to #21 in Backlog.
- OQ-17 closed. `develop` is now the repository's default branch.
- OQ-15 updated with the root cause of the package-manager denials: the cloud
  environment was at the Custom network level without the default package
  manager list included, so PyPI, npm, and the apt archives were denied with
  `host_not_allowed` even though they appear in `no_proxy`. Being in `no_proxy`
  is not an allowlist entry. The environment fix is recorded; the question stays
  open until a preflight from a new session confirms it.
- `docs/08_SDLC_PROCESS.md` section 7 now states that tags are created through
  GitHub Releases from `main` rather than pushed from a session, and why.

## [0.1.0] - 2026-08-22

### Added

- Repository initialization with Git Flow branching: `main` for releases,
  `develop` for integration.
- SDLC documentation set under `docs/`: project charter, scope, requirements,
  user stories, architecture, security and compliance, test strategy, SDLC
  process, and a deployment outline.
- Five architecture decision records covering cloud platform, compute, the text
  extraction path, the matching strategy, and branching, plus an ADR template.
- `docs/OPEN_QUESTIONS.md` and `docs/ASSUMPTIONS.md`, recording what is
  unanswered and what was inferred rather than stated.
- `docs/TRACEABILITY_MATRIX.md`, mapping stakeholder statements through
  requirements and stories to tests and ADRs.
- FastAPI backend scaffold exposing `GET /api/health` only, with configuration
  read from environment variables.
- React and TypeScript frontend scaffold built with Vite, served as static files
  by the backend container.
- Multi-stage `Dockerfile` running as a non-root user, and `docker-compose.yml`
  for local use.
- GitHub Actions CI covering backend lint and tests, frontend lint and build,
  dependency audit for both ecosystems, container build with a health probe and
  a non-root assertion, and SBOM generation.
- Deployment workflow scaffolded and disabled with an `if: false` guard, because
  no AWS infrastructure exists yet.
- Issue templates for user stories, bugs, and tasks; a pull request template
  carrying the traceability checklist; `CODEOWNERS`; and Dependabot for pip,
  npm, GitHub Actions, and Docker.
- Pre-commit configuration for both ecosystems.
- GitHub Issues for all twenty-one user stories, with epic, priority, and type
  labels.
- `docs/cloud_choice_and_abv_assumption.md`, the source document for the cloud
  platform rationale and the alcohol content and net contents assumptions.
- Assumption A-12: alcohol content on the label and in the application must be
  numerically identical, with normalization, a proof equals 2 x ABV cross-check
  per 27 CFR 5.65, and no tolerance band. The tolerances in 27 CFR 5.65, 4.36,
  and 7.65 govern actual against labeled content, so none of them applies to two
  values the applicant declared.
- Assumption A-13: net contents are compared numerically only when units match
  after normalization; different units are reported as needs human review with
  no conversion, and standards of fill are not validated.
- `TTB_ABV_TOLERANCE`, defaulting to `0.0`, so the A-12 position can change
  without a code change.
- Section "Why not Azure, given the agency runs Azure" in ADR 0001, recording
  why the prototype is built on AWS when the agency states it is on Azure, the
  public Treasury evidence bearing on it, and the negative consequence that the
  Terraform would need an Azure provider module before a pilot.
- Manual UAT rows 18 to 22 covering the A-12 and A-13 rules.

### Changed

- Decision D-11 replaced everywhere it appeared. The previous text asserted that
  the agency's intended production environment is AWS GovCloud (US); no source
  supports that, and the Marcus Williams interview says Azure. D-11 now records
  the agency's stated Azure position, the author's choice of AWS commercial
  `us-east-1` for delivery speed, the container-first portable design, and
  FedRAMP status confirmed against the FedRAMP Marketplace at deployment time
  rather than asserted.
- NFR-10 retitled to "Portability to a FedRAMP-authorized government region
  (AWS GovCloud or Azure Government)"; its acceptance criteria are unchanged.
- FR-7 acceptance criteria extended with the A-12 and A-13 rules.
- OQ-1 marked as answered by ADR 0001, as the author's decision rather than a
  stakeholder answer. OQ-4 closed by A-12 and OQ-5 closed by A-13.

### Known limitations

- No application logic. Label extraction, comparison, and verification are
  designed but not implemented; only the health endpoint exists.
- The build session could not reach PyPI, npm, or the Ubuntu package archive
  and had no Docker daemon, so tests, the frontend build, and the container
  build were not run locally. All of them run and pass in CI, which is where
  the scaffold was actually verified. See `docs/OPEN_QUESTIONS.md`, OQ-15.
- Branch protection is not applied and the default branch is still `main`
  rather than `develop`; neither endpoint was reachable from the initializing
  session. See OQ-12 and OQ-17.
- No lockfile in either ecosystem, so builds are not yet reproducible.
  Backend dependencies use minimum-version floors rather than exact pins,
  because hand-written exact pins went stale and `pip-audit` found seven
  advisories against the transitive `starlette` version they resolved to.
  See OQ-3.
- Container base images are pinned by tag rather than by digest.

[Unreleased]: https://github.com/kimkight/26-DO-12891471-DH_T_ITS_AI_THT/compare/v0.1.0...develop
[0.1.0]: https://github.com/kimkight/26-DO-12891471-DH_T_ITS_AI_THT/releases/tag/v0.1.0
