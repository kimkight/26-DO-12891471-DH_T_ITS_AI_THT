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

  # IMMUTABLE since v1.3.0 (code review finding 27). It was MUTABLE on the
  # argument that what runs is pinned by digest either way, so forbidding a tag
  # rewrite added nothing. It added something: a manual dispatch with
  # `image_tag=v1.2.0` could re-point the release tag, and the true release
  # digest, now untagged, would be expired by the lifecycle rule below within
  # a day. The service would keep running the right digest; the release
  # artefact would be gone. With immutability a push to an existing tag is
  # refused by the registry, and the deploy workflow's preflight refuses a
  # release-shaped dispatch tag before a build so the refusal comes with a
  # sentence. A re-run of a dispatch on the same commit pushes the same
  # `sha-` tag and is refused too; dispatch with an explicit tag in that case.
  #
  # Changing this on an existing repository is an in-place update; nothing is
  # recreated and the images stay.
  image_tag_mutability = "IMMUTABLE"

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
