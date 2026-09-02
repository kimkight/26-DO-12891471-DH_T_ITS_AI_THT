# Security and Compliance

Scope note: this document describes the prototype as built and as designed. It
does not claim any authorization, certification, or compliance status. Where a
status would have to be confirmed with an authoritative source, this document
says so rather than asserting it.

**The premise, restated for v1.3.0.** This document was first written when the
prototype's input was a photograph of a beverage label and five typed values,
and it said the prototype handled no sensitive data, quoting Marcus Williams:
"We're not storing anything sensitive for this exercise." [Source: Marcus
Williams interview] That sentence is still true of storage and no longer
describes the input. Since [ADR 0008](adr/0008-cola-document-extraction.md)
and [ADR 0010](adr/0010-embedded-label-artwork.md) the primary input is a filed
application, TTB F 5100.31, and a filed copy carries the applicant's signature
image on page 2, the applicant's name and address, and the permit and registry
numbers on page 1. The prototype reads the pages, keeps none of them (NFR-6,
section 3.2) and logs nothing they contain; but it receives them, over a
listener that is plain HTTP, from anyone who has the URL. The sections below
are written against that input. Where an acceptance used to rest on "nothing
sensitive", it now rests on two narrower facts: nothing is stored, and nothing
on the wire is a credential, a session or a record of who used the tool,
because there is no authentication and no persistence. The filing itself is on
the wire, and section 3.1 says so in those words (code review finding 20,
#119).

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
| Uploaded label artwork, and the filed application | Disclosure through retention | Nothing is kept: no database, no bucket, no cache and no log of content. An upload lives in process memory, and each image lives briefly in the temporary directory while the OCR engine reads it, and both are gone when the request returns (NFR-6; section 3.2 says exactly where the bytes are). Asserted by `TestNothingIsRetained` in the backend suite, which watches the temporary and working directories across a request | Content exists in process memory, and in the engine's temporary file, while the request runs, and could appear in a core dump or memory snapshot. |
| Uploaded label artwork, and the filed application | Disclosure through logs | No image content, uploaded filename or extracted field value is logged (NFR-6); the application's logger writes counts, timings and path names, as one JSON line per record, and the retention test asserts the filename and the values are absent from what it wrote | An unhandled exception could put field content into a stack trace. Error handling must be written with this in mind. |
| Data in transit | Interception | **None in the prototype: the listener is plain HTTP.** See section 3.1, which sizes the fix and says why it is not done for the evaluation stack. | The filed application, its signature image, the label artwork, the declared values and the results cross the network in the clear. No credential, session or identity does, because none exists. The production fix is an ACM certificate, an HTTPS listener on 443 and a redirect from 80, roughly one Terraform block plus a domain; even then, traffic from the load balancer to the task would travel inside the VPC unencrypted, so it would still not be end-to-end to the container. |
| Verification results | A wrong result treated as authoritative | Three-outcome design with a human-review band; every result carries the label value, the application value, and the score, so an agent can check the reasoning (FR-3) | The tool can be wrong. A rushed agent may accept a match without checking. This is the central residual risk and is addressed by design, not eliminated. |
| Software supply chain | Compromised or vulnerable dependency | `pip-audit` and `npm audit` in CI; Dependabot weekly for pip, npm, GitHub Actions, and Docker; every action pinned by commit SHA and both base images by digest (v1.3.0, #111); an SBOM of the CI build as a CI artifact, and an SBOM of every pushed image, taken from the registry by the deployed digest, kept 90 days as an artifact and attached to the release for a release build (#112) | A dependency compromised between audit runs is not detected. Nothing consumes the SBOM automatically: no scanner reads it and no policy blocks on it, so it is an inventory, not a gate. |
| Build and deploy pipeline | Stolen long-lived cloud credentials | No static AWS access keys anywhere. Deployment authenticates through GitHub OIDC to an IAM role. The trust policy (`infra/terraform/iam.tf`, subjects in `locals.tf`) requires `aud` to be `sts.amazonaws.com` and `sub` to match this repository at `develop`, `main` or a `v*` tag, and nothing else (v1.3.0, #110; the reasoning is in section 2 under the OIDC row); the role's permissions name the one ECR repository and the one ECS service. Every action in the two workflows is pinned by commit SHA (#111). | A workflow file on `develop` or `main`, or a `v*` tag, can reach the role, so write access to those branches and the right to create such a tag are write access to the deployment; branch protection and the tag rule are the whole of that control. The image push and the service update are gated by the same thing, because the repository's `production` environment has no protection rules to gate either separately. |
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
| SBOM for the container image | `.github/workflows/ci.yml`, `.github/workflows/deploy.yml` | Syft via `anchore/sbom-action`, SPDX JSON. CI generates one for its own build and keeps it 30 days. The deploy workflow generates one from the registry for the digest it is about to deploy, names the artifact by that digest, keeps it 90 days, and for a release attaches it to the release, where it does not expire (#112) |
| Actions pinned by commit SHA; base images pinned by digest | `.github/workflows/ci.yml`, `.github/workflows/deploy.yml`, `Dockerfile` | Every `uses:` carries a 40-character SHA with the version beside it; both `FROM` lines carry the manifest-list digest beside the tag. Dependabot proposes the bumps in both forms (#111) |
| `id-token: write` on the two jobs that assume the AWS role, and on no other | `.github/workflows/deploy.yml` | The workflow default is `contents: read`; the SBOM-attaching job holds `contents: write` and no AWS session |
| No `.env` file reaches the image | `.dockerignore`, `.github/workflows/ci.yml` | `**/.env` and `**/.env.*` at every depth; CI plants one at each depth, builds the frontend stage, and asserts none is in the stage and the planted value is not in the bundle (finding 28) |
| The task's execution role can pull one image and write one log group | `infra/terraform/iam.tf` | An inline policy naming the stack's repository and log group replaces the account-wide managed policy; the task role still has no policy at all (finding 26) |
| The task's egress is TCP 443 only | `infra/terraform/network.tf` | Image pull, layer fetch and log delivery are all HTTPS; a compromised container has no other reverse path (finding 26) |
| Release tags cannot be re-pointed | `infra/terraform/ecr.tf`, `.github/workflows/deploy.yml` | The registry is `IMMUTABLE`; the deploy workflow refuses a dispatch tag matching `^v[0-9]` before it builds (finding 27) |
| Automated dependency updates | `.github/dependabot.yml` | Weekly for pip, npm, GitHub Actions, Docker |
| OIDC instead of static keys, scoped by repository and ref | `.github/workflows/deploy.yml`, `infra/terraform/iam.tf`, `infra/terraform/locals.tf` | `aws-actions/configure-aws-credentials` with `role-to-assume`; no secret access keys. The trust policy admits this repository at `refs/heads/develop`, `refs/heads/main` and `refs/tags/v*`, in both subject formats GitHub issues, and nothing else. **Why the ref and not the environment, checked rather than assumed (2026-09-01, #110):** the `production` environment on this repository has "Deployment branches and tags: No restriction", no protection rules, no environment secrets and no environment variables, and required reviewers are not available on a private repository at this plan. GitHub issues the `environment:production` subject to any job in any workflow on any branch that names the environment, so the trust entry v1.2.0 carried for that subject admitted every branch, and the two branch entries beside it constrained nothing. The ref is the claim GitHub enforces from the token itself. No job in `deploy.yml` declares an environment, because a job that does presents the environment-scoped subject instead of the ref-scoped one, and the two changes have to go together. **What would change it:** a deployment-branch policy (`main` and `v*`) and required reviewers on the environment would make the environment subject a gate worth trusting, and the shape the review suggested (environment on both AWS-touching jobs, environment subject in the trust policy) would then be the stronger one; that setting lives outside this repository, so this table would have to say it is load-bearing. **What the ref condition does not do:** it does not put the image push behind a review that the service update is not behind, or the other way round, because there is no review gate on either; both are gated by who can push to the two branches or create a `v*` tag |
| Least-privilege workflow tokens | `.github/workflows/ci.yml` | `permissions: contents: read` |
| Input size and MIME validation | `backend/app/config.py`, `backend/app/api.py`, `backend/app/verify.py` | Envelope size checked from `Content-Length` before the body is read; per-image size and MIME type checked before decoding. Covered by `backend/tests/test_api_validation.py` |
| Secret hygiene | `.gitignore`, `.pre-commit-config.yaml` | `.env` ignored; `detect-private-key` hook |
| Code review required | `.github/CODEOWNERS`, branch protection | Every change requires review from `@kimkight` |

**Done in v1.3.0, after five tagged releases had gone by without it:** the base
images are pinned by digest and the actions by commit SHA (#111). This
paragraph used to say the pinning would be closed "before the first tagged
release", and `README.md` and the CHANGELOG listed the tag pinning as a known
limitation at the same time; the review (finding 12) read the two side by side.

## 3. Prototype limitations and their production path

Stated so that no reader mistakes a prototype boundary for a considered
judgment that the control is unnecessary.

| Limitation | Why it is acceptable now | What production requires |
| --- | --- | --- |
| No authentication (D-9), and the load balancer is internet-facing | Accepted, not defaulted into: see below. The prototype stores nothing, holds no credential and records no identity. Marcus scoped it: "for a prototype? Just don't do anything crazy." The input it receives is a filed application, which is not nothing; the premise at the top of this document says what that changes. | An authentication layer at the edge, agency identity integration, role separation between agents and supervisors, and session management. |
| Plain HTTP; no TLS, no certificate, no custom domain | There is no domain to attach a certificate to, and the deliverable is a URL an evaluator can open at the load balancer's own DNS name. Traffic, including the filed application and its signature image, is unencrypted in transit. A CIDR restriction was considered and refused, because a URL that refuses reviewers' networks is not the deliverable (decision 5, `CODE_REVIEW_DECISIONS_2026-09.md`). Section 3.1 sizes the fix. | An ACM certificate, an HTTPS listener on port 443, a redirect from port 80 and the matching security group rule: roughly one Terraform block. The certificate is the part that needs a domain. |
| Task runs in a public subnet with a public IP | A Fargate task must reach ECR and CloudWatch Logs to start. The alternatives, a NAT gateway or a set of interface endpoints, each cost more per hour than the task. Its security group accepts inbound traffic only from the load balancer, so the public IP is an egress path rather than an entrance. | Private subnets, with either a NAT gateway or VPC interface endpoints for ECR, S3, and CloudWatch Logs. |
| Terraform state is local and unencrypted at rest beyond the operator's disk | One operator, one machine, and a stack whose resting state is destroyed. The state file is git-ignored, and it contains the account number and every ARN. | An S3 backend with versioning and server-side encryption, plus a DynamoDB lock table. See 09_DEPLOYMENT.md section 11. |
| No persistence (D-9) | Removes retention and privacy questions entirely for the exercise. Marcus names "PII considerations, document retention policies." | An audit record of every verification, with a retention schedule set by records management, and a defined disposition. |
| No audit trail, and no load balancer access logs | Follows from having neither authentication nor persistence. Access logs would need an S3 bucket and a bucket policy, which is a second stack to fund and destroy. | Who ran what, when, against which label, and what the tool returned. In a regulatory workflow this is not optional. Load balancer access logs to S3 are the cheap half of it. |
| No rate limiting or WAF | **This row used to read "not exposed to the public workload." That is no longer true.** Once deployed the load balancer is internet-facing with no authentication, so the prototype is exposed to anyone who learns its DNS name. What bounds the exposure is that nothing is stored and no credential is held, so the risk is open use of compute rather than disclosure. | Rate limiting, AWS WAF, and request throttling at the load balancer. |
| Capitalization checked, boldness not | 27 CFR 16.22(a)(2) requires both. The prototype checks capitals only and must not imply otherwise (OOS-4). | Typographic analysis, or an explicit statement in the product that boldness remains a manual check. |
| Image scanning reports and does not block | Scan on push in ECR is configured (`infra/terraform/ecr.tf`); it reports findings under the image tag and blocks nothing, and pretending otherwise would be a control this prototype does not have. The SBOM of every pushed image exists (section 2) and nothing reads it automatically. | A scanner that fails the deploy on a finding above a threshold, reading either ECR's scan result or the SBOM (`grype` against the SPDX file is the smallest version), with an exception path that records why a finding was accepted. |

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

**What bounds it.** Nothing is kept (NFR-6): no database, no object store, no
cache, nothing that outlives the request (section 3.2 says where the bytes are
while it runs), and the batch response stream is the only copy of a result. The
task holds no credential, and its IAM role has no policy attached at all. There
is no path from the application to any other resource in the account.

**What the residual risks actually are**, named rather than waved at:

1. **Open use of compute.** Anyone who learns the DNS name can submit images
   and consume the single task. There is no rate limit, so the practical
   consequence is denial of service against a prototype, and an AWS bill for a
   stack estimated at about $0.12 an hour.
2. **Unencrypted transit.** The application document, its signature image, the
   label artwork, the declared values and the result cross the network in the
   clear, and so does the batch stream. This is stated as the limitation it
   is rather than as an acceptable property of the data: the earlier text
   here said the data was "a beverage label and its declared fields rather
   than anything personal", and since ADR 0008 that is not what the primary
   input is (code review finding 20, #119). What does not cross the wire,
   because none exists: a credential, a session token, a cookie, or any
   record of who used the tool. The signature image is held in process
   memory for the seconds the check takes (section 3.2) and is not read,
   matched or logged by anything: the item 5 sampler reads three check boxes
   on page 1, and the artwork pass reads embedded pictures that clear the
   artwork floor, which the signature does not (OQ-24 is about that floor
   being too strict for real artwork, not too loose for a signature).
3. **No attribution.** With no authentication and no access logs, there is no
   record of who used it.

**What production adds for transit, sized.** An ACM certificate for a name
the agency controls; a second `aws_lb_listener` on port 443 carrying it; the
port 80 listener's default action changed from forward to a 301 redirect to
443; and one more ingress rule on the load balancer's security group for 443.
In `infra/terraform/alb.tf` and `network.tf` that is roughly one Terraform
block plus two one-line changes. The certificate is the only part that needs
something this repository does not have, a domain, and validating one is the
part that takes days rather than minutes.

**Why it is not done for the evaluation stack (decision 5,
`CODE_REVIEW_DECISIONS_2026-09.md`).** Two mitigations short of TLS were
considered and refused. A CIDR restriction on the listener would break the
deliverable: the assignment asks for a URL reviewers can open, from networks
nobody can enumerate in advance, and a URL that refuses them is not that
deliverable. Buying and validating a domain for a stack whose resting state is
destroyed is scope on the week of submission. So the gap is stated at its
size, here and in the scope document, rather than half-closed. What an
evaluator should do about it is stated too: submit a filing they are content
to send in the clear, or one of the synthetic documents under `samples/`, and
not a real filing they would not send by unencrypted email.

**The rest of the production fix**, in the order it would be done after
transit: an authentication layer at the edge integrated with agency identity;
then AWS WAF and rate limiting; then access logs and an application audit
trail.

**The mitigation available now, without changing the posture.** Between
demonstrations, `terraform destroy`, which is the runbook's resting state.
The `ingress_cidr_blocks` variable in `infra/terraform/variables.tf` still
exists and still narrows the load balancer's security group to a single
address; it is not used for the evaluation stack, for the reason above.

### 3.2 Where an upload lives while it is checked

NFR-6 is a promise about retention: nothing uploaded is kept. This is the whole
of what happens to an upload between arrival and answer, stated so that the
promise can be checked rather than taken. Until v1.3.0 this document said
nothing was written to disk, and that was not true of any request the service
accepted (code review finding 4); the claim was corrected, not the code
(`CODE_REVIEW_DECISIONS_2026-09.md`, decision 4).

**In memory.** The multipart parser holds each part in memory up to the
per-file limit (`TTB_MAX_UPLOAD_BYTES`, 10 MiB), the route reads it into a
`bytes` object, the decoded pixel arrays and the parsed document live in
process memory, and all of it is released when the response is built.

**In the temporary directory, briefly, twice.** The OCR engine reads each
image through a short-lived temporary file: `pytesseract` writes the decoded
picture to the temporary directory, runs the Tesseract binary over that path,
and deletes that file and the engine's output file before the call returns.
Every label photograph, every embedded picture lifted out of a filed
application, and every page rendered from a scanned one goes through that
path. Separately, a part larger than the per-file limit is spooled by
Starlette to a temporary file before the exact size check refuses it, because
the whole-request guard reads `Content-Length` and cannot count the parts
without reading the body it exists not to read: a single-label request may
legitimately carry up to four files, so the guard bounds the envelope at four
times the per-file limit. The window is therefore one part between 10 MiB and
40 MiB on `POST /api/verify` and `POST /api/classify`, and between 10 MiB and
the batch envelope (3 000 MiB as deployed) on `POST /api/verify-batch`;
`POST /api/read-application` takes one file and refuses it from the header.
The spooled file is deleted when the request ends. Both files live in the
task's ephemeral storage, which is destroyed with the task; closing the window
from the header is not possible without owning the framework's parser, and
that is recorded rather than attempted (OQ-30).

**Nowhere else.** Nothing is written to the working directory. There is no
database, no bucket, no cache, and no log line carries content, a filename or
an extracted value: the application's logger writes counts, timings and path
names. `backend/tests/test_verify_integration.py::TestNothingIsRetained`
asserts, after a real request, that the temporary directory and the working
directory carry no artefact of it, having first observed that the engine's
temporary files were created during it, so the test can fail and was broken on
purpose to prove it; the same assertion covers the batch path in
`test_batch.py`. The stronger guarantee, feeding the engine over standard
input so that no temporary file exists at all, is recorded and deliberately not
taken in OQ-30.

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
| SBOM per pushed image, by digest; attached to each release | Deploy workflow artifact (90 days) and release asset, SPDX JSON; CI keeps one for its own build | Supply chain inventory |
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
