# ============================================
# ALB — Application Load Balancer
# ============================================
# Internet-facing: recebe tráfego da internet na porta 80.
# Distribuído nas 2 subnets públicas para alta disponibilidade.

resource "aws_lb" "main" {
  name               = "${local.name_prefix}-alb"
  internal           = false # internet-facing
  load_balancer_type = "application"
  security_groups    = [aws_security_group.alb.id]
  subnets            = aws_subnet.public[*].id

  # Proteção contra deleção acidental pelo console.
  enable_deletion_protection = false

  tags = { Name = "${local.name_prefix}-alb" }
}

# ============================================
# Target Group — grupo de destino dos containers
# ============================================
# O ALB manda o tráfego para os targets registrados aqui.
# O ECS Service registra as tasks automaticamente.

resource "aws_lb_target_group" "app" {
  name        = "${local.name_prefix}-tg"
  port        = var.container_port
  protocol    = "HTTP"
  vpc_id      = aws_vpc.main.id
  target_type = "ip" # Fargate usa tipo IP (não instance)

  # Health check — o ALB bate nesse endpoint para saber se
  # o container está saudável antes de mandar tráfego.
  health_check {
    enabled             = true
    path                = "/health"
    port                = "traffic-port"
    protocol            = "HTTP"
    healthy_threshold   = 2  # 2 checks OK → saudável
    unhealthy_threshold = 3  # 3 checks falhos → unhealthy
    interval            = 30 # Verifica a cada 30 segundos
    timeout             = 5  # Se não responder em 5s, conta como falha
    matcher             = "200"
  }

  # Configuração de deregistration — quanto tempo o ALB espera
  # para parar de mandar tráfego antes de remover um target.
  # 30s é suficiente para requests em andamento terminarem.
  deregistration_delay = 30

  tags = { Name = "${local.name_prefix}-tg" }
}

# ============================================
# Listener — regra de roteamento
# ============================================
# Escuta na porta 80 (HTTP) e encaminha para o target group.
# Em produção, adicionaria listener HTTPS na 443 com certificado ACM.

resource "aws_lb_listener" "http" {
  load_balancer_arn = aws_lb.main.arn
  port              = 80
  protocol          = "HTTP"

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.app.arn
  }
}
