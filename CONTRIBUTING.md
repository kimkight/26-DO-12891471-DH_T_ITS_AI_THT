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
pip install --require-hashes -r requirements-dev.lock
pip install --no-deps -e .
ruff check . && ruff format --check . && pytest

# Frontend
cd frontend
npm ci
npm run lint && npm run format:check && npm run build

# Everything together
docker compose up -d --build && curl http://localhost:8000/api/health
```

Every install comes from a lock file, so a fresh checkout resolves to the same
versions CI uses. `pip install --no-deps -e .` registers the `app` package
without letting pip re-resolve anything the lock file already decided.

Local development uses `requirements-dev.lock`, not `requirements.lock`. The
runtime file has no `pytest` and no `ruff` in it, by design: see below.

Install the pre-commit hooks so lint failures surface before a push rather than
in the pull request:

```bash
pip install pre-commit && pre-commit install
```

## Regenerating lock files

Three files are generated and **none of them is ever hand-edited**:

| File | Contents | Consumed by |
| --- | --- | --- |
| `backend/requirements.lock` | the `ocr` and `matching` extras, 27 packages | the container image, and the runtime half of the audit |
| `backend/requirements-dev.lock` | the same plus the `dev` extra, 61 packages | the `backend lint and test` CI job, local development, and the dev half of the audit |
| `frontend/package-lock.json` | the resolved npm tree | `npm ci` in CI, in the image build, and locally |

A hand-edited lock file no longer describes a resolution anyone can reproduce,
and both mechanisms reject one anyway: `--require-hashes` fails on an entry
whose digest does not match, and `npm ci` refuses to run at all when the lock
and `package.json` disagree.

**Why the Python lock is split.** `requirements.lock` is what the Dockerfile
installs, so anything in it ships in the image. `pytest`, `ruff`, `pip-audit`
and `httpx` are contributor tools, not product, and putting them in the image
would enlarge it and widen its surface for nothing. The dev file is a strict
superset of the runtime file, generated from the same resolution, so the tools
are the ones the runtime set resolved against rather than whatever pip would
pick alongside them later.

The declared dependencies live in `backend/pyproject.toml` and
`frontend/package.json`. `pyproject.toml` keeps **minimum-version floors, not
exact pins**: the floors state the oldest version that is safe to use (they are
raised when an advisory requires it), and the lock files record the exact
versions those floors resolved to on the day they were generated. Change a floor
in `pyproject.toml`, then regenerate; never the other way round.

Regenerate **both** Python lock files after any change to `pyproject.toml`
dependencies, on Python 3.11 to match CI and the runtime image. Regenerating one
and not the other leaves them describing two different resolutions:

```bash
cd backend
pip install pip-tools

# Runtime: what ships in the image.
pip-compile --allow-unsafe --strip-extras --generate-hashes \
    --extra ocr --extra matching \
    --output-file requirements.lock pyproject.toml

# Development: the same, plus the test and lint tooling.
pip-compile --allow-unsafe --strip-extras --generate-hashes \
    --extra ocr --extra matching --extra dev \
    --output-file requirements-dev.lock pyproject.toml
```

- `--generate-hashes` writes a digest for every artifact, which is what lets the
  installs use `--require-hashes`.
- `--strip-extras` writes plain package names, because extras markers are not
  meaningful once the set is fully resolved.
- `--allow-unsafe` pins the packaging tools (`pip`) that pip-compile otherwise
  leaves out; leaving them unpinned is the unsafe option, despite the flag name.

Regenerate the frontend lock file after any change to `package.json`:

```bash
cd frontend
npm install --package-lock-only
```

`--package-lock-only` updates the lock file from the registry without writing
`node_modules`, which is what is wanted when the only artifact being changed is
the lock file. Plain `npm install` produces the same lock and is fine when a
working `node_modules` is wanted too.

Then verify before committing:

```bash
cd backend
pip-audit -r requirements.lock --no-deps
pip-audit -r requirements-dev.lock --no-deps

cd ../frontend
npm ci                             # fails if the lock and package.json disagree
npm audit --audit-level=high
```

### The rule

**Any pull request that changes `frontend/package.json` or
`backend/pyproject.toml` must regenerate the affected lock file in the same pull
request.** This is not a style preference. `npm ci` and `--require-hashes` both
reject a stale lock file rather than working around it, so a manifest change
committed without its lock file update does not produce a subtly different
build; it produces a red pull request, and every later pull request that touches
the same manifest inherits the failure.

This applies to Dependabot pull requests too. Dependabot updates
`package-lock.json` itself when a lock file exists on the base branch, so its
pull requests carry the lock change from now on. A bump merged from a pull
request opened before the lock file existed does not, and has to be followed by
a regeneration commit on `develop`.

## Before opening a pull request

Run what CI runs. One validated push beats three speculative ones.

- `ruff check .` and `ruff format --check .` in `backend/`
- `pytest` in `backend/`
- `pip-audit -r requirements.lock --no-deps` and the same for
  `requirements-dev.lock`, in `backend/`, if either lock file changed
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
