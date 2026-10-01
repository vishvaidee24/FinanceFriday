# Finance Platform Worker

Python ingestion worker for the FinanceFriday data platform.
# SOFI analyst ratings

The `sofi-analyst-ratings` command fetches FMP's firm-level SOFI grade events,
archives the raw response to S3, and idempotently upserts `analyst.rating`.

Production runs daily at 07:00 UTC with up to 20 minutes of randomized delay.
Terraform creates the Secrets Manager container but deliberately does not put
the API key in Terraform state. After applying the dev infrastructure, populate
the secret once from the repository root:

```powershell
.\scripts\put-fmp-secret.ps1
```

Then rerun the worker SSM association (or apply Terraform again) to install and
enable the timer. The worker retrieves both database and FMP credentials at run
time; neither is written into the systemd unit.
