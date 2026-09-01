# Code review: TTB Label Verifier at v1.2.0

**Reviewed:** `main` at tag `v1.2.0` (`a6279e2`, 2026-09-01). The working tree
reviewed is byte-identical to the tag.
**Author of the code:** Kimberly D. Kight.
**Review date:** 2026-09-01.
**Method:** every claim in the README, `docs/03_REQUIREMENTS.md`,
`docs/TRACEABILITY_MATRIX.md`, `docs/ACCESSIBILITY_CONFORMANCE.md`,
`docs/09_DEPLOYMENT.md`, `docs/06_SECURITY_AND_COMPLIANCE.md`, the ADRs and the
CHANGELOG was read against the code it describes. Every backend module was read
in full; the frontend, Terraform, workflows and container files were read in
full; every test named by the traceability matrix was opened. The suites and
linters were run in this session, and where a behaviour could be exercised
rather than reasoned about, it was exercised (section 5). Nothing in the code
was changed; this document is the only file this branch adds.

The rule for a finding: it has a file and line, a concrete failure scenario with
inputs and the wrong output, and a recommended fix. Anything without a
constructible failure is in section 3 as an observation. Where a finding rests
on reasoning rather than on something run, the finding says so.

---

## 1. Summary for an assessor

**What is solid.** The verification engine is careful, well tested and honest
about its own limits. The orientation logic (`backend/app/ocr.py`) handles
every boundary the review looked for: OSD unavailable, OSD exactly at the floor,
a tie between candidates, and an operator switching the check off; and the
tests in `test_orientation_floor.py` cover each of those with the engine
stubbed rather than coaxed. The panel segmentation is arithmetic on a word
table the one Tesseract pass already returns, it costs no read, and a
single-panel label provably comes out as one column. The government warning
check is exact by requirement, normalises only whitespace and case, routes a
one or two character OCR artifact to a person rather than passing it, and says
on every result that bold type was not checked. The batch path isolates every
failure to its own row, streams progress, bounds its worker pool, and cancels
what has not started when a client drops. Input validation is in the right
order: size from the header before the body is read, media type before decode,
the count before any row is worked. The PDFium lock is complete: every PDFium
call is inside it and Tesseract runs outside it. The container runs as a
non-root user from hash-verified lock files, the deploy role is scoped to one
repository, one ECR repository, one service and two passable roles, and no
credential, account number or load-balancer hostname appears anywhere in the
tree or the history. The documentation is unusually candid, and most of what
this review found is where that candour has fallen behind the code.

**What is weak.** Three things would embarrass the author if a panel found
them first.

1. **The presence check on alcohol content can pass a label that has no
   alcohol content statement at all.** The v1.2.0 search "rescue" takes the
   declared value, searches the label for it as a whole word, and hands a bare
   `12` printed anywhere (`AGED 12 MONTHS IN OAK`) to the numeric comparison,
   which reports "Label 12 percent and application 12 percent are numerically
   equal". This was reproduced in this session against the running API, and it
   undoes both the FR-7 alcohol-marker rule that fixed the `7%` defect of
   2026-08-27 and the FR-15 presence finding. There is no test of the rescue
   path (section 2, finding 1).
2. **Real applicant data is in the repository.** A real Mexican producer tax
   identifier (an RFC) was committed in three commits on 2026-08-31 and taken
   out in a fourth; it is recoverable from the history of `main`. A real
   brand name of a real producer is the default value of a fixture type in
   `samples/labelmaker.py` and appears in about ninety lines across tests,
   code and documentation, while `docs/07_TEST_STRATEGY.md` says none of that
   filing is committed (finding 2).
3. **The build tagged v1.2.0 identifies itself as 1.1.0** at `/api/health`, in
   `pyproject.toml`, in `package.json`, and in the OpenAPI document, because
   the version is declared by hand in three files and the release procedure's
   first step was skipped. Meanwhile the CHANGELOG marks 1.0.0, 1.1.0 and
   1.2.0 as "unreleased until tagged" though all three are tagged, and the
   conformance report says "Version evaluated: v1.2.0" of a build nothing in
   the tree calls 1.2.0 (finding 3).

Below those: the traceability row that cites `TestNothingIsPersisted` for
NFR-6 cites a test that asserts two identical requests give identical outcomes
and nothing about disk, while an oversize upload demonstrably does reach a
temporary file before it is refused; the README, ADR 0003 and NFR-3 describe an
optional Bedrock fallback that does not exist in the code; the interface
silently drops a value the agent typed when a document uploaded afterwards
does not carry that field; the single-label handler runs Tesseract on the
event loop so one slow request stalls the health endpoint the load balancer
relies on; the application's INFO log records are never emitted under uvicorn
while the documentation and one test describe structured logging; a Terraform
change to the task definition cannot reach the service through the documented
deploy path; and the infrastructure README and the deployment runbook still
open with "Nothing here has been applied" under a README that reports
measurements on the deployed target.

**Counts.** 7 high, 13 medium, 12 low findings; 34 observations. Of 78 claims
audited, 39 are true and evidenced, 9 true but not evidenced by the test or
document named, 21 stale, 9 false.

---

## 2. Findings, ranked by severity

Severity is the impact on a reader of the repository or a user of the tool, not
the interest of the bug.

### High

#### 1. The alcohol-content rescue search produces a false pass on a label with no alcohol statement

**Where.** `backend/app/verify.py:932-944` (the rescue loop over
`RESCUED_FIELDS`), `backend/app/search.py:194-204` (`_exact`, whole-word
containment scores 100), `backend/app/compare.py:171,213` (`_ABV_BARE` accepts
a bare number).

**What is wrong.** FR-7 requires an alcohol-content reading to carry an alcohol
marker on its line (`parse.py:93-99`, the fix for the `7%` defect). When the
pattern finds nothing, v1.2.0 searches the label for the *declared* value and,
at or above the match threshold, installs the hit as the label side. The
declared value is normalised to a bare number (`12`, `12%` both become `12`),
one word matches any `12` on the sheet with a score of 100, and `compare_abv`
then parses the bare `12` as 12 percent and reports a match. The presence
finding that would have said "Alcohol content was not found on the label" never
runs, because `label_values["alcohol_content"]` is no longer `None`.

**Failure scenario, run in this session.** A label rendered with the sample
renderer whose alcohol line reads `AGED 12 MONTHS IN OAK` and which prints no
alcohol content anywhere, submitted to `POST /api/verify` with the application
declaring `12` (and again with `12%`):

```
alcohol_content: outcome=match label='12' app='12' score=100.0
  reason: Label 12 percent and application 12 percent are numerically equal.
```

With the application silent on the field, the same label correctly returns
`mismatch` with "Alcohol content was not found on the label". A wine whose
label omits the mandatory statement and mentions the age of the wine, the
number of months in oak, a vintage fragment or a lot number containing the
same digits passes 27 CFR 4.32(b)(3) on this tool. Net contents is safe by
accident: its parser requires a unit, so a bare `750` does not parse and the
row falls to review.

