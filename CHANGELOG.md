# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

Nothing yet.

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
