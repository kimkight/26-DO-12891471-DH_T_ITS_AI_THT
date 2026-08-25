# Provider configuration.
#
# The region comes from a variable and defaults to us-east-1 (ADR 0001). No
# account identifier, profile, or credential appears anywhere in this
# directory: the provider reads whatever the operator's environment already
# holds, which is what `aws configure` or an SSO session leaves behind.

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project     = "ttb-label-verifier"
      Environment = var.environment_name
      ManagedBy   = "terraform"
      Repository  = "${var.github_owner}/${var.github_repository}"
    }
  }
}

# Both are read rather than written down. GovCloud (US) is the `aws-us-gov`
# partition, so every ARN built by hand in this configuration is built from
# these rather than from the literal string "aws" or a hardcoded account
# number. That is the portability rule from infra/README.md and NFR-10, and it
# is also what keeps an account identifier out of the repository.
data "aws_partition" "current" {}

data "aws_region" "current" {}

# Availability zones that can actually run the workload, rather than the first
# N names in the region. `opt-in-status` excludes Local Zones and Wavelength
# Zones, which do not offer Fargate.
data "aws_availability_zones" "available" {
  state = "available"

  filter {
    name   = "opt-in-status"
    values = ["opt-in-not-required"]
  }
}
