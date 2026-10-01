output "management_account_id" {
  description = "AWS account ID that owns the Organization/Terraform state."
  value       = data.aws_caller_identity.current.account_id
}

output "organization_id" {
  description = "AWS Organizations organization ID."
  value       = aws_organizations_organization.main.id
}

output "finance_ou_id" {
  description = "Finance Organizational Unit ID."
  value       = aws_organizations_organizational_unit.finance.id
}

output "finance_dev_account_id" {
  description = "AWS account ID for finance-dev. Copy this into infra/environments/dev/terraform.tfvars."
  value       = aws_organizations_account.finance_dev.id
}

output "finance_dev_access_role_arn" {
  description = "Role ARN the management account can assume to administer finance-dev."
  value       = "arn:aws:iam::${aws_organizations_account.finance_dev.id}:role/${var.organization_access_role_name}"
}
