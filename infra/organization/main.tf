provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project   = var.project_name
      ManagedBy = "Terraform"
    }
  }
}

data "aws_caller_identity" "current" {}

resource "aws_organizations_organization" "main" {
  feature_set = "ALL"
}

resource "aws_organizations_organizational_unit" "finance" {
  name      = var.finance_ou_name
  parent_id = aws_organizations_organization.main.roots[0].id

  tags = {
    Project = var.project_name
  }
}

resource "aws_organizations_account" "finance_dev" {
  name      = var.finance_account_name
  email     = var.finance_account_email
  parent_id = aws_organizations_organizational_unit.finance.id
  role_name = var.organization_access_role_name

  close_on_deletion = false

  tags = {
    Project     = var.project_name
    Environment = "dev"
    ManagedBy   = "Terraform"
  }

  lifecycle {
    prevent_destroy = true
    # AWS Organizations cannot read role_name back after account creation.
    ignore_changes = [role_name]
  }

  timeouts {
    create = "15m"
  }
}
