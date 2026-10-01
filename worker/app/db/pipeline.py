from datetime import datetime, timezone
from app.db.connection import get_connection

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
    return run_id

def finish_run(
    run_id: int,
    *,
    status: str,
    records_received: int | None = None,
    records_inserted: int | None = None,
    error_message: str | None = None,
) -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
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
