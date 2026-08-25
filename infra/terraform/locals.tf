locals {
  # The port uvicorn listens on inside the container, matching the Dockerfile's
  # EXPOSE and CMD. One place, because the target group, both security group
  # rules, and the port mapping all have to agree.
  container_port = 8000

  container_name = "${var.name_prefix}-app"

  # Which GitHub OIDC subjects may assume the deploy role. Each entry is a
  # `sub` claim pattern, and together they are the deploy workflow's two
  # triggers and nothing else:
  #
  #   - workflow_dispatch runs from a branch, so the claim is the branch ref.
  #     develop and main only.
  #   - a published release runs at the tag, so the claim is the tag ref.
  #     v-prefixed tags only, which is the release convention in
  #     docs/08_SDLC_PROCESS.md.
  #   - the deploy job declares `environment: production`, and a job with an
  #     environment gets an environment-scoped claim instead of a ref-scoped
  #     one, so that form is listed too.
  #
  # A pull request from a fork produces `repo:<owner>/<repo>:pull_request`,
  # which matches none of these.
  github_repo_path = "${var.github_owner}/${var.github_repository}"

  github_oidc_subjects = [
    "repo:${local.github_repo_path}:ref:refs/heads/develop",
    "repo:${local.github_repo_path}:ref:refs/heads/main",
    "repo:${local.github_repo_path}:ref:refs/tags/v*",
    "repo:${local.github_repo_path}:environment:production",
  ]
}
