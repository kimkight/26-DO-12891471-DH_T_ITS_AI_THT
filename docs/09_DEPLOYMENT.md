# Deployment

This is a runbook. It is written for one operator, at one machine, with
administrative credentials for her own AWS account. It was written before the
first apply and is kept as the procedure for the next one.

**The stack has been applied and the prototype is deployed.** The Terraform in
`infra/terraform/` was applied by the author on 2026-08-28 to one account in
`us-east-1`, and the deploy workflow has put releases behind the load balancer
since. Every number in section 5 is still an estimate from published list
prices, and every number in section 4 is still arithmetic; section 9 records
the measurements taken on the deployed target, and one of them, peak memory,
is still open.

## 1. What this builds

| Resource | Why |
| --- | --- |
| VPC, two public subnets, internet gateway, two security groups | Somewhere to put the task and the load balancer. No NAT gateway; see `infra/terraform/network.tf` for why. |
| ECR repository | The image the deploy workflow pushes. Scan on push, lifecycle policy keeping the last five images. |
| ECS cluster, task definition, Fargate service, one task | The application. Circuit breaker on, rollback on. |
| Application Load Balancer, target group, HTTP listener | The URL. Health check on `GET /api/health`. |
| CloudWatch log group | Container logs, seven-day retention. |
| IAM: task role, task execution role, GitHub OIDC provider, deploy role | The task runs with no permissions at all; GitHub Actions assumes a role scoped to this repository. No static access key exists. |

Only services on the AWS FedRAMP services-in-scope list are used, per
[ADR 0001](adr/0001-cloud-platform-aws.md) and
[ADR 0002](adr/0002-compute-ecs-fargate-not-app-runner.md): ECR, ECS on
Fargate, Elastic Load Balancing, CloudWatch Logs, IAM. That in-scope status is
still confirmed at deployment time and is not asserted here; see
[06_SECURITY_AND_COMPLIANCE.md](06_SECURITY_AND_COMPLIANCE.md) section 4.

## 2. Before you start

- An AWS account you have administrative access to, and credentials in your
  shell. `aws sts get-caller-identity` should answer.
- Terraform 1.6 or later. CI pins 1.13.3.
- Region `us-east-1`, per [ADR 0001](adr/0001-cloud-platform-aws.md).
- Write access to this repository's Actions variables.

You do **not** need to put an account number, an ARN, or a key anywhere in this
repository. Terraform reads your credentials from the environment. The one
value that identifies your account, the deploy role ARN, reaches GitHub
Actions as a repository variable produced by `terraform output` at the end of
section 3; the ECR registry hostname is never stored, because
`amazon-ecr-login` resolves it at run time from the repository name.

`terraform.tfvars` is git-ignored. `terraform.tfvars.example` is committed and
is a copy-and-edit starting point; every value in it is optional, and
`terraform apply` with no tfvars file at all produces the stack this document
describes.

## 3. Apply

```bash
cd infra/terraform

# .terraform.lock.hcl is committed, with hashes for the platforms this project
# is applied from. Re-run the lock step only when the provider version changes.
terraform init
terraform providers lock \
  -platform=linux_amd64 -platform=darwin_arm64 -platform=darwin_amd64

terraform fmt -check -recursive
terraform validate

terraform plan -out=tf.plan
terraform apply tf.plan
```

`tf.plan` is git-ignored: a saved plan contains the same resolved values the
state file does.

**If the account already has a GitHub OIDC provider.** An AWS account holds at
most one OIDC provider per issuer URL, and a second one for
`token.actions.githubusercontent.com` fails the apply with
`EntityAlreadyExists`. If that happens, the existing provider is reused
instead:

```bash
terraform apply -var 'create_github_oidc_provider=false'
```

or put `create_github_oidc_provider = false` in `terraform.tfvars`.

**What the first apply leaves behind, and why it looks broken.** The ECR
repository is created empty, so the tag the task definition names does not
resolve and the task cannot pull an image. The service will show `0/1` running
tasks and the ECS console will show events about the image not being found.
That is expected. The service recovers on its own at the end of section 4,
when the deploy workflow pushes an image and points the service at it. Nothing
needs to be re-applied.

Read the outputs:

```bash
terraform output
```

## 4. Task sizing, the batch caps, and the idle timeout

Three numbers in `infra/terraform/` are not conventions and must not be changed
without redoing the arithmetic below: `task_memory`, `max_batch_bytes`, and
`alb_idle_timeout_seconds`.

### 4.1 The constraint

Batch verification (`POST /api/verify-batch`, FR-8,
[ADR 0006](adr/0006-batch-execution-model.md)) is one multipart request. FastAPI
finishes parsing the whole envelope before the route function is entered, and
`backend/app/api.py` then reads every part into memory as `bytes` before the
first line of NDJSON is written. **A batch is resident in memory before any of
it is processed.** Memory, not CPU, is what sizes this task.

The application derives `TTB_MAX_BATCH_BYTES` as
`2 * TTB_MAX_BATCH_FILES * TTB_MAX_UPLOAD_BYTES`, which at the defaults is two
files per label, 300 labels, 10 MiB each, 6 000 MiB (the factor of two is
ADR 0009's document per label; the task definition sets a lower explicit cap,
below). That is an upper bound implied by two limits already
stated elsewhere. It is not a recommendation, and a task sized below it while
still accepting it is a task that dies on a large batch: Fargate kills a task
that exceeds its memory rather than throttling it, and losing the task loses
the batch, because ADR 0006 has no job store and no resume.

So: size the task, then set the caps to what that size holds.

### 4.2 The size

`task_cpu = 1024` (1 vCPU) and `task_memory = 8192` (8 GiB). 8192 MiB is the
largest memory Fargate offers at 1024 CPU units, and the sizing decision is to
hold the assignment's own scenario, 300 labels in one submission, rather than
to hold a smaller batch cheaply.

### 4.3 The memory budget

| Component | MiB | Where the figure comes from |
| --- | --- | --- |
| Interpreter, FastAPI, uvicorn, numpy, OpenCV, pytesseract | 150 | Measured: 77 MiB peak RSS after importing `app.main` against `backend/requirements.lock`, on a four-core Linux session container running Python 3.11. Doubled here for the running ASGI stack and allocator behaviour under load. **Not measured on Fargate.** |
| The batch payload, held as `bytes` for the batch's duration | 3 000 | `TTB_MAX_BATCH_BYTES`, below. Since [ADR 0009](adr/0009-batch-cola-documents.md) this covers the label images **and** their COLA documents together, which does not change the figure: it is the envelope that bounds the payload, not the file count. |
| Transient duplication while the parts are read | 300 | Starlette spools a multipart part to a temporary file once it exceeds `TTB_MAX_UPLOAD_BYTES` (`app/api.py` raises the 1 MiB default to the per-file limit); below that the part stays in memory while `await image.read()` makes the copy the batch holds. Worst case is 300 parts each just under 1 MiB, so both copies of all of them are resident at once. |
| Per-image working set, one worker | 400 | The decoded image at the 1600 px long edge is about 7.3 MiB per copy and the preprocessing chain holds several; the Tesseract child process is the unmeasured part, and 400 MiB is a deliberately generous ceiling for it. |
| Result objects, futures, NDJSON framing | 20 | 300 small dataclasses. No image bytes: results carry text and scores. |
| **Total** | **3 870** | |

