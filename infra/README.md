# Infrastructure

Terraform for the prototype's AWS deployment, in
[`terraform/`](terraform/). The runbook that drives it, including every command
and every value's origin, is
[docs/09_DEPLOYMENT.md](../docs/09_DEPLOYMENT.md).

**This configuration has been applied**, by the author from her own machine,
to one AWS account in `us-east-1`; the prototype runs on it and the measurements
in `docs/09_DEPLOYMENT.md` section 9 were taken against it. CI formats and
validates it against the provider schema on every pull request (the
`infrastructure format and validate` job in `.github/workflows/ci.yml`), which
is a statement about the code; the apply is a statement about one account, and
the state file that records it is local and not committed.

## What is here

| File | Contents |
| --- | --- |
| `versions.tf` | Terraform and provider constraints. No backend block: state is local. |
| `providers.tf` | Provider, region variable, default tags, and the partition, region, and availability zone data sources. |
| `variables.tf` | Every input, with its default and the reasoning for it. |
| `locals.tf` | Container port and name, and the GitHub OIDC subject patterns. |
| `network.tf` | VPC, public subnets in two availability zones, internet gateway, two security groups. |
| `ecr.tf` | Repository with scan-on-push and a lifecycle policy. |
| `logs.tf` | CloudWatch log group with explicit retention. |
| `iam.tf` | Task role, task execution role, GitHub OIDC provider, deploy role and its policy. |
| `alb.tf` | Load balancer, target group, HTTP listener. |
| `ecs.tf` | Cluster, task definition, Fargate service. |
| `outputs.tf` | ALB DNS name, ECR repository URL and name, deploy role ARN, and the rest of the repository variable values. |
| `terraform.tfvars.example` | Copy to `terraform.tfvars`, which is git-ignored. |

Only services on the AWS FedRAMP services-in-scope list are used, per
[ADR 0001](../docs/adr/0001-cloud-platform-aws.md) and
[ADR 0002](../docs/adr/0002-compute-ecs-fargate-not-app-runner.md): ECR, ECS on
Fargate, Elastic Load Balancing, CloudWatch Logs, IAM.

## What is not here, and where it is written down

- **No AWS account identifier, ARN containing one, or credential.** Terraform
  reads credentials from the operator's environment. Values that identify an
  account leave through `terraform output` and go into GitHub repository
  variables. `terraform.tfvars`, `terraform.tfstate`, and `*.tfplan` are
  git-ignored.
- **No remote state.** State is local, which is right for one operator and
  wrong for anything else. The production alternative, S3 with a DynamoDB lock
  table, is named in [docs/09_DEPLOYMENT.md](../docs/09_DEPLOYMENT.md)
  section 11 and not built.
- **No TLS, no custom domain, no authentication, no WAF.** Recorded as
  accepted prototype limitations with their production fixes in
  [docs/06_SECURITY_AND_COMPLIANCE.md](../docs/06_SECURITY_AND_COMPLIANCE.md)
  section 3.
- **No Azure module.** A production deployment to the agency's platform runs
  the same image on Azure Container Apps or AKS and needs a provider module
  this repository does not contain (Decision D-11,
  [ADR 0001](../docs/adr/0001-cloud-platform-aws.md)).
- **`.terraform.lock.hcl` is committed**, carrying the provider hashes for
  linux and both macOS architectures. The session that first wrote this
  configuration had no route to `registry.terraform.io` and left a note here
  saying the file was not committed yet; it was, later, and the note outlived
  the fact (code review finding 15, #113). A `terraform init` that changes the
  file is a provider change and belongs in its own pull request.

## Two things in here that are load-bearing

**`OMP_THREAD_LIMIT` must never appear in the task definition's environment
block.** Tesseract's OpenMP runtime deadlocks when the binary is invoked off
the process's main thread, which is what the batch worker pool does on every
image, and the symptom is a request that never returns rather than an error.
`backend/app/ocr.py` pins it with `os.environ.setdefault`, so a value set in
the task definition would win. The comment next to the environment block in
`ecs.tf` says so at length.

**The memory figure is the batch path's, not the OCR path's.** FastAPI parses
the whole multipart envelope before the route runs, so a batch is resident in
memory before any of it is processed, and `TTB_MAX_BATCH_BYTES` is set to what
the chosen task memory holds rather than left to the application's derivation.
The arithmetic is in [docs/09_DEPLOYMENT.md](../docs/09_DEPLOYMENT.md)
section 4. Change `task_memory` and that section has to change with it.

## Portability constraints for a government region

Rules this configuration follows so an AWS GovCloud (US) target needs no
redesign. They are constraints on how the Terraform is written, not claims
about what has been tested, and **nothing has been tested**: NFR-10 is argued,
not demonstrated.

- No hardcoded region, partition, or account identifier. ARNs built by hand
  derive their partition from `data.aws_partition.current`, because GovCloud is
  the `aws-us-gov` partition rather than `aws`.
- Availability zones come from `data.aws_availability_zones` with Local Zones
  and Wavelength Zones filtered out, rather than being named.
- Region-specific values, such as the availability zone count, are variables.
- Only services that exist in the target region, confirmed against AWS
  documentation before a GovCloud target is attempted.
