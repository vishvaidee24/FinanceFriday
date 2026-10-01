import json
import os
import sys
from urllib.parse import quote

import boto3


def main() -> None:
    client = boto3.client("secretsmanager", region_name=os.environ["AWS_REGION"])
    response = client.get_secret_value(SecretId=os.environ["RDS_SECRET_ARN"])
    rds = json.loads(response["SecretString"])
    username = quote(rds["username"], safe="")
    password = quote(rds["password"], safe="")
    host = os.environ["RDS_ENDPOINT"]
    port = os.environ.get("RDS_PORT", "5432")
    database = os.environ.get("DB_NAME", "finance")
    os.environ["DATABASE_URL"] = (
        f"postgresql://{username}:{password}@{host}:{port}/{database}"
    )
    os.execv(sys.executable, [sys.executable, "-m", "app.cli", "tracked-insiders"])


if __name__ == "__main__":
    main()
