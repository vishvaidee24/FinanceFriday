from datetime import datetime, timezone
from typing import Any
from zoneinfo import ZoneInfo

from psycopg.rows import dict_row

from app.common.s3 import RawArchive
from app.db.connection import get_connection
from app.db.pipeline import finish_run, start_run
from app.models.market import StockBar
from app.providers.alpaca import AlpacaMarketDataProvider
from app.providers.base import MarketDataProvider


def aggregate_stock_bars_1h(
    *,
    symbols: list[str],
    provider: str = "alpaca",
    start: datetime | None = None,
    end: datetime | None = None,
) -> int:
    """Upsert completed UTC clock hours from one provider's minute bars."""
    source = f"{provider}_1m"
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
                      AND b.provider = %s
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
                    volume, trade_count, vwap, %s
                FROM hourly
                ON CONFLICT (security_id, ts, source) DO UPDATE SET
                    open = EXCLUDED.open,
                    high = EXCLUDED.high,
                    low = EXCLUDED.low,
                    close = EXCLUDED.close,
                    volume = EXCLUDED.volume,
                    trade_count = EXCLUDED.trade_count,
                    vwap = EXCLUDED.vwap,
                    source = EXCLUDED.source
                """,
                (symbols, provider, start, start, end, end, source),
            )
            affected = cur.rowcount
        conn.commit()
    return affected

def _store_stock_bars(*, bars: list[StockBar], symbols: list[str], provider: str) -> int:
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
                row["ticker"].upper(): row["security_id"] for row in cur.fetchall()
            }

            values = []
            for bar in bars:
                security_id = security_by_symbol.get(bar.symbol.upper())
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
                        provider,
                    )
                )

            cur.executemany(
                """
                INSERT INTO market.stock_bar_1m (
                    security_id, ts, open, high, low, close,
                    volume, trade_count, vwap, provider
                )
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
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
    return inserted


