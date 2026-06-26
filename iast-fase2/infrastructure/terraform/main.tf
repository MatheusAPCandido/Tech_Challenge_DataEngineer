# ─── Providers ───────────────────────────────────────────────────────────────

terraform {
  required_version = ">= 1.5"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

# ─── Variáveis ────────────────────────────────────────────────────────────────

variable "aws_region" {
  description = "Região AWS"
  default     = "us-east-1"
}

variable "project_name" {
  description = "Nome do projeto"
  default     = "iast-fase2"
}

variable "environment" {
  description = "Ambiente (dev, prod)"
  default     = "dev"
}

locals {
  bucket_name = "${var.project_name}-datalake-${var.environment}"
  tags = {
    Project     = var.project_name
    Environment = var.environment
    ManagedBy   = "Terraform"
  }
}

# ─── S3 – Data Lake ──────────────────────────────────────────────────────────

resource "aws_s3_bucket" "datalake" {
  bucket = local.bucket_name
  tags   = local.tags
}

resource "aws_s3_bucket_versioning" "datalake" {
  bucket = aws_s3_bucket.datalake.id
  versioning_configuration {
    status = "Enabled"
  }
}

# FinOps: move dados antigos para Glacier após 90 dias
resource "aws_s3_bucket_lifecycle_configuration" "datalake" {
  bucket = aws_s3_bucket.datalake.id

  rule {
    id     = "bronze-lifecycle"
    status = "Enabled"
    filter { prefix = "bronze/" }
    transition {
      days          = 90
      storage_class = "GLACIER"
    }
  }

  rule {
    id     = "silver-lifecycle"
    status = "Enabled"
    filter { prefix = "silver/" }
    transition {
      days          = 180
      storage_class = "STANDARD_IA"
    }
  }
}

# Bloqueia acesso público
resource "aws_s3_bucket_public_access_block" "datalake" {
  bucket                  = aws_s3_bucket.datalake.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# ─── IAM – Role para Glue ────────────────────────────────────────────────────

resource "aws_iam_role" "glue_role" {
  name = "${var.project_name}-glue-role"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action    = "sts:AssumeRole"
      Effect    = "Allow"
      Principal = { Service = "glue.amazonaws.com" }
    }]
  })
  tags = local.tags
}

resource "aws_iam_role_policy_attachment" "glue_service" {
  role       = aws_iam_role.glue_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSGlueServiceRole"
}

resource "aws_iam_role_policy" "glue_s3" {
  name = "glue-s3-access"
  role = aws_iam_role.glue_role.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = ["s3:GetObject", "s3:PutObject", "s3:DeleteObject", "s3:ListBucket"]
      Resource = [
        aws_s3_bucket.datalake.arn,
        "${aws_s3_bucket.datalake.arn}/*"
      ]
    }]
  })
}

# ─── Glue Database ───────────────────────────────────────────────────────────

resource "aws_glue_catalog_database" "alfabetizacao" {
  name        = "${var.project_name}_alfabetizacao"
  description = "Base de dados de alfabetização INEP – IAST Fase 2"
}

# ─── Glue Crawler – Silver ───────────────────────────────────────────────────

resource "aws_glue_crawler" "silver_crawler" {
  name          = "${var.project_name}-silver-crawler"
  role          = aws_iam_role.glue_role.arn
  database_name = aws_glue_catalog_database.alfabetizacao.name

  s3_target {
    path = "s3://${aws_s3_bucket.datalake.bucket}/silver/"
  }

  configuration = jsonencode({
    Version = 1.0
    CrawlerOutput = {
      Partitions = { AddOrUpdateBehavior = "InheritFromTable" }
    }
  })

  tags = local.tags
}

# ─── Glue Crawler – Gold ─────────────────────────────────────────────────────

resource "aws_glue_crawler" "gold_crawler" {
  name          = "${var.project_name}-gold-crawler"
  role          = aws_iam_role.glue_role.arn
  database_name = aws_glue_catalog_database.alfabetizacao.name

  s3_target {
    path = "s3://${aws_s3_bucket.datalake.bucket}/gold/"
  }

  tags = local.tags
}

# ─── Athena Workgroup ────────────────────────────────────────────────────────

resource "aws_athena_workgroup" "main" {
  name = "${var.project_name}-workgroup"

  configuration {
    result_configuration {
      output_location = "s3://${aws_s3_bucket.datalake.bucket}/athena-results/"
    }
    # FinOps: limita bytes escaneados por query a 1GB
    bytes_scanned_cutoff_per_query = 1073741824
  }

  tags = local.tags
}

# ─── Outputs ─────────────────────────────────────────────────────────────────

output "s3_bucket_name" {
  value       = aws_s3_bucket.datalake.bucket
  description = "Nome do bucket S3 do Data Lake"
}

output "glue_role_arn" {
  value       = aws_iam_role.glue_role.arn
  description = "ARN da role IAM do Glue"
}

output "athena_workgroup" {
  value       = aws_athena_workgroup.main.name
  description = "Nome do Workgroup Athena"
}

output "glue_database" {
  value       = aws_glue_catalog_database.alfabetizacao.name
  description = "Database no Glue Catalog"
}
