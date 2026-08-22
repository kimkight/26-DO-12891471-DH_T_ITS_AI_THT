# Contributing

Full process is in [docs/08_SDLC_PROCESS.md](docs/08_SDLC_PROCESS.md). This is
the short version.

## Ground rules for documentation

These are not style preferences. They exist because a document that cannot be
traced back to a source is indistinguishable from a document that was invented.

1. **Cite the source.** Every requirement and user story carries a traceability
   tag: `[Source: Sarah Chen interview]`, `[Source: Technical Requirements]`,
   `[Source: Decision D-3]`.
2. **Mark inferences.** Anything inferred rather than stated is marked
   `(Assumption)` and listed in [docs/ASSUMPTIONS.md](docs/ASSUMPTIONS.md).
3. **Record questions; do not guess.** An unanswered question goes in
   [docs/OPEN_QUESTIONS.md](docs/OPEN_QUESTIONS.md). A guess that reaches a
   requirement becomes indistinguishable from a fact within one revision.
4. **Quote regulation, do not paraphrase it.** Fetch the text from ttb.gov or
   ecfr.gov, cite the URL and section, and quote it verbatim. If it cannot be
   fetched, leave a marked `TODO` rather than writing it from memory.
5. **No em dashes.** Use a semicolon or an ellipsis.
6. **No secrets, account identifiers, or personal data.** Anywhere, including
   test fixtures and issue bodies.

## Branching

Git Flow ([ADR 0005](docs/adr/0005-git-flow-branching.md)).

- `main` holds releases only. Every commit on it is a tagged release.
- `develop` is the integration branch. It is the intended default branch;
  the repository default is still `main` (see OQ-17), so check your base branch
  when opening a pull request.
- Work happens on `feature/<issue-number>-<short-description>`, branched from
  `develop` and merged back to `develop`.
- `release/*` and `hotfix/*` as described in the SDLC document.
- Never commit directly to `main` or `develop`. Never rewrite history on a
  shared branch.

## Commits

[Conventional Commits](https://www.conventionalcommits.org/):

```
feat(matching): add three-outcome classification for text fields

Implements FR-3. Scores at or above the match threshold return match,
scores between the review and match thresholds return needs human review.

Closes #3
```

Types: `feat`, `fix`, `docs`, `chore`, `refactor`, `test`, `ci`, `build`,
`perf`.

## Local setup

```bash
# Backend
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.lock
pip install --no-deps -e .
ruff check . && ruff format --check . && pytest

# Frontend
cd frontend
npm ci
npm run lint && npm run format:check && npm run build

# Everything together
docker compose up -d --build && curl http://localhost:8000/api/health
```

Both installs come from a lock file, so a fresh checkout resolves to the same
versions CI and the container image use. `pip install --no-deps -e .` registers
the `app` package without letting pip re-resolve anything the lock file already
decided.

Install the pre-commit hooks so lint failures surface before a push rather than
in the pull request:

```bash
pip install pre-commit && pre-commit install
```

## Regenerating lock files

`backend/requirements.lock` and `frontend/package-lock.json` are generated
files. **Neither is ever hand-edited.** A hand-edited lock file is a lock file
that no longer describes a resolution anyone can reproduce, and the hashes in
`requirements.lock` make an edited entry fail the install rather than fail
quietly.

The declared dependencies live in `backend/pyproject.toml` and
`frontend/package.json`. `pyproject.toml` keeps **minimum-version floors, not
exact pins**: the floors state the oldest version that is safe to use (they are
raised when an advisory requires it), and the lock file records the exact
versions that floor resolved to on the day it was generated. Change a floor in
`pyproject.toml`, then regenerate the lock file; never the other way round.

Regenerate the backend lock file after any change to `pyproject.toml`
dependencies, on Python 3.11 to match CI and the runtime image:

```bash
cd backend
pip install pip-tools
pip-compile --allow-unsafe --strip-extras --generate-hashes \
    --extra ocr --extra matching --extra dev \
    --output-file requirements.lock pyproject.toml
```

- `--generate-hashes` writes a digest for every artifact, which is what lets the
  Dockerfile install with `--require-hashes`.
- `--strip-extras` writes plain package names, because extras markers are not
  meaningful once the set is fully resolved.
- `--allow-unsafe` pins the packaging tools (`pip`) that pip-compile otherwise
  leaves out; leaving them unpinned is the unsafe option, despite the flag name.
- All three extras are included, so one file covers the container runtime, the
  test run, and the lint and audit tools.

Regenerate the frontend lock file after any change to `package.json`:

```bash
cd frontend
npm install
```

Then verify before committing:

```bash
cd backend && pip-audit -r requirements.lock --no-deps
cd frontend && npm ci && npm audit --audit-level=high
```

Commit the regenerated lock file in the same pull request as the manifest change
that caused it. A manifest change without its lock file update will fail CI at
`npm ci`, which refuses to run when the two disagree.

## Before opening a pull request

Run what CI runs. One validated push beats three speculative ones.

- `ruff check .` and `ruff format --check .` in `backend/`
- `pytest` in `backend/`
- `npm ci`, `npm run lint`, `npm run format:check`, and `npm run build` in
  `frontend/`
- `docker build .` from the repository root

## Pull requests

Use the template. It is a checklist, not a formality; a pull request that
changes a requirement without updating
[docs/TRACEABILITY_MATRIX.md](docs/TRACEABILITY_MATRIX.md) will be sent back.

Every pull request needs:

- A linked issue.
- Green CI: lint, tests, dependency audit, container build, SBOM.
- Tests for the behaviour changed, including its failure paths, or a stated
  reason none were needed.
- Documentation updated where the change touches documented behaviour.
- Review from a CODEOWNER.

## Definition of Ready and Definition of Done

Both are in [docs/08_SDLC_PROCESS.md](docs/08_SDLC_PROCESS.md) sections 5 and 6.
An issue that does not meet the Definition of Ready does not get started; work
that does not meet the Definition of Done does not get merged.

## Test data

No real application data and no personal data in any fixture. Sample label
artwork is generated or sourced locally and is git-ignored; see
[samples/README.md](samples/README.md).
