# Security and Compliance

Scope note: this document describes the prototype as built and as designed. It
does not claim any authorization, certification, or compliance status. Where a
status would have to be confirmed with an authoritative source, this document
says so rather than asserting it.

The prototype handles no sensitive data by design: "We're not storing anything
sensitive for this exercise." [Source: Marcus Williams interview]

## 1. Threat model

Limited to what the prototype actually does: accept an image and form fields
over HTTP, process them in memory, and return a result. There is no datastore,
no user account, and no session.

| Asset | Threat | Mitigation in this build | Residual risk |
| --- | --- | --- | --- |
| Availability of the service | Resource exhaustion through very large uploads | Per-file size limit enforced before the body is read into memory (`TTB_MAX_UPLOAD_BYTES`, NFR-7) | A distributed flood still saturates the service. No rate limiting or WAF in the prototype. |
| Availability of the service | Resource exhaustion through very large batches | Batch file-count limit enforced before any file is processed (`TTB_MAX_BATCH_FILES`), and a whole-envelope byte cap checked from `Content-Length` before the body is read (`TTB_MAX_BATCH_BYTES`, NFR-7). The deployed values are set to what the task's memory holds; see 09_DEPLOYMENT.md section 4. | A batch inside both caps still occupies the single task for its duration, and there is no queue and no second task to take the next one. |
| Container runtime | Malicious file exploiting an image decoder | MIME type checked against an allowlist before decoding; decoding runs as an unprivileged user in a container with no mounted volumes | Image parsing libraries remain a real attack surface. A decoder vulnerability could execute in the container. No seccomp or AppArmor profile is defined yet. |
| Container runtime | Privilege escalation after a compromise | Container runs as UID 10001, non-root, with `nologin` shell; application files owned by root and not writable at runtime | Container escape through a kernel vulnerability is unmitigated by this control. |
| Uploaded label artwork | Disclosure through retention | Nothing is written to disk, database, object storage, or cache; buffers are released with the request (NFR-6) | Content exists in process memory while the request runs, and could appear in a core dump or memory snapshot. |
| Uploaded label artwork | Disclosure through logs | No image content or extracted field value is logged (NFR-6) | An unhandled exception could put field content into a stack trace. Error handling must be written with this in mind. |
| Data in transit | Interception | **None in the prototype: the listener is plain HTTP.** See section 3.1. | Label artwork, application field values, and results cross the network in the clear. The production fix is an ACM certificate and an HTTPS listener; even then, traffic from the load balancer to the task would travel inside the VPC unencrypted, so it would still not be end-to-end to the container. |
| Verification results | A wrong result treated as authoritative | Three-outcome design with a human-review band; every result carries the label value, the application value, and the score, so an agent can check the reasoning (FR-3) | The tool can be wrong. A rushed agent may accept a match without checking. This is the central residual risk and is addressed by design, not eliminated. |
| Software supply chain | Compromised or vulnerable dependency | `pip-audit` and `npm audit` in CI; Dependabot weekly for pip, npm, GitHub Actions, and Docker; SBOM generated for every image | Base images are not yet pinned by digest. A dependency compromised between audit runs is not detected. |
| Build and deploy pipeline | Stolen long-lived cloud credentials | No static AWS access keys anywhere. Deployment authenticates through GitHub OIDC to an IAM role. The trust policy is written (`infra/terraform/iam.tf`): it requires `aud` to be `sts.amazonaws.com` and `sub` to match this repository at `develop`, `main`, a `v*` tag, or the `production` environment, and the role's permissions name the one ECR repository and the one ECS service. | The policy has never been applied, so it has been reviewed but not exercised. A workflow file on `develop` or `main` can reach the role, so write access to those branches is write access to the deployment. |
| The application itself | Unauthorized use | **None. There is no authentication.** (Decision D-9) | Anyone who reaches the URL can use the service. Accepted for a prototype that stores nothing and handles no sensitive data; unacceptable for production. See section 3. |

## 2. Secure-by-design controls present in the scaffold

These exist in the repository today and are verifiable by reading it.