Against 8 192 MiB that leaves 4 322 MiB unused, 53 percent.

**That headroom is deliberate.** Two of the five rows are estimates rather than
measurements, one of them covers a child process nobody in this repository has
profiled, and the failure mode on the wrong side of the line is a killed task
and a lost batch rather than a slow one. Section 9 replaces the estimates with
measurements, and after that the size can come down.

If you would rather have the money now: `task_memory = 6144` still holds these
caps with about 2 274 MiB spare and saves about $0.0089 an hour, roughly $6.50
a month. It is one variable.

Ephemeral storage needs no configuration. Fargate provides 20 GiB by default,
and the worst case here is the spooled multipart parts, at most the 3 000 MiB
envelope.

### 4.4 The caps that follow

Set in the task definition's environment block
(`infra/terraform/ecs.tf`), not left to the application's derivation, so that
the deployed ceiling is readable where the size is:

| Variable | Value | Reading |
| --- | --- | --- |
| `TTB_MAX_BATCH_FILES` | `300` | The assignment's scenario. |
| `TTB_MAX_UPLOAD_BYTES` | `10485760` | 10 MiB per image, the application default. |
| `TTB_MAX_BATCH_BYTES` | `3145728000` | 3 000 MiB exactly. The budget above holds it. See the note below: this is now a tighter bound than the application would derive. |
| `TTB_BATCH_WORKERS` | `1` | One worker per vCPU of quota. |