def aggregate_stock_bar_rollups(
    *, symbols: list[str], provider: str, start: datetime | None = None,
    end: datetime | None = None,
) -> int:
    """Build completed interval, session-window, daily, and monthly bars."""
    if provider != "alpaca":
        raise ValueError(f"Unsupported rollup provider: {provider}")
    input_table, provider_column, provider_value = (
        "market.stock_bar_1m", "provider", "alpaca"
    )
    source = "alpaca_1m"

    query_start = start
    if start is not None:
        eastern = start.astimezone(ZoneInfo("America/New_York"))
        query_start = eastern.replace(
            day=1, hour=0, minute=0, second=0, microsecond=0
        ).astimezone(timezone.utc)
    params = (symbols, provider_value, query_start, query_start, end, end)
    base_where = f"""
        FROM {input_table} AS b
        JOIN core.security AS s ON s.security_id = b.security_id
        WHERE s.ticker = ANY(%s) AND b.{provider_column} = %s
          AND (b.ts AT TIME ZONE 'America/New_York')::time >= TIME '09:30'
          AND (b.ts AT TIME ZONE 'America/New_York')::time < TIME '16:00'
          AND (%s::timestamptz IS NULL OR b.ts >= %s)
          AND (%s::timestamptz IS NULL OR b.ts < %s)
    """
    affected = 0
    with get_connection() as conn:
        with conn.cursor() as cur:
            if provider == "alpaca":
                for minutes, table in ((5, "stock_bar_5m"), (15, "stock_bar_15m")):
                    cur.execute(
                        f"""
                        WITH bars AS (
                            SELECT b.*, date_bin('{minutes} minutes', b.ts,
                                TIMESTAMPTZ '2000-01-01 00:00:00+00') AS bucket
                            {base_where}
                        ), rollup AS (
                            SELECT security_id, bucket,
                                (array_agg(open ORDER BY ts))[1] AS open,
                                max(high) AS high, min(low) AS low,
                                (array_agg(close ORDER BY ts DESC))[1] AS close,
                                sum(volume) AS volume, sum(trade_count) AS trade_count,
                                CASE WHEN sum(volume) > 0
                                    THEN sum(vwap * volume) / sum(volume) END AS vwap
                            FROM bars
                            WHERE bucket < date_bin('{minutes} minutes', now(),
                                TIMESTAMPTZ '2000-01-01 00:00:00+00')
                            GROUP BY security_id, bucket
                        )
                        INSERT INTO market.{table}
                            (security_id, ts, open, high, low, close, volume,
                             trade_count, vwap, source)
                        SELECT security_id, bucket, open, high, low, close, volume,
                               trade_count, vwap, %s FROM rollup
                        ON CONFLICT (security_id, ts, source) DO UPDATE SET
                            open=EXCLUDED.open, high=EXCLUDED.high, low=EXCLUDED.low,
                            close=EXCLUDED.close, volume=EXCLUDED.volume,
                            trade_count=EXCLUDED.trade_count, vwap=EXCLUDED.vwap
                        """,
                        (*params, source),
                    )
                    affected += cur.rowcount

            cur.execute(
                f"""
                WITH bars AS (
                    SELECT b.*,
                        (b.ts AT TIME ZONE 'America/New_York')::date AS session_date
                    {base_where}
                ), sessions AS (
                    SELECT security_id, session_date, min(ts) AS session_start,
                           max(ts) + interval '1 minute' AS session_end
                    FROM bars
                    GROUP BY security_id, session_date
                ), windows AS (
                    SELECT security_id, session_date, 'open_2h'::text AS session_window,
                           session_start AS window_start,
                           least(session_start + interval '2 hours', session_end) AS window_end
                    FROM sessions
                    UNION ALL
                    SELECT security_id, session_date, 'close_2h',
                           greatest(session_end - interval '2 hours', session_start), session_end
                    FROM sessions
                ), rollup AS (
                    SELECT w.security_id, w.session_date, w.session_window,
                           w.window_start, w.window_end,
                           (array_agg(b.open ORDER BY b.ts))[1] AS open,
                           max(b.high) AS high, min(b.low) AS low,
                           (array_agg(b.close ORDER BY b.ts DESC))[1] AS close,
                           sum(b.volume) AS volume, sum(b.trade_count) AS trade_count,
                           CASE WHEN sum(b.volume) > 0
                               THEN sum(b.vwap * b.volume) / sum(b.volume) END AS vwap
                    FROM windows w JOIN bars b ON b.security_id=w.security_id
                        AND b.session_date=w.session_date
                        AND b.ts >= w.window_start AND b.ts < w.window_end
                    WHERE w.session_date < (now() AT TIME ZONE 'America/New_York')::date
                    GROUP BY w.security_id, w.session_date, w.session_window,
                             w.window_start, w.window_end
                )
                INSERT INTO market.stock_bar_power_hour
                    (security_id, session_date, session_window, window_start, window_end,
                     open, high, low, close, volume, trade_count, vwap, source)
                SELECT security_id, session_date, session_window, window_start, window_end,
                       open, high, low, close, volume, trade_count, vwap, %s FROM rollup
                ON CONFLICT (security_id, session_date, session_window, source) DO UPDATE SET
                    window_start=EXCLUDED.window_start, window_end=EXCLUDED.window_end,
                    open=EXCLUDED.open, high=EXCLUDED.high, low=EXCLUDED.low,
                    close=EXCLUDED.close, volume=EXCLUDED.volume,
                    trade_count=EXCLUDED.trade_count, vwap=EXCLUDED.vwap
                """,
                (*params, source),
            )
            affected += cur.rowcount

            for period, table, column in (
                ("day", "stock_bar_1d", "trading_date"),
                ("month", "stock_bar_1mo", "month_start"),
            ):
                period_expr = (
                    "(b.ts AT TIME ZONE 'America/New_York')::date"
                    if period == "day"
                    else "date_trunc('month', b.ts AT TIME ZONE 'America/New_York')::date"
                )
                completed = (
                    "(now() AT TIME ZONE 'America/New_York')::date"
                    if period == "day"
                    else "date_trunc('month', now() AT TIME ZONE 'America/New_York')::date"
                )
                cur.execute(
                    f"""
                    WITH bars AS (
                        SELECT b.*, {period_expr} AS period_start {base_where}
                    ), rollup AS (
                        SELECT security_id, period_start,
                            (array_agg(open ORDER BY ts))[1] AS open,
                            max(high) AS high, min(low) AS low,
                            (array_agg(close ORDER BY ts DESC))[1] AS close,
                            sum(volume) AS volume, sum(trade_count) AS trade_count,
                            CASE WHEN sum(volume) > 0
                                THEN sum(vwap * volume) / sum(volume) END AS vwap
                        FROM bars WHERE period_start < {completed}
                        GROUP BY security_id, period_start
                    )
                    INSERT INTO market.{table}
                        (security_id, {column}, open, high, low, close, volume,
                         trade_count, vwap, source)
                    SELECT security_id, period_start, open, high, low, close, volume,
                           trade_count, vwap, %s FROM rollup
                    ON CONFLICT (security_id, {column}, source) DO UPDATE SET
                        open=EXCLUDED.open, high=EXCLUDED.high, low=EXCLUDED.low,
                        close=EXCLUDED.close, volume=EXCLUDED.volume,
                        trade_count=EXCLUDED.trade_count, vwap=EXCLUDED.vwap
                    """,
                    (*params, source),
                )
                affected += cur.rowcount
        conn.commit()
    return affected


async def _ingest_stock_bars(
    *,
    symbols: list[str],
    start: datetime,
    end: datetime,
    provider_name: str,
    provider: MarketDataProvider,
    archive_pages: list[dict[str, Any]] | None = None,
) -> int:
    run_id = start_run("stock_bars_1m", provider_name)

    try:
        bars = await provider.get_bars(
            symbols=symbols,
            start=start,
            end=end,
            timeframe="1Min",
        )

        if archive_pages:
            archive = RawArchive()
            observed_at = datetime.now(timezone.utc)
            window = f"{start:%Y%m%dT%H%M%S}-{end:%Y%m%dT%H%M%S}"
            joined_symbols = "-".join(sorted(symbols))
            for index, payload in enumerate(archive_pages, start=1):
                archive.put_json(
                    provider=provider_name,
                    dataset="stock_bars_1m",
                    object_name=f"{joined_symbols}-{window}-page-{index:04d}",
                    payload=payload,
                    observed_at=observed_at,
                )

        inserted = _store_stock_bars(
            bars=bars, symbols=symbols, provider=provider_name
        )
        aggregate_stock_bars_1h(
            symbols=symbols,
            provider=provider_name,
            start=start,
            end=end,
        )
        if provider_name == "alpaca":
            aggregate_stock_bar_rollups(
                symbols=symbols, provider="alpaca", start=start, end=end
            )
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


async def ingest_stock_bars(
    *, symbols: list[str], start: datetime, end: datetime
) -> int:
    return await _ingest_stock_bars(
        symbols=symbols,
        start=start,
        end=end,
        provider_name="alpaca",
        provider=AlpacaMarketDataProvider(),
    )
