# Open Questions

Questions raised during this work that the assignment text and the recorded
decisions do not answer. Nothing here is guessed. Each entry names who can
answer it and what it blocks.

Resolution procedure is in [08_SDLC_PROCESS.md](08_SDLC_PROCESS.md) section 9:
a question is closed by a commit that records the answer, cites its source, and
updates every artifact the answer affects.

| ID | Status | Blocks |
| --- | --- | --- |
| [OQ-1](#oq-1) | Answered by ADR 0001 (author's decision, not a stakeholder answer) | Nothing now; affects platform strategy beyond the prototype |
| [OQ-2](#oq-2) | Closed 2026-08-22 | Nothing; the version is recorded |
| [OQ-3](#oq-3) | Closed 2026-08-22 | Nothing; both ecosystems build from a committed lock file |
| [OQ-4](#oq-4) | Closed by assumption A-12 | Nothing; FR-7 acceptance criteria state the rule |
| [OQ-5](#oq-5) | Closed by assumption A-13 | Nothing; FR-7 acceptance criteria state the rule |
| [OQ-6](#oq-6) | Closed by ADR 0006 | Nothing; the execution model is decided |
| [OQ-7](#oq-7) | Open | Accessibility acceptance (NFR-5) |
| [OQ-8](#oq-8) | Open | Accuracy acceptance (US-21) |
| [OQ-9](#oq-9) | Open | Matching threshold defaults (FR-3) |
| [OQ-10](#oq-10) | Open | ATO planning |
| [OQ-11](#oq-11) | Open | AI governance sign-off |
| [OQ-12](#oq-12) | Closed 2026-08-21 | Nothing; rules are declared, enforcement waits on the plan |
| [OQ-13](#oq-13) | Closed 2026-08-24 | Nothing; the infrastructure code exists and 09_DEPLOYMENT.md is the runbook. Nothing is applied |
| [OQ-14](#oq-14) | Closed 2026-08-21 | Nothing; the board exists and is linked to the repository |
| [OQ-15](#oq-15) | Closed 2026-08-23 | Nothing; both registries and Tesseract are reachable from a session |
| [OQ-16](#oq-16) | Reopened and reclosed 2026-08-28 by ADR 0009 | Nothing; a batch carries the applicant's own COLA documents |
| [OQ-17](#oq-17) | Closed 2026-08-21 | Nothing; `develop` is the default branch |
| [OQ-18](#oq-18) | Closed 2026-08-22 | Nothing; tags are created in the Releases web interface |
| [OQ-19](#oq-19) | Open | Triggering Dependabot commands from a session |
| [OQ-20](#oq-20) | Open | Whether an all-capitals warning body passes FR-5 |
| [OQ-21](#oq-21) | Open | How often real photographed labels need cylinder dewarping (SG-1) |
| [OQ-22](#oq-22) | Open | Nothing in the prototype; it bounds any claim that the COLA parser works on real documents (FR-11, A-17), and now bounds the batch path too |
| [OQ-23](#oq-23) | Open | Nothing; it would confirm or improve the ADR 0009 pairing rule |
| [OQ-24](#oq-24) | Open | Nothing in the prototype; it bounds the size and shape floor and the coverage claim for the embedded artwork path (ADR 0010) |
| [OQ-25](#oq-25) | Decided 2026-08-30: stays needs human review | Nothing; the constant is unchanged and FR-7, A-12 and UAT row 21 all stand |
| [OQ-26](#oq-26) | Answered 2026-08-30: met at about 3.5 s | Nothing; re-measured against deploy #11, and to be re-taken once v1.1.0 changes what is read |

---

## OQ-1
**Which cloud should this system target beyond the prototype?**

**Status: Answered by ADR 0001 (author's decision, not a stakeholder answer).**

Marcus Williams states "We're on Azure now after the migration in 2019."
[Source: Marcus Williams interview] Decision D-1 targets AWS commercial for the
prototype.

The earlier text of Decision D-11 named AWS GovCloud (US) as the agency's
intended production environment. **No source supports that**; it was an
assertion rather than a sourced statement, and it has been replaced. D-11 now
records that the agency states it is on Azure, that this prototype deploys to
AWS commercial `us-east-1` by the author's choice for delivery speed on the
platform the author knows best, and that a production deployment would target
the agency's platform, presumed to be Azure Government.

[ADR 0001](adr/0001-cloud-platform-aws.md), section "Why not Azure, given the
agency runs Azure", gives the reasoning and the public Treasury evidence. That
is the author's decision for this prototype. It is **not** a stakeholder answer:
nobody at the agency has stated which cloud a production system would use, and
the question of agency platform strategy remains open for whoever owns it.
[Source: [cloud_choice_and_abv_assumption.md](cloud_choice_and_abv_assumption.md)
section 1]

**Who can answer:** Marcus Williams, or whoever owns the agency cloud strategy.
**Blocks:** nothing in the prototype.

## OQ-2
**What version of Tesseract does the container use?**

**Status: Closed 2026-08-22.** Answer: **Tesseract 5.3.0**, with
leptonica 1.82.0, the version Debian bookworm ships.

Read from the summary of the most recent successful CI run on `develop`, run
32574942848 at commit `ef3086a`, step "Report the Tesseract version in the
image":
<https://github.com/kimkight/26-DO-12891471-DH_T_ITS_AI_THT/actions/runs/32574942848>

Recorded in the version table in
[05_ARCHITECTURE.md](05_ARCHITECTURE.md) section 8. The version was read from a
real run rather than inferred from the base image tag, which is what this
question asked for. It will change only when the base image moves to a different
Debian release.

The record of why it could not be read in the initializing session follows.

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

**Now readable from CI.** The `container build and SBOM` job has a step,
"Report the Tesseract version in the image", that runs `tesseract --version`
against the built image and writes the result to the workflow run summary page.
The version also appears in the SBOM artifact attached to every run.

**How it was closed:** the version was read from the run summary named above and
recorded in the version table in
[05_ARCHITECTURE.md](05_ARCHITECTURE.md) section 8.

**Who answered:** CI run 32574942848. The same value can be reproduced locally
with `docker run --rm --entrypoint tesseract <image> --version`.
**Blocks:** nothing.

## OQ-3
**Should a frontend lockfile be committed, and which package manager?**

**Status: Closed 2026-08-22.** Answer: yes, and npm. `frontend/package-lock.json`
and `backend/requirements.lock` are both committed, and CI, the Dockerfile and
the documented local setup all install from them.

Originally no `package-lock.json` existed, because `npm install` could not run in
the initializing session (see OQ-15). Without a lockfile, CI and the Docker build
had to use `npm install` rather than `npm ci`, so dependency resolution was not
reproducible and a transitive update could change a build without any commit.

**The same issue applies to the backend, and it had teeth.** `backend/pyproject.toml`
originally carried exact `==` pins written by hand. Those pins were stale, and
`pip-audit` in CI found seven advisories against the transitive `starlette`
version they resolved to (PYSEC-2026-161, -248, -249, -1941, -1942, -2280,
-2281), the highest requiring a fix in 1.3.1. The pins have been replaced with
minimum-version floors at or above the fixed versions, so the resolver picks
current releases.

Floors are the right answer for security but the wrong answer for
reproducibility: two builds a week apart can now resolve different versions.
Closing this question properly therefore meant generating real lock files for
both ecosystems, committing them, and switching CI and the Dockerfile to
`npm ci` and to installing from a locked requirements file. That is what was
done.

**How it was closed.** npm is the package manager, because the frontend was
scaffolded with npm and nothing in the assignment or the recorded decisions asks
for another one; adding pnpm or yarn would be a change with no stated reason.
Both lock files were generated outside a session, because the session egress
policy still denies PyPI and npm (OQ-15), and committed to
`feature/lockfiles`:

| File | Contents | Generated with | Verified with |
| --- | --- | --- | --- |
| `frontend/package-lock.json` | the resolved npm tree | npm on Node 22 | `npm audit` clean |
| `backend/requirements.lock` | extras ocr and matching, 27 packages | pip-compile on Python 3.11, `--allow-unsafe --strip-extras --generate-hashes` | `pip-audit` clean |
| `backend/requirements-dev.lock` | the same plus the dev extra, 61 packages | the same, with `--extra dev` | `pip-audit` clean |

**The Python lock is split in two on purpose.** `requirements.lock` is what the
Dockerfile installs, so anything in it ships in the image. `pytest`, `ruff`,
`pip-audit` and `httpx` are contributor tools, not product; a single combined
lock file put all four in the runtime image, which enlarged it and widened its
surface for no benefit. The dev file is a strict superset generated from the
same resolution, so the tooling is the version the runtime set resolved against.

The floors in `backend/pyproject.toml` stay as floors. They record the oldest
safe version and are raised when an advisory requires it; the lock file records
what those floors resolved to. Restoring exact `==` pins to `pyproject.toml`
would recreate the stale-pin problem described above, so it was not done.

Consuming the lock files:

- The `backend lint and test` job installs
  `pip install --require-hashes -r requirements-dev.lock` followed by
  `pip install --no-deps -e .`. It needs the dev file, because the runtime file
  has no pytest and no ruff in it.
- The `dependency audit` job audits **both** Python files, in two independently
  gating steps: `pip-audit -r backend/requirements.lock --no-deps` and
  `pip-audit -r backend/requirements-dev.lock --no-deps`. The runtime file is
  what ships, but an advisory against a dev tool is still an advisory against
  something contributors run.
- The frontend is installed with `npm ci` everywhere.
- The Dockerfile uses `npm ci` and
  `pip install --require-hashes -r requirements.lock`, the runtime file only, so
  every artifact in the image is verified against the digest recorded at
  resolution time and no test tooling is present.
- The comments in both files that marked the switch as pending are removed.

**Confirmed by CI**, run 32600078898 at commit `1d7f59b`, all five checks green:

| Job | What it proves |
| --- | --- |
| `backend lint and test` | `pip install --require-hashes -r requirements-dev.lock` installed the 61 pinned packages with every hash verified, then `pip install --no-deps -e .`, then ruff and pytest ran against them |
| `dependency audit` | both `pip-audit -r backend/requirements.lock --no-deps` and `pip-audit -r backend/requirements-dev.lock --no-deps` passed as separate gating steps, and `npm audit --audit-level=high` passed |
| `frontend lint and build` | `npm ci` installed the locked tree, then eslint, prettier and `tsc -b && vite build` |
| `container build and SBOM` | the image built with `npm ci` and `pip install --require-hashes -r requirements.lock`, served `/api/health`, ran as uid 10001, reported its Tesseract version, and produced an SBOM |

The container job is the one that matters most here, because it is the only
place the hash-verified runtime install actually runs. It had never reached that
layer before: on the earlier attempts the build failed one stage earlier at
`npm ci` and the pip layer was cancelled.

**A stale frontend lock file was caught by CI and fixed.** The first version of
`frontend/package-lock.json` was generated before pull requests #32, #34 and #35
merged into `develop`, and those three raised devDependency ranges in
`frontend/package.json`. `npm ci` rejected it, in all three jobs that install
npm dependencies:

```
npm error `npm ci` can only install packages when your package.json and
package-lock.json or npm-shrinkwrap.json are in sync.
npm error Invalid: lock file's eslint-plugin-react-hooks@5.2.0 does not satisfy eslint-plugin-react-hooks@7.1.1
npm error Invalid: lock file's eslint-plugin-react-refresh@0.4.26 does not satisfy eslint-plugin-react-refresh@0.5.4
npm error Invalid: lock file's globals@15.15.0 does not satisfy globals@17.11.0
```

This is worth recording rather than quietly fixing, because it is the failure
mode the switch introduces and it will recur. It was fixed by regenerating the
lock file against the current `package.json`, not by patching it: the three
packages cross a major each, so their transitive trees and integrity hashes
change, and no correct edit could be written by hand.

The rule that prevents a repeat is in [CONTRIBUTING.md](../CONTRIBUTING.md):
any pull request that changes `package.json` or `pyproject.toml` regenerates the
affected lock file in the same pull request. `npm ci` and `--require-hashes`
both reject a stale lock rather than working around it, so the cost of
forgetting is a red pull request, not a subtly different build.

**Who answered:** the repository owner, by generating both lock files in a
network-enabled environment.
**Blocks:** nothing.

## OQ-4
**What numeric tolerance applies to alcohol content?**

**Status: Closed by assumption [A-12](ASSUMPTIONS.md#a-12).** Answer: none. The
label ABV and the application ABV must be numerically identical, and
`TTB_ABV_TOLERANCE` defaults to `0.0`.

FR-7 requires numeric comparison, so `45%` and `45.0%` agree. It did not
establish whether a near miss is a match, a review, or a mismatch.

The regulations were fetched from eCFR on 2026-08-20 and they do not answer the
question, because they answer a different one:

- 27 CFR 5.65 (distilled spirits): "A tolerance of plus or minus 0.3 percentage
  points is allowed for actual alcohol content that is above or below the
  labeled alcohol content."
  <https://www.ecfr.gov/current/title-27/section-5.65>
- 27 CFR 4.36 (wine): 1 percent for wines over 14 percent ABV and 1.5 percent
  for wines at 14 percent or less, "either above or below" the stated
  percentage. <https://www.ecfr.gov/current/title-27/section-4.36>
- 27 CFR 7.65 (malt beverages): "a tolerance of 0.3 percentage points will be
  permitted, either above or below the stated alcohol content, for malt
  beverages containing 0.5 percent or more alcohol by volume."
  <https://www.ecfr.gov/current/title-27/section-7.65>

Every one of those governs the difference between the **actual** alcohol content
of the liquid and the **labeled** content, which is a laboratory question. This
tool compares two **declared** values: what the applicant wrote on the label
artwork and what the applicant typed into the application form. There is no
regulatory basis for allowing them to differ, and Sarah's description of the
check is "ABV is correct? Check." A label reading 45.1% against an application
reading 45% is therefore a **mismatch**.

The full rule, including the proof cross-check and range handling, is A-12 in
[ASSUMPTIONS.md](ASSUMPTIONS.md) and the FR-7 acceptance criteria in
[03_REQUIREMENTS.md](03_REQUIREMENTS.md). Reasoning:
[cloud_choice_and_abv_assumption.md](cloud_choice_and_abv_assumption.md)
section 2.

**What would reopen it:** a compliance agent or Sarah Chen stating that
applications and labels are routinely accepted with small ABV differences. No
source says so. `TTB_ABV_TOLERANCE` exists so that answer changes the behaviour
without a code change.
**Blocks:** nothing. FR-7 acceptance criteria state the rule.

## OQ-5
**How should net contents in different units be compared?**

**Status: Closed by assumption [A-13](ASSUMPTIONS.md#a-13).** Answer: they are
not converted. Values are compared numerically only when units match after
normalization (`mL`/`ml`/`milliliters`, `L`/`liters`, `fl oz`/`fl. oz.`).
Different units are reported as **needs human review**, and no conversion is
performed. `750 mL` against `25.4 fl oz` is therefore a review, not a match.

Standards of fill are still not validated. Whether the tool should validate
against them is not stated in the assignment and is not assumed here.

The reasoning is A-12's: a conversion the tool performs silently is a place a
false match can be manufactured. See A-13 in [ASSUMPTIONS.md](ASSUMPTIONS.md),
the FR-7 acceptance criteria in [03_REQUIREMENTS.md](03_REQUIREMENTS.md), and
[cloud_choice_and_abv_assumption.md](cloud_choice_and_abv_assumption.md)
section 2.

**What would reopen it:** Sarah Chen or a compliance agent stating that
cross-unit net contents are routinely accepted, or that standards of fill should
be validated.
**Blocks:** nothing. FR-7 acceptance criteria state the rule.

## OQ-6
**Is there a latency target for a batch, and does a batch need an asynchronous
job model?**

**Status: Closed by [ADR 0006](adr/0006-batch-execution-model.md).**

Two questions, two different answers.

**Is there a latency target for a batch? No, and one is not invented here.** No
source states one, and this question is the record that it was asked rather than
assumed. ADR 0006 therefore optimizes for the two properties NFR-2 does state,
which are that completed work is not discarded and that progress is visible,
rather than for a completion time nobody has specified.

**Does a batch need an asynchronous job model? No, and it cannot have one.**
Batch verification is a single synchronous multipart request carrying up to
`TTB_MAX_BATCH_FILES` images plus one CSV, processed concurrently by a bounded
worker pool, streaming per-label results as newline-delimited JSON. There is no
job store, because a job identifier that outlives the request implies stored
state and Decision D-9 forbids persistence.

The accepted cost is stated plainly in the ADR: a dropped connection loses the
batch, because the response stream is the only copy of the results. An
asynchronous job model with a results store is the right production design and
is recorded in ADR 0006 as the expected successor once persistence and
authentication exist.

**What would reopen it:** Sarah Chen or Janet stating an actual completion-time
expectation for a batch, or persistence being permitted, either of which changes
the trade the ADR makes.

The original record follows.

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
**Branch protection could not be applied, and could not even be attempted.**

**Status: Closed 2026-08-21.** Rules declared on `main` and `develop` on
2026-08-21; not enforced by GitHub until the repository is public or moves to a
Team or Enterprise plan; the required status check is `ci`.

The rules were declared in the GitHub web interface under Settings, Rules, and
they are: pull request required, the `ci` status check required, approvals not
required, force pushes blocked, deletions blocked. GitHub displays them as "Not
enforced" because this repository is private on a Free plan, which is obstacle 2
below, reached only after obstacle 1 was worked around by declaring the rules by
hand rather than through an API.

The record of why this could not be done from a session follows.

Decision D-6 requires protection on `main` and `develop`: pull request required,
the `ci` status check required, stale approvals dismissed, force pushes blocked.

**This was not applied.** Two independent obstacles:

1. **No API path exists in this session.** The build instructions specified
   `gh api -X PUT repos/.../branches/<branch>/protection`. The `gh` CLI is not
   installed in this environment, and direct REST calls to `api.github.com`
   return:

   ```
   HTTP 403
   {"message":"GitHub access is not enabled for this session. An org admin must
   connect the Claude GitHub App for this organization."}
   ```

   GitHub access in this session is mediated by a tool set that provides issues,
   pull requests, branches, and file contents, but exposes **no branch
   protection endpoint and no repository settings endpoint**.

2. **The anticipated plan limitation may also apply.** GitHub does not enforce
   branch protection on private repositories under a Free plan. Whether that
   applies here was never reached, because obstacle 1 blocked the attempt.

Until protection is applied, the Git Flow rules in
[08_SDLC_PROCESS.md](08_SDLC_PROCESS.md) section 2 are followed by convention
rather than enforced by the platform. `CODEOWNERS` still requests review, but
nothing prevents a direct push to `main` or `develop`.

**Who can answer:** the repository owner, in the GitHub web interface under
Settings, Branches. The required `ci` status check is named `ci`.
**Blocks:** enforcement, not process.

## OQ-13
**Deployment details not yet decided.**

**Status: Closed 2026-08-24.** Answered by the author, who owns the AWS account
this prototype deploys to. The decisions are recorded item by item below, and
each one is now built or written down somewhere: the Terraform in
`infra/terraform/`, the runbook in [09_DEPLOYMENT.md](09_DEPLOYMENT.md), and
the limitations table in
[06_SECURITY_AND_COMPLIANCE.md](06_SECURITY_AND_COMPLIANCE.md) section 3.

**Nothing has been applied.** Closing this question means the decisions exist
and the code that implements them exists, not that any AWS resource does. The
author applies from her own machine; no session in this project has ever held
AWS credentials.

The eight items, as asked and as answered.

**1. Custom domain, and where the TLS certificate comes from.**
Neither. The prototype is reached at the load balancer's own DNS name over
plain HTTP. There is no domain to attach a certificate to and no certificate.
Recorded as a known limitation, with the production fix named as an ACM
certificate plus an HTTPS listener and a redirect from port 80, in
[06_SECURITY_AND_COMPLIANCE.md](06_SECURITY_AND_COMPLIANCE.md) section 3.

**2. Internet-facing or internal.**
Internet-facing, with no authentication, deliberately and with the conflict
this question raised accepted rather than resolved. The deliverable is a URL
an evaluator can open; an internal load balancer would not be one. What makes
it acceptable is bounded and stated: nothing is stored (NFR-6), so there is no
data to reach, and the residual risks are open compute use and unencrypted
transit. The production fix is an authentication layer at the edge. The
`ingress_cidr_blocks` variable narrows the exposure to a single address between
demonstrations, which is a mitigation the author can use without changing the
posture.

**3. VPC and subnet topology.**
A new VPC, created by this configuration, with two public subnets across two
availability zones and no NAT gateway. The task runs in a public subnet with a
public IP because a Fargate task must reach ECR and CloudWatch Logs to start at
all, and the alternatives, a NAT gateway or four interface endpoints, each cost
more per hour than the task they would be serving. The task's security group
accepts inbound traffic only from the load balancer's security group, so the
public IP is an egress path rather than an entrance. Private subnets are the
production shape and are named as such in `infra/terraform/network.tf`.

**4. Terraform state backend.**
Local state, and no backend block. One operator, one machine, and a stack whose
resting state is destroyed. The production alternative, an S3 bucket with
versioning and encryption plus a DynamoDB lock table, is named and not built;
see [09_DEPLOYMENT.md](09_DEPLOYMENT.md) section 11 for why standing up a
second stack to hold the state of a stack that is usually destroyed was not
worth it here.

**5. CloudWatch log retention.**
Seven days, set explicitly rather than left to the ECS default of never
expiring. A prototype that is applied and destroyed repeatedly should not leave
log data outliving every stack that produced it. A production retention period
is set by records management, not by this repository.

**6. ECS task CPU and memory sizing.** This is the item that had the most in
it, and the answer is arithmetic rather than a measurement.

**1 vCPU and 8 GiB** (`task_cpu = 1024`, `task_memory = 8192`, the largest
memory Fargate offers at that CPU). Sized to hold the assignment's own
scenario, 300 labels in one submission, because that scenario is the load
model.

The memory question this item raised is answered as it asked to be: the task
was sized first, then the caps were set to what that memory holds, and the
working is shown. `TTB_MAX_BATCH_BYTES` is set to **3 145 728 000 bytes**,
3 000 MiB exactly, with `TTB_MAX_BATCH_FILES` at 300 and `TTB_MAX_UPLOAD_BYTES`
at 10 MiB. The budget that leaves 4 322 MiB of the 8 192 unused, and why that
headroom is deliberate rather than waste, is
[09_DEPLOYMENT.md](09_DEPLOYMENT.md) section 4.3.

Two things were found while doing it that were not in the question:

- **`TTB_BATCH_WORKERS` has to be pinned, not derived.** The application sizes
  its pool from `os.sched_getaffinity`, which reports a cpuset. Fargate
  enforces task CPU as a CFS quota instead, so the affinity mask can report
  more cores than the task may use and the derived pool would oversubscribe a
  quota it cannot see. It is set to 1 in the task definition.
- **`OMP_THREAD_LIMIT` must stay out of the task definition entirely.**
  `backend/app/ocr.py` pins it with `setdefault`, so any value set in the
  environment wins, and any value other than 1 reinstates the Tesseract
  deadlock that hangs the batch path with no error. There is a comment saying
  so next to the environment block.

**7. Desired task count and autoscaling.**
One task, no autoscaling. That follows from the cost posture rather than from a
capacity judgment: a single task means a deployment has a brief window with no
healthy target and a task failure is an outage until ECS replaces it, and both
are acceptable for a prototype that is destroyed between demonstrations. It
does mean the "desired count >= 2" that appeared in the topology diagram of
[09_DEPLOYMENT.md](09_DEPLOYMENT.md) was wrong; that document has been rewritten
as the runbook and no longer says it.

**8. Who pays, and what the cost ceiling is.**
The author, from her own AWS account, with a posture of minimize: deploy,
demonstrate, destroy. `terraform destroy` is the resting state of the stack and
the runbook is written that way. The running stack is estimated at about **$0.12
an hour**, or about **$90 a month** if it were left up, from AWS published list
prices for `us-east-1`. Those are estimates and not measurements; nothing in
this repository has ever been billed. The itemized table is
[09_DEPLOYMENT.md](09_DEPLOYMENT.md) section 5.

**What remains open after this closure**, because closing a question honestly
means naming what it did not answer:

- Nothing has been measured on the deployed target. Every performance figure in
  this repository names the hardware it came from and none names production.
  The checklist that changes that is [09_DEPLOYMENT.md](09_DEPLOYMENT.md)
  section 9, and the README's claims do not move until it is done.
- Whether the NDJSON stream survives the load balancer unbuffered is
  **unverified**. `X-Accel-Buffering: no` is a hint to intermediaries, not a
  guarantee. Section 8.4 of the runbook is the test, and it can only be run
  against a real deployment.
- NFR-10 portability is argued, not demonstrated. No apply has been run in any
  region.

**Answered by:** the author, who owns the AWS account.
**Blocked:** nothing further. The deployment task is done to the boundary of
what a session without credentials can do.

## OQ-14
**Manual step: create Project board "TTB Label Verifier" with columns Backlog,
Ready, In Progress, In Review, Done and add all story issues.**

**Status: Closed 2026-08-21.** The board exists at
<https://github.com/users/kimkight/projects/1> with the columns Backlog, Ready,
In Progress, In Review, and Done, and issues #1 to #21 sit in Backlog.

It is a **user-owned** project, owned by `kimkight` rather than by an
organization, linked to this repository. That distinction matters for anyone
looking for it later: it does not appear under the repository's own Projects tab
the way an organization project would, and access to it follows the owning user
account rather than the repository's collaborator list.

The record of why it could not be created from a session follows.

Decision D-7 calls for a GitHub Project board. It was **not** created
during the initializing session. GitHub
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

**Status: Closed 2026-08-23.** The environment change described below took
effect. The preflight this question named as its own closing condition, "the
same preflight run from a new session returns `200` from both registries", was
run at the start of the session that built the verification engine and returned
`200` from both, with Tesseract present:

```
$ curl -sS -o /dev/null -w "%{http_code}\n" https://pypi.org/simple/requests/
200
$ curl -sS -o /dev/null -w "%{http_code}\n" https://registry.npmjs.org/express
200
$ tesseract --version 2>&1 | head -1
tesseract 5.3.4
```

**What that made possible in the same session**, which is the point of recording
it rather than just noting a status change:

- `pip install --require-hashes -r backend/requirements-dev.lock` installed all
  61 packages from the committed lock file, so the lock files generated outside
  a session under OQ-3 are now verified to install.
- The backend test suite ran locally, including the OCR tier, against
  Tesseract 5.3.4.
- `scripts/measure.py` ran the engine over the sample set and produced real
  per-field accuracy and latency numbers.

**Two caveats that the `200` does not remove.**

- **The session Tesseract is 5.3.4; the container ships 5.3.0.** The local
  binary comes from whatever the session image carries, and the container
  installs from Debian bookworm, which is the version recorded in OQ-2 and in
  `docs/05_ARCHITECTURE.md` section 8. A local OCR result is therefore not
  byte-for-byte evidence about the deployed one. The CI job that reports the
  version from inside the built image remains the authoritative record.
- **There is still no Docker daemon in a session.** That is a separate
  capability from egress policy and no network setting provides one, exactly as
  the original entry says. The container build and the health probe against a
  running container still happen only in CI.

The record of the three sessions in which this was denied follows, unchanged,
because the root cause and the way the denial presented are worth keeping.

---

**Original status, 2026-08-22: Open. Root cause identified. The fix was applied
to the environment but three sessions later the preflight still returned `403`,
so it was still unverified.**

**Root cause.** The cloud environment was set to the Custom network level with
the box "Also include default list of common package managers" left unchecked.
At that setting only the domains typed into the allowed-domains list are
permitted, and the platform's Trusted default list, which does include PyPI,
npm, and `archive.ubuntu.com` and `security.ubuntu.com`, is not applied at all.
So every package host was denied.

The denials were easy to misread, because `pypi.org`, `files.pythonhosted.org`,
and `registry.npmjs.org` all appear in the session's `no_proxy` variable.
**Being in `no_proxy` is not an allowlist entry.** It only means those hosts
bypass the local agent proxy on `127.0.0.1`; they still traverse the upstream
egress gateway, which denied them with an explicit header:

```
HTTP/2 403
x-deny-reason: host_not_allowed
Host not in allowlist: pypi.org. Add this host to your network egress settings
to allow access.
```

`deb.debian.org` failed one layer earlier, at the proxy `CONNECT` rather than at
the response, which is why it produced a transport error rather than a status
code:

```
CONNECT tunnel failed, response 403
connect_rejected: gateway answered 403 to CONNECT (policy denial or upstream
failure)   host: deb.debian.org:443
```

**Fix applied.** The `ttb-label-verifier` environment is set to Custom, with
"Also include default list of common package managers" checked, plus these
allowed domains: `www.ecfr.gov`, `ecfr.gov`, `unblock.federalregister.gov`,
`www.ttb.gov`, `ttb.gov`, `deb.debian.org`, `security.debian.org`. The two
Debian hosts are listed explicitly because the runtime image is
`python:3.11-slim-bookworm`, which is Debian and not Ubuntu, and the container
build runs `apt-get` inside it. The Ubuntu hosts come from the default list.

**Not yet verified.** Changing the allowed hosts or the setup script rebuilds
the environment cache on the next **new** session. The preflight below was run
on 2026-08-22 from a **resumed** session, which still carries the old cache, so
it still shows the denials:

| Check | Result |
| --- | --- |
| `curl https://pypi.org/simple/requests/` | `403`, `x-deny-reason: host_not_allowed` |
| `curl https://registry.npmjs.org/express` | `403`, `x-deny-reason: host_not_allowed` |
| `curl https://deb.debian.org/debian/dists/bookworm/Release` | `000`, CONNECT tunnel failed, response 403 |
| `curl https://www.ecfr.gov/api/versioner/v1/titles.json` | `200` |
| `tesseract --version` | `command not found` |
| `syft version` | `command not found` |
| `docker info` | unavailable |

This question closes when the same preflight run from a new session returns
`200` from both registries. Until then the lockfile work in OQ-3 cannot be done
from a session, and the Docker observation below stands on its own: a Docker
daemon is a separate capability from egress policy, and no network setting
provides one. **That condition was met on 2026-08-23; see the status at the top
of this entry.**

**Still denied on 2026-08-22, third session.** The preflight was run again at
the start of the session that closed OQ-3. Raw output:

```
$ curl -sS -o /dev/null -w "%{http_code}\n" https://pypi.org/simple/requests/
403
$ curl -sS -o /dev/null -w "%{http_code}\n" https://registry.npmjs.org/express
403
$ tesseract --version 2>&1 | head -1
/bin/bash: line 1: tesseract: command not found
$ docker info >/dev/null 2>&1 && echo "docker: ok" || echo "docker: unavailable"
docker: unavailable
```

The denial is the same one, from the same layer, with the response body naming
the host:

```
HTTP/2 403
x-deny-reason: host_not_allowed
Host not in allowlist: pypi.org. Add this host to your network egress settings
to allow access.
```

```
HTTP/2 403
x-deny-reason: host_not_allowed
Host not in allowlist: registry.npmjs.org. Add this host to your network egress
settings to allow access.
```

Both hosts are still listed in the session's `no_proxy`, which is again the
misleading part and again means nothing for egress. So the environment change
recorded above has not taken effect for sessions: either it was not saved, or
this session was served from the pre-change environment cache. **The question
stays open.** It is no longer blocking, because both lock files were generated
outside a session and committed (OQ-3 is closed), but the local verification
this question is about still cannot be done, and neither can any work that needs
Tesseract or a Docker daemon.

The original record follows.

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
failure)` for `pypi.org:443` and `files.pythonhosted.org:443`. The npm failure
surfaced as `npm error code E403 ... 403 Forbidden - GET
https://registry.npmjs.org/@eslint%2fjs`.

**A fourth, separate obstacle:** there is no Docker daemon in this session. The
`docker` CLI is present, but `docker compose up -d --build` fails with:

```
failed to connect to the docker API at unix:///var/run/docker.sock; check if
the path is correct and if the daemon is running: dial unix
/var/run/docker.sock: connect: no such file or directory
```

So the container build could not have run even with package access, and
`curl http://localhost:8000/api/health` correspondingly failed with
`Connection refused`.

Every one of the four required checks was attempted and every one failed for an
environmental reason, not a defect in the code:

| Required check | Attempted | Result |
| --- | --- | --- |
| `pytest` | Yes | Failed: `pip install` could not reach PyPI |
| Frontend build | Yes | Failed: `npm install` returned 403 |
| `docker compose up -d` | Yes | Failed: no Docker daemon |
| `curl /api/health` | Yes | Failed: nothing running to serve it |

The proxy documentation states that policy denials must be reported rather than
routed around, so no workaround was attempted.

Verification was therefore delegated to GitHub Actions, which has package
network access. The CI run result is reported in the final summary for this
work, and it is the only place where these checks have actually executed.

**A second capability is missing from the same session, unrelated to egress.**
Creating the two repository labels that `.github/dependabot.yml` applies,
`dependencies` and `type:task`, could not be done either. Neither label exists,
so Dependabot posts "labels could not be found" on every pull request it opens.
The `gh` CLI is not installed in the session, and the GitHub REST API is refused
before it reaches GitHub:

```
$ curl -sS -i -X POST \
    https://api.github.com/repos/kimkight/26-DO-12891471-DH_T_ITS_AI_THT/labels
HTTP/1.1 403 Forbidden
{"message":"GitHub access is not enabled for this session. An org admin must
connect the Claude GitHub App for this organization."}
```

This is a different denial from the package-manager one and does not have the
same cause. The session does reach GitHub through its own tooling, which
confirms the labels are absent rather than merely unreadable:

```
get_label(name="dependencies") -> label 'dependencies' not found
get_label(name="type:task")    -> label 'type:task' not found
```

That tooling can read labels but exposes no operation that creates one, and no
network setting changes that. The two labels must therefore be created by the
repository owner, either on the repository's Labels page or with:

```
gh api repos/kimkight/26-DO-12891471-DH_T_ITS_AI_THT/labels \
  -f name='dependencies' -f color='0366d6' \
  -f description='Dependency updates, usually opened by Dependabot'
gh api repos/kimkight/26-DO-12891471-DH_T_ITS_AI_THT/labels \
  -f name='type:task' -f color='c2e0c6' \
  -f description='Maintenance or tooling work, not a user-facing change'
```

Until they exist, Dependabot still opens its pull requests; it just cannot label
them. Recorded here rather than left implicit, because it is the second thing
this session could not do that the work assumed it could.

**Who can answer:** answered by the environment itself on 2026-08-23. The
allowed-domains change recorded above took effect once a session was served from
a rebuilt environment cache.
**Blocks:** nothing. A Docker daemon is still absent from sessions, but that was
never this question, and it is recorded above rather than left implicit.

## OQ-16
**How is application data supplied for a batch?**

**Status: reopened by the author on 2026-08-28 and closed again by
[ADR 0009](adr/0009-batch-cola-documents.md).** Answer: the applicant's own COLA
document, one per label, paired with its label image by filename stem. That is
a document that exists rather than a format that did not, and the FR-11 parser
already reads it.

The author's question was "where would these CSVs even come from?" and the
answer was that they would come from nowhere: nothing an importer files with TTB
produces one, so the batch path silently required an agent to type 300 rows of
the data they were trying not to type. A-14 is marked superseded. What is still
genuinely unknown is what a bulk submission looks like as files, which is
[OQ-23](#oq-23).

*The original closure, kept because it is the reasoning ADR 0009 rests on:*

**Status: Closed by [ADR 0006](adr/0006-batch-execution-model.md) and assumption
[A-14](ASSUMPTIONS.md#a-14).** Answer: one CSV keyed by image filename,
submitted as a part of the same multipart request as the images, with the
columns `filename`, `brand_name`, `class_type`, `alcohol_content`,
`net_contents`, and `beverage_type`.

**This is an assumption, not a stakeholder answer**, and it is marked
`(Assumption)` wherever it appears. The observation this question already
recorded, that `samples/expected.csv` keys on image filename and so a CSV would
be a natural fit, is what the decision rests on, together with the fact that
filename is the only identifier present on both sides of a submission: there is
no application number among the extracted fields, no persistence to hold a
mapping, and no authentication to scope one.

`beverage_type` is the one column that adds a field an agent would not otherwise
supply. It is there because A-12 and A-13 need the beverage class to know which
rule applies, and it is the part of A-14 most likely to be wrong.

The contract is stated in the FR-8 acceptance criteria in
[03_REQUIREMENTS.md](03_REQUIREMENTS.md), in ADR 0006, and in
[samples/README.md](../samples/README.md).

**What would reopen it:** Sarah Chen or Janet describing what importers actually
send, or COLAs Online turning out to export application data in a fixed layout.
Either supersedes A-14, and the cost is one input adapter.

The original record follows.

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

## OQ-17
**The default branch was not changed to `develop`.**

**Status: Closed 2026-08-21.** `develop` is now the repository's default branch,
set in the GitHub web interface under Settings, General, Default branch. Both
consequences listed below are therefore resolved: new pull requests opened
through the web interface default to targeting `develop`, and a fresh
`git clone` checks out `develop`.

The record of why it could not be done from a session follows.

Decision D-6 makes `develop` the integration branch, and the build instructions
called for `gh api -X PATCH repos/... -f default_branch=develop`.

**This was not done.** The repository's default branch is still `main`. The
reason is the same as obstacle 1 in OQ-12: `gh` is not installed, direct REST
calls to `api.github.com` return 403 with "GitHub access is not enabled for this
session," and the GitHub tool set available here exposes no repository settings
endpoint.

Consequences while `main` remains the default:

- New pull requests opened through the web interface default to targeting
  `main` rather than `develop`, which contradicts the Git Flow rules in
  [08_SDLC_PROCESS.md](08_SDLC_PROCESS.md) section 2.
- A fresh `git clone` checks out `main`, which holds only the initial commit,
  rather than `develop`, which holds all of the work.

Note that `.github/dependabot.yml` sets `target-branch: develop` explicitly, so
Dependabot is unaffected by this.

**Who can answer:** the repository owner, in the GitHub web interface under
Settings, General, Default branch.
**Blocks:** correct default targeting for new pull requests and clones. It does
not block any code.

## OQ-18
**The session git proxy rejects pushes to `refs/tags/*` with HTTP 403.**

Pushing an annotated tag from a session fails at the proxy, not at GitHub. Push
of a commit to `refs/heads/*` on the same remote, in the same session, with the
same credentials, succeeds. Only the tag ref is refused, which points at ref
filtering in the proxy rather than at repository permissions.

**Status: Closed 2026-08-22.** Resolution: tags and releases are created through
the GitHub Releases web interface rather than pushed from a session. Release
v0.1.0 was created that way, tagged at `79d5ac7` on `main`.

This is a durable change to the release procedure, not a one-time workaround, so
it is recorded in [08_SDLC_PROCESS.md](08_SDLC_PROCESS.md) section 7 as the
normal path. The practical consequence is small: the tag is still created from
`main` at a reviewed commit, and the deployment workflow still triggers on the
`v*` tag, because a tag created in the Releases interface fires the same event
as a pushed one.

**Who can answer:** whoever provisions the session environment, if the
restriction is ever meant to be lifted.
**Blocks:** nothing. The web interface path works.

## OQ-19
**How is a Dependabot command issued when the session's GitHub tooling rewrites
bot mentions?**

**Status: Open, 2026-08-23.**

`docs/DEPENDENCY_TRIAGE_2026-08.md` recommends `@dependabot rebase` as the clean
way to bring #42, #43 and #44 onto a `develop` that now has a lock file:
Dependabot regenerates `frontend/package-lock.json` as part of the pull request,
so the bump and its lock arrive together.

A rebase comment was posted to #43 and Dependabot did not act on it. Reading the
comment back through the API shows why. The session's GitHub tooling inserted
`U+00B7` middle dots into the mention and into the command word before posting:

```
·@·d·ependabot r·ebase
```

so what reached the pull request was not a command Dependabot recognizes. The
same rewriting is visible in the body of #45, where the identical string appears
in the merge-order note.

**This is a guardrail, not a defect.** It stops an agent from driving another
automation on the repository, which is a reasonable thing to stop. No attempt
was made to evade it, and none should be: the point of the rule is that a person
decides when a bot acts.

**What it costs.** Every Dependabot command in the triage document, `rebase`,
`recreate`, `ignore this major version`, has to be issued by the repository
owner rather than from a session. Three alternatives were considered and
rejected in the triage document: the "Update branch" button makes the pull
request red rather than green, pushing to Dependabot's branch takes the pull
request out of its management, and recreating the bump by hand replaces one
manual step with two.

**Who can answer:** whoever configures the session's GitHub integration, on
whether bot commands are meant to be issuable from a session at all. The answer
may well be no, in which case this entry stands as the record of why the triage
document's recommendations carry a manual step.
**Blocks:** nothing in the prototype. It makes Dependabot triage a two-party
operation: a session can read the pull requests and write the recommendation,
and a person issues the command.

## OQ-20
**Does a government warning printed entirely in capital letters match
27 CFR 16.21?**

**Status: Open, 2026-08-26.**

FR-5 compares the warning body for exact text after whitespace normalization,
and the comparison is case sensitive: `app/warning.py` tests
`body_found == expected_body`. 27 CFR 16.21 prints the statement with only the
first two words capitalized, and 27 CFR 16.22(a)(2) requires capitals for those
two words specifically, which implies the rest is not required to be in capitals
but does not say that setting it in capitals is a defect.

The question arose while writing assumption A-15. The real label examined for
that assumption was read for its hyphenation, not for its case, so this is not a
finding about that label; it is a gap noticed in the rule. Many commercial labels
do set the whole statement in capitals.

**Nothing is guessed here.** The comparison is left case sensitive, which is what
FR-5 as written requires, and no case folding was added on the strength of a
question. If the answer is that capitals are acceptable, the fix is one
normalization step in `app/warning.py` and one acceptance criterion in FR-5.

**Who can answer:** Jenny Park, or a compliance agent, or published TTB guidance
on 27 CFR part 16. Jenny is the stakeholder who described rejecting a label for a
title-case prefix, so she is the person most likely to know whether the reverse,
an all-capitals body, is also a rejection.
**Blocks:** nothing today. It would change FR-5's acceptance criteria and one
comparison in `app/warning.py`.

## OQ-21
**How often does real label artwork need cylinder or perspective dewarping, and
how much accuracy is lost without it?**

**Status: Open, 2026-08-26.**

The first real-artwork test found three causes for a photograph returning none of
its five fields. Two are fixed and recorded as A-15. The third is that the label
wraps a round bottle, so the far edges compress and no single photograph shows
the label flat. That is SG-1 and the ADR 0003 risk, and it is not attempted:
correcting it needs a cylindrical unwrap with an estimated radius, which is a
substantial piece of image processing to build against a sample of one
photograph.

[ADR 0007](adr/0007-multi-photo-single-label.md) works around it rather than
solving it, by accepting up to three photographs of the same label so an agent
can photograph the parts a single frame distorts. Whether that is sufficient in
practice is exactly what is unknown.

**What would answer it:** running the engine over a set of real photographed
bottles with ground truth, and reporting per-field accuracy with and without a
second photograph. That is the accuracy tier of
[07_TEST_STRATEGY.md](07_TEST_STRATEGY.md) section 3 applied to real artwork
rather than to the synthetic set, which is already named there as the largest
open technical risk.

**Who can answer:** measurement, not a person. It needs real label photographs,
which the repository does not hold and cannot redistribute
(`samples/README.md`).
**Blocks:** nothing in the prototype. It bounds any claim about accuracy on real
artwork, and it is the reason no such claim is made.

## OQ-22
**Which COLA document shapes and which form editions has the parser actually
been verified against?**

**Status: Open, 2026-08-27.**

FR-11 accepts an uploaded label application and reads the values off it. Two
things about that are verified and two are not, and the difference matters
because a reader who assumes all four will over-trust the feature.

**Verified.** The item map in assumption A-17 is read off the blank
TTB F 5100.31 (04/2023), downloaded once during development from
`https://www.ttb.gov/system/files/images/pdfs/forms/f510031.pdf`, including its
AcroForm field names and item 5's radio group export values. The three
extraction paths are each exercised against synthetic documents generated at
test time by `samples/formmaker.py`.

**Not verified.** No real filed application has been parsed, and no real Public
COLA Registry printout has been parsed. Both are real applicants' records, and
the no-personal-data rule in [07_TEST_STRATEGY.md](07_TEST_STRATEGY.md)
section 8 forbids committing one as a fixture. So the Registry captions the
parser matches, `BRAND NAME`, `FANCIFUL NAME`, `CLASS/TYPE`, `ALCOHOL CONTENT`
and `NET CONTENTS`, are the ones a printout is expected to carry rather than
ones that have been read off a printout. And the item map holds for the 04/2023
edition only: the form states that previous editions are obsolete without saying
how they differed, and an earlier edition may number its items differently.

**What would answer it:** running the parser over a set of real applications and
Registry printouts with the values known, and reporting per-field extraction
rates by document shape and edition, the way
[07_TEST_STRATEGY.md](07_TEST_STRATEGY.md) section 3 does for label artwork. A
redacted or synthetic set produced by TTB would serve, and would not carry the
personal-data problem.

**Who can answer:** Sarah Chen or Jenny Park, for which of the two documents an
agent actually holds and in what editions they arrive; measurement, for the
extraction rate.
**Blocks:** nothing in the prototype. Every parsed value is shown for
confirmation in an editable field before a check runs (ADR 0008), so a caption
this parser does not recognize costs an agent the typing they were doing
anyway rather than producing a wrong comparison. It bounds any claim that the
feature works on real documents, and it is the reason no such claim is made.

## OQ-23
**What does an importer's bulk submission look like as files, and would an agent
expect a batch to pair on filenames?**

**Status: Open, 2026-08-28.**

[ADR 0009](adr/0009-batch-cola-documents.md) decides that a batch is label
images plus one COLA document each, paired by filename stem:
`0001-stones-throw.png` with `0001-stones-throw.pdf`. The first half of that,
that a submission consists of applications and label images, follows from what
is filed with TTB. The second half, the pairing rule, is a choice this project
made, and it is the part no source speaks to.

**What is not known.** Whether a bulk submission arrives with filenames that
already correspond, or as a folder per application, or as one archive, or as
attachments on a set of emails. Whether an agent would find renaming files to
match an acceptable price, or an obstacle that keeps them on the one-at-a-time
path the batch exists to replace. Whether a stable identifier inside the
document, the TTB ID or the serial number, would be the better key.

**The alternative that was closest.** Pairing on an identifier read out of each
document would survive renamed files. It was rejected for this session because
it requires parsing every document before anything can be paired, so a batch
could not report its total until every document had been read, which is what
drives the progress display NFR-2 requires; because it depends on the parser
finding that identifier, which is A-17 territory and unverified against a real
filing ([OQ-22](#oq-22)); and because it still needs a fallback for a document
where the identifier is not found. If the answer to this question is that
filenames do not correspond in practice, that alternative is the one to build.

**Who can answer:** Sarah Chen, and Janet in the Seattle office, who is the
original requester of batch verification. One question each: what does the drop
actually look like when it lands, and what is on the files.
**Blocks:** nothing. The pairing rule is stated on the batch page, a mismatch
names the file it is about, and the rest of the batch still runs. The cost of
being wrong is that agents rename files they should not have had to.

## OQ-24
**Which COLA form editions embed the label artwork in the filed PDF, and which
file it separately? And how big are those embedded images in practice?**

**Status: Open, 2026-08-29.**

[ADR 0010](adr/0010-embedded-label-artwork.md) extracts every embedded raster
image from an uploaded COLA document, discards the ones below a size floor, and
reads the rest as label artwork. Two things about that rest on one document.

**What one document establishes.** The author's own filing, put through the
deployed v1.0.1 build on 2026-08-29, is TTB Form 5100.31, OMB No. 1513-0020,
three pages, and it carries the complete flat label artwork as an embedded image
on page 3 at 1750 by 1150 pixels. That is a filing that embeds its artwork. The
form's own item 15 refers to "THE LABELS AFFIXED BELOW", so the practice of
affixing labels to the application is the form's, not this filing's alone.

**What it does not establish.** Whether every edition of the form embeds the
artwork rather than attaching it as separate files; whether a COLAs Online
submission produces the same shape as a filed paper form scanned to PDF;
whether an approved application retrieved from the Public COLA Registry carries
the artwork at all, or only the typed items; and what range of pixel sizes real
embedded label images actually span. That last one is what the size floor was
chosen against, and it was chosen as a judgement about what a seal, a barcode
and a signature block look like next to a label scan, not from a distribution
anybody measured. The defaults are 400 pixels on the shortest edge, 250,000
pixels of area and a long-to-short edge ratio of 3.0, all settable
(`TTB_MIN_ARTWORK_EDGE_PX`, `TTB_MIN_ARTWORK_PIXELS`,
`TTB_MAX_ARTWORK_ASPECT_RATIO`).

**What the ratio adds, and why it was added in v1.1.0.** The two absolute
floors are properties of the scanner as much as of the thing scanned. The
author's document carries the applicant's handwritten signature on page 2 at
687 by 195, which both of them reject twice over; the same strip scanned at
300 dpi rather than 100 is about 2000 by 580, which clears both comfortably and
is still a signature. The shape does not move with resolution. That makes the
ratio the part of the floor least dependent on the distribution this question
asks about, and it is also the part that trades something away: a neck or strip
label filed on its own is genuinely long and thin and is rejected by it. Every
rejection is reported with its page, its size and a named reason, so the trade
is visible in the response rather than silent.

**What would answer it:** a set of real filings across editions and submission
routes, with the embedded image sizes reported, the way
[07_TEST_STRATEGY.md](07_TEST_STRATEGY.md) section 3 reports per-field accuracy
for label artwork. A redacted or synthetic set produced by TTB would serve and
would not carry the personal-data problem that keeps a real filing out of this
repository (07_TEST_STRATEGY.md section 8).

**Who can answer:** Sarah Chen or Jenny Park, for which document shapes actually
reach an agent's desk; measurement, for the sizes.
**Blocks:** nothing in the prototype. A filing whose artwork sits below the
floor reports the artwork fields as absent, which is exactly where v1.0.1 was,
and the agent types them. A filing that embeds something large that is not a
label has it reported as the label side, in the response and on screen, where
the agent can see it. It bounds the claim that this works across filings, and it
is the reason no such claim is made.



## OQ-25
**Should a label whose stated proof is not twice its stated alcohol content be
reported as a mismatch rather than as needs human review?**

**Status: Decided and closed, 2026-08-30. It stays needs human review, and the
constant is not flipped.**

**The decision, and the reasoning behind it.** Three sourced documents fix this
outcome and they agree: FR-7's third acceptance criterion, assumption A-12, and
UAT row 21 in [07_TEST_STRATEGY.md](07_TEST_STRATEGY.md). All three give the
same reason, which is that a proof disagreeing with an ABV "indicates an
internal inconsistency on the label itself".

That reason is the decision. A proof-against-percentage disagreement read off
one imperfect scan is exactly the judgement call Dave Morrison's human-review
band exists for: the tool has two numbers off one picture, they do not agree,
and it cannot tell from the picture whether the label is wrong or the reading
is. A mismatch says the label is wrong, which is a claim about the bottle. A
review says the label contradicts itself and a person should look, which is a
claim about the evidence. The second is what the evidence supports, and it is
what all three documents already say.

Neither outcome passes a label, so nothing about compliance turns on it. What
turns on it is what an agent is asked to do next, and asking a person to look at
a contradiction is the right ask.

**What was actually at issue, and why it was never the constant.** The author's
brief of 2026-08-30 described the defect as one that "is reported as a mismatch,
not as artwork-derived". Read in context the contrast is with the new
`artwork_derived` state rather than with `needs_review`: the requirement is that
a real defect must never be absorbed by a state meaning "nothing was checked".
That requirement is implemented and tested
([ADR 0013](adr/0013-artwork-derived-values.md)), and it is satisfied by either
failing outcome.

**Blocks:** nothing, and nothing is changed. `backend/app/compare.py` keeps the
constant it has, and the three documents keep the criterion they state.

**The question as it stood, kept for the record.**

FR-7's third acceptance criterion and assumption A-12 both fix this outcome as
**needs human review**, and both give the same reason: a proof that does not
equal twice the ABV "indicates an internal inconsistency on the label itself",
which is a person's call rather than the tool's. UAT row 21 in
[07_TEST_STRATEGY.md](07_TEST_STRATEGY.md) states the same expectation.

The author's brief of 2026-08-30, which is what
[ADR 0013](adr/0013-artwork-derived-values.md) implements, described the same
defect as one that "is reported as a mismatch, not as artwork-derived". Read in
context the contrast in that sentence is with the new `artwork_derived` state
rather than with `needs_review`: the requirement it states is that a real defect
must never be absorbed by a state that means "nothing was checked". That
requirement is implemented and tested.

What is left open is the outcome itself. Both are failing outcomes and neither
passes a label, so nothing turns on it for correctness; what turns on it is what
an agent is asked to do. A mismatch says the label is wrong. A review says the
label contradicts itself and a person should look. The second is what FR-7 and
A-12 say today, and it was chosen deliberately.

**Why this is not resolved by guessing.** Flipping it means amending FR-7's
acceptance criterion, A-12, and UAT row 21 together, which is an assumption
change rather than a code change. Making that change silently would leave three
sourced documents disagreeing with the code, which is the failure mode
[CONTRIBUTING.md](../CONTRIBUTING.md) rule 1 exists to prevent.

**What would answer it:** the author confirming which of the two they intended,
or a compliance agent stating what they do with a label that contradicts itself.

**Who can answer:** the author, for the requirement; Jenny Park or Dave
Morrison, for the practice.
**Blocks:** nothing. The check runs, the contradiction is reported, and it is
never reported as artwork-derived. The change, if it is wanted, is one constant
in `backend/app/compare.py` plus the three document edits above.
## OQ-26
**Does the application-document path meet NFR-1 once the duplicated OCR pass is
gone, on the deployed target rather than on a session container?**

**Status: Answered and closed, 2026-08-30. It does, at about 3.5 s against a
target of roughly five.**

**The answer.** The same document was submitted to the same URL against deploy
#11, three consecutive runs from the author's browser:

| run | wall clock | server `elapsed_ms` | `unaccounted_ms` | `ocr_passes` |
| --- | --- | --- | --- | --- |
| 1 | 3468 ms | 3387 ms | 1.3 ms | 1 |
| 2 | 3505 ms | 3411 ms | 1.3 ms | 1 |
| 3 | 3543 ms | 3463 ms | 1.3 ms | 1 |

`ocr_passes` reads 1, which is what this question asked for. `elapsed_ms` is now
within 80 ms of the browser's wall clock rather than 3.5 seconds away from it,
and `unaccounted_ms` of 1.3 ms is what says the phase breakdown covers the
request rather than a part of it. The matrix row, the README and
[09_DEPLOYMENT.md](09_DEPLOYMENT.md) section 9 all carry these figures.

**What the answer does not cover, stated because it is a real limitation.**
Those runs were taken while the artwork OCR on this document was still failing:
the label was being turned 180 degrees on an orientation verdict of 0.03
confidence and then flattened to grayscale, so 3.5 seconds was the cost of
reading a wrongly turned, wrongly rendered image. v1.1.0 changes what is read.
The figure is re-measured against the next deploy, by re-running
[09_DEPLOYMENT.md](09_DEPLOYMENT.md) step 8.3a, and updated everywhere it
appears if it moves. That is a follow-up on a closed question rather than the
question staying open: what was asked was whether removing the duplicate pass
put this path inside the bar on the deployed target, and it did.

**The history, kept because the shape of the mistake is the useful part.**

**What is measured.** The author submitted their own mezcal COLA document, a
382 KB PDF, alone to the deployed URL on 2026-08-30, build 1.1.0, three
consecutive runs from the browser: 6883, 6786 and 6781 ms wall clock. That is
outside NFR-1's roughly five seconds, and it is recorded as a miss in the README
and in [09_DEPLOYMENT.md](09_DEPLOYMENT.md) section 9.

**What was wrong with the number beside it.** The response reported `elapsed_ms`
of 3323, 3214 and 3198 ms, within 2 ms of `ocr_ms` on every run, because
`elapsed_ms` was measuring the label-side OCR span rather than the request. Two
controls from the same session bound the network at 18 to 25 ms for a health
round trip and 68 to 111 ms for a POST of the same file to a path that processes
nothing, so the roughly 3.5 seconds the interface was calling "sending the
image" was server work nobody was counting.

**What changed.** `elapsed_ms` now covers the handler end to end, the response
carries a measured phase breakdown, and the picture chosen as the label side is
read once instead of twice. On a session container a one-image document went
from 2.19 s to 1.12 s and a two-image document from 3.17 s to 1.15 s, with the
Tesseract passes going from two and three to one.

**Why this is still open.** A session container is not a Fargate task behind a
load balancer, and halving the number of OCR passes on hardware where each pass
took about 3.3 seconds *should* put this near 3.5 seconds, but that is
arithmetic. This repository does not publish arithmetic as measurement
([README](../README.md), "Measured performance and accuracy"). The 6.8 s figure
stands until it is re-measured.

**What would answer it:** deploy a build carrying this change and re-run
`docs/09_DEPLOYMENT.md` step 8.3a with the same document, recording the wall
clock and the `timings` block. `ocr_passes` should read 1.

**Who can answer:** the author, with the deployed URL and that PDF.
**Blocks:** nothing in the prototype. It blocks any claim that NFR-1 is met on
this path, which is why no such claim is made.
