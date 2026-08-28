# ADR 0006: Batch execution model

| | |
| --- | --- |
| Status | Accepted; the input contract half superseded by [ADR 0009](0009-batch-cola-documents.md) on 2026-08-28 |
| Date | 2026-08-22 |
| Author | Kimberly D. Kight |
| Decision reference | Implements FR-8 and NFR-2; constrained by D-9 |

> **What ADR 0009 changed, and what it did not.** The execution model decided
> here stands unchanged: one synchronous multipart request, a bounded worker
> pool, NDJSON streamed as each label finishes, no job store. What is superseded
> is what the request carries. The CSV contract below, marked `(Assumption)`
> A-14 when it was written, is replaced by label images plus one COLA document
> per label paired by filename stem. The sections below are left as they were
> written, because the reasoning they record is what made the replacement
> obvious once FR-11 existed.

## Context

Sarah Chen describes the problem this requirement exists to solve: "we get these
big importers who dump 200, 300 label applications on us at once. Right now we
literally have to process them one at a time." [Source: Sarah Chen interview]
She also names the original requester: "Janet from our Seattle office has been
asking about this for years." [Source: Sarah Chen interview]

The facts that constrain the design:

- **NFR-1 sets about 5 seconds for a single label**, from Sarah Chen: "If we
  can't get results back in about 5 seconds, nobody's going to use it. We
  learned that the hard way." [Source: Sarah Chen interview]
- **No source states a latency target for a batch.** This was recorded as OQ-6
  and is not invented here. What follows from the single-label figure is
  arithmetic, not a target: 300 labels at about 5 seconds each is about 25
  minutes of processing work.
