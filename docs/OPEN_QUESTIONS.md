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
| [OQ-7](#oq-7) | Open on the formal question; answered in practice 2026-09-01 | Nothing; Section 508 via WCAG 2.0 AA is claimed and evidenced in ACCESSIBILITY_CONFORMANCE.md, and WCAG 2.1 AA is verified above it |
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
| [OQ-22](#oq-22) | Closed 2026-09-06, by measurement on two real filings (ADR 0021) | Nothing; the two documents are committed as evidence in `samples/real/`, and what stays unmeasured, editions and routes, is carried by OQ-24 |
| [OQ-23](#oq-23) | Open | Nothing; it would confirm or improve the ADR 0009 pairing rule |
| [OQ-24](#oq-24) | Narrowed 2026-09-03 and again 2026-09-04: the size question is answered for three real documents and no code decision now rests on it; what stays open is which editions and routes embed the artwork at all | Nothing in the prototype; it bounds the coverage claim for the embedded artwork path (ADR 0010) and nothing else |
| [OQ-25](#oq-25) | Decided 2026-08-30: stays needs human review | Nothing; the constant is unchanged and FR-7, A-12 and UAT row 21 all stand |
| [OQ-26](#oq-26) | Answered 2026-08-30: met at 5.0 s, at the line | Nothing; re-measured against deploy #12, and the 1.4 s the orientation check costs is what took the margin |
| [OQ-27](#oq-27) | Open | Nothing; it would buy back part of the NFR-1 margin the orientation check consumed (OQ-26) |
| [OQ-28](#oq-28) | Open | Nothing; class or type is compared where declared and reported not compared where not |
| [OQ-29](#oq-29) | Decided and closed 2026-09-01: history stands | Nothing; the line that would have changed the answer is recorded |
| [OQ-30](#oq-30) | Decided and closed 2026-09-02: NFR-6 reworded, engine not re-plumbed | Nothing; the stronger guarantee and the spool window are recorded with what would change the answer |
| [OQ-31](#oq-31) | Open, #122; tracked, not fixed, in v1.3.0 | Nothing; the fanciful name is displayed and never compared |
| [OQ-32](#oq-32) | Open, #123; measured on synthetic documents in v1.3.0, floor not moved | Nothing; where the margin falls short the agent chooses |
| [OQ-33](#oq-33) | Open, #128; found in v1.3.0, the test corrected, the panel not changed | Nothing; the result is complete and readable, it scrolls |
| [OQ-34](#oq-34) | Decided and closed 2026-09-02: the registry stays mutable, the release-tag guard is in the workflow | Nothing; a re-run of the deploy on the same commit works |
| [OQ-35](#oq-35) | Open; measured 2026-09-02, recommendation recorded, Terraform unchanged | Nothing; the task runs. It costs about 59 times the memory it uses |
| [OQ-36](#oq-36) | Open; found 2026-09-02, inert, fix named | Nothing; the three dead subjects admit nothing and the three live ones do the work |
| [OQ-37](#oq-37) | Open; measured 2026-09-02 | Nothing; the check does not wait for the chips. A twenty-image drop reads each image twice, once to classify and once to check |
| [OQ-38](#oq-38) | Open; named 2026-09-06, logic unchanged | Nothing in the prototype; it bounds the alcohol content presence check to distilled spirits. On a malt beverage or a table wine the check can report a compliant label as a finding |
| [OQ-39](#oq-39) | Open; measured 2026-09-06; the arms that read nothing on that panel no longer paid for, 2026-09-08 | Nothing; a line of legible type set over full-colour artwork is not isolated by the reader, and a real filing's class or type, alcohol content and net contents sit on one |
| [OQ-40](#oq-40) | Open; found 2026-09-08 on a third real filing, not fixed | Nothing in the prototype; on that filing the area floor rejects both label panels, no artwork is read, and a document-only check is refused for want of a label side |
| [OQ-41](#oq-41) | Open; found 2026-09-08 on the same filing, not fixed | Nothing in the prototype; on a scanned form the OCR path can fill the brand name with the form's own caption and the class or type with the next item's instruction, and the check then reports a confident mismatch against a correct application |
| [OQ-42](#oq-42) | Open; the third failure of a single-document calibration, number not moved | Nothing; where the item 5 margin is not cleared the agent chooses the beverage type, which is never compared |

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

**Answered in practice on 2026-09-01, and still open as a question.** The author's
instruction was "this entire project needs to be 508 compliant; ensure that it
is." So the work was done as though it applies: NFR-5 now names Section 508 and
the WCAG 2.0 AA standard it adopts at 36 CFR Part 1194, Appendix A, E205.4, and
[ACCESSIBILITY_CONFORMANCE.md](ACCESSIBILITY_CONFORMANCE.md) is a
criterion-by-criterion report with its exceptions stated.

What remains open is the half only the agency can answer: whether a prototype of
this kind is formally in scope, and whether there is an agency standard beyond
WCAG 2.1 AA. Neither changes what was built. Doing the work while the question is
open is the right way round: the cost of being wrong that way is a report nobody
needed, and the cost of being wrong the other way is a system an agent cannot
use.

**Who can answer:** Marcus Williams, or the agency Section 508 program office.
**Blocks:** nothing. Section 508 via WCAG 2.0 AA is claimed and evidenced, and
WCAG 2.1 AA is verified above it.

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
case inventory? The answers would change if a generative fallback were ever
built (ADR 0003 designed one and it was not built), since the only path is
deterministic OCR rather than a generative model.

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

**Status: Closed 2026-09-06, by measurement.** The parser has been run against
two real Public COLA Registry printouts, both now committed unaltered as
evidence in `samples/real/` under
[ADR 0021](adr/0021-real-filings-as-evidence-not-fixtures.md), which also
records why the no-personal-data rule below no longer forbids that and what it
still forbids. Nothing automated reads either file.

**What was measured, in one paragraph each.** The mezcal, TTB ID
22118001000389, returns five of five: its declared values are read off the
printout and its embedded artwork is read as the label side, all five fields
matched, at the NFR-1 line on the application-document path. The figures are
in the README's latency table and in [09_DEPLOYMENT.md](09_DEPLOYMENT.md)
section 9, and the misread that preceded them is traceability source row 31.
The bourbon, TTB ID 15309001000084, found three separate defects, and the
record of them is [ADR 0021](adr/0021-real-filings-as-evidence-not-fixtures.md)
and `samples/real/README.md` rather than a restatement here: an alcohol
statement in a form the matcher did not handle, a government warning that
reads well but is overprinted so that a word for word comparison fails on a
label a human would pass, and a net contents statement absent from every
panel, which is the tool being correct about the label as submitted. Before
those three it had also found the two defects in the artwork floor, one of
five on v1.4.0 and two of five on v1.5.0, which are source rows 42 and 43 and
ADR 0010 as amended twice.

**What the two documents answered about editions.** The question anticipated
that an earlier edition might number its items differently, and both do. The
bourbon's printout states TTB F 5100.31 (07/2012) and the mezcal's states
(06-2016); neither is the 04/2023 edition the item map in A-17 was read off,
and the telephone number, for one, is item 12 on the one and item 16 on the
other. The values parser reads the Registry captions rather than item
numbers, and it read both. So the caption path is measured on two editions.
The item map itself, which serves the fillable-form path and item 5's radio
group, is still measured on the 04/2023 form alone, because neither real
document is a fillable form.

**What stays unmeasured, and where it lives.** A filled-in fillable form of
any edition, and which editions and submission routes embed the artwork at
all. Both bound the coverage claim and neither blocks anything; OQ-24 already
carries the editions and routes question, and it is not reopened here. A
per-field extraction rate by document shape and edition, which the original
entry named as the full answer, would need more than two documents and is
not claimed.

The original entry follows, unchanged, because the reasoning it records for
keeping real records out of fixtures still holds; what changed is that
evidence is no longer treated as a fixture.

---

**Original status, 2026-08-27: Open.**

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

**Status: Narrowed 2026-09-03, and again 2026-09-04. The size question is
answered for three real documents and the floor is rebuilt on the answer; the
second measurement of the bourbon then showed that neither size nor shape
says which panel carries a value, and the fixed read count that still rested
on size is gone. No code decision now depends on the distribution this entry
asks for. What stays open is which editions and submission routes embed the
artwork at all, which bounds the coverage claim and nothing else. See the last
two paragraphs, ADR 0010 as amended twice, and #121.**

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

**The floor rejects real Registry artwork wholesale (2026-09-01, #121; tracked,
not fixed, in v1.3.0).** The author's secondary test document, a one-page
Public COLA Registry printout, carries seven embedded images, the largest at
1442 by 433. All seven are rejected: the largest on aspect ratio (3.33 against
the ceiling of 3.0) and the other six on the short edge. Submitted alone the
document returns `no_label_to_check`. The rule was set to exclude a signature
strip, and it is excluding label artwork with the same rule, which answers the
question this entry asked with a distribution of one: at least one real
submission route embeds its artwork at sizes and shapes the floor refuses.
**This is a design question, not a threshold tweak.** Raising the ratio ceiling
to admit a 3.33 strip admits a signature scanned at the same shape, which is
the case the ratio exists for; lowering the edge floor admits the barcodes and
seals it exists for. What separates a label from a signature on that page is
not size or shape but what it carries, and a floor cannot see that. A fix
needs a synthetic fixture shaped like the printout (seven images, the largest
wide and short, the rest small), built from the dimensions the author can
report, and a rule that reads a rejected candidate rather than measuring it, or
that lets a document with no admitted artwork fall back to its largest rejected
picture and say so. Either is a decision with an ADR, and v1.3.0 is polish on a
submission that is already defensible (SC-5), so it is recorded here and in
#121 rather than half-built. **What would change the answer:** the fixture,
and the numbers from a second real Registry page. The printout itself never
enters the repository.

**The second filing answered it, and the floor is rebuilt (2026-09-03,
v1.5.0).** The author put a real filed bourbon COLA through the deployed
v1.4.0 build. One of five checks passed, and the response said why: six
embedded pictures, five rejected on `short_edge`, and the aspect-ratio rule
would have taken four of them next. Their sizes, which are the measurement
this question asked for:

| Picture | Area | Ratio | What it is |
| --- | --- | --- | --- |
| 1103 x 340 | 375,020 | 3.24 | a label panel |
| 772 x 194 | 149,768 | 3.98 | small enough to be a neck band |
| 1050 x 309 | 324,450 | 3.40 | a label panel |
| 187 x 1697 | 317,339 | 9.07 | a vertical side band |
| 1350 x 300 | 405,000 | 4.50 | a label panel, a wrap-around |
| 687 x 195, the author's other filing | 133,965 | 3.52 | the applicant's signature |

Against the Registry printout's seven (the largest 1442 by 433, then 754 by
379, 800 by 226, 519 by 327, 190 by 190, 355 by 93, 238 by 62), that is three
real documents and eighteen embedded pictures, which is a distribution of
three rather than one. What it shows: the two shape rules reject real label
panels wholesale and no value of either admits the panels while excluding the
signature; the area floor at 250,000 admits every panel that carries a value
on both filings and excludes the signature with margin on each side. So the
shape rules are gone, the area floor is the whole of the floor, every panel
that clears it is read and pooled, and the response lists what was read as
well as what was set aside. [ADR 0010](adr/0010-embedded-label-artwork.md)
as amended on 2026-09-03 records the reasoning; `backend/tests/test_artwork_panels.py`
is the synthetic fixture in the bourbon's shape this entry asked for, and it
fails on the v1.4.0 rules and passes on the new one. The 772 by 194 picture is
still set aside, reported with its size and the reason, which is the right
outcome for a neck band and would be the wrong one for a small back label;
whether such a picture ever carries one of the five values is the part of this
question the two filings do not answer.

**The second measurement of the bourbon, and what it took off this question
(2026-09-04).** The rebuilt floor was deployed and the bourbon was put through
it again. Every panel cleared the floor; the two panels the shape rules had
thrown away read at 86.8 and 89.9, better than the 45.3 of the wide sheet the
rules had kept; the brand and the class or type matched. And the alcohol
content, the net contents and the government warning were still not found,
because `TTB_MAX_ARTWORK_IMAGES` was four, the filing carries five pictures
above the floor, and the 187 by 1697 side strip ranked last by area and was
never read. The size question this entry asked had been answered well enough
to set the floor; it was still being asked, silently, by a count. Reading now
stops when the panels read so far carry all five values and the count is a
ceiling on the worst case, at eight (ADR 0010 as amended 2026-09-04). So the
sizes of embedded pictures no longer decide anything in the code except which
of them is the applicant's signature, and that decision has three real
documents on the right side of it. Which of the bourbon's panels carries the
three missing values is the author's next request against the deployed build,
and the response now says; the synthetic fixture puts them on the strip.

**What stays open.** Which form editions and submission routes embed the
artwork at all. Three documents cannot answer that; a redacted or synthetic
set from TTB still would. It bounds the claim that the artwork path works
across filings, and it is the reason no such claim is made. Nothing in the
prototype blocks on it: every picture above the floor is read until the values
are in hand, and every picture is reported either way.



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

**Status: Answered and closed, 2026-08-30. It does, at 5.0 s against a target of
roughly five: at the line rather than under it.**

**The answer, re-taken against deploy #12.** The same document was submitted to
the same URL once the release that reads this artwork correctly had landed, two
consecutive runs from the author's browser:

| run | wall clock | server `elapsed_ms` | `ocr_passes` | `tesseract_reads` |
| --- | --- | --- | --- | --- |
| 1 | 4999 ms | 4928 ms | 1 | 4 |
| 2 | 4992 ms | 4918 ms | 1 | 4 |

`ocr_passes` reads 1, which is what this question asked for. It is written as
5.0 s and not rounded down, because 4999 ms against a bar of about five seconds
is a fact worth stating precisely rather than a number to be tidied.

**What consumed the margin, stated plainly: the fix that made the readings
correct.** Against deploy #11 earlier the same day the same document measured
3468, 3505 and 3543 ms, with `unaccounted_ms` at 1.3 ms. Those runs were taken
while the artwork OCR on this document was still failing: the label was being
turned 180 degrees on an orientation verdict of 0.03 confidence and then
flattened to grayscale, so 3.5 seconds was the cost of reading a wrongly turned,
wrongly rendered image and getting three of five fields wrong. About 1.4 s of
the rise from 3.5 to 5.0 is the 180-degree check that replaced that: it reads
the image at both candidate rotations and keeps the better-scoring one, and it
runs only where Tesseract's own orientation confidence falls under the floor.
It took this artwork's OCR confidence from 37.9 to 89.6 and found the alcohol
content and net contents. On the twelve sample labels it does not run at all.

That is a real engineering trade and it is worth making: a second and a half of
a five-second budget to stop reading a label upside down. It is also worth
seeing rather than averaging away, which is why it is here and in the three
other places the figure appears. A costed but unbuilt way to get some of it
back is [OQ-27](#oq-27).

`elapsed_ms` is within 80 ms of the browser's wall clock on both runs, which is
what says the phase breakdown covers the request rather than a part of it. The
matrix row, the README and [09_DEPLOYMENT.md](09_DEPLOYMENT.md) section 9 all
carry these figures.

**The panel segmentation released after deploy #12 is not expected to move
this,** because it adds no Tesseract read: the column split and the block
grouping are both arithmetic on the word table the single existing pass already
returns, and `backend/tests/test_panel_segmentation.py` asserts the read count
rather than leaving it to a measurement. Confirmed on a session container, which
is not production hardware and is quoted only as a before-and-after on one
machine: a median of 3300 ms over five runs before that change and 3280 ms after
it, `ocr_passes` 1 and `tesseract_reads` 4 either side. Re-run
[09_DEPLOYMENT.md](09_DEPLOYMENT.md) step 8.3a against the next deploy anyway,
and record what is measured rather than what was expected.

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

## OQ-27

**Would reading the two rotation candidates at a lower resolution separate them
just as reliably, and how much of NFR-1's margin would that buy back?**

**Status: Closed 2026-09-01. Measured over the forty-eight cases, and built at
half resolution.**

**Why it was worth asking.** The 180-degree check in `backend/app/ocr.py` is what
made the author's mezcal artwork readable, and it is what took this path from
3.5 s to 5.0 s against NFR-1's roughly five (OQ-26). It costs two full Tesseract
reads at the working resolution, and it does so only to decide between two
numbers that are far apart: on that artwork, 91.8 upright against 32.1 upside
down. Separating 91.8 from 32.1 does not obviously need every pixel.

**The first measurement, on one image.** The same artwork, both candidates scored
at each scale, on a session container. The time is for both candidates together;
the confidences are upright against upside down.

| scale | long edge | both candidates | upright | upside down | chose |
| --- | --- | --- | --- | --- | --- |
| 1.00 | 1600 px | 1013 ms | 91.8 | 32.1 | correctly |
| 0.60 | 960 px | 838 ms | 82.2 | 28.9 | correctly |
| 0.50 | 800 px | 671 ms | 62.2 | 25.0 | correctly |
| 0.40 | 640 px | 648 ms | 39.0 | 21.9 | correctly |
| 0.30 | 480 px | 285 ms | 35.3 | 21.7 | correctly |
| 0.25 | 400 px | 183 ms | 0.0 | 1.0 | **backwards** |

One image is not a measurement of a decision rule, so this was not built on it.

**The measurement that answered it, on 2026-09-01.** The set ADR 0003 was decided
on: the twelve sample labels at all four cardinal rotations, forty-eight cases,
with the check forced to run on every one of them and offered the correct turn
against its opposite. Run twice. First on the clean renderings, where the check
is right in 48 of 48 at every scale down to 0.25; an input that easy cannot
separate a good scale from a bad one, so it decides nothing. Then on the same
set degraded into something shaped like a phone photograph
(`tests/conftest.py::photographic`), which is the input the check exists for:

| scale | long edge | right | both candidates, per case |
| --- | --- | --- | --- |
| 1.00 | 1600 px | 48 of 48 | 1504 ms |
| 0.60 | 960 px | 48 of 48 | 957 ms |
| 0.50 | 800 px | 48 of 48 | 781 ms |
| 0.40 | 640 px | 48 of 48 | 649 ms |
| 0.30 | 480 px | **44 of 48** | 381 ms |
| 0.25 | 400 px | 48 of 48 | 312 ms |

The four failures at 0.30 are the beer label at all four submitted rotations,
where the correct turn scores 35.2 against its opposite's 37.1: 1.9 points the
wrong way round.

**What was built: 0.50, and the reason it is not lower.** Half resolution is
right in as many of the forty-eight cases as full resolution is, on both the
clean and the degraded set, and on the one real filing measured it keeps the two
candidates 37 points apart. It costs about 48 percent less on the degraded set
and about 34 percent less on the real filing, which on the deployed figures is
roughly half a second off a path that had 5.0 s against a target of about five.

0.30 fails, and 0.25 passes again below it. A rule whose accuracy is not
monotone in its own parameter has started reading noise rather than text, and
the single-image table above has 0.25 answering backwards on real artwork. So
the scale sits one measured step above the first failure rather than at the last
passing value. `ORIENTATION_CHECK_SCALE` in `backend/app/ocr.py` carries the
table and the argument; `tests/test_orientation_floor.py` asserts that the
scoring passes are reduced and that the picture the pipeline goes on to read is
not.

**What would reopen it:** a Tesseract release that changes how word confidence
behaves under downsampling, or a real filing on which the check answers
backwards at 0.50. Either means re-running the sweep before trusting the scale.

## OQ-28

**Should the class or type designation also be a presence check?**

**Status: Open, raised 2026-09-01 by [ADR 0018](adr/0018-presence-checks.md).**

**Why it is worth asking.** 27 CFR requires a class or type designation on the
label as surely as it requires alcohol content and net contents, so the argument
FR-15 makes for those two runs the same way for this one: where the application
declares nothing, whether the label carries the designation is still a real,
answerable, non-circular question.

**Why it was not decided with FR-15.** Two things are missing that the other two
fields have. The regulation citations were fetched, quoted and checked for those
two on 2026-08-30 and no equivalent work has been done here; a section number
written from memory is exactly what CONTRIBUTING.md forbids. And more
substantially, "the label carries a class or type designation" is not a question
this tool can currently answer. Alcohol content and net contents are recognized
by pattern, and a pattern either matches or does not. A class or type
designation is recognized by type size, which is the ranking that
[ADR 0015](adr/0015-verify-by-search.md) exists to work around because it read
the fanciful name as the brand on the author's own artwork. A presence check
built on a ranking that declines would report "the label does not carry a class
or type" about a label that plainly does.

**What would answer it:** the citation work, plus a way of establishing that a
class or type designation is present that does not depend on the type-size
ranking. The second is the harder half and it is the same problem OOS-5 and
ADR 0015 circle.

**Who can answer:** the author, with the regulation text; the recognition half
needs a measurement over real artwork, which is OQ-21's territory.
**Blocks:** nothing. The field is compared normally wherever the application
declares it, and reports "not compared" where it does not, which is what it did
before FR-15 and is not wrong, only incomplete.

## OQ-29

**Should the repository's history be rewritten to remove a real producer's tax
registration number?**

**Status: Decided and closed 2026-09-01. No. Recorded here so the line is
reusable.**

**What happened.** The v1.2.0 code review (`docs/CODE_REVIEW_2026-09.md`,
finding 2) found that a Mexican RFC, the business tax registration number of
the producer of the author's own filed COLA, had been committed in a docstring
of `backend/app/ocr.py` in three consecutive commits on 2026-08-31 and removed
in a fourth. It is not in any release's tree; it is recoverable from history.

**What it is, and what it is not.** An RFC is printed on the back of every
bottle of the product and on public registry pages. It is not a credential, not
a secret, not a personal identifier, and not an applicant's private filing
data. The signature image on page 2 of the same filing is in a different class
and has never been committed.

**What a rewrite would cost.** A force-push of `main` and `develop`, re-creating
the published `v1.2.0` tag on a different commit, a support request to purge
cached views, and every commit hash cited in this CHANGELOG, the ADRs and
eighteen merged pull request bodies pointing at objects that no longer exist. A
reader following a link from the CHANGELOG to a dead commit is a worse outcome
than the datum itself.

**Decision.** History stands. The value was removed from the tree on
2026-08-31; the real brand and product values that were fixture defaults and
test expectations were replaced with invented ones in v1.2.1 (#101); the
CHANGELOG and ADR text that record what happened on that filing are left as the
record they are, because a record describes what happened and a fixture asserts
what should happen. **The line that would have changed the answer:** a permit
number tied to a named individual, a contact's details, a signature, or anything
not already printed on a public retail package. Any of those in history is
rewritten out, whatever it costs.

**Who decided:** the author, 2026-09-01, in
`docs/CODE_REVIEW_DECISIONS_2026-09.md` decisions 1 and 8.
**Blocks:** nothing.

## OQ-30

**Should the OCR engine be fed over standard input, so that no temporary file
exists at all, and can the multipart spool window be closed from the header?**

**Status: Decided and closed 2026-09-02. Neither, for now; both recorded here
as the stronger measures available if NFR-6 ever hardens.**

**What happened.** The v1.2.0 code review (finding 4, #103) found that NFR-6's
first acceptance criterion, "no image or form field is written to disk", was not
true of any request the service accepted: `pytesseract` hands the engine every
image through a temporary file it writes and deletes before the call returns,
and Starlette spools a multipart part over the per-file limit to a temporary
file before the exact size check refuses it. The author's decision
(`CODE_REVIEW_DECISIONS_2026-09.md`, decision 4) was to correct the claim
rather than the code: NFR-6 is reworded in v1.3.0 as the retention promise it
always was, `docs/06_SECURITY_AND_COMPLIANCE.md` section 3.2 says where the
bytes are while a request runs, and `TestNothingIsRetained` asserts that
nothing survives one.

**The stronger guarantee, and why it was not taken.** Tesseract reads an image
from standard input (`tesseract - -`), so a direct `subprocess` call could feed
it the decoded pixels with no file on any disk. That drops a maintained
dependency and hand-rolls a wrapper covering the OSD and TSV output paths the
pipeline uses, which is code to own for a guarantee the reworded claim already
gives honestly; SC-5 rewards owning less. It would also leave the spool window
untouched, which is the other half of the finding.

**The spool window, and why it is documented rather than closed.** The
whole-request guard reads `Content-Length` before the body is read. A
single-label request may carry up to four files, so the guard bounds the
envelope at four times the per-file limit and cannot count the parts without
reading the body it exists not to read; a part between 10 MiB and 40 MiB on
`POST /api/verify` and `POST /api/classify`, or between 10 MiB and the batch
envelope on `POST /api/verify-batch`, is spooled and then refused, and the
spooled file is deleted with the request. Starlette 1.6 caps non-file parts
(`max_part_size`) and the count of files, and has no per-file byte cap; closing
the window means owning its multipart parser, which is the framework internal
the decision said not to fight. `test_verify_integration.py::TestNothingIsRetained::test_an_oversize_part_is_spooled_refused_and_gone`
counts exactly one rollover on such a part and asserts the directory is empty
afterwards, so the window's size and its retention are both pinned.

**What would change the answer:** a requirement that content never touch
ephemeral storage even transiently, which is a different requirement from
retention and would come from a records or security review rather than from
this prototype's own scope. Then: the stdin wrapper, and either a Starlette
release with a per-file cap or a small parser of this repository's own.

**Who decided:** the author, 2026-09-01, in decision 4.
**Blocks:** nothing.

## OQ-31

**The fanciful-name capture over-runs on a Registry printout: what should bound
the value?**

**Status: Open, filed 2026-09-01 as #122; tracked, not fixed, in v1.3.0.**

**What happened.** On the author's secondary test document, a one-page Public
COLA Registry printout, `_VALUE_LOOKAHEAD` in `backend/app/application_form.py`
swallowed a line belonging to the next item, so the fanciful name came back as
seven words where the document prints fewer. The value is shown to the agent as
a line and is never compared (OOS-5), so the cost today is a wrong caption on a
datum the check does not use.

**Why it is not fixed in this release.** The over-run is a property of how the
printout lays out captions and values, and there is one real example of it,
which cannot enter this repository. A fix that is not reproduced on a synthetic
fixture shaped like that printout would be a guess at the layout, and a fixture
that reproduces it has to be built first from the measurements the author can
take on the real page: which caption follows the fanciful name, and on which
line. That is a design step, and v1.3.0 is polish on a submission that is
already defensible (SC-5).

**What would change the answer:** a synthetic Registry printout in
`samples/formmaker.py` whose fanciful-name line is followed by the next item's
caption in the real page's order, with a test that fails on the over-run. Then
the lookahead is bounded by the next caption rather than by a line count.

**Who can answer:** the author, with the real printout's caption order.
**Blocks:** nothing; the value is displayed, never compared.

## OQ-32

**Should the item 5 margin move, and on what measurement?**

**Status: Open, filed 2026-09-01 as #123; measured on the synthetic documents
in v1.3.0, not moved.**

**What happened.** `PRODUCT_TYPE_MARGIN` is 12.0 luminance points, and on the
author's own filing at the default render scale the ticked box separated from
the next darkest by 12.1, on the very document the margin was derived from,
while the code comments described a 22 point separation taken by hand from a
looser crop. The comment was corrected in v1.2.1 (#123). The measurement the
decision called for, both documents at three render scales, was taken in
v1.3.0 on the two synthetic stand-ins and is recorded in
[09_DEPLOYMENT.md](09_DEPLOYMENT.md) section 9: the separation swings by about
seven points with the render scale on the text-layer form (27.6 at scale 1.0,
about 20 at 2.0 and 3.0) and the scanned form cannot be sampled at all at scale
1.0, because its captions are too small for the engine to find. The three
scales disagree, so the number does not move.

**What would change the answer:** the same table on the two real documents,
which only the author can take, showing either that the real filing's 12.1 is
stable across scales (then the floor can come down toward the noise, which
measured 0.0 to 2.8 points here and 1.9 on her filing) or that it swings the way
the synthetic form does (then the fix is not the floor but the window
`_checkbox_of` samples, which is what the seven-point swing implicates).

**Who can answer:** the author, with the real documents; measurement.
**Blocks:** nothing. Where the separation falls short the agent chooses, which
is FR-1's direction of error.

## OQ-33

**Should the clean single-label result be made to fit one screen at 1280 by
800, and how?**

**Status: Open, filed 2026-09-02 as #128; the test corrected in v1.3.0, the
panel not changed.**

**What happened.** NFR-4 carries the author's target that a clean result fits
one screen at 1280 by 800 without scrolling, and `frontend/tests/a11y.spec.ts`
held it. The test measured where the panel's footnote ended relative to the
viewport, which depends on how far the page has scrolled, and the page had
scrolled for two reasons unrelated to the panel: a photograph uploaded on its
own opened the gap boxes and moved focus into the first (a smooth scroll), and
the test runner scrolls the check button into view before pressing it. Fixing
#118 took the focus move away for that case, the page stopped scrolling, and
the test went red on a panel exactly as tall as before. Measured in document
coordinates, heading to footnote, the panel is about 1655 px at 1280 wide:
five cards of about 202 px each, the photo notes, the summary line and the
heading. The 412 px recorded against #74 was a viewport-relative figure taken
after the same scrolling. The test now measures the panel itself and is
annotated as an expected failure with the figure, so the run is green while the
panel is known not to fit and red the day it does.

**Options.** A denser card (the "On the label" and "On the application" pair on
one line, the reason folded behind a disclosure); two columns of cards at 1280
and wider; or a different target, one screen for the summary line and the
first card with the rest reachable by scrolling. Each is a layout decision with
a NFR-5 cost to check (reflow at 320 wide, reading order, the disclosure's
name), and none is a correctness fix.

**What would change the answer:** the author looking at a clean result on her
own screen and saying which of the three she wants, or that scrolling is fine.

**Who can answer:** the author; taste and a screen.
**Blocks:** nothing. The result is complete, in reading order and readable; it
scrolls.

## OQ-34

**Should the container registry's tags be immutable, when the deploy path tags
by commit alone?**

**Status: Decided and closed 2026-09-02: `MUTABLE`. Immutability was applied
for code review finding 27 inside pull request C (#130) and reverted on the
same branch before v1.3.0 was tagged. The guard against re-pointing a release
tag is the workflow's, not the registry's.**

**What happened.** Finding 27 observed that a manual dispatch of the deploy
workflow with `image_tag=v1.2.0` could push a new image under an existing
release tag. The service would keep running the digest it was given, but the
true release digest, now untagged, would be expired by the repository's
lifecycle rule within a day, and the release artefact would be gone. Pull
request C did both of the things the review suggested: it set
`image_tag_mutability = "IMMUTABLE"` on the repository in
`infra/terraform/ecr.tf`, and it added a preflight step to
`.github/workflows/deploy.yml` that refuses a dispatch tag matching `^v[0-9]`
before anything is built. The first was then checked against the AWS
documentation and reverted; the second stays.

**What immutability would buy.** A registry-side refusal that does not depend
on the workflow: no push, from any client with push rights, can replace the
image under an existing tag. For a release tag that is a stronger property
than a check in one workflow, because it holds against a dispatch of a
different workflow, a push from an operator's machine, and a future edit that
removes the preflight step.

**Why it was reverted.** Once tag immutability is on, ECR returns
`ImageTagAlreadyExistsException` for a push to any tag that already exists in
the repository, and it does so whatever the digest being pushed: an identical
image under an existing tag is refused the same as a different one. The deploy
workflow tags an image from the commit SHA alone, `sha-<short sha>`, with no
check that the tag exists. So re-running the deploy workflow on an unchanged
commit, which is the documented and habitual way this project redeploys and is
what the runbook step for every release says to do, fails at the push step.
Before the reversal the runbook told the operator to give a re-run an explicit
tag instead; that is a working step that turns every re-run into a manual one
and defeats the point of re-running. On a stack whose posture is deploy, demo,
destroy, registry-wide immutability protects an artefact that is deleted with
the stack, and it traded away the ability to re-run a deploy in the week before
submission. That is the same trade recorded for TLS and for the CIDR
restriction (decision 5, `CODE_REVIEW_DECISIONS_2026-09.md`): the working
deliverable is not broken to buy a partial mitigation. The workflow-side
refusal is the control that addresses the substance of the finding, and the
`docs/06` control row, the traceability matrix, the CHANGELOG and the runbook
now say that the registry itself does not prevent a re-point. `terraform`
treats `image_tag_mutability` as an in-place update, so the change was safe to
apply and is safe to reverse; nothing is recreated and the images stay.

**What would change the answer.** Any one of three, each of which removes the
collision between immutability and a re-run:

1. **A deploy path that tags uniquely per run**, for instance
   `sha-<short sha>-<run number>`, so that no two runs ever push the same tag.
   Cheap in the workflow, but every re-run then leaves a new tagged image for
   the lifecycle rule to count, and a release tag would still have to be
   exempt from the suffix.
2. **A skip-if-exists guard**: before the build, one
   `aws ecr describe-images --repository-name <repo> --image-ids imageTag=<tag>`
   call, and a conditional on the build-and-push step that, when the tag is
   already present, reuses the digest of the image already in the registry and
   goes straight to the service update. This is the cheapest of the three,
   roughly one CLI call plus a condition on one step, and it makes a re-run on
   the same commit exactly what it should be: a redeploy of the image that
   commit already produced. It was not built because it is not needed for a
   demo stack; it is the first thing to build if immutability is wanted back.
3. **ECR's `IMMUTABLE_WITH_EXCLUSION`** mutability setting, with the moving
   tags (`sha-*`, or whatever the dispatch path pushes) excluded by filter and
   the release tags left immutable. That keeps the registry-side property for
   exactly the tags finding 27 was about and lets the commit-tagged re-runs
   through; it needs a provider version that carries the setting and the
   exclusion filter block.

**Who can answer:** the author, if the stack outlives the evaluation window;
until then the decision above stands.
**Blocks:** nothing. Re-running the deploy on the same commit works, and a
release-shaped dispatch tag is refused before a build.

---

## OQ-35

**Should the task come down from 8192 MiB to 2048 MiB, keeping 1 vCPU?**

**Status: Open. Measured 2026-09-02; the recommendation is recorded here and
the Terraform is deliberately unchanged in v1.4.0.**

**What was measured.** Section 9 of [09_DEPLOYMENT.md](09_DEPLOYMENT.md)
records the CloudWatch figures for `AWS/ECS`, cluster and service
`ttb-verifier`, over 2026-08-28 00:00 to 2026-08-29 00:00 UTC at a 60-second
period, the day the 300-label batch and every single-label gate of that
release were run:

| Measure | Percent | Of 8192 MiB |
| --- | --- | --- |
| `MemoryUtilization` peak (`TIME_SERIES(MAX(m1))`) | 1.7 % | 139.3 MiB |
| `MemoryUtilization` mean (`TIME_SERIES(AVG(m1))`) | 0.699 % | 57.3 MiB |
| `CPUUtilization` peak | 99.8 % | one vCPU saturated |

The task is over-provisioned on memory by about 59 times. The 1-minute
datapoints behind those figures expire around 2026-09-12, so the percentages
are the durable record; a query after that date sees only coarser aggregates.

**The recommendation: `task_memory = 2048`, `task_cpu = 1024` unchanged.**

*Why 2048 and not less.* Fargate accepts only 2 GB through 8 GB of memory at
1 vCPU, so 2048 MiB is the platform floor at this CPU size, not a number
chosen to fit the peak. At 2048 MiB the observed peak becomes 6.8 percent, which
is still generous: the two estimates in section 4.3 that were waiting on this
measurement, 400 MiB for the per-image working set and 150 MiB for the stack,
are together larger than the whole measured peak.

*Why the vCPU stays.* 99.8 percent of one core during OCR is
`OMP_THREAD_LIMIT=1` working as designed (section 4.4): Tesseract runs on one
thread and uses all of it. CPU is the real constraint on this task, and cutting
it, which Fargate only allows by going to 0.5 or 0.25 vCPU, would slow every
check and put NFR-1's five seconds, already at the line on the document path
(OQ-26), out of reach. The saving is on memory alone.

**Why it is not applied here.** The infrastructure was applied for v1.3.0 and
is what the deployed prototype runs on; a sizing change belongs in its own
reviewed change, for two reasons beyond process. First, section 4's arithmetic
has to be redone with it: the memory budget in 4.3 puts the batch payload at
3 000 MiB because `TTB_MAX_BATCH_BYTES` is set to that, and a 2048 MiB task
cannot hold it, so the cap comes down with the task, to what 2048 MiB holds
after the stack and the working set, and section 4.4 and the task definition
change together (ADR 0019: apply then deploy). Second, the window measured did
not exercise that payload row at all: the 300-label run carried the
twelve-label synthetic set copied 25 times, an envelope of tens of megabytes,
so the 139 MiB peak is evidence about the stack and the per-image working set
and not about a batch at the byte cap. Both belong in the change that moves
the number.

**Who can answer:** the author, in the next infrastructure change.
**Blocks:** nothing. The task runs; at section 5's list price for Fargate memory
the six unused gigabytes cost about $0.027 an hour, about $19 a month if the
stack were left running.

---

## OQ-36

**Three subjects in the deploy role's OIDC trust policy can never match. What
are they, and what is the fix?**

**Status: Open. Found 2026-09-02 during the v1.3.0 apply; inert rather than
dangerous; the fix is one deletion in the next infrastructure change.**

**What they are.** `local.github_oidc_subjects` in
`infra/terraform/locals.tf` is built from two prefixes, and the applied
`aws_iam_role.deploy` trust policy (`iam.tf`, the `StringLike` condition on
`token.actions.githubusercontent.com:sub`) therefore carries six patterns.
Three are the classic form and match the deploy workflow's two triggers:

```
repo:kimkight/26-DO-12891471-DH_T_ITS_AI_THT:ref:refs/heads/develop
repo:kimkight/26-DO-12891471-DH_T_ITS_AI_THT:ref:refs/heads/main
repo:kimkight/26-DO-12891471-DH_T_ITS_AI_THT:ref:refs/tags/v*
```

Three are of the shape

```
repo:kimkight@*/26-DO-12891471-DH_T_ITS_AI_THT@*:ref:...
```

**Why they cannot match.** GitHub's OIDC `sub` claim contains no `@`. The
claim is `repo:<owner>/<repo>:<context>`, where the context is a ref, an
environment, or `pull_request`; the owner and repository IDs GitHub also
issues travel in their own claims (`repository_id`, `repository_owner_id`)
and never inside `sub`. A `StringLike` pattern with `@` in it is compared
against a string that never contains one, so the three patterns match
nothing. They admit no extra caller, which is why this is inert: the three
classic entries are the ones every successful deploy has assumed the role
through.

**What the repository says about them, which has to be corrected in the same
change.** The comment above `github_oidc_sub_prefixes` in `locals.tf` records
the second prefix as the fix for a first deploy that STS denied, and quotes a
CloudTrail subject in the `@` form as the reason. That account and the
observation above cannot both be right: either the recorded subject was
misread, or the denial had another cause and was resolved by something else
in the same change. Before the deletion, read the CloudTrail
`AssumeRoleWithWebIdentity` record for one successful deploy and confirm which
of the six patterns it matched; the expectation is one of the three classic
ones. Then delete the second prefix from `github_oidc_sub_prefixes`, which
removes all three dead patterns from the `StringLike` list, and rewrite the
comment to say what was actually observed. Dead conditions in a trust policy
invite exactly the question a reviewer asked here, and a comment that explains
them wrongly is worse than none.

**Who can answer:** the author, with the CloudTrail record, in the next
infrastructure change alongside OQ-35.
**Blocks:** nothing. The deploy works through the three live subjects.

---

## OQ-37

**Classifying an image on arrival is an OCR pass, and the check makes it
again. Should the batch tab pay it twice?**

**Status: Closed 2026-09-03, v1.5.0. The batch tab no longer sorts an image on
arrival; it labels it provisionally and the batch line sorts it. The option
was chosen by measurement, below, and the numbers are in section 9 of
[09_DEPLOYMENT.md](09_DEPLOYMENT.md).**

**What was measured.** The batch tab classifies every file on arrival with the
single-label tab's `POST /api/classify`, one request per file, two in flight
(ADR 0020). For twenty filed PDFs that is 0.46 s in total: the header decides
the side and the artwork is not read (ADR 0017). For twenty label PNGs it is
23 s on a one-worker task, about 2.3 s a call, because an image has no text
layer and deciding whether it is a form or a label is the same OCR pass the
check makes. The two are in different requests, so the check then reads each
image again, another 25 s for twenty. The single-label tab pays the same
double read for one photograph and it was never noticeable; at twenty it is.

**Why nothing is done about it here.** The obvious fix, keeping the classify
read on the server for the check to reuse, is a server-side cache of parsed
uploads, and NFR-6 forbids it: nothing uploaded is kept past the request it
arrived in. The check is available from the first file, so the chips never
block a batch; what is lost is the agent's time watching "Reading..." settle
two files at a time.

**The options, each with its cost.**

1. **A cheaper classification for images.** Read a downscaled copy, or the
   top of the image only, looking for the form's own markers rather than the
   whole text. Cheap to build; its accuracy against real photographs of forms
   is unmeasured, and a wrong side is the failure ADR 0011 exists to make
   visible rather than silent.
2. **Classify images from the extension on arrival and let the check
   correct it.** Free, and it puts a guess in the chip, which is the thing
   ADR 0011 removed; the chip would say "label image" for a scanned form
   until the check said otherwise.
3. **Classify the batch's images in one request instead of twenty**, so the
   HTTP overhead goes and the server reads them in its pool. Saves little on
   a one-worker task, where the reads serialize anyway.
4. **Accept it.** The measured case is twenty photographs; an importer's
   drop is filed applications, for which the chips settle in under a second.

**Who can answer:** the author, from how the batch tab is actually used: if
drops are applications, option 4 costs nothing; if they are photographs,
option 1 is the one to measure.
**Blocks:** nothing.

**Measured and decided, 2026-09-03.** Three ways to make the arrival sort
cheaper were on the table, since a cache is not: read a heavily downscaled
copy, decide from metadata alone, or defer the decision to the check and say
so in the chip. The first was measured before it was chosen against. On a
session container, the twelve sample labels and two synthetic photographed
forms (the paper form and a Registry printout rendered as PNGs by
`samples/formmaker.py`) were each read once at five scales, and the read's
verdict compared with what the file is:

| Long edge | Label read, median | Twenty labels | Labels sorted right | Form read, median | Forms sorted right |
| --- | --- | --- | --- | --- | --- |
| 1600 px (the default) | 1784 ms | 21.2 s | 12 of 12 | 1860 ms | 2 of 2 |
| 1000 px | 1247 ms | 15.0 s | 12 of 12 | 2103 ms | 1 of 2 |
| 800 px | 1551 ms | 18.5 s | 12 of 12 | 1634 ms | 2 of 2 |
| 600 px | 1335 ms | 15.7 s | 12 of 12 | 1110 ms | 1 of 2 |
| 400 px | 550 ms | 7.3 s | 12 of 12 | 427 ms | 0 of 2 |

Downscaling does not buy a proportional saving, and the reason is in the
pipeline rather than in the engine: a read whose first arm comes back under
the short-circuit confidence runs the other arms too, so a smaller image is
read more times, and the cost lands between 70 and 85 percent of a full read
until the scale is low enough that the form's own markers stop being
recognized. At 400 pixels the read is a third of the cost and sorts both
photographed forms as labels, which is the wrong side, silently, on the chip.
The point of sorting on arrival was that the chip is the file's own evidence
(ADR 0011); a chip that is right for labels and wrong for forms is a guess
that looks like evidence.

**The decision is to defer.** An image dropped on the batch tab is not sent
to `POST /api/classify`. It is shown with the chip "Label image, sorted when
checked" and a line saying why, the batch runs on it exactly as before, and
the batch line, which carries what the server took each file in the row to
be, replaces the chip with the server's sorting. A PDF is still sorted on
arrival, because that costs about fifty milliseconds and reads no picture
(0.57 s for twenty on the same container, 56 ms a call). So twenty label
photographs cost nothing before the batch starts, where they cost 23 s on the
2026-09-02 container and 36.55 s on the 2026-09-03 one; a photographed form is
still sorted correctly, a moment later than it was; and the check reads every
image once, as it always did. The single-label
tab is unchanged: one image's arrival read is what fills the five boxes from a
photographed form, and one read was never the problem. Metadata alone was not
taken because it is the same provisional answer with the word "provisional"
left off. `frontend/src/__tests__/batchTable.test.tsx` asserts that no
classify call is made for an image and that the line's sorting replaces the
chip, including the case of a photographed form the server sorts to the other
side.

## OQ-38
**Should "alcohol content not found" be a finding on a malt beverage or a
table wine at all?**

**Status: Open. Named and cited 2026-09-06; the checking logic is unchanged.**

The alcohol content presence check (FR-14, FR-15, ADR 0013, ADR 0018) reports
a label that carries no alcohol statement as a finding, citing 27 CFR
5.63(a)(3) for spirits and 4.32(b)(3) for wine. Two things the regulation says
are not accounted for in that design:

- **27 CFR 7.65(a)**: on a malt beverage, alcohol content "may be stated on any
  malt beverage label, unless prohibited by State law". It is optional unless
  State law requires it. The row's copy already narrows 7.63(a)(3) to malt
  beverages with alcohol from added nonbeverage ingredients; the general case
  is that a beer label need not state it.
- **27 CFR 4.36(a)**: for a wine of 14 percent alcohol or less, the alcohol
  content "may be stated, but need not be stated if the type designation
  'table' wine (or 'light' wine) appears on the brand label".

So on a beer, or on a table wine, "not found" can be the correct reading of a
fully compliant label, and a row that reports it as a finding is wrong about
that label. The check is calibrated to distilled spirits, which is what the
assignment's worked examples are and what both real filings are.

**What was done instead of changing the logic.** The row's reason now names
the 4.36(a) allowance beside the 7.63(a)(3) one, so an agent reading the
finding sees when it is not a defect; the limit is recorded in
[09_DEPLOYMENT.md](09_DEPLOYMENT.md) section 9 with the citations; and the
tests, FR-14 and FR-15 are untouched. Changing the check touches two
requirements, it needs the beverage type (ADR 0016) to be trusted as the input
that decides whether absence is a finding, and for wine it needs the class or
type designation read for the words "table" or "light", none of which belongs
in the session that found it.

**What would answer it:** a decision on whether the presence check consults
the beverage type, and if so what it reports when the type is not determined;
and for wine, whether "table" or "light" in the class or type designation
stands in for the figure.

**Who can answer:** Jenny Park or Sarah Chen, on whether an agent expects the
tool to raise absence on a beer or a table wine, and on which they see more of.
**Blocks:** nothing in the prototype. It bounds the claim the presence check
makes: on distilled spirits it is a finding; on a malt beverage or a table wine
it is a question for the agent, and the row says so.

## OQ-39
**How should a single line of legible type set over full-colour artwork be
isolated before it is read?**

**Status: Open. Measured 2026-09-06; not tuned for.**

The bourbon filing committed as evidence in `samples/real/` carries its alcohol
content and its net contents on one line of light type about 24 pixels tall
along the bottom edge of a 1950 by 862 panel that is otherwise a painting. On
the session's Tesseract 5.3.4 the whole panel reads as no text at all through
every arm of the pipeline; the container's 5.3.0 read it at 45.3 confidence
and found neither value. Every page segmentation mode Tesseract offers was
tried on the whole panel, on the colour image, the 1600-pixel grayscale and
the native grayscale, and the best recovered the percentage figure alone.
Cropped to its own text band, the same line reads at 88.0 confidence,
complete, and every rule downstream accepts it: the matcher, the proof
cross-check, the net contents unit.

So the type is legible and the pipeline reads it; what fails is the layout
analysis, which does not find one line of text on a picture. That is a
different limit from the low-contrast labels recorded in
[09_DEPLOYMENT.md](09_DEPLOYMENT.md) section 9 alongside it, where the type
itself is the problem and tuning is declined. Here the fix would be text-region
detection before OCR: finding the bands of a panel that carry type and reading
those on their own. It is real image-processing work, it would run only on a
panel that read poorly, and it is not attempted in this session; the crop
measurement is recorded so that whoever attempts it knows the line reads once
it is found.

**What would answer it:** a region detector measured on this panel and on the
twelve synthetic labels, showing the line found here and nothing lost there,
with its cost.

**Added 2026-09-08 (ADR 0025, ADR 0026).** Three things settled while the
bourbon's reads were being cut, none of which closes this. The line carries
the class or type as well as the two values: it reads `KENTUCKY STRAIGHT
BOURBON WHISKEY 45.2% ALC/VOL (90.4 PROOF) 1L`, so on a Tesseract that reads
nothing off the panel the bourbon returns one of five, and that is what the
session container returns; the two of five recorded for the deployed 5.3.0
build is the same document on an engine that read the panel at 45.3. The
187 by 1697 strip, which the synthetic fixture and the session brief took to
carry the two values, carries none: two script signatures set along it, a
logo and a placeholder serial number. And the panel now costs two reads
rather than four, the orientation call and the plain arm both being reads
that could not have found the line either; what would find it is unchanged
from the paragraph above.

**Who can answer:** measurement.
**Blocks:** nothing in the prototype. On this filing the class or type, the
alcohol content and the net contents are reported not found, and the
deployment notes say why.

---

## OQ-40
**The area floor rejects real label panels. What separates a label panel from
a logo or a signature, if not absolute area?**

**Status: Open. Found 2026-09-08 on a third real filing; not fixed.**

A third real filed COLA, with no text layer and not committed to this
repository, was put through the deployed v1.5.0 build. It carries
twenty-three embedded pictures and every one was rejected, all twenty-three
on `area`. Two of them are label panels: **580 by 293** (169,940 pixels) and
**772 by 189** (145,908 pixels), both under the 250,000-pixel floor.
`label_artwork_available` came back false, no artwork was read at all, and a
document-only check is refused with `no_label_to_check`.

**This is the defect class #140 addressed, one rule further in.** #140
removed the short-edge and aspect-ratio rules because they rejected five of
the six pictures on the bourbon filing, and kept the area floor because area
was what separated that filing's panels (the smallest 317,339 pixels) from
the author's signature (133,965 pixels) with margin on both sides. On this
third filing the area floor is the rule rejecting real labels, and the
margin has closed from the other side: a 772 by 189 panel here sits at
almost exactly the size of the 772 by 194 picture the bourbon filing carries
and the floor was set to exclude.

**The floor's purpose is to skip logos and signatures, and these are
neither.** A floor on absolute pixels answers "is this picture big" and the
question is "is this picture a label". Small artwork is ordinary: a neck
band, a back strip, a miniature's front. Two other shapes of the same test
are on the table, neither measured: a floor relative to the page (a
signature is a fixed fraction of a form; a label panel is not a fixed
fraction of anything) and a rank rule (read the largest pictures, since the
signature is never the largest, and let the read budget of ADR 0023 bound
the cost). Both would have admitted these two panels; what neither has been
measured against is a filing whose signature is scanned large, which is the
case the floor was set for. The lever that exists today is
`TTB_MIN_ARTWORK_PIXELS`, and lowering it to 140,000 would admit both
panels here and the bourbon's 772 by 194 picture and, on the author's
filing, still exclude the 133,965-pixel signature by about 6,000 pixels,
which is no margin at all.

**What would answer it:** the sizes of every label panel and every signature
across more real filings than three, with each picture labelled by a person,
so that the rule is set from a distribution rather than from whichever
document was measured last. The three measured so far are in the deployment
notes and in this entry: the two committed filings by page and size in
`samples/real/README.md`, and this one by the two sizes above, which is all
of it that enters the repository.

**Who can answer:** measurement on more filings.
**Blocks:** nothing in the prototype. On this filing no label side exists,
the check refuses with a message that says so, and an agent supplies a
photograph.

---

## OQ-41
**On a scanned form the OCR path captures the wrong text for the brand name
and the class or type. How should a value be separated from the caption
beside it and the instruction after it?**

**Status: Open. Found 2026-09-08 on the third real filing; not fixed.**

Shapes, not strings: nothing read from that document enters the repository.
The same filing as OQ-40, read through the `ocr` path because it has no
text layer, came back with the **brand name filled with the form's own field
caption**, the printed words that label the box rather than what is written
in it, and the **class or type running past its own value into the
instruction printed for the following item**. Both are confident readings,
and both would produce a confident mismatch against a correct application:
a brand that is the words "brand name" matches no label, and a class or type
with a sentence of form instruction appended matches none either. That is
worse than reporting nothing, because a mismatch tells the agent the label
is wrong when the reading is.

**Why the synthetic scan does not show it.** The paper-form fixture prints
each caption and its value on one line, `CAPTION: value`, and
`app/parse.py`'s caption rules were written and tested against that shape.
On the real form the caption sits in its own box above the value, the value
is set in a different face, and the next item's caption and instruction
follow within the same column, so a line-based reader that takes "the text
after the caption" takes the caption's own remainder on one line and reads
on into the next item on another. The rules are right for the fixture and
the fixture is not the form.

**What a fix looks like, and why it is not done here.** Reading the scanned
form by layout rather than by line: a value is the text inside the box the
caption names, bounded by the box, not the text that follows the caption
until the next caption is recognised. That is the same class of work OQ-39
names for the artwork, region detection before recognition, and it needs a
fixture that renders the form's boxes as the form prints them. Until then the
value arrives on the result, where the agent sees it beside the label's and
retypes it (FR-11's precedence), which costs a second check; ADR 0024 records
that cost.

**What would answer it:** a scanned-form fixture with boxed captions and
values in the form's own layout, showing the current reader capturing the
caption and a layout reader capturing the value, with per-field results on
the twelve synthetic filings unchanged.

**Who can answer:** measurement.
**Blocks:** nothing in the prototype. A wrong value from a scan is visible on
the result with its source named, and a typed value wins.

---

## OQ-42
**Item 5's twelve-point margin has now failed on a third document, in a third
way. What should the margin be set from?**

**Status: Open. The number is not moved.**

On the third real filing (OQ-40, OQ-41) the darkest of item 5's three boxes
measured **10.4 luminance points** darker than the next darkest, inside the
12-point margin `PRODUCT_TYPE_MARGIN` requires, so no beverage type was
determined and the agent chooses. The margin was calibrated on one document:
the author's own mezcal filing, whose ticked box cleared it by **0.1**, 12.1
against 12.0.

**Three documents, three different ways the single-document calibration has
failed.** The document it was set from clears it by a tenth of a point, so
the floor sits at the edge of its own evidence. The synthetic forms
`samples/formmaker.py` builds swing about seven points with the render scale
alone, 27.6 at scale 1.0 against about 20 at 2.0 and 3.0 on the same drawn
tick, so a reading a few points either side of the line is a property of the
render as much as of the ink (OQ-32). And now a real ticked box on a real
filing sits 1.6 points under it and is read as nothing. One calibration
document cannot say which of those three the next filing will be.

**The number is not moved, and this is why.** Lowering it to 10 would admit
this filing and, by the swing OQ-32 measured, would admit an empty box on a
form rendered at a scale that happens to darken it; the empty-box noise
measured 0.0 to 2.8 on the synthetic forms and 1.9 on the author's, which
says a floor of 10 is probably safe and says nothing about a floor of 10 on
the fourth document. Raising it would fail the calibration document itself.
A margin set from one document has been wrong three ways; setting it from a
second document, this one, is the same mistake with a different number.

**What would answer it:** the separation the module's own window reports,
on real filings with the ticked box known, enough of them that the ticked and
empty distributions can be seen and the margin set between them with a
stated error rate. The author's half of OQ-32, the table on the two real
documents at three scales, is the first four rows of that.

**Who can answer:** measurement on more filings.
**Blocks:** nothing. Where the margin is not cleared the beverage type is
not determined and the agent chooses it; it is never compared.
