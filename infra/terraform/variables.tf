# Input variables.
#
# Every default here is committable: a region, a repository name, a size, a
# timeout. Nothing that identifies an AWS account has a default, because
# nothing that identifies an AWS account belongs in this repository. The one
# value an operator normally overrides is `container_image_tag`, and the
# account the stack lands in comes from the credentials in the operator's
# environment, not from a variable.
#
# Copy terraform.tfvars.example to terraform.tfvars to override any of these.
# terraform.tfvars is git-ignored.

variable "aws_region" {
  description = "Region to deploy into. us-east-1 per ADR 0001."
  type        = string
  default     = "us-east-1"
}

variable "name_prefix" {
  description = "Prefix for every resource name. Short, because ALB and target group names are capped at 32 characters."
  type        = string
  default     = "ttb-verifier"

  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{2,20}$", var.name_prefix))
    error_message = "name_prefix must be 3 to 21 lowercase letters, digits or hyphens and start with a letter, so that derived ALB and target group names stay inside the 32-character AWS limit."
  }
}

variable "environment_name" {
  description = "Value of TTB_ENVIRONMENT in the container and of the Environment tag. This is a prototype, and the name says so."
  type        = string
  default     = "prototype"
}

# ---------------------------------------------------------------------------
# GitHub identity. Public information: the repository is public and its owner
# and name appear throughout the documentation. Neither is a secret and neither
# identifies an AWS account.
# ---------------------------------------------------------------------------

variable "github_owner" {
  description = "GitHub account that owns the repository allowed to assume the deploy role."
  type        = string
  default     = "kimkight"
}

variable "github_repository" {
  description = "Repository name allowed to assume the deploy role."
  type        = string
  default     = "26-DO-12891471-DH_T_ITS_AI_THT"
}

variable "create_github_oidc_provider" {
  description = <<-EOT
    Create the token.actions.githubusercontent.com OIDC provider in this account.

    An AWS account holds at most one OIDC provider per issuer URL, and creating
    a second fails with EntityAlreadyExists. Set this to false if the account
    already has one from earlier work; the existing provider is then read and
    reused. See docs/09_DEPLOYMENT.md section 5.
  EOT
  type        = bool
  default     = true
}

# ---------------------------------------------------------------------------
# Task sizing. The arithmetic behind these four numbers is in
# docs/09_DEPLOYMENT.md section 4, and it is arithmetic rather than a
# measurement: nothing in this repository has been measured on Fargate.
# ---------------------------------------------------------------------------

variable "task_cpu" {
  description = "Fargate task CPU units. 1024 = 1 vCPU."
  type        = number
  default     = 1024
}

variable "task_memory" {
  description = "Fargate task memory, MiB. 8192 is the maximum Fargate allows at 1024 CPU units."
  type        = number
  default     = 8192
}

variable "desired_count" {
  description = "Number of tasks. One, because the cost posture is deploy, demo, destroy. One task means a deployment briefly has no healthy target."
  type        = number
  default     = 1
}

variable "container_image_tag" {
  description = <<-EOT
    Tag of the image the service starts from.

    On the first apply the ECR repository is empty and no tag resolves, so the
    service cannot pull and reports 0/1 running tasks. That is expected and it
    is documented in the runbook: the first run of the deploy workflow pushes
    an image and updates the service, and the service recovers on its own.

    After that, the deploy workflow registers new task definition revisions by
    image digest and this value is not consulted again. The service ignores
    changes to its task definition for exactly that reason.
  EOT
  type        = string
  default     = "bootstrap"
}

# ---------------------------------------------------------------------------
# Application limits carried into the container environment. These are not
# arbitrary: they are what task_memory can hold. Change one and re-do the
# arithmetic in docs/09_DEPLOYMENT.md section 4.
# ---------------------------------------------------------------------------

variable "max_batch_files" {
  description = "TTB_MAX_BATCH_FILES. The assignment's own scenario is 300 labels in one submission."
  type        = number
  default     = 300
}

variable "max_upload_bytes" {
  description = "TTB_MAX_UPLOAD_BYTES. Per-image ceiling, 10 MiB, the application default."
  type        = number
  default     = 10485760
}

variable "max_batch_bytes" {
  description = "TTB_MAX_BATCH_BYTES. Set explicitly rather than derived, so the deployed ceiling is readable in the task definition instead of computed at start-up."
  type        = number
  default     = 3145728000
}

variable "batch_workers" {
  description = <<-EOT
    TTB_BATCH_WORKERS. Pinned rather than derived.

    The application derives its worker count from sched_getaffinity, which
    reports a cpuset. Fargate enforces task CPU as a CFS quota, not as a
    cpuset, so the affinity mask can report more cores than the task is
    allowed to use and the derived pool would oversubscribe the quota. One
    worker per vCPU of quota, stated here, removes the question.
  EOT
  type        = number
  default     = 1
}

# ---------------------------------------------------------------------------
# Network and ingress.
# ---------------------------------------------------------------------------

variable "vpc_cidr" {
  description = "CIDR for the VPC created by this configuration. Nothing else lives in it."
  type        = string
  default     = "10.20.0.0/16"
}

variable "availability_zone_count" {
  description = "How many availability zones to spread subnets across. An ALB requires at least two."
  type        = number
  default     = 2

  validation {
    condition     = var.availability_zone_count >= 2
    error_message = "An Application Load Balancer requires subnets in at least two availability zones."
  }
}

variable "ingress_cidr_blocks" {
  description = <<-EOT
    Who may reach the load balancer.

    Defaults to the whole internet, which is the author's recorded decision:
    the deliverable is a URL an evaluator can open, and there is no
    authentication in front of it. Narrow this to your own address while
    testing if you would rather not have the prototype reachable by anyone who
    learns the DNS name. Recorded as a known limitation in
    docs/06_SECURITY_AND_COMPLIANCE.md section 3.
  EOT
  type        = list(string)
  default     = ["0.0.0.0/0"]
}

variable "alb_idle_timeout_seconds" {
  description = <<-EOT
    ALB idle timeout, seconds.

    A batch response is one HTTP response held open for the whole batch. The
    default here covers a full batch at the configured caps with room to
    spare; the arithmetic is in docs/09_DEPLOYMENT.md section 4. AWS caps this
    at 4000.
  EOT
  type        = number
  default     = 3600

  validation {
    condition     = var.alb_idle_timeout_seconds >= 60 && var.alb_idle_timeout_seconds <= 4000
    error_message = "The ALB idle timeout must be between 1 and 4000 seconds."
  }
}

variable "deregistration_delay_seconds" {
  description = "How long the target group waits for in-flight requests before removing a draining target. A batch running when a deployment starts is lost once this elapses; raise it toward 3600 to protect one, at the cost of slow deployments and slow destroys."
  type        = number
  default     = 120
}

variable "health_check_grace_period_seconds" {
  description = "How long ECS ignores load balancer health checks on a newly started task."
  type        = number
  default     = 120
}

# ---------------------------------------------------------------------------
# Registry and logs.
# ---------------------------------------------------------------------------

variable "ecr_image_count_to_keep" {
  description = "How many images the ECR lifecycle policy retains. Older ones expire."
  type        = number
  default     = 5
}

variable "ecr_force_delete" {
  description = "Allow terraform destroy to delete the ECR repository while it still holds images. True, because destroy is this stack's resting state and an operator should not have to empty a repository by hand to get there."
  type        = bool
  default     = true
}

variable "log_retention_days" {
  description = "CloudWatch Logs retention. Seven days for a prototype that is destroyed between demonstrations. A production system's retention is set by records management, not here."
  type        = number
  default     = 7
}
