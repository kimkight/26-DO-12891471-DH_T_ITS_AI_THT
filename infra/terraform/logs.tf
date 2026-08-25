# Container logs.
#
# Retention is set explicitly. The default for a log group created implicitly
# by ECS is "never expire", which for a prototype that is applied and destroyed
# repeatedly means log data outliving every stack that produced it and quietly
# accruing storage charges after the demonstration ends.
#
# What reaches this group is bounded by NFR-6: the application logs structured
# events with no image content and no extracted field values. See
# docs/05_ARCHITECTURE.md section 6.

resource "aws_cloudwatch_log_group" "app" {
  name              = "/ecs/${var.name_prefix}"
  retention_in_days = var.log_retention_days
}