**Changing any of these, or a size, is apply then deploy, and the order is
the whole of the procedure.** Terraform owns the shape of the task definition
and the deploy workflow owns one field of it, the image
([ADR 0019](adr/0019-task-definition-has-one-owner.md)). `terraform apply`
registers a new revision carrying the new value and, by design, does not move
the service onto it (`ignore_changes` in `ecs.tf`, so that an apply never
reverts a deployment). The next run of the deploy workflow reads the **latest
revision of the family**, which is the one the apply registered, puts the
image into it and moves the service. Until v1.3.0 the workflow read the
revision the service was running instead, so a changed cap could never reach
the service through this path (code review finding 10, #109); the
`describe-task-definition` call in `deploy.yml` now names the family, and
its log prints both revisions when they differ. Forgetting the deploy leaves
the service on the old shape, and nothing warns; `aws ecs describe-services
--query 'services[0].taskDefinition'` against the family's latest revision
is the check.

**`TTB_MAX_BATCH_BYTES` is now a real bound rather than arithmetic, and that is
deliberate.** It used to be exactly 300 times 10 MiB, one image per label at the
per-file cap. Since [ADR 0009](adr/0009-batch-cola-documents.md) a batch carries
one COLA document per image as well, and the application's own derivation
doubled to match: `2 * TTB_MAX_BATCH_FILES * TTB_MAX_UPLOAD_BYTES`, about
6 GiB on the defaults. **The deployed value is not raised to follow it**, because
the memory budget above is what sets this number and an 8 GiB task cannot hold a
6 GiB payload.

What that means in practice. A batch whose files total more than 3 000 MiB is
refused from its Content-Length before the body is read, with the limit named
(FR-9, NFR-7). That is the safe failure: a refusal an agent can act on rather
than a task killed mid-batch. In the ordinary case it costs nothing, because the
documents are the small half of each pair: a Public COLA Registry printout is
kilobytes and the label photograph beside it is megabytes. The case it does bite
is 300 scanned multi-page documents alongside 300 large photographs, and the
answer there is the one FR-8 already gives, which is to split the batch. Section
9's CloudWatch `MemoryUtilization` measurement is what would justify raising
both this and `task_memory`.

`TTB_BATCH_WORKERS` is pinned rather than derived, and this is worth knowing
before you change the vCPU count. `backend/app/config.py` sizes the pool from
`os.sched_getaffinity`, which reports a **cpuset**. Fargate enforces task CPU
as a **CFS quota** instead, so the affinity mask can report more cores than the
task is allowed to use, and a derived pool would oversubscribe a quota it
cannot see. Stating the number removes the question. If you raise `task_cpu`,
raise this to match, in the same change.

**`OMP_THREAD_LIMIT` is deliberately absent from the task definition and must
stay absent.** Tesseract's OpenMP runtime deadlocks when the binary is invoked
off the process's main thread, which is exactly what the batch worker pool
does on every image: no error, no crash, the request never returns.
`backend/app/ocr.py` pins `OMP_THREAD_LIMIT=1` with `os.environ.setdefault`
before `pytesseract` is imported, and `setdefault` means a value set in the
task definition would win. Adding that variable is the one way to break batch
verification without touching a line of application code. The same comment is
in `infra/terraform/ecs.tf` next to the environment block.

### 4.5 The load balancer idle timeout

A batch response is one HTTP response held open for the whole run. The load
balancer closes a connection idle longer than its timeout, and a connection
closed mid-batch loses the batch.

| | Seconds |
| --- | --- |
| 300 labels at NFR-1's per-label budget of about 5 seconds | 1 500 |
| Receiving and parsing a full 3 000 MiB envelope before the first line is written | 120 |
| **Worst case** | **1 620** |
| `alb_idle_timeout_seconds` | **3 600** |

3 600 is about 2.2 times the worst case; AWS caps this setting at 4 000.

Strictly, an ALB's idle timer resets on every byte, and the stream writes a line
per image, so the gap that actually matters is one image's processing time.
Setting the timeout above the whole batch is the conservative reading, it costs
nothing, and it covers the one window where nothing flows at all: between the
last request byte and the first response line, while the envelope is being
parsed.

For scale, not as a target: at the 527 ms median per label measured on a
four-core session runner, 300 labels run sequentially in about 2.6 minutes; at
NFR-1's 5-second budget, about 25 minutes. Neither figure was measured on
Fargate, and no source states a batch latency target (OQ-6).

## 5. What it costs

**Estimates from AWS published list prices for `us-east-1`, not measurements,
and not a quote.** Prices change; confirm in the AWS Pricing Calculator and
against your own bill. Nothing in this repository has ever been billed.

| Item | List price | Per hour |
| --- | --- | --- |
| Fargate vCPU, 1 vCPU | $0.04048 per vCPU-hour | $0.0405 |
| Fargate memory, 8 GB | $0.004445 per GB-hour | $0.0356 |
| Application Load Balancer | $0.0225 per hour | $0.0225 |
| ALB capacity units, at about one LCU | $0.008 per LCU-hour | $0.0080 |
| Public IPv4 addresses: two ALB nodes and one task | $0.005 per address-hour | $0.0150 |
| ECR storage, image about 1.5 GB | $0.10 per GB-month | $0.0002 |
| CloudWatch Logs at demonstration volume | $0.50 per GB ingested | negligible |
| **Running total** | | **about $0.12 per hour** |

Left running for a month, 730 hours: **about $90**.

That monthly figure is the reason the resting state of this stack is
destroyed. The runbook is written for deploy, demonstrate, destroy: a fresh
`terraform apply` plus one run of the deploy workflow brings the URL back in
under fifteen minutes, and a destroyed stack costs nothing. Section 10 is the
teardown.

## 6. Set the repository variables

From `terraform output`, in the repository under **Settings > Secrets and
variables > Actions > Variables**:

| Repository variable | Value from |
| --- | --- |
| `AWS_REGION` | `us-east-1` |
| `AWS_ROLE_ARN` | `terraform output deploy_role_arn` |
| `ECR_REPOSITORY` | `terraform output ecr_repository_name` |
| `ECS_CLUSTER` | `terraform output ecs_cluster_name` |
| `ECS_SERVICE` | `terraform output ecs_service_name` |
| `ECS_CONTAINER_NAME` | `terraform output ecs_container_name` |

These are configuration rather than secrets, which is why they are variables.
`AWS_ROLE_ARN` does contain the AWS account number, and that is precisely why
it is a repository variable and not a committed string: **do not paste it into
a file in this repository.**

If any of the six is unset, the deploy workflow's first job fails and names
every missing one in the run summary. It does not half-run.

## 7. Deploy

`.github/workflows/deploy.yml` runs on `workflow_dispatch` and on a published
release. It never runs on a pull request or on a push to `develop`, so CI needs
no AWS credentials and never has any.

For the first deployment, before there is a release:

**Actions > deploy > Run workflow**, on `develop`. Leave the image tag input
empty and it uses the short commit SHA.

The run does four things: checks the six variables, assumes the deploy role
with a GitHub OIDC token, builds and pushes the image, and points the service
at the **digest** that push produced rather than at the tag. A tag can be moved
by the next push; a service that referenced one would silently change what it
runs the next time a task restarted.

The deploy step waits for service stability, so a task that never becomes
healthy fails the run rather than leaving the workflow green over a broken
service. The service's circuit breaker rolls the deployment back.

For a release, the normal path: cut `release/*`, merge to `main`, publish a
`vX.Y.Z` release. The workflow runs on publication and tags the image with the
release tag. **Each trigger produces one tag shape:** a release pushes the
image under its own tag, `v1.3.1`; a dispatch pushes it under
`sha-<short sha>`, or under the tag given in the input if one was. A hotfix
release therefore pushes a new `vX.Y.Z` tag beside the last one rather than
re-pointing it, and a re-run of the same release deploy pushes the same tag
again, which the `MUTABLE` registry accepts ([OQ-34](OPEN_QUESTIONS.md#oq-34)).
The role's trust policy accepts `workflow_dispatch` from `develop`
and `main` and a published release at a `v*` tag, and nothing else; no job
declares a GitHub environment, and [docs/06](06_SECURITY_AND_COMPLIANCE.md)
section 2 says why the ref and not the environment is the control (#110).

**Tags are mutable; the workflow guards the release tags (v1.3.0, code review
finding 27).** The registry's tag immutability was turned on for finding 27
inside v1.3.0 and reverted before the release: once it is on, ECR returns
`ImageTagAlreadyExistsException` for any push to a tag that already exists,
whatever the digest, and this workflow tags by commit alone, so a re-run on an
unchanged commit pushes the same `sha-` tag and fails at the push step.
**Re-running the deploy workflow on an unchanged commit works**, with the image
tag input left empty, and it is the way to redeploy. What prevents a dispatch
from re-pointing a release tag is the workflow's preflight, which refuses a
dispatch tag matching `^v[0-9]` before it builds; the registry itself does not
prevent a re-point. The trade, and what would change it, is
[OQ-34](OPEN_QUESTIONS.md#oq-34). The service is unaffected either way, because
it runs by digest.

**The SBOM of the pushed image** is generated in the same job, from the
registry by the digest that is about to be deployed, and uploaded as an
artifact named `sbom-<digest prefix>` for 90 days. On a release it is also
attached to the release as `sbom-<digest prefix>.spdx.json`, where it does not
expire (#112). CI's own SBOM is of CI's build and is a different artifact.

## 8. Post-deploy verification

Run these against the URL, in order. `terraform output alb_dns_name` prints it,
scheme included.

```bash
URL=$(terraform output -raw alb_dns_name)
```

**The URL is `http://`, and it cannot be `https://`.** Give it and open it as
`http://<alb host>`, which is what the output prints; the same host over
`https://` does not connect, and will not, because the load balancer has a
listener on port 80 only. A browser that tries HTTPS first, or a link a mail
client has rewritten to `https://`, fails to connect instead of showing the
application, so whoever runs this gate or receives the URL should not lose
time to it. A certificate alone is not the shortcut: ACM will not issue one for
an `*.elb.amazonaws.com` name, so HTTPS here needs a domain as well as the
certificate, the 443 listener and the security group rule
([docs/06](06_SECURITY_AND_COMPLIANCE.md) section 3.1). Verified 2026-09-02
against the running v1.2.1: `http://<alb host>/api/health` answered `1.2.1`
and the interface loaded; `https://` on the same host could not connect.

**8.1 The service answers.**

```bash
curl -i "$URL/api/health"
```

Expect 200 and a body naming the service, the version, and
`"environment": "prototype"`. If this hangs or returns 503, the target is not
healthy: check the target group's health in the EC2 console and the container
logs in the CloudWatch group `terraform output cloudwatch_log_group` names.

**8.2 The interface loads.** Open `$URL` in a browser. The agent interface is
served from the same origin as the API.

**8.3 One label, end to end, against NFR-1.**

```bash
# samples/images is git-ignored and is rendered on demand.
python samples/generate_samples.py

curl -s -o /dev/null -w 'total %{time_total}s\n' \
  -F 'image=@samples/images/01-spirits-clean.png' \
  -F 'brand_name=Stone'"'"'s Throw' \
  -F 'class_type=Kentucky Straight Bourbon Whiskey' \
  -F 'alcohol_content=45' \
  -F 'net_contents=750 mL' \
  -F 'beverage_type=distilled spirits' \
  "$URL/api/verify"
```

Take the field values from the matching row of
`samples/applications/applications.csv`, which is keyed on `filename` and is the
sample set's application data (it is not a batch input any more, see ADR 0009);
the four
above are the first row as generated and are worth checking against the file
rather than trusted from this page. What this measures is the whole path,
including the load balancer and the network between you and it, which is what
NFR-1's "about 5 seconds" is actually about. The `elapsed_ms` the response body
reports is the server's own time and will be smaller.

**Take the difference between those two as unattributed, not as network time.**
Before v1.1.0 `elapsed_ms` measured only the label-side OCR span, and the
difference between it and the wall clock was three quarters server work.
It now covers the whole handler, and the response carries a `timings` block
whose phases are each measured by a timer around the work they name. If you want
to know where a slow request went, read that block; do not subtract two numbers
and name the remainder.

**8.3a The application-document path, which is the one that missed NFR-1.**

**Both requests, because a submission is both.** An agent picking a file waits
for `POST /api/classify`, and then, when they press the button, for
`POST /api/verify`. Measuring only the second reported a target met per request
and missed per submission: the author's measurement of 2026-09-01 was 5492 and
5410 ms for the first and 5331 to 5498 ms for the second, about eleven seconds
for one document, with each request on its own inside the target
([ADR 0017](adr/0017-read-the-artwork-once.md)). So the figure to record is the
sum, and the two parts beside it.

```bash
curl -s -o /tmp/classify.json -w 'classify %{time_total}s\n' \
  -F 'files=@/path/to/your-cola-application.pdf' \
  "$URL/api/classify"

curl -s -o /tmp/verify.json -w 'verify   %{time_total}s\n' \
  -F 'files=@/path/to/your-cola-application.pdf' \
  "$URL/api/verify"

python -c "import json;t=json.load(open('/tmp/verify.json'))['timings'];print(json.dumps(t,indent=2))"
```

The prefill request should now be about the time the file takes to upload rather
than about five seconds, because it reads the document's text layer and none of
the pictures inside it. Check that it says so rather than inferring it from the
clock:

```bash
python -c "import json;d=json.load(open('/tmp/classify.json'))['application_document'];print('artwork_read', d['artwork_read'], 'found', d['artwork_images_found'], 'read', d['artwork_images_read'])"
```

`artwork_read` false with a non-zero `artwork_images_found` is the expected
reading: the pictures were located, counted, and left for the check. False with a
zero count means this document carries no artwork at all, which is a different
thing and is why the two are reported separately.

One file and nothing else, so the artwork embedded in it is the label side
(ADR 0010). This is the submission that measured 6.8 s on 2026-08-30 while
reporting 3.2 s, 3.5 s against deploy #11 later the same day once the
instrumentation was honest and the duplicated read was gone, and 5.0 s against
deploy #12 once the release that reads this artwork correctly had landed;
section 9 carries all three sets of numbers, what was wrong with the first and
what the last one bought. The
`timings` block printed by the second command is the phase breakdown, and
`ocr_passes` is the figure to look at first: a document-only submission should
read one picture once.

**Read it from the response, not from the screen.** The panel stopped printing
the elapsed time and the phase disclosure in v1.2.0, on the author's own
instruction, because an agent checking a label is not measuring the tool
(NFR-1, NFR-4). Nothing about the measurement changed: every phase is still
timed by a timer around the work it names, `timings` still carries them all, and
this step is now the only place they are read. `item_five_ocr_ms` is new in
v1.2.0 and should be 0 on any document with a text layer (ADR 0016).

**8.4 The stream is a stream, and this is the step that cannot be skipped.**

`X-Accel-Buffering: no` is a hint to intermediaries, not a guarantee. If
something between the application and the browser buffers the response, every
NDJSON line arrives in one flush at the end, the progress display shows nothing
until it is over, and NFR-2 is not met even though every test passes. **This
has never been verified against a load balancer.**

A batch is one pile of files grouped into rows by filename stem, each row the
single-label check ([ADR 0020](adr/0020-batch-items-are-derived.md); the stem
rule is [ADR 0009](adr/0009-batch-cola-documents.md)'s).
`samples/generate_samples.py` writes both sides and the filed set, so
`samples/applications/documents/01-spirits-clean.pdf` is already named to pair
with `samples/images/01-spirits-clean.png`.

```bash
curl -N -s \
  -F 'files=@samples/images/01-spirits-clean.png' \
  -F 'files=@samples/images/02-spirits-case-difference.png' \
  -F 'files=@samples/images/03-spirits-title-case-warning.png' \
  -F 'files=@samples/applications/documents/01-spirits-clean.pdf' \
  -F 'files=@samples/applications/documents/02-spirits-case-difference.pdf' \
  -F 'files=@samples/applications/documents/03-spirits-title-case-warning.pdf' \
  -F 'files=@samples/applications/filed/04-spirits-altered-warning.pdf' \
  -F 'files=@samples/applications/filed/05-spirits-no-warning.pdf' \
  "$URL/api/verify-batch" \
  | while IFS= read -r line; do printf '%s  %s\n' "$(date +%T)" "${line:0:80}"; done
```

Five rows: three pairs, grouped by name, and two filed applications on their
own, checked against the artwork inside them (ADR 0020). Everything goes in the
one `files` part; the older `images` and `application_documents` names still
work. `scripts/measure.py --batch --url "$URL"` sends the same shape of request
and prints the arrival spread as a number, and `--filed` sends the filed set
alone; use whichever is easier to read. There is no `applications` CSV part any
more: sending one is ignored.

`-N` disables curl's own buffering, so what you are watching is the network.
**Read the timestamps.** Lines should arrive spread across the run, roughly one
per image. If every timestamp is identical, the response was buffered somewhere
and the finding belongs in the issue tracker before the URL is shown to anyone.

Then repeat it in the browser: open the batch tab, attach the same five images
in the first picker and their five documents in the second, and confirm two
things. The page states how many pairs it found before you submit, and the
progress bar advances while the run is in flight rather than jumping to complete
at the end.

**8.5 One full batch.** The same, at the configured cap. See section 9.

## 9. First measurements

**Run on 2026-08-28. The README now carries the results.** Every performance and
accuracy number in this repository names the hardware it came from, and these
name the deployed target: build `sha-f66a4e2`, ECS Fargate with 1 vCPU and
8 GiB behind the Application Load Balancer in `us-east-1`, exercised from the
author's browser. The boxes below record what each run returned. One box is
still open, the CloudWatch memory figure, and the README says "memory
utilization measurement pending" rather than a number until it is in hand.

The same figures are summarized in the README under
[Measured performance and accuracy](../README.md#measured-performance-and-accuracy).
This section is the record of the runs; the README is the summary of them.

- [x] **`scripts/measure.py` semantics against the deployed URL.** The script
      has two modes and they measure different things. **Which one produced
      each figure is recorded**, because in-process and through-the-ALB are not
      the same measurement. **Every figure below is through the ALB.** The
      single-label rows were submitted from the browser against the deployed
      URL; the batch row used `--batch --url "$URL"`. No in-process figure is
      quoted here.
      - Default, no arguments: imports the engine and runs it in this process.
        Accuracy, no network. To get that figure from the deployed hardware,
        run it inside the task (`aws ecs execute-command`, which needs
        `enable_execute_command` on the service, currently off). **Not used for
        anything below.**
      - `--batch --url "$URL"`: submits a real batch over HTTP, following the
        ADR 0020 contract (one `files` part; it followed ADR 0009's two parts
        when the batch row below was taken), and prints total wall clock,
        per-label time, when the first and last lines arrived, the spread
        between them, the counts by status and error code, and since v1.4.0
        `total_ms`, `tesseract_reads` and `ocr_passes` per row. `--filed`
        sends the filed applications alone. This is the mode that produced the
        batch rows. It needs `samples/generate_samples.py` to have run, which
        writes the images, the paired COLA documents and the filed set.
- [x] **NFR-1 end to end through the load balancer.** Measured 2026-08-28,
      build `sha-f66a4e2`. One label, the synthetic 1200x1600 fixture rotated
      90 degrees, submitted with a Public COLA Registry printout attached:
      **1.5 s end to end, 1.4 s of it inside the checker.** All five fields
      matched, and the rotation was detected and reported. **NFR-1's roughly
      five seconds is met with margin on this path.**
- [x] **NFR-1 on the application-document path, which is a different path and
      now meets it.** Measured twice on 2026-08-30, from the author's browser
      against the deployed URL. Sample both times: the author's own mezcal COLA
      document, a 382 KB PDF, submitted **alone**, so that the label artwork
      embedded in it is the label side (ADR 0010).

      **Before, build 1.1.0 as first deployed.** Three consecutive runs:

      | run | wall clock | server `elapsed_ms` | server `ocr_ms` |
      | --- | --- | --- | --- |
      | 1 | 6883 ms | 3323 ms | 3321 ms |
      | 2 | 6786 ms | 3214 ms | 3213 ms |
      | 3 | 6781 ms | 3198 ms | 3196 ms |

      **After, deploy #11, same day, same document, same URL.** Three
      consecutive runs:

      | run | wall clock | server `elapsed_ms` | `unaccounted_ms` | `ocr_passes` |
      | --- | --- | --- | --- | --- |
      | 1 | 3468 ms | 3387 ms | 1.3 ms | 1 |
      | 2 | 3505 ms | 3411 ms | 1.3 ms | 1 |
      | 3 | 3543 ms | 3463 ms | 1.3 ms | 1 |

      **After, deploy #12, same day, same document, same URL**, once the
      release that corrected the reading of this artwork had landed. Two
      consecutive runs:

      | run | wall clock | server `elapsed_ms` | `ocr_passes` | `tesseract_reads` |
      | --- | --- | --- | --- | --- |
      | 1 | 4999 ms | 4928 ms | 1 | 4 |
      | 2 | 4992 ms | 4918 ms | 1 | 4 |

      **5.0 s end to end is NFR-1's roughly five seconds at the line rather
      than under it**, and it is written as 5.0 rather than rounded down. It is
      recorded separately from the image path's 1.5 s rather than averaged into
      it, because they are two different paths and one number covering both
      would be a claim about neither.

      **What consumed the margin is the fix that made the readings correct, and
      that is a trade worth seeing stated.** About 1.4 seconds of the rise from
      3.5 to 5.0 is the 180-degree orientation check: it reads the image at
      both candidate rotations and keeps the better-scoring one, and it runs
      only where Tesseract's own orientation confidence falls under the floor,
      which on this document it did at 0.03. It is why this artwork's OCR
      confidence went from 37.9 to 89.6, why the alcohol content and net
      contents are found at all, and why the label is no longer read upside
      down. On the twelve sample labels it does not run and costs nothing.
      A second and a half of a five-second budget to stop reading a label the
      wrong way up is worth paying. It is not free, and this path now sits at
      the bar rather than comfortably inside it. A costed but unbuilt
      optimisation is in [OQ-27](OPEN_QUESTIONS.md#oq-27).

      The `elapsed_ms` column is the change worth reading twice. Before, it sat
      2 ms from `ocr_ms` and was measuring one span. After, it sits within
      80 ms of the browser's wall clock and `unaccounted_ms` is 1.3 ms, which is
      what says the phase breakdown beside it covers the request rather than a
      part of it. `ocr_passes` went from 2 to 1.

      **The 3.5 s runs are kept above because they are why the figure moved,
      not because they are the current figure.** They were taken while the
      artwork OCR on this document was still failing: the label was being
      turned 180 degrees on a Tesseract orientation verdict of 0.03 confidence
      and then flattened to grayscale, so what took 3.5 seconds was reading a
      wrongly turned, wrongly rendered image and getting three of five fields
      wrong. The deploy #12 figures are the ones to quote.

      **The panel segmentation released after deploy #12 adds no Tesseract
      read**, so it should not move this figure: the column split and the block
      grouping are both arithmetic on the word table the single existing pass
      already returns. Re-measured on the deployed target rather than
      on a session container, as this entry instructed: **v1.2.1, deploy #19,
      2026-09-01**, the same document returned 4736, 4896 and 4741 ms of wall
      clock, with `elapsed_ms` 4665, 4826 and 4671, `ocr_passes` 1 and
      `tesseract_reads` 4 on every run. Phase breakdown on that build: PDFium
      396 ms, artwork OCR 4267 ms, comparison 1.1 ms, unaccounted 30 ms. The
      earlier session-container before-and-after is superseded by this.
      `backend/tests/test_panel_segmentation.py` asserts the read count so the
      claim does not rest on the measurement. **Re-run this step against the
      next deploy anyway and replace these figures if they move.** Report what
      is measured rather than what was expected.

      **The instrumentation was also wrong, and wrong in the flattering
      direction.** `elapsed_ms` and `ocr_ms` are within 2 ms of each other on
      every run above, because `elapsed_ms` was measuring the label-side OCR
      span rather than the request. The interface then printed the wall clock,
      subtracted that figure and attributed the remainder to "sending the image
      and receiving the answer". Two controls from the same page and session
      bound what the network could have been:

      - `GET /api/health` round trip: 22, 19, 25, 23, 18 ms.
      - `POST` of the identical 382 KB file to a nonexistent path, so the bytes
        cross the wire and nothing processes them: 68, 86, 111 ms.

      About 3.5 seconds of real server work per request was therefore both
      missing from the instrumentation and mislabelled as network time.
      `elapsed_ms` now starts on entry to the handler and stops when the
      response is built, and the response carries a measured phase breakdown
      (`timings`).

      **What the honest measurement found.** The picture chosen as the label
      side was read twice: once to fill the application values and again as the
      label side, through the identical pipeline for an identical result. That
      read is now handed on, and reading stops once every value has been found.
      On a session container, which is not production hardware and is quoted
      only as a before-and-after on one machine: a one-image document went from
      2.19 s to 1.12 s and a two-image document from 3.17 s to 1.15 s, with the
      Tesseract passes going from two and three respectively to one.

      **And the 6.8 s figure was superseded by measurement rather than by that
      arithmetic.** The earlier edition of this entry said it would stand until
      the same document was submitted to the deployed URL on a build carrying
      the fix. It was, against deploy #11, and the second table above is the
      result. The session-container figures are still quoted only as a
      before-and-after on one machine; they are not what closed this.
- [x] **One full batch at the configured cap**: 300 label images plus 300 COLA
      documents, which is 600 files in one envelope (ADR 0009).

      ```bash
      python scripts/measure.py --batch --url "$URL" --copies 25
      ```

      `--copies 25` repeats the twelve-label sample set under fresh filename
      stems, so the pairing still holds and no two labels collide.

      Measured 2026-08-28, build `sha-f66a4e2`: **approximately 6.5 to 7
      minutes total wall clock, roughly 1.3 s per label.** 300 of 300 rows
      returned. No line failed: 270 fully matching, 30 not matching, 0 needing
      review, 0 unreadable. The 30 mismatches were exactly the 30 seeded ABV
      defects in the fixture set, so every seeded defect was caught and there
      were no false alarms. **NFR-2 is met**: the batch completed with no
      timeout and no lost work, and progress was visible throughout.
- [x] **Peak task memory from the CloudWatch `MemoryUtilization` metric for the
      batch window.** Retrieved 2026-09-02 during the v1.3.0 apply, from the
      `AWS/ECS` namespace, cluster and service `ttb-verifier`, over
      2026-08-28 00:00 to 2026-08-29 00:00 UTC at a 60-second period, using
      `TIME_SERIES(MAX(m1))` for the peak and `TIME_SERIES(AVG(m1))` for the
      mean. That window holds the 300-label batch above and every single-label
      run of the same day. The task was 1 vCPU and 8192 MiB.

      | Measure | Percent | Of 8192 MiB |
      | --- | --- | --- |
      | `MemoryUtilization` peak | 1.7 % | 139.3 MiB |
      | `MemoryUtilization` mean | 0.699 % | 57.3 MiB |
      | `CPUUtilization` peak | 99.8 % | one vCPU saturated |

      **The task is over-provisioned on memory by about 59 times**, 8192
      against a 139 MiB peak, and it is not over-provisioned on CPU at all:
      99.8 percent of one core during OCR is `OMP_THREAD_LIMIT=1` doing what
      section 4.4 says it does, so CPU is the real constraint on this task and
      memory is not. The two estimates in section 4.3 that this figure was
      going to replace, the 400 MiB per-image working set and the 150 MiB
      stack, are together larger than the whole measured peak; the batch
      payload row was never exercised by this window, because the 300-label
      run carried the twelve-label synthetic set copied 25 times and its
      envelope was a few tens of megabytes, not the 3 000 MiB cap. The
      recommendation that follows, 8192 MiB down to 2048 MiB with the vCPU
      kept, and why 2048 rather than less, is [OQ-35](OPEN_QUESTIONS.md#oq-35).
      **The Terraform is not changed in this release**: the infrastructure was
      applied for v1.3.0 and a sizing change is its own reviewed change, with
      the section 4 arithmetic redone as part of it.

      **The percentages above are the durable record.** CloudWatch keeps
      1-minute datapoints for fifteen days, so the datapoints behind these
      figures expire around 2026-09-12; after that only the 5-minute and
      coarser aggregates of the same metric remain, and a re-query would not
      reproduce the 60-second peak. Anyone repeating the measurement after that
      date measures a different window.
- [ ] **The document parse is inside the per-label cost now.** The sample
      documents are digitally generated PDFs, so their text layer is read in
      milliseconds, and the 1.3 s per label above is a text-layer figure. A
      scanned document goes through OCR instead, which costs about what reading
      a label photograph costs, so a batch of scans is roughly twice a batch of
      text-layer PDFs. If real submissions are scans, measure that separately
      rather than quoting the sample figure for it. **Not measured.**
- [x] **The stream arrived progressively.** Yes. Observed live through the load
      balancer during the 300-label run: **83 labels complete at the 109 second
      mark**, with the count advancing rather than jumping to complete at the
      end. A spread near zero between the first and last line would have meant
      a buffering intermediary; this is the opposite of that, and it is the
      specific risk ADR 0006 recorded.
- [x] **A three-photograph single-label submission** (ADR 0007). Measured
      2026-08-28 on the deployed target with three real phone photographs of a
      round bottle: **7.8 s end to end**, which is **outside NFR-1's roughly
      five seconds**. On a session runner one, two and three photographs had
      measured 1.24 s, 2.49 s and 3.83 s, so this section named it beforehand as
      the thinnest margin against NFR-1 anywhere in the prototype, and the run
      confirmed it. The levers stay what they were: `TTB_MAX_LABEL_PHOTOS` and
      `TTB_CORRECT_ORIENTATION`, both task environment variables, neither
      needing a code change. Neither has been changed; the figure is recorded
      rather than tuned away.
- [x] **A real photograph, not a rendered one.** Done, and it is the run above.
      Three photographs of an actual round bottle: **brand name and class or
      type stayed unreadable on the curved glass** and came back as mismatch and
      not found. That is honest reporting by the tool rather than a defect in
      it, and it is the SG-1 dewarping residual: a label wrapping a round bottle
      is never flat in one photograph, and three photographs work around the
      geometry rather than modelling it. Recorded, not fixed. See
      [ADR 0007](adr/0007-multi-photo-single-label.md) and OQ-21.
- [x] Record all of it with the date, the task size, and the image digest, the
      way every other measurement in this repository is recorded. Done: 2026-08-28,
      1 vCPU and 8 GiB on Fargate, build `sha-f66a4e2`, behind the ALB in
      `us-east-1`, exercised from the author's browser.

- [x] **The two real filed documents, run as a gate against the deployed
      build.** Measured 2026-09-01 against **v1.2.1, deploy #19**, 1 vCPU and
      8 GiB on Fargate behind the ALB in `us-east-1`, exercised from the
      author's browser. Neither document is in this repository, in any fixture,
      log, issue or pull request; only these measurements leave them, and
      anyone repeating the gate supplies their own copies.

      **A three-page filing, 382 KB.** Upload and parse 501, 495 and 494 ms.
      Check 4736, 4896 and 4741 ms. All five rows pass: brand name and class or
      type match, alcohol content and net contents are present on the label,
      the government warning matches. The orientation check overrode a
      Tesseract verdict of 0.03 confidence, `overrode_osd` true, which is the
      v1.1.0 fix doing its job on a real document.

      **A one-page Public COLA Registry printout, 1.1 MB.** Upload and parse
      624 ms. Brand name and class or type read from the text layer, product
      type read from the item 5 boxes. Alcohol content and net contents are
      reported absent, never as a match, which is the property this half of the
      gate exists to protect. Submitted alone the check returns
      `no_label_to_check` in 526 ms, because **all seven of its embedded
      images are rejected by the artwork floor**: the largest, 1442 by 433, on
      aspect ratio, and the remaining six on the short edge. That is a real
      Registry page whose label artwork the floor excludes wholesale, and it is
      tracked as an open defect rather than accepted.

- [x] **The item 5 margin at three render scales** (#123, OQ-32). The
      luminance separation between the ticked box and the next darkest measured
      **12.1 points against the 12.0 floor** on the author's own filing at the
      default scale, on the very document the margin was derived from. The
      question was whether the number moves with the render scale, and it was
      taken across both document shapes at three scales before deciding whether
      the floor moves. **Measured 2026-09-02 on a session container** (not
      production hardware, and not on the real documents, which stay on the
      author's machine) over the two synthetic stand-ins `samples/formmaker.py`
      builds: the text-layer form with its three boxes drawn and one filled at
      the grey calibrated against the author's measurement, and the same page
      rasterised as a scan. The render long edge is `TTB_OCR_LONG_EDGE_PX`; the
      scale is that over the page's longer side.

      | document | render long edge (scale) | WINE | DISTILLED SPIRITS, ticked | MALT BEVERAGES | separation | read as | empty-box noise |
      | --- | --- | --- | --- | --- | --- | --- | --- |
      | text-layer form PDF | 792 px (1.0) | 218.8 | 191.2 | 219.4 | **27.6** | distilled spirits | 0.0 |
      | rasterised scan | 792 px (1.0) | not sampled | | | | not determined | |
      | text-layer form PDF | 1600 px (2.0, the default) | 232.6 | 212.1 | 234.6 | **20.5** | distilled spirits | 2.0 |
      | rasterised scan | 1600 px (2.0, the default) | 223.0 | 194.4 | 226.0 | **28.6** | distilled spirits | 2.8 |
      | text-layer form PDF | 2400 px (3.0) | 232.4 | 212.5 | 234.3 | **19.9** | distilled spirits | 1.8 |
      | rasterised scan | 2400 px (3.0) | 228.9 | 196.5 | 223.2 | **26.6** | distilled spirits | 2.4 |

      **The three scales do not agree, so the number does not move.** On the
      text-layer document the separation is 27.6 at scale 1.0 and about 20 at
      2.0 and 3.0, a seven-point swing from the render scale alone on a tick
      whose darkness never changed; on the scan it is 28.6 and 26.6 where it
      can be read at all, and at scale 1.0 the captions are too small for the
      engine to find, so nothing is sampled and the agent chooses. The
      synthetic tick clears 12.0 by eight to sixteen points at every scale that
      reads; the author's real filing cleared it by 0.1 at the default, and a
      swing of the size seen here would take that reading either way. What
      would justify moving the floor is the same table on the two real
      documents, which is the author's half of this measurement; until then
      the comment in `backend/app/product_type.py` describes 12.1, not 22, and
      the margin stays where it is. The empty-box noise, 0.0 to 2.8 points,
      agrees with the 1.9 the author measured, so the floor's other end stands.

      **Reconciling the table with the 12.1 (added 2026-09-02).** None of the
      five separations above is anywhere near the 12.1 that put this item on
      the list, and a published measurement should not sit beside another with
      no account of the gap. The two runs measured the same quantity, the
      separation the module's own `_checkbox_of` window reports, but on
      **different documents**. The 12.1 was taken at v1.2.0 on the author's own
      three-page filing at the default scale, and the 32.3 recorded on the same
      day was the one-page Public COLA Registry printout, per the module
      docstring in `backend/app/product_type.py`; neither document leaves the
      author's machine, so neither could be in this run. The table above was
      taken on the two synthetic stand-ins `samples/formmaker.py` builds, and
      the darkness of their drawn tick, `TICK_GREY = 110`, was chosen to
      reproduce the author's **hand** measurement of the filing, 217.5 against
      239.9 and 241.8 from a loose crop, which is the 22-point figure the code
      comment once described and not the 12.1 the module's window measures on
      the same page. So the 20.5 at the default scale is the fixture returning
      its own calibration, within two points of the 212 against 233 and 235
      recorded beside that constant, and it says nothing about the real filing's
      margin in either direction. Both figures stand, each labelled with what it
      measures: **12.1 points, the author's real filing, the module's window,
      default scale, v1.2.0, and not re-taken since**; **20.5 points, the
      synthetic text-layer form, the module's window, default scale, v1.3.0**.
      Neither is wrong and neither supersedes the other. The one the floor was
      set from, and the one that would justify moving it, is the first, and it
      is the measurement OQ-32 still asks the author for. The floor stays at
      12.0.

- [x] **The batch path on filed applications alone** (v1.4.0,
      [ADR 0020](adr/0020-batch-items-are-derived.md)). **Measured 2026-09-02
      on a session container**, not production hardware, against a local
      uvicorn with `TTB_BATCH_WORKERS=1` as the task definition sets it, so
      that rows run one at a time as they do on the deployed task. The
      fixtures are `samples/applications/filed/*.pdf`, the synthetic Registry
      printout with the rendered label affixed, copied under fresh stems for
      the larger batches; no image was sent, so every row's label side is the
      artwork inside its application. One warm-up batch of one was run first
      and discarded.

      | Batch | Wall clock | Per label | First line | `tesseract_reads` per row | `ocr_passes` per row | row `total_ms`, median |
      | --- | --- | --- | --- | --- | --- | --- |
      | 1 filed application | 1.32 s | 1.32 s | 1.31 s | 2 | 1 | 1310 |
      | 5 filed applications | 5.95 s | 1.19 s | 1.25 s | 2 (max 4) | 1 | 1238 |
      | 20 filed applications | 24.64 s | 1.23 s | 1.33 s | 2 (max 4) | 1 | 1244 |

      Every row returned `ok` with `label_source` `application_artwork`. One
      OCR pass per row: the artwork is read once to fill the application values
      and that read is the label side (ADR 0017); the two `tesseract_reads` are
      the orientation detection and the read, and the rows at 4 are the ones
      where the 180-degree check ran. The per-label cost is the single-label
      document path's, about 1.2 s on this container, and it does not rise
      with the batch: a batch is the check, many times, in one worker.

      **The capacity limiter holds.** During the 20-row batch `GET /api/health`
      was polled every 250 ms from a second thread: 98 probes, median 2 ms,
      maximum 4 ms, none over one second. The stream is a synchronous
      generator Starlette iterates in a worker thread and each row runs in the
      pool, so the event loop is never inside a Tesseract call;
      `backend/tests/test_event_loop.py` asserts the same ordering with a
      stubbed row.

      **Classify on arrival, for a twenty-file drop**, one `POST /api/classify`
      per file with two in flight, which is what the batch tab does:

      | Twenty files | Wall clock | Per call, median |
      | --- | --- | --- |
      | filed PDFs | 0.46 s | 45 ms |
      | label PNGs | 22.96 s | 2 300 ms |

      For applications it is the cheap text-layer read the single-label tab
      learned to make in v1.2.0 (ADR 0017): the PDF header decides the side
      and the artwork is not read, so twenty chips settle in under half a
      second. **For images it is not cheap, and this is said here rather than
      designed around.** An image has no text layer; deciding whether it is a
      form or a label is an OCR pass, the same pass the check makes, and the
      two are in different requests so the check reads the image again. A drop
      of twenty label photographs therefore takes about 23 seconds to settle
      its chips on a one-worker task and about 25 seconds more to check, and
      the chips arrive two at a time while the agent waits. The check is
      available from the first file, so nothing blocks on the chips; what the
      agent sees is "Reading..." beside each image for longer than they would
      like. The follow-up, and why it is not done here, is
      [OQ-37](OPEN_QUESTIONS.md#oq-37).

- [x] **The cost of reading every panel, and the arrival sort on the batch
      tab** (v1.5.0, #121, OQ-24, OQ-37; [ADR 0010](adr/0010-embedded-label-artwork.md)
      as amended). **Measured 2026-09-03 on a session container**, not
      production hardware, against a local uvicorn with `TTB_BATCH_WORKERS=1`
      and `OMP_THREAD_LIMIT=1` as the task definition sets them, one warm-up
      batch run first and discarded. This container is slower than the one
      the 2026-09-02 rows above were taken on (a one-panel filing took 1.32 s
      there and 1.98 s here), so the figures below compare with each other and
      not with the rows above. Two fixture shapes, both synthetic and neither
      the author's document: the one-panel filing is
      `samples/applications/filed/*.pdf`, the Registry printout with the
      rendered 1000 by 1500 label sheet affixed; the three-panel filing is
      `backend/tests/test_artwork_panels.py`'s bourbon-shaped document, a
      1350 by 300 front panel, a 1050 by 309 back panel, a 187 by 1697 side
      band and a 687 by 195 signature, of which the floor admits the first
      three. No image was sent, so every row's label side is the artwork
      inside its application.

      | Batch | Wall clock | Per label | `ocr_passes` per row | `tesseract_reads` per row, median (max) | row `total_ms`, median | `artwork_ocr_ms`, median | panels read |
      | --- | --- | --- | --- | --- | --- | --- | --- |
      | 1 one-panel filing | 1.98 s | 1.98 s | 1 | 2 (2) | 1973 | 1944 | 1 |
      | 5 one-panel filings | 9.02 s | 1.80 s | 1 | 2 (4) | 1893 | 1874 | 1 |
      | 20 one-panel filings | 40.04 s | 2.00 s | 1 | 2 (4) | 2084 | 2066 | 1 |
      | 1 three-panel filing | 2.86 s | 2.86 s | 3 | 6 (6) | 2856 | 2841 | 3 |
      | 5 three-panel filings | 13.39 s | 2.68 s | 3 | 6 (6) | 2731 | 2713 | 3 |
      | 20 three-panel filings | 53.75 s | 2.69 s | 3 | 6 (6) | 2677 | 2661 | 3 |

      Every row returned `ok` with `label_source` `application_artwork`, all
      five checks passing on the three-panel filing and `label_ocr_ms` zero on
      every row: each panel is read once, to fill the application values, and
      that read is the label side (ADR 0017). **Three panels cost about 1.35
      times one flat sheet, not three times.** The phase timings say where the
      time goes: `artwork_ocr_ms` is the whole of the row on both shapes, and
      `tesseract_reads` is two per panel (the orientation call and the read)
      on either. A Tesseract pass costs by the text it has to read rather than
      by the picture it is handed, and a 1350 by 300 panel carrying two lines,
      scaled to the same 1600 pixel long edge, is about 0.9 s against about
      1.9 s for a full sheet carrying the whole label including the
      government warning. So four panels is not four times the work on
      artwork shaped like this filing's; it is roughly the cost of the text
      on them, however it is divided. **That is a property of this fixture's
      text density and not a law**: the author's real bourbon panels carry
      whatever they carry, and the honest per-label figure on the deployed
      target is the next thing to measure with that document. The per-panel
      cost is visible in the response either way, and the lever if it is too
      high is `TTB_MAX_ARTWORK_IMAGES`, which now lists what it cut as
      `not_read` rather than dropping it.

      **The capacity limiter holds.** During the 20-row batches `GET
      /api/health` was polled every 250 ms from a second thread: 159 probes
      during the one-panel batch, median 3 ms, maximum 5 ms; 212 probes
      during the three-panel batch, median 3 ms, maximum 69 ms. None was
      near a second.

      **Classify on arrival, for a twenty-file drop**, one `POST /api/classify`
      per file with two in flight, on the same server, before the change:

      | Twenty files | Wall clock | Per call, median |
      | --- | --- | --- |
      | filed PDFs | 0.57 s | 56 ms |
      | label PNGs | 36.55 s | 3 734 ms |

      The same shape as the 2026-09-02 row, on a slower container. Three
      cheaper sorts were on the table, since NFR-6 rules out keeping the read
      for the check: a heavily downscaled read, metadata alone, or deferring
      the decision to the check with a provisional chip. The downscaled read
      was measured before being chosen against, and the table is in
      [OQ-37](OPEN_QUESTIONS.md#oq-37): at every scale down to 600 pixels it
      cost 70 to 85 percent of a full read, because a lower-confidence first
      arm sends the pipeline into its other arms, and at 400 pixels, the one
      scale that saved anything, it sorted both synthetic photographed forms
      as labels. **The batch tab now defers.** An image is not sent on
      arrival; its chip reads "Label image, sorted when checked" with a line
      saying why, and the batch line, which carries the server's sorting of
      every file in the row, replaces it. So the twenty-PNG figure above is
      now 0 s before the batch starts, a PDF is still sorted on arrival in
      the 56 ms it costs, a photographed form is still sorted correctly when
      checked, and the check reads each image once as it always did. The
      single-label tab is unchanged.

The README status table and its
[Measured performance and accuracy](../README.md#measured-performance-and-accuracy)
section have been updated from this run.
[05_ARCHITECTURE.md](05_ARCHITECTURE.md) section 10 is unchanged, because these
runs did not change anything it describes.

## 10. Teardown

```bash
cd infra/terraform
terraform destroy
```

This is the resting state of the stack, not an exception. Expect it to take a
few minutes; the load balancer and the ECS service drain first, and
`deregistration_delay_seconds` (120) is part of that.

**The evaluation window is the one standing exception, and it does not change
the policy.** The stack stays up from submission until the author confirms the
assignment has been reviewed, so that the deployed URL is live for whoever is
reviewing it; `terraform destroy` runs once that confirmation is in. Destroy is
still the resting state, and the window is a period with an end rather than a
new default.

Two things that would otherwise stop a destroy are already handled:

- **The ECR repository is not empty.** `ecr_force_delete` defaults to `true`,
  so destroy deletes the repository with its images. Set it to `false` if you
  would rather keep the images, and then empty the repository by hand before
  destroying, or the destroy fails on it.
- **The load balancer has no deletion protection**, deliberately.

The GitHub repository variables survive teardown and stay correct for the
cluster and service names, because the names are deterministic. **The deploy
role ARN also survives and will be wrong** if you later apply into a different
account. Re-read `terraform output deploy_role_arn` after any re-apply and
update `AWS_ROLE_ARN`.

What a destroy leaves behind: nothing that costs money. The CloudWatch log
group is destroyed with the stack, and its seven-day retention would have
expired the contents anyway.

## 11. Terraform state

**State is local.** There is no `backend` block, so `terraform.tfstate` sits
next to the configuration and is git-ignored, along with `terraform.tfvars` and
any saved plan. That file records every attribute of every resource, including
the account number and every ARN, which is why it is ignored rather than merely
untracked.

Local state is right for exactly this situation: one operator, one machine, a
stack whose resting state is destroyed. It is wrong for anything else. It does
not lock, so two people applying at once corrupt it, and it does not survive
the machine.

**The production alternative, named and not built:** an S3 bucket with
versioning and server-side encryption for the state, plus a DynamoDB table for
the lock, declared in a `backend "s3"` block. That is a second stack with its
own lifecycle, which has to exist before the first apply of this one and must
outlive every destroy of it, and standing it up for a prototype that is
destroyed between demonstrations would cost more attention than it protects.

If the state file is lost while a stack is up, the resources are still there
and Terraform no longer knows about them. Recovery is `terraform import` per
resource, or deleting them in the console and applying again, which for this
stack is the faster path.

## 12. Portability to a government region

Decision D-11 presumes the agency's platform, Azure per the interview, as the
production target, with AWS GovCloud (US) if AWS were retained. Portability is
carried by the container image and by how the Terraform is written, not by the
region this prototype runs in.

The rules this configuration follows, and they are rules about the code rather
than claims about what has been tested:

- No hardcoded partition, region, or account identifier. `aws_partition` and
  `aws_region` are data sources, and the one hand-built ARN in the
  configuration, the managed execution policy in `iam.tf`, is built from
  `data.aws_partition.current.partition` because GovCloud is the `aws-us-gov`
  partition. Every other ARN comes from a resource attribute, so nothing has an
  account number written into it.
- Availability zones are read from `aws_availability_zones` with a filter that
  excludes Local Zones and Wavelength Zones, rather than named.
- Only services that exist in GovCloud, confirmed at deployment time.

**This has not been demonstrated.** No apply has been run in any region, let
alone a government one. NFR-10 is argued, not shown, and the traceability
matrix says so.

An Azure target is a different piece of work: the same image on Azure Container
Apps or AKS, and an Azure provider module this repository does not contain.

## 13. Known limitations of this deployment

Recorded in full, with production fixes, in
[06_SECURITY_AND_COMPLIANCE.md](06_SECURITY_AND_COMPLIANCE.md) section 3. In
short:

- **Plain HTTP**, no certificate, no custom domain. Traffic is unencrypted in
  transit. The fix is an ACM certificate, an HTTPS listener, and a redirect
  from port 80.
- **Internet-facing with no authentication.** Anyone who learns the DNS name
  can use it. `ingress_cidr_blocks` narrows it to your own address if you would
  rather it were not open while you are not demonstrating.
- **One task**, so a deployment has a brief window with no healthy target, and
  a task failure is an outage until ECS replaces it.
- **A running batch is lost** if a deployment or a destroy starts under it.
- **No WAF, no rate limiting, no access logs.**

## 14. Local deployment, which also works

```bash
docker compose up -d --build
curl http://localhost:8000/api/health
```

Unchanged, and still the fastest way to see the application. See the README
quick start.
