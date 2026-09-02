# ADR 0019: Terraform owns the shape of the task definition; the deploy workflow owns only the image

| | |
| --- | --- |
| Status | Accepted |
| Date | 2026-09-02 |
| Author | Kimberly D. Kight |
| Decision reference | NFR-9, NFR-11; code review finding 10 (#109); keeps D-8 (no static credential) and ADR 0002 (Fargate) |

## Context

The task definition is written twice. `infra/terraform/ecs.tf` declares it,
with the CPU and memory sizes, the environment block that carries the deployed
caps (`TTB_MAX_BATCH_FILES`, `TTB_MAX_UPLOAD_BYTES`, `TTB_MAX_BATCH_BYTES`,
`TTB_BATCH_WORKERS`, `TTB_LOG_LEVEL`), the log configuration and a bootstrap
image tag that never resolves. `.github/workflows/deploy.yml` registers a new
revision on every deploy with the image replaced by the digest it just pushed,
and points the service at that revision. The service resource carries
`lifecycle { ignore_changes = [task_definition] }` so that a later
`terraform apply` does not put the service back on the bootstrap revision and
undo the deployment.

The comment beside that lifecycle block said what the intended path was:
"change a limit or a size here, apply, then run the deploy workflow to put the
new shape into service". The code review (finding 10, #109) read the workflow
and found the path did not exist. The workflow read the revision the service
was **running**, which is the one the previous deploy registered, and
re-registered that with the new image. A `terraform apply` after a change to a
size or a cap registered a new revision and left the service where it was; the
next deploy then read the service's old revision and carried the old shape
forward. The new shape could never reach the service through the documented
path. Nothing in the repository was wrong in a way a test could catch, because
the defect was in which of two revisions a shell command named.

Two constraints shape the fix. No account identifier is committed to this
repository, so the task definition cannot be a checked-in JSON file, which
would have to carry the execution role ARN (D-8's neighbour: no static
credential and no account number in version control). And the deploy runs
without Terraform, on a runner that holds an OIDC session for one role whose
permissions are the push, the register and the one `UpdateService`; giving it
Terraform state and a plan would widen that role to the whole stack.

## Decision

**Terraform owns the shape of the task definition. The deploy workflow owns
exactly one field of it, the image, and starts every deploy from the latest
revision of the family rather than from the revision the service is running.**

The workflow derives the family name from the service's current task
definition ARN and reads `describe-task-definition` for the family, which
returns the newest `ACTIVE` revision. That revision is either the one
Terraform registered last, if there has been an apply since the last deploy,
or the one the previous deploy registered, whose shape came from Terraform's
revision before it. In both cases the shape is Terraform's and the image is the
workflow's, and a change applied through Terraform reaches the service on the
next deploy, which is what the `ecs.tf` comment claimed and now describes.

`ignore_changes = [task_definition]` stays on the service, for the reason it
was there: without it an apply would put the service on the bootstrap tag.

## Alternatives considered

### Drop `ignore_changes` and deploy through Terraform

Pass the digest in as a variable and let `terraform apply` register the
revision and update the service. One owner, in the strictest sense. Not
chosen: the deploy would then need Terraform, the state file and a role with
the whole stack's permissions on a GitHub runner, where today it needs a role
with three permissions and no state. The state is local and unencrypted
(`docs/06` section 3), so putting it on a runner is a second change with its
own risks, and the `$0.12` an hour posture of deploy, demo, destroy does not
justify an S3 backend and a lock table for it. This alternative is the right
one for a stack with a remote backend and a team, and it is recorded here so
that the next operator sees it was weighed rather than missed.

### A committed task definition JSON

The path most GitHub examples take. Not chosen because it has to name the
execution role by ARN, which contains the account number, and because it is a
second copy of what `ecs.tf` already says, which is the drift the review's
finding 10 is about, made permanent.

### Leave it and correct the comment

Cheapest. Not chosen because the deploy path the runbook describes would then
be documented as not working, and the caps in section 4.4 of the runbook could
only be changed by hand in the console.

## Consequences

**Positive**

- A change to a size, a cap or `TTB_LOG_LEVEL` in `ecs.tf` reaches the
  service through apply then deploy, as the runbook says.
- The workflow's shell reads one revision by family name and never by the
  service's ARN, so the ordering that hid the defect is gone.
- The deploy role's permissions do not change.

**Negative**

- Two revisions still exist per deploy that follows an apply: Terraform's, with
  the bootstrap tag, and the workflow's, with the digest. ECS keeps both; the
  lifecycle of task definition revisions is not managed, and the family grows
  by two on those deploys rather than one.
- The path is still apply then deploy, two commands by two actors. Forgetting
  the deploy leaves the service on the old shape, which the runbook says.

**Risks accepted**

- A revision registered outside both owners, by hand in the console, becomes
  the family's latest and the next deploy carries it forward. The deploy role
  cannot do this (its `RegisterTaskDefinition` is on `*` because the API
  allows no resource, but the role cannot reach the console), so it takes an
  operator with account credentials, and an operator with those can do
  anything to the stack already.
- This has not been exercised against AWS in this session, which holds no
  credentials. The workflow change is a shell substitution and one CLI call
  read from the same API reference as the one it replaces; the author's gate
  runs the deploy on `develop` before the release.

## References

- `.github/workflows/deploy.yml`, "Read the latest revision of the task
  definition family"
- `infra/terraform/ecs.tf`, the service's lifecycle block and its comment
- `docs/09_DEPLOYMENT.md`, section 4.4 and the note under it on changing a cap
- `docs/CODE_REVIEW_2026-09.md`, finding 10; #109
