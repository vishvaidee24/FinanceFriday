import time
from datetime import datetime, timezone

from app.common.metrics import (
    publish_ingestion_error,
    publish_news_articles,
    publish_stock_ingest_age,
    publish_worker_execution_time,
)
from app.db.connection import get_connection

_START_TIMES: dict[int, float] = {}


def _worker_name(pipeline: str) -> str:
    if pipeline == "stock_bars_1m":
        return "stock"
    if pipeline.endswith("_news"):
        return "news"
    if "analyst" in pipeline:
        return "analyst"
    if "insider" in pipeline:
        return "insider"
    if "congress" in pipeline or "executive" in pipeline:
        return "government_trades"
    return pipeline

def start_run(pipeline: str, provider: str) -> int:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO pipeline.ingestion_run
                    (pipeline, provider, status, started_at)
                VALUES (%s, %s, 'RUNNING', %s)
                RETURNING ingestion_run_id
                """,
                (pipeline, provider, datetime.now(timezone.utc)),
            )
            run_id = cur.fetchone()[0]
        conn.commit()
    _START_TIMES[run_id] = time.monotonic()
    return run_id

def finish_run(
    run_id: int,
    *,
    status: str,
    records_received: int | None = None,
    records_inserted: int | None = None,
    error_message: str | None = None,
) -> None:
    pipeline = "unknown"
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT pipeline FROM pipeline.ingestion_run WHERE ingestion_run_id=%s",
                (run_id,),
            )
            row = cur.fetchone()
            if row is not None:
                pipeline = row[0]
            cur.execute(
                """
                UPDATE pipeline.ingestion_run
                SET completed_at=%s,
                    status=%s,
                    records_received=%s,
                    records_inserted=%s,
                    error_message=%s
                WHERE ingestion_run_id=%s
                """,
                (
                    datetime.now(timezone.utc),
                    status,
                    records_received,
                    records_inserted,
                    error_message,
                    run_id,
                ),
            )
        conn.commit()

    worker = _worker_name(pipeline)
    started = _START_TIMES.pop(run_id, None)
    if started is not None:
        publish_worker_execution_time(worker=worker, seconds=time.monotonic() - started)
    if status == "SUCCESS":
        if worker == "stock":
            publish_stock_ingest_age(0)
        elif worker == "news":
            publish_news_articles(records_received or 0)
    else:
        publish_ingestion_error(worker=worker)