| Control | Where | Verified by |
| --- | --- | --- |
| Non-root container user (UID 10001, `nologin`) | `Dockerfile` | CI asserts `id -u` is not 0 in the built image |
| Multi-stage build; Node toolchain absent from the runtime image | `Dockerfile` | Runtime stage starts from `python:3.11-slim-bookworm` |
| No volumes mounted; nothing writable persists | `docker-compose.yml`, `Dockerfile` | Inspection |
| Python dependency audit | `.github/workflows/ci.yml` | `pip-audit --no-deps` over both fully pinned lock files, runtime and dev |
| Node dependency audit | `.github/workflows/ci.yml` | `npm audit --audit-level=high` |
| SBOM for the container image | `.github/workflows/ci.yml` | Syft via `anchore/sbom-action`, SPDX JSON, uploaded as a build artifact |
| Automated dependency updates | `.github/dependabot.yml` | Weekly for pip, npm, GitHub Actions, Docker |
| OIDC instead of static keys | `.github/workflows/deploy.yml`, `infra/terraform/iam.tf` | `aws-actions/configure-aws-credentials@v6` with `role-to-assume`; no secret access keys. The role's trust policy is scoped to this repository |
| Least-privilege workflow tokens | `.github/workflows/ci.yml` | `permissions: contents: read` |
| Input size and MIME validation | `backend/app/config.py`, `backend/app/api.py`, `backend/app/verify.py` | Envelope size checked from `Content-Length` before the body is read; per-image size and MIME type checked before decoding. Covered by `backend/tests/test_api_validation.py` |
| Secret hygiene | `.gitignore`, `.pre-commit-config.yaml` | `.env` ignored; `detect-private-key` hook |
| Code review required | `.github/CODEOWNERS`, branch protection | Every change requires review from `@kimkight` |

**Not yet done, and tracked:** base images are pinned by tag rather than by
`sha256` digest. A `TODO` marks this in the `Dockerfile`; it must be closed
before the first tagged release.

## 3. Prototype limitations and their production path

Stated so that no reader mistakes a prototype boundary for a considered
judgment that the control is unnecessary.

| Limitation | Why it is acceptable now | What production requires |
| --- | --- | --- |
| No authentication (D-9), and the load balancer is internet-facing | Accepted, not defaulted into: see below. The prototype stores nothing and handles no sensitive data. Marcus scoped it: "for a prototype? Just don't do anything crazy." | An authentication layer at the edge, agency identity integration, role separation between agents and supervisors, and session management. |
| Plain HTTP; no TLS, no certificate, no custom domain | There is no domain to attach a certificate to, and the deliverable is a URL an evaluator can open at the load balancer's own DNS name. Traffic is unencrypted in transit. | An ACM certificate, an HTTPS listener on port 443, and a redirect from port 80. The Terraform has one listener and adding the second is a small change; the certificate is the part that needs a domain. |
| Task runs in a public subnet with a public IP | A Fargate task must reach ECR and CloudWatch Logs to start. The alternatives, a NAT gateway or a set of interface endpoints, each cost more per hour than the task. Its security group accepts inbound traffic only from the load balancer, so the public IP is an egress path rather than an entrance. | Private subnets, with either a NAT gateway or VPC interface endpoints for ECR, S3, and CloudWatch Logs. |
| Terraform state is local and unencrypted at rest beyond the operator's disk | One operator, one machine, and a stack whose resting state is destroyed. The state file is git-ignored, and it contains the account number and every ARN. | An S3 backend with versioning and server-side encryption, plus a DynamoDB lock table. See 09_DEPLOYMENT.md section 11. |
| No persistence (D-9) | Removes retention and privacy questions entirely for the exercise. Marcus names "PII considerations, document retention policies." | An audit record of every verification, with a retention schedule set by records management, and a defined disposition. |
| No audit trail, and no load balancer access logs | Follows from having neither authentication nor persistence. Access logs would need an S3 bucket and a bucket policy, which is a second stack to fund and destroy. | Who ran what, when, against which label, and what the tool returned. In a regulatory workflow this is not optional. Load balancer access logs to S3 are the cheap half of it. |
| No rate limiting or WAF | **This row used to read "not exposed to the public workload." That is no longer true.** Once deployed the load balancer is internet-facing with no authentication, so the prototype is exposed to anyone who learns its DNS name. What bounds the exposure is that nothing is stored and no credential is held, so the risk is open use of compute rather than disclosure. | Rate limiting, AWS WAF, and request throttling at the load balancer. |
| Capitalization checked, boldness not | 27 CFR 16.22(a)(2) requires both. The prototype checks capitals only and must not imply otherwise (OOS-4). | Typographic analysis, or an explicit statement in the product that boldness remains a manual check. |
| Base images pinned by tag | Acceptable while nothing is released. | Digest pinning. Image scanning on push in ECR is now configured (`infra/terraform/ecr.tf`); it reports findings and blocks nothing, and pretending otherwise would be a control this prototype does not have. |

### 3.1 The internet-facing prototype, stated as an acceptance

