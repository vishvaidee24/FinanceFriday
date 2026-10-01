# AWS Organization Bootstrap

This Terraform root is intentionally separate from the application infrastructure.
It runs in the existing AWS **management account** and creates:

- an AWS Organization with all features enabled (if one does not already exist)
- a `Finance` Organizational Unit
- a `finance-dev` member account
- the standard `OrganizationAccountAccessRole` cross-account role

## Important safety rules

- Do not create or use root-user access keys for Terraform.
- Authenticate the AWS CLI with an IAM administrator/role or IAM Identity Center in the management account.
- The member account resource uses `prevent_destroy = true` and `close_on_deletion = false` so a normal Terraform destroy cannot close the AWS account.
- Keep this Terraform state separate from `infra/environments/dev`.

## First run

PowerShell:

```powershell
cd infra/organization
Copy-Item terraform.tfvars.example terraform.tfvars
notepad terraform.tfvars
aws sts get-caller-identity
terraform init
terraform plan
terraform apply
terraform output finance_dev_account_id
```

Set `finance_account_email` to a globally unique email address before applying.

After the account is created, copy `finance_dev_account_id` into:

`infra/environments/dev/terraform.tfvars`

## Existing AWS Organization

If this management account already has an AWS Organization created outside this Terraform state, import it instead of trying to create a second one:

```powershell
aws organizations describe-organization
terraform import aws_organizations_organization.main o-xxxxxxxxxx
```

Then run `terraform plan` before applying.
