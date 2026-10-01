provider "aws" {
  region = var.aws_region

  assume_role {
    role_arn     = "arn:aws:iam::${var.finance_account_id}:role/${var.organization_access_role_name}"
    session_name = "finance-platform-terraform"
  }

  default_tags {
    tags = {
      Project     = var.project_name
      Environment = var.environment
      ManagedBy   = "Terraform"
    }
  }
}

data "aws_caller_identity" "current" {}

module "networking" {
  source = "../../modules/networking"

  project_name         = var.project_name
  vpc_cidr             = var.vpc_cidr
  public_subnet_cidr   = var.public_subnet_cidr
  private_subnet_cidrs = var.private_subnet_cidrs
  availability_zones   = var.availability_zones
}

module "s3" {
  source       = "../../modules/s3"
  project_name = var.project_name
}

module "worker" {
  source = "../../modules/worker"

  project_name     = var.project_name
  vpc_id           = module.networking.vpc_id
  public_subnet_id = module.networking.public_subnet_id
  raw_bucket_arn   = module.s3.raw_bucket_arn
}

module "rds" {
  source = "../../modules/rds"

  project_name             = var.project_name
  db_name                  = var.db_name
  db_username              = var.db_username
  db_instance_class        = var.db_instance_class
  allocated_storage        = var.db_allocated_storage
  max_allocated_storage    = var.db_max_allocated_storage
  private_subnet_ids       = module.networking.private_subnet_ids
  vpc_id                   = module.networking.vpc_id
  worker_security_group_id = module.worker.worker_security_group_id
}

resource "aws_secretsmanager_secret" "alpaca" {
  name        = "${var.project_name}/${var.environment}/alpaca"
  description = "Alpaca market-data credentials used by the EC2 ingestion worker"
}

resource "aws_secretsmanager_secret" "fmp" {
  name        = "${var.project_name}/${var.environment}/fmp"
  description = "FMP API credential used by the EC2 analyst-rating worker"
}

resource "aws_iam_role_policy" "worker_secrets" {
  name = "${var.project_name}-worker-secrets"
  role = module.worker.iam_role_name

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = ["secretsmanager:GetSecretValue"]
      Resource = [
        module.rds.master_user_secret_arn,
        aws_secretsmanager_secret.alpaca.arn,
        aws_secretsmanager_secret.fmp.arn,
      ]
    }]
  })
}

data "archive_file" "worker" {
  type        = "zip"
  output_path = "${path.root}/.terraform/finance-platform-worker.zip"

  dynamic "source" {
    for_each = setunion(
      fileset("${path.root}/../../../worker", "app/**/*.py"),
      fileset("${path.root}/../../../worker", "scripts/*.py"),
      toset(["pyproject.toml", "README.md"]),
    )
    content {
      content  = file("${path.root}/../../../worker/${source.value}")
      filename = source.value
    }
  }
}

resource "aws_s3_object" "worker_artifact" {
  bucket = module.s3.raw_bucket_name
  key    = "artifacts/worker/${data.archive_file.worker.output_sha256}.zip"
  source = data.archive_file.worker.output_path
  etag   = data.archive_file.worker.output_md5
}

locals {
  install_worker_script = templatefile("${path.root}/../../scripts/install-worker.sh", {
    artifact_bucket   = module.s3.raw_bucket_name
    artifact_key      = aws_s3_object.worker_artifact.key
    aws_region        = var.aws_region
    rds_secret_arn    = module.rds.master_user_secret_arn
    alpaca_secret_arn = aws_secretsmanager_secret.alpaca.arn
    fmp_secret_arn    = aws_secretsmanager_secret.fmp.arn
    rds_endpoint      = module.rds.endpoint
    db_name           = var.db_name
  })
}

resource "aws_ssm_association" "install_worker" {
  name = "AWS-RunShellScript"

  targets {
    key    = "InstanceIds"
    values = [module.worker.instance_id]
  }

  parameters = {
    commands = "echo '${base64encode(local.install_worker_script)}' | base64 -d | bash"
  }

  depends_on = [
    aws_iam_role_policy.worker_secrets,
    aws_s3_object.worker_artifact,
  ]
}
