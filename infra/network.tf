# ============================================
# VPC
# ============================================

resource "aws_vpc" "main" {
  cidr_block           = "10.0.0.0/16"
  enable_dns_hostnames = true # Permite que recursos na VPC tenham hostname DNS
  enable_dns_support   = true

  tags = { Name = "${local.name_prefix}-vpc" }
}

# ============================================
# Subnets Públicas (2 AZs)
# ============================================
# Usamos duas subnets em AZs diferentes para alta disponibilidade.
# O count cria 2 subnets automaticamente, uma em cada AZ.
# cidrsubnet() calcula os blocos CIDR sem precisar hardcodar:
#   10.0.0.0/16 → 10.0.1.0/24, 10.0.2.0/24

resource "aws_subnet" "public" {
  count = 2

  vpc_id            = aws_vpc.main.id
  #cidrsubnet(prefix, newbits, netnum) > qual vpc, quantos bits adiciona na máscara e número da subnet
  cidr_block        = cidrsubnet(aws_vpc.main.cidr_block, 8, count.index + 1)
  availability_zone = data.aws_availability_zones.available.names[count.index]

  # Recursos nessa subnet recebem IP público automaticamente.
  # Necessário porque não estamos usando NAT Gateway.
  map_public_ip_on_launch = true

  tags = {
    Name = "${local.name_prefix}-public-${data.aws_availability_zones.available.names[count.index]}"
  }
}

# ============================================
# Internet Gateway + Route Table
# ============================================

resource "aws_internet_gateway" "main" {
  vpc_id = aws_vpc.main.id
  tags   = { Name = "${local.name_prefix}-igw" }
}

resource "aws_route_table" "public" {
  vpc_id = aws_vpc.main.id

  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.main.id
  }

  tags = { Name = "${local.name_prefix}-public-rt" }
}

# Associa a route table às subnets — sem isso a subnet usa a route table
# padrão da VPC que NÃO tem rota para o IGW.
resource "aws_route_table_association" "public" {
  count          = 2
  subnet_id      = aws_subnet.public[count.index].id
  route_table_id = aws_route_table.public.id
}

# ============================================
# Security Groups
# ============================================

# --- ALB Security Group ---
# Aceita tráfego HTTP (porta 80) de qualquer lugar da internet.
# É o único ponto de entrada público da arquitetura.

resource "aws_security_group" "alb" {
  name        = "${local.name_prefix}-alb-sg"
  description = "Permite trafego HTTP da internet para o ALB"
  vpc_id      = aws_vpc.main.id

  ingress {
    description = "HTTP da internet"
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    description = "Permite saida para qualquer destino"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = { Name = "${local.name_prefix}-alb-sg" }
}

# --- ECS Security Group ---
# Aceita tráfego APENAS do ALB na porta da aplicação.
# Ninguém da internet acessa os containers diretamente.
# O security_groups referencia o SG do ALB — regra baseada em SG,
# não em IP. Se o ALB mudar de IP, continua funcionando.

resource "aws_security_group" "ecs" {
  name        = "${local.name_prefix}-ecs-sg"
  description = "Permite trafego do ALB para os containers"
  vpc_id      = aws_vpc.main.id

  ingress {
    description     = "Trafego do ALB na porta da aplicacao"
    from_port       = var.container_port # 8000
    to_port         = var.container_port
    protocol        = "tcp"
    security_groups = [aws_security_group.alb.id]
  }

  egress {
    description = "Permite saida para qualquer destino (APIs externas, ECR, etc)"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = { Name = "${local.name_prefix}-ecs-sg" }
}
