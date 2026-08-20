# ADR 0001: Deploy the prototype to AWS commercial us-east-1, portable to GovCloud

| | |
| --- | --- |
| Status | Accepted |
| Date | 2026-08-20 |
| Author | Kimberly D. Kight |
| Decision reference | D-1, D-11 |

## Context

The assignment requires a "Deployed Application URL: Working prototype we can
access and test." [Source: Deliverables] It does not name a cloud provider and
leaves technical choices open: "You are free to use any programming languages,
frameworks, or libraries you prefer." [Source: Technical Requirements]

Marcus Williams states the agency's current position: "We're on Azure now after
the migration in 2019." He also describes what that migration cost in compliance
terms: "don't get me started on the FedRAMP certification process. Took 18
months just for the paperwork." [Source: Marcus Williams interview]

The agency's intended production environment for this class of system is AWS
GovCloud (US). [Source: Decision D-11]

Two facts shape the decision. First, this is explicitly a standalone proof of
concept with no COLA integration, so it inherits no platform dependency from the
existing estate. [Source: Marcus Williams interview] Second, the eventual
production target is GovCloud, which means a prototype built in a way that
cannot move there would have to be rebuilt.

## Decision

Deploy the prototype to **AWS commercial, region `us-east-1`**, and write the
infrastructure code so that the same modules target **AWS GovCloud (US)** without
redesign.

## Alternatives considered

### Microsoft Azure

The agency migrated to Azure in 2019, so Azure matches the current estate.
[Source: Marcus Williams interview]

Not chosen because Decision D-1 specifies AWS, and because the stated production
target for this system is AWS GovCloud (US) rather than Azure Government
(Decision D-11). The prototype is standalone and integrates with nothing in the
existing estate, so estate alignment carries less weight here than alignment
with where this system is intended to go.

The discrepancy between the agency's Azure estate and this AWS target is real
and is not resolved by this ADR. It is recorded as OQ-1 in
[../OPEN_QUESTIONS.md](../OPEN_QUESTIONS.md).

### Deploy directly to AWS GovCloud (US)

Would exercise the actual production target rather than approximating it.

Not chosen because GovCloud requires a separate account with a sponsorship and
vetting process, which is not available for a time-constrained take-home
exercise, and because reviewers need a URL they can reach without agency
credentials. [Source: Deliverables] Decision D-11 states this assignment
deploys to commercial `us-east-1`.

### A platform-as-a-service host such as Heroku, Render, or Fly.io

Would be the fastest route to a working URL.

Not chosen because it would make the prototype a poor predictor of the
production path. None of these is a federal cloud environment, and moving from
one to ECS later would discard the deployment work rather than build on it.

### No deployment; source code only

Not chosen because the assignment lists the deployed URL as one of exactly two
deliverables. [Source: Deliverables]

## Consequences

**Positive**

- Reviewers get a reachable URL without agency credentials.
- The infrastructure work is a step toward the GovCloud target rather than a
  detour, provided the portability rules in NFR-10 are followed.
- AWS provides the managed container services this design needs, so nothing has
  to be self-hosted.

**Negative**

- The prototype runs on a different cloud from the agency's current Azure
  estate. If a future decision keeps the estate on Azure, the infrastructure
  work does not transfer.
- Commercial `us-east-1` is not GovCloud. Portability is a property of how the
  code is written, and it stays unproven until someone actually deploys to
  GovCloud.
- Running in commercial AWS incurs cost.

**Risks accepted**

- That `us-east-1` behaviour differs from GovCloud in ways not caught until a
  GovCloud deployment is attempted. Service availability differences are the
  most likely source; the mitigation is the constraint set in NFR-10 and
  `infra/README.md`, not a claim that the risk is absent.
- FedRAMP in-scope status of the services used is **not asserted** in this ADR
  and must be confirmed at deployment time. See
  [../06_SECURITY_AND_COMPLIANCE.md](../06_SECURITY_AND_COMPLIANCE.md) section 4.

## References

- [../01_PROJECT_CHARTER.md](../01_PROJECT_CHARTER.md) section 8
- [../05_ARCHITECTURE.md](../05_ARCHITECTURE.md) section 9
- [ADR 0002](0002-compute-ecs-fargate-not-app-runner.md)
