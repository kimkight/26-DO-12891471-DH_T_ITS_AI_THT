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
| Availability of the service | Resource exhaustion through very large batches | Batch file-count limit enforced before any file is processed (`TTB_MAX_BATCH_FILES`, NFR-7) | A batch of files each just under the size limit can still be expensive. No total-bytes cap on a batch yet. |
| Container runtime | Malicious file exploiting an image decoder | MIME type checked against an allowlist before decoding; decoding runs as an unprivileged user in a container with no mounted volumes | Image parsing libraries remain a real attack surface. A decoder vulnerability could execute in the container. No seccomp or AppArmor profile is defined yet. |
| Container runtime | Privilege escalation after a compromise | Container runs as UID 10001, non-root, with `nologin` shell; application files owned by root and not writable at runtime | Container escape through a kernel vulnerability is unmitigated by this control. |
| Uploaded label artwork | Disclosure through retention | Nothing is written to disk, database, object storage, or cache; buffers are released with the request (NFR-6) | Content exists in process memory while the request runs, and could appear in a core dump or memory snapshot. |
| Uploaded label artwork | Disclosure through logs | No image content or extracted field value is logged (NFR-6) | An unhandled exception could put field content into a stack trace. Error handling must be written with this in mind. |
| Data in transit | Interception | TLS terminated at the Application Load Balancer | Traffic between the load balancer and the task travels inside the VPC. Not end-to-end encrypted to the container. |
| Verification results | A wrong result treated as authoritative | Three-outcome design with a human-review band; every result carries the label value, the application value, and the score, so an agent can check the reasoning (FR-3) | The tool can be wrong. A rushed agent may accept a match without checking. This is the central residual risk and is addressed by design, not eliminated. |
| Software supply chain | Compromised or vulnerable dependency | `pip-audit` and `npm audit` in CI; Dependabot weekly for pip, npm, GitHub Actions, and Docker; SBOM generated for every image | Base images are not yet pinned by digest. A dependency compromised between audit runs is not detected. |
| Build and deploy pipeline | Stolen long-lived cloud credentials | No static AWS access keys anywhere. Deployment authenticates through GitHub OIDC to an IAM role. | The OIDC trust policy must be scoped to this repository and to specific branches. That policy does not exist yet and must be reviewed when written. |
| The application itself | Unauthorized use | **None. There is no authentication.** (Decision D-9) | Anyone who reaches the URL can use the service. Accepted for a prototype that stores nothing and handles no sensitive data; unacceptable for production. See section 3. |

## 2. Secure-by-design controls present in the scaffold

These exist in the repository today and are verifiable by reading it.

| Control | Where | Verified by |
| --- | --- | --- |
| Non-root container user (UID 10001, `nologin`) | `Dockerfile` | CI asserts `id -u` is not 0 in the built image |
| Multi-stage build; Node toolchain absent from the runtime image | `Dockerfile` | Runtime stage starts from `python:3.11-slim-bookworm` |
| No volumes mounted; nothing writable persists | `docker-compose.yml`, `Dockerfile` | Inspection |
| Python dependency audit | `.github/workflows/ci.yml` | `pip-audit --strict` |
| Node dependency audit | `.github/workflows/ci.yml` | `npm audit --audit-level=high` |
| SBOM for the container image | `.github/workflows/ci.yml` | Syft via `anchore/sbom-action`, SPDX JSON, uploaded as a build artifact |
| Automated dependency updates | `.github/dependabot.yml` | Weekly for pip, npm, GitHub Actions, Docker |
| OIDC instead of static keys | `.github/workflows/deploy.yml` | `aws-actions/configure-aws-credentials` with `role-to-assume`; no secret access keys |
| Least-privilege workflow tokens | `.github/workflows/ci.yml` | `permissions: contents: read` |
| Input size and MIME validation | `backend/app/config.py` | Limits defined; enforcement is written with the upload endpoints, which do not exist yet |
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
| No authentication (D-9) | The prototype stores nothing and handles no sensitive data. Marcus scoped it: "for a prototype? Just don't do anything crazy." | Agency identity integration, role separation between agents and supervisors, and session management. |
| No persistence (D-9) | Removes retention and privacy questions entirely for the exercise. Marcus names "PII considerations, document retention policies." | An audit record of every verification, with a retention schedule set by records management, and a defined disposition. |
| No audit trail | Follows from having neither authentication nor persistence. | Who ran what, when, against which label, and what the tool returned. In a regulatory workflow this is not optional. |
| No rate limiting or WAF | Not exposed to the public workload. | Rate limiting, AWS WAF, and request throttling at the load balancer. |
| Capitalization checked, boldness not | 27 CFR 16.22(a)(2) requires both. The prototype checks capitals only and must not imply otherwise (OOS-4). | Typographic analysis, or an explicit statement in the product that boldness remains a manual check. |
| Base images pinned by tag | Acceptable while nothing is released. | Digest pinning plus image scanning on push in ECR. |

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
| Amazon Bedrock | Optional, off by default, not on the committed path (D-4) |

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
