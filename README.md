# Finance Platform

Low-cost personal financial research platform.

## AWS Account Layout

The project uses a separate AWS member account so finance resources are isolated from the management account.

```text
AWS Management Account
└── AWS Organization
    └── Finance OU
        └── finance-dev
            ├── VPC
            ├── RDS PostgreSQL
            ├── S3 raw archive
            └── EC2 ingestion worker
```

Terraform is split into two independent roots/states:

1. `infra/organization` — runs in the management account and creates `finance-dev`.
2. `infra/environments/dev` — assumes `OrganizationAccountAccessRole` in `finance-dev` and deploys the application infrastructure.

## V1 Architecture

- AWS region: `us-east-1`
- Amazon RDS PostgreSQL
- Single-AZ, private RDS
- Small ARM EC2 ingestion worker in a public subnet
- No NAT Gateway
- S3 raw archive
- AWS Systems Manager instead of SSH
- Terraform-managed infrastructure
- Python ingestion workers
- SQL migrations

## V1 Free Data Sources

1. Alpaca — stock bars and initial options data
2. SEC EDGAR — filings, CompanyFacts, Form 4
3. RSS / company IR feeds — news
4. FINRA — fixed income where available
5. Reddit — social data where accessible
6. Kalshi
7. Polymarket

Paid feeds should be added only when a free source becomes a concrete limitation.

## Local Development

Requirements:

- Python 3.12+
- Docker
- Terraform
- AWS CLI
- PostgreSQL client tools

Start PostgreSQL:

```bash
docker compose up -d postgres
```

Copy environment file:

```bash
cp .env.example .env
```

Windows PowerShell:

```powershell
Copy-Item .env.example .env
```

Install worker:

```bash
cd worker
python -m venv .venv
pip install -e ".[dev]"
```

Apply migrations:

```bash
make migrate
```

Health check:

```bash
cd worker
python -m app.cli health
```

## Terraform — Step 1: Create the Finance AWS Account

Use credentials for an IAM administrator/role in your existing management account. Do **not** create root-user access keys.

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

Before applying, replace the example `finance_account_email` with a globally unique email address that is not already associated with an AWS account.

The account resource is protected with `prevent_destroy = true` and `close_on_deletion = false`.

## Terraform — Step 2: Deploy V1 Into finance-dev

From the repository root:

```powershell
$FinanceAccountId = terraform -chdir=infra/organization output -raw finance_dev_account_id
Copy-Item infra/environments/dev/terraform.tfvars.example infra/environments/dev/terraform.tfvars
(Get-Content infra/environments/dev/terraform.tfvars) `
    -replace '123456789012', $FinanceAccountId | `
    Set-Content infra/environments/dev/terraform.tfvars

terraform -chdir=infra/environments/dev init
terraform -chdir=infra/environments/dev plan
terraform -chdir=infra/environments/dev apply
terraform -chdir=infra/environments/dev output deployed_account_id
```

`deployed_account_id` should match `finance_dev_account_id`. This verifies that RDS/S3/EC2 were deployed into the finance account rather than the management account.

Do not commit `terraform.tfvars` or Terraform state files.

## Codex

Open the root folder in VS Code:

```bash
code finance-platform
```

Have Codex read `AGENTS.md` and `docs/ARCHITECTURE.md` before making architectural changes.

Suggested implementation order:

1. Bootstrap AWS Organization + `finance-dev`
2. Validate cross-account Terraform access
3. Validate Terraform networking
4. Validate RDS/S3/worker
5. Apply schema
6. Alpaca ingestion
7. SEC ingestion
8. S3 raw archival
9. Options
10. News
11. Social
12. FINRA
13. Kalshi / Polymarket
14. Derived features

## Cost Goal

V1 AWS target: approximately `$25–35/month` once the application infrastructure is running.

Creating the AWS Organization, OU, and member account does not itself add an AWS Organizations fee. Mandatory paid data subscriptions: `$0`.
