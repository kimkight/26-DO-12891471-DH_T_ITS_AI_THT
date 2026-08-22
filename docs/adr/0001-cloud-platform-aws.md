# ADR 0001: Deploy the prototype to AWS commercial us-east-1, portable to a FedRAMP-authorized government region

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

Decision D-11 records the target environment: the agency states it is on Azure
(Marcus Williams interview); this prototype deploys to AWS commercial
`us-east-1` by the author's choice, for delivery speed on the platform the
author knows best, which the assignment permits; the architecture is
container-first and cloud-portable by design; a production deployment would
target the agency's platform, presumed to be Azure Government, and that would be
a deployment change rather than a redesign; FedRAMP status of any target service
is confirmed against the FedRAMP Marketplace at deployment time, not asserted
here.
[Source: [../cloud_choice_and_abv_assumption.md](../cloud_choice_and_abv_assumption.md) section 1]

Two facts shape the decision. First, this is explicitly a standalone proof of
concept with no COLA integration, so it inherits no platform dependency from the
existing estate. [Source: Marcus Williams interview] Second, whichever platform
production lands on, it will be a FedRAMP-authorized government region, which
means a prototype built in a way that cannot move would have to be rebuilt.

## Decision

Deploy the prototype to **AWS commercial, region `us-east-1`**, and write the
infrastructure code so that the same modules target **AWS GovCloud (US)** without
redesign.

Keep the application container-first and free of provider-specific logic, so
that a production deployment to **the agency's platform, presumed to be Azure
Government**, is a deployment change rather than a redesign. FedRAMP status of
any target service is confirmed against the FedRAMP Marketplace at deployment
time, not asserted here. [Source: Decision D-11]

## Alternatives considered

### Microsoft Azure

The agency migrated to Azure in 2019, so Azure matches the current estate.
[Source: Marcus Williams interview]

Not chosen for the reasons set out in "Why not Azure, given the agency runs
Azure" below. The short form: the assignment permits any platform, the prototype
is standalone, and delivering a working deployment on the platform the author
knows best is the better trade for a one-week exercise.

The discrepancy between the agency's Azure estate and this AWS target is real.
It is recorded as OQ-1 in [../OPEN_QUESTIONS.md](../OPEN_QUESTIONS.md), which
this ADR answers as the author's decision, not as a stakeholder answer.

### Deploy directly to AWS GovCloud (US)

Would exercise a FedRAMP-authorized government region rather than approximating
one.

Not chosen because GovCloud requires a separate account with a sponsorship and
vetting process, which is not available for a time-constrained take-home
exercise, and because reviewers need a URL they can reach without agency
credentials. [Source: Deliverables] Decision D-11 states this prototype
deploys to commercial `us-east-1`.

### A platform-as-a-service host such as Heroku, Render, or Fly.io

Would be the fastest route to a working URL.

Not chosen because it would make the prototype a poor predictor of the
production path. None of these is a federal cloud environment, and moving from
one to ECS later would discard the deployment work rather than build on it.

### No deployment; source code only

Not chosen because the assignment lists the deployed URL as one of exactly two
deliverables. [Source: Deliverables]

## Why not Azure, given the agency runs Azure

The honest record, so a reviewer who asks "you read that we're on Azure and
built on AWS, why?" gets an answer that does not contradict the interview.
[Source: [../cloud_choice_and_abv_assumption.md](../cloud_choice_and_abv_assumption.md) section 1]

### Context

1. **The prototype does not have to run inside TTB's Azure tenant.** The
   assignment says "You are free to use any programming languages, frameworks,
   or libraries you prefer" [Source: Technical Requirements], and Marcus says
   the prototype is "standalone," not integrated with COLA, and "could
   potentially inform future procurement decisions... years away."
   [Source: Marcus Williams interview]
2. **What must survive a platform change is the design, not the hosting.** A
   single container image, Terraform with no provider-specific application
   logic, OCR in-process with no cloud ML dependency, and an optional vision
   fallback behind an interface. Moving from ECS Fargate to Azure Container Apps
   or AKS is a deployment change, not a rewrite. The firewall lesson from the
   vendor pilot is the reason the default path has no cloud API dependency at
   all, and that decision is what makes the platform swappable.
   [Source: Marcus Williams interview; Decision D-4]
3. **Delivering a working, deployed prototype in the time available on the
   platform the author knows best is the better trade** than delivering a
   half-working one on the platform that matches the agency. The assignment says
   exactly this: "A working core application with clean code is preferred over
   ambitious but incomplete features." [Source: Technical Requirements]
4. **Both platforms have FedRAMP High government regions** (AWS GovCloud;
   Azure Government). The compliance story is equivalent, so the portability
   statement names Azure Government as the likely production target rather than
   GovCloud.

**Public evidence, researched 2026-08-20.** Treasury's department-wide shared
cloud, the Workplace Community Cloud (WC2), runs on commercial AWS at FedRAMP
Moderate and High (WC2-M and WC2-H), operated through the OCIO with Booz Allen
as integrator; Treasury stated an intent to add Azure to WC2 and in 2023 awarded
SAIC the $1.3B T-Cloud broker contract covering AWS, Microsoft, Google, IBM, and
Oracle. No public document states which provider TTB's own systems (COLAs
Online, myTTB) run on; TTB's FY 2027 budget justification describes replacing
COLAs Online with myTTB but names no cloud provider. So the real-world Treasury
baseline is AWS-first and multicloud by policy; the "Azure since 2019" statement
belongs to the assignment's scenario and is treated as stakeholder context, not
verified fact. All three things are true at once: the scenario's stakeholder
says Azure, public Treasury evidence says AWS WC2 plus multicloud, and the
design is portable to either.

### Consequence

**Negative.** The prototype's infrastructure code does not exercise the agency's
actual platform, so the Terraform would need an Azure provider module before a
pilot. Portability on the Azure path is therefore a property of the container
image and the absence of provider-specific application logic, not of any
infrastructure code that exists in this repository.

## Consequences

**Positive**

- Reviewers get a reachable URL without agency credentials.
- The infrastructure work is a step toward an AWS GovCloud (US) target rather
  than a detour, provided the portability rules in NFR-10 are followed.
- AWS provides the managed container services this design needs, so nothing has
  to be self-hosted.

**Negative**

- The prototype runs on a different cloud from the agency's stated Azure
  estate. The infrastructure code does not exercise that platform, so the
  Terraform would need an Azure provider module before a pilot.
- Commercial `us-east-1` is not a government region. Portability is a property
  of how the code is written, and it stays unproven until someone actually
  deploys to AWS GovCloud (US) or to Azure Government.
- Running in commercial AWS incurs cost.

**Risks accepted**

- That `us-east-1` behaviour differs from a government region in ways not
  caught until a deployment there is attempted. Service availability differences
  are the most likely source; the mitigation is the constraint set in NFR-10 and
  `infra/README.md`, not a claim that the risk is absent.
- FedRAMP in-scope status of the services used is **not asserted** in this ADR
  and must be confirmed at deployment time. See
  [../06_SECURITY_AND_COMPLIANCE.md](../06_SECURITY_AND_COMPLIANCE.md) section 4.

## References

- [../cloud_choice_and_abv_assumption.md](../cloud_choice_and_abv_assumption.md) section 1
- [../01_PROJECT_CHARTER.md](../01_PROJECT_CHARTER.md) section 8
- [../05_ARCHITECTURE.md](../05_ARCHITECTURE.md) section 9
- [../OPEN_QUESTIONS.md](../OPEN_QUESTIONS.md) OQ-1
- [ADR 0002](0002-compute-ecs-fargate-not-app-runner.md)
