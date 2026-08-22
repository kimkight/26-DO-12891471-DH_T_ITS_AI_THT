# SDLC Process

How work moves from a stakeholder statement to a released change, and which
artifact in this repository proves each phase was done.

## 1. Phases

Entry and exit criteria are gates, not suggestions. A phase is not exited
because time ran out; it is exited because the criteria are met or because the
gap is recorded in [OPEN_QUESTIONS.md](OPEN_QUESTIONS.md).

### Initiation

| | |
| --- | --- |
| **Entry** | A stated business need with an identified sponsor. |
| **Exit** | Purpose, stakeholders, success criteria, constraints, and deliverables agreed and written. |
| **Artifacts** | [01_PROJECT_CHARTER.md](01_PROJECT_CHARTER.md); [ASSUMPTIONS.md](ASSUMPTIONS.md); [OPEN_QUESTIONS.md](OPEN_QUESTIONS.md) |
| **Status** | Complete. |

### Requirements

| | |
| --- | --- |
| **Entry** | An approved charter. |
| **Exit** | Every requirement numbered, prioritized, source-tagged, and given acceptance criteria. Every requirement traces to a user story. Scope boundaries written down, including what is excluded and why. |
| **Artifacts** | [02_PROJECT_SCOPE.md](02_PROJECT_SCOPE.md); [03_REQUIREMENTS.md](03_REQUIREMENTS.md); [04_USER_STORIES.md](04_USER_STORIES.md); [TRACEABILITY_MATRIX.md](TRACEABILITY_MATRIX.md); GitHub Issues |
| **Status** | Complete for the prototype. |

### Design

| | |
| --- | --- |
| **Entry** | Requirements with acceptance criteria. |
| **Exit** | Architecture documented with context, containers, and request flows. Every significant technical choice recorded as an ADR with alternatives and consequences. Security posture and threat model written. |
| **Artifacts** | [05_ARCHITECTURE.md](05_ARCHITECTURE.md); [06_SECURITY_AND_COMPLIANCE.md](06_SECURITY_AND_COMPLIANCE.md); [adr/](adr/) |
| **Status** | Complete for the prototype. Infrastructure design is outlined but not written; see `infra/README.md`. |

### Build

| | |
| --- | --- |
| **Entry** | A refined issue meeting the Definition of Ready. |
| **Exit** | Code merged to `develop` through a reviewed pull request with CI green. |
| **Artifacts** | `backend/`; `frontend/`; `Dockerfile`; `.github/workflows/ci.yml` |
| **Status** | Scaffold only. No application logic. |

### Test

| | |
| --- | --- |
| **Entry** | A build with the behaviour under test implemented. |
| **Exit** | Unit and integration tiers pass in CI. Accuracy and performance measured against the sample set and reported. Accessibility checks run. Manual UAT checklist executed against a deployed build. |
| **Artifacts** | [07_TEST_STRATEGY.md](07_TEST_STRATEGY.md); `backend/tests/`; CI results; `samples/` |
| **Status** | Unit tier partially present, health endpoint only. Every other tier blocked. |

### Deploy

| | |
| --- | --- |
| **Entry** | A release candidate on a `release/*` branch with CI green and UAT complete. |
| **Exit** | The prototype is reachable at a URL reviewers can test, and the health endpoint responds through the load balancer. |
| **Artifacts** | [09_DEPLOYMENT.md](09_DEPLOYMENT.md); `infra/`; `.github/workflows/deploy.yml` |
| **Status** | Not started. The deploy workflow is committed but guarded with `if: false` because no infrastructure exists. |

### Operate and Retire

| | |
| --- | --- |
| **Entry** | A deployed prototype. |
| **Exit for operate** | Health checks green; logs flowing to CloudWatch with a set retention; dependency updates triaged weekly. |
| **Exit for retire** | Infrastructure destroyed, image deleted from ECR, and the repository marked archived with a note on where the work went. |
| **Artifacts** | `infra/`; `.github/dependabot.yml`; CloudWatch |
| **Status** | Not started. |

