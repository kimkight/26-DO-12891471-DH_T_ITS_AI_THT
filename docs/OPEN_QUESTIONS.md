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
| [OQ-13](#oq-13) | Open | Deployment (a later task) |
| [OQ-14](#oq-14) | Closed 2026-08-21 | Nothing; the board exists and is linked to the repository |
| [OQ-15](#oq-15) | Open, root cause identified 2026-08-22, still denied on re-check | Local verification of the build in this environment |
| [OQ-16](#oq-16) | Closed by ADR 0006 and assumption A-14 | Nothing; the CSV contract is stated |
| [OQ-17](#oq-17) | Closed 2026-08-21 | Nothing; `develop` is the default branch |
| [OQ-18](#oq-18) | Closed 2026-08-22 | Nothing; tags are created in the Releases web interface |

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

**Status: Open. Root cause identified 2026-08-22. The fix was applied to the
environment but three sessions later the preflight still returns `403`, so it is
still unverified.**

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
provides one.

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

**Who can answer:** whoever provisions the session environment. If the intent
was for the environment to allow the default package-manager list, the policy
does not currently match that intent.
**Blocks:** local verification only.

## OQ-16
**How is application data supplied for a batch?**

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
