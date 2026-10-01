import json
import os
import sys
import argparse
from urllib.parse import quote

import boto3


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--year", type=int, action="append", dest="years")
    args = parser.parse_args()
    client = boto3.client("secretsmanager", region_name=os.environ["AWS_REGION"])
    response = client.get_secret_value(SecretId=os.environ["RDS_SECRET_ARN"])
    rds = json.loads(response["SecretString"])
    os.environ["DATABASE_URL"] = (
        f"postgresql://{quote(rds['username'], safe='')}:{quote(rds['password'], safe='')}@"
        f"{os.environ['RDS_ENDPOINT']}:{os.environ.get('RDS_PORT', '5432')}/{os.environ.get('DB_NAME', 'finance')}"
    )
    command = [sys.executable, "-m", "app.cli", "sofi-congress"]
    for year in args.years or []:
        command.extend(("--year", str(year)))
    os.execv(sys.executable, command)


if __name__ == "__main__":
    main()