**Why it matters.** This is the one class of error the design forbids: an error
path returning a match (FR-9's last criterion) and a guess dressed as a reading
(FR-1). It is also the exact shape of the 2026-08-27 defect, reintroduced by
the release that fixed the brand-name defect.

**Fix.** Require the rescued hit to satisfy the same marker rule the pattern
does: search only the units whose line passes `is_alcohol_content_line`, or
require the declared value to carry a marker before it is searched for, or
drop alcohol content from `RESCUED_FIELDS` and keep the rescue for net contents,
where the unit is a marker. Add the test above to `test_verify_by_search.py`;
today no test exercises the rescue (a grep for "rescue" in `backend/tests`
finds only docstrings about other things).

#### 2. Real applicant data: a producer's tax identifier in history, a real brand as a fixture default

**Where.** Commits `1138714`, `244cde2`, `6cef94a` (all 2026-08-31),
`backend/app/ocr.py:258`; removed in `d8225b1` ("take the applicant's tax
identifier back out"). `samples/labelmaker.py:210-211`;
`backend/tests/test_verify_by_search.py:80,84,114`;
`backend/tests/test_colour_arm.py:69-70`; `backend/app/search.py:23-28`;
`backend/app/parse.py:21-23`; `frontend/src/__tests__/reset.test.tsx:37,104,178`;
`README.md:475,495-496`; `docs/TRACEABILITY_MATRIX.md:57-60`; and about eighty
further lines across `CHANGELOG.md`, the ADRs, `docs/02_PROJECT_SCOPE.md`,
`docs/03_REQUIREMENTS.md`, `docs/05_ARCHITECTURE.md` and `docs/ASSUMPTIONS.md`.

**What is wrong.** Three commits reachable from `main` carry a string in Mexican
RFC format identifying the producer of the author's own filed COLA. The tree at
`v1.2.0` does not, but `git log -p` does, and `docs/07_TEST_STRATEGY.md:612-616`
and `backend/tests/test_panel_segmentation.py:42-44` state that the filing
"carries a real company, a real tax identifier and a real address" and that
"none of it is committed". Separately, the brand name, fanciful name, class
designation, alcohol content and net contents of that real product are the
default field values of `ColourLabelSpec`, are rendered into a test fixture on
every run, are asserted by name in `test_verify_by_search.py`, are typed into
the interface by `reset.test.tsx`, and are named in the README as "the real
COLA for that product". The standing rule (`samples/README.md:38-45`,
`docs/07_TEST_STRATEGY.md` section 8) forbids real application data in any
fixture.

**Failure scenario.** A panel member runs
`git log --all -p -S'RFC:' -- backend/app/ocr.py` and reads the identifier. Or
reads `samples/labelmaker.py:210` and matches the default against the README's
"real COLA for that product". Either way the repository contradicts its own
stated policy on the one axis a Treasury panel is certain to check.

**Fix.** The identifier needs a history rewrite (`git filter-repo` over the
three commits) and a force-push of `main` and `develop`, then a GitHub support
request to purge cached views; a further commit cannot remove it. The brand
name and product values should be replaced by the invented names the rest of
the sample set uses, in the fixture default, the tests and the prose. The
measurements taken on the real filing can stay; they are numbers, not the
filing.

#### 3. The build tagged v1.2.0 says it is 1.1.0

**Where.** `backend/app/__init__.py:3` (`__version__ = "1.1.0"`),
`backend/pyproject.toml:3`, `frontend/package.json:4`,
`frontend/package-lock.json:3,9`; read by `backend/app/main.py:35` (OpenAPI
`version`) and `:114` (`/api/health`). `CHANGELOG.md:10,479,1167` ("unreleased
until tagged" on 1.2.0, 1.1.0 and 1.0.0). `docs/08_SDLC_PROCESS.md` section 7,
step 1 of the release procedure. `docs/ACCESSIBILITY_CONFORMANCE.md:6`.

**Why it did not move.** The version is a literal in three files with nothing
deriving one from another and no check in CI that they agree with each other
or with the tag. The 1.1.0 bump was made inside a feature commit on 2026-08-29
(`dfbc2fc`); the 1.2.0 release (PR #99, tagged 2026-09-01) skipped step 1 of
the repository's own release procedure, and step 2 (date the CHANGELOG section
when the tag is cut) was skipped for every release. `README.md:75` shows the
health response as `"version":"1.1.0"`, which is accurate about the code and
wrong about the tag.

**What derives from the string.** `/api/health` (which the deploy workflow,
the ALB and the container health check all read, so the deployed v1.2.0 build
reports 1.1.0), the OpenAPI document served at `/docs`, and the package
metadata `pip install` records in the image. Nothing in the frontend reads it.
`docs/09_DEPLOYMENT.md` section 9 and the traceability matrix cite "build
1.1.0" for the deploy #12 measurements, which is the same string a v1.2.0
deploy would report, so a future measurement cannot be told from that one by
version alone.

**Failure scenario.** A panel member deploys the tag, runs
`curl /api/health`, sees `1.1.0`, and reads the release procedure that says
step 1 is to bump it.

**Fix.** Derive the version once: `importlib.metadata.version("ttb-label-verifier-backend")`
in `__init__.py` with `pyproject.toml` as the source, and a CI step that fails
when `package.json` disagrees with it or when a `v*` tag does not match. Date
the three CHANGELOG sections.

#### 4. NFR-6's cited test does not test persistence, and an oversize part does reach disk

**Where.** `docs/TRACEABILITY_MATRIX.md` row 19 and the NFR-6 row of section 2
("multipart spool threshold raised so no upload reaches disk", tested by
`TestNothingIsPersisted`); `backend/tests/test_verify_integration.py:151-156`;
`backend/app/api.py:72-87,149-162`; `docs/06_SECURITY_AND_COMPLIANCE.md:23,39`;
`docs/09_DEPLOYMENT.md:140`.

**What is wrong.** `TestNothingIsPersisted.test_two_identical_requests_share_no_state`
posts the same label twice and asserts the two outcome lists are equal. It
passes with the uploads written to disk, logged, or held in a module-level
list; it is a test of determinism. The spool claim the row makes is untested,
and it is not fully true: `api.py:86` raises Starlette's spool threshold to
`max_upload_bytes` (10 MB), so a part under that stays in memory, but a part
over it rolls over to a real temporary file before `check_size` refuses it
after parsing. The `api.py:152-153` docstring says such a submission "is read
into memory and then refused"; it is read to disk and then refused.
`docs/09_DEPLOYMENT.md:140` still says the threshold is 1 MiB.

**Failure scenario, run in this session.** With `tempfile.SpooledTemporaryFile.rollover`
counted:

```
MultiPartParser.spool_max_size = 10485760
  5 MB part  -> HTTP 200 ok;            rollover-to-disk calls: 0
  11 MB part -> HTTP 413 file_too_large; rollover-to-disk calls: 1
```

An 11 MB photograph of a label is written to `/tmp` inside the container, then
refused with the message "Send a smaller image". The file is unlinked when the
request ends, and the task's ephemeral storage is destroyed with the task, so
the exposure is small; the written statements "No image ... is written to
disk" (NFR-6 acceptance criterion 1) and "Nothing is written to disk"
(`docs/06:23`) are nevertheless not true for every request the service
accepts, and the test cited as proof could not have found out.

**Fix.** Either lower the envelope check to refuse any single-part submission
over `max_upload_bytes` from `Content-Length` (impossible to do exactly for
multipart, as the docstring says) or accept the rollover and say so in NFR-6,
`docs/06` and `docs/09`. Replace the cited test with one that monkeypatches
`SpooledTemporaryFile.rollover` (as above) and asserts zero calls for an
in-limit upload, and add `readonlyRootFilesystem` with an explicit ephemeral
`/tmp` to the task definition so the writable surface is stated.

#### 5. The optional Bedrock fallback does not exist

**Where.** `README.md:128-130` ("An optional vision-model fallback on Amazon
Bedrock exists but is off unless explicitly enabled"),
`docs/adr/0003-local-ocr-default-bedrock-optional.md:42-43` (Decision:
"Provide an optional fallback to a vision model on Amazon Bedrock"),
`docs/03_REQUIREMENTS.md:846-849` (NFR-3 acceptance criteria 2 and 3),
`docs/05_ARCHITECTURE.md:535,661`. Code: `backend/app/config.py:33-35` declares
`enable_bedrock_fallback`, `bedrock_region` and `bedrock_model_id`; nothing
reads them. There is no `boto3` in `requirements.lock`, no client, no call
site. `backend/app/verify.py:1072` sets `external_call_made=False` as a
literal.

**Failure scenario.** Set `TTB_ENABLE_BEDROCK_FALLBACK=true` and
`TTB_BEDROCK_MODEL_ID=anthropic.claude-3-haiku` on the task and submit an
unreadable photograph. Nothing changes: the response still says
`external_call_made: false`, no request leaves the container, and the
"visible in the response" criterion of NFR-3 is satisfied only because the
field can never be anything else. `TestEgressBlocked` (cited for NFR-3)
asserts the constant.

**Why it matters.** ADR 0003 is the decision the whole extraction architecture
rests on, and its second clause records a component that was never built. A
reader who trusts the README will believe the tool has a path for the
photographs Jenny Park describes. It does not, and OQ-2 or an ADR amendment
should say so.

**Fix.** Amend ADR 0003 ("the fallback was designed and not built"), reword the
README and NFR-3, and either delete the three settings or make the application
refuse to start when the flag is set and no implementation exists, so the
configuration cannot promise something silently.

#### 6. A value the agent typed is silently dropped when a document uploaded afterwards lacks that field

**Where.** `frontend/src/components/SingleLabelTab.tsx:291-299`
(`fillFromDocument` rebuilds the whole source map from the document, mapping
every not-found field to `'absent'`); `frontend/src/lib/applicationFields.ts:74-80`
(`typedValues` posts only fields whose source is `'typed'`).

**What is wrong.** The source map is replaced rather than merged, so a field the
agent had typed becomes `'absent'` if the document does not carry it. The
value stays in the box on screen (`application[name]` is untouched), the gap
logic treats it as answered (line 318), and the request omits it.

**Failure scenario (reasoned from the code; not run in a browser).** Open "Or
type the application values", type Brand name `GREY HARBOR`, then upload a COLA
whose text layer has no brand name. The screen shows a summary line "Brand
name / GREY HARBOR / Not supplied"; the request carries `brand_name=''`; the
server compares nothing for the brand and the row reads "The application
supplied no value for this field (FR-2)" beside a screen that shows the
agent's value. No test types before uploading a document with a gap.

**Fix.** Merge: keep `'typed'` where `previous[name] === 'typed'` and the box
is non-empty; add a test in `oneUpload.test.tsx` that types first, uploads a
brand-only document, and asserts the posted body carries the typed value.

#### 7. Section 508 conformance claims that the code contradicts, and tests that cannot fail

**Where.** `docs/ACCESSIBILITY_CONFORMANCE.md` rows 4.1.3, 3.2.2, 2.4.4 and
1.4.11; `frontend/src/components/BatchTab.tsx:173,238`;
`frontend/src/components/ApplicationFields.tsx:154-160`;
`frontend/tests/a11y.spec.ts:483,571,595`;
`frontend/src/__tests__/contrast.test.ts:115,135,165,251-254`.

**What is wrong.**

- **4.1.3 (false).** The row says "Four polite `role="status"` regions, each
  labelled apart ... Each is always in the DOM rather than mounted with its
  text." There are five. The two on the batch tab (`BatchTab.tsx:173,238`)
  carry no `aria-label`, and the pairing region at 173 is rendered inside
  `chosen ? ... : null`, so it is created at the same moment as its text, the
  pattern the row says is avoided. The test cited for the criterion,
  `a11y.spec.ts:595`, drops unlabelled regions with `.filter(Boolean)` and
  never opens the batch tab, so it cannot detect either.
- **3.2.2 (false).** The row says choosing a file is "a change of content, not
  of context". `ApplicationFields.tsx:154-160` moves focus to the first gap
  field when a document leaves one, and `a11y.spec.ts:876` asserts that it
  does. Moving focus on input is the change of context 3.2.2 names; the
  behaviour may be defensible, the row is not.
- **2.4.4 (stale).** "Links within the Help tab's prose": `HelpTab.tsx` contains
  no anchor element.
- **1.4.11 (partly unevidenced).** The banner focus ring is checked against
  `--focus` (`contrast.test.ts:115`) while `index.css` draws `--focus-on-dark`
  on `.prototype-banner :focus-visible`, which computes to 1.52:1 on the pale
  banner; nothing in the banner is focusable today, so the rule is dormant and
  the test certifies a ring the stylesheet does not draw. The active pill fill
  is asserted at 1.2:1 (`contrast.test.ts:251-254`), a threshold fitted to the
  measured 1.22, under a comment citing 3:1.
- **4.1.2 (unevidenced).** The chip role check at `a11y.spec.ts:571` asserts
  zero `[data-outcome][role="button"]` on a page where no check has run and
  there are zero `[data-outcome]` elements at all.
- **1.4.12 (unevidenced).** `a11y.spec.ts:483` uses
  `getByText('Does not match').first()`, which resolves to the visually hidden
  live region ahead of the cards in DOM order, so the "still readable" check
  under text-spacing overrides never looks at a chip.
- **1.4.3 (stale claim about derivation).** The row and the CHANGELOG say the
  outcome list is derived from the outcome definitions; `contrast.test.ts:135`
  and `:165` hand-type it twice. A seventh outcome with an unchecked tone
  passes `tsc` and ships.

**Failure scenario.** Delete `aria-label="Check result"` from
`SingleLabelTab.tsx:477`: the status-region test stays green. Change
`OutcomeBadge` to render a `<button>`: the role test stays green. A reviewer
who checks 4.1.3 by opening the batch tab with a screen reader hears two
unnamed regions.

**Fix.** Label the two batch regions and keep the pairing one mounted; rewrite
the four tests to assert the thing they name (every region labelled, chips
present before the role check, a chip locator under text spacing, the ring
token the stylesheet uses per ground); derive the outcome list in
`contrast.test.ts` from `PRESENTATIONS`; correct rows 3.2.2, 2.4.4 and 4.1.3.

### Medium

#### 8. Single-label OCR runs on the event loop and stalls the health endpoint

**Where.** `backend/app/api.py:197` (`async def verify`) and `:297-407`
(`classify`, `parse_application_document`, `verify_photos` called
synchronously inside it); `backend/app/ocr.py:62-67` (the comment says so);
`Dockerfile:85` (one uvicorn worker); `infra/terraform/alb.tf` target group
health check (timeout 5 s, three failures) and `infra/terraform/ecs.tf:120-126`
(container health check, timeout 5 s).

**What is wrong.** Every Tesseract pass on the single-label path blocks the
only event loop, so `/api/health` cannot be answered until the request
finishes. The batch path is fine (a thread pool behind a sync generator).

**Failure scenario, partly run.** In this session a three-photograph
`POST /api/verify` took 3.35 s against a local uvicorn, and a concurrent
`GET /api/health` took 3.34 s to answer. On the deployed target the same
submission measured 7.8 s (`docs/09_DEPLOYMENT.md` section 9), which is over
the 5 s health-check timeout. An unauthenticated client sending one
three-photograph submission every five seconds keeps the loop busy, three
consecutive probes time out, ECS stops the task, and a 300-label batch another
user had in flight is lost with no resume (`batch.py:33-35`). The stall is
measured; the task replacement is reasoned from the health-check settings.

**Fix.** Run the classify, parse and verify calls in `_verify` and
`classify_uploads` through `starlette.concurrency.run_in_threadpool` (the batch
path already runs OCR in threads, so `OMP_THREAD_LIMIT` covers it), or run
uvicorn with two workers. Correct the `ocr.py:62-67` comment, which describes
the loop-blocking as a property that keeps the single path safe.

#### 9. The application's INFO log records are never emitted, and the test that certifies them cannot tell

**Where.** `backend/app/api.py:414,491,632`, `backend/app/batch.py:370`
(`logger.info` with `extra`); `backend/app/config.py:30` (`log_level`, read
nowhere); `Dockerfile:85` (uvicorn with its default logging config);
`backend/tests/test_verify_integration.py:190-227`;
`infra/terraform/logs.tf:8-9` ("the application logs structured events");
`docs/05_ARCHITECTURE.md:68,534`.

**What is wrong.** Nothing configures the root logger. Uvicorn's default config
attaches handlers to its own loggers only, the root logger stays at WARNING,
so every `logger.info` in `app.*` is discarded and `TTB_LOG_LEVEL` does
nothing. The completion-record test passes because `caplog` installs its own
handler at DEBUG.

**Failure scenario, run in this session.** uvicorn started with
`TTB_LOG_LEVEL=INFO`, one verification posted: the process output carries the
access line `"POST /api/verify HTTP/1.1" 200 OK` and no "verification
completed" record. An operator reading CloudWatch for the `ocr_ms` figure the
runbook describes finds access lines only. The `logger.warning` and
`logger.exception` calls do reach stderr, message-only, through Python's
last-resort handler, with the `extra` fields dropped.

**Fix.** Configure logging at startup from `settings.log_level` with a JSON
formatter that renders `extra`, or delete the INFO calls, the setting, and the
`logs.tf` sentence. Make the completion-record test run through the real
configuration rather than `caplog`.

#### 10. A Terraform change to the task definition cannot reach the service through the documented path

**Where.** `.github/workflows/deploy.yml:220-262` (reads the task definition
the service is *running* and re-registers it with the new image);
`infra/terraform/ecs.tf:180-189` (`lifecycle { ignore_changes = [task_definition] }`
with the comment "change a limit or a size here, apply, then run the deploy
workflow to put the new shape into service"); `docs/09_DEPLOYMENT.md:163-165`
and `infra/README.md:70-75` say the same.

**Failure scenario (reasoned).** The CloudWatch memory figure section 9 is
still waiting for shows the batch near 8 GiB. The operator sets
`max_batch_bytes` lower in Terraform and applies: revision N is registered and
the service is left on N-1 by `ignore_changes`. The deploy workflow then reads
N-1 from the service and registers N+1 with the old environment. The new cap
never ships and nothing in the run summary says so.

**Fix.** Read the latest revision of the family
(`aws ecs describe-task-definition --task-definition "$FAMILY"`) rather than the
service's current one, or drop `ignore_changes` and let Terraform deploy by
passing the digest in. Correct the three comments.

#### 11. The OIDC trust admits any branch through the `environment:production` subject, and the image push sits outside the environment gate

**Where.** `infra/terraform/locals.tf:44-51` (four subjects per prefix,
including `:environment:production`); `infra/terraform/iam.tf:107-115`
(`StringLike` over them); `.github/workflows/deploy.yml:198`
(`environment: production` on the deploy job only; the build-and-push job at
104-192 has none); `infra/terraform/ecr.tf:18` (`MUTABLE`);
`docs/06_SECURITY_AND_COMPLIANCE.md:28` ("write access to develop or main is
write access to the deployment").

**What is wrong.** GitHub issues the `environment:production` subject to any
job in any workflow in the repository that declares that environment, from any
branch, unless the environment itself carries a branch policy, which lives in
repository settings this review cannot see. The ECR push and the digest are
produced by a job with no environment, so an environment's required reviewers,
if any, gate `UpdateService` but not the image.

**Failure scenario (reasoned).** A collaborator with push rights to a feature
branch adds a workflow with `on: push`, `permissions: id-token: write`,
`environment: production` and the same credentials step. STS honours the
subject, and the deploy role's `RegisterTaskDefinition` on `*` plus
`UpdateService` on the one service puts that branch's image behind the
evaluation URL with no pull request involved.

**Fix.** Remove the `environment:production` subject and put
`environment: production` on both AWS-touching jobs so the branch-scoped
subjects decide, or keep it and configure the environment with a branch and
tag policy and say in `docs/06` that the GitHub setting is load-bearing.
Tighten `refs/tags/v*` to `refs/tags/v[0-9]*`.

#### 12. Actions pinned by mutable tag in the workflow that holds the deploy role; base images pinned by tag past a deadline five releases old

**Where.** `.github/workflows/deploy.yml:112,119,127,148,152,258,270` (seven
third-party actions at major tags, including the one that receives STS
credentials); `.github/workflows/ci.yml:288` (`anchore/sbom-action@v0`);
`Dockerfile:8-9,33` ("TODO: pin both base images by sha256 digest before the
first tagged release"); `docs/06_SECURITY_AND_COMPLIANCE.md:50-52,69`
("must be closed before the first tagged release ... Acceptable while nothing
is released"). Five tags exist.

**Failure scenario (reasoned).** A retargeted `docker/build-push-action` tag,
in the style of the March 2025 `tj-actions` compromise, runs after
`configure-aws-credentials` has placed a one-hour session in the job's
environment; the payload pushes an image and calls `UpdateService`. Nothing in
this repository changed and review sees nothing. For the base image: the
`python:3.11-slim-bookworm` tag is retagged upstream between the CI build and
the release build, and the image behind the URL has a base the SBOM never
described.

**Fix.** Pin every action by full commit SHA with a version comment
(Dependabot already covers `github-actions` and `docker`); pin both `FROM`
lines by digest; move `id-token: write` from the workflow level to the two jobs
that need it. Update the two documents and the TODO, which the README's
"Known limitations" already contradicts.

#### 13. The SBOM describes an image that is not the one deployed, and nothing consumes it

**Where.** `.github/workflows/ci.yml:237-300` (build with `push: false`, SBOM
generated, uploaded for 30 days, never read); `.github/workflows/deploy.yml:150-164`
(a separate build with `platforms: linux/amd64` and `provenance: false`, no SBOM
step); `docs/06_SECURITY_AND_COMPLIANCE.md:27,42,179` ("SBOM generated for
every image", "Supply chain inventory"); `README.md` CI row.

**Failure scenario (reasoned).** An auditor asks for the SBOM of the digest the
service is running. There is none for that digest; the nearest artifact is for
a different build on a different trigger and expired after thirty days.

**Fix.** Generate the SBOM in `deploy.yml` from the pushed reference, attach it
to the digest (`cosign attest` or `oras attach`) or name the artifact by digest
with long retention, and add a `grype` step that fails on high. Until then say
"an SBOM is generated for the CI build" rather than "for every image".

#### 14. Two documents open with "Nothing here has been applied" under a README that reports measurements on the deployed target

**Where.** `infra/README.md:8-12`; `docs/09_DEPLOYMENT.md:7-14` ("Nothing in
this repository has been applied ... The first measurement of anything on the
deployed target is section 9, and it does not exist yet"), and the same
document's section 9, which records the runs; `docs/09_DEPLOYMENT.md:58-60`
(the provider lock file "is absent from the repository") while
`infra/terraform/.terraform.lock.hcl` is committed; `docs/06_SECURITY_AND_COMPLIANCE.md:40`
(`pip-audit --strict`; `ci.yml:214,217` run without it);
`docs/09_DEPLOYMENT.md:140` (1 MiB spool threshold; the code sets 10 MB);
`infra/terraform/iam.tf:154-158` ("The condition below is what narrows them";
the statement at 159-166 has no condition); `infra/terraform/iam.tf:9-10`
("Pulling the image and creating log streams, nothing else"; the attached
managed policy is account-wide on `*`).

**Failure scenario.** A panel member opens `infra/README.md`, reads the second
paragraph, and then reads the README status table two clicks away that says
"applied to an AWS account in `us-east-1`". One of them is wrong, and the
reader does not know which.

**Fix.** Rewrite the two openings to say what has been applied and when; delete
the lock-file paragraph; either add `--strict` to CI or remove it from the
document; correct the two `iam.tf` comments or add the condition they describe.

#### 15. The traceability matrix's coverage summary and the README's document table count things that are no longer there

**Where.** `docs/TRACEABILITY_MATRIX.md:104-118` ("Requirements defined: 22
(11 functional, 11 non-functional)", "ADRs: 10", "413 backend tests", "252
component tests", "User stories: 24"); `README.md:217-225` ("FR-1 to FR-10",
"24 stories across 6 epics", "21 questions, 8 still open", "16 inferences");
row 31 ("11 tests" in `test_orientation_floor.py`), FR-8 row ("34 tests" in
`test_batch.py`).

**Actual, counted in this session.** 15 functional requirements (FR-1 to FR-15)
and 11 non-functional; 18 ADRs; 526 backend tests collected; 338 component
tests; 30 user stories; 28 open questions; 17 assumptions; 13 tests in
`test_orientation_floor.py`; 36 in `test_batch.py`. The section explicitly says
its two counts "are read off the section 2 table by one rule each, so they can
be checked rather than taken"; checking them is how the drift shows.

**Failure scenario.** An assessor asked to verify "22 of 22 requirements traced"
counts 26 requirement headings and stops trusting the matrix.

**Fix.** Recount, and add a small test (the repository has the pattern in
`test_warning.py::TestTheConstantMatchesTheRegulation`) that parses the two
tables and fails when the headings and the summary disagree.

#### 16. Batch table and batch summary misreport rows whose outcomes are not match, review or mismatch

**Where.** `frontend/src/components/BatchTable.tsx:146-156` (`summarize`
returns "All five fields match." whenever no field is `needs_review` or
`mismatch`); `frontend/src/components/BatchTab.tsx:120-125` (four buckets:
match, review, mismatch, error) and `:236-243` (the live-region sentence built
from them).

**Failure scenario (reasoned from the code).** A batch row whose document omits
the brand name returns fields `[not_compared, match, match, match, match]`. The
row's chip reads "Not compared" (`outcomes.ts`), its detail column reads "All
five fields match.", and the summary counts it in none of the four buckets, so
"0 fully matching, 0 needing review, 0 not matching, 0 could not be checked"
sits beside "1 of 1 labels checked". The same happens for `present` and
`artwork_derived` rows, which v1.2.0 introduced for exactly the document-only
submissions the README highlights.

**Fix.** Tally by outcome in `summarize` ("4 of 5 passed; brand name not
compared") and add a passed bucket (`match` plus `present`) and an
uncompared bucket to the summary; assert in `batchTable.test.tsx` that the
buckets sum to the row count, which its comment already claims.

#### 17. Reset does not cancel an in-flight single-label check

**Where.** `frontend/src/components/SingleLabelTab.tsx:218-231` (`reset` clears
state), `:368-381` (`submit` awaits `verifyLabel` with no `AbortController` and
no generation guard). The batch tab has the abort (`BatchTab.tsx:54-78`).

**Failure scenario (reasoned from the code).** Upload document A, press Check,
press "Clear and start another label" while the server is reading A's artwork
(about five seconds on the deployed target), upload document B. A's response
resolves: five cards and the "Check result" live region announce A's verdicts
under a file list that shows B, and the "The form was cleared" announcement is
overwritten.

**Fix.** Hold an `AbortController` in a ref, abort it in `reset` and at the top
of `submit`, pass its signal into `verifyLabel`, and treat `AbortError` as no
outcome, as `verifyBatch` already does.

#### 18. A file removed before its classification returns is still announced and its values filled in

**Where.** `frontend/src/components/UploadPanel.tsx:105-127` (`send` has no
sequencing; the last response to resolve wins).

**Failure scenario (reasoned from the code).** Add `cola.pdf`; while
`/api/classify` is in flight, click "Remove cola.pdf". `send([])` clears the
form; then the first response lands, `setResult` and `onClassified` fill the
five boxes from a file that is no longer listed, and the uploads region
announces "cola.pdf, read as a label application".

**Fix.** A request counter or per-call `AbortController`; ignore any response
whose file list is not the current one.

#### 19. Choosing a photograph alone opens four boxes, moves focus and gives the wrong advice

**Where.** `frontend/src/components/SingleLabelTab.tsx:257-266`
(`fillFromClassification` treats every untyped field as a gap when the upload
carried no document); `frontend/src/components/ApplicationFields.tsx:154-160`
(focus moves to the first gap and an announcement is made).

**Failure scenario (reasoned from the code).** Upload `label.png` and nothing
else. The screen reports four values "not found in your upload", focus jumps
into Brand name, and the announcement ends "Enter them, or upload a clearer
image". The upload was a photograph; a clearer photograph cannot supply
application values. `applicationFirst.test.tsx:296-316`, named "uploading a
label photograph opens nothing", asserts only the disclosure's `aria-expanded`.

**Fix.** For a photo-only upload leave the fields optional with no focus move;
keep the gap behaviour for a document that leaves gaps, and state in the
drop-zone hint that focus will move (see finding 7, 3.2.2).

#### 20. The service is public, unauthenticated and plain HTTP while it now accepts real filings

**Where.** `infra/terraform/alb.tf:220-229` (one HTTP listener, no 443, no
certificate, no redirect); `infra/terraform/variables.tf:167-180`
(`ingress_cidr_blocks` defaults to `0.0.0.0/0`);
`docs/06_SECURITY_AND_COMPLIANCE.md:25,62,79-82` (acknowledged). The
acknowledgement rests on "handles no sensitive data" (`docs/06:8`), written
before ADR 0008 made a filed TTB F 5100.31, with the applicant's signature
image on page 2, the primary input.

**Failure scenario (reasoned).** An evaluator on shared Wi-Fi posts their own
COLA PDF to the HTTP address. A passive observer on the path captures the
filing, the signature image and the result, and no access log records that it
happened (`alb.tf:183-186`).

**Fix.** An ACM certificate on a subdomain the author controls, a 443 listener,
and a 301 from 80; failing that, narrow `ingress_cidr_blocks`, which the
configuration already supports, and say in `docs/06` and on the banner that
real filings must not be submitted over the evaluation URL.

### Low

#### 21. The client pairing preview does not implement the server's rule

`frontend/src/lib/pairing.ts:30` uses `toLowerCase()`; `backend/app/batch.py:81`
uses `casefold()`; the comment at `pairing.ts:11` says they "must stay
identical", and no test exercises `pairingStem`. **Scenario.** `Straße.png` and
`STRASSE.pdf`: the server pairs them and checks the row; the page says "0
pairs ready to check, 1 image with no matching document, 1 document with no
matching image". **Fix.** The same fold on both sides and a shared vector list.

#### 22. Three server error codes have no plain-language line

`frontend/src/lib/plainLanguage.ts:14-43` lacks `no_label_to_check`
(`api.py:385`), `too_many_application_documents` (`api.py:346`) and `no_files`
(`api.py:322,591`); `batchTable.test.tsx:313-334` calls its list "the contract"
and omits all three. **Scenario.** Upload a COLA PDF with no readable artwork
and no photo: the headline reads "We couldn't check this label. Try again, and
tell your administrator if it keeps happening", and only the detail line names
the missing piece. **Fix.** Add the three lines and derive the test's list from
the backend's codes.

#### 23. Two wall-clock assertions in the backend suite gate CI on runner speed

`backend/tests/test_verify_integration.py:82-111` and `:414-431` assert
`elapsed < 5.0` for a real OCR request. On this session's runner they measured
1.08 s and 1.20 s; on a loaded shared runner a 5 s wall clock is not a
property of the code. **Scenario.** A slow CI runner turns a green pull request
red with no change in behaviour, which the repository's own rule ("a failing
test is never an infra flake") then obliges someone to investigate. **Fix.**
Print the figure (the tests already do) and assert it only under an explicit
opt-in, or raise the ceiling to something a runner cannot miss.

#### 24. The half-resolution orientation check obeys a worthless verdict on a tie of nothing

`backend/app/ocr.py:849-865`: both candidates are scored at half resolution;
when the challenger does not strictly beat the OSD choice, the OSD verdict
stands. A label whose type is too small to read at 800 px scores 0 words and
0.0 confidence both ways, the tie leaves a verdict OSD reported at 0.03
confidence in place, and the full-resolution read that follows is of the wrong
way up. **Scenario (reasoned, not run).** Fine-print-only artwork filed upside
down with OSD answering 0 degrees at 0.03: read upside down. **Fix.** Treat a
tie at zero words as "unavailable" and leave the image as it arrived.

#### 25. The PDFium lock is held over PNG encoding of every embedded image, not only the four that are read

`backend/app/application_form.py:645` encodes a PNG for every image that
passes the size floor before the list is cut to `max_artwork_images` at `:658`;
`_render_at` (`:972-981`) encodes page renders under the same lock. PNG
encoding is Pillow work, not a PDFium call. **Scenario.** A batch of scanned
filings with twenty page-sized images each serialises twenty encodes per
document across the whole pool. On the text-layer documents the runbook
measured, the lock is milliseconds, so the batch figure stands. **Fix.** Copy
the bitmap under the lock and encode outside it; slice to
`max_artwork_images` before encoding.

#### 26. The deploy role and the task can do more than the comments say

`infra/terraform/iam.tf:33-36` attaches `AmazonECSTaskExecutionRolePolicy`,
which is account-wide on `*` (cited from memory of the managed policy; not
fetched); `iam.tf:159-166` grants `RegisterTaskDefinition` and
`DescribeTaskDefinition` on `*` with no condition; `network.tf:137-142` gives
the task unrestricted egress from a public IP (`ecs.tf:145`). **Scenario.** A
decoder exploit in the container (the residual risk `docs/06:21` names) has an
unrestricted reverse path. **Fix.** An inline execution-role policy scoped to
the one repository and log group; egress `tcp/443` only; tag conditions on the
task-definition actions.

#### 27. ECR is mutable and a manual dispatch can overwrite a release tag

`.github/workflows/deploy.yml:38-41,140-141` accept any `image_tag`;
`infra/terraform/ecr.tf:18` is `MUTABLE`; `ecr.tf:40-49` expires untagged
images after one day. **Scenario.** A dispatch with `image_tag=v1.2.0` from
`develop` repoints the tag; the true release digest becomes untagged and is
deleted within a day. The service keeps running the right digest; the release
artefact is gone. **Fix.** `IMMUTABLE`, or reject inputs matching `^v[0-9]`.

#### 28. `.dockerignore` excludes `.env` files at the root only, while the frontend stage copies a whole tree

`.dockerignore:14-15` (`.env`, `.env.*`, not `**/`), `Dockerfile:27`
(`COPY frontend/ ./`). **Scenario.** A developer's `frontend/.env.local` with a
`VITE_*` value enters the build stage and Vite inlines it into the public
bundle. No such file exists today. **Fix.** `**/.env*` in `.dockerignore`;
copy `src`, `index.html` and the config files explicitly.

#### 29. Blanking a document-read value does not remove it from the check

`frontend/src/components/ApplicationFields.tsx:329-330` says "an empty box is
not compared"; `SingleLabelTab.tsx:243-248` marks a cleared field `'absent'`,
`typedValues` sends `''`, and the document is still posted, so the server
re-derives the value. **Scenario.** Clear the brand name the document filled;
the result row still compares `DEL MAGUEY`. **Fix.** Send an explicit override
for cleared document fields, or change the hint.

#### 30. `file_too_large` always says "image"

`frontend/src/lib/plainLanguage.ts:17` against three distinct server messages
at `backend/app/api.py:643-658`. **Scenario.** Four 9 MB files trip the 40 MB
envelope; the headline says "That image is too large. Send a smaller one."
**Fix.** Key the line on the `limit` string.

#### 31. Two files with the same name share one classification chip

`frontend/src/components/UploadPanel.tsx:174` matches classification entries
by filename; `sameFile` at `:85-89` admits two files of one name and different
sizes. **Scenario.** Two `label.png` from two folders both show the first
entry's chip and reason. **Fix.** Match by index; the server returns entries
in submission order.

#### 32. TIFF previews render as broken images

`UploadPanel.tsx:43` accepts `image/tiff`; `:182` previews anything `image/*`;
Chromium and Firefox do not decode TIFF. **Scenario.** Upload `label.tif`: a
broken-image glyph with alt "Preview of label.tif". **Fix.** Preview only the
types browsers decode, and say so for the rest.

---

## 3. Observations (no constructible failure scenario)

**Pipeline and correctness**

1. `backend/app/compare.py:431-433` and `:584-586`: the `_missing` call in
   `compare_abv` and `compare_net_contents` is unreachable. `missing_from_label`
   returns for an empty label value and the presence branch returns for an
   empty application value before it, so its two `NOT_COMPARED` branches are
   reachable only through `compare_text`. Dead code from the ADR 0018 change.
2. `backend/app/api.py:152-153`: "a 25 MB single-photograph submission is read
   into memory and then refused" describes the pre-`spool_max_size` behaviour
   wrongly (finding 4); it is read to disk and then refused.
3. `backend/app/batch.py:122-142`: a document whose stem is empty after
   trimming (a filename of spaces) is dropped silently and reported on no line;
   two documents sharing a stem with no image are reported as one unpaired
   line, because the second is in `duplicates` and not in `documents`.
4. `backend/app/batch.py:214-238`: `_row_error` and the `table.documents[...]`
   lookup run outside the try in `_verify_one_row`; nothing there can raise
   today, but a raise would kill the stream, the outcome NFR-2 forbids.
5. Starlette's default `max_files` of 1000 (`formparsers.py:157`) refuses a
   batch of more than 1000 parts with `malformed_upload` before the route's
   300-count message runs. Rejected either way; the message differs.
6. The 300-file cap is applied after the whole envelope, up to 6 GiB, has been
   parsed. The code's docstring (`api.py:724-727`) is honest that "before any
   file is processed" is the guarantee kept; NFR-7's "before processing" is
   met by that reading and no other. There is no client-side count check, so a
   301-file batch uploads in full before it is refused.
7. `backend/app/ocr.py:1025-1038`: two blank arms (0 words, 0.0 confidence)
   are reported as decided by "confidence"; cosmetic.
8. `backend/app/product_type.py`: on a scanned form the caption OCR runs on the
   raw render; a form whose captions OCR badly returns `NOT_LOCATED` and the
   agent chooses, which is the safe direction. A form with no boxes at all
   returns the same. No defect found in this module; it is one of the cleaner
   ones.
9. Panel segmentation: no defect found. A single-column label has no
   full-height blank and comes back as one column (`test_panel_segmentation.py::TestASinglePanelLabelIsUnaffected`);
   a caption alone in a column is left to the width rule (`_is_gutter` returns
   true with nothing adjacent), which cuts it into its own column harmlessly;
   the type-size condition protects letter-spaced display type. The gap
   threshold scales with image width as claimed.
10. `backend/app/verify.py:1072`: `external_call_made=False` is a literal
    (finding 5).
11. `OMP_THREAD_LIMIT=1` is set by `ocr.py:78` with `setdefault` before
    `pytesseract` is imported, and every OCR call site (`_read`,
    `detect_orientation`, `word_boxes_from_ocr`) is in a module that imports
    `app.ocr` first, so the child process inherits it on every path including
    the batch pool. The constraint is enforced. It is not in the image's `ENV`,
    so `docker inspect` does not show it, and the repository's own explanation
    of *why* it is needed (an OpenMP deadlock off the main thread) describes a
    subprocess boundary as a thread boundary; the effect is right, the story is
    approximate.
12. The PDFium lock: every PDFium call is inside `_read_pdf_with_pdfium` under
    `_PDFIUM_LOCK` and the document is closed inside it; Tesseract reads run
    outside. The batch is not serialised on the measured (text-layer) path.
    Finding 25 is the one place it holds longer than it needs to.
13. `backend/app/timing.py`: the phases are disjoint as claimed; each batch
    row opens its own recording in its worker thread, and `ContextVar` gives
    each thread its own value. Correct.

**Tests**

14. `backend/tests/test_batch.py:484-496` `TestNothingIsPersisted` checks the
    logs, not persistence; a misnamed but useful test.
15. `TestEgressBlocked` (`test_verify_integration.py:228-283`) is a real test
    of the image path with sockets refused; it does not exercise a PDF
    submission, and `external_call_made` is a constant.
16. `backend/tests/test_multi_photo.py` prints one, two and three photograph
    timings and says "Not gated"; good.
17. Fixtures: every backend fixture is rendered by `samples/labelmaker.py` or
    `samples/formmaker.py` at test time; every frontend fixture is built in
    `fixtures.ts`; the a11y spec inlines a one-pixel PNG. No binary file exists
    in the tree or in any commit. The generation rule is kept, apart from the
    real values in finding 2.
18. Weakest tests in the frontend suite, each of which passes with the named
    behaviour removed: `applicationFirst.test.tsx:296-316` (asserts only
    `aria-expanded`), `artworkDerived.test.tsx:116-119` (score is rendered on
    no path), `reset.test.tsx:124-134` (no dialog exists to assert absent),
    `helpTab.test.tsx:252-258` (no links exist), `verifyBySearch.test.tsx:57-59`
    (tests a function nothing in the UI calls), `contrast.test.ts:270-274`
    (stale, names removed viewfinder brackets), `batchTable.test.tsx:217-244`
    (asserts absence of a part name no code ever wrote),
    `warningNearMiss.test.tsx:205-208` (the outcome is passed in by the
    fixture).
19. `batchTable.test.tsx:109-112` says a chunk "deliberately falls
    mid-record"; every chunk is a whole line, so the partial-line buffer in
    `api.ts:197-206` is never exercised.
20. `a11y.spec.ts:922-948` is named "the axe scan covers a result built from
    two photos" and never calls `violations()`; `:258` names "an error notice"
    and no route in the suite returns a non-200. The batch tab is scanned only
    empty: the results table, the progress element, the total row, the
    warning diff and the Stop and CSV buttons are never axe-scanned.
21. `contrast.test.ts:44-49` regexes the raw stylesheet, so a comment above
    `:root` naming a token would be read first; only `.field__source` is
    checked class-to-token, and `#b9c6da` at `index.css:1022` (drop-zone dashed
    border, about 1.6:1) is the one hard-coded colour outside the tokens.
22. `branding.test.tsx:144-150` would miss `import x from './seal.svg?url'`,
    `<img src="/seal.svg">` and a favicon link.
23. `branding.test.tsx:30` and `contrast.test.ts:23` resolve paths from
    `process.cwd()`, so vitest launched from the repository root fails.
24. `helpTab.test.tsx:129-133` runs a full upload-and-check six times through
    `it.each` at the default 1 s `waitFor`; the component suite took 18.8 s
    here and is the first thing a loaded runner would trip.
25. Criteria in the conformance report with no automated backing at all:
    1.3.3, 1.3.4, 1.4.13, 2.1.4, 2.2.2 (reduced motion is not emulated), 2.3.1,
    2.4.5, 2.4.6, 2.5.1, 2.5.2, 2.5.3, 2.5.4, 3.1.2, 3.2.1, 3.2.2, 3.3.4. Backed
    only in jsdom: 3.3.1, 3.3.3. Backed by a proxy: 1.4.4 (the viewport is
    halved; no text is resized). The report's section 5.1 already says no
    screen reader was used, and that statement is honest.

**Code quality**

26. Frontend dead code: `readApplication` and `ApplicationOutcome`
    (`frontend/src/lib/api.ts:32-35,123-147`) are never imported and the file's
    header says "three calls" for four functions; `SingleOutcome.seconds`
    (`api.ts:29,85-93`) is computed and never rendered; `DropZone`'s `preview`
    prop (`DropZone.tsx:29-30,101`) is never passed; `anySearched`
    (`labelSearch.ts:57`) is unused by its own admission.
27. The CSV batch contract is gone from the backend entirely; the client's
    `csv.ts` is the results export and is still used. No superseded server path
    remains.
28. `verify.py` (1161 lines) and `application_form.py` (1541 lines) have grown
    through five sessions; `build_result` is 240 lines with three overlay passes
    (search, presence withdrawal, circularity, declined) applied in sequence.
    It is readable because it is commented, and the comments are current. The
    single and batch paths share `verify_photos` through `verify_image`, so
    the duplication the review looked for is not there; what differs is that
    the single path classifies and the batch path pairs.
29. Comments that describe a behaviour the code no longer has: `api.py:152-153`
    (observation 2), `ocr.py:62-67` (the single path "never hit this" is true
    and is presented as a safety property rather than as the loop-blocking it
    is), `ecs.tf:185-187` (finding 10), `iam.tf:154-158` (finding 14),
    `contrast.test.ts:270-274` (observation 18), `api.ts:2` (observation 26).
30. `docs/09_DEPLOYMENT.md:117-119` derives `TTB_MAX_BATCH_BYTES` as files
    times upload size (3 000 MiB); `config.py:241` is twice that, and the same
    document says so three paragraphs later at 177-178.
31. `docs/09_DEPLOYMENT.md:44-46` says the ECR registry hostname reaches
    GitHub Actions as a repository variable; `outputs.tf` exports the bare
    name and `deploy.yml:156` takes the hostname from `amazon-ecr-login` at run
    time.
32. `infra/terraform/locals.tf:30` quotes the GitHub owner ID and repository
    ID from a CloudTrail record. They are public identifiers, not secrets, and
    the comment explains them; noted because the repository's rule is "no
    account identifiers" and a reader may pause on them.
33. Three personal email addresses appear in commit author metadata (none in
    file content). Authorship, not a finding.
34. `docs/05_ARCHITECTURE.md:661` names the Bedrock fallback as "the one
    portability risk" of a component that does not exist (finding 5).

---

## 4. Claims audit

Verdicts: **E** true and evidenced; **T** true but not evidenced by the test or
document named; **S** stale (true of an earlier build); **F** false.

| # | Claim | Where made | Verdict | Evidence |
| --- | --- | --- | --- | --- |
| 1 | Row 1: FR-1, FR-2 tested by `test_parse.py`, `test_verify_integration.py` | Matrix row 1 | E | Both files exist and exercise extraction and the end-to-end path |
| 2 | Row 3: FR-3 tested by `TestOutcomeClassification` | Matrix row 3 | E | `test_compare.py:37-50`, all four boundaries |
| 3 | Row 5: FR-4 by `TestBrandName` | Matrix row 5 | E | `test_compare.py:53-77` |
| 4 | Row 6, 7, 8: FR-5, FR-6, OOS-4 by `TestWarningBody`, `TestWarningCapitalization`, `TestBoldTypeIsNeverClaimed` | Matrix rows 6-8 | E | `test_warning.py:42-162`; the bold note is asserted on every result |
| 5 | Row 9: FR-7 by `TestAlcoholContentComparison`, `TestNetContents` | Matrix row 9 | E, with a gap | `test_compare.py:102-180`; the rescue that feeds FR-7 has no test (finding 1) |
| 6 | Row 10: FR-9 by `test_api_validation.py` | Matrix row 10 | E | Corrupt, empty, blank, oversize, wrong type, and "no error body carries fields" |
| 7 | Row 12: FR-8 by `TestOverCount`, `TestEveryLineIdentifiesItsLabel`, `TestTheGeneratedSampleSet` | Matrix row 12 | E | `test_batch.py:132-198,497-531` |
| 8 | Row 13: pairing by `TestPairing`, `TestUnusableSubmissions`, `TestThePairingRule` | Matrix row 13 | E | `test_batch.py:100-131,308-404`, including two images on one stem and two under one filename |
| 9 | Row 14: one bad item by `TestOneBadItemDoesNotFailTheBatch` | Matrix row 14 | E | `test_batch.py:199-307`: corrupt image, unreadable document, wrong types, oversize on both sides |
| 10 | Row 15: NFR-2 framing by `TestEveryLineIdentifiesItsLabel` | Matrix row 15 | E | Index and total asserted per line |
| 11 | Row 16, 17: NFR-4/5 by `a11y.spec.ts`, `liveRegion.test.tsx`, `contrast.test.ts` | Matrix rows 16-17 | E, with the gaps of finding 7 | Suites exist and run in CI; see finding 7 for what they miss |
| 12 | Row 18: NFR-3 by `TestEgressBlocked` | Matrix row 18 | E for the image path | `test_verify_integration.py:228-283`; `external_call_made` is a constant |
| 13 | Row 19: NFR-6 by `TestNothingIsPersisted` | Matrix row 19 | **F** (the test does not test it) | `test_verify_integration.py:151-156` asserts determinism; finding 4 |
| 14 | NFR-6 row: "multipart spool threshold raised so no upload reaches disk" | Matrix section 2 | **S** (partly) | True under 10 MB; an oversize part rolls over before refusal (finding 4) |
| 15 | Row 20: `TestNothingSensitiveReachesTheLogs` | Matrix row 20 | E | `test_verify_integration.py:159-227`; the allow-list is real; note the records are never emitted in production (finding 9) |
| 16 | Row 21: NFR-9 "applied to an AWS account ... run 3 green" | Matrix row 21 | T | Not verifiable from the repository; `infra/README.md` says the opposite (finding 14) |
| 17 | Row 28: orientation by `TestExifOrientation`, `TestCardinalOrientation`, `TestWhyOrientationUsesOsd` | Matrix row 28 | E | `test_ocr.py:132-211,230-288,436-465` |
| 18 | Row 31: `test_orientation_floor.py` "11 tests" | Matrix row 31 | S | 13 collected |
| 19 | Row 31: `test_colour_arm.py` "19 tests" | Matrix row 31 | E | 19 collected |
| 20 | Row 31: signature tests "7 tests" | Matrix row 31 | E | `test_embedded_artwork.py:249-369`, 7 |
| 21 | Row 32: `test_verify_by_search.py` "35 tests" incl. "a value inside a longer word" | Matrix row 32 | E for the count; T for coverage | 35 collected; `TestInsideALongerWord` covers the exact pass, not the rescue (finding 1) |
| 22 | Row 33: `test_product_type_boxes.py` "27 tests" | Matrix row 33 | E | 27 collected; text layer, image, rasterised PDF, none, two, margin, precedence |
| 23 | Row 35: `test_read_once.py` "12 tests" | Matrix row 35 | E | 12 collected; prefill reads no picture, check still fills both values |
| 24 | Row 35: `TestTheCheckIsScoredSmall` | Matrix row 35 | E | `test_orientation_floor.py:229-265` |
| 25 | Row 36: `test_presence_checks.py` "14 tests" | Matrix row 36 | E | 14 collected |
| 26 | Row 37: `helpTab.test.tsx` "21 tests" | Matrix row 37 | E | 21 |
| 27 | Row 38: `reset.test.tsx` "16 tests" | Matrix row 38 | E, one gap | 16; reset during an in-flight check is not among them (finding 17) |
| 28 | Row 39: "8 tests" in the incomplete-criteria block | Matrix row 39 | E | 8 in `a11y.spec.ts:446-597` |
| 29 | Row 39: contrast pairs "derived from the outcome definitions rather than from a list beside them" | Matrix row 39, CHANGELOG, conformance 1.4.3 | **F** | `contrast.test.ts:135,165` hand-type the list |
| 30 | FR-8 row: `test_batch.py` "34 tests" | Matrix section 2 | S | 36 |
| 31 | "Requirements defined: 22 (11 functional, 11 non-functional)" | Matrix section 3 | S | 15 FR, 11 NFR |
| 32 | "ADRs: 10" | Matrix section 3 | S | 18 |
| 33 | "413 backend tests", "252 component tests" | Matrix section 3 | S | 526 and 338 |
| 34 | "User stories: 24"; README "24 stories across 6 epics" | Matrix section 3; README:218 | S | 30 |
| 35 | "FR-1 to FR-10" | README:217 | S | FR-1 to FR-15 |
| 36 | "21 questions, 8 still open" | README:224 | S | 28 questions |
| 37 | "16 inferences" | README:225 | S | 17 |
| 38 | Health response `"version":"1.1.0"` | README:75 | E about the code, S about the tag | Finding 3 |
| 39 | "An optional vision-model fallback on Amazon Bedrock exists" | README:128; ADR 0003:42; NFR-3 AC 2-3; 05_ARCHITECTURE:535,661 | **F** | No implementation (finding 5) |
| 40 | "Bundled as a variable font ... never fetched from a CDN" | README tools table | E | `index.css:64`; seven woff2 files in `dist/assets`; `a11y.spec.ts:712-734` |
| 41 | "No outbound network calls on the default path" | README:124; NFR-3 | E | No client, no URL in `backend/app`; same-origin `fetch` only in `api.ts`; sockets refused in `TestEgressBlocked` |
| 42 | 1.5 s image path, build `sha-f66a4e2`, 2026-08-28 | README, 09 section 9, matrix NFR-1 | T | Build and date named; not reproducible from the repository (no URL, no AWS access) |
| 43 | 5.0 s document path, deploy #12, "build 1.1.0" | README, 09 section 9 | T | Named; the build string would be the same for v1.2.0 (finding 3) |
| 44 | 300-label batch 6.5 to 7 minutes, 300 of 300 correct, 83 at 109 s | README, 09 section 9 | T | Named; not reproducible here |
| 45 | "Peak task memory ... pending" | README, 09 section 9 | E | Stated as pending, honestly |
| 46 | Half-resolution check "right in 48 of 48" | README, `ocr.py:149-158`, OQ-27 | T | The table is in the code; the run is not a test; `TestTheCheckIsScoredSmall` asserts the scale, not the accuracy |
| 47 | "Panel segmentation adds no Tesseract read", asserted by `test_panel_segmentation.py` | README, 09 | E | `TestSegmentationCostsNoTesseractRead:385-410` |
| 48 | Session-container before/after tables (2.19 to 1.12 s, 1518 to 216 ms) | README | T | Named as session-container figures; not reproducible here |
| 49 | In-process accuracy on the sample set: 100 percent precision and recall | README (implied by 300 of 300) | E | Reproduced in this session: 100 percent on every field, median 1104 ms |
| 50 | "Container base images are pinned by tag, not digest" | README known limitations | E | `Dockerfile:9,33`; contradicts `docs/06:69` "acceptable while nothing is released" (finding 12) |
| 51 | "No authentication and no persistence" | README | E | No auth anywhere; persistence per finding 4 |
| 52 | "Section 508 conformance is claimed and evidenced" | README status table | T, with finding 7 | Report exists; four rows contradict the code |
| 53 | "Four polite `role="status"` regions" | Conformance 4.1.3 | **F** | Five; two unlabelled (finding 7) |
| 54 | "Choosing a file ... a change of content, not of context" | Conformance 3.2.2 | **F** | Focus moves (finding 7) |
| 55 | "Links within the Help tab's prose" | Conformance 2.4.4 | S | None exist |
| 56 | "Focus ring checked at 3:1 against ... the banner" | Conformance 1.4.11 | T | Checked against a token the banner's rule does not use (finding 7) |
| 57 | "Component-scoped ids come from `useId`" | Conformance 4.1.1 | S (partial) | `ApplicationFields.tsx:189,227,232` are static |
| 58 | "No `order` property and no absolute positioning except the skip link" | Conformance 1.3.2 | S (minor) | `.visually-hidden` is also `position:absolute` |
| 59 | "Verified at 200 percent" | Conformance 1.4.4 | T | The viewport is halved; text is not resized |
| 60 | "No screen reader was used" | Conformance 5.1 | E | Stated; nothing in the repository claims otherwise |
| 61 | "Nothing here has been applied ... No plan or apply has been run" | `infra/README.md:8-12`; `docs/09:7-14` | S | Contradicted by README, 09 section 9, `locals.tf:27-31` |
| 62 | `.terraform.lock.hcl` "is absent from the repository" | `docs/09:58-60` | S | Committed |
| 63 | `pip-audit --strict` | `docs/06:40` | **F** | `ci.yml:214,217` without `--strict` |
| 64 | "Nothing is written to disk" | `docs/06:23,39`; `SECURITY.md:40-42`; `batch.py:30-31` | S (partly) | Finding 4 |
| 65 | "SBOM generated for every image" | `docs/06:27,42,179` | **F** | CI build only, different from the deployed build (finding 13) |
| 66 | "Write access to develop or main is write access to the deployment" | `docs/06:28` | S | Any branch via the environment subject (finding 11) |
| 67 | "Change a limit here, apply, then run the deploy workflow" | `ecs.tf:185-187`; `docs/09:163-165` | **F** | Finding 10 |
| 68 | "The condition below is what narrows them" | `iam.tf:154-158` | **F** | No condition on that statement |
| 69 | "The application logs structured events" | `logs.tf:8-9`; `docs/05:68` | S | Finding 9 |
| 70 | "Starlette spools a multipart part ... once it exceeds 1 MiB" | `docs/09:140` | S | 10 MB since `api.py:86` |
| 71 | `TTB_MAX_BATCH_BYTES` "= FILES × UPLOAD, 3 000 MiB" | `docs/09:117-119` | S | `config.py:241` is twice that |
| 72 | ADR 0003 alternatives: local OCR primary, fallback optional | ADR 0003 | S (second clause) | Fallback not built (finding 5) |
| 73 | ADR 0004: thresholds 95 and 80, review band | ADR 0004 | E | `config.py:113-114`; `compare.py:119-130` |
| 74 | ADR 0006: NDJSON stream, bounded pool, no job store; CSV half superseded by ADR 0009 | ADR 0006 | E | `batch.py`; no CSV path remains in the backend |
| 75 | ADR 0007: up to three photographs, batch stays one per label | ADR 0007 | E | `config.py:46`; `test_multi_photo.py::TestTheBatchPathIsUnaffected` |
| 76 | ADR 0008 amended by ADR 0016: tick read from the page, ranked below AcroForm and above the text inference, in both directions | ADR 0008:128; ADR 0016 | E | `application_form.py:858-919`; `test_product_type_boxes.py::TestPrecedence` |
| 77 | ADR 0009 amendment: a batch row still requires its image | ADR 0009:228 | E | `batch.py:158-173` enumerates rows from images |
| 78 | ADR 0010, 0011, 0012, 0013 (as amended by 0018), 0014, 0015, 0017, 0018: the decision each records is the one the code implements | The ADRs | E | `application_form.py` (0010, 0017 `read_artwork=False` on the classify route only, no cache), `classify.py` (0011), `warning.py` and `config.py:129` (0012), `verify.py:707-733,957-965` (0013 narrowed, 0018), `ocr.py:935-947` (0014), `search.py` (0015; see finding 1 for what decision 5 did not foresee) |

**Tally.** E 39, T 9, S 21, F 9.

---

## 5. What was run, and what happened

All runs in this session, on the session container (Python 3.11.15, Node 22,
Tesseract 5.3.4 with `osd`, DejaVu fonts), from a clean checkout of `a6279e2`.

| Suite or check | Command | Result |
| --- | --- | --- |
| Preflight | `curl pypi.org`, `curl registry.npmjs.org`, `tesseract --version` | 200, 200, 5.3.4 |
| Backend lint | `ruff check --config pyproject.toml . ../samples ../scripts` | All checks passed |
| Backend format | `ruff format --check --diff ...` | 50 files already formatted |
| Backend tests | `pytest --cov=app --cov-report=term-missing` | **526 passed, 0 skipped, 0 failed**, 340 s; coverage 96 percent (`main.py` 81, `classify.py` 92, `application_form.py` 93, everything else 95 to 100) |
| Frontend lint | `npm run lint` | Clean |
| Frontend build | `npm run build` | Clean; 244 kB JS, 21 kB CSS, seven Inter woff2 files; no external URL in `dist/` other than XML namespace constants and React's error-URL strings |
| Frontend tests | `npx vitest run` | **338 passed, 0 skipped**, 18.8 s across 21 files |
| Accessibility suite | `npx playwright test` against `vite preview` of `dist/` | See below |
| Python audit | `pip-audit -r backend/requirements.lock --no-deps` | No known vulnerabilities |
| Node audit | `npm audit --audit-level=high` | 0 vulnerabilities |
| Accuracy | `python samples/generate_samples.py && python scripts/measure.py` | 100 percent precision and recall on all five fields over the twelve labels; review rate 1 of 12 on alcohol content and net contents (the seeded cross-unit and inconsistent-proof cases); median 1104 ms; mean OCR confidence 95.2 |
| Probe: spool to disk | `SpooledTemporaryFile.rollover` counted around `POST /api/verify` | 5 MB: 0 rollovers; 11 MB: 1 rollover then 413 (finding 4) |
| Probe: INFO logging | uvicorn subprocess with `TTB_LOG_LEVEL=INFO`, one verification | No `app.*` INFO record in the process output (finding 9) |
| Probe: event loop | Concurrent `GET /api/health` during a three-photograph `POST /api/verify` | Verify 3.35 s; the health probe waited 3.34 s (finding 8) |
| Probe: rescue false pass | Rendered label with no alcohol statement, application declaring `12` and `12%` | `alcohol_content: match, score 100.0` both times (finding 1) |

**Accessibility suite.** **28 passed, 0 failed**, 16.7 s, run against the
built page as CI runs it. One environmental note, because it cost three
attempts: the pinned `@playwright/test` 1.62.1 looks for Chromium headless
shell build 1234, the session's preinstalled browsers are build 1194, and
`npx playwright install chromium` could not download through the session
proxy, so the run used the preinstalled 1194 headless shell linked at the
path 1234 is expected at. Nothing in the repository was changed for this. The
first two attempts failed all 28 tests at browser launch, which is what a
Playwright bump without the matching browser install does in CI too;
`ci.yml:127-131` installs the browser explicitly, so CI is not exposed to it.

Not run: `terraform fmt` and `terraform validate` (no Terraform binary in the
session), the container build and the SBOM step (Docker present but the build
was not attempted; CI's own container job is the evidence for it).

---

## 6. What could not be verified, and why

- **Every figure measured on the deployed target** (1.5 s, 5.0 s, 7.8 s, the
  300-label batch, the 83-at-109-s observation, the three-photograph run). The
  load-balancer hostname is deliberately not in the repository and the session
  has no AWS access. The figures are taken as reported; the claims audit marks
  them T.
- **That the stack is applied as written.** State is local and uncommitted;
  the repository's own documents disagree about whether it has been applied
  (finding 14). Not resolvable from the tree.
- **GitHub settings that findings 11 and 27 depend on**: whether the
  `production` environment has a deployment-branch policy or required
  reviewers, branch and tag protection rules, and which repository variables
  are set. None of that is in the repository, and the session's GitHub access
  is scoped to reading the repository, its issues and pull requests.
- **CI results.** The workflows were read, not their runs; the README badge
  points at `develop`. Whether `terraform validate` on aws 5.100.0 accepts
  the omitted OIDC thumbprint was not checked.
- **The contents of `AmazonECSTaskExecutionRolePolicy`** (finding 26) are
  cited from memory, not fetched.
- **The author's real mezcal filing.** Every v1.1.0 and v1.2.0 defect was
  found on it and it is not (and should not be) in the repository, so none of
  the "reads correctly now" claims about that document were reproduced. The
  synthetic fixtures that stand in for it pass.
- **Screen-reader behaviour.** None was used here either; the conformance
  report is honest about this.
- **Firefox behaviour** on the synchronous `revokeObjectURL` in `csv.ts:81`.
- **The task-replacement half of finding 8.** The stall was measured; that
  three missed probes stop the task is read from the health-check settings,
  not observed.
- **Findings 6, 16, 17, 18, 19 and 21 were traced in the source and not
  reproduced in a browser**; each says so.

---

## 7. Where the code is good, and why

- **Orientation** (`ocr.py:692-873`): the floor is real, the second opinion is
  two rotations rather than the four ADR 0003 rejected, a tie leaves the
  engine's answer standing, an unavailable verdict is not scored, and every one
  of those boundaries has a test with the engine stubbed. The measured table
  that sets `ORIENTATION_CHECK_SCALE` is in the code beside the constant.
- **Input validation order** (`api.py:132-184,501-530`; `batch.py:249-254`):
  Content-Length in middleware before the body, media type before decode,
  count before any row, and every rejection in one shape with the limit named.
  `test_api_validation.py` checks the shape and the limit string.
- **Batch isolation** (`batch.py:241-298`): a broad except that turns an
  unforeseen failure into one row's error with the traceback logged and the
  filename kept out of it; futures cancelled on disconnect.
- **The warning** (`warning.py`): exact by requirement, length-preserving case
  fold so the diff indices stay aligned with the label's own text, hyphenation
  rejoined for the stopping rule only, and the bold-type note on every result.
- **The presence and circularity overlays** (`verify.py:676-796`): keyed on
  provenance rather than field name, so ADR 0018 narrowed ADR 0013 without a
  rewrite, and the amendment in the ADR matches the code line for line.
- **The deploy role** (`iam.tf:129-220`): one repository, one ECR repository,
  one service, two passable roles with `iam:PassedToService`, a one-hour
  session, the `aud` condition, and the owner and repository literal in every
  subject; deployment by digest with an empty-digest guard and a stability
  wait.
- **Fixtures**: rendered and written at test time throughout; no binary in the
  tree or the history.
- **Timing** (`timing.py`): disjoint phases, an explicit `unaccounted_ms`, a
  separate count of engine invocations, and the defect that motivated it
  written at the top of the module.
- **Documentation habit**: the CHANGELOG records what was measured, on what,
  and what it cost, including the regressions. Most of this review's medium
  findings are places where that habit was not applied to the infrastructure
  documents on the same day it was applied to the code.
