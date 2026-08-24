# Application Load Balancer.
#
# Internet-facing and plain HTTP, which is the author's recorded decision and
# not a default that slipped through: the deliverable is a URL an evaluator can
# open, there is no custom domain to attach a certificate to, and there is no
# authentication in front of the application either. Both facts are recorded as
# known limitations, with their production fixes, in
# docs/06_SECURITY_AND_COMPLIANCE.md section 3.

resource "aws_lb" "main" {
  name               = "${var.name_prefix}-alb"
  internal           = false
  load_balancer_type = "application"
  security_groups    = [aws_security_group.alb.id]
  subnets            = aws_subnet.public[*].id

  # This is the number that makes batch verification work through a load
  # balancer at all.
  #
  # A batch is one HTTP request whose response is held open for the whole run:
  # ADR 0006 rules out a job store, so the stream is the only copy of the
  # results. The ALB closes a connection that goes idle for longer than this,
  # and closing it mid-batch loses the batch with no way to resume.
  #
  # 3600 seconds against a worst case of about 1620: 300 labels at NFR-1's
  # 5-second per-label budget is 1500 seconds, plus about 120 to receive and
  # parse a full-size multipart envelope before the first line is written. The
  # arithmetic is set out in docs/09_DEPLOYMENT.md section 4. AWS caps this at
  # 4000.
  idle_timeout = var.alb_idle_timeout_seconds

  # Off, so that `terraform destroy` is one command. Destroy is this stack's
  # resting state; protection would make the cheap path the awkward one.
  enable_deletion_protection = false

  # HTTP/1.1 desync mitigation. `defensive` is the AWS default and is stated
  # here because a load balancer with no authentication in front of it should
  # not have its request-smuggling posture left implicit.
  desync_mitigation_mode = "defensive"

  # Off: access logs need an S3 bucket and a bucket policy, which is a second
  # stack to fund and destroy. What this costs is named in
  # docs/06_SECURITY_AND_COMPLIANCE.md section 3 under the audit trail row.
  # Request-level logging in production goes here.
}

resource "aws_lb_target_group" "app" {
  name        = "${var.name_prefix}-tg"
  port        = local.container_port
  protocol    = "HTTP"
  vpc_id      = aws_vpc.main.id
  target_type = "ip"

  # How long a draining target keeps serving in-flight requests. A batch
  # running when a deployment starts is cut off once this elapses; see the
  # variable's description for the trade.
  deregistration_delay = var.deregistration_delay_seconds

  # GET /api/health, the same endpoint the container HEALTHCHECK and
  # docker-compose use. It returns 200 with the service name, version, and
  # environment and touches nothing else, so a healthy answer means the process
  # is serving rather than that OCR works.
  health_check {
    enabled             = true
    path                = "/api/health"
    protocol            = "HTTP"
    matcher             = "200"
    interval            = 30
    timeout             = 5
    healthy_threshold   = 2
    unhealthy_threshold = 3
  }

  # No stickiness. There is no session and no server-side state to be sticky
  # to (NFR-6), and with one task there is nowhere else to go anyway.
}

resource "aws_lb_listener" "http" {
  load_balancer_arn = aws_lb.main.arn
  port              = 80
  protocol          = "HTTP"

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.app.arn
  }
}
