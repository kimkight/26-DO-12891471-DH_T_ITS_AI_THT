# ADR 0005: Use Git Flow branching

| | |
| --- | --- |
| Status | Accepted |
| Date | 2026-08-20 |
| Author | Kimberly D. Kight |
| Decision reference | D-6 |

## Context

The repository needs a branching model before the first feature branch, because
changing one later means rewriting protection rules, CI triggers, and the
release procedure.

Two properties of this project shape the choice. Deployment is **not**
continuous: the deployment workflow is committed but disabled, and releases are
expected to be discrete, reviewed events rather than an automatic consequence of
merging. [Source: Decision D-8] And the eventual environment is federal, where a
release is an auditable event and the question "what exactly is running in
production, and who approved it" needs an answer that does not depend on reading
a commit log.

Marcus Williams describes an environment where changes carry authorization
weight: "there's PII considerations, document retention policies, the usual
federal compliance stuff," and a FedRAMP process that "Took 18 months just for
the paperwork." [Source: Marcus Williams interview]

## Decision

Use **Git Flow**. `main` holds releases only; `develop` is the integration
branch; `feature/*`, `release/*`, and `hotfix/*` as needed. Both `main` and
`develop` are protected: pull request required, `ci` status check required,
stale approvals dismissed, force pushes blocked.

## Alternatives considered

### GitHub Flow (single long-lived branch)

One `main` branch, short-lived feature branches, deploy on merge. Simpler, fewer
branches, less ceremony, and it is the better fit for genuinely continuous
deployment.

Not chosen because deployment here is not continuous, and because it gives up
the property that matters most in this context: with GitHub Flow, `main`
contains merged work that has not been released, so "what is in production" is
no longer answerable by looking at a branch. Under Git Flow every commit on
`main` is a release.

### Trunk-based development with release branches

Short-lived branches into trunk, with release branches cut as needed. Strong
model, and it reduces the long-lived merge divergence Git Flow can accumulate.

Not chosen because its benefits depend on high merge frequency and mature
feature-flagging, neither of which applies to a single-contributor prototype.
The overhead would exceed the benefit at this size.

### No defined model

Not chosen. Undefined branching becomes a de facto model that nobody wrote down
and nobody can audit, which is the opposite of what this repository is
demonstrating.

## Consequences

**Positive**

- `main` answers "what is released" without interpretation.
- `develop` gives a place to integrate and stabilize work that is not ready to
  release.
- Release branches create a stabilization window where only fixes land, which
  matches a review-gated release process.
- Hotfix branches allow an urgent fix against a release without dragging in
  unreleased work from `develop`.
- Protection on both branches means every change is reviewed and CI-gated.

**Negative**

- More ceremony than a single-contributor prototype strictly needs. The
  process is sized for where this system is headed, not for its current size.
- Long-lived branches can diverge, making merges harder.
- Every release requires two merges, into `main` and back into `develop`, and
  forgetting the second loses stabilization fixes.
- `develop` as the default branch is less conventional and can surprise
  contributors who expect `main`.

**Risks accepted**

- That the model is heavier than needed if the prototype is never taken further.
  Accepted deliberately: the assignment is evaluated in part on "Code quality and
  organization," and a documented, enforced branching model is part of that.
  [Source: Evaluation Criteria]
- That branch protection cannot be enforced. GitHub does not enforce branch
  protection on private repositories under a Free plan. If the protection API
  rejects the request for that reason, the rules remain the documented process
  and the gap is recorded in [../OPEN_QUESTIONS.md](../OPEN_QUESTIONS.md) rather
  than left silent.

## References

- [../08_SDLC_PROCESS.md](../08_SDLC_PROCESS.md) sections 2, 3, and 7
- [../../.github/workflows/ci.yml](../../.github/workflows/ci.yml)
- [../../.github/PULL_REQUEST_TEMPLATE.md](../../.github/PULL_REQUEST_TEMPLATE.md)
