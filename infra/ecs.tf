# ============================================
# ECR — Registry de imagens Docker
# ============================================

resource "aws_ecr_repository" "app" {
  name                 = var.app_name
  #Permite sobrescrever uma tag existente.
  image_tag_mutability = "MUTABLE"

  # Scan automático de vulnerabilidades toda vez que uma imagem é puxada.
  image_scanning_configuration {
    scan_on_push = true
  }

  # Força deletar o repositório mesmo com imagens dentro.
  # Útil no terraform destroy — sem isso daria erro.
  force_delete = true

  tags = { Name = "${local.name_prefix}-ecr" }
}

# Lifecycle policy — limpa imagens antigas automaticamente.
# Mantém só as 5 mais recentes. Sem isso o ECR acumula imagens
# a cada deploy e o custo de storage cresce.
resource "aws_ecr_lifecycle_policy" "app" {
  repository = aws_ecr_repository.app.name

  policy = jsonencode({
    rules = [{
      rulePriority = 1
      description  = "Manter apenas as 5 imagens mais recentes"
      selection = {
        tagStatus   = "any"
        countType   = "imageCountMoreThan"
        countNumber = 5
      }
      action = {
        type = "expire"
      }
    }]
  })
}

# ============================================
# CloudWatch Logs — onde os logs do container vão
# ============================================

resource "aws_cloudwatch_log_group" "app" {
  name              = "/ecs/${local.name_prefix}"
  retention_in_days = 7 

  tags = { Name = "${local.name_prefix}-logs" }
}

# ============================================
# IAM — Permissões do ECS
# ============================================

# Execution Role — permite ao ECS puxar imagem do ECR,
# ler secrets do Secrets Manager, e escrever logs no CloudWatch.
# É quem o ECS "assume" para fazer o setup do container.


#Cria a role e define quem pode usar
resource "aws_iam_role" "ecs_execution" {
  name = "${local.name_prefix}-ecs-execution-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action    = "sts:AssumeRole"
      Effect    = "Allow"
      Principal = { Service = "ecs-tasks.amazonaws.com" }
    }]
  })
}

# Policy padrão da AWS para execution role — cobre ECR e CloudWatch.
resource "aws_iam_role_policy_attachment" "ecs_execution_base" {
  role       = aws_iam_role.ecs_execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

# Inline policy para ler os secrets específicos do projeto.
# Segue o princípio de least privilege — só lê o secret que precisa,
# não todos os secrets da conta.
resource "aws_iam_role_policy" "ecs_execution_secrets" {
  name = "${local.name_prefix}-secrets-access"
  role = aws_iam_role.ecs_execution.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = "secretsmanager:GetSecretValue"
      Resource = var.secrets_arn
    }]
  })
}

# ============================================
# ECS Cluster
# ============================================

#Cluster
# └─ Service
#      ├─ Task 1 (container)
#      └─ Task 2 (container)

resource "aws_ecs_cluster" "main" {
  name = "${local.name_prefix}-cluster"

  # Container Insights — métricas detalhadas de CPU, memória, rede
  # por task e service no CloudWatch. Pequeno custo extra mas muito
  # útil para debugging.
  setting {
    name  = "containerInsights"
    value = "enabled" 
  }
}

# ============================================
# ECS Task Definition — a receita do container
# ============================================

resource "aws_ecs_task_definition" "app" {
  family                   = "${local.name_prefix}-task"
  network_mode             = "awsvpc" # Cada task recebe seu próprio IP
  requires_compatibilities = ["FARGATE"]
  cpu                      = var.task_cpu
  memory                   = var.task_memory
  execution_role_arn       = aws_iam_role.ecs_execution.arn

  container_definitions = jsonencode([{
    name      = "${var.app_name}-api"
    image     = "${aws_ecr_repository.app.repository_url}:latest"
    essential = true # Se esse container morrer, a task inteira é encerrada

    portMappings = [{
      containerPort = var.container_port
      protocol      = "tcp"
    }]

    # As API keys são injetadas do Secrets Manager em tempo de execução.
    # O "valueFrom" indica que o valor vem de um ARN externo, não é literal.
    # O formato ARN:chave:: diz qual chave específica pegar do JSON do secret.
    secrets = [
      {
        name      = "ABUSEIPDB_KEY"
        valueFrom = "${var.secrets_arn}:ABUSEIPDB_KEY::"
      },
      {
        name      = "IPINFO_KEY"
        valueFrom = "${var.secrets_arn}:IPINFO_KEY::"
      }
    ]

    # Configuração de logs — manda stdout/stderr do container pro CloudWatch.
    logConfiguration = {
      logDriver = "awslogs"
      options = {
        "awslogs-group"         = aws_cloudwatch_log_group.app.name
        "awslogs-region"        = var.aws_region
        "awslogs-stream-prefix" = "ecs"
      }
    }

    # Health check nível container — o ECS monitora isso além do ALB.
    # Se falhar, o ECS marca a task como unhealthy e sobe outra.
    healthCheck = {
      command     = ["CMD-SHELL", "python -c \"import httpx; httpx.get('http://localhost:${var.container_port}/health').raise_for_status()\" || exit 1"]
      interval    = 30
      timeout     = 5
      retries     = 3
      startPeriod = 15
    }
  }])

  tags = { Name = "${local.name_prefix}-task-def" }
}

# ============================================
# ECS Service — o gerente dos containers
# ============================================

resource "aws_ecs_service" "app" {
  name            = "${local.name_prefix}-service"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.app.arn
  desired_count   = var.desired_count
  launch_type     = "FARGATE"

  # Tempo de espera antes de começar health checks no deploy.
  # Dá tempo pro container inicializar (uvicorn subir, FastAPI carregar).
  health_check_grace_period_seconds = 30

  network_configuration {
    subnets          = aws_subnet.public[*].id
    security_groups  = [aws_security_group.ecs.id]
    assign_public_ip = true # Necessário em subnet pública sem NAT
  }

  # Conecta o service ao ALB — registra as tasks no target group.
  load_balancer {
    target_group_arn = aws_lb_target_group.app.arn
    container_name   = "${var.app_name}-api"
    container_port   = var.container_port
  }

  # Garante que o ALB listener existe antes de criar o service.
  depends_on = [aws_lb_listener.http]

  # Ignora mudanças na task_definition e desired_count feitas fora
  # do Terraform (ex: pelo GitHub Actions ou auto-scaling).
  # Sem isso o Terraform reverteria deploys feitos pelo CI/CD.
  lifecycle {
    ignore_changes = [task_definition, desired_count]
  }
}
