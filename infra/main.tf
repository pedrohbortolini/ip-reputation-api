terraform {
  required_version = ">= 1.5.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  # backend "s3" {
  #   bucket = "ip-reputation-tf-state"
  #   key    = "infra/terraform.tfstate"
  #   region = "us-east-1"
  # }
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project     = var.app_name
      ManagedBy   = "terraform"
      Environment = var.environment
    }
  }
}

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

locals {
  name_prefix = "${var.app_name}-${var.environment}"
}

data "aws_availability_zones" "available" {
  state = "available"
}
