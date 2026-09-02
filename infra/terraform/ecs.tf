# ECS cluster, task definition, and service.

resource "aws_ecs_cluster" "main" {
  name = var.name_prefix

  # Container Insights off. It is a per-metric CloudWatch charge on a stack
  # sized to be cheap, and the first measurements this system needs come from
  # scripts/measure.py against the deployed URL rather than from a metrics
  # dashboard. Turn it on when there is something to watch over time.
  setting {
    name  = "containerInsights"
    value = "disabled"
  }
}

resource "aws_ecs_cluster_capacity_providers" "main" {
  cluster_name       = aws_ecs_cluster.main.name
  capacity_providers = ["FARGATE"]

  default_capacity_provider_strategy {
    capacity_provider = "FARGATE"
    weight            = 1
  }
}

resource "aws_ecs_task_definition" "app" {
  family                   = var.name_prefix
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]

  # 1 vCPU and 8 GiB. The memory figure is the batch path's, not the OCR
  # path's: FastAPI parses the whole multipart envelope before the route runs,
  # so a full batch is resident before any of it is processed. The arithmetic
  # from this pair of numbers to the three TTB_MAX_* values below is in
  # docs/09_DEPLOYMENT.md section 4. Change one and re-do it.
  cpu    = var.task_cpu
  memory = var.task_memory

  execution_role_arn = aws_iam_role.task_execution.arn
  task_role_arn      = aws_iam_role.task.arn

  runtime_platform {
    operating_system_family = "LINUX"
    # The image is built for amd64 by the deploy workflow's runner. Stating it
    # here means a task placed on Graviton capacity fails to start with a clear
    # architecture error rather than pulling an image it cannot run.
    cpu_architecture = "X86_64"
  }

  container_definitions = jsonencode([
    {
      name  = local.container_name
      image = "${aws_ecr_repository.app.repository_url}:${var.container_image_tag}"

      essential = true

      portMappings = [
        {
          containerPort = local.container_port
          protocol      = "tcp"
        }
      ]

      # -------------------------------------------------------------------
      # OMP_THREAD_LIMIT IS DELIBERATELY ABSENT FROM THIS BLOCK. DO NOT ADD IT.
      #
      # Tesseract is built against OpenMP, and its OpenMP runtime deadlocks
      # when the binary is invoked from a thread other than the process's main
      # thread. The batch path runs OCR in a worker pool, so it invokes
      # Tesseract off the main thread on every image. Without the limit the
      # Tesseract child process never exits: no error, no crash, the request
      # simply never returns.
      #
      # backend/app/ocr.py pins OMP_THREAD_LIMIT=1 with os.environ.setdefault
      # before pytesseract is imported. setdefault means an environment
      # variable set here would win, and winning with any other value
      # reintroduces the deadlock. An entry in this list is the one way to
      # break batch verification without changing a line of application code.
      # -------------------------------------------------------------------
      environment = [
        { name = "TTB_ENVIRONMENT", value = var.environment_name },
        { name = "TTB_LOG_LEVEL", value = "INFO" },

        # The batch caps, set to what var.task_memory holds rather than left to
        # the application's derivation. The application derives
        # TTB_MAX_BATCH_BYTES as twice the file count times the per-file bytes,
        # one label image and one COLA document per label since ADR 0009, which
        # is an upper bound implied by other limits and not a sizing
        # recommendation; writing the number here makes the deployed ceiling
        # readable in the task definition. It is deliberately tighter than the
        # derivation, because an 8 GiB task cannot hold the 6 GiB the derivation
        # permits, and the effect is that an oversize batch is refused with the
        # limit named rather than killing the task.
        # docs/09_DEPLOYMENT.md section 4 shows the working.
        { name = "TTB_MAX_BATCH_FILES", value = tostring(var.max_batch_files) },
        { name = "TTB_MAX_UPLOAD_BYTES", value = tostring(var.max_upload_bytes) },
        { name = "TTB_MAX_BATCH_BYTES", value = tostring(var.max_batch_bytes) },

        # Pinned rather than derived. The application sizes its pool from
        # sched_getaffinity, which reports a cpuset; Fargate enforces task CPU
        # as a CFS quota instead, so the affinity mask can report more cores
        # than the task may use and the derived pool would oversubscribe the
        # quota it cannot see.
        { name = "TTB_BATCH_WORKERS", value = tostring(var.batch_workers) },
      ]

      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = aws_cloudwatch_log_group.app.name
          "awslogs-region"        = data.aws_region.current.name
          "awslogs-stream-prefix" = "app"
        }
      }

      # The image's own HEALTHCHECK, restated so ECS runs it. curl is installed
      # in the runtime stage for this. It duplicates the target group check on
      # purpose: this one catches a process that is alive but not serving,
      # before the load balancer has taken the target out.
      healthCheck = {
        command     = ["CMD-SHELL", "curl --fail --silent http://localhost:${local.container_port}/api/health || exit 1"]
        interval    = 30
        timeout     = 5
        retries     = 3
        startPeriod = 30
      }
    }
  ])
}

