# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- More than one photograph of one label on the single-label path, following
[ADR 0007](docs/adr/0007-multi-photo-single-label.md) and implementing US-22
(#61). `POST /api/verify` accepts one to three `image` parts. A label wraps a
round bottle, so no single photograph shows all of it flat, and 27 CFR 16.21
allows the government warning on "a back or side label", so the required
elements need not be on one face at all.

Each photograph is decoded, turned upright and read independently, and the
fields found across all of them are merged. A field counts as found if any
photograph shows it, and where two photographs both show one, each field is
decided by the signal that located it: alcohol content and net contents by
per-field OCR confidence, the brand name and the class or type designation by
type size, so the small print on a back label cannot outscore the brand name on
a front one. The warning is decided by the length of the located statement,
because a statement running off the edge of the frame is read confidently and
is simply incomplete. Ties go to the earlier photograph.

One photograph behaves exactly as it did, on the wire and in the result. Image
stitching was rejected: it needs feature matching on frames that may not
overlap at all, and its failure mode is silent distortion that reads as altered
label wording, which is indistinguishable from a genuine compliance defect.
- `photos` on the verification response, one entry per submitted photograph with
its orientation, its confidence, and its error if it had one, and `source_photo`
on every field result. A photograph that cannot be read no longer fails the
submission while another one did read, which is FR-8's rule applied inside one
label; it is reported as a failed entry instead. Only when no photograph could
be read does the request fail, with its own code `all_photos_unreadable`
(FR-9). The top-level `orientation` field added earlier in this cycle is
replaced by the per-photograph one rather than duplicated.
- `TTB_MAX_LABEL_PHOTOS`, defaulting to 3. More than the cap is refused before
any photograph is processed, with the limit named (NFR-7). The single-label
request envelope is now that many times `TTB_MAX_UPLOAD_BYTES`, which loosens
the Content-Length guard from 10 MB to 30 MB on the defaults; each photograph is
still checked exactly against `TTB_MAX_UPLOAD_BYTES` after parsing, and the
loosening is recorded in the middleware's own docstring.
- Per-field OCR confidence and type size on `ParsedFields`, which is what makes
"the reading from the photograph that read it best" a measurement rather than a
guess.
- An "Add another photo of this label" control on the single-label tab, up to
three, each added slot removable, every control keyboard reachable, and each
change announced through its own live region. The cap is enforced by
withdrawing the control rather than by letting an agent reach the API's refusal
(NFR-4). Removing a slot returns focus to the add control, because the button
that removed it goes with it and focus would otherwise fall to the document
body.
- A per-photograph note in the results: what was turned and by how much, and
which photographs could not be read. Nothing is rendered for the ordinary case
of one upright photograph that read without trouble. Each field card says which
photograph its value was read from, and only when more than one was sent.
- Assumption A-16, recording the cap of three and the fact that the API cannot
tell whether the photographs are of the same label. What is done about the
second is disclosure rather than a check: deciding two photographs are "the
same label" from their text is the judgement the tool defers to an agent
everywhere else.
- US-22 and issue
[#61](https://github.com/kimkight/26-DO-12891471-DH_T_ITS_AI_THT/issues/61).
The number breaks the US-n to #n pattern because GitHub draws issue and pull
request numbers from one sequence; the break is noted in the story.
- UAT rows 26 to 29, and the measured cost of reading more than one photograph:
1.24 s, 2.49 s and 3.83 s end to end for one, two and three photographs on a
session runner, against NFR-1's roughly 5 seconds. The three-photograph figure
is printed by `test_multi_photo.py` and deliberately not gated: about a second
of margin is too thin to gate on, and section 7 of the test strategy already
applies that rule to the performance tier.
- 22 backend tests in `backend/tests/test_multi_photo.py` and 20 frontend tests
in `frontend/src/__tests__/multiPhoto.test.tsx`, plus two accessibility tests.
The suites are 187 backend and 81 frontend.

### Changed

- **The batch path stays at one photograph per row.** ADR 0007 does not extend
to it this session: the A-14 CSV keys application data on one image filename, so
a row covering several photographs would need a different column shape, a
reconciliation rule for a partly matched group, and an answer for what a per-row
error means when one photograph of three failed. None of that is difficult and
none is asked for by any source. It is stated in the FR-8 notes and in ADR 0007,
and asserted in `test_multi_photo.py::TestTheBatchPathIsUnaffected` so it cannot
change unnoticed.

- Orientation correction on the extraction path, after the first photograph of a
real bottle returned none of its five fields. `app/ocr.py` decodes through
Pillow so the EXIF orientation tag a phone writes is applied before OpenCV sees
a pixel, then asks Tesseract's orientation and script detection which cardinal
quarter-turn brings the text upright, turns it, and runs the existing
small-angle deskew after that rather than before. What was applied, by what
method and at what confidence is carried out to the response as `orientation`,
so an agent can be told the photograph was turned. `TTB_CORRECT_ORIENTATION`
turns it off. `tesseract-ocr-osd` is added to the container image and to CI,
because the orientation model is a separate Debian package.
- The measurement behind that choice, in `docs/07_TEST_STRATEGY.md` section 2
and assumption A-15. Over the twelve-label sample set at all four cardinal
rotations, forty-eight cases: Tesseract OSD was right in 46, and picking the
rotation with the highest mean word confidence was right in 7. The second is
not a tuning problem. Tesseract's layout analysis already corrects text turned
a quarter-turn clockwise, so the upright image and the clockwise-turned image
produce identical output, 62 words at a mean confidence of 95.4 either way, and
a score equal on the two cases it must separate cannot separate them.
`test_ocr.py::TestWhyOrientationUsesOsd` asserts that equality so the claim
cannot go stale.
- Rejoining of words split across a line break by a printer's hyphen, before the
government warning body is compared. The same real label sets the statement in a
narrow column and hyphenates to fill it, reading `AC-` / `CORDING`, `GEN-` /
`ERAL` and `CONSUMP-` / `TION`. 27 CFR 16.21 fixes the wording, not the line
breaks. Applied to the label side only, after the `GOVERNMENT WARNING:` prefix
has been taken off, so the FR-6 capitalization check reads exactly the
characters it read before. The same join is applied to the stopping rule in
`app/parse.py` that decides how many lines the statement occupies, which
otherwise truncated a hyphenated column.
- Assumption A-15, recording both rules, the measurement that chose OSD, and
what is deliberately not attempted: perspective and cylinder dewarping. That is
recorded against SG-1 in `docs/02_PROJECT_SCOPE.md` and against the accepted
risk in ADR 0003 rather than attempted on a sample of one photograph.
- OQ-20, whether a warning body set entirely in capital letters matches
27 CFR 16.21. The comparison is left case sensitive, which is what FR-5 as
written requires; nothing was changed on the strength of the question.
- OQ-21, how often real photographed labels need cylinder dewarping and how much
accuracy is lost without it. It needs measurement over real artwork, which the
repository does not hold.
- UAT rows 23, 24 and 25 in `docs/07_TEST_STRATEGY.md` section 6: a sideways
photograph, a photograph turned only by its EXIF tag, and a hyphenated warning
column.
- 39 backend tests for the above, taking the suite to 165.
`samples/labelmaker.py` now honours explicit line breaks in the warning rather
than reflowing it, and `samples/warning_text.py` derives the hyphenated column
from the regulation constant so the fixture cannot drift from it.

- `frontend/package-lock.json`, and two Python lock files:
`backend/requirements.lock` (the ocr and matching extras, 27 packages) and
`backend/requirements-dev.lock` (the same plus the dev extra, 61 packages).
Both Python files are generated with
`pip-compile --allow-unsafe --strip-extras --generate-hashes` on Python 3.11
and both audit clean. The split keeps `pytest`, `ruff`, `pip-audit` and
`httpx` out of the container image, which installs the runtime file only.
All three were generated outside a session, because the session egress policy
still denies PyPI and npm (OQ-15).
- A "Regenerating lock files" section in `CONTRIBUTING.md` with the exact
regeneration commands and the rule that `backend/pyproject.toml` keeps
minimum-version floors while the lock file is regenerated and never
hand-edited.
- OQ-18, recording that the session git proxy rejects pushes to `refs/tags/*`
with HTTP 403 while accepting pushes to `refs/heads/*`, and that tags and
releases are therefore created through the GitHub Releases web interface.
v0.1.0 was created that way, tagged at `79d5ac7` on `main`.
- A header on `docs/cloud_choice_and_abv_assumption.md` marking it as the source
record for ADR 0001, A-12, and A-13, and as not maintained going forward.
- ADR 0006, recording the batch execution model: one synchronous multipart
request carrying up to `TTB_MAX_BATCH_FILES` images plus one CSV of
application data keyed by image filename, processed concurrently by a bounded
worker pool, with per-label results streamed as newline-delimited JSON and no
job store, consistent with D-9. Implements FR-8 and NFR-2. (#39)
- Assumption A-14, stating the batch CSV contract: one CSV keyed by image
filename with the columns `filename`, `brand_name`, `class_type`,
`alcohol_content`, `net_contents` and `beverage_type`. FR-8 requires batch
submission "with their application data" and no source states the format.
(#39)
- `docs/DEPENDENCY_TRIAGE_2026-08.md`, triaging the twelve Dependabot pull
requests from the first run against `develop`: six recommended merge, one
merge with a caveat, four close, one hold, with the reason for each and a
full diagnosis of why the TypeScript 7 bump could not resolve a dependency
tree. (#40)
- `.github/dependabot.yml`, setting the update policy that follows from that
triage: minor and patch updates grouped into one pull request per ecosystem
per week, major bumps left ungrouped so each keeps its own pull request and
recorded decision, and major bumps of `typescript` and `react` ignored. (#40)
- The single-label verification engine: `POST /api/verify`, implementing FR-1
through FR-7 and FR-9 for one label, and US-1 through US-7 at the API level.
Six new modules under `backend/app/`, each naming the requirement it exists
to satisfy in its own docstring, mapped in `docs/05_ARCHITECTURE.md` section
5.1. There is no user interface for it; FR-10, NFR-4 and NFR-5 remain unbuilt.
- The 27 CFR 16.21 statement as a constant in `backend/app/warning.py`, compared
exactly after whitespace normalization, with the `GOVERNMENT WARNING:` prefix
carrying a separate capitalization check. Every warning result states that
bold type was not checked (FR-5, FR-6, OOS-4).
- 101 backend tests across the unit and integration tiers, covering every UAT
row in `docs/07_TEST_STRATEGY.md` section 6 that does not need a user
interface or batch processing.
- The sample set: `samples/specs.py` describes twelve synthetic labels across
spirits, wine and malt beverage, carrying a title-case warning, altered
warning wording, an absent warning, a wrong ABV, missing net contents, an
inconsistent proof statement, cross-unit net contents, one rotated image and
one low-contrast image. `samples/generate_samples.py` renders them and writes
`samples/expected.csv` and `samples/applications/applications.csv`. Images
stay git-ignored; the script and both CSVs are committed.
- `scripts/measure.py`, which runs the engine over the sample set and prints
per-field precision, recall, review rate, false match rate and latency as
Markdown. It writes nothing into `docs/`: a number belongs in a document once
it has been measured on hardware the document describes.
- `TTB_ALLOWED_MIME_TYPES` and `TTB_OCR_LONG_EDGE_PX`, both mirrored in
`.env.example` alongside `TTB_ABV_TOLERANCE`, which the settings class had not
previously read.
- Batch verification: `POST /api/verify-batch`, implementing FR-8 and NFR-2 and
following ADR 0006. One synchronous multipart request carries up to
`TTB_MAX_BATCH_FILES` images plus one CSV of application data keyed by image
filename in the A-14 column contract. Images are read by a bounded worker
pool sized from the cores the process may use, and per-label results stream
back as newline-delimited JSON, one object per line, each naming the image it
belongs to and carrying its position and the batch total so a client can
render progress. There is no job store; the stream is the only copy of the
results (D-9, NFR-6). A batch over the file limit is refused before anything
is processed, with the limit named. One unreadable image, one disallowed
type, one oversize file, a CSV row matching no image, an image matching no
CSV row, and a duplicated CSV filename are each that row's error on its own
line, leaving the rest of the batch to return (US-9, US-10, US-11).
- `backend/app/verify.py`, holding the single-image pipeline both routes run, so
that a batch result cannot drift from what a single result means. `app/api.py`
keeps `build_result` as a re-export; `scripts/measure.py` imports it from the
new module.
- `backend/app/batch.py`, holding the A-14 CSV parser, the reconciliation of
images against rows, the worker pool and the NDJSON writer.
- `TTB_BATCH_WORKERS` and `TTB_MAX_BATCH_BYTES`, both defaulting to 0 meaning
"derive it" rather than "unlimited": the pool size from the cores the process
may use, and the batch envelope limit as
`TTB_MAX_BATCH_FILES * TTB_MAX_UPLOAD_BYTES`. Documented in `.env.example`
and `docs/05_ARCHITECTURE.md`, with the memory consequence recorded against
OQ-13 item 6.
- 22 batch tests in `backend/tests/test_batch.py`, including a batch of three
with one corrupt image, a batch over the cap, a CSV referencing a missing
file, and a full run of the twelve-label generated sample set asserting that
every row returns. The suite is 126 tests.
- The agent-facing interface, implementing FR-10, NFR-4 and NFR-5. One screen,
two tabs, plain React with no new runtime dependency beyond `react` and
`react-dom`.

The first tab is the primary task and is open on load, so verifying one label
needs no navigation (NFR-4). Left: a large drop zone and the five labelled
inputs, with one "Check this label" button. Right: five result cards, each
showing the field name, the value found on the label, the value from the
application, the outcome as text and shape and colour, and the API's reason
string. Needs-review cards are visually distinct from both match and
mismatch by tint and edge weight as well as hue. The government warning card
reports the prefix capitalization in its own labelled section and repeats the
bold-type note verbatim (FR-6, OOS-4). Total time is shown as the round trip
the agent waited for, with the server's own elapsed figure as the detail.

The second tab is batch: a multi-file picker, a CSV picker, a progress
indicator driven by the NDJSON stream rather than by an animation, a sortable
results table with a status chip per row, summary counts, and a "Download
results CSV" button that builds the file in the browser because D-9 leaves no
server-side copy to download.

FR-9 errors render as plain language ("We couldn't read this label. Try a
clearer photo.") with the API's own message kept underneath as the detail.
- Accessibility work against NFR-5: every input has a programmatically
associated label, every control is keyboard reachable with a visible focus
ring, results are announced through a polite live region that is in the DOM
before the results exist, the tab strip follows the ARIA tabs pattern with
arrow-key navigation, and a skip link is the first thing in the tab order.
- `axe-core` as a dev dependency and an automated accessibility test that runs
it in Chromium against the built page, in CI. It covers the landing page, the
batch tab, and a rendered result set including a needs-review card. A
keyboard walk and a focus-visibility assertion run alongside it, because axe
cannot check whether a control can actually be operated.
- `frontend/src/__tests__/contrast.test.ts`, computing WCAG 2.1 contrast ratios
from the tokens in `index.css` and asserting 4.5:1 for every foreground on
every surface it can appear on, including pairs no component happens to
combine today.
- 61 frontend component tests covering outcome rendering as text and shape and
colour, the live region, the timing line, the plain-language error path, the
batch table's sorting and status chips, and the results CSV.
- `vitest`, `@testing-library/react`, `jsdom` and `@playwright/test` as dev
dependencies, and `npm run test` and `npm run test:a11y`. The npm lock file
is regenerated in the same change, per the standing rule in
`CONTRIBUTING.md`.

- Terraform for the AWS deployment, in `infra/terraform/`, implementing NFR-9
and the NFR-10 groundwork (US-17, US-19). ECR with scan-on-push and a
lifecycle policy; an ECS cluster, task definition and Fargate service with the
deployment circuit breaker and rollback on; an internet-facing Application
Load Balancer with a target group health-checking `GET /api/health`; a
CloudWatch log group with explicit retention; a VPC with public subnets in two
availability zones; a task role with no policy attached, a task execution
role, a GitHub OIDC identity provider, and a deploy role whose trust policy
names this repository and whose permissions name the one ECR repository and
the one ECS service. Only services on the AWS FedRAMP services-in-scope list,
per ADR 0001 and ADR 0002. **Nothing has been applied to an AWS account**; no
session in this project has ever held AWS credentials.
- `infra/terraform/terraform.tfvars.example`, committed, alongside a
`.gitignore` that keeps `terraform.tfvars`, `terraform.tfstate*` and `*.tfplan`
out of the repository. No AWS account identifier, ARN containing one, or
credential is committed anywhere; account-specific values reach GitHub Actions
as repository variables.
- An `infrastructure format and validate` job in `.github/workflows/ci.yml`,
running `terraform fmt -check -recursive` and `terraform validate` over
`infra/terraform/`. `terraform init -backend=false` is what lets validate run
with no credentials: it resolves the provider plugins and skips the state
backend, which is the only step that would authenticate. Added to the
aggregating `ci` check.
- `docs/09_DEPLOYMENT.md` rewritten as the author's runbook: the exact
commands, where every variable value comes from, the task sizing arithmetic,
an itemized cost estimate, the post-deploy verification steps, a first
measurements checklist, and teardown.
- A post-deploy verification step that cannot be skipped: run a real batch
through the load balancer and read the timestamps on the arriving NDJSON
lines. `X-Accel-Buffering: no` is a hint to intermediaries and not a
guarantee, and whether the stream survives an ALB unbuffered has never been
verified. If it does not, NFR-2 is unmet while every test still passes.
- A "first measurements" checklist in `docs/09_DEPLOYMENT.md` section 9.
No figure in this repository was measured on a deployed target, and the
README's performance claims do not change until that checklist has been run.
- Section 3.1 of `docs/06_SECURITY_AND_COMPLIANCE.md`, recording the
internet-facing prototype with no authentication and plain HTTP as an explicit
acceptance rather than a default: what bounds it (nothing is stored, NFR-6,
and the task's IAM role has no policy), what the residual risks are (open use
of compute, unencrypted transit, no attribution), and the production fix in
order (ACM certificate and HTTPS listener, an auth layer at the edge, then WAF
and rate limiting, then access logs and an audit trail).

### Changed

- OQ-15 closed. The preflight it named as its own closing condition returned
`200` from PyPI and from the npm registry in a new session, with Tesseract
5.3.4 present, so the lock files generated outside a session under OQ-3 are now
verified to install and the OCR tier runs locally. Two caveats are recorded
rather than dropped: the session Tesseract is 5.3.4 while the container ships
the 5.3.0 Debian bookworm builds, and sessions still have no Docker daemon.
- The README's "could not reach PyPI, npm, or the Ubuntu package archive"
limitation removed, along with the question counts it stated, which were stale.

- CI installs Tesseract, its English language data and a TrueType font in the
backend job. Without them the integration tier skipped itself rather than
failing, which would have left the OCR path untested while CI stayed green.
- CI lints and format-checks `samples/` and `scripts/` with the same ruff
configuration as `backend/`, so no corner of the repository holds Python that
CI never reads.
- The multipart spool threshold is raised to `TTB_MAX_UPLOAD_BYTES`. Starlette's
default rolls any part over 1 MB onto a temporary file on disk, which NFR-6
forbids outright.
- The upload size check moved from a route dependency into middleware. NFR-7
requires it "before the body is read into memory", and FastAPI parses the
multipart body while resolving the endpoint's parameters, so a dependency
cannot satisfy that wording.
- `eslint` and `@eslint/js` raised to 10 together, with `frontend/package-lock.json`
regenerated in the same commit. This is the evidence
`docs/DEPENDENCY_TRIAGE_2026-08.md` said did not exist: `npm ci` resolves with
no ERESOLVE, `eslint .` is clean, prettier is clean, `tsc -b && vite build`
succeeds and `npm audit` finds nothing. `frontend/eslint.config.js` needed no
change. The recommendation is to close #42 and #44, each of which is half of
this upgrade, in its favour. The lock entry being replaced carried an upstream
deprecation notice, so `develop` was pinned to an unsupported eslint.
- OQ-19 recorded: the session's GitHub tooling rewrites bot mentions before
posting, inserting `U+00B7` middle dots into the mention and the command word,
so `@dependabot rebase` cannot be issued from a session. #43 is therefore still
un-rebased and still `package.json` only. The three ways around it were
considered and rejected in the triage document; the command stays a manual step
for the repository owner.
- `*.tsbuildinfo` added to `.gitignore`. `tsc -b` writes it next to each tsconfig
it builds, and it showed up untracked after every frontend build.

- OQ-3 closed. Builds now install from the committed lock files rather than
resolving afresh. The `backend lint and test` job installs
`pip install --require-hashes -r requirements-dev.lock` followed by
`pip install --no-deps -e .`, and the frontend with `npm ci`. The
`dependency audit` job audits both Python lock files in two independently
gating steps rather than scanning an installed environment. The Dockerfile
uses `npm ci` and `pip install --require-hashes -r requirements.lock`, the
runtime file only, so every artifact in the image is verified against the
digest recorded at resolution time and no test tooling ships in it. The
comments marking the switch as pending are removed, and the "No frontend
lockfile" limitation is removed from the README.
- `CONTRIBUTING.md` states the rule that any pull request changing
`frontend/package.json` or `backend/pyproject.toml` regenerates the affected
lock file in the same pull request, because `npm ci` and `--require-hashes`
reject a stale lock rather than working around it.
- OQ-15 re-checked from a new session on 2026-08-22 and left open. PyPI and npm
still return `403 host_not_allowed`, and Tesseract and a Docker daemon are
still absent, so the recorded environment fix has not taken effect for
sessions.
- OQ-12 closed. Branch protection rules were declared on `main` and `develop` on
2026-08-21: pull request required, the `ci` status check required, approvals
not required, force pushes and deletions blocked. GitHub shows them as "Not
enforced" because the repository is private on a Free plan.
- OQ-14 closed. The Project board "TTB Label Verifier" exists at
<https://github.com/users/kimkight/projects/1>, a user-owned project linked to
this repository, with issues #1 to #21 in Backlog.
- OQ-17 closed. `develop` is now the repository's default branch.
- OQ-15 updated with the root cause of the package-manager denials: the cloud
environment was at the Custom network level without the default package
manager list included, so PyPI, npm, and the apt archives were denied with
`host_not_allowed` even though they appear in `no_proxy`. Being in `no_proxy`
is not an allowlist entry. The environment fix is recorded; the question stays
open until a preflight from a new session confirms it.
- `docs/08_SDLC_PROCESS.md` section 7 now states that tags are created through
GitHub Releases from `main` rather than pushed from a session, and why.
- OQ-2 closed. Tesseract 5.3.0 is the version shipped in the container image,
read from `tesseract --version` against the built image in CI run 32574942848
at commit `ef3086a` and recorded in the version table in
`docs/05_ARCHITECTURE.md` section 8. It was not assumed: the initializing
session could not install Tesseract, so CI is the authoritative source. 5.3.0
is the LSTM-era line, which is what the extraction path is written against.
(#38)
- OQ-6 and OQ-16 closed by ADR 0006 and assumption A-14. (#39)
- `react-dom` added to the npm major-version ignore list alongside `react`. The
triage named `typescript` and `react` only, but `react` and `react-dom` ship
as a matched pair and `react-dom` declares a peer dependency on the exact
`react` version, so a `react-dom` major proposed on its own could never be
merged alone. This closes the gap `docs/DEPENDENCY_TRIAGE_2026-08.md` recorded
as left open.
- `vite` and `@vitejs/plugin-react` added to the npm major-version ignore list
as a coupled pair. The repository has now hit the same deadlock from both
sides: #28 (`vite` 6 to 8) failed CI at `npm install` with ERESOLVE because
`@vitejs/plugin-react@4.7.0` declares `peer vite "^4.2.0 || ^5.0.0 || ^6.0.0
|| ^7.0.0"`, and #41 (`@vitejs/plugin-react` 4 to 6) was closed because plugin
6 requires a Vite major. Neither half is mergeable alone, so either half
proposed on its own can only produce a pull request that gets closed. Removing
both entries together is what reopens the upgrade.
- `docs/DEPENDENCY_TRIAGE_2026-08.md` triages the second Dependabot run: #43
(`typescript` 5.9.3) recommended merge, green and within
`typescript-eslint`'s `>=4.8.4 <6.1.0` peer window; #42 (`eslint` 10.8.1) and
#44 (`@eslint/js` 10.0.1) recommended for merge only as a single combined
change, since `@eslint/js` 10 alone fails `npm install` with ERESOLVE against
`eslint` 9 while every plugin in the tree already declares an `eslint` 10 peer
range. No ignore entries were added for that pair, because the failure is
explained by the split rather than by incompatibility.
- `docs/DEPENDENCY_TRIAGE_2026-08.md` adds a "lock file interaction" section:
from now on a merged bump that changes only a manifest leaves `develop` red,
because `npm ci` and `--require-hashes` both reject a stale lock. Dependabot
carries the npm lock change on branches cut after the lock file exists; #42,
#43 and #44 predate it and need a rebase or a follow-up regeneration, and pip
bumps always need a manual regeneration.
- `docs/DEPENDENCY_TRIAGE_2026-08.md` records what happened after the first
triage was acted on, and states the condition for closing #27
(`aws-actions/configure-aws-credentials` 4 to 6): it stays open until
`deploy.yml` is enabled. Nothing is wrong with the bump, so closing it would
discard a valid update and invite Dependabot to reopen it weekly, and ignoring
it would hide a credential-handling action from updates entirely. It is held
open until a workflow exists that can actually exercise it.
- `.github/dependabot.yml` now ignores runtime-line bumps of the `python` and
`node` Docker base images. #25 and #26 had already been closed for splitting
the tested runtime from the shipped one, and #47 reintroduced the same
`python` 3.11 to 3.14 bump inside a grouped "minor-and-patch" pull request.
Docker tags are not semver: Dependabot reads `node:22` to `node:26` as a
semver major but `python:3.11` to `python:3.14` as a semver minor, so `python`
is ignored for both major and minor and `node` for major only. Patch updates
are still proposed for both, so security rebuilds inside the pinned line
still arrive. Recorded in `docs/DEPENDENCY_TRIAGE_2026-08.md`.

- `.github/workflows/deploy.yml` enabled. Every job's `if: false` is removed;
the workflow runs on `workflow_dispatch` and on a published release, so no
pull request and no push to `develop` can start it and CI still needs no AWS
credentials. It builds the image, pushes it to ECR under a tag, and deploys
the **digest** that push returned rather than the tag, because a tag can be
moved by the next push and a service referencing one would silently change
what it runs. A preflight job fails with a readable list of every unset
repository variable rather than letting the run half-finish. The task
definition is read from the running service instead of from a committed JSON
file, which keeps the execution role ARN, and with it the AWS account number,
out of the repository.
- `aws-actions/configure-aws-credentials` adopted at v6, directly from v4,
which is what Dependabot PR #27 was held for since the 2026-08-22 triage. #27
is superseded and recommended for closing; it has not been closed from this
session. Recorded in `docs/DEPENDENCY_TRIAGE_2026-08.md`. The bump has still
never authenticated against anything, and the first run of the deploy workflow
is what confirms it.
- OQ-13 closed, item by item, with the author's decisions: her own AWS account;
a minimize cost posture where `terraform destroy` is the resting state; an
internet-facing load balancer with no authentication over plain HTTP; and
`us-east-1` commercial per ADR 0001. Item 6, ECS task sizing, is answered as
it asked to be, by sizing the task first and then setting the caps to what
that memory holds: 1 vCPU and 8 GiB, `TTB_MAX_BATCH_BYTES` at 3 145 728 000
bytes (3 000 MiB), `TTB_MAX_BATCH_FILES` at 300, and the memory budget shown
in `docs/09_DEPLOYMENT.md` section 4.3.
- `TTB_BATCH_WORKERS` pinned to 1 in the task definition rather than left to
the application's derivation. `backend/app/config.py` sizes the worker pool
from `os.sched_getaffinity`, which reports a cpuset; Fargate enforces task CPU
as a CFS quota instead, so the affinity mask can report more cores than the
task may use and a derived pool would oversubscribe a quota it cannot see.
- The ALB idle timeout set to 3600 seconds against a worst case of about 1620:
300 labels at NFR-1's roughly 5-second per-label budget is 1500 seconds, plus
about 120 to receive and parse a full-size multipart envelope before the first
NDJSON line is written. A batch is one response held open for the whole run,
and a connection closed mid-batch loses the batch, because ADR 0006 has no job
store and no resume.
- `OMP_THREAD_LIMIT` documented as deliberately absent from the ECS task
definition, in a comment beside the environment block, in `infra/README.md`,
in `docs/05_ARCHITECTURE.md` section 7, and in the OQ-13 closure.
`backend/app/ocr.py` pins it with `os.environ.setdefault`, so a value set in
the task definition would win, and any value other than 1 reinstates the
Tesseract OpenMP deadlock that hangs the batch path with no error at all.
- Traceability matrix rows for NFR-9 and NFR-10 moved off "no infrastructure
code exists" and onto the Terraform paths. NFR-10 stays honest: portability is
argued from how the configuration is written, not demonstrated, because no
apply has been run in any region.
- `docs/05_ARCHITECTURE.md` section 2's container diagram no longer claims TLS
termination at the load balancer, section 7 records the deployed batch caps,
section 9 says partition independence is a property of the code and not a
demonstrated one, and section 10 records that the infrastructure exists as
code and has never been applied.
- Four rows of `docs/06_SECURITY_AND_COMPLIANCE.md` corrected where deployment
made them false. "Data in transit: TLS terminated at the Application Load
Balancer" was wrong once the listener became plain HTTP. "No rate limiting or
WAF: not exposed to the public workload" was wrong once the load balancer
became internet-facing. The batch threat row said there was no total-bytes cap
when `TTB_MAX_BATCH_BYTES` has been enforced from `Content-Length` since #53,
and the input-validation control row still said the upload endpoints did not
exist.
- `infra/README.md` rewritten from a placeholder describing intended contents
into a description of what is there, what is deliberately not, and the two
load-bearing facts (`OMP_THREAD_LIMIT`, and that the memory figure is the
batch path's).
- The README status table replaced the single "Deployed URL: no AWS
infrastructure exists" row with three: infrastructure as code, the deployment
workflow, and the still-undeployed URL.

### Fixed

- Tesseract could not be called from a worker thread. Its OpenMP runtime
deadlocks when the binary is invoked from any thread other than the process
main thread, so the child process never exits and the request hangs rather
than failing. `POST /api/verify` never met this, being an async handler that
runs OCR on the event loop thread; the batch worker pool does.
`backend/app/ocr.py` now sets `OMP_THREAD_LIMIT=1` if it is unset, which is
also the right shape for the work because the pool already parallelizes
across images. Recorded in ADR 0006.
- Every rejection now leaves the service in one documented shape. A submission
missing a required part previously escaped as FastAPI's own
`{"detail": [...]}` while every other rejection used `ErrorResponse`; a
`RequestValidationError` handler in `backend/app/main.py` maps it, naming the
part at fault without echoing any submitted value (FR-9, NFR-6).
- The upload size and accepted-type limits named in a rejection are now read
when the rejection is built rather than when the module is imported, so a
configured `TTB_MAX_UPLOAD_BYTES` is reflected in both the check and the
message that names it (NFR-7, NFR-11).
- The upload-size middleware matched `/api/verify` by prefix, which would have
measured a batch envelope against the per-image limit and rejected every
batch of more than one file. Matching is now exact, with a limit per route.
- `frontend/*.tsbuildinfo` is git-ignored, and the two files that had been
committed before that rule existed are removed. They are machine-specific
TypeScript incremental build state, regenerated on every build.
- `Dockerfile` and the CI frontend and audit jobs set
`PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD`. `@playwright/test` downloads browser
binaries from its own postinstall script; the image build never opens a
browser, and in CI the explicit `playwright install chromium` step is now the
single place a browser is fetched.
- The `react` and `vite` ignore entries in `.github/dependabot.yml` carried a
reason that has stopped being true: that CI passing on a frontend major would
be evidence of nothing because the frontend was a scaffold. There is now a
real interface with component tests and an accessibility run. The entries
stay, because each upgrade is still a decision wanting its own pull request,
but the recorded reason now says so rather than claiming there is nothing to
test.

## [0.1.0] - 2026-08-22

### Added

- Repository initialization with Git Flow branching: `main` for releases,
`develop` for integration.
- SDLC documentation set under `docs/`: project charter, scope, requirements,
user stories, architecture, security and compliance, test strategy, SDLC
process, and a deployment outline.
- Five architecture decision records covering cloud platform, compute, the text
extraction path, the matching strategy, and branching, plus an ADR template.
- `docs/OPEN_QUESTIONS.md` and `docs/ASSUMPTIONS.md`, recording what is
unanswered and what was inferred rather than stated.
- `docs/TRACEABILITY_MATRIX.md`, mapping stakeholder statements through
requirements and stories to tests and ADRs.
- FastAPI backend scaffold exposing `GET /api/health` only, with configuration
read from environment variables.
- React and TypeScript frontend scaffold built with Vite, served as static files
by the backend container.
- Multi-stage `Dockerfile` running as a non-root user, and `docker-compose.yml`
for local use.
- GitHub Actions CI covering backend lint and tests, frontend lint and build,
dependency audit for both ecosystems, container build with a health probe and
a non-root assertion, and SBOM generation.
- Deployment workflow scaffolded and disabled with an `if: false` guard, because
no AWS infrastructure exists yet.
- Issue templates for user stories, bugs, and tasks; a pull request template
carrying the traceability checklist; `CODEOWNERS`; and Dependabot for pip,
npm, GitHub Actions, and Docker.
- Pre-commit configuration for both ecosystems.
- GitHub Issues for all twenty-one user stories, with epic, priority, and type
labels.
- `docs/cloud_choice_and_abv_assumption.md`, the source document for the cloud
platform rationale and the alcohol content and net contents assumptions.
- Assumption A-12: alcohol content on the label and in the application must be
numerically identical, with normalization, a proof equals 2 x ABV cross-check
per 27 CFR 5.65, and no tolerance band. The tolerances in 27 CFR 5.65, 4.36,
and 7.65 govern actual against labeled content, so none of them applies to two
values the applicant declared.
- Assumption A-13: net contents are compared numerically only when units match
after normalization; different units are reported as needs human review with
no conversion, and standards of fill are not validated.
- `TTB_ABV_TOLERANCE`, defaulting to `0.0`, so the A-12 position can change
without a code change.
- Section "Why not Azure, given the agency runs Azure" in ADR 0001, recording
why the prototype is built on AWS when the agency states it is on Azure, the
public Treasury evidence bearing on it, and the negative consequence that the
Terraform would need an Azure provider module before a pilot.
- Manual UAT rows 18 to 22 covering the A-12 and A-13 rules.

### Changed

- Decision D-11 replaced everywhere it appeared. The previous text asserted that
the agency's intended production environment is AWS GovCloud (US); no source
supports that, and the Marcus Williams interview says Azure. D-11 now records
the agency's stated Azure position, the author's choice of AWS commercial
`us-east-1` for delivery speed, the container-first portable design, and
FedRAMP status confirmed against the FedRAMP Marketplace at deployment time
rather than asserted.
- NFR-10 retitled to "Portability to a FedRAMP-authorized government region
(AWS GovCloud or Azure Government)"; its acceptance criteria are unchanged.
- FR-7 acceptance criteria extended with the A-12 and A-13 rules.
- OQ-1 marked as answered by ADR 0001, as the author's decision rather than a
stakeholder answer. OQ-4 closed by A-12 and OQ-5 closed by A-13.

### Known limitations

- No application logic. Label extraction, comparison, and verification are
designed but not implemented; only the health endpoint exists.
- The build session could not reach PyPI, npm, or the Ubuntu package archive
and had no Docker daemon, so tests, the frontend build, and the container
build were not run locally. All of them run and pass in CI, which is where
the scaffold was actually verified. See `docs/OPEN_QUESTIONS.md`, OQ-15.
- Branch protection is not applied and the default branch is still `main`
rather than `develop`; neither endpoint was reachable from the initializing
session. See OQ-12 and OQ-17.
- No lockfile in either ecosystem, so builds are not yet reproducible.
Backend dependencies use minimum-version floors rather than exact pins,
because hand-written exact pins went stale and `pip-audit` found seven
advisories against the transitive `starlette` version they resolved to.
See OQ-3.
- Container base images are pinned by tag rather than by digest.

[Unreleased]: https://github.com/kimkight/26-DO-12891471-DH_T_ITS_AI_THT/compare/v0.1.0...develop
[0.1.0]: https://github.com/kimkight/26-DO-12891471-DH_T_ITS_AI_THT/releases/tag/v0.1.0
