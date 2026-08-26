locals {
  # The port uvicorn listens on inside the container, matching the Dockerfile's
  # EXPOSE and CMD. One place, because the target group, both security group
  # rules, and the port mapping all have to agree.
  container_port = 8000

  container_name = "${var.name_prefix}-app"

  github_repo_path = "${var.github_owner}/${var.github_repository}"

  # Which GitHub OIDC subjects may assume the deploy role. Each entry is a
  # `sub` claim pattern, and together they are the deploy workflow's two
  # triggers and nothing else:
  #
  # - workflow_dispatch runs from a branch, so the claim is the branch ref.
  #   develop and main only.
  # - a published release runs at the tag, so the claim is the tag ref.
  #   v-prefixed tags only, which is the release convention in
  #   docs/08_SDLC_PROCESS.md.
  # - the deploy job declares `environment: production`, and a job with an
  #   environment gets an environment-scoped claim instead of a ref-scoped
  #   one, so that form is listed too.
  #
  # A pull request from a fork produces `repo:<owner>/<repo>:pull_request`,
  # which matches none of these.
  #
  # Two subject formats are accepted, because GitHub issues two. The first
  # deploy run of this stack was denied by STS, and CloudTrail showed the
  # token's actual subject as
  # `repo:kimkight@195974403/26-DO-12891471-DH_T_ITS_AI_THT@1340902599:ref:refs/heads/develop`:
  # GitHub's "unique by default" subject embeds the owner ID and repository ID
  # after `@`, so a policy written for the classic `repo:owner/repo:...` form
  # never matches it. The second prefix below accepts that format. The
  # wildcards cover only the numeric IDs; the owner and repository names stay
  # exact in every entry, so no other repository matches, and renaming or
  # re-creating the repository (which changes the IDs) does not lock the
  # deploy out. The classic prefix is kept because the format is issued
  # per-installation and a policy that accepts both survives either.
  github_oidc_sub_prefixes = [
    "repo:${local.github_repo_path}",
    "repo:${var.github_owner}@*/${var.github_repository}@*",
  ]

  github_oidc_subjects = flatten([
    for prefix in local.github_oidc_sub_prefixes : [
      "${prefix}:ref:refs/heads/develop",
      "${prefix}:ref:refs/heads/main",
      "${prefix}:ref:refs/tags/v*",
      "${prefix}:environment:production",
    ]
  ])
}
