from dataclasses import dataclass

from app.db.connection import get_connection


@dataclass(frozen=True, slots=True)
class TrackedSecurity:
    ticker: str
    cik: str | None


def list_tracked_securities(*, require_cik: bool = False) -> list[TrackedSecurity]:
    """Return active, ticker-bearing securities in deterministic order."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT DISTINCT upper(s.ticker) AS ticker, c.cik
                FROM core.security AS s
                LEFT JOIN core.company AS c ON c.company_id = s.company_id
                WHERE s.ticker IS NOT NULL
                  AND btrim(s.ticker) <> ''
                  AND (s.valid_to IS NULL OR s.valid_to >= current_date)
                  AND (%s = FALSE OR c.cik IS NOT NULL)
                ORDER BY ticker, c.cik NULLS LAST
                """,
                (require_cik,),
            )
            return [TrackedSecurity(ticker=row[0], cik=row[1]) for row in cur.fetchall()]
