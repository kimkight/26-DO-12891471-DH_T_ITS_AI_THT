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

  # MUTABLE, deliberately. The deploy workflow pushes a moving tag (the release
  # tag or a dispatch tag) and then deploys the immutable digest that push
  # returned, so immutability at the registry would forbid the tag rewrite
  # without adding anything: what actually runs is pinned by digest either way.
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
