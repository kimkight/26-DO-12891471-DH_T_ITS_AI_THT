# IAM: two task roles, the GitHub OIDC trust, and one deploy role.
#
# No user, no access key, no long-lived credential of any kind is created here.
# GitHub Actions authenticates with a short-lived OIDC token and assumes a role
# whose trust policy names this repository. That is Decision D-8 and it is what
# lets the deployment path exist without a secret in the repository.

# ---------------------------------------------------------------------------
# Task execution role: what the ECS agent uses to start the task. Pulling the
# image and writing log streams. It carries the AWS-managed policy, which grants
# those actions on every repository and log group in the account rather than
# on this stack's two; scoping it to them is tracked as a low finding of the
# v1.2.0 code review.
# ---------------------------------------------------------------------------

data "aws_iam_policy_document" "ecs_tasks_assume" {
  statement {
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["ecs-tasks.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "task_execution" {
  name               = "${var.name_prefix}-task-execution"
  assume_role_policy = data.aws_iam_policy_document.ecs_tasks_assume.json
}

# The AWS-managed execution policy is the ECR pull and CloudWatch Logs write
# that every Fargate task needs. Its ARN is built from the partition data
# source rather than written as "arn:aws:...", so the same configuration
# resolves in GovCloud, where the partition is aws-us-gov.
resource "aws_iam_role_policy_attachment" "task_execution" {
  role       = aws_iam_role.task_execution.name
  policy_arn = "arn:${data.aws_partition.current.partition}:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

# ---------------------------------------------------------------------------
# Task role: what the application itself may call. Nothing.
#
# The default extraction path makes no AWS API call: OCR runs in-process
# against the Tesseract binary in the image (ADR 0003, NFR-3), nothing is
# persisted (NFR-6), and no outbound call exists to make (D-4). A role
# with no policy attached is the honest expression of that, and it exists at
# all so that adding a permission later is an explicit change to this file
# rather than a discovery that the task has been running as the execution role.
# ---------------------------------------------------------------------------

resource "aws_iam_role" "task" {
  name               = "${var.name_prefix}-task"
  assume_role_policy = data.aws_iam_policy_document.ecs_tasks_assume.json
}

# ---------------------------------------------------------------------------
# GitHub OIDC identity provider.
#
# An account holds at most one provider per issuer, so this is created or read
# depending on create_github_oidc_provider. thumbprint_list is deliberately
# omitted: IAM verifies this issuer against its own trust store and computes
# the thumbprint itself, and a thumbprint written down here would be a rotating
# certificate fingerprint pinned in version control.
# ---------------------------------------------------------------------------

resource "aws_iam_openid_connect_provider" "github" {
  count = var.create_github_oidc_provider ? 1 : 0

  url            = "https://token.actions.githubusercontent.com"
  client_id_list = ["sts.amazonaws.com"]
}

data "aws_iam_openid_connect_provider" "github" {
  count = var.create_github_oidc_provider ? 0 : 1

  url = "https://token.actions.githubusercontent.com"
}

locals {
  github_oidc_provider_arn = (
    var.create_github_oidc_provider
    ? aws_iam_openid_connect_provider.github[0].arn
    : data.aws_iam_openid_connect_provider.github[0].arn
  )
}

# ---------------------------------------------------------------------------
# Deploy role.
# ---------------------------------------------------------------------------

data "aws_iam_policy_document" "deploy_assume" {
  statement {
    actions = ["sts:AssumeRoleWithWebIdentity"]

    principals {
      type        = "Federated"
      identifiers = [local.github_oidc_provider_arn]
    }

    # Both conditions are required, and the aud one is not decoration. Without
    # it, any GitHub Actions workflow in any repository that requested a token
    # for a different audience could still present it here; StringEquals on aud
    # is what keeps the token specific to AWS STS.
    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:aud"
      values   = ["sts.amazonaws.com"]
    }

    # StringLike rather than StringEquals only because one entry ends in a
    # wildcard, for release tags. The repository path is fixed in every entry,
    # so no other repository matches.
    condition {
      test     = "StringLike"
      variable = "token.actions.githubusercontent.com:sub"
      values   = local.github_oidc_subjects
    }
  }
}

resource "aws_iam_role" "deploy" {
  name               = "${var.name_prefix}-github-deploy"
  description        = "Assumed by GitHub Actions in ${local.github_repo_path} to push images and update the ECS service"
  assume_role_policy = data.aws_iam_policy_document.deploy_assume.json

  # An OIDC session is one workflow run. An hour is longer than a deploy that
  # waits for service stability needs, and shorter than the default twelve.
  max_session_duration = 3600
}

data "aws_iam_policy_document" "deploy" {
  # GetAuthorizationToken has no resource to scope to: the ECR login token is
  # account-wide and the API rejects a resource on this action. Everything else
  # in this document names a specific ARN.
  statement {
    sid       = "EcrLogin"
    actions   = ["ecr:GetAuthorizationToken"]
    resources = ["*"]
  }

  statement {
    sid = "EcrPushAndPullThisRepositoryOnly"
    actions = [
      "ecr:BatchCheckLayerAvailability",
      "ecr:BatchGetImage",
      "ecr:CompleteLayerUpload",
      "ecr:DescribeImages",
      "ecr:GetDownloadUrlForLayer",
      "ecr:InitiateLayerUpload",
      "ecr:PutImage",
      "ecr:UploadLayerPart",
    ]
    resources = [aws_ecr_repository.app.arn]
  }

  # RegisterTaskDefinition and DescribeTaskDefinition cannot be scoped to a
  # resource: a task definition revision does not exist until it is registered,
  # so there is no ARN to name, and IAM rejects a resource on either action.
  # Nothing narrows this statement. What bounds what the role can do with a
  # registered definition is the two statements that follow: UpdateService is
  # scoped to this one service, and PassRole to this stack's two roles.
  statement {
    sid = "EcsTaskDefinitions"
    actions = [
      "ecs:DescribeTaskDefinition",
      "ecs:RegisterTaskDefinition",
    ]
    resources = ["*"]
  }

  statement {
    sid = "EcsDeployThisServiceOnly"
    actions = [
      "ecs:DescribeServices",
      "ecs:UpdateService",
    ]
    # `id` rather than `arn`: aws_ecs_service exports the service ARN as its
    # id, and has no separate `arn` attribute in provider v5.
    resources = [aws_ecs_service.app.id]
  }

  # The deploy action reads task state while it waits for stability. These
  # actions take a cluster-scoped ARN, so the condition is what ties them to
  # this cluster rather than to every task in the account.
  statement {
    sid = "EcsReadTasksInThisClusterOnly"
    actions = [
      "ecs:DescribeTasks",
      "ecs:ListTasks",
    ]
    resources = ["*"]

    condition {
      test     = "ArnEquals"
      variable = "ecs:cluster"
      values   = [aws_ecs_cluster.main.arn]
    }
  }

  # Registering a task definition that names a role is passing that role. The
  # two roles are named explicitly and the condition restricts the pass to ECS,
  # so this cannot be used to hand either role to some other service.
  statement {
    sid     = "PassTheTaskRolesToEcsOnly"
    actions = ["iam:PassRole"]
    resources = [
      aws_iam_role.task.arn,
      aws_iam_role.task_execution.arn,
    ]

    condition {
      test     = "StringEquals"
      variable = "iam:PassedToService"
      values   = ["ecs-tasks.amazonaws.com"]
    }
  }
}

resource "aws_iam_role_policy" "deploy" {
  name   = "${var.name_prefix}-github-deploy"
  role   = aws_iam_role.deploy.id
  policy = data.aws_iam_policy_document.deploy.json
}
