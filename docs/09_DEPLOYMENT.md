# Deployment

This is a runbook. It is written for one operator, at one machine, with
administrative credentials for her own AWS account, and it assumes nothing has
been applied yet.

**Nothing in this repository has been applied.** The Terraform in
`infra/terraform/` has been formatted and validated against the AWS provider
schema in CI, which means it is well formed. It has never been planned or
applied against an account, because the sessions that wrote it had no AWS
credentials and were not given any. Every number in section 5 is an estimate
from published list prices, and every number in section 4 is arithmetic. The
first measurement of anything on the deployed target is section 9, and it does
not exist yet.

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
repository. Terraform reads your credentials from the environment. The two
values that do identify your account, the deploy role ARN and the ECR
registry hostname, reach GitHub Actions as repository variables and are
produced by `terraform output` at the end of section 3.

`terraform.tfvars` is git-ignored. `terraform.tfvars.example` is committed and
is a copy-and-edit starting point; every value in it is optional, and
`terraform apply` with no tfvars file at all produces the stack this document
describes.

## 3. Apply

```bash
cd infra/terraform

# One-time: resolve the AWS provider and write .terraform.lock.hcl for every
# platform this project might be applied from, then commit the lock file. It is
# absent from the repository because the session that wrote this configuration
# had no route to registry.terraform.io.
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
`TTB_MAX_BATCH_FILES * TTB_MAX_UPLOAD_BYTES`, which at the defaults is 300
times 10 MiB, 3 000 MiB. That is an upper bound implied by two limits already
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
| The batch payload, held as `bytes` for the batch's duration | 3 000 | `TTB_MAX_BATCH_BYTES`, below. |
| Transient duplication while the parts are read | 300 | Starlette spools a multipart part to a temporary file once it exceeds 1 MiB; below that the part stays in memory while `await image.read()` makes the copy the batch holds. Worst case is 300 parts each just under 1 MiB, so both copies of all of them are resident at once. |
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
| `TTB_MAX_BATCH_BYTES` | `3145728000` | 3 000 MiB exactly, which is 300 times 10 MiB. The budget above holds it. |
| `TTB_BATCH_WORKERS` | `1` | One worker per vCPU of quota. |

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
release tag. The role's trust policy accepts `workflow_dispatch` from `develop`
and `main`, a published release at a `v*` tag, and the `production`
environment, and nothing else.

## 8. Post-deploy verification

Run these against the URL, in order. `terraform output alb_dns_name` prints it.

```bash
URL=$(terraform output -raw alb_dns_name)
```

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
`samples/applications/applications.csv`, which is keyed on `filename`; the four
above are the first row as generated and are worth checking against the file
rather than trusted from this page. What this measures is the whole path,
including the load balancer and the network between you and it, which is what
NFR-1's "about 5 seconds" is actually about. The `elapsed_ms` the response body
reports is the server's own time and will be smaller.

**8.4 The stream is a stream, and this is the step that cannot be skipped.**

`X-Accel-Buffering: no` is a hint to intermediaries, not a guarantee. If
something between the application and the browser buffers the response, every
NDJSON line arrives in one flush at the end, the progress display shows nothing
until it is over, and NFR-2 is not met even though every test passes. **This
has never been verified against a load balancer.**

```bash
curl -N -s \
  -F 'applications=@samples/applications/applications.csv' \
  -F 'images=@samples/images/01-spirits-clean.png' \
  -F 'images=@samples/images/02-spirits-case-difference.png' \
  -F 'images=@samples/images/03-spirits-title-case-warning.png' \
  -F 'images=@samples/images/04-spirits-altered-warning.png' \
  -F 'images=@samples/images/05-spirits-no-warning.png' \
  "$URL/api/verify-batch" \
  | while IFS= read -r line; do printf '%s  %s\n' "$(date +%T)" "${line:0:80}"; done
```

`-N` disables curl's own buffering, so what you are watching is the network.
**Read the timestamps.** Lines should arrive spread across the run, roughly one
per image. If every timestamp is identical, the response was buffered somewhere
and the finding belongs in the issue tracker before the URL is shown to anyone.

Then repeat it in the browser: open the batch tab, submit the same five, and
confirm the progress bar advances while the run is in flight rather than
jumping to complete at the end.

**8.5 One full batch.** The same, at the configured cap. See section 9.

## 9. First measurements

**No figure in this repository was measured on the deployed target.** Every
performance and accuracy number in the README, in
[07_TEST_STRATEGY.md](07_TEST_STRATEGY.md), and in the commit history names the
hardware it came from, and none of them names production. This checklist is
what turns that around, and until it is done the README's performance claims do
not change.

- [ ] **`scripts/measure.py` semantics against the deployed URL.** The script
      as committed imports the engine and runs it in-process; it does not take
      a URL. Run it inside the task (`aws ecs execute-command`, which needs
      `enable_execute_command` on the service, currently off) or extend it with
      an HTTP mode. Either way, record which one, because in-process and
      through-the-ALB are different measurements.
- [ ] **NFR-1 end to end through the load balancer.** Median, 95th percentile,
      and maximum over the twelve sample labels, from section 8.3. Report all
      three; a single latency figure is not a measurement
      ([07_TEST_STRATEGY.md](07_TEST_STRATEGY.md) section 4).
- [ ] **One full batch at the configured cap**: 300 images plus the CSV. Record
      total wall clock, whether any line failed, and the peak task memory from
      the CloudWatch `MemoryUtilization` metric. **The memory number is the one
      that matters**, because it is what replaces the two estimates in section
      4.3 with a measurement, and it is what tells you whether 8 GiB was right.
- [ ] **The stream arrived progressively**, from section 8.4, recorded as a
      yes or no with the timestamps that show it.
- [ ] Record all of it with the date, the task size, and the image digest, the
      way every other measurement in this repository is recorded.

Then, and only then, update the README status table and
[05_ARCHITECTURE.md](05_ARCHITECTURE.md) section 10.

## 10. Teardown

```bash
cd infra/terraform
terraform destroy
```

This is the resting state of the stack, not an exception. Expect it to take a
few minutes; the load balancer and the ECS service drain first, and
`deregistration_delay_seconds` (120) is part of that.

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
