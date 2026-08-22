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
pip install -e ".[dev,matching]"
ruff check . && ruff format --check . && pytest

# Frontend
cd frontend
npm install
npm run lint && npm run format:check && npm run build

# Everything together
docker compose up -d --build && curl http://localhost:8000/api/health
```

Install the pre-commit hooks so lint failures surface before a push rather than
in the pull request:

```bash
pip install pre-commit && pre-commit install
```

## Before opening a pull request

Run what CI runs. One validated push beats three speculative ones.

- `ruff check .` and `ruff format --check .` in `backend/`
- `pytest` in `backend/`
- `npm run lint`, `npm run format:check`, and `npm run build` in `frontend/`
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
