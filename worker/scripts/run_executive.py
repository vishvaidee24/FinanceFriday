import json
import os
import sys
from urllib.parse import quote

import boto3


def main() -> None:
    client = boto3.client("secretsmanager", region_name=os.environ["AWS_REGION"])
    response = client.get_secret_value(SecretId=os.environ["RDS_SECRET_ARN"])
    rds = json.loads(response["SecretString"])
    os.environ["DATABASE_URL"] = (
        f"postgresql://{quote(rds['username'], safe='')}:{quote(rds['password'], safe='')}@"
        f"{os.environ['RDS_ENDPOINT']}:{os.environ.get('RDS_PORT', '5432')}/"
        f"{os.environ.get('DB_NAME', 'finance')}"
    )
    os.execv(
        sys.executable,
        [sys.executable, "-m", "app.cli", "executive-trades"],
    )


if __name__ == "__main__":
    main()
