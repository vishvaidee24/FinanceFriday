from datetime import datetime
from psycopg.rows import dict_row
from app.db.connection import get_connection
from app.db.pipeline import finish_run, start_run
from app.providers.alpaca import AlpacaMarketDataProvider


def aggregate_stock_bars_1h(
    *, symbols: list[str], start: datetime | None = None, end: datetime | None = None
) -> int:
    """Upsert completed UTC clock hours from available one-minute bars."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                WITH hourly AS (
                    SELECT
                        b.security_id,
                        date_trunc('hour', b.ts) AS hour_ts,
                        (array_agg(b.open ORDER BY b.ts ASC))[1] AS open,
                        max(b.high) AS high,
                        min(b.low) AS low,
                        (array_agg(b.close ORDER BY b.ts DESC))[1] AS close,
                        sum(b.volume) AS volume,
                        sum(b.trade_count) AS trade_count,
                        CASE WHEN sum(b.volume) > 0 THEN
                            sum(b.vwap * b.volume) / sum(b.volume)
                        END AS vwap
                    FROM market.stock_bar_1m AS b
                    JOIN core.security AS s ON s.security_id = b.security_id
                    WHERE s.ticker = ANY(%s)
                      AND b.ts < date_trunc('hour', now())
                      AND (%s::timestamptz IS NULL OR b.ts >= date_trunc('hour', %s::timestamptz))
                      AND (%s::timestamptz IS NULL OR b.ts < %s)
                    GROUP BY b.security_id, date_trunc('hour', b.ts)
                )
                INSERT INTO market.stock_bar_1h (
                    security_id, ts, open, high, low, close,
                    volume, trade_count, vwap, source
                )
                SELECT
                    security_id, hour_ts, open, high, low, close,
                    volume, trade_count, vwap, 'alpaca_1m'
                FROM hourly
                ON CONFLICT (security_id, ts) DO UPDATE SET
                    open = EXCLUDED.open,
                    high = EXCLUDED.high,
                    low = EXCLUDED.low,
                    close = EXCLUDED.close,
                    volume = EXCLUDED.volume,
                    trade_count = EXCLUDED.trade_count,
                    vwap = EXCLUDED.vwap,
                    source = EXCLUDED.source
                """,
                (symbols, start, start, end, end),
            )
            affected = cur.rowcount
        conn.commit()
    return affected

async def ingest_stock_bars(
    *,
    symbols: list[str],
    start: datetime,
    end: datetime,
) -> int:
    run_id = start_run("stock_bars_1m", "alpaca")
    provider = AlpacaMarketDataProvider()

    try:
        bars = await provider.get_bars(
            symbols=symbols,
            start=start,
            end=end,
            timeframe="1Min",
        )

        with get_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    """
                    SELECT security_id, ticker
                    FROM core.security
                    WHERE ticker = ANY(%s)
                    """,
                    (symbols,),
                )
                security_by_symbol = {
                    row["ticker"]: row["security_id"] for row in cur.fetchall()
                }

                values = []
                for bar in bars:
                    security_id = security_by_symbol.get(bar.symbol)
                    if security_id is None:
                        continue
                    values.append(
                        (
                            security_id,
                            bar.timestamp,
                            bar.open,
                            bar.high,
                            bar.low,
                            bar.close,
                            bar.volume,
                            bar.trade_count,
                            bar.vwap,
                        )
                    )

                cur.executemany(
                    """
                    INSERT INTO market.stock_bar_1m (
                        security_id, ts, open, high, low, close,
                        volume, trade_count, vwap, provider
                    )
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,'alpaca')
                    ON CONFLICT (security_id, ts, provider)
                    DO UPDATE SET
                        open=EXCLUDED.open,
                        high=EXCLUDED.high,
                        low=EXCLUDED.low,
                        close=EXCLUDED.close,
                        volume=EXCLUDED.volume,
                        trade_count=EXCLUDED.trade_count,
                        vwap=EXCLUDED.vwap
                    """,
                    values,
                )
                inserted = len(values)
            conn.commit()

        aggregate_stock_bars_1h(symbols=symbols, start=start, end=end)
        finish_run(
            run_id,
            status="SUCCESS",
            records_received=len(bars),
            records_inserted=inserted,
        )
        return inserted

    except Exception as exc:
        finish_run(run_id, status="FAILED", error_message=str(exc))
        raise
