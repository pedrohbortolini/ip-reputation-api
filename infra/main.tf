#Indica a configuração do terraform/opentofu e quais plugins ele precisa e suas versões
terraform {
  #Versão mínima do terraform/opentofu para conseguir rodar o código.
  required_version = ">= 1.5.0"

#plugin feito pela hashicorp pra traduzir os arquivos .tf em chamadas API.
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  # Backend remoto no S3 — guarda o state fora da sua máquina.
  # Descomente quando tiver o bucket criado.
  # Sem isso o state fica local (terraform.tfstate) e se você perder
  # o arquivo, o Terraform perde noção do que já foi criado.
  #
  # backend "s3" {
  #   bucket = "ip-reputation-tf-state"
  #   key    = "infra/terraform.tfstate"
  #   region = "us-east-1"
  # }
}

#Configuração de como se conectar na AWS.
#Bloco obrigatório, sem ele o OpenTofu não sabe para onde ir na AWS.
#O bloco até funcionaria tendo região configurada no "aws configure" mas é má prática.
provider "aws" {
  region = var.aws_region

  # Tags aplicadas automaticamente em TODOS os recursos criados.
  # Facilita identificar o que pertence a esse projeto no console.
  default_tags {
    tags = {
      Project     = var.app_name
      ManagedBy   = "terraform"
      Environment = var.environment
    }
  }
}

# ============================================
# Variáveis
# ============================================

variable "aws_region" {
  description = "Região AWS onde os recursos serão criados"
  type        = string
  default     = "us-east-1"
}

variable "app_name" {
  description = "Nome do projeto — usado como prefixo em todos os recursos"
  type        = string
  default     = "ip-reputation"
}

variable "environment" {
  description = "Ambiente (dev, staging, prod)"
  type        = string
  default     = "dev"
}

variable "container_port" {
  description = "Porta onde a aplicação escuta dentro do container"
  type        = number
  default     = 8000
}

variable "task_cpu" {
  description = "CPU da task em unidades Fargate (256 = 0.25 vCPU)"
  type        = number
  default     = 256
}

variable "task_memory" {
  description = "Memória da task em MB"
  type        = number
  default     = 512
}

variable "desired_count" {
  description = "Número de tasks (containers) rodando simultaneamente"
  type        = number
  default     = 2
}

variable "secrets_arn" {
  description = "ARN do secret no Secrets Manager contendo as API keys"
  type        = string
}

# ============================================
# Locals — valores derivados das variáveis
# ============================================
# Locals evitam repetição. Em vez de escrever "${var.app_name}-alb"
# em 5 lugares diferentes, centraliza aqui.

locals {
  name_prefix = "${var.app_name}-${var.environment}"
}

# ============================================
# Data sources — busca informações da AWS
# ============================================

# Pega as AZs disponíveis na região automaticamente.
# Assim o código funciona em qualquer região sem hardcodar AZs.
data "aws_availability_zones" "available" {
  #retorna as AZs que estão de pé e aceitando recursos
  state = "available"
}