Retirement is genuinely short here, and that is a property of the design rather
than an oversight: nothing is persisted, so there is no data to migrate,
export, or dispose of (D-9). A production system with an audit trail would have
a records disposition obligation instead.

## 2. Branching: Git Flow

Per Decision D-6. Rationale and alternatives are in
[ADR 0005](adr/0005-git-flow-branching.md).

| Branch | Purpose | Merges from | Merges to |
| --- | --- | --- | --- |
| `main` | Releases only. Every commit is a tagged release. | `release/*`, `hotfix/*` | nothing |
| `develop` | Integration branch. Intended default branch; see OQ-17. | `feature/*`, `release/*`, `hotfix/*` | `release/*` |
| `feature/*` | One issue's worth of work | `develop` | `develop` |
| `release/*` | Release stabilization; version bump, changelog, fixes only | `develop` | `main` and back to `develop` |
| `hotfix/*` | Urgent fix against a release | `main` | `main` and `develop` |

**Rules**

1. No direct commits to `main` or `develop`. Everything arrives by pull request.
2. `main` and `develop` are to be protected: pull request required, the `ci`
   status check required, stale approvals dismissed on new commits, force pushes
   blocked. **Protection is not applied yet**; see OQ-12 in
   [OPEN_QUESTIONS.md](OPEN_QUESTIONS.md). Until it is, these rules hold by
   convention.
3. Branch names carry the issue number: `feature/12-batch-upload`.
4. A `release/*` branch takes no new features, only version bump, changelog, and
   fixes for problems found in stabilization.
5. After a release merges to `main`, it merges back to `develop` so that fixes
   made during stabilization are not lost.
6. Never rewrite history on a shared branch.

## 3. Commit convention

Conventional Commits, so that the changelog can be assembled from history and
the intent of a change is readable without opening it.

```
<type>(<optional scope>): <subject>

<body: what changed and why>

<footer: Closes #<issue>>
```

Types: `feat`, `fix`, `docs`, `chore`, `refactor`, `test`, `ci`, `build`, `perf`.

## 4. Pull request checklist

Enforced by `.github/PULL_REQUEST_TEMPLATE.md` and by review.

- [ ] Targets `develop`, or `main` for a release or hotfix.
- [ ] Linked to an issue.
- [ ] CI green: lint, tests, dependency audit, container build, SBOM.
- [ ] Tests added or updated for the behaviour changed, or the reason none were
      needed is stated.
- [ ] Documentation in `docs/` updated where scope, requirements, architecture,
      or process changed.
- [ ] `TRACEABILITY_MATRIX.md` updated if a requirement, story, or test changed.
- [ ] Anything inferred is marked `(Assumption)` and listed in
      [ASSUMPTIONS.md](ASSUMPTIONS.md).
- [ ] Anything unanswered is recorded in
      [OPEN_QUESTIONS.md](OPEN_QUESTIONS.md) rather than guessed.
- [ ] No secrets, account identifiers, or personal data.
- [ ] No em dashes introduced in documentation.
- [ ] Reviewed by a CODEOWNER.

## 5. Definition of Ready

An issue may enter Build only when all of these hold. The purpose is to stop
work starting on something that cannot be finished or verified.

1. The story is in "As a, I want, so that" form with a persona from the
   interviews.
2. Acceptance criteria are written as Given / When / Then and are testable.
3. A source tag names where the requirement came from.
4. Related requirement IDs are listed.
5. Dependencies are identified and either resolved or explicitly accepted.
6. No unresolved open question blocks the work. If one does, the issue stays in
   Backlog and the question is escalated.
7. It is estimated.
8. It is small enough to complete inside one iteration. If not, it is split.

## 6. Definition of Done

A story is done when all of these hold. "It works on my machine" is not on this
list.

1. Acceptance criteria demonstrably met.
2. Unit and integration tests cover the new behaviour, including its failure
   paths.
