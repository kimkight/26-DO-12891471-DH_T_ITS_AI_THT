# Outputs.
#
# These print to the operator's terminal. Two of the three are the values that
# go into GitHub repository variables, and the role ARN contains the AWS
# account number: it belongs in a repository variable, never in a file in this
# repository. See docs/09_DEPLOYMENT.md section 6.

output "alb_dns_name" {
  description = "Public hostname of the load balancer. This is the deployed URL, over plain HTTP."
  value       = "http://${aws_lb.main.dns_name}"
}

output "ecr_repository_url" {
  description = "ECR repository URL. Its account-qualified form is resolved by the deploy workflow at run time; the repository variable ECR_REPOSITORY takes the bare name below."
  value       = aws_ecr_repository.app.repository_url
}

output "ecr_repository_name" {
  description = "Value for the ECR_REPOSITORY repository variable."
  value       = aws_ecr_repository.app.name
}

output "deploy_role_arn" {
  description = "Value for the AWS_ROLE_ARN repository variable. Contains the AWS account number: put it in a repository variable, not in a committed file."
  value       = aws_iam_role.deploy.arn
}

output "ecs_cluster_name" {
  description = "Value for the ECS_CLUSTER repository variable."
  value       = aws_ecs_cluster.main.name
}

output "ecs_service_name" {
  description = "Value for the ECS_SERVICE repository variable."
  value       = aws_ecs_service.app.name
}

output "ecs_container_name" {
  description = "Value for the ECS_CONTAINER_NAME repository variable."
  value       = local.container_name
}

output "ecs_task_family" {
  description = "Task definition family. Not a repository variable: the deploy workflow reads the running revision from the service itself. Useful for `aws ecs describe-task-definition` by hand."
  value       = aws_ecs_task_definition.app.family
}

output "cloudwatch_log_group" {
  description = "Where the container writes. Useful when the service will not start."
  value       = aws_cloudwatch_log_group.app.name
}
