# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [1.3.0] - unreleased until tagged

The rest of the v1.2.0 code review (`docs/CODE_REVIEW_2026-09.md`; the
author's decisions on it are `docs/CODE_REVIEW_DECISIONS_2026-09.md`), in
three pull requests merged in order: the backend, the screen, and the
infrastructure with the documents that describe it. This release is polish on
a submission that is already defensible. Where a finding turned out to be
larger than it was written, it is tracked in `docs/OPEN_QUESTIONS.md` and the
pull request says so, rather than half-built (SC-5).

### Backend correctness (pull request A)

#### Changed

- **NFR-6 is worded as the retention promise it always was** (finding 4,
  #103; decision 4). "Nothing is written to disk" was not true of any request
  the service accepted: `pytesseract` hands the engine every image through a
  temporary file it deletes before the call returns, and Starlette spools a
  part over the per-file limit to a temporary file before the exact size check
  refuses it. The claim is corrected, not the code: NFR-6 now says nothing
  uploaded is kept, that files exist only for the moments the check takes and
  are gone when it returns, and that there is no database, no bucket and no log
  of content. `docs/06_SECURITY_AND_COMPLIANCE.md` section 3.2 says where the
  bytes live while a request runs, including the exact size of the spool
  window (one part between 10 MiB and 40 MiB on the single-label routes;
  between 10 MiB and the batch envelope on the batch route), and why the window
  is documented rather than closed: closing it from the header means owning
  the framework's multipart parser, and feeding the engine over standard input
  means owning a subprocess wrapper for a guarantee the reworded claim already
  gives (OQ-30). The same wording lands in the Help tab, `SECURITY.md`, the
  architecture and test-strategy documents, US-15, the traceability matrix,
  and the comments in `api.py`, `ocr.py`, `batch.py` and
  `application_form.py`; ADR 0006 carries an amendment rather than an edit.
  `TestNothingIsPersisted`, which asserted that two identical requests gave
  identical outcomes and could not have seen a file, is replaced on both paths
  by `TestNothingIsRetained`: the engine's temporary files are observed being
  created and asserted gone when the request returns, the working directory
  gains no file and no file changes, an oversize part is spooled exactly once,
  refused and gone, and nothing the request carried reaches a line the real
  logging configuration wrote. Every one of those was watched go red with the
  behaviour broken on purpose before it was committed.
- **The single-label check runs in a worker thread, and the number of them is
  bounded** (finding 8, #107). Every Tesseract pass on `POST /api/verify`,
  `/api/classify` and `/api/read-application` ran on the only event loop
  thread, so `GET /api/health` waited for the whole request: 3.34 s in the
  review session, and 7.8 s on the deployed target against a 5 s health-check
  timeout that stops the task after three misses. The reading now runs through
  `anyio.to_thread.run_sync` behind a `CapacityLimiter` sized from
  `TTB_BATCH_WORKERS`, the same setting that sizes the batch pool, because
  anyio's default pool is forty threads and forty concurrent OCR passes on a
  1 vCPU task would trade a stalled probe for an out-of-memory kill.
  `OMP_THREAD_LIMIT=1` and the PDFium lock already cover a worker thread, and
  the `ocr.py` comment that presented the loop-blocking as a safety property
  says what it was. `test_event_loop.py` asserts ordering, not milliseconds: a
  health probe issued while a stubbed, blocking check is in flight is answered
  before the check finishes, and it goes red when the work is run inline.
- **The application's logger emits** (finding 9, #108). Nothing configured
  logging; uvicorn attaches handlers to its own loggers only, so every INFO
  record the routes wrote was discarded and `TTB_LOG_LEVEL` was read by
  nothing. `app/logging_config.py` attaches one handler to the `app` logger at
  the configured level, writing one JSON object per record with the call
  site's `extra` fields as keys, so the `ocr_ms` figure the runbook tells an
  operator to read from CloudWatch is now written. `test_logging.py` runs the
  real configuration, including once under a real uvicorn process whose
  output is read for the completion record at INFO and its absence at
  WARNING, and asserts on that same output that no uploaded filename and no
  value reaches a line; the process test was watched go red with the
  configuration call removed.
- **A tie of nothing in the orientation check is rescored at full
  resolution** (finding 24). When Tesseract's orientation confidence falls
  under the floor, the verdict is scored against its opposite at half
  resolution; type too small to read at that scale scored zero words both
  ways, and the tie kept the verdict the check exists to second-guess. Both
  candidates are now read again at full resolution before deciding, and only a
  tie there falls back to the OSD answer. The path is reported in the existing
  fields: `method` is `osd_180_check_full_resolution` and `overrode_osd` says
  what the full-resolution pair decided. Three tests stub the read and assert
  the four reads, the reported method, and that words at half scale are never
  rescored.
- **PNG encoding leaves the PDFium lock** (finding 25). Every embedded picture
  that cleared the floor was encoded to PNG inside `_PDFIUM_LOCK`, whether or
  not it was ever read, and so were the page renders. The pictures now leave
  the lock as decoded copies and encode themselves on first use, so the
  prefill pass, which counts them and reads none (ADR 0017), encodes none, and
  the check encodes only the ones it reads; page renders are encoded after the
  lock is released. A test watches every encode and asserts none happens
  while the lock is held.
- **The two wall-clock ceilings are opt-in** (finding 23). `elapsed < 5.0` on
  a real OCR request is a property of the runner as much as of the code. The
  figures are still printed on every run; the assertions are behind a
  `wall_clock` marker that `tests/conftest.py` skips unless
  `TTB_ASSERT_WALL_CLOCK=1`, with the reason written beside it. The evidence
  for NFR-1 is the section 9 measurement on the deployed target.
- The 1.2.1 section below carries its tag date, which the tag did not add.

#### Measured

Session container, not production hardware, on synthetic fixtures built at
run time (the author's two real documents stay on her machine and are the
gate in `docs/09_DEPLOYMENT.md` section 9). Three runs each, medians.

| Finding | Fixture | Before | After |
| --- | --- | --- | --- |
| 25, the lock | A filing carrying eight copies of the three-ink colour label (1.5 MB), `POST /api/verify` alone: `document_pdfium_ms` | 905 ms | **105 ms** |
| 25, the lock | The same, `POST /api/classify` wall clock (the prefill pass, which reads no picture) | 963 ms | **160 ms** |
| 25, the lock | The same filing carrying one copy: `document_pdfium_ms` | 173 ms | **23 ms** |
| 24, the orientation check | The one-copy filing, `POST /api/verify` alone: `tesseract_reads` | 2 | 2 |
| 24, the orientation check | The same: `artwork_ocr_ms` | 1618 ms | 1764 ms |

The finding 24 figures are unchanged within run-to-run variation (1580 to
1837 ms before, 1677 to 1786 ms after): the full-resolution pass runs only
when the half-resolution pair reads no words at all, and this artwork, like
the author's, reads dozens at half scale. Her document's `tesseract_reads` of 4
and `overrode_osd: true` are re-taken against the release in the gate.

The item 5 margin at three render scales is recorded in
`docs/09_DEPLOYMENT.md` section 9: the separation swings by about seven points
with the scale on the synthetic form and the scanned form cannot be sampled at
scale 1.0, so the floor does not move (OQ-32, #123).

#### Tracked, not fixed

- The artwork floor rejects a real Registry printout's artwork wholesale:
  OQ-24 and #121. A design question, needing a synthetic fixture shaped like
  the printout, which never enters the repository.
- The fanciful-name capture over-runs on a Registry printout: OQ-31 and #122.
- The item 5 margin: measured, recorded, not moved: OQ-32 and #123.

### The screen (pull request B)

Every item here is something an agent using the tool can hit, and every one
has a test; the four accessibility tests were each broken on purpose and
watched go red before they were committed.

#### Fixed

- **A typed value survives a document uploaded afterwards** (finding 6, #105).
  The source map was rebuilt from the document, so a field the agent had
  typed and the document did not carry became "absent": the value stayed in
  the box, the screen said "Not supplied" beside it, and the request omitted
  it. Agent input now wins over absence, as FR-11's precedence always said it
  should. Where the document carries a different value the disagreement is
  shown under the agent's value ("The application you uploaded says ...; the
  check uses your value") in the summary and in the box, and the agent's
  value is the one sent; a difference of case or spacing alone is not a
  disagreement (FR-4). Editing the box settles it. `typedFirst.test.tsx`.
- **Four Section 508 conformance rows said things the code contradicted, and
  the four tests behind them could not fail** (finding 7, #106). Rows 4.1.3,
  3.2.2, 2.4.4 and 1.4.11 now describe what the code does; 4.1.1 and 1.3.2
  are corrected on the smaller points the review noted. The two batch-tab
  status regions are labelled ("Batch pairing", "Batch progress") and the
  pairing region is always mounted; the stylesheet no longer draws the gold
  ring on the pale banner; the file picker's hint says the cursor will move
  when an application leaves a value unread, which is the advice 3.2.2 asks
  for. The status-region test opens the batch tab and names all five regions;
  the name-role-value test runs a check first and asserts five chips, none a
  button, none focusable; the text-spacing test locates a chip as a chip and
  checks its word is not clipped; the contrast test reads the ring token for
  each ground off the stylesheet's own rules, walks the outcome list off the
  outcome definitions, and asserts the active pill's weight and shadow rather
  than a fill threshold fitted to the measurement. Section 508 is WCAG 2.0 A
  and AA via 36 CFR 1194 Appendix A E205.4, verified to 2.1 AA, as before.
- **The batch table and tally account for every row** (finding 16, #115). A
  row whose worst outcome was not compared, present or artwork-derived was
  counted in none of the four buckets and its detail cell read "All five
  fields match." The tally has seven buckets that partition what `rowOutcome`
  returns, the finished announcement names each non-zero one, and the detail
  cell is the single-label wording, "4 of 5 checks passed", followed by every
  field that was not a match. A test submits one row of each kind and
  asserts the buckets sum to the row count.
- **Reset cancels a check in flight** (finding 17, #116). An `AbortController`
  is held per check, aborted on reset and when a later check starts, and a
  counter disowns an answer that arrives after the screen stopped asking, so
  a late result cannot repopulate a cleared form or overwrite "The form was
  cleared." `inFlight.test.tsx`, with the response released by hand.
- **A file removed before its classification returns is ignored** (finding 18,
  #117). Each change to the list cancels the request for the previous list;
  an answer for a list the agent no longer has fills nothing and announces
  nothing. Tested with a removal mid-flight and with two overlapping requests
  resolving out of order.
- **A photograph alone opens no box, moves no focus, and says the true thing**
  (finding 19, #118). It can be checked for the elements a label must carry,
  and there is nothing to compare it against yet; the upload panel and its
  live region say so, and the four gap boxes and the focus move are gone for
  that case. "Upload a clearer image" is not said about a photograph.
- **Blanking a document-read value removes it from the check** (finding 29).
  An empty typed value let the server re-derive the field from the document it
  was sent anyway. The interface now sends the blanked fields as
  `cleared_fields`, the server treats each as declared absent, and the hint
  above the boxes says what a blank does. Backend and frontend tests.
- **The pairing preview implements the server's rule** (finding 21). The
  server folded with `casefold`, which rewrites `ß` to `ss`; the page folds
  with `toLowerCase`, which does not, so `Straße.png` paired on the server
  and not on the page. The server now uses the plain lower-case mapping too,
  and the same vectors are asserted on both sides. The preview is kept: the
  runbook's section 8.4 relies on the count before sending, and the code is
  small and now provably the same rule.
- **Three server error codes have plain-language lines** (finding 22):
  `no_label_to_check`, `too_many_application_documents` and `no_files`. The
  test reads every code off the backend's own source, so a code added without
  a line fails the build.
- **`file_too_large` says what was too large** (finding 30): a file, a
  submission of several, or a batch, read off the server's message.
- **Two files with the same name get their own chips** (finding 31): the
  classification is matched by position, which is submission order.
- **A TIFF shows an honest placeholder** (finding 32): the preview frame says
  the browser cannot draw a TIFF and the server reads it as usual, instead of
  a broken-image glyph.

#### Found, not fixed

- **The clean result does not fit one screen at 1280 by 800, and the test that
  said so was measuring scroll position** (#128, OQ-33). Removing the focus
  move for a photograph on its own (#118) stopped the page scrolling under the
  test, and the panel it then measured is about 1655 px from heading to
  footnote, as it was before. The test now measures the panel in document
  coordinates and is annotated as an expected failure with the figure, so it
  turns red the day the panel fits; NFR-4 keeps the target and records that it
  is not met. Making it fit is a layout decision for the author.

### The infrastructure and the documents that describe it (pull request C)

Nothing here has been applied to an AWS account in this session, which holds
no credentials; the Terraform is formatted and CI validates it against the
provider schema, and the author's gate runs the deploy on `develop` before the
release. Each item names the finding and the issue.

#### Fixed

- **The deploy role is scoped by repository and ref, not by environment**
  (finding 11, #110). The `environment:production` subject is gone from the
  trust policy and `environment: production` is gone from the deploy job,
  because the two go together. Checked rather than assumed: the environment
  on this repository has no deployment-branch policy and no protection rules,
  so the subject admitted any branch and the two branch entries beside it
  constrained nothing. `docs/06` section 2 records the reasoning, what would
  change it, and what the ref condition does not do: with no review gate on
  the environment, the image push and the service update are gated by the
  same thing, write access to `develop`, `main` or a `v*` tag.
- **Transit is stated as the limitation it is** (finding 20, #119). The
  premise at the top of `docs/06` said the prototype handled no sensitive
  data; since ADR 0008 its primary input is a filed application with the
  applicant's signature on page 2. The premise is rewritten, section 3.1 says
  the filing crosses the wire in the clear and that no credential, session or
  identity does, sizes the production fix (an ACM certificate, a 443 listener,
  a redirect from 80 and one security group rule: roughly one Terraform block
  plus a domain), and records why a CIDR restriction and a domain were both
  refused for the evaluation stack. The scope document and the README say the
  same. No CIDR, no domain, no authentication was added (decision 5).
- **The task definition has one owner** (finding 10, #109; ADR 0019).
  Terraform owns its shape; the deploy workflow owns the image and starts from
  the latest revision of the family rather than from the revision the service
  is running, so a cap or a size changed in `ecs.tf` reaches the service on
  the next deploy, which is what the `ecs.tf` comment claimed. `docs/09`
  section 4.4 describes the apply-then-deploy path and its check.
- **Every action is pinned by commit SHA and both base images by digest**
  (finding 12, #111). Twelve actions across the two workflows, each with the
  version it was resolved from beside it; `id-token: write` moved from the
  workflow to the two jobs that assume the role. The Dockerfile `TODO` that
  said "before the first tagged release", five releases late, is closed.
- **The SBOM describes the image that was pushed** (finding 13, #112).
  `deploy.yml` generates it from the registry by the deployed digest, names
  the artifact by that digest, keeps it 90 days, and attaches it to the
  release from a job that holds `contents: write` and no AWS session. CI's
  SBOM of its own build stays as a CI artifact. `docs/06` says what consumes
  it: nothing automatic, so it is an inventory and not a gate.
- **The execution role and the task's egress are narrowed** (finding 26).
  An inline policy naming the stack's one repository and one log group
  replaces the account-wide managed execution policy; the task's egress is
  TCP 443 only, which is all that image pull, layer fetch and log delivery
  use. The task role still has no policy at all.
- **Release tags cannot be re-pointed** (finding 27). The registry is
  `IMMUTABLE`, and the deploy workflow refuses a dispatch tag matching
  `^v[0-9]` before it builds. The runbook says what a re-run on the same
  commit now needs.
- **No `.env` file at any depth reaches the image** (finding 28).
  `.dockerignore` excludes `**/.env` and `**/.env.*`; CI plants one at each
  depth, builds the frontend stage from that context, and asserts none is in
  the stage and the planted value is not in the bundle.
- **`infra/README.md` no longer says the lock file is not committed** (finding
  15, #113). It has been since the first local init.

#### Changed

- Version 1.3.0 in `backend/pyproject.toml`, which is the one source; the
  package reads it from its own metadata and `frontend/package.json` carries
  the same value, as `test_release_metadata.py` asserts.

## [1.2.1] - 2026-09-01

A hotfix from `main`, carrying the corrections a hiring panel would trip over
first among the findings of the v1.2.0 code review
(`docs/CODE_REVIEW_2026-09.md`, on `develop` in #120), and nothing else. The
author's decisions on the review, including the ones deliberately not taken,
are in `docs/CODE_REVIEW_DECISIONS_2026-09.md`.

### Fixed

- **The alcohol-content rescue search could pass a label with no alcohol
  statement** (FR-7, FR-9, FR-15; #100). Where the pattern extractor found no
  alcohol content, v1.2.0 searched the label for the declared value and installed
  a whole-word hit as the label side. The declared value normalizes to a bare
  number, so a label printing `AGED 12 MONTHS IN OAK` and no alcohol content,
  submitted with the application declaring `12`, returned `alcohol_content:
  match`. `RESCUED_FIELDS` is now `("net_contents",)`; net contents keeps the
  rescue because its unit is the marker and a bare number never parses as one.
  A regression test renders that label and asserts not found for `12` and `12%`.
  ADR 0015 is amended with the reason and the alternatives rejected.
- **The build tagged v1.2.0 reported version 1.1.0** (#102). The version was a
  literal in three files and the release skipped the bump. `app.__version__` is
  now read from the installed distribution, so `pyproject.toml` is the one
  declaration; `test_release_metadata.py` fails when `package.json` disagrees;
  and the deploy workflow refuses a release whose tag does not match. The
  1.0.0, 1.1.0 and 1.2.0 sections above now carry their tag dates.
- **The optional Bedrock fallback the README, ADR 0003 and NFR-3 described does
  not exist** (#104). There is no client, no dependency and no call site; the
  three settings that promised it were read by nothing. They are removed, the
  README and NFR-3 say the fallback was designed and not built, ADR 0003 is
  amended, and `external_call_made` is documented as the constant it is.
- **Real applicant data in fixtures and current documentation** (#101). The
  brand, designation and product values of a real filing were the defaults of
  `ColourLabelSpec` and appeared in two backend and three frontend tests and in
  the README, the scope, requirements, architecture and assumptions documents
  and the traceability matrix. All are invented values now. The CHANGELOG entries
  and ADR context that describe what happened on that filing are left as the
  record they are; the decision and its line are OQ-29. The identifier that was
  in three commits' history is not rewritten out, for the reasons OQ-29 gives.
- **Infrastructure documents that said the stack had never been applied**, and
  five other stale statements (#113): the openings of `infra/README.md` and
  `docs/09_DEPLOYMENT.md`, the lock-file paragraph, the `pip-audit --strict`
  claim, the batch envelope derivation, the spool threshold, the registry
  hostname, and two `iam.tf` comments that described a condition and a scope
  the policy does not have.
- **Counts in the traceability matrix and the README that were stale** (#114):
  26 requirements not 22, 18 ADRs not 10, 30 stories not 24, 29 open questions,
  17 assumptions, and the per-file test counts. `test_release_metadata.py` now
  checks the matrix summary against the headings.
- **The item 5 comment described a 22 point separation** that the module's own
  window does not measure: 12.1 on the same filing (#123). The comment says so;
  the margin is unchanged until the measurement is taken at three scales.

### Measured

The two-document gate in `docs/CODE_REVIEW_DECISIONS_2026-09.md` decision 7,
run on a session container against this branch, with only measurements
recorded (the documents are real filings and stay out of the repository):

| Document | Result on this branch |
| --- | --- |
| The author's 3-page filing, submitted alone, three runs | Five rows pass: brand and class match, alcohol content and net contents are presence checks, the warning matches. `elapsed_ms` 3477, 3592 and 3337; `ocr_passes` 1; `tesseract_reads` 4; the orientation check ran (`osd_confidence` 0.03) and `overrode_osd: true`; the colour arm won; four columns cut; item 5 read from the box. |
| The 1-page Registry printout, `POST /api/read-application` | Brand, class and item 5 read from the text layer and the box; alcohol content and net contents absent; all seven embedded images rejected by the size floor (#121); the fanciful name over-runs to seven words (#122). |
| The printout submitted alone | `422 no_label_to_check`, as at v1.2.0 (#121). |
| The printout with a synthetic label that prints no alcohol statement | `alcohol_content: mismatch`, not found on the label, both with the application silent and with `12` typed. At v1.2.0 the typed case returned `match`. |

Measured on a session container, which is not production hardware; the
deployed figure for the filing is section 9's 5.0 s and is re-taken against
the release.

## [1.2.0] - 2026-09-01

The author's use of the released v1.1.0 build on 2026-08-30, with the same real
mezcal COLA document uploaded alone. Everything upstream worked, two of the four
compared fields still came back as defects, item 5 was still blank, and the
screen said far too much about all of it.

### The evidence

The application side filled correctly, `DEL MAGUEY` for the brand name and
`MEZCAL FB` for the class or type, both out of the document's own text layer.
The label artwork was found, lifted out, turned the right way up and read. And
then:

> Does not match. Brand name. On the label: **Not found on the label**. On the
> application: DEL MAGUEY.

Measured against the segmented label text that same pipeline produced:

| declared by the application | present in the label text | best fuzzy score |
| --- | --- | --- |
| `DEL MAGUEY` | **yes, exact** | 100.0 |
| `MEZCAL` | **yes, exact** | 100.0 |
| `42% ALC BY VOL` | **yes, exact** | 100.0 |
| `750 ML` | **yes, exact** | 100.0 |

Four of four declared values were on the label, exactly, in text the tool was
already holding. It reported two of them as not found. The author's summary of
what the tool is for: "basically the whole goal is to match what's in the
application to the picture of the label."

### Changed

- **The comparison is inverted: the label is searched for the value the
  application declares** ([ADR 0015](docs/adr/0015-verify-by-search.md), FR-1
  through FR-4 rewritten). The tool no longer extracts a value from the label and
  then compares two strings. Extraction is the fragile half, and every field-level
  defect reported against a deployed build has been an extraction failure rather
  than a matching failure or an OCR failure: the brand name read as the producer's
  tax identifier, and then the brand name and the class or type both declined by a
  type-size ranking on a label whose largest text is the fanciful name.
  - Both sides are normalized as FR-4 already required. The label reading is
    searched one unit per region of the sheet, with the lines joined, so a brand
    set across two lines is found. Whole-word containment scores 100; otherwise
    the best window of words is scored with the same `fuzz.ratio` as before.
  - **The thresholds are the ones already configured.** A search score is
    classified by the same `classify` at the same A-4 numbers, 95 and 80. No new
    scale is introduced.
  - **The row reports where the value was found**, by column and block, and shows
    the label's own printing of it. That replaces the extracted value and is more
    useful than one: an agent can see the brand was found on the front panel
    rather than in the small print. Dave Morrison's `STONE'S THROW` against
    `Stone's Throw` now shows both casings side by side.
  - **The limit is stated, once, on the screen and in FR-1**: a hit shows the
    declared value appears on the label; it does not show it appears as the brand,
    in the required type size, or on the required panel. Type size and placement
    are OOS-5 and unchanged.
  - **The class or type is searched for its description, not its registry code.**
    The application states `MEZCAL FB` and no label prints `FB`. The full value is
    searched for first, so stripping can never lose a match, and the row says the
    code was left off.
  - **Extraction does not disappear.** Where the application supplied no value
    there is nothing to search for, and the existing extractor is the fallback
    with its existing honest not-found behaviour.
- **`scripts/measure.py` now measures the search**, because it hands the pipeline
  the same reading the API does. Its accuracy figures are for the code an agent
  runs rather than for a fallback path.

### Added

- **Item 5's product type is read off the rendered page**
  ([ADR 0016](docs/adr/0016-product-type-from-the-page.md), FR-11, A-17 amended).
  The author asked whether beverage type is a field on the application. It is:
  item 5 on TTB F 5100.31 (04/2023), "TYPE OF PRODUCT (Required)", three check
  boxes. The tool left it blank on every filing that was not an unflattened
  AcroForm copy, because it read only the text layer, where all three captions
  print and no tick can be seen. The tick is in the pixels, and the tool renders
  the pages already. On the author's own filing, at scale 2.0:

  | item 5 option | mean luminance |
  | --- | --- |
  | WINE | 239.9 |
  | **DISTILLED SPIRITS** | **217.5** |
  | MALT BEVERAGE | 241.8 |

  - **The boxes are located from their own captions, never from a pixel
    coordinate.** The form has editions and this tool renders at a scale derived
    from the page size and a setting, so a coordinate would be right once. The
    captions come out of the text layer exactly where the file has one, and are
    recognized only on a page that has none.
  - **The margin is 12.0 luminance points** between the darkest box and the next,
    and it is set from both ends of the measurement: the signal is 20 to 22 points
    across the author's filing and three fixtures, and the noise between two boxes
    that are both empty is 0.5 to 2.8. Two boxes too close to separate, and no box
    filled, both come back as not determined and the agent chooses.
  - **The sample window is deliberately loose.** A tight crop gives a bigger
    number when it lands exactly and a wrong answer when it does not: at twelve
    pixels of caption height, a one pixel difference in a caption's left edge put
    fifteen points between two boxes that were both empty.
  - The value is surfaced for confirmation and stays editable like every other
    parsed value, with a provenance chip of its own, "Ticked box on the form". It
    is still never compared against the label; it selects which numeric rule runs
    (A-12 for spirits, A-13 for wine) and the result already names the rule.
  - A new `item_five_ocr_ms` phase reports what this costs. It is zero on every
    document that carries a text layer.

### Fixed

- **A scanned form with nothing ticked stops being answered wrongly.** The
  "document names exactly one product type" rule is an inference from absence: it
  is sound on a Registry printout and unsound on a scan whose OCR lost two of the
  three captions, which looks identical. Sampling the boxes is direct evidence of
  the thing being inferred, so it now supersedes that inference in both
  directions, filling the value where a box stands out and clearing it where the
  boxes were sampled and none did. An AcroForm radio group still wins over both.

### Removed

- **The timing line and the "Where the time went" disclosure are off the screen**
  (NFR-1 amended, NFR-4). The author: "I don't need the time listed on the screen
  think about what a regular application looks like do not put all these extra
  words on the screen that should not be there." An agent checking a label is not
  measuring the tool. The number was also not measuring what she experienced: her
  run showed 7.8 seconds of which 2334 ms was her own browser and network.
  - **Nothing about the measurement changes.** Every phase is still timed by a
    timer around the work it names and every figure is still in the API response,
    where `docs/09_DEPLOYMENT.md` section 8.3a reads them. This is a presentation
    change.
  - The live region drops the seconds with it, so a screen reader is not read a
    number nobody can see. It says no less about what changed.
  - `frontend/src/lib/timing.ts` and `honestTiming.test.tsx` go with the panel
    they existed for.

### Changed, on the screen

- **One sentence per row, at most.** The artwork-derived rows carried a paragraph
  above the reason and a ninety-word reason under it, saying the same thing
  twice. The outcome chip already reads "Read from the artwork" and the row
  already carries "Label artwork (same source as the label)"; what is left is the
  one sentence neither of those states.
- **One notice per screen, not four.** The self-consistency explanation appeared
  in the upload card, in the results header and on every affected row, and the
  "this came off a picture" caveat appeared under every read value and again
  under every result row. Each is now said once, where it is first relevant.
- **A word budget, asserted.** Measured on the same fixtures before and after:

  | measurement | before | after |
  | --- | --- | --- |
  | clean five-row panel | 246 | 157 |
  | one row that matched | 26 | 26 |
  | the author's own submission, whole panel | 584 | 253 |
  | one artwork-derived row on it | 159 | 51 |

  159 words on one row is the "about 150 words explaining a single row" the
  author was looking at. `quietScreen.test.tsx` holds the ceilings, and
  `a11y.spec.ts` holds her own target: a clean single-label result fits one
  screen at 1280 by 800, its last element ending at 412 px against 535 px before.

### Unchanged, deliberately

- **The prototype banner, the author attribution, the FR-9 error messages, and
  the sentence that says who decides.** Cutting words is not licence to drop a
  message that names a real problem, and each of those is asserted separately.
- **Accessibility.** axe green on the built page, the contrast test green, the
  keyboard walk unchanged, outcomes still carrying text and shape before colour,
  and every live-region announcement still saying what changed. Shorter copy did
  not become vaguer copy.
- **FR-5, the government warning.** It already searches the label for a known
  statutory string, it is exact rather than fuzzy by requirement, and it returns
  an exact match on the author's own document. Nothing here touches it and it
  still carries no similarity score.
- **FR-7, A-12 and A-13, the numeric comparisons.** The alcohol content and the
  net contents are located by pattern, which is deterministic and which read both
  correctly on the author's document. A similarity score cannot express "different
  units, no conversion, needs human review", or the 27 CFR 5.65 proof cross-check,
  or a wine range under 27 CFR 4.36. So those rules stand, and the search supplies
  the label side for them only where the pattern found nothing and the declared
  value is on the label at or above the match threshold.
- **FR-14 and ADR 0013.** A row whose two sides are one reading of one picture is
  still reported as read from the artwork rather than as a match, and searching
  that picture for a value read off it is circular in exactly the same way.
- The beverage type is still never compared against the label, and the embedded
  label artwork still cannot supply it: a label does not print a form answer.

### Added

- **Item 5's product type is read off the rendered page**
  ([ADR 0016](docs/adr/0016-product-type-from-the-page.md), FR-11, A-17 amended).
  The author asked whether beverage type is a field on the application. It is:
  item 5 on TTB F 5100.31 (04/2023), "TYPE OF PRODUCT (Required)", three check
  boxes. The tool left it blank on every filing that was not an unflattened
  AcroForm copy, because it read only the text layer, where all three captions
  print and no tick can be seen. The tick is in the pixels, and the tool renders
  the pages already. On the author's own filing, at scale 2.0:

  | item 5 option | mean luminance |
  | --- | --- |
  | WINE | 239.9 |
  | **DISTILLED SPIRITS** | **217.5** |
  | MALT BEVERAGE | 241.8 |

  - **The boxes are located from their own captions, never from a pixel
    coordinate.** The form has editions and this tool renders at a scale derived
    from the page size and a setting, so a coordinate would be right once. The
    captions come out of the text layer exactly where the file has one, and are
    recognized only on a page that has none.
  - **The margin is 12.0 luminance points** between the darkest box and the next,
    and it is set from both ends of the measurement: the signal is 20 to 22 points
    across the author's filing and three fixtures, and the noise between two boxes
    that are both empty is 0.5 to 2.8. Two boxes too close to separate, and no box
    filled, both come back as not determined and the agent chooses.
  - **The sample window is deliberately loose.** A tight crop gives a bigger
    number when it lands exactly and a wrong answer when it does not: at twelve
    pixels of caption height, a one pixel difference in a caption's left edge put
    fifteen points between two boxes that were both empty.
  - The value is surfaced for confirmation and stays editable like every other
    parsed value, with a provenance chip of its own, "Ticked box on the form". It
    is still never compared against the label; it selects which numeric rule runs
    (A-12 for spirits, A-13 for wine) and the result already names the rule.
  - A new `item_five_ocr_ms` phase reports what this costs. It is zero on every
    document that carries a text layer.

### Fixed

- **A scanned form with nothing ticked stops being answered wrongly.** The
  "document names exactly one product type" rule is an inference from absence: it
  is sound on a Registry printout and unsound on a scan whose OCR lost two of the
  three captions, which looks identical. Sampling the boxes is direct evidence of
  the thing being inferred, so it now supersedes that inference in both
  directions, filling the value where a box stands out and clearing it where the
  boxes were sampled and none did. An AcroForm radio group still wins over both.

### Unchanged, deliberately

- The beverage type is still never compared against the label, and the embedded
  label artwork still cannot supply it: a label does not print a form answer.

### Added: a Section 508 conformance report, with its exceptions

The author: "this entire project needs to be 508 compliant; ensure that it is."

Section 508 of the Rehabilitation Act, as revised in 2017, adopts WCAG 2.0
Levels A and AA for web content at 36 CFR Part 1194, Appendix A, E205.4. NFR-5
targeted WCAG 2.1 AA, which is a superset and therefore satisfies it, so the gap
was not conformance; it was that the requirement never named the standard a
federal reviewer would ask about, and that the criteria no automated tool
evaluates had not been walked and recorded.

- **[docs/ACCESSIBILITY_CONFORMANCE.md](docs/ACCESSIBILITY_CONFORMANCE.md)**
  (US-30). Criterion by criterion across all four principles, with a result and
  a line of evidence for each, five named test methods, and three stated
  exceptions.
- **NFR-5 rewritten** to name Section 508 and the WCAG 2.0 AA standard it
  adopts, and to say separately that the interface is verified to WCAG 2.1 AA.
  Those answer different questions: what is required, and what was done.
- **The criteria axe reports as incomplete are now tested**, in
  `a11y.spec.ts::the criteria a tool reports as incomplete`: reflow at 320 by
  256 pixels on all three tabs and with a five-row result, text spacing
  overridden to the values 1.4.12 names, 200 percent zoom, use of colour under a
  real greyscale filter on two different results, name-role-value on the tab
  set, the disclosure and the outcome chips, and the status-message regions.
- **The contrast test derives its outcome list from the outcome definitions**
  rather than from a list kept beside them, so an outcome added with an
  unchecked colour fails rather than shipping. It also checks the focus ring
  against every ground it actually lands on rather than only the two surfaces.
  No new token was introduced by the presence checks or the Help tab: Contains
  reuses the match pair deliberately, and Help uses only tokens already covered.
- **The pill control was already a real tab set** and is now asserted as one,
  with `aria-selected` and the panel association checked rather than assumed.
- **No screen reader was used, and the report says so** as exception 5.1, with
  what that does and does not leave open and what should be run before any use
  beyond this assessment. A truthful report with exceptions is worth more to a
  reviewer than a blanket claim.
- **OQ-7 is answered in practice and left open as a question.** Whether Section
  508 formally applies to a prototype of this kind is for the agency; the work
  was done as though it does.

### Added: a reset, on both views that hold state

The author: "add a reset option that clears the information so another
application can be uploaded." An agent working through a stack of applications
had no way back to the empty state but to reload the page.

- **One control on the single-label view** (US-29), labelled "Clear and start
  another label", beside the results rather than at the top of the form. It
  clears the uploaded files, the parsed values, every typed field and the results
  together, closes the disclosure if it was open, and is offered only when there
  is something to clear.
- **Focus moves to the file picker and the live region says the form was
  cleared.** Not polish: this control removes the element that had focus, which
  is itself, and one that left focus on the document body would fail exactly the
  agent who could not see that the screen had emptied.
- **No confirmation dialog.** Nothing is stored, so nothing is lost that cannot
  be re-uploaded, and a dialog is one more thing in the way.
- **The batch view got one too**, because it holds state: both pickers, the rows
  and any error, with a running stream stopped first so that a reset cannot leave
  a table filling itself back up.
- **The picker is remounted rather than emptied by hand.** A file input's value
  is not React's to clear, and choosing a file identical to the one already in it
  fires no event, so an agent who cleared by mistake could not re-choose the file
  they had.

### Added: a Help tab, and the check screen gets quiet

The author, on the build the word budget produced: "this has way too many words
on the screen. create a help me tab and put all of the text you are removing plus
some FAQs on that tab."

The budget added earlier in this release stops the panel growing back in bulk. It
does not stop one long paragraph replacing three short ones, and it was being met
by a screen that still explained itself at every control: six paragraphs of
standing caveat, each true, each on every check an agent ever runs.

- **A third segment of the tab strip, Help** (US-28). A reading page: headings,
  short paragraphs, no controls except links, and no requirement identifier
  anywhere on it. It answers what to upload, what each outcome means including
  the new Contains, why a value can come from the artwork inside the application,
  why the brand name is found but not judged for type size, why a bottle photo
  reads worse than filed artwork, where beverage type comes from, what happens to
  your files, and what this tool is not.
- **Six paragraphs come off the check screens** and are rewritten for a reader
  rather than pasted across. `helpTab.test.tsx` asserts each one absent from the
  check screen and its replacement present on Help.
- **The empty-state prompt becomes a short label**, "Upload a file to check.",
  rather than nothing. The agent still has to know why the button is inert.
- **The fanciful name and the class or type code become lines, not sentences.**
  Each is now the name, the value, and a chip reading "Not compared". They are
  real values the parser read off the document in front of the agent, so they
  stay as data; why they are not compared is a Help entry. That is the quieter of
  the two options the brief offered.
- **A sentence rule, asserted.** From the top of the upload card to the last
  result row, no explanatory paragraph runs to more than one sentence. Its
  exemptions are listed in the test and each is something that stays exactly as
  it is: FR-9's messages, the government warning card's own detail, and "This
  tool recommends. You decide."
- **Nothing that names a real problem moved.** The persistent prototype banner,
  the footer and the FR-9 error messages are unchanged and are not on Help. A
  quieter screen that achieved itself by hiding a failure would be worse than the
  wordy one.

### Changed: alcohol content and net contents are presence checks, and they pass

The author, on the released build: "Alcohol content and net content needs to
also say 'match' or 'Contains' in green when these items are found on the
artwork (that is the requirement right? to have the volume and alcohol content
listed?)"

It is the requirement, and the tool was throwing the finding away. 27 CFR
5.63(a)(3), 4.32(b)(3) and 7.63(a)(3) put alcohol content on the label;
5.63(b)(2), 4.32(b)(2) and 7.63(a)(5) put net contents there. When the artwork
carried `42% ALC BY VOL`, the tool had established something real: the label
carries an element the regulation requires. It reported that nothing had been
established, because it was comparing the value against the picture it was read
from. The circular part was the comparison, not the finding.

- **A sixth outcome, `present`, and it is a pass**
  ([ADR 0018](docs/adr/0018-presence-checks.md), FR-15). Where the application
  declares no value, the row is a one-sided presence check: it carries the
  label's value, no score, and a reason citing the section of 27 CFR it answers.
- **The chip reads Contains, in the same green as Match, with its own shape.**
  "Contains" is the stronger claim, not a hedge: Match says two things agreed,
  and here one thing was found. Sharing a colour with Match is what makes the
  word and the silhouette load-bearing rather than decorative, so Contains uses
  a ring holding a dot, which no other outcome uses and which is nothing like a
  tick in greyscale. If the author prefers the word "Match", it is one constant:
  `label` on the `present` entry in `frontend/src/lib/outcomes.ts`.
- **No application side on the row at all**, not even a "not supplied"
  placeholder. The row used to print the identical string in both columns,
  because the value had been read off the artwork and written into the
  application side, and an agent reading two identical values reads a
  comparison. There was none.
- **Both paths exist and both are tested.** Where the application does declare
  the value, by typing or from a form edition that carries it, the row is a
  two-sided comparison reporting match or does not match exactly as before.
  FR-11's precedence is unchanged.
- **Absence is still a finding**, reported against the regulation with both
  container carve-outs in the reason, and a spirits label whose percentage and
  proof disagree is still the A-12 review: a contradiction is the more specific
  finding and the presence check does not overrule it.
- **The summary line reads "5 of 5 checks passed"**, counting comparisons and
  presence checks together. It replaces "3 of 3 verifiable fields match; 2 read
  from the artwork only", which was the honest line while those rows were
  circular comparisons.
- **ADR 0013 is amended, not deleted.** The `artwork_derived` state narrows to
  what it was built for: a field with no presence rule, read off the artwork, on
  a submission carrying no photograph. It should be rare, and on the author's own
  filing it does not arise, because that form states the class or type in item 9.
  Whether the class or type should become a presence check too is
  [OQ-28](docs/OPEN_QUESTIONS.md#oq-28), open rather than guessed: the citations
  have not been fetched, and a presence check for it would rest on the type-size
  ranking ADR 0015 exists to work around.

### Performance: the artwork is read once, in one request

The author measured the deployed build on 2026-09-01 with her own mezcal COLA
document, 382 KB, submitted alone:

| request | when it runs | measured |
| --- | --- | --- |
| `POST /api/classify` | the moment she picks the file | 5492 ms, 5410 ms |
| `POST /api/verify` | when she selects **Check this label** | 5331 ms to 5498 ms |

About eleven seconds of waiting for one document, with each request on its own
inside NFR-1's target. Both were reading the same pictures: the prefill request
came back with `artwork_images_read: 1`, and the document's own text layer takes
277 ms, so the rest of it was a full Tesseract pass over artwork that
`POST /api/verify` was about to read again for the label side.

- **`POST /api/classify` reads the document's text layer and stops**
  ([ADR 0017](docs/adr/0017-read-the-artwork-once.md), NFR-1, NFR-6). It counts
  the pictures it found without reading them and says which of the two readings
  it did, in a new `artwork_read` on the parsed block. The five boxes fill as
  fast as the file uploads.
- **The artwork is read once, at check time**, where the check needs it anyway.
  What it yields fills alcohol content and net contents in the result.
- **A value the artwork is about to supply is not reported as a gap.** A gap
  opens a box inline, moves focus into it and announces that the value was not
  found in the upload. Saying that about a value the next click reads off the
  artwork would be the tool asking an agent to do work it is one second from
  doing itself. The two stay editable behind the disclosure, because FR-11's
  precedence still makes a typed value win.
- **`POST /api/read-application` still reads everything.** It is FR-11's route
  for a caller that wants the parsed values without verifying, and there is no
  second request behind it to do the reading.
- **Not a cache, and the ADR says so in as many words.** A server-side store of
  parsed documents would breach NFR-6, which is an acceptance criterion of this
  system and a promise printed above the masthead on every screen: "Nothing you
  upload is stored." The second read is gone because there is no second read.

Measured on a session container, which is not production hardware and is
reported only as a before-and-after on one machine, with a synthetic 155 KB
filing carrying one embedded label image, three runs each:

| Request | Before | After |
| --- | --- | --- |
| `POST /api/classify` | 1463 / 1518 / 1594 ms, median **1518** | 160 / 216 / 245 ms, median **216** |
| `POST /api/verify` | 1459 / 1472 / 1606 ms, median **1472** | 1370 / 1394 / 1425 ms, median **1394** |
| Both together | **2990 ms** | **1610 ms** |

### Performance: the 180-degree check is scored at half resolution

[OQ-27](docs/OPEN_QUESTIONS.md#oq-27) is closed. It was costed on one image on
2026-08-30 and deliberately not built on it, because one image is not a
measurement of a decision rule. The measurement that answered it is the one
ADR 0003 was decided on: the twelve sample labels at all four cardinal
rotations, forty-eight cases, with the check forced to run on every one of them,
run over the clean renderings and again over the same set degraded into
something shaped like a phone photograph. The degraded run is the one that
decides, because the clean set is right at every scale and so separates nothing:

| scale | long edge | right | both candidates, per case |
| --- | --- | --- | --- |
| 1.00 | 1600 px | 48 of 48 | 1504 ms |
| 0.60 | 960 px | 48 of 48 | 957 ms |
| 0.50 | 800 px | 48 of 48 | 781 ms |
| 0.40 | 640 px | 48 of 48 | 649 ms |
| 0.30 | 480 px | **44 of 48** | 381 ms |
| 0.25 | 400 px | 48 of 48 | 312 ms |

- **`ORIENTATION_CHECK_SCALE` is 0.5**, and the scale sits one measured step
  above the first failure rather than at the last passing value. A rule whose
  accuracy is not monotone in its own parameter has started reading noise, and
  OQ-27's single-image table has 0.25 answering backwards on the author's own
  artwork.
- **Scoring is not reading.** The two candidate passes exist to separate two
  numbers that on real artwork are fifty points and more apart. The winning
  rotation is applied to the full-resolution image, which is what the pipeline
  goes on to read, and `test_orientation_floor.py` asserts both halves.

## [1.1.0] - 2026-08-31

The author's own use of the deployed v1.0.1 build on 2026-08-29, with a real
COLA document: TTB Form 5100.31, OMB No. 1513-0020, three pages. Two problems
reported and one design instruction, and this release is the answer to all
three.

### The evidence

**Only two of the five fields reconciled.** The diagnosis was made against the
file rather than guessed. The brand name and the class or type designation came
out of the PDF's embedded text layer, both correct. The alcohol content and the
net contents are genuinely absent from the form's text layer, exactly as
assumption A-17 already said. **But they are not absent from the document**:
pages 2 and 3 each carry an embedded raster image, and page 3 is the complete
flat label artwork at 1750 by 1150 pixels, carrying `DEL MAGUEY`,
`VIDA SINGLE VILLAGE MEZCAL`, `42% ALC BY VOL`, `750 ML` and the full horizontal
GOVERNMENT WARNING. The parser never rasterized or extracted those images, so it
never saw values that were sitting inside the file it had been handed. OCR of
that artwork at 2x reads the warning with exactly one character wrong, `MPAIRS`
for `IMPAIRS`.

**Submission was blocked because a label image was required.** The author's
words: "if COLA is uploaded, I don't also need an image."

**And the instruction:** "these should be combined; just one upload; simplify
the interface. You should be able to upload (pdfs or images). Collapse the form
fields and only expand if there is something that isn't read in from the
application or picture."

### Added

- **The COLA document's own label artwork is read**
  ([ADR 0010](docs/adr/0010-embedded-label-artwork.md)). Every embedded raster
  image at or above a size floor is lifted out of the PDF at its own resolution
  and read through the same OCR pipeline label artwork goes through, with the
  v1.0.1 orientation and preprocessing decisions unchanged. What it says fills
  application values the text layer left empty.
  - The floor has three parts, all of which have to be met: at least 400 pixels
    on the shortest edge and at least 250,000 pixels of area, which between them
    reject a seal or a logo, and a long-to-short edge ratio no greater than 3.0,
    which rejects a signature strip at any scanning resolution. All three are
    settings (`TTB_MIN_ARTWORK_EDGE_PX`, `TTB_MIN_ARTWORK_PIXELS`,
    `TTB_MAX_ARTWORK_ASPECT_RATIO`), and `TTB_MAX_ARTWORK_IMAGES` bounds how
    many are read. The ratio was added later in this release; see
    "Fixed: the label artwork is turned the right way and read in colour".
  - Extracted rather than rendered. A page rasterized at a fixed scale loses
    resolution the embedded picture already has and hands the engine the form's
    own printed captions along with the label text. The alternatives rejected,
    and why, are in ADR 0010.
- **A three-source precedence, reported per field.** Typed by the agent, then
  the document's text layer or form fields, then the embedded artwork, then
  absent. Artwork never overrides text, because a value the file states is read
  and a value off a picture is recognized. Every field says which of the four
  supplied it, in the response and on screen, and the artwork case carries a
  line telling the agent to check it.
- **An application document alone is now a complete submission.** Where the
  agent uploaded no photograph and the document carries readable artwork, the
  largest such image is the label side and the check runs. Where it carries
  none, the submission is refused with a message naming the missing piece and
  offering the photo upload, which is an FR-9 message rather than a validation
  error on a field.

- **A government warning that differs by one or two characters goes to a person**
  ([ADR 0012](docs/adr/0012-warning-near-miss.md)). The comparison is unchanged
  and still exact: a statement is a match only when it is identical to
  27 CFR 16.21 after whitespace normalization. What changed is what a very small
  difference is reported **as**.
  - The author's own artwork OCRs the statement with exactly one character
    wrong, `MPAIRS` for `IMPAIRS`. Reported as a flat mismatch, that tells an
    agent their label is defective when the truth is that the scan is imperfect.
  - A difference of at most `TTB_WARNING_NEAR_MISS_EDITS` characters, two by
    default, is reported as needing human review, with the exact character-level
    difference shown. **It is never a pass**: it is one of the two failing
    outcomes, and the reason says "This is not a match" in those words.
  - Anything beyond the threshold is still a mismatch. A capitalization failure
    on the prefix is never a near miss: it is a defect a person caught on a real
    submission, not something OCR produces from a compliant label.
  - The difference is shown on a mismatch too, because it is evidence either
    way, and each run is marked by text as well as by styling so the distinction
    survives greyscale.
  - **This is not a fuzzy match.** A fuzzy match would let a label through on a
    similarity score. Nothing here lets anything through; what changed is which
    sentence the agent reads and whether they are handed the difference to look
    at. The existing FR-5 fixtures are unchanged in outcome, and that is
    asserted.

- **A value read off the artwork is filled in, and never called a match**
  ([ADR 0013](docs/adr/0013-artwork-derived-values.md), FR-14). ADR 0010 put the
  artwork into the application side and let it stand in as the label side. Both
  are right on their own; together they produce a row that compares a value
  against the picture it was read from, and such a row always agrees.
  - The values are still filled, because asking an agent to hand-type what the
    tool has already read puts back the data entry the tool exists to remove,
    and on the batch path there is nobody there to type it.
  - A row whose application value came off the same artwork that supplied the
    label side reports a fifth outcome, `artwork_derived`, carrying no score. It
    is not a verdict about agreement; it says the value was read and that there
    was nothing independent to check it against.
  - The summary line stops saying "5 of 5 fields match" and says what is true:
    "3 of 3 verifiable fields match; 2 read from the artwork only". Where no row
    is artwork-derived the qualifier disappears and the line reads as before.
  - The state carries a word, "Read from the artwork", and a picture-frame
    silhouette no other outcome uses, before any colour (NFR-5). The row states
    its own source, "Label artwork (same source as the label)", on the row
    rather than in a footnote.
  - **The rule keys on provenance, not on a field name.** It covers whatever
    fields fell that way on a given filing, and it does not fire when the agent
    supplied a photograph: comparing that photograph against the filed artwork
    is two pictures and is reported as the real comparison it is. A batch row
    pairs a document with a label image (ADR 0009), so no batch row is
    artwork-derived.
  - **Only an agreement is relabelled.** Reading one picture twice can
    manufacture agreement; it cannot manufacture a mismatch, a review or a
    not-found. Every other outcome on such a row is left exactly as the
    comparison found it.
- **Presence is reported as a finding rather than as "not compared"**
  (FR-14, FR-1). 27 CFR 5.63(a)(3) and 4.32(b)(3) require alcohol content on the
  label and 5.63(b)(2), 4.32(b)(2) and 7.63(a)(5) require net contents, whatever
  the application form says. A label that carries neither the value nor a form
  value used to report "nothing to compare"; it now reports the finding, and the
  reason names the section and its carve-outs, including that net contents may
  be "blown, embossed, or molded into the container". All three sections fetched
  from eCFR on 2026-08-30.
- **The proof cross-check reads the label on its own** (FR-14, FR-7, A-12). A
  spirits label stating both a percentage and a proof states the same number
  twice, and whether they agree is a property of that label. The check now runs
  before the application side is considered, so a label that contradicts itself
  is reported whether or not anything was declared against it; it used to be
  silenced by a row that had nothing to compare. Its outcome is unchanged and
  still needs human review, as FR-7 and A-12 fix it; see
  [OQ-25](docs/OPEN_QUESTIONS.md).

### The limitation, stated rather than implied

Checking a label lifted out of an application against that same application is
a **self-consistency check**. It shows that the artwork on file carries the
mandatory elements and agrees with the typed form data. It shows nothing about
a physical bottle; verifying the bottle against the filing still needs a
photograph of the bottle. That sentence is in the parser's notes, in the
response as `self_consistency_note`, and once on screen above the result,
because a limitation that lives only in an ADR is a limitation nobody reads.

### Changed

- `POST /api/verify` takes one repeated `files` part. The older `image` and
  `application_document` parts remain accepted and are routed through the same
  classifier, so a caller written against v1.0 keeps working and a COLA PDF sent
  in the `image` part is now read as the application rather than as a label.
- `POST /api/verify` accepts a submission with no label picture at all, when the
  application document carries label artwork.
- The response gains `label_source`, `self_consistency_note`, `photos[].origin`,
  a per-value `source` on the parsed application block, and
  `artwork_images_found`, `artwork_images_read` and `label_artwork_available`.
  `application_value_source` gains `parsed_from_artwork` as a fourth value.
- Assumption A-17 is amended: two of the three values it records as "not items
  on the form" are recoverable from the artwork embedded in a filing.
- `frontend/src/components/ApplicationUpload.tsx` is replaced by `UploadPanel.tsx`,
  and the photograph slots from ADR 0007 are gone from the interface. Up to
  `TTB_MAX_LABEL_PHOTOS` pictures of one label are still read independently and
  merged; what has gone is the row of numbered slots and the agent having to say
  in advance which file is which.
- `samples/formmaker.py` can embed raster artwork into a synthetic form as an
  image XObject, so the new fixtures are still generated at test time and no
  real applicant's filing is committed.

- **One upload, sorted by the server**
  ([ADR 0011](docs/adr/0011-one-upload.md)). The single-label view has one file
  picker. It takes the label application, photographs of the label, or any mix,
  as PDFs or images, and the server decides what each file is **from the file
  itself** rather than from which control it arrived in.
  - The rule: a PDF by its header, or by its declared type; an image by whether
    its text carries a COLA form or Public COLA Registry marker, or reads as a
    filled-in form; anything else is a label picture; an image that will not
    decode is a label picture carrying its error.
  - The classification is reported per file, in `POST /api/classify` and on
    every verification response, so a wrong call is visible rather than silent.
    That was the failure the two pickers actually produced: a COLA PDF dropped
    into the photo picker was read as label artwork.
  - Each image is read exactly once. The OCR result from classifying is handed
    to whichever side the file lands on. Measured on a session runner:
    single-label verification stayed at about 1.5 seconds end to end.
- **The label image requirement is gone as a hard gate.** The check turns on as
  soon as anything is uploaded. Three submissions are valid and all three
  complete end to end: the application document alone, a label photograph plus
  typed values, or both. An application with no readable artwork and no
  photograph is refused with a message naming the missing piece and offering the
  photo upload, which is an FR-9 message rather than a validation error on a
  field.
- **The values that were read go quiet; the ones that were not go loud** (FR-13,
  US-26). Once an upload has been read, each value it supplied is a read-only
  line carrying the value and where it came from, and each compared value it did
  not supply is an editable field, shown. If it supplied all of them, no
  editable field is shown at all and one collapsed disclosure, "Review the
  values", holds them.
  - A gap takes focus, scrolls into view, and is announced: "Alcohol content was
    not found in your upload. Enter it, or upload a clearer image."
  - The two sections are decided when the upload is read, not from what is
    currently in the boxes. A field that moved between them as the agent typed
    would remount under them and drop focus after the first keystroke.
  - Beverage type keeps its own line with the ADR 0008 truth: read where the
    document states it in text, and otherwise reported as not read from the form
    because the product-type boxes are check marks, which a text layer cannot
    report. It is never compared, so it never takes focus and is never counted
    as a gap.
  - Before anything is uploaded the view is exactly what Session 10 left: one
    collapsed disclosure, no summaries of values that do not exist.
  - The result panel is unchanged. This is the input side only.
- `POST /api/classify` sorts an upload and reads the application side without
  comparing anything. It exists for the interface, in the same sense
  `POST /api/read-application` does: the parsed values have to reach the agent as
  editable fields before the comparison runs.

### Changed: the interface stops talking about taking a picture

- **The heading is "Upload. Read. Check."** (US-27). It read "Point. Upload.
  Check.", transcribed in Session 9 from a pattern written for a phone camera.
  This application has no camera. Nothing is pointed at anything; a file is
  chosen and uploaded, and the first word described a capability the tool does
  not have.
- **The rule applied across the sweep is narrower than "remove the word
  photo".** A word that implies the tool takes the picture goes. A word that
  names a file the agent already has stays: "photo", "photograph" and "scan"
  are all correct as nouns for something being uploaded, and replacing them
  would make the copy vaguer without making it truer.
- Strings changed: the `LABEL SCANNING` kicker is now `LABEL CHECK`; the batch
  results kicker says `READING` rather than `SCANNING` while the stream is
  open; "Upload the label application, a photo of the label, or both" is "an
  image of the label", in the upload heading, the results empty state, the
  disabled-check hint and the API's own `no_files` message; "PDFs and photos"
  is "PDFs and images", and "a photo shows us what it does say" is "an image of
  the label shows us what it does say"; "One photograph for each label" on the
  batch picker is "One image for each label"; "upload a clearer picture" is
  "upload a clearer file"; "Try a clearer photo" is "Try a clearer image" on
  both unreadable-image messages; a file classified as the label side is a
  "Label image" rather than a "Label picture"; "the way we read a label photo"
  and "the same reading we use on a label photo" both say "label image"; "you
  do not have to add a photo" says "add an image"; and the API's
  `no_label_to_check` message says "Add an image of the label".
- Strings deliberately kept, and asserted so a later sweep does not take them:
  "Try clearer photos, in better light" for a submission where every photograph
  failed, because those are the agent's own photographs and retaking them is
  the right advice; "a photo or scan of the form" and "A PDF, or a scan or
  photograph of the form", because both name files an agent holds; "Your
  photos", "Photo 2" and "Read from photo 2"; and "it was saved sideways by the
  camera", which is a fact the EXIF tag states about the file.
- **The viewfinder brackets are gone; the preview stays.** The four gold corner
  brackets around the chosen file failed the same test the heading did: corner
  brackets mean align the subject here and the device will capture it, and by
  the time that panel renders the file has been chosen, uploaded and read. The
  frame, the image and the caption stay, because the reason they exist is good
  and unrelated: before them, an agent who chose the wrong file could not tell
  until the results came back. The `scan*` class names are now `preview*`, the
  batch progress line's `scanning*` classes are `reading-line*`, and the
  viewfinder kicker glyph is replaced by a label glyph, so the code stops
  calling it a scan too.
- Everything from Session 9 that does not concern capture is untouched: the
  palette, the pill controls, the key-value result rows, the status chips, the
  persistent prototype banner and its exact wording, and the footer.
- Regression-gated as always: axe green over the built page including the
  removed brackets and the new heading, the computed-contrast check green, the
  keyboard walk unchanged, and the live-region announcements updated to the new
  strings.

### Documented, not built

- **A judged scope line on bottle photography**
  ([02_PROJECT_SCOPE.md](docs/02_PROJECT_SCOPE.md) section 6), answering the
  author's question: "Should I even be contemplating a label on a bottle, or is
  everything coming through COLA?"
  - **The input that works is flat label artwork**: the images filed with the
    COLA application, and photographs of flat labels or of a label lying flat.
    Every measured performance and accuracy figure in this repository came from
    that input.
  - **The input that does not work reliably is a photograph of a label still
    wrapped on a round bottle**, with three findings from the 2026-08-29 mezcal
    test stated as evidence: the GOVERNMENT WARNING block is printed at 90
    degrees to the body copy so no single global rotation makes both upright; a
    4 by 5 rotation and page-segmentation sweep over the isolated warning crop
    returned `4 AANDVW 1AG` at 2.1 percent similarity; and the real COLA gives
    Brand `DEL MAGUEY` and Fanciful `VIDA` while the largest text is "Vida
    Clasico", so the type-size heuristic is wrong on a real product even with
    perfect OCR.
  - **The decision:** bottle photography stays in the prototype as a best-effort
    path with honest failure reporting, and is not claimed as a supported
    capability. It is not removed, because an agent standing at a bottling line
    has nothing else; it is not promised, because the evidence says that would be
    a false promise.
  - The four things that would make it work are named with their costs:
    per-text-block orientation detection, cylindrical dewarp, multi-photo
    stitching (ADR 0007 exists, stitching does not), or a vision model, which is
    SG-2 and carries the FedRAMP and data-handling questions already recorded
    there.
  - Cross-linked from assumption SG-1's discussion in
    [ASSUMPTIONS.md](docs/ASSUMPTIONS.md) and from the traceability matrix. **No
    code changed and no capability is claimed.**
- **ADR 0009 answers the batch question this release raises.** A batch row still
  requires its label image, because rows are enumerated from the images so the
  stream can report a total before any document is read. What a batch does get:
  a paired document's embedded artwork now fills application values its text
  layer left empty. The simplification left on the table is named as such.

### Fixed

- **`elapsed_ms` is elapsed, and the interface stops inventing an explanation
  for the difference** (NFR-1). The field was measured inside
  `verify_photos`, which starts after the multipart form is parsed, after the
  files are classified and after the COLA document is read. On the
  application-document path those three are most of the request. Measured
  against the deployed build on 2026-08-30 with the author's own mezcal COLA
  PDF, `elapsed_ms` and `ocr_ms` came back within 2 ms of each other on all
  three runs: the field was reporting the label-side OCR span and calling itself
  the request.
  - The panel then printed the browser's wall clock, subtracted that figure and
    told the agent the remainder was "sending the image and receiving the
    answer". A control POST of the identical 382 KB file to a path that
    processes nothing crossed the wire in 68 to 111 ms, and a health round trip
    took 18 to 25 ms. About 3.5 seconds of real server work per request was both
    missing from the instrumentation and mislabelled as network time.
  - `elapsed_ms` now starts on entry to the handler and stops when the response
    is built. The response carries a `timings` block whose phases are each
    measured by a timer around the work they name: sorting the upload, PDFium
    work, page OCR, artwork OCR, label OCR, and the comparison. The phases are
    disjoint, and what no timer covered is reported as `unaccounted_ms` rather
    than attributed to whichever phase is nearest.
  - The panel reports the wall clock and the server's total and names their
    difference as time in the browser and on the network, which is a location
    rather than a mechanism. The phase breakdown is on the page behind a closed
    disclosure.
  - A batch line gets its own recording per row, so its figures are that row's
    work rather than a share of the batch's.

### Performance

- **The label artwork is read once instead of twice** (NFR-1). The honest
  measurement above exposed it immediately: the picture chosen as the label side
  is by construction a picture the document parser has just put through the OCR
  pipeline to fill the application values, and the label side was putting the
  identical bytes through the identical pipeline again for an identical result.
  The read is now handed on, the same way ADR 0011 already hands on the
  classifier's read.
- **Reading stops once every value has been found.** A further embedded picture
  can only add a value no earlier picture showed, because values are taken in
  size order and never overwritten. Once all four are in hand the remaining
  passes cannot change one thing in the response, so they are not run. The
  front-and-back case ADR 0010 reads several pictures for is untouched: a
  largest picture that answers only some of the four does not trigger it.
- Measured on a session container, which is not production hardware and is
  quoted only as a before-and-after on one machine: a one-image document went
  from **2.19 s to 1.12 s** and a two-image document from **3.17 s to 1.15 s**,
  with Tesseract passes going from two and three respectively to **one**.

### The acceptance criterion this release reported missing, and then re-measured

**The application-document path measured 6.8 s against NFR-1's roughly five
seconds** on the deployed target on 2026-08-30, build 1.1.0 as first deployed,
with the author's own mezcal COLA PDF submitted alone: 6883, 6786 and 6781 ms
over three runs. The image path meets NFR-1 at 1.5 s and is a different path;
one number covering both would be a claim about neither.

That entry said the figure would stand until the same document was submitted to
the deployed URL on a build carrying the fixes above, because halving the OCR
passes on hardware where each took about 3.3 seconds *should* land near 3.5
seconds and "should" is arithmetic rather than measurement.

**It was submitted, against deploy #11, the same day, the same URL, the same
document.** Three consecutive runs:

| run | wall clock | server `elapsed_ms` | `unaccounted_ms` | `ocr_passes` |
| --- | --- | --- | --- | --- |
| 1 | 3468 ms | 3387 ms | 1.3 ms | 1 |
| 2 | 3505 ms | 3411 ms | 1.3 ms | 1 |
| 3 | 3543 ms | 3463 ms | 1.3 ms | 1 |

**NFR-1 is met on this path at about 3.5 s, with about 1.5 s of margin.**
`elapsed_ms` now sits within 80 ms of the browser's wall clock instead of 3.5
seconds away from it, `unaccounted_ms` of 1.3 ms is what says the phase
breakdown covers the request rather than a part of it, and `ocr_passes` reads 1
against the 2 the same document paid before. The traceability matrix row, the
README performance section and `docs/09_DEPLOYMENT.md` section 9 all carry these
figures with the date, the build and the sample named. OQ-26 is closed with
them.

**One caveat, recorded rather than assumed away.** Those runs were taken while
the artwork OCR on this document was still failing: the label was being turned
180 degrees on an orientation verdict of 0.03 confidence and then flattened to
grayscale, so the 3.5 seconds was the cost of reading a wrongly turned, wrongly
rendered image. The fixes below change what is read. **It was re-measured, and
it moved: 5.0 s against deploy #12 the same day.** See "Changed" at the end of
this release for the figures and for what consumed the margin.

### Fixed: the label artwork is turned the right way and read in colour

The same document, on the same deploy, still read `AMoviy TS` for `DEL MAGUEY`,
`CLI).` for the class, and did not find the government warning at all. Three
causes, one branch, and each was a number that looked confident about text it
had never seen.

- **An orientation verdict of 0.03 confidence was applied on trust, and the
  floor to reject it already existed.** `LOW_ORIENTATION_CONFIDENCE` has been in
  `app/ocr.py` since v1.0.1 and was only ever a caption: the response said the
  engine had guessed, and the rotation was applied regardless. Below the floor
  the verdict is now scored against its own opposite by mean word confidence and
  the better one is kept.

  This refines [ADR 0003](docs/adr/0003-local-ocr-default-bedrock-optional.md)
  rather than contradicting it. Its 46 of 48 for OSD against 7 of 48 for a
  four-rotation sweep stands untouched, and above the floor OSD still decides
  alone. What the 7 of 48 hides is *which* cases the sweep loses: it loses the
  quarter-turns, because Tesseract corrects those itself and returns identical
  output either way, so the score is equal on the two cases it would have to
  separate. On this very artwork it separates 0 from 180 by more than fifty
  points. Two rotations, never four, and a tie leaves the engine's answer
  standing. A-15 carries the refinement.
- **Flattening a coloured label to grayscale dropped an entire ink class, and
  mean word confidence could not see it**
  ([ADR 0014](docs/adr/0014-colour-as-an-ocr-candidate.md)). Filed artwork
  carries dark-on-light and light-on-dark text on one ground; a threshold
  separates two luminance classes, not three. On this artwork the colour image
  read 257 words at 89.1 including `42% ALC BY VOL`, and the grayscale read 106
  at 89.9 without it: the arm that lost a required field scored *higher*,
  because a word that was never read lowers no score.

  The colour image is now a first-class candidate and on a coloured source it is
  read first. Ranking stays mean word confidence; ties inside one point are
  broken by how much text was recovered, which never overrides a real difference
  in confidence and fires on no case in the twelve-label sample set. Whether a
  source has colour to lose is measured as chroma rather than assumed from the
  channel count, so every image in the sample set and every grayscale scan takes
  the v1.0.1 path at the v1.0.1 cost. A coloured label that reads cleanly now
  costs one Tesseract read where this document paid two.
- **The embedded-image floor was made only of absolute sizes, and a signature
  clears them at a better scanning resolution.** The author's signature sits on
  page 2 at 687 by 195 and is rejected twice over; the same strip at 300 dpi is
  about 2000 by 580 and clears both. A long-to-short edge ratio above 3.0 is now
  rejected too (`TTB_MAX_ARTWORK_ASPECT_RATIO`), which is the one part of the
  floor a better scanner cannot defeat. Every rejection is reported with its
  page, its size and a named reason. The picture never is: not to the response,
  not to a log, not to disk.

`ocr_passes` still counts pictures. `tesseract_reads` is added beside it,
because every arm above happens inside one pass, and a release that tripled the
engine invocations while the reported pass count held at 1 would be the same
mistake the timing finding above was.

### Known limits

- The size floor is a judgement about what a filing looks like, not a
  measurement of one. Which form editions embed their artwork, and what pixel
  sizes real embedded label images span, is [OQ-24](docs/OPEN_QUESTIONS.md#oq-24).
- The batch path is unchanged: a row still requires its label image, because
  rows are enumerated from the images so the stream can report a total before
  any document is read. The reason, and what it would take to change, is in
  ADR 0010 under "Effect on the batch path". The batch also keeps its two named
  parts rather than folding into one; ADR 0011 records why the two paths differ.
- A label picture is read twice on the interface path, once to classify it when
  the agent chooses it and once to check it when they press the button. The
  agent's wait for the check is unchanged, because the first read happens while
  they are still working; what it costs is server CPU. An API caller sending
  everything to `POST /api/verify` in one request pays it once.
- The classification can be wrong. A photograph of a label that prints "Alcohol
  and Tobacco Tax and Trade Bureau", which some labels do, would be taken for a
  form. It is reported per file and the agent can remove it; there is no silent
  path.

### Fixed: a sheet of several panels is read as several panels

The same document again, on deploy #12, with the orientation and colour work
above in place. The artwork read at 89.6 against 37.9, the alcohol content and
net contents were found, and three fields were still wrong. One cause, one layer
downstream: the filed artwork is one flat sheet carrying a left panel, a front
panel, a right panel and a narrow strip of type set at 90 degrees in each
gutter, and the reader was assembling its words into lines across the full width
of it.

| field | read as | should read |
| --- | --- | --- |
| brand name | the producer's tax identifier, off the vertical strip | `DEL MAGUEY` |
| class or type | the producer's street address, off the same strip | something containing `MEZCAL` |
| government warning | the statute with `ORIGEN PROTEGIDA` and `NOM-041X` spliced through it from the left panel | the statute, exactly |

- **The sheet is cut at its gutters before its words are grouped into lines.**
  A blank column of pixels that no word box covers is a gutter when it clears
  two conditions: 2.5 percent of the image width, and 1.25 times the largest
  type touching it. The three gutters on this artwork measure 63, 86 and 70
  pixels at the reader's 1600 pixel working width, which is 3.94, 5.38 and 4.38
  percent; the widest blank on it that is not a gutter is 28 pixels, 1.75
  percent.
  - The width share alone is not sufficient, and sample label 05 is the case
    that shows it: it sets `LANTERN HILL` in 75 pixel display type with a 53
    pixel word space in it, 4.97 percent of that label's width, wider as a
    share than two of the three real gutters. The type either side of a blank
    is what separates the two, measured on the shorter side of each word box so
    that a strip set sideways is measured by the same rule as the panels beside
    it. As a multiple of that type the three gutters are 2.17, 1.59 and 3.33
    and every non-gutter is 0.93 or less.
  - Words are then grouped inside a column by Tesseract's own block and
    paragraph, as they always were. Blocks alone were never sufficient here:
    on this artwork Tesseract returns blocks spanning x 44 to 1526 of a 1600
    pixel image, so `HECHO EN MEXICO` from the left panel and
    `long, smooth finish.` from the right one arrive in one block, one
    paragraph and one line.
  - Reading order is column by column and each column top to bottom, which is
    what lets the government warning be collected as a run of consecutive lines
    without another panel's words falling into the middle of it.
  - **This adds no Tesseract read.** Both segmentations are arithmetic on the
    word table the single existing pass already returns; nothing is cropped, no
    page segmentation mode changes, and nothing is read twice.
    `test_panel_segmentation.py` asserts the read count rather than arguing it.
  - A label with no gutter wide enough is one column and reads exactly as it did
    before this existed. All twelve sample labels are byte-identical, asserted
    against the previous grouping rule reproduced in the test rather than
    against a stored expectation.
- **The brand name and the class or type designation are ranked among upright
  regions only, and the ranking may now decline.** A word set at 90 degrees
  reports a box about one cap-height wide and one word long, so its height
  measures its length: on this artwork that made the producer's tax identifier
  the tallest text on the sheet at 81.5 pixels against a 43 pixel display line.
  Type set sideways is excluded from the size ranking and from nothing else.
  - And where the largest upright text is not clear of the next largest by 0.70,
    type size has identified nothing and the field reports not found rather than
    the winner of a photo finish (FR-1). On the twelve sample labels that ratio
    runs 0.46 to 0.64 and every brand name is still found. On this artwork it is
    0.83, and not found is the honest answer: the filing declares a brand name
    of `DEL MAGUEY` and a fanciful name of `VIDA` while the largest text on the
    artwork is `Vida Clasico`, so a largest-text rule is not merely
    inconclusive here, it is wrong here. The row says which of the two happened
    rather than reporting a bare not found.
- **Letter case joins whitespace as presentational in the FR-5 body
  comparison.** After the split, the statement on this artwork is 283
  characters in exactly the order 27 CFR 16.21 sets them, and the exact
  comparison still failed on 209 differences of which every one was a capital
  letter. 27 CFR 16.21 fixes the wording; 27 CFR 16.22(a)(2) governs the
  setting, and FR-6 checks the prefix separately and still case-sensitively. An
  altered, added or omitted word fails in either case, asserted in both, and the
  difference an agent is shown is still the label's own text because the fold is
  length-preserving and the diff segments are sliced from what was printed.
- **The browser stops posting values it read out of the document back as values
  the agent typed.** The five application boxes are filled from the uploaded
  COLA and the whole set was sent with the check. A value arriving in a typed
  part is a typed value, so `resolve_application` recorded all five as typed,
  which is the top of ADR 0010's precedence, and FR-14's circularity overlay
  could not see the two rows that were one reading of one picture compared with
  itself. Measured on 2026-08-30 with this filing: the alcohol content and the
  net contents came back as matches and the panel read "2 of 5 fields match.
  3 does not match." The API returns those rows correctly as `artwork_derived`
  when the browser sends nothing; the round trip was what broke it, which is
  why the accessibility fixture, which stubs the endpoint, could not catch it.
  The browser now sends what the agent typed, including anything they edited,
  and lets the server re-derive the rest from the document it is being sent
  anyway.

### Added

- `photos[].segmentation` on every photograph: how many columns the sheet was
  cut into, how many Tesseract blocks the words fell into, and the cuts
  themselves as pixel bounds. One column spanning the image is a sheet that was
  not cut at all.
- `fields[].label_region` on every field: which column and which block the value
  was read from, or null where it was not found on the label. An agent who sees
  a brand name should be able to see it came from the front panel, and an agent
  looking at a surprising value should be able to see it came from somewhere the
  value has no business coming from.

### Changed

- NFR-1 on the application-document path is re-measured and the figure moved.
  Against deploy #12 on 2026-08-30, the author's own mezcal COLA submitted
  alone: 4999 and 4992 ms wall clock, `elapsed_ms` 4928 and 4918 ms,
  `ocr_passes` 1, `tesseract_reads` 4. **5.0 s against a target of roughly five
  is at the line rather than under it, and it is published as 5.0 rather than
  rounded down.** About 1.4 s of the rise from the 3.5 s measured against deploy
  #11 is the 180-degree orientation check, which is the fix that made this
  document's readings correct at all. That is what consumed the margin, it was
  worth paying, and it is stated rather than smoothed over. A costed but unbuilt
  optimisation is [OQ-27](docs/OPEN_QUESTIONS.md#oq-27). The README,
  [09_DEPLOYMENT.md](docs/09_DEPLOYMENT.md) section 9, the traceability matrix
  NFR-1 row and [OQ-26](docs/OPEN_QUESTIONS.md#oq-26) all carry the new figures.

## [1.0.1] - 2026-08-29

Hotfix against the released v1.0.0, branched from `main` per the Git Flow path
in [docs/08_SDLC_PROCESS.md](docs/08_SDLC_PROCESS.md) section 2. It goes to
`main`, is tagged and published from there, and `main` is then merged back into
`develop`.

### The evidence

A photograph of a Ketel One vodka back label was submitted to the deployed
v1.0.0 build on 2026-08-28. The label is crisp and flat and carries the full
government warning in clear capitals plus `750 mL`. The build returned the brand
as `Sal.`, the class as shrapnel from the bottom fine print, net contents not
found, and the government warning not found, on a photograph the interface
flagged as saved sideways by the camera.

A controlled experiment against the deployed URL, with a screenshot of the same
label, isolated two behaviours. Upright pixels with no EXIF tag: plain Tesseract
on the file read the warning nearly perfectly, and the deployed build reported it
not found. The identical pixels turned 90 degrees counter-clockwise carrying
EXIF orientation 6, which is what a phone stores and what every browser displays
upright: the deployed build found no text at all.

### What was actually wrong, and what was not

**The EXIF transform was not wrong.** v1.0.0 already delegated the tag to
`PIL.ImageOps.exif_transpose`, and it is correct for all eight orientation
values: measured here on 2026-08-29, a fixture stored the way a file carrying
each value stores its pixels decodes to an array identical to the upright
original, for every value from 1 to 8. That is now asserted rather than assumed.
The report that orientation 6 was transposed wrongly is not reproducible, and
the blackout it describes has a different cause.

**The preprocessing was wrong.** Adaptive thresholding at a 31-pixel block
suits the printed artwork the sample set is built from and destroys a
soft-contrast photograph. Two consequences, and together they are the whole
failure. Tesseract's orientation detection was being asked about the thresholded
image, so on a photograph it was being asked about noise: over the twelve-label
sample set degraded into a photograph-like fixture and turned to all four
cardinal rotations, it answered correctly in 0 of 48 cases against 44 of 48 on
the grayscale. Having been turned wrongly, the destroyed image then read as
nothing. The EXIF-6 variant blacked out where the upright one merely read badly
because a re-encode after turning is enough to push a marginal image over that
edge.

### Fixed

- The orientation call is made on the upright grayscale rather than on the
  thresholded image. On rendered artwork the two are level, 45 of 48 against
  46 of 48; on anything resembling a photograph they are not.
- Preprocessing can no longer make a read worse than no preprocessing.
  `extract_text` reads the preprocessed image and, unless that read comes back
  at 85 or better, reads the plain upright grayscale too and keeps whichever
  scored higher. On the degraded sample label the preprocessed read scores 0.0
  and returns nothing where the plain read scores 90.9 and returns all
  sixty-two words including the full warning.
- The quarter-turn confidence check now demonstrably runs whether or not an EXIF
  tag was applied, and there is a test that fails if it stops. A tag is a claim
  about pixels that any edit can invalidate, so a file whose tag lies about its
  own contents is rescued by the same net that catches an untagged sideways
  photograph.

### Added

- `orientation.exif_orientation` on every photograph in the response: the tag
  value found in the file, 1 to 8, or null when none was carried. Reported
  beside `exif_transposed` and `rotation_degrees` so that all three figures are
  visible and their disagreement is legible. A non-zero `rotation_degrees` on a
  file that carried a tag now reads as what it is: the tag was wrong and the
  check corrected it.
- `read_path` on every photograph: which of the two reads was kept, and what
  each scored. `plain_confidence` is null when the preprocessed read scored well
  enough that the second one never ran.
- Tests, all generated at test time and none committed as a binary. A legible
  fixture stored under every EXIF orientation value 1 to 8, at the unit tier
  compared pixel for pixel against the upright original and at the integration
  tier asserted to find the government warning. A fixture whose tag lies about
  its pixels, rescued by the confidence check. A photograph-like fixture, soft
  contrast and slight blur and a little sensor noise, where the plain read beats
  the preprocessed one and the better result is kept, with a companion test
  asserting that the preprocessed image alone would have lost the warning. The
  existing synthetic set is unchanged.
- UAT rows 54 to 57 and traceability row 28h, recording the 2026-08-28
  submission and what it did and did not settle.

### Cost

The second read is skipped when the first scores 85 or better, which is eleven
of the twelve sample labels, so the ordinary per-label figure is roughly
unchanged: median 1,086 ms on v1.0.0 against 1,153 ms here. Where preprocessing
loses on every image, the photograph-like set, the median goes from 383 ms to
1,589 ms, about 1.5 times rather than double, because decode, scaling and the
orientation call are shared between the two reads. v1.0.0's 383 ms there is the
cost of returning nothing. Both are inside NFR-1's roughly five seconds. The
batch path inherits the cost, once per row.

### Deliberately not fixed

- **The blackletter logotype.** The brand on the front label of this product is
  a brand mark rather than type, and OCR does not read it. The front label also
  carries the brand in plain type, which is what ADR 0007's multi-photo path
  exists for. UAT row 57 tests the limit rather than a fix: the brand should
  report not found rather than shrapnel from nearby fine print.
- **Perspective and cylinder dewarp.** A label wrapped on round glass is
  SG-1 and is unchanged by this hotfix.
- **ABV on this label side.** The alcohol statement is on the front label of
  this product. Not found was the correct answer for the back label, and it
  stays the correct answer.

## [1.0.0] - 2026-08-28

**This section collects everything below it and is the release the author cuts
after the pull requests from 2026-08-28 merge.** It is dated when the tag is
created, not before. The version is bumped in `backend/app/__init__.py`,
`backend/pyproject.toml` and `frontend/package.json`, so the deployed build
identifies itself as 1.0.0 through `GET /api/health` rather than as 0.1.0, which
named a build from before most of what is in it. The release procedure, and the
fact that **publishing the release is what deploys rather than the tag itself**,
are in [docs/08_SDLC_PROCESS.md](docs/08_SDLC_PROCESS.md) section 7.

### Added

- **The batch takes COLA documents, and the CSV is gone** (FR-8 rewritten,
FR-11, US-9, [#70](https://github.com/kimkight/26-DO-12891471-DH_T_ITS_AI_THT/issues/70),
[ADR 0009](docs/adr/0009-batch-cola-documents.md), superseding assumption A-14).
The question this answers was the author's: why are we assuming the batch is a
CSV, and where would these CSVs even come from? The answer was already in the
repository. A-14 said "No source states this format; it is assumed." The CSV
existed because Session 3 needed some way to attach application data to 300
images before any COLA parser existed. Nothing an importer files with TTB
produces such a file: what they file is, per application, a COLA form plus label
images, and FR-11 can now read that form.

**A batch submission is label images plus COLA documents, paired by filename
stem.** `0001-stones-throw.png` pairs with `0001-stones-throw.pdf`: the stem is
the filename with its final extension removed, compared without regard to case,
and only the final extension is removed, so `0001-stones-throw.front.png` pairs
with `0001-stones-throw.front.pdf`. On the wire, repeated `images` parts and
repeated `application_documents` parts in one request to
`POST /api/verify-batch`. The rule is implemented once as `pairing_stem` in
`backend/app/batch.py` and mirrored in `frontend/src/lib/pairing.ts` so the page
can say what will pair before anything is sent.

**The CSV path is removed, not kept alongside.** Two input contracts would be
two things to build, test, document and explain, and the CSV's only origin story
was our own assumption: there is no population of users with CSVs to preserve
compatibility for. `parse_applications_csv`, the column contract and the CSV's
reconciliation errors are deleted. A-14 is marked superseded in
`docs/ASSUMPTIONS.md` rather than removed, with the original entry kept below
the line, because the history of why the CSV existed is the reason the
replacement is short. The alternatives rejected, one combined PDF of all the
forms and pairing on an identifier inside each document, are recorded in
ADR 0009 with what would make the second one right.
- The batch's plain-language error lines follow the contract change: the
CSV-row codes are gone and the five pairing codes ADR 0009 defines each have a
sentence of their own, naming the file the agent has to do something about. A
new test asserts that every batch code an agent can meet has a line rather than
falling through to the generic one, because a code the server emits and the
interface has never heard of reads as "we could not check this label" when the
real problem is a filename.
- Each batch row is verified against what its own document said. Every value on
that path is parsed rather than typed, so each row's result carries the parsed
block and says per field whether the document supplied the value or did not
carry it, exactly as a single-label submission with an attached document does. A
value the document does not carry is not compared, per FR-2, rather than
guessed.
- The beverage type for a row comes from its document, and where the document
does not state it the row says so. **No per-field comparison reads it**, and
that is now stated rather than implied: A-12's proof cross-check keys off a
proof statement the label itself carries and A-13's range handling keys off a
range in the value, so an unstated beverage type costs the comparison nothing.
It is carried because A-12 and A-13 name it as the class that would decide which
rule applies if a rule ever needed deciding.
- Pairing failures are per row, not per batch, which keeps FR-8's isolation rule
intact. An image with no document is `missing_application_document`; a document
with no image is `unmatched_application_document` on its own line; two documents
on one stem is `duplicate_application_document`; two images on one stem is
`duplicate_label_stem`; a document that cannot be read is
`unreadable_application_document`, naming the document. Only two refusals stay
at batch level, because there is nothing to attach them to: no images at all,
and no documents at all, whose message states the pairing rule.
- The batch view takes two pickers, label images and COLA documents, states the
pairing rule on screen rather than behind a disclosure, and works out the
pairing as soon as files are chosen. The count of pairs and of unmatched files
is shown and announced through a live region from the same sentence, so an agent
who has dropped 300 images and 299 documents finds out from the page rather than
from one error line 20 minutes into a run.
- `scripts/measure.py` grows a batch mode: `--batch --url "$URL"` submits a real
batch over HTTP under the new contract and prints total wall clock, per-label
time, when the first and last lines arrived, the spread between them, and the
counts by status and error code. The spread is the section 8.4 streaming check
in one number. `--copies 25` repeats the twelve-label sample set under fresh
stems, which is the 300-label batch at the configured cap that section 9 asks
for. It uses only the standard library, so nothing is added to either lock file.
- `samples/generate_samples.py` writes one synthetic Public COLA Registry
printout per label into `samples/applications/documents/`, named to pair with
its image. A printout rather than a blank TTB F 5100.31, because the form has no
item for three of the five compared values (A-17) and a batch of forms would
leave four of five fields with nothing to compare against. Git-ignored and
regenerated, like the artwork. `samples/applications/applications.csv` stays,
and is no longer an input to any API: it is the accuracy tier's application data
and the file the documents are written from.

- **The label application accepted as an input, instead of typed** (FR-11,
US-23, [#65](https://github.com/kimkight/26-DO-12891471-DH_T_ITS_AI_THT/issues/65),
[ADR 0008](docs/adr/0008-cola-form-as-application-input.md)). The question this
answers was the author's, while using the deployed prototype: why enter all this
information, when the applicant already submitted it? The five values the form
asks an agent to type are on the label application, TTB Form 5100.31, and on the
Public COLA Registry detail page for an approved one. An agent can now attach
that document instead.

**This is not the COLA system integration OOS-1 excludes**, and the boundary is
now written down rather than left to be inferred: a note under OOS-1 in
`docs/02_PROJECT_SCOPE.md` and a section in ADR 0008 state that the exclusion
covers API calls, COLAs Online authorization and registry lookups, and does not
cover reading a file the agent already holds. NFR-3 and NFR-6 apply to the
document exactly as they apply to a label image: nothing is fetched, nothing is
kept.
- Three ways into a COLA document, tried in order, because the document reaches
an agent in three shapes. **Form fields** first: a filled-in copy of the
downloadable PDF keeps its values in AcroForm fields, which is also the only
place a ticked checkbox can be read. **The text layer** next: COLAs Online
output and a Registry printout are digitally generated, so extraction is
deterministic, with no recognition step and no misread. **OCR** last, and only
when neither of the other two produced a single value: pages are rendered and
read through exactly the Tesseract pipeline label artwork goes through, bounded
by `TTB_MAX_DOCUMENT_PAGES`, defaulting to 3.
- **What the form does not carry, said out loud.** The blank form was downloaded
once during development and its items read off the file: TTB F 5100.31
(04/2023), OMB No. 1513-0020. Of the five values this tool compares, two are
items on the form and three are not. The brand name is item 6 and the beverage
type is item 5's three checkboxes. The class or type designation and the alcohol
content are not items at all, and the net contents is item 15 only when it is
blown, branded or embossed on the container and does not appear on the affixed
labels. Each of those is reported as not found **with the reason**, so an agent
is not sent looking for a box that does not exist. The fanciful name, item 7, is
read and reported and compared against nothing. The full map is assumption A-17.
- `POST /api/read-application`, which parses a document and compares nothing. It
exists for the interface rather than for the API: the parsed values have to
reach an agent as editable fields before a verification runs, and routing that
through `POST /api/verify` would mean submitting the label photographs and
running OCR over them once to read the form and again to run the check the agent
then asked for.
- An optional `application_document` part on `POST /api/verify`, with the
precedence rule ADR 0008 states: **any explicitly typed field overrides the
parsed value**, field by field, and a blank field is not a correction. Every
field result now carries `application_value_source`, one of `typed`,
`parsed_from_form` or `absent`, and the response carries the parsed application
data as a distinct block rather than folded into the comparison.
- **Parsed values are surfaced for confirmation, never silently trusted.** On
the single-label view, "Upload the label application (COLA form) instead" sits
alongside the typed fields. What comes back fills those same fields, each marked
"Read from the application form. Change it if it is wrong." Every field stays
editable, editing one clears its mark, and the check runs on what is in the
fields when the button is pressed. This is FR-3's philosophy applied one step
earlier: the tool reads, the agent judges.
- The upload is keyboard reachable in reading order between the photographs and
the fields it fills, labelled, and announced through its own live region rather
than the results one. An empty or unparseable document gets an FR-9 message
naming the problem, fills nothing in, and leaves the typed path open. The axe
run covers a form filled from a document, and the contrast check covers the new
mark through its class rather than only through its token.
- `pypdfium2` as a runtime dependency, with both lock files regenerated in the
same change and both audited in CI. One library rather than three: it reads
AcroForm values, extracts a text layer and renders pages, and it carries PDFium
as a wheel so nothing further is installed in the image. Licensed BSD-3-Clause
and Apache-2.0; PyMuPDF was rejected because it is AGPL.
- `TTB_MAX_DOCUMENT_PAGES`, defaulting to 3. The single-label request envelope is
now one more than `TTB_MAX_LABEL_PHOTOS` times `TTB_MAX_UPLOAD_BYTES`, 40 MB on
the defaults rather than 30 MB, because the request may carry the document as a
fourth upload. Every individual file is still checked exactly against
`TTB_MAX_UPLOAD_BYTES` after parsing.
- Assumption A-17 (the field map, and the three values the form has no item
for), open question OQ-22, UAT rows 31 to 35, and 43 backend tests across
`backend/tests/test_application_form.py` and `test_cola_document_api.py`, 21
frontend tests in `frontend/src/__tests__/applicationUpload.test.tsx`, one
accessibility test and one contrast assertion.
- **What is not claimed.** The parser has been exercised against documents
generated at test time by `samples/formmaker.py` and against the item map read
off the blank form. No real filed application and no real Registry printout has
been parsed, because committing one would put an applicant's record in this
repository. That is OQ-22, and it is why the README says the feature is
unverified on real documents rather than saying it works.
- **The batch path is unchanged.** It keeps the CSV contract in A-14. Per-row
COLA documents are a possible future extension and no part of them is built.

- The interface rebranded in federal design language, in the spirit of the
U.S. Web Design System: a navy masthead band (`#112e51`) ruled off in gold
(`#ffbe2e`), navy as the working primary (`#1a4480`), gold for edges and rules
(`#c05600`), neutral greys, white panels on a grey field, and a navy hairline
across the top of each panel. The masthead reads "TTB Label Verifier" with
"Alcohol and Tobacco Tax and Trade Bureau" above it as plain text styling only.
- Public Sans as the typeface, the face the U.S. Web Design System commissioned,
under the SIL Open Font License 1.1. It is bundled as a variable font through
`@fontsource-variable/public-sans`, a dev dependency, with
`frontend/package-lock.json` regenerated in the same change. It is served from
the application's own origin and never fetched from a CDN, because NFR-3 applies
to the page as well as to the API: a stylesheet linking a font CDN would break
the interface on exactly the firewall Marcus Williams describes, and would do so
silently. `system-ui` follows it in the stack, so a build whose font file failed
still renders in something sensible.
- **The disclosures that make the visual language legitimate rather than a
forgery**, and the tests that keep them. A banner is the first element on every
view, above the masthead, never dismissible: "Prototype built for an employment
assessment. Not an official TTB or Treasury system. Nothing you upload is
stored." The footer reads "Built by Kimberly D. Kight as a take-home
assignment." The document title carries "(prototype)", which is the one place
the page's own banner cannot reach.
- **What is refused, in code rather than in a person's memory.** No TTB seal, no
Treasury seal, no eagle, no coat of arms, and no "official website of the United
States government" banner appears anywhere in the repository. No raster or
vector asset is imported at all; the only SVG in the interface is the four
outcome glyphs, drawn inline.
`frontend/src/__tests__/branding.test.tsx` asserts both halves: that each
disclosure is present in the words it was written in and in the position that
makes it read first, and that none of the forbidden marks or phrases appears in
any source file the built page is assembled from. It strips comments before
scanning, so the comment explaining which marks are forbidden is not itself a
violation of the rule it explains.
- 15 new contrast assertions against the new tokens, in
`frontend/src/__tests__/contrast.test.ts`. **No threshold was changed.** The
gold exists in three tokens rather than one because one gold cannot do all three
jobs and pass: `#c05600` clears 3:1 as a rule and an edge but reaches only 4.03
against the grey surface as text, so `--gold-text` is the same hue darkened
until it clears 4.5:1 on both surfaces, and `--gold-bright` is checked against
the navy band, which is the only place it is used. The masthead, the page shell
and the prototype banner are each checked as surfaces in their own right.
- Two assertions in the same file that the stylesheet fetches nothing from an
external origin and names a fallback after the bundled font, and one in the
accessibility run that loading the built page issues no request off this origin
at all (NFR-3).
- Two accessibility tests against the built page: that the prototype banner and
the author attribution are visible and that the masthead carries no image or
inline SVG.

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
- 23 backend tests in `backend/tests/test_multi_photo.py` and 20 frontend tests
in `frontend/src/__tests__/multiPhoto.test.tsx`, plus two accessibility tests.
The suites are 188 backend and 81 frontend.

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

- **The first measurements taken on the deployed target, written into the
README as measurements** (NFR-1, NFR-2, DoD items 7 and 9,
[docs/09_DEPLOYMENT.md](docs/09_DEPLOYMENT.md) section 9). Until now every
figure in this repository named a session container as the hardware it came
from, and the README said so in place of a number. These name the deployed
target instead: 2026-08-28, build `sha-f66a4e2`, ECS Fargate with 1 vCPU and
8 GiB behind the Application Load Balancer in `us-east-1`, exercised from the
author's browser.

**One label, one photograph: 1.5 s end to end, 1.4 s of it inside the
checker.** The synthetic 1200x1600 fixture rotated 90 degrees, submitted with a
Public COLA Registry printout attached. All five fields matched and the rotation
was detected and reported. NFR-1's roughly five seconds is met with margin.

**One label, three real phone photographs of a round bottle: 7.8 s end to
end**, which is over NFR-1's target and is recorded rather than tuned away.
Brand name and class or type stayed unreadable on that bottle's curved glass and
came back as mismatch and not found. That is the SG-1 dewarping residual
[ADR 0007](docs/adr/0007-multi-photo-single-label.md) works around rather than
solves, reported honestly by the tool, not a defect in it. Both levers against
the latency are task environment variables and neither needs a code change:
`TTB_MAX_LABEL_PHOTOS` and `TTB_CORRECT_ORIENTATION`.

**A batch at the configured cap: 300 label images with their 300 paired COLA
documents in one submission, approximately 6.5 to 7 minutes, roughly 1.3 s per
label.** 300 of 300 rows returned, no timeout and no lost work. Results streamed
progressively through the load balancer, with 83 labels complete at the 109
second mark observed live, which is the direct answer to the ADR 0006 question
of whether an intermediary would buffer the stream. NFR-2 is met. The prior
claim scaled 12 and 100 labels to 300 arithmetically; that arithmetic is now
replaced by a run.

**Accuracy on the synthetic seeded set: 300 of 300 outcomes correct.** 270 fully
matching, 30 not matching, 0 needing review, 0 unreadable, and the 30 were
exactly the 30 seeded ABV defects in the fixture set. Every seeded defect caught,
zero false alarms. The README publishes it with the qualification section 5 of
[docs/02_PROJECT_SCOPE.md](docs/02_PROJECT_SCOPE.md) already states: accuracy on
a self-built sample is not accuracy on the real application population, and the
three-photograph run above is the counter-example measured on the same day.

**One figure is missing and is written as missing.** The CloudWatch
`MemoryUtilization` peak for the batch window is being retrieved. The README
says "memory utilization measurement pending" and section 9 leaves that box
unchecked, rather than carrying an estimate dressed as a measurement. It is the
number that would replace the two estimates in `09_DEPLOYMENT.md` section 4.3.
- The deployment runbook records the evaluation window. `terraform destroy`
remains the resting state of the stack and the posture is unchanged; the one
standing exception, now written down in
[docs/09_DEPLOYMENT.md](docs/09_DEPLOYMENT.md) section 10, is that the stack
stays up from submission until the author confirms the assignment has been
reviewed, and the destroy runs once that confirmation is in.
- Dependabot [#67](https://github.com/kimkight/26-DO-12891471-DH_T_ITS_AI_THT/pull/67)
and [#68](https://github.com/kimkight/26-DO-12891471-DH_T_ITS_AI_THT/pull/68)
are closed out in [docs/DEPENDENCY_TRIAGE_2026-08.md](docs/DEPENDENCY_TRIAGE_2026-08.md).
Both were merged by the author on 2026-08-28, in the order the sixth triage
recommended, and each subsection now ends with the merge commit that closed it.

- **The application document comes first, and the typed fields are behind a
disclosure** (FR-11, FR-2, FR-9, NFR-4, NFR-5, US-24,
[#74](https://github.com/kimkight/26-DO-12891471-DH_T_ITS_AI_THT/issues/74)).
The author's question, from using the deployed prototype: when would the typed
fields actually be used? Walked through from the agent's chair, the answer is
almost never as a starting point. The normal case is an agent holding the COLA
document, and then the five fields are a confirmation surface rather than a
data-entry task. The layout said the opposite. Five empty text boxes greeted the
agent and the upload was styled as the alternative, worded "instead". It is
inverted.

**The upload is the primary application-side input on the single-label view**,
directly after the photo picker, and no longer framed as the alternative to
typing. FR-11's title changes with it, from "accepted as an input, instead of
typed" to "the input, with typing as the fallback", because which one is the
default is a requirement rather than a layout preference.

**The typed fields live under "Or type the application values", collapsed by
default, and open in exactly three cases.** The agent opens the disclosure, with
no document at hand. A parsed document leaves gaps, which is the normal outcome
rather than an error: TTB F 5100.31 (04/2023) has no box for the class or type
designation or the alcohol content at all and carries the net contents only when
it is blown, branded or embossed (A-17), so the fields appear with the parsed
values filled and the gaps empty. Or a document fails to parse, and the fields
open as the fallback FR-9's message already promised. A document that supplies
every value opens nothing, because there is nothing left to enter. Nothing but
the agent ever closes it, and no expansion moves focus: the parse can return
while the agent is reading something else, so each auto-expansion is announced to
a live region of its own instead.

**Parsed values keep today's behaviour exactly**, and there is no API change.
Shown filled, marked "Read from the application form", editable, and FR-11's
precedence unchanged: a typed value always wins, and the response still says
which it was.

**Beverage type is demoted.** It is never compared; it says which numeric rule to
expect and nothing else. It fills from the document when the document states it
and otherwise sits at the bottom of the disclosure, so it is no longer the first
field an agent meets. Written down while doing it, because the requirement text
and the engine did not quite agree: the rules key off the value rather than off
this control. A-12's proof cross-check fires when the label itself states a
proof, and A-13's range handling fires when the value carries a range. The rule
that actually ran is named in the field result's own reason line, which is where
an agent reads it.

**Accessibility is regression-gated as always.** The disclosure is a button with
`aria-expanded` and `aria-controls` rather than a styled `<details>`, because the
open state has to be settable from the two document cases as well as from the
control. Collapsed, the panel is `hidden`, so the five fields leave the tab order
and the accessibility tree together rather than one without the other. axe-core
runs over the built page in both states, the keyboard walk covers the control and
its visible focus, and outcomes keep text plus shape.

The batch tab is untouched: it has told this story since ADR 0009, taking
documents only and asking for no typing. The single-label empty state now tells
the same one, photographs then the application then check.

Nineteen new component tests in `frontend/src/__tests__/applicationFirst.test.tsx`
cover the collapsed default and the three expansion cases by name, and two new
accessibility tests cover the collapsed and expanded page and the gap case
end to end. The existing prefill and precedence tests are unchanged in behaviour.
UAT rows 46 to 53 carry the same cases for a person to run.
- **The application version is 1.0.0**, declared in `backend/app/__init__.py`,
`backend/pyproject.toml` and `frontend/package.json`, so `GET /api/health`
reports the version of the build being reviewed. `frontend/package-lock.json` is
regenerated with it. The backend lock files were regenerated too and came back
byte-identical, because they carry no entry for the project itself and a
version-only bump does not move the resolved dependency set.
- `docs/08_SDLC_PROCESS.md` section 7 is corrected against the deploy workflow as
it exists rather than the workflow being changed to match it. Two things were
wrong. The section said the workflow triggers on the `v*` tag "once that workflow
is enabled"; the workflow is enabled, and it triggers on `workflow_dispatch` and
on `release` with `types: [published]`, never on a pushed tag. **Publishing the
release is what deploys, and a tag created without publishing deploys nothing.**
And the release procedure led with cutting a `release/*` branch, which v1.0.0
does not do: the version bump and the changelog section are prepared on
`develop`, and a release branch is now written as the exception it is, for when
`develop` has to keep moving while a release settles.
### Changed

- **The interface is modern, and the palette is not.** The author reviewed the
deployed USWDS-flavoured page and asked for something that reads as a working
instrument rather than a published form. The reference vocabulary is
transcribed from a product the author walked through on 2026-08-28, with its
colours substituted for the government ones.

What changed: content sits in white cards with 12 to 16 px radii and layered,
low-opacity navy shadows, floating over a muted blue-grey field, with no hard
black border anywhere. The two views are a segmented pill control on a pale
navy track rather than underlined tabs. Inputs have a soft tinted fill and a
large radius instead of a heavy outline, with the focus ring on the navy scale.
Primary actions are generous navy pills; secondary actions are bordered white
pills. Card titles are short declarative sentences under small-caps,
letter-spaced kicker labels with a leading icon. Notices are soft-tinted
rounded panels. The masthead is a deep navy band over the light content area,
carrying exactly one gold-highlighted phrase, "You decide."
- **The single-label view got the pattern that maps onto this tool.** The chosen
photograph now previews inside a scan-frame panel with gold corner brackets, and
the per-field results render as key-value rows: the outcome chip leads the row,
the field name follows, and the two values sit as a muted label on the left and
a bold value on the right. The preview earns its place beyond looking like a
scanner: before it, an agent who chose a file got the filename back and nothing
else, so a photograph of the wrong bottle looked exactly like a photograph of
the right one until the results came back.
- **The batch view became a live scanning widget.** A pulsing status line while
the NDJSON stream is open, rows arriving one at a time, and a running total
pinned under them: "3 of 3 checked, 1 mismatch". Presentation only. The stream,
the progress element and the live-region announcements are unchanged.
- Rounded-square icon tiles head the feature areas, and small rounded chips
carry counts and states: "1 of 3 chosen", "Read from the application form",
"3 pairs ready to check". Every chip is text first, so each reads correctly with
its colour removed.
- **Inter replaces Public Sans**, bundled as a dev dependency and served from
this origin, with the lock file regenerated in the same change and the system
stack behind it. No CDN font and no external request: NFR-3 covers the page, and
the accessibility run asserts it. Public Sans is the U.S. Web Design System's
own commissioned face, and once the surface stopped being a USWDS-flavoured one,
keeping its typeface was the last thing claiming a lineage the page no longer
has.
- **What did not change, and is regression-gated so it cannot.** The palette
stays navy and gold. There is still no TTB or Treasury seal, no eagle, and no
official-government banner; the persistent prototype banner carries the same
wording, stays at the top of every view, and is still not dismissible, now as a
soft gold-tinted panel; the footer still names the author and the assignment.
The computed-contrast test passes against the new tokens, which were changed
until they passed rather than the thresholds being moved: the greys went onto a
blue axis and the gold text darkened a step to hold 4.5:1 against the new tints.
axe is green over the landing page, the batch view and a rendered result set;
the keyboard walk passes; outcomes keep their text-plus-shape encoding; the
live-region announcements are unchanged.
- `docs/DEPENDENCY_TRIAGE_2026-08.md` gains the sixth Dependabot run:
[#67](https://github.com/kimkight/26-DO-12891471-DH_T_ITS_AI_THT/pull/67), `@types/react-dom` 19.2.4 to 19.2.5, and
[#68](https://github.com/kimkight/26-DO-12891471-DH_T_ITS_AI_THT/pull/68), `hashicorp/setup-terraform` 3 to 4. **Both recommended for
merge, and neither merged or closed by the triage**, which is the standing rule
in that document. #67 is a types-only patch verified on this session's tree
rather than only on the one it was opened against, because two branches here
change the files it touches and it will need a rebase. #68 is a CI action major
whose one upstream breaking change is a Node 24 runner requirement, and the
green job on its own pull request is the job that uses the action, which is the
same evidence that carried the action bumps in the first triage.
- The batch results table's header row was misaligned: the sortable headers
supplied their own padding through their buttons and the one header without a
button, "Detail", had none, so it sat hard against the top of the row. The cells
carry the padding now and the buttons fill them. The progress element was
drawing Chromium's default green bar, which belonged to no part of this palette;
its track and value are set explicitly for both engines.
- The batch envelope limit the application *derives* doubled, from
`TTB_MAX_BATCH_FILES * TTB_MAX_UPLOAD_BYTES` to twice that: about 6 GiB on the
defaults rather than 3 GiB. A batch carries one label image and one COLA
document per label now (ADR 0009), and each of the two is an upload bounded by
the same per-file limit.

**The deployed task does not follow that, deliberately.**
`infra/terraform/ecs.tf` pins `TTB_MAX_BATCH_BYTES` at 3 000 MiB, a figure
chosen from the memory budget of an 8 GiB task rather than from the file count,
and an 8 GiB task cannot hold a 6 GiB payload. So the deployed envelope is
unchanged and the effect of ADR 0009 there is a refusal rather than more memory:
a batch whose files total more than 3 000 MiB is rejected from its
Content-Length before the body is read, with the limit named. That is the safe
failure, and in the ordinary case it costs nothing, because the document is the
small half of each pair. `docs/09_DEPLOYMENT.md` section 4.4 writes out the
reasoning, and section 9 says to read the real figure off CloudWatch
`MemoryUtilization` rather than estimate it.

- **The batch path stays at one photograph per row.** ADR 0007 does not extend
to it this session: the A-14 CSV keys application data on one image filename, so
a row covering several photographs would need a different column shape, a
reconciliation rule for a partly matched group, and an answer for what a per-row
error means when one photograph of three failed. None of that is difficult and
none is asked for by any source. It is stated in the FR-8 notes and in ADR 0007,
and asserted in `test_multi_photo.py::TestTheBatchPathIsUnaffected` so it cannot
change unnoticed. (The reasoning is now stated against the pairing contract
rather than the CSV, since ADR 0009 replaced it later in this same unreleased
block. The limit itself did not change: two images on one stem are an error.)

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

- PDFium is not thread-safe, and the batch path reads COLA documents in a worker
pool. Reading two at once segfaults the process, which takes the NDJSON stream
and every completed result with it: a whole-batch failure NFR-2 forbids and one
no per-row error can catch, because the process is gone. It was found the first
time the new batch tests ran. Every call into PDFium is now made under one lock
in `backend/app/application_form.py`, and the document is closed explicitly
under that lock rather than left to a garbage collection that could run on
another thread. The OCR fallback is deliberately outside the lock: pages are
rendered to bytes under it and read by Tesseract after it is released, so a
batch of scanned documents still spends its expensive step in parallel. This is
the same shape of problem as the OpenMP one in `backend/app/ocr.py`, found the
same way: a library that is fine on the single-label path and not fine in a
pool.
- A Public COLA Registry printout left a caption word inside the class or type
designation it supplied. In the author's deployed-target test on 2026-08-28, a
printout carrying the line `Class/Type Description: Kentucky Straight Bourbon
Whiskey` produced the class or type value `Description: Kentucky Straight
Bourbon Whiskey`, and that is what the label was compared against. The caption
pattern matched `Class/Type` and stopped there, so the rest of the caption
became the head of the value.

After a value caption matches, a residual caption word at the front of what is
left, `Description`, `Designation` or `Code`, and its separator, are now removed
before the value is taken. The rule is applied where the caption matched rather
than by lengthening each caption pattern, because those three words attach to
more than one caption and no value is one of them on its own; it is anchored, so
a value that merely contains one of the words keeps it. A printout that splits
the code onto its own `Class/Type Code:` line is read too, and the code is still
reported beside the designation rather than in place of it. This is a defect fix
against FR-11 and A-17, covered by
`backend/tests/test_application_form.py::TestARegistryPrintoutWithDescriptiveCaptions`
and `::TestCaptionResidueInGeneral`, and by UAT row 36.
- The alcohol content was read from any percent on the label, including one in
marketing copy. In the author's three-photograph bottle test against the
deployed prototype on 2026-08-27 the field came back as `7%`, taken from a
sentence on the back label about reducing environmental impact, because the
pattern accepted any percent token in reading order. A candidate now counts
only where the OCR line carrying the number also carries an alcohol marker:
`ALC`, `ALC.`, `VOL`, `VOLUME`, `ABV`, `ALCOHOL` or `PROOF`, case-insensitively.
`VOLUME` is admitted with `VOL` because it is the same word spelled out.

The marker has to survive OCR; the words around it do not, so
`12.5% AlC. 8Y VOL.` still reads. A number with no marker on its line and a
marker with no number on its line are both reported as not found, which retires
the old behaviour of reporting a bare `ALC./VOL.` with no figure in it as the
alcohol content. This is a defect fix against FR-1 and FR-7, not a new
requirement: the FR-7 acceptance criteria now state the rule, UAT row 30 tests
it against a real bottle, and seven tests in
`backend/tests/test_parse.py::TestAlcoholContentNeedsAnAlcoholMarker` cover it.
The residual risk, a line carrying both an unrelated number and a marker word,
is narrower than the risk it replaces and is stated rather than claimed away.
- Two stale counts in `docs/TRACEABILITY_MATRIX.md`, corrected to what the
suites report: 195 backend tests and 110 frontend tests.
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

[Unreleased]: https://github.com/kimkight/26-DO-12891471-DH_T_ITS_AI_THT/compare/v1.0.1...develop
[1.0.1]: https://github.com/kimkight/26-DO-12891471-DH_T_ITS_AI_THT/compare/v1.0.0...v1.0.1
[1.0.0]: https://github.com/kimkight/26-DO-12891471-DH_T_ITS_AI_THT/compare/v0.1.0...v1.0.0
[0.1.0]: https://github.com/kimkight/26-DO-12891471-DH_T_ITS_AI_THT/releases/tag/v0.1.0