resource "aws_ecs_service" "app" {
  name            = var.name_prefix
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.app.arn
  desired_count   = var.desired_count
  launch_type     = "FARGATE"

  # Public subnets with a public IP, so the task can reach ECR and CloudWatch
  # Logs without a NAT gateway. The task's security group accepts inbound
  # traffic only from the load balancer; see the comment at the top of
  # network.tf for why this is the shape and what production's is.
  network_configuration {
    subnets          = aws_subnet.public[*].id
    security_groups  = [aws_security_group.tasks.id]
    assign_public_ip = true
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.app.arn
    container_name   = local.container_name
    container_port   = local.container_port
  }

  # A new task takes a little while to import OpenCV and start serving. Without
  # a grace period the load balancer can fail it before it has answered once,
  # and the service replaces a task that was only starting.
  health_check_grace_period_seconds = var.health_check_grace_period_seconds

  # Roll back a deployment whose tasks never become healthy, rather than
  # leaving a service that keeps launching and killing tasks. On the very first
  # deployment there is no previous revision to roll back to, so the deployment
  # simply fails and the service sits at zero tasks until an image exists.
  deployment_circuit_breaker {
    enable   = true
    rollback = true
  }

  # With desired_count = 1, 100 percent minimum healthy would deadlock: ECS
  # would have to keep the one existing task while starting its replacement and
  # would never be allowed to stop it. Zero accepts a short gap in service
  # during a deployment, which is the right trade for a single-task prototype.
  deployment_minimum_healthy_percent = 0
  deployment_maximum_percent         = 200

  # Wait for the deployment during `terraform apply`? No. On the first apply
  # the repository is empty and the task cannot pull, so waiting would hang the
  # apply for the full timeout on the one run where the failure is expected.
  wait_for_steady_state = false

  lifecycle {
    # The deploy workflow registers a new task definition revision on every
    # release and points the service at it. Terraform does not own what is
    # running after that, and without this every subsequent `terraform apply`
    # would revert the service to the bootstrap tag in this file and undo the
    # deployment. Terraform still owns the shape of the task definition: change
    # a limit or a size here, apply, then run the deploy workflow to put the
    # new shape into service. That path works because the workflow reads the
    # LATEST revision of the family, which the apply just registered, and not
    # the revision the service is running; until v1.3.0 it read the running
    # one and the new shape could never reach the service (code review finding
    # 10, #109, ADR 0019).
    ignore_changes = [task_definition]
  }

  # The listener, because a service registering with a target group whose load
  # balancer has no listener yet is a race. The execution role's policy
  # attachment, because a task that starts before it is attached cannot pull
  # its image: ECS would retry until it worked, which is a self-healing failure
  # that still fills the service events with pull errors.
  depends_on = [
    aws_lb_listener.http,
    aws_iam_role_policy.task_execution,
  ]
}
