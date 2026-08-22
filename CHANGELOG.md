# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- ADR 0006, recording the batch execution model: one synchronous multipart
  request carrying up to `TTB_MAX_BATCH_FILES` images plus one CSV of
  application data keyed by image filename, processed concurrently by a bounded
  worker pool, with per-label results streamed as newline-delimited JSON and no
  job store, consistent with D-9. Implements FR-8 and NFR-2. (#39)
- Assumption A-14, stating the batch CSV contract: one CSV keyed by image
  filename with the columns `filename`, `brand_name`, `class_type`,
  `alcohol_content`, `net_contents` and `beverage_type`. FR-8 requires batch
  submission "with their application data" and no source states the format.
  (#39)
- `docs/DEPENDENCY_TRIAGE_2026-08.md`, triaging the twelve Dependabot pull
  requests from the first run against `develop`: six recommended merge, one
  merge with a caveat, four close, one hold, with the reason for each and a
  full diagnosis of why the TypeScript 7 bump could not resolve a dependency
  tree. (#40)
- `.github/dependabot.yml`, setting the update policy that follows from that
  triage: minor and patch updates grouped into one pull request per ecosystem
  per week, major bumps left ungrouped so each keeps its own pull request and
  recorded decision, and major bumps of `typescript` and `react` ignored. (#40)
- OQ-18, recording that the session git proxy rejects pushes to `refs/tags/*`
  with HTTP 403 while accepting pushes to `refs/heads/*`, and that tags and
  releases are therefore created through the GitHub Releases web interface.
  v0.1.0 was created that way, tagged at `79d5ac7` on `main`.
- A header on `docs/cloud_choice_and_abv_assumption.md` marking it as the source
  record for ADR 0001, A-12, and A-13, and as not maintained going forward.

### Changed

- OQ-2 closed. Tesseract 5.3.0 is the version shipped in the container image,
  read from `tesseract --version` against the built image in CI run 32574942848
  at commit `ef3086a` and recorded in the version table in
  `docs/05_ARCHITECTURE.md` section 8. It was not assumed: the initializing
  session could not install Tesseract, so CI is the authoritative source. 5.3.0
  is the LSTM-era line, which is what the extraction path is written against.
  (#38)
- OQ-6 and OQ-16 closed by ADR 0006 and assumption A-14. (#39)
- `react-dom` added to the npm major-version ignore list alongside `react`. The
  triage named `typescript` and `react` only, but `react` and `react-dom` ship
  as a matched pair and `react-dom` declares a peer dependency on the exact
  `react` version, so a `react-dom` major proposed on its own could never be
  merged alone. This closes the gap `docs/DEPENDENCY_TRIAGE_2026-08.md` recorded
  as left open.
- `vite` and `@vitejs/plugin-react` added to the npm major-version ignore list
  as a coupled pair. The repository has now hit the same deadlock from both
  sides: #28 (`vite` 6 to 8) failed CI at `npm install` with ERESOLVE because
  `@vitejs/plugin-react@4.7.0` declares `peer vite "^4.2.0 || ^5.0.0 || ^6.0.0
  || ^7.0.0"`, and #41 (`@vitejs/plugin-react` 4 to 6) was closed because plugin
  6 requires a Vite major. Neither half is mergeable alone, so either half
  proposed on its own can only produce a pull request that gets closed. Removing
  both entries together is what reopens the upgrade.
- `docs/DEPENDENCY_TRIAGE_2026-08.md` triages the second Dependabot run: #43
  (`typescript` 5.9.3) recommended merge, green and within
  `typescript-eslint`'s `>=4.8.4 <6.1.0` peer window; #42 (`eslint` 10.8.1) and
  #44 (`@eslint/js` 10.0.1) recommended for merge only as a single combined
  change, since `@eslint/js` 10 alone fails `npm install` with ERESOLVE against
  `eslint` 9 while every plugin in the tree already declares an `eslint` 10 peer
  range. No ignore entries were added for that pair, because the failure is
  explained by the split rather than by incompatibility.
- `docs/DEPENDENCY_TRIAGE_2026-08.md` adds a "lock file interaction" section:
  from now on a merged bump that changes only a manifest leaves `develop` red,
  because `npm ci` and `--require-hashes` both reject a stale lock. Dependabot
  carries the npm lock change on branches cut after the lock file exists; #42,
  #43 and #44 predate it and need a rebase or a follow-up regeneration, and pip
  bumps always need a manual regeneration.
- `docs/DEPENDENCY_TRIAGE_2026-08.md` records what happened after the first
  triage was acted on, and states the condition for closing #27
  (`aws-actions/configure-aws-credentials` 4 to 6): it stays open until
  `deploy.yml` is enabled. Nothing is wrong with the bump, so closing it would
  discard a valid update and invite Dependabot to reopen it weekly, and ignoring
  it would hide a credential-handling action from updates entirely. It is held
  open until a workflow exists that can actually exercise it.
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
