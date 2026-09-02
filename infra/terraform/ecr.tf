# Container image registry.

resource "aws_ecr_repository" "app" {
  name = var.name_prefix

  # Scan on push, because the point of a registry gate is that it runs without
  # anyone remembering to run it. Findings appear in the ECR console under the
  # image tag; nothing here blocks a push on a finding, and pretending
  # otherwise would be a control this prototype does not have.
  image_scanning_configuration {
    scan_on_push = true
  }

  # MUTABLE, so that a re-run of the deploy workflow on the same commit
  # succeeds.
  #
  # This was set to IMMUTABLE inside v1.3.0 for code review finding 27 and
  # reverted before the release. Once tag immutability is on, ECR returns
  # ImageTagAlreadyExistsException for any push to a tag that already exists
  # in the repository, whatever the digest being pushed. The deploy workflow
  # tags an image from the commit SHA alone (`sha-<short sha>`) with no check
  # that the tag exists, so re-running the deploy on an unchanged commit,
  # which is how this project redeploys and what the runbook says to do for
  # every release, fails at the push step.
  #
  # The substance of finding 27 was that a manual dispatch with
  # `image_tag=v1.2.0` could re-point the release tag, leaving the true release
  # digest untagged and expired by the lifecycle rule below within a day. The
  # control against that lives in the workflow: `.github/workflows/deploy.yml`
  # refuses a dispatch tag matching `^v[0-9]` before it builds. The registry
  # itself does not prevent a re-point. What immutability would buy, why it was
  # reverted, and the cheaper guard that would make it compatible with a re-run
  # are in docs/OPEN_QUESTIONS.md, OQ-34.
  #
  # Changing this on an existing repository is an in-place update in either
  # direction; nothing is recreated and the images stay.
  image_tag_mutability = "MUTABLE"

  # Let destroy delete the repository with images still in it. Without this,
  # `terraform destroy` fails on a non-empty repository and the operator has to
  # empty it by hand before trying again, which is a bad property for a stack
  # whose resting state is destroyed.
  force_delete = var.ecr_force_delete

  encryption_configuration {
    encryption_type = "AES256"
  }
}

# Keep the last few images and expire the rest. Untagged images are expired
# first: every push that moves a tag leaves the previous digest untagged, and
# those accumulate faster than the tagged ones.
resource "aws_ecr_lifecycle_policy" "app" {
  repository = aws_ecr_repository.app.name

  policy = jsonencode({
    rules = [
      {
        rulePriority = 1
        description  = "Expire untagged images after one day"
        selection = {
          tagStatus   = "untagged"
          countType   = "sinceImagePushed"
          countUnit   = "days"
          countNumber = 1
        }
        action = { type = "expire" }
      },
      {
        rulePriority = 2
        description  = "Keep the last ${var.ecr_image_count_to_keep} images"
        selection = {
          tagStatus   = "any"
          countType   = "imageCountMoreThan"
          countNumber = var.ecr_image_count_to_keep
        }
        action = { type = "expire" }
      },
    ]
  })
}