OQ-13 item 2 raised this as a conflict rather than a detail: reviewers need
access to test the prototype, which points at an internet-facing load balancer,
and there is no authentication (D-9), which points the other way. It is
recorded here as an explicit acceptance by the author rather than left to a
default.

**The posture.** Internet-facing, no authentication, plain HTTP at the load
balancer's DNS name, for the length of an evaluation window. The deliverable
the assignment asks for is a working prototype an evaluator can open, and that
is a URL.

**What bounds it.** Nothing is stored (NFR-6): no database, no object store, no
disk write, and the batch response stream is the only copy of a result. The
task holds no credential, and its IAM role has no policy attached at all. There
is no path from the application to any other resource in the account.

**What the residual risks actually are**, named rather than waved at:

1. **Open use of compute.** Anyone who learns the DNS name can submit images
   and consume the single task. There is no rate limit, so the practical
   consequence is denial of service against a prototype, and an AWS bill for a
   stack estimated at about $0.12 an hour.
2. **Unencrypted transit.** Label artwork and application field values cross
   the network in the clear, and so do the results. The data is a beverage
   label and its declared fields rather than anything personal, but "not
   sensitive" is a judgment about this sample data and not a property of the
   channel.
3. **No attribution.** With no authentication and no access logs, there is no
   record of who used it.

**The production fix**, in the order it would be done: an ACM certificate and
an HTTPS listener with a redirect from port 80; an authentication layer at the
edge integrated with agency identity; then AWS WAF and rate limiting; then
access logs and an application audit trail.

**The mitigation available now, without changing the posture.** The
`ingress_cidr_blocks` variable in `infra/terraform/variables.tf` narrows the
load balancer's security group to a single address. Between demonstrations, the
stronger mitigation is `terraform destroy`, which is the runbook's resting
state.

## 4. FedRAMP posture

**No FedRAMP status is asserted in this document.**

The production target is the agency platform (Azure per the interview); AWS
GovCloud if AWS were retained. Both have FedRAMP High government regions, so the
compliance story is equivalent either way, and the in-scope status that matters
is the one for whichever platform and region a deployment actually uses.
[Source: Decision D-11;
[cloud_choice_and_abv_assumption.md](cloud_choice_and_abv_assumption.md)
section 1]

AWS services this system uses or would use:

| Service | Role |
| --- | --- |
| Amazon ECR | Container image registry |
| Amazon ECS on AWS Fargate | Compute |
| Elastic Load Balancing (Application Load Balancer) | Ingress and TLS termination |
| AWS IAM | Roles for the task, task execution, and the CI OIDC principal |
| Amazon CloudWatch Logs | Container logging |
| Amazon Bedrock | Designed as an optional fallback in ADR 0003 and not built; not used (D-4) |

The in-scope status of each of these services, for the relevant impact level and
for the relevant region, **must be confirmed at deployment time** against the
FedRAMP Marketplace and the authoritative AWS list:

> https://marketplace.fedramp.gov/
>
> https://aws.amazon.com/compliance/services-in-scope/FedRAMP/

If the deployment target is the agency platform (Azure per the interview) rather
than AWS, the equivalent confirmation is against the FedRAMP Marketplace listing
for the Azure Government services used.

This is a deployment-time gate, not a documentation exercise. Status varies by
service, by region, and by impact level, and it changes over time; a claim
recorded here would go stale and could be wrong.

**AWS App Runner was excluded on this basis.** Decision D-2 records that App
Runner is not on the AWS FedRAMP services-in-scope list. See
[ADR 0002](adr/0002-compute-ecs-fargate-not-app-runner.md). That exclusion is a
design constraint taken from the decision record; the current contents of the
AWS list must still be confirmed at deployment time by whoever deploys.

Marcus's experience frames why this matters: the Azure migration's FedRAMP
process "Took 18 months just for the paperwork."
[Source: Marcus Williams interview]

## 5. ATO readiness

This system would require an **agency Authorization to Operate** before
operational use with real application data. Nothing in this repository
constitutes an ATO, an assessment, or a control implementation statement.

What this repository provides toward that package:

