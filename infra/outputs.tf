output "alb_dns_name" {
  description = "DNS do ALB — use para acessar a API"
  value       = aws_lb.main.dns_name
}

output "api_url" {
  description = "URL completa da API"
  value       = "http://${aws_lb.main.dns_name}"
}

output "ecr_repository_url" {
  description = "URL do repositório ECR — use para docker push"
  value       = aws_ecr_repository.app.repository_url
}

output "ecs_cluster_name" {
  description = "Nome do cluster ECS"
  value       = aws_ecs_cluster.main.name
}

output "ecs_service_name" {
  description = "Nome do service ECS"
  value       = aws_ecs_service.app.name
}
