"""Load secrets from AWS and ingest bars for active database securities."""

import json
import os
import sys
from urllib.parse import quote

import boto3


def get_secret(secret_id: str) -> dict[str, str]:
    client = boto3.client("secretsmanager", region_name=os.environ["AWS_REGION"])
    response = client.get_secret_value(SecretId=secret_id)
    return json.loads(response["SecretString"])


def main() -> None:
    rds = get_secret(os.environ["RDS_SECRET_ARN"])
    alpaca = get_secret(os.environ["ALPACA_SECRET_ARN"])

    username = quote(rds["username"], safe="")
    password = quote(rds["password"], safe="")
    host = os.environ["RDS_ENDPOINT"]
    port = os.environ.get("RDS_PORT", "5432")
    database = os.environ.get("DB_NAME", "finance")

    os.environ["DATABASE_URL"] = (
        f"postgresql://{username}:{password}@{host}:{port}/{database}"
    )
    os.environ["ALPACA_API_KEY"] = alpaca["ALPACA_API_KEY"]
    os.environ["ALPACA_API_SECRET"] = alpaca["ALPACA_API_SECRET"]

    minutes = os.environ.get("BAR_LOOKBACK_MINUTES", "120")
    os.execv(
        sys.executable,
        [sys.executable, "-m", "app.cli", "tracked-stock-bars", "--minutes", minutes],
    )


if __name__ == "__main__":
    main()
