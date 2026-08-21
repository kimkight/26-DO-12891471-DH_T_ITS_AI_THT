# Infrastructure

**Nothing in this directory is written yet.** Infrastructure as code is a
separate, later task; this file records the intended shape so that the
architecture and deployment documents have something concrete to reference.

## Planned contents

Terraform, targeting AWS commercial `us-east-1` for the prototype and written so
that the same modules apply to AWS GovCloud (US) without redesign
(Decisions D-1 and D-11). Decision D-11 presumes the agency's platform, Azure
per the interview, as the eventual production target; the Terraform here does
not cover that path and would need an Azure provider module before a pilot. See
[docs/adr/0001-cloud-platform-aws.md](../docs/adr/0001-cloud-platform-aws.md).

| Resource | Purpose |
| --- | --- |
| Amazon ECR repository | Stores the container image built by CI. Image scanning on push. |
| Amazon ECS cluster and service on AWS Fargate | Runs the container. No EC2 hosts to patch. |
| Application Load Balancer | Public entry point; forwards to the ECS target group; terminates TLS. |
| Target group with health check | Points at `GET /api/health`. |
| IAM role for GitHub Actions via OIDC | Lets CI push images and update the service without long-lived access keys. |
| ECS task execution role and task role | Least-privilege separation between pulling the image and running the workload. |
| Amazon CloudWatch log group | Container logs, with a retention period set explicitly. |
| Security groups | Load balancer accepts inbound HTTPS; tasks accept traffic only from the load balancer. |

## Portability constraints for a government region

These are the rules the modules must follow so an AWS GovCloud (US) target needs
no redesign. They are constraints on how the Terraform is written, not claims
about what has been tested.

- No hardcoded region, partition, or account identifiers. Derive ARNs from
  `aws_partition` and `aws_region` data sources, because GovCloud uses the
  `aws-us-gov` partition rather than `aws`.
- Use only services that exist in GovCloud. Service availability must be
  confirmed against AWS documentation before the GovCloud target is attempted.
- Keep region-specific values, such as availability zone counts, in variables.

## Not decided yet

The following are unresolved and are tracked in
[docs/OPEN_QUESTIONS.md](../docs/OPEN_QUESTIONS.md): custom domain and TLS
certificate source, whether the load balancer is internet-facing or internal,
VPC and subnet topology (new or existing), Terraform state backend, and log
retention period.
