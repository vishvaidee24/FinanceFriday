# Architecture

## Objective

Centralize:

- stock price / volume
- options volume / open interest
- corporate bond activity
- news
- analyst changes
- social sentiment
- prediction markets
- insider transactions
- congressional transactions
- SEC fundamentals

## AWS Account Boundary

```text
+---------------------------+
| AWS Management Account    |
|                           |
| infra/organization        |
| - AWS Organizations       |
| - Finance OU              |
+-------------+-------------+
              |
              | creates / assumes
              v
+---------------------------+
| finance-dev member account|
|                           |
| infra/environments/dev    |
| - VPC                     |
| - EC2 worker              |
| - S3                      |
| - RDS PostgreSQL          |
+---------------------------+
```

The management account is used only for organization/bootstrap responsibilities. Application resources belong in `finance-dev`.

## AWS V1

```text
                    Public APIs
                         |
                         v
                +------------------+
                | EC2 worker       |
                | Python ingestion |
                +--------+---------+
                         |
              +----------+----------+
              |                     |
              v                     v
        +-----------+        +-------------+
        | S3 raw    |        | RDS         |
        | archive   |        | PostgreSQL  |
        +-----------+        | private     |
                             | Single-AZ   |
                             +-------------+
```

## Networking

- one VPC
- one public subnet for EC2
- two private subnets for RDS subnet group
- Internet Gateway
- no NAT Gateway
- RDS is not public
- RDS TCP/5432 from worker SG only
- no inbound SSH
- SSM for administration

## Terraform State Boundaries

- `infra/organization`: management-account state; owns Organizations, Finance OU, and `finance-dev` account.
- `infra/environments/dev`: member-account state; assumes `OrganizationAccountAccessRole` and owns the finance V1 resources.

Do not merge these states. Keeping account lifecycle separate prevents application-level Terraform operations from affecting organization/account lifecycle.

## Database Schemas

- `core`
- `market`
- `options`
- `fixed_income`
- `news`
- `analyst`
- `social`
- `prediction`
- `ownership`
- `fundamentals`
- `derived`
- `pipeline`

## Data Identity

```text
core.company
    |
    +--> core.security
```

Do not use ticker as a durable identity.

## Temporal Correctness

Store both event time and public availability time where applicable.

A backtest may only use information at or after its public availability time.
