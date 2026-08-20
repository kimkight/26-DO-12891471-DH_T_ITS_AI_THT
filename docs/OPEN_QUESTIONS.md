# Open Questions

Questions raised during this work that the assignment text and the recorded
decisions do not answer. Nothing here is guessed. Each entry names who can
answer it and what it blocks.

Resolution procedure is in [08_SDLC_PROCESS.md](08_SDLC_PROCESS.md) section 9:
a question is closed by a commit that records the answer, cites its source, and
updates every artifact the answer affects.

| ID | Status | Blocks |
| --- | --- | --- |
| [OQ-1](#oq-1) | Open | Nothing now; affects platform strategy beyond the prototype |
| [OQ-2](#oq-2) | Open | Recording the Tesseract version in the architecture document |
| [OQ-3](#oq-3) | Open | Reproducible frontend builds; `npm ci` in CI and Docker |
| [OQ-4](#oq-4) | Open | FR-7 implementation |
| [OQ-5](#oq-5) | Open | FR-7 implementation |
| [OQ-6](#oq-6) | Open | Batch design (FR-8, NFR-2) |
| [OQ-7](#oq-7) | Open | Accessibility acceptance (NFR-5) |
| [OQ-8](#oq-8) | Open | Accuracy acceptance (US-21) |
| [OQ-9](#oq-9) | Open | Matching threshold defaults (FR-3) |
| [OQ-10](#oq-10) | Open | ATO planning |
| [OQ-11](#oq-11) | Open | AI governance sign-off |
| [OQ-12](#oq-12) | Open | Enforcement of branch protection |
| [OQ-13](#oq-13) | Open | Deployment (a later task) |
| [OQ-14](#oq-14) | Open | Nothing; a manual step for the repository owner |
| [OQ-15](#oq-15) | Open | Local verification of the build in this environment |
| [OQ-16](#oq-16) | Open | Batch UI design (US-9) |

---

## OQ-1
**Which cloud should this system target beyond the prototype?**

Marcus Williams states "We're on Azure now after the migration in 2019."
[Source: Marcus Williams interview] Decision D-1 targets AWS commercial for the
prototype, and Decision D-11 names AWS GovCloud (US) as the intended production
environment. These are not reconciled by any source available here.

No inference is drawn. Recorded because a reader comparing the charter against
the interview will notice the discrepancy, and it should be visible rather than
appear to have been overlooked.

**Who can answer:** Marcus Williams, or whoever owns the agency cloud strategy.
**Blocks:** nothing in the prototype.

## OQ-2
**What version of Tesseract does the container use?**

Section 6 of the build instructions stated that Tesseract was preinstalled in
this environment and asked for `tesseract --version` to be recorded in
[05_ARCHITECTURE.md](05_ARCHITECTURE.md). It was not installed, and it could not
be installed.

Exact failure, from `apt-get install -y tesseract-ocr tesseract-ocr-eng`:

```
Err:6 http://archive.ubuntu.com/ubuntu noble/universe amd64 tesseract-ocr amd64 5.3.4-1build5
  403  Forbidden [IP: 172.66.152.176 80]
E: Failed to fetch http://archive.ubuntu.com/ubuntu/pool/universe/t/tesseract/tesseract-ocr_5.3.4-1build5_amd64.deb  403  Forbidden
E: Unable to fetch some archives, maybe run apt-get update or try with --fix-missing?
```

The session's egress policy returns 403 for `archive.ubuntu.com`. The proxy
documentation directs that policy denials be reported rather than routed around,
so no workaround was attempted.

The version is therefore **unknown, not assumed**. The Dockerfile installs
`tesseract-ocr` and `tesseract-ocr-eng` from Debian bookworm at image build
time; the actual version must be read from a built image and recorded.

**Who can answer:** anyone who can build the image in a network-enabled
environment, with `docker run --rm <image> tesseract --version`.
**Blocks:** the version row in [05_ARCHITECTURE.md](05_ARCHITECTURE.md) section 8.

## OQ-3
**Should a frontend lockfile be committed, and which package manager?**

No `package-lock.json` exists, because `npm install` could not run in this
session (see OQ-15). Without a lockfile, CI and the Docker build must use
`npm install` rather than `npm ci`, so dependency resolution is not reproducible
and a transitive update can change a build without any commit.

This should be closed by running `npm install` in a network-enabled environment
and committing the resulting lockfile, then switching CI and the Dockerfile to
`npm ci`. Both places carry a comment marking the switch.

**Who can answer:** the repository owner.
**Blocks:** reproducible frontend builds.

## OQ-4
**What numeric tolerance applies to alcohol content?**

FR-7 requires numeric comparison, so `45%` and `45.0%` agree. It does not
establish whether a near miss is a match, a review, or a mismatch. Is a label
reading 45.1% against an application reading 45% a mismatch, or within
tolerance?

TTB regulation defines labeling tolerances for alcohol content, and 27 CFR 4.36
and 27 CFR 5.37 are the likely locations for wine and distilled spirits
respectively. **Those sections were not fetched, read, or quoted during this
work, and no tolerance figure is stated anywhere in this repository**, because
writing one from memory would be exactly the invention the ground rules prohibit.

**Who can answer:** Sarah Chen or a compliance agent, confirmed against the
applicable CFR section fetched from ecfr.gov.
**Blocks:** FR-7 implementation. A tolerance must be chosen deliberately, since
either default silently encodes a compliance position.

## OQ-5
**How should net contents in different units be compared?**

If the label reads `750 mL` and the application reads `25.4 fl oz`, is that a
match? FR-7 compares numerically but says nothing about unit conversion.

Related: TTB has standards of fill, which constrain permitted container sizes.
Whether the tool should validate against them is not stated in the assignment
and is not assumed here.

**Who can answer:** Sarah Chen or a compliance agent.
**Blocks:** FR-7 implementation.

## OQ-6
**Is there a latency target for a batch, and does a batch need an asynchronous
job model?**

NFR-1 sets about 5 seconds for a single label, from Sarah Chen. Nothing states a
target for a batch of 300. At 5 seconds each, sequential processing of 300
labels takes 25 minutes, which no single HTTP request should hold open.

This determines whether batch verification is a synchronous request with
concurrency, or a submitted job with a results page. The choice changes the API,
the UI, and the infrastructure, so it should be settled before FR-8 is built.

**Who can answer:** Sarah Chen, and Janet in the Seattle office, who is named as
the original requester of batch handling.
**Blocks:** FR-8 and NFR-2 design.

## OQ-7
**Does Section 508 apply to this prototype, and is there an agency
accessibility standard beyond WCAG 2.1 AA?**

NFR-5 targets WCAG 2.1 Level AA. Section 508 is a federal accessibility
obligation that would plausibly apply to a system used by agency staff, but no
source in this assignment states that it applies to a prototype of this kind,
and the conclusion is not asserted.

**Who can answer:** Marcus Williams, or the agency Section 508 program office.
**Blocks:** the accessibility acceptance bar. WCAG 2.1 AA is targeted regardless.

## OQ-8
**What accuracy is good enough?**

No source states a target for extraction or matching accuracy. Without one,
"the accuracy tests pass" has no meaning, and any figure written here would be
unfalsifiable.

The specific question worth asking is not a single number: an acceptable false
match rate, where the tool reports a match that is actually a mismatch, is
likely far lower than an acceptable false review rate, because the first causes
an agent to skip a check and the second only costs time.

**Who can answer:** Sarah Chen, with input from Dave Morrison and Jenny Park.
**Blocks:** accuracy acceptance (US-21). Measurement can proceed without it;
judging the result cannot.

## OQ-9
**What should the match and review thresholds be?**

`TTB_MATCH_THRESHOLD` defaults to 95 and `TTB_REVIEW_THRESHOLD` to 80. These are
starting points for tuning, not derived values, and they are listed in
[ASSUMPTIONS.md](ASSUMPTIONS.md) as A-4.

They cannot be chosen responsibly before the labeled sample set exists, since
the right values depend on measured score distributions for real label and
application pairs.

**Who can answer:** measurement against the sample set, then review with
compliance agents.
**Blocks:** FR-3 tuning. It does not block implementation, since the values are
configurable.

## OQ-10
**What is the security categorization for this system?**

[06_SECURITY_AND_COMPLIANCE.md](06_SECURITY_AND_COMPLIANCE.md) states that
production use would require an agency ATO. The NIST SP 800-53 control baseline
follows from a FIPS 199 categorization of the system's confidentiality,
integrity, and availability impact. No source supplies one.

Label applications may contain business-confidential information, and Marcus
mentions "PII considerations" for production, but that is not a categorization.

**Who can answer:** the agency information system owner and the authorizing
official.
**Blocks:** any real ATO planning. It does not block the prototype.

## OQ-11
**Which AI governance requirements apply, and in what versions?**

[06_SECURITY_AND_COMPLIANCE.md](06_SECURITY_AND_COMPLIANCE.md) section 6.2 lists
the NIST AI RMF, the Generative AI Profile, applicable OMB policy on federal
agency use of AI, and Treasury AI policy as documents to be reviewed and cited.
**None was fetched, read, or summarized during this work.**

Two specific questions: does a prototype of this kind fall within the scope of
the applicable OMB memorandum at all, and would it appear in an agency AI use
case inventory? The answers may differ depending on whether the Bedrock fallback
is ever enabled, since the default path is deterministic OCR rather than a
generative model.

**Who can answer:** the Treasury AI governance function or the agency Chief AI
Officer, citing the current controlling documents.
**Blocks:** AI governance sign-off for anything beyond a prototype.

## OQ-12
**Can branch protection be enforced on this repository?**

Decision D-6 requires protection on `main` and `develop`. GitHub does not
enforce branch protection on private repositories under a Free plan.

The outcome of the protection API calls made during initialization is recorded
in the final summary for this work. If protection could not be applied, the Git
Flow rules in [08_SDLC_PROCESS.md](08_SDLC_PROCESS.md) section 2 remain the
documented process and are followed by convention rather than enforced by the
platform.

**Who can answer:** the repository owner, by checking the plan or by making the
repository public.
**Blocks:** enforcement, not process.

## OQ-13
**Deployment details not yet decided.**

All of the following are needed before infrastructure can be written, and none
is stated in any source:

1. Custom domain, and where the TLS certificate comes from.
2. Whether the load balancer is internet-facing or internal. Reviewers need
   access to test the prototype, which suggests internet-facing, but that
   conflicts with there being no authentication (D-9).
3. VPC and subnet topology: create new, or use existing.
4. Terraform state backend: S3 bucket and DynamoDB lock table, or alternative.
5. CloudWatch log retention period.
6. ECS task CPU and memory sizing. Cannot be chosen before the performance tier
   produces a latency measurement, since OCR is CPU bound.
7. Desired task count and whether autoscaling is configured.
8. Who pays for the AWS resources, and what the cost ceiling is.

Item 2 deserves attention: an internet-facing prototype with no authentication is
reachable by anyone who learns the URL. That is a deliberate prototype
limitation, and it should be an explicit acceptance rather than a default.

**Who can answer:** Marcus Williams, and whoever owns the AWS account.
**Blocks:** the deployment task.

## OQ-14
**Manual step: create Project board "TTB Label Verifier" with columns Backlog,
Ready, In Progress, In Review, Done and add all story issues.**

Decision D-7 calls for a GitHub Project board. It was **not** created. GitHub
Projects v2 is a GraphQL-only API, and this session's proxy does not support the
required GraphQL operations, so there is no REST equivalent to fall back to.

The board must be created in the GitHub web interface, and every issue listed in
the final summary for this work added to it.

**Who can answer:** the repository owner, in the GitHub UI.
**Blocks:** nothing in the code. The issues and labels exist and carry the same
information.

## OQ-15
**How should the build be verified when the session has no package-manager
network access?**

Section 6 of the build instructions required running `docker compose up -d`,
curling `/api/health`, running `pytest`, and running the frontend build in this
session. **None of these could be run.** The session's egress policy returned
`403 Forbidden` for every package source:

| Host | Result | Consequence |
| --- | --- | --- |
| `pypi.org`, `files.pythonhosted.org` | 403 on CONNECT | `pip install` fails; `pytest` cannot run |
| `registry.npmjs.org` | 403 | `npm install` fails; the frontend cannot be built |
| `archive.ubuntu.com` | 403 | `apt-get install` fails; see OQ-2 |

Confirmed against the proxy status endpoint, which recorded
`connect_rejected: gateway answered 403 to CONNECT (policy denial or upstream
failure)` for `pypi.org:443` and `files.pythonhosted.org:443`. Because the
Docker build installs from all three sources, `docker compose up --build` fails
for the same reason.

The proxy documentation states that policy denials must be reported rather than
routed around, so no workaround was attempted.

Verification was therefore delegated to GitHub Actions, which has package
network access. The CI run result is reported in the final summary for this
work, and it is the only place where these checks have actually executed.

**Who can answer:** whoever provisions the session environment. If the intent
was for the environment to allow the default package-manager list, the policy
does not currently match that intent.
**Blocks:** local verification only.

## OQ-16
**How is application data supplied for a batch?**

FR-8 requires batch submission of labels with their application data. For a
single label the agent types the field values. For 300 labels that is not
plausible, but no source states the format.

Likely candidates are a CSV keyed by filename, or a structured file per label.
The assignment does not say, and the choice affects both the API contract and
the UI.

Note that `samples/expected.csv` solves a related problem for testing, which
suggests a CSV keyed by image filename would be a natural fit. That is an
observation, not a decision.

**Who can answer:** Sarah Chen, or Janet in the Seattle office.
**Blocks:** FR-8 and US-9 interface design.
