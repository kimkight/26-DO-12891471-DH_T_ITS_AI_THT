# Terraform and provider version constraints.
#
# State is local. There is no `backend` block, so `terraform.tfstate` is written
# next to this file and is git-ignored. That is a deliberate prototype choice:
# one operator applies from one machine, and an S3 state bucket would itself
# need creating, funding, and tearing down for a stack whose resting state is
# destroyed. It does not scale past one operator, because nothing stops two
# people applying at once and nothing keeps the state file if the machine dies.
#
# The production alternative, not built here: an S3 bucket with versioning and
# encryption for the state, plus a DynamoDB table for the lock, declared in a
# `backend "s3"` block. See docs/09_DEPLOYMENT.md section 10.

terraform {
  required_version = ">= 1.6.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.60"
    }
  }
}