3. CI green on the pull request.
4. Reviewed and approved by a CODEOWNER.
5. Documentation updated where the change touches documented behaviour.
6. Traceability matrix updated.
7. No new secret, account identifier, or personal data introduced.
8. Merged to `develop`.
9. Any assumption made is recorded in [ASSUMPTIONS.md](ASSUMPTIONS.md); any
   question raised is recorded in [OPEN_QUESTIONS.md](OPEN_QUESTIONS.md).

The prototype-level Definition of Done, which is a different and larger thing,
is in [02_PROJECT_SCOPE.md](02_PROJECT_SCOPE.md) section 4.

## 7. Releases and versioning

**Semantic Versioning.** `MAJOR.MINOR.PATCH`.

While the prototype is pre-release it stays on `0.x`. Under SemVer, `0.x` makes
no backward-compatibility promise, which is honest for something whose API does
not exist yet.

**Release procedure**

1. Cut `release/vX.Y.Z` from `develop`.
2. Bump the version in `backend/pyproject.toml` and `frontend/package.json`.
3. Move `CHANGELOG.md` entries from Unreleased into a dated version section.
4. Stabilize: fixes only, no new features.
5. Open a pull request to `main`. CI must be green.
6. Merge, then create the `vX.Y.Z` tag through the GitHub Releases web interface
   with `main` as the target. See below.
7. Merge `main` back into `develop`.
8. The `v*` tag is what the deployment workflow triggers on, once that workflow
   is enabled. A tag created in the Releases interface fires the same event as a
   pushed one, so the trigger is unaffected.

**Tags are created through GitHub Releases from `main`, not pushed from a
session.** The session git proxy rejects pushes to `refs/tags/*` with HTTP 403
while accepting pushes to `refs/heads/*` on the same remote with the same
credentials, so `git push origin vX.Y.Z` is not a usable step. Release v0.1.0
was created in the Releases interface, tagged at `79d5ac7` on `main`. This is
the normal path for this repository, not a one-time workaround. Recorded as
OQ-18 in [OPEN_QUESTIONS.md](OPEN_QUESTIONS.md).

Every commit on `main` is a release. That is the whole point of keeping it
separate from `develop`.

## 8. Work tracking

Per Decision D-7. GitHub Issues, with labels:

| Label group | Values |
| --- | --- |
| Epic | `epic:single-label-verification`, `epic:batch-verification`, `epic:usability-accessibility`, `epic:platform-security-deployment`, `epic:documentation` |
| Priority | `priority:must`, `priority:should`, `priority:could` |
| Type | `type:story`, `type:bug`, `type:task` |

Each user story in [04_USER_STORIES.md](04_USER_STORIES.md) is one issue. The
issue is the unit of work; the document is the readable narrative. When they
disagree, the document is corrected, because it is the one that carries
traceability.

A GitHub Project board is intended but was **not** created; Projects v2 is a
GraphQL-only API and is not reachable through this session's proxy. It is
recorded as a manual step in [OPEN_QUESTIONS.md](OPEN_QUESTIONS.md).

## 9. Resolving open questions and assumptions

This is the mechanism that keeps the documents from drifting into fiction.

**An open question is resolved by a commit**, never by a conversation that
leaves no trace. The commit must, in one change:

1. Remove the entry from [OPEN_QUESTIONS.md](OPEN_QUESTIONS.md), or mark it
   resolved with the answer and its source.
2. Update every requirement, story, or document the answer affects.
3. Cite the source of the answer, so a later reader can check it.
4. Reference the question identifier in the commit message, for example
   `docs: resolve OQ-4, numeric tolerance for alcohol content`.

**An assumption is resolved the same way.** When an assumption is confirmed, the
`(Assumption)` marker is removed and replaced with a source tag. When it is
contradicted, the affected requirement is changed and the change is traced.

The rule behind both: an unanswered question is recorded, never guessed. A guess
that reaches a requirement becomes indistinguishable from a fact within one
revision, and there is no way to find it again afterwards.
