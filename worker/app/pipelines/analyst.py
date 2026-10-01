from datetime import datetime, timezone

from app.common.s3 import RawArchive
from app.db.connection import get_connection
from app.db.pipeline import finish_run, start_run
from app.providers.fmp import FmpProvider


async def ingest_analyst_ratings(symbol: str) -> int:
    symbol = symbol.upper()
    run_id = start_run(f"{symbol.lower()}_analyst_ratings", "fmp_grades")
    observed_at = datetime.now(timezone.utc)
    try:
        payload, ratings = await FmpProvider().get_grades(symbol)
        raw_key = RawArchive().put_json(
            provider="fmp",
            dataset="grades",
            object_name=f"{symbol}-run-{run_id}",
            payload=payload,
            observed_at=observed_at,
        )
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """SELECT c.company_id FROM core.company c
                       JOIN core.security s ON s.company_id = c.company_id
                       WHERE s.ticker = %s
                       ORDER BY s.valid_to NULLS FIRST, s.security_id DESC LIMIT 1""",
                    (symbol,),
                )
                company = cur.fetchone()
                if company is None:
                    raise RuntimeError(f"{symbol} company row is missing")
                inserted = 0
                for rating in ratings:
                    cur.execute(
                        """
                        INSERT INTO analyst.rating (
                            company_id, firm, analyst_name, published_at, action,
                            prior_rating, new_rating, prior_price_target,
                            new_price_target, provider, provider_record_key,
                            source_url, raw_s3_key, ingested_at
                        ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                        ON CONFLICT (provider, provider_record_key)
                            WHERE provider_record_key IS NOT NULL
                        DO UPDATE SET
                            firm=EXCLUDED.firm,
                            published_at=EXCLUDED.published_at,
                            action=EXCLUDED.action,
                            prior_rating=EXCLUDED.prior_rating,
                            new_rating=EXCLUDED.new_rating,
                            raw_s3_key=EXCLUDED.raw_s3_key,
                            ingested_at=EXCLUDED.ingested_at
                        RETURNING (xmax = 0)
                        """,
                        (
                            company[0], rating.firm, rating.analyst_name,
                            rating.published_at, rating.action,
                            rating.prior_rating, rating.new_rating,
                            rating.prior_price_target, rating.new_price_target,
                            rating.provider, rating.provider_record_key,
                            rating.source_url, raw_key, observed_at,
                        ),
                    )
                    inserted += int(cur.fetchone()[0])
            conn.commit()
        finish_run(
            run_id,
            status="SUCCESS",
            records_received=len(ratings),
            records_inserted=inserted,
        )
        return inserted
    except Exception as exc:
        finish_run(run_id, status="FAILED", error_message=str(exc))
        raise


async def ingest_sofi_analyst_ratings() -> int:
    return await ingest_analyst_ratings("SOFI")
