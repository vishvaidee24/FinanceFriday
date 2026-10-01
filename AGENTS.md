# Codex Project Instructions

## Goal

Build a low-cost personal financial research data platform with replaceable providers.

## Architecture Rules

- Region: `us-east-1`
- Terraform manages AWS infrastructure.
- RDS PostgreSQL is the normalized central database.
- RDS must remain private.
- RDS is Single-AZ.
- EC2 is the V1 ingestion worker.
- EC2 can access public APIs directly.
- Do not create a NAT Gateway.
- Do not expose SSH.
- Use AWS Systems Manager Session Manager.
- Archive raw provider payloads to S3 before or alongside normalization.
- Ticker symbols are not canonical primary keys.

## Do Not Add Unless Explicitly Requested

- NAT Gateway
- Kubernetes / EKS
- ECS
- Redshift
- Kafka / MSK
- Kinesis
- Multi-AZ RDS
- read replicas
- Aurora
- OpenSearch

## Python

Use Python 3.12+.

Preferred packages:

- httpx
- psycopg
- boto3
- pydantic
- pydantic-settings
- tenacity
- structlog

Keep:

- provider API code in `worker/app/providers`
- orchestration in `worker/app/pipelines`
- DB utilities in `worker/app/db`
- AWS/logging utilities in `worker/app/common`

Use type hints.

## Database Rules

- Migrations live in `/migrations`.
- Use UTC `TIMESTAMPTZ`.
- Make ingestion idempotent.
- Use foreign keys and useful uniqueness constraints.
- Maintain `pipeline.ingestion_run`.
- Maintain `pipeline.watermark`.
- Distinguish when an event occurred from when it became publicly available.
- Avoid look-ahead bias.

## S3

Raw path convention:

```text
raw/<provider>/<dataset>/year=YYYY/month=MM/day=DD/<object>.json.gz
```

## Terraform Rules

- Reusable modules.
- No hard-coded credentials.
- RDS security group permits TCP/5432 only from the worker security group.
- Worker has no inbound SSH rule.
- DB subnet group spans at least two private subnets.
- Prefer Graviton/ARM where supported and cost-efficient.