- **Decision D-9 forbids persistence.** Nothing is retained beyond the request
  lifecycle, and there is no datastore, no authentication, and no user identity.
  [Source: Decision D-9; Marcus Williams interview, "We're not storing anything
  sensitive for this exercise."]
- **NFR-2 requires that a batch not fail as a whole**, and that "batch progress
  is observable to the user rather than presenting as a frozen page."
- **NFR-3 forbids outbound network calls on the default path**, because TTB's
  firewall broke a previous vendor's pilot. [Source: Marcus Williams interview]
- **A-1 sets the default batch limit at 300 files**, `TTB_MAX_BATCH_FILES=300`,
  taking the top of the range Sarah names. `(Assumption)`
- **OCR is CPU bound and runs in-process**, per
  [ADR 0003](0003-local-ocr-default-bedrock-optional.md). Concurrency is
  therefore bounded by available cores, not by network wait.
- **No source states how application data arrives for a batch.** For a single
  label the agent types the field values, per A-8. Typing them 300 times is not
  plausible, but nothing in the assignment names a format. This was recorded as
  OQ-16, and the format chosen below is marked `(Assumption)` A-14.

The tension is that D-9 forbids the persistence that an asynchronous job model
needs, while the arithmetic above rules out holding a single request open
sequentially for 25 minutes. The decision has to resolve that without inventing
a requirement.

## Decision

**Batch verification is a single synchronous multipart request** carrying up to
`TTB_MAX_BATCH_FILES` images plus one CSV of application data keyed by image
filename. **The server processes images concurrently with a bounded worker
pool** and **streams per-label results as newline-delimited JSON** so the client
can render progress as results arrive. **There is no job store**, consistent
with D-9.

Concretely:

- `POST /api/verify/batch`, `Content-Type: multipart/form-data`, with a repeated
  `images` part and one `applications` CSV part.
- The file count is checked against `TTB_MAX_BATCH_FILES` and rejected before
  any file is read, as FR-8 already requires.
- Responses are `Content-Type: application/x-ndjson`. One JSON object per line,
  each naming the image filename it belongs to. Lines are emitted as each label
  finishes, not in submission order.
- Concurrency is a bounded pool sized from available CPU, since OCR is CPU
  bound. The bound exists so that 300 simultaneous Tesseract invocations do not
  exhaust memory.
- A per-label failure is a result line with an error, not a failed request. This
  is what FR-9 and NFR-2 require.
- Nothing is written to disk or to a datastore. The response stream is the only
  copy of the results.

### CSV contract `(Assumption)` A-14

**Superseded by [ADR 0009](0009-batch-cola-documents.md).** Kept as written, for
the history. The batch now carries one COLA document per label, paired by
filename stem, and the values below are read off that document by the FR-11
parser rather than typed into a row.

One header row, one row per image. Columns:

| Column | Meaning |
| --- | --- |
| `filename` | Must match the filename of one submitted image part |
| `brand_name` | Application brand name, compared per FR-4 |
| `class_type` | Application class or type designation |
| `alcohol_content` | Application ABV, compared per FR-7 and A-12 |
| `net_contents` | Application net contents, compared per FR-7 and A-13 |
| `beverage_type` | Distilled spirits, wine, or malt beverage |

`beverage_type` is in the contract because A-12 and A-13 need it. The proof
cross-check in A-12 applies to distilled spirits, and the range handling for
wine cites 27 CFR 4.36. Without the beverage class the tool would have to guess
which rule to apply, and guessing is the failure mode A-12 exists to prevent.

A row whose `filename` matches no submitted image, and an image with no matching
row, are both reported as errors on their own result lines rather than failing
the batch.

**This format is assumed, not stated by any source.** The assignment does not
specify it. It is recorded as A-14 in [ASSUMPTIONS.md](../ASSUMPTIONS.md), and
`samples/expected.csv` already uses a CSV keyed by image filename for the
accuracy tier, so the shape is at least consistent with the repository's own
test fixtures.

## Alternatives considered

### Alternative A: an asynchronous job model with a results store

Submit the batch, receive a job identifier, poll or subscribe for progress, and
fetch results from a results page that survives the submitting request.

**Rejected because it requires persistence, which contradicts D-9.** A job
identifier that means anything after the request ends implies stored state, and
D-9 states that nothing is retained beyond the request lifecycle. It also adds a
queue and a worker process to the deployment, and a second UI surface for
retrieving results, both of which are scope the assignment does not ask for.
With no authentication (D-9, OOS-2), a guessable job identifier would also
expose one agent's results to anyone who requested that identifier, which is a
new security property the prototype does not currently have to reason about.

This is the right model for production. It is recorded here as the expected
successor, not as a rejected idea: when persistence and authentication arrive,
the batch path should move to it, and this ADR should be superseded.

### Alternative B: sequential processing in one request

Process the images one after another and return a single JSON response at the
end.

**Rejected on arithmetic.** 300 labels at about 5 seconds each is about 25
minutes in one request. That exceeds default idle timeouts on every layer
between the browser and the application, including the AWS Application Load
Balancer default of 60 seconds
([ADR 0002](0002-compute-ecs-fargate-not-app-runner.md)), and it produces
exactly the frozen page NFR-2 forbids. It also discards all completed work if
the request fails at minute 24, which is the failure NFR-2 names explicitly.

Note that this was **not measured**. The 5 seconds is Sarah's stated target from
NFR-1, and A-7 records that treating it as a per-label figure is itself an
assumption. No timing run has been performed against real label artwork, because
no implementation and no sample set exist yet.

### Alternative C: many single-label requests driven by the client

Have the browser fan out 300 calls to the existing single-label endpoint.

Rejected because it moves the concurrency bound to the client, where it cannot
be enforced. The server would have no way to apply `TTB_MAX_BATCH_FILES`, no
way to bound simultaneous OCR work, and the CSV would have to be parsed in the
browser. It also makes the per-batch error reporting FR-8 requires into
something the client has to assemble, and it is not what "a single submission"
in FR-8 describes.

## Consequences

**Positive**

- No persistence, so D-9 holds and the deployment stays a single container with
  no queue, no worker, and no datastore.
- Progress is observable, satisfying NFR-2, because results stream as they
  finish rather than arriving in one block at the end.
- Wall-clock time for a batch is roughly the sequential time divided by the pool
  size, rather than the sum of every label.
- A per-label error is a line in the stream, so one unreadable image cannot fail
  the batch. This is FR-8 and FR-9 without additional machinery.
- The single-label and batch paths share the same verification core; the batch
  path adds a CSV parser, a pool, and a streaming writer.

**Negative**

- **A dropped connection loses the batch.** There is no server-side copy of the
  results, so a closed laptop, a lost network, or a proxy timeout at minute 20
  discards every completed result and the batch must be resubmitted from the
  start. This is the direct cost of having no job store, and it is the strongest
  argument for Alternative A once persistence is permitted.
- **The 300-file cap is a hard limit, not a soft one.** An importer submitting
  400 labels must split the submission by hand. FR-8 requires the rejection to
  name the limit, which makes the failure legible but does not make it less
  annoying.
- **The CSV contract has to be documented and kept in step** with FR-1's
  extracted fields. It is now stated in three places: this ADR, the FR-8
  acceptance criteria, and `samples/README.md`. Three copies drift. The
  requirement document is the one to correct first when they disagree.
- Streaming responses are harder to test than a single JSON body, and harder to
  consume from tools that assume a buffered response.
- A long-lived streaming response holds a worker for the duration of the batch,
  which affects how the service is sized. That interacts with OQ-13 item 6, the
  ECS task sizing, which is still open.

**Risks accepted**

- **No batch latency target exists.** OQ-6 asked whether one exists and the
  answer is that no source states one. This ADR therefore optimizes for not
  losing work and for visible progress, which are stated in NFR-2, rather than
  for a completion time, which is not stated anywhere. If Sarah or Janet later
  states a target, that is new information and may reopen the choice.
- **The CSV format is assumed.** If Janet's actual workflow produces a different
  artifact, for example an export from COLAs Online in a fixed layout, A-14 is
  wrong and the parser changes. The cost is contained: it is one input adapter,
  and the verification core does not depend on the format.
- **Pool sizing is unmeasured.** Bounding concurrency by CPU count is a
  reasonable default for CPU-bound work but has not been benchmarked, for the
  same reason as Alternative B: nothing is implemented and no sample set exists.

## What implementation changed, 2026-08-23

Recorded after FR-8 was built. The decision above stands; three things it stated
turned out differently, and one thing it could not have known.

**The path is `POST /api/verify-batch`, not `POST /api/verify/batch`.** A
sibling path rather than a child of the single-label one. The
`UploadSizeLimitMiddleware` matches paths to decide which envelope limit to
enforce, and the two routes need different limits: a batch envelope carries many
images plus a CSV, so measuring it against the per-image limit would reject every
batch of more than one file. A nested path invites a prefix match, and a prefix
match on `/api/verify` silently applies the single-file limit to the batch route.
Making them siblings makes the match exact and the mistake unavailable. This
supersedes the path written in the Decision section.

**Tesseract cannot be called from a worker thread with its default OpenMP
settings.** This is the fact the ADR could not have known, and it is the one
worth carrying forward. Tesseract is built against OpenMP, and its OpenMP runtime
deadlocks when the binary is invoked from any thread other than the process main
thread: the child process never exits and the request hangs rather than failing.
The single-label path never met it, because `POST /api/verify` is an async
handler and so runs OCR on the event loop thread. The bounded pool this ADR
specifies does not, and the first batch written against it hung.

`backend/app/ocr.py` now sets `OMP_THREAD_LIMIT=1` if it is unset. One thread per
invocation is also the right shape rather than merely the safe one: this design
already parallelizes across images, so letting each Tesseract also fan out across
cores would oversubscribe the CPU the pool is sized to. The measured cost to a
single label is small. **Anyone changing the concurrency model here should
re-read this paragraph first**, because the failure it describes presents as a
hang with no error, not as a crash.

**Pool sizing is still unmeasured as a tuning question, but it is no longer
unmeasured as an arithmetic one.** The ADR recorded "wall-clock time for a batch
is roughly the sequential time divided by the pool size" as an expectation.
Measured over the twelve-label sample set and a synthetic hundred-label batch,
throughput held roughly constant per label as the batch grew, which is what that
expectation predicts. The numbers are in the pull request that added the feature
rather than here or in the README, because they were measured on a session
runner and NFR-1 requires the hardware to be stated with the figure. Nothing has
been measured on the deployed target.

**Two limits exist now that the ADR did not name**, both defaulting to a derived
value rather than an invented one:

- `TTB_BATCH_WORKERS`, the pool size, derived from the cores the process may
  use.
- `TTB_MAX_BATCH_BYTES`, the largest batch request body accepted, derived as
  `TTB_MAX_BATCH_FILES * TTB_MAX_UPLOAD_BYTES`. At the defaults that is about
  3 GiB, and FastAPI has the whole envelope parsed before the route runs. That
  is a deployment input, not a memory guarantee, and it is recorded against
  OQ-13 item 6.

**One negative consequence is sharper than written.** "Streaming responses are
harder to test than a single JSON body" understated it. The harder part was not
the assertion; it was that a failure inside the stream presents as a truncated
response with no status code to carry it, because the status line is sent before
the first row is computed. `app/batch.py` therefore catches every exception per
row, including ones it does not anticipate, and turns it into that row's error.
A broad except is normally a smell; here the alternative is a silently short
stream.

## References

- [03_REQUIREMENTS.md](../03_REQUIREMENTS.md), FR-8, FR-9, NFR-1, NFR-2, NFR-3
- [04_USER_STORIES.md](../04_USER_STORIES.md), US-9, US-10, US-11
- [ASSUMPTIONS.md](../ASSUMPTIONS.md), A-1, A-7, A-8, A-12, A-13, A-14
- [OPEN_QUESTIONS.md](../OPEN_QUESTIONS.md), OQ-6, OQ-16, OQ-13
- [ADR 0002](0002-compute-ecs-fargate-not-app-runner.md), compute and timeouts
- [ADR 0003](0003-local-ocr-default-bedrock-optional.md), OCR in-process
- [samples/README.md](../../samples/README.md), the CSV contract as a fixture
- 27 CFR 4.36, wine alcohol content statements,
  <https://www.ecfr.gov/current/title-27/section-4.36>
- 27 CFR 5.65, distilled spirits alcohol content and proof,
  <https://www.ecfr.gov/current/title-27/section-5.65>
