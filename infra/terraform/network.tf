# Network: one VPC, public subnets in two availability zones, no NAT gateway.
#
# Why public subnets with public task IPs rather than private subnets. A
# Fargate task in a private subnet still needs to reach ECR, ECR's S3 layer
# store, and CloudWatch Logs to start at all, which means either a NAT gateway
# or a set of VPC interface endpoints. A NAT gateway is roughly $0.045 an hour
# plus data processing, and four interface endpoints are roughly $0.01 an hour
# each; both are larger than the task they would be protecting, in a stack
# whose cost posture is deploy, demo, destroy.
#
# What that costs in security is narrower than it looks: the task's security
# group accepts inbound traffic only from the load balancer's security group,
# so the public IP is an egress path rather than an entrance. It is still not
# what production should look like, and the production shape is named in
# docs/06_SECURITY_AND_COMPLIANCE.md section 3: private subnets with either a
# NAT gateway or VPC endpoints for ECR, S3, and CloudWatch Logs.

resource "aws_vpc" "main" {
  cidr_block           = var.vpc_cidr
  enable_dns_support   = true
  enable_dns_hostnames = true

  tags = {
    Name = "${var.name_prefix}-vpc"
  }
}

resource "aws_internet_gateway" "main" {
  vpc_id = aws_vpc.main.id

  tags = {
    Name = "${var.name_prefix}-igw"
  }
}

# One /24 per availability zone, carved from the VPC CIDR by index so the
# subnet CIDRs follow from vpc_cidr rather than being written out. cidrsubnet
# on a /16 with 8 additional bits yields 10.20.0.0/24, 10.20.1.0/24, and so on.
resource "aws_subnet" "public" {
  count = var.availability_zone_count

  vpc_id                  = aws_vpc.main.id
  cidr_block              = cidrsubnet(var.vpc_cidr, 8, count.index)
  availability_zone       = data.aws_availability_zones.available.names[count.index]
  map_public_ip_on_launch = true

  tags = {
    Name = "${var.name_prefix}-public-${data.aws_availability_zones.available.names[count.index]}"
  }
}

resource "aws_route_table" "public" {
  vpc_id = aws_vpc.main.id

  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.main.id
  }

  tags = {
    Name = "${var.name_prefix}-public"
  }
}

resource "aws_route_table_association" "public" {
  count = var.availability_zone_count

  subnet_id      = aws_subnet.public[count.index].id
  route_table_id = aws_route_table.public.id
}

# ---------------------------------------------------------------------------
# Security groups. Two of them, and the split is the point: the load balancer
# is the only thing the internet can reach, and the task is reachable only
# from the load balancer.
# ---------------------------------------------------------------------------

resource "aws_security_group" "alb" {
  name        = "${var.name_prefix}-alb"
  description = "Ingress to the load balancer from the internet on port 80"
  vpc_id      = aws_vpc.main.id

  tags = {
    Name = "${var.name_prefix}-alb"
  }
}

# Port 80, not 443. The prototype has no certificate and no custom domain, so
# there is nothing to terminate TLS with. That is an accepted limitation
# recorded in docs/06_SECURITY_AND_COMPLIANCE.md section 3, not an oversight:
# the production fix is an ACM certificate, an HTTPS listener, and a redirect
# from 80 to 443.
resource "aws_vpc_security_group_ingress_rule" "alb_http" {
  count = length(var.ingress_cidr_blocks)

  security_group_id = aws_security_group.alb.id
  description       = "HTTP from ${var.ingress_cidr_blocks[count.index]}"
  cidr_ipv4         = var.ingress_cidr_blocks[count.index]
  from_port         = 80
  to_port           = 80
  ip_protocol       = "tcp"
}

resource "aws_vpc_security_group_egress_rule" "alb_to_tasks" {
  security_group_id            = aws_security_group.alb.id
  description                  = "Forward to the task port"
  referenced_security_group_id = aws_security_group.tasks.id
  from_port                    = local.container_port
  to_port                      = local.container_port
  ip_protocol                  = "tcp"
}

resource "aws_security_group" "tasks" {
  name        = "${var.name_prefix}-tasks"
  description = "Task ingress from the load balancer only; egress for image pull and logs"
  vpc_id      = aws_vpc.main.id

  tags = {
    Name = "${var.name_prefix}-tasks"
  }
}

resource "aws_vpc_security_group_ingress_rule" "tasks_from_alb" {
  security_group_id            = aws_security_group.tasks.id
  description                  = "Application traffic from the load balancer"
  referenced_security_group_id = aws_security_group.alb.id
  from_port                    = local.container_port
  to_port                      = local.container_port
  ip_protocol                  = "tcp"
}

# Egress on TCP 443 only. The task pulls its image from ECR, fetches layers
# from ECR's S3 store, and writes to CloudWatch Logs, and each of those is a
# public HTTPS endpoint reached over the internet gateway; nothing the task
# does needs another port or protocol, and the application's default request
# path makes no outbound call at all (NFR-3). Until v1.3.0 this rule was all
# protocols to everywhere (code review finding 26): the residual risk in
# docs/06 section 1, a decoder exploit in the container, would have had an
# unrestricted reverse path from a public IP. Now it has 443. DNS is not
# affected: traffic to the VPC's Route 53 Resolver is not filtered by security
# groups. This is a narrowing of what the task may do, not of who may reach it.
resource "aws_vpc_security_group_egress_rule" "tasks_egress" {
  security_group_id = aws_security_group.tasks.id
  description       = "Image pull and log delivery, HTTPS only"
  cidr_ipv4         = "0.0.0.0/0"
  from_port         = 443
  to_port           = 443
  ip_protocol       = "tcp"
}
