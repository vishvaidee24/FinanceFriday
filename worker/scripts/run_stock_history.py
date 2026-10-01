"""Backfill Alpaca IEX minute bars in bounded, idempotent chunks."""

import argparse
import asyncio
import json
import os
from datetime import datetime, timedelta, timezone
from urllib.parse import quote

import boto3
import structlog

from app.common.logging import configure_logging
from app.pipelines.stock_bars import ingest_stock_bars

log = structlog.get_logger()


def get_secret(secret_id: str) -> dict[str, str]:
    client = boto3.client("secretsmanager", region_name=os.environ["AWS_REGION"])
    response = client.get_secret_value(SecretId=secret_id)
    return json.loads(response["SecretString"])


async def backfill(symbol: str, start: datetime, chunk_days: int) -> None:
    end = datetime.now(timezone.utc) - timedelta(minutes=16)
    cursor = start
    total = 0
    while cursor < end:
        chunk_end = min(cursor + timedelta(days=chunk_days), end)
        inserted = await ingest_stock_bars(
            symbols=[symbol], start=cursor, end=chunk_end
        )
        total += inserted
        log.info(
            "stock_history_chunk_complete",
            symbol=symbol,
            start=cursor.isoformat(),
            end=chunk_end.isoformat(),
            inserted=inserted,
            total=total,
        )
        cursor = chunk_end


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("symbol")
    parser.add_argument("--start", default="2016-01-01")
    parser.add_argument("--chunk-days", type=int, default=31)
    args = parser.parse_args()

    rds = get_secret(os.environ["RDS_SECRET_ARN"])
    alpaca = get_secret(os.environ["ALPACA_SECRET_ARN"])
    username = quote(rds["username"], safe="")
    password = quote(rds["password"], safe="")
    os.environ["DATABASE_URL"] = (
        f"postgresql://{username}:{password}@{os.environ['RDS_ENDPOINT']}:"
        f"{os.environ.get('RDS_PORT', '5432')}/{os.environ.get('DB_NAME', 'finance')}"
    )
    os.environ["ALPACA_API_KEY"] = alpaca["ALPACA_API_KEY"]
    os.environ["ALPACA_API_SECRET"] = alpaca["ALPACA_API_SECRET"]

    configure_logging()
    start = datetime.fromisoformat(args.start).replace(tzinfo=timezone.utc)
    asyncio.run(backfill(args.symbol.upper(), start, args.chunk_days))


if __name__ == "__main__":
    main()