| Artifact | Where | ATO relevance |
| --- | --- | --- |
| System purpose, boundary, and stakeholders | `docs/01_PROJECT_CHARTER.md` | System description |
| Explicit scope boundary, in and out | `docs/02_PROJECT_SCOPE.md` | Authorization boundary definition |
| Requirements with sources and acceptance criteria | `docs/03_REQUIREMENTS.md` | Functional and non-functional baseline |
| Architecture, data flow, and data handling | `docs/05_ARCHITECTURE.md` | Data flow diagrams; categorization input |
| Threat model with residual risk | This document, section 1 | Risk assessment input |
| Control decisions with alternatives and consequences | `docs/adr/` | Design rationale and traceability |
| SBOM per image build | CI artifact, SPDX JSON | Supply chain inventory |
| Dependency audit results | CI logs | Vulnerability management evidence |
| Test strategy including accessibility | `docs/07_TEST_STRATEGY.md` | Assessment procedures input |
| Change control process | `docs/08_SDLC_PROCESS.md` | Configuration management |
| Traceability from stakeholder statement to test | `docs/TRACEABILITY_MATRIX.md` | Requirements traceability |

What is **absent** and would be required:

- A system security plan mapped to a NIST SP 800-53 control baseline.
- A FIPS 199 security categorization, which drives that baseline.
- Assessment results from an independent assessor.
- A plan of action and milestones.
- Contingency, incident response, and configuration management plans.
- A privacy threshold analysis, and a privacy impact assessment if it triggers.

The control baseline depends on a categorization that no source in this
assignment supplies. It is therefore not guessed; see OQ-10 in
[OPEN_QUESTIONS.md](OPEN_QUESTIONS.md).

## 6. AI governance

### 6.1 Human in the loop

**The tool recommends. The agent decides.**

This is the governing design position, and it is enforced structurally rather
than by policy statement:

1. **No automated decision.** The system returns per-field agreement between the
   label and the application. It does not approve, reject, or score an
   application overall (OOS-8).
2. **A deliberate uncertainty band.** The middle outcome, needs human review,
   exists so the system routes ambiguity to a person instead of resolving it
   silently. This is the direct answer to Dave Morrison: "Technically a
   mismatch? Sure. But it's obviously the same thing. You need judgment."
   [Source: Dave Morrison interview]
3. **Inspectable output.** Every field returns the extracted value, the
   application value, and the score. An agent can see why the tool said what it
   said and overrule it (FR-3).
4. **No claim beyond what is checked.** The warning result reports
   capitalization and body text only, and must not imply that bold type was
   verified (FR-6, OOS-4). Overstating what was checked would be the most
   consequential failure mode in this system, because it would cause an agent to
   skip a check the tool never performed.
5. **A bounded default path.** With the Bedrock fallback off, extraction is
   deterministic OCR rather than a generative model. When the fallback is
   enabled, the result says so, so a reader knows which path produced it (NFR-3).

Adoption risk is a governance concern here, not only a product one. Dave has
watched tools fail: "We ended up with more calls because nobody could figure out
how to navigate it." [Source: Dave Morrison interview] A tool that is trusted
too much is as damaging as one that is not used.

### 6.2 Governance documents to be reviewed and cited

The following must be reviewed against this system, and cited with specific
section references, before any use beyond a prototype. **Their requirements are
deliberately not summarized here**, because none of them was fetched or quoted
during this work, and paraphrasing a governance requirement from memory is
exactly the kind of invention this project's ground rules prohibit.

| Document | Status in this repository |
| --- | --- |
| NIST AI Risk Management Framework (AI RMF 1.0), NIST AI 100-1 | To be reviewed and cited. Not fetched, not quoted, not summarized. |
| NIST AI RMF Generative AI Profile, NIST AI 600-1 | To be reviewed and cited. Relevant only if the Bedrock fallback is enabled. |
| Applicable OMB policy on federal agency use of artificial intelligence | To be reviewed and cited. The controlling memorandum, its current version, and its applicability to a prototype of this kind must be confirmed from the authoritative source. |
| Department of the Treasury AI policy and inventory requirements | To be reviewed and cited. Whether this system would appear in an agency AI use case inventory is unknown. |

Tracked as OQ-11 in [OPEN_QUESTIONS.md](OPEN_QUESTIONS.md).

### 6.3 Model and data considerations for the optional fallback

If the Bedrock fallback is ever enabled, these change and must be reassessed
before it is used:

- Label artwork would leave the container and be sent to an external service.
  That contradicts NFR-3 and the network constraint Marcus describes, and it
  reintroduces the data-handling questions that "nothing is persisted" removes.
- The service and model would need confirmed FedRAMP in-scope status at the
  required impact level, per section 4.
- Generative extraction can produce plausible values that were never on the
  label. In a compliance workflow that failure mode is more dangerous than
  returning nothing, because it is not obviously wrong.
- Data retention terms for the model service would need review against federal
  records requirements.

This is why the fallback is off by default and is not part of the committed
scope; it is a stretch goal (SG-2), not a design assumption.
