# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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

### Known limitations

- No application logic. Label extraction, comparison, and verification are
  designed but not implemented; only the health endpoint exists.
- The build session could not reach PyPI, npm, or the Ubuntu package archive,
  so tests, the frontend build, and the container build were not run locally.
  They run in CI. See `docs/OPEN_QUESTIONS.md`, OQ-15.
- No lockfile in either ecosystem, so builds are not yet reproducible.
  Backend dependencies use minimum-version floors rather than exact pins,
  because hand-written exact pins went stale and `pip-audit` found seven
  advisories against the transitive `starlette` version they resolved to.
  See OQ-3.
- Container base images are pinned by tag rather than by digest.

[Unreleased]: https://github.com/kimkight/26-DO-12891471-DH_T_ITS_AI_THT/commits/develop
