import argparse
import asyncio
from datetime import date, datetime, timedelta, timezone
import structlog
from app.common.logging import configure_logging
from app.db.connection import get_connection
from app.db.securities import list_tracked_securities
from app.pipelines.stock_bars import (
    aggregate_stock_bar_rollups,
    aggregate_stock_bars_1h,
    ingest_stock_bars,
)
from app.pipelines.news import ingest_intel_news, ingest_sofi_news
from app.pipelines.ownership import ingest_insider_transactions, ingest_sofi_insider_transactions
from app.pipelines.congress import ingest_sofi_congress_trades
from app.pipelines.analyst import ingest_analyst_ratings, ingest_sofi_analyst_ratings
from app.pipelines.executive import ingest_executive_trades

log = structlog.get_logger()

def health() -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT current_database(), now()")
            database, now = cur.fetchone()
    log.info("health_ok", database=database, database_time=str(now))

async def stock_bars(symbols: list[str], minutes: int) -> None:
    end = datetime.now(timezone.utc)
    start = end - timedelta(minutes=minutes)
    inserted = await ingest_stock_bars(symbols=symbols, start=start, end=end)
    log.info("stock_bars_complete", symbols=symbols, inserted=inserted)

async def tracked_stock_bars(minutes: int) -> None:
    tracked_symbols = [security.ticker for security in list_tracked_securities()]
    if not tracked_symbols:
        return
    await stock_bars(tracked_symbols, minutes)

def stock_bars_1h(symbols: list[str]) -> None:
    affected = aggregate_stock_bars_1h(symbols=symbols)
    log.info("stock_bars_1h_complete", symbols=symbols, affected=affected)


def stock_bar_rollups(symbols: list[str], provider: str) -> None:
    affected = aggregate_stock_bar_rollups(symbols=symbols, provider=provider)
    log.info(
        "stock_bar_rollups_complete", symbols=symbols,
        provider=provider, affected=affected,
    )

async def sofi_news() -> None:
    inserted = await ingest_sofi_news()
    log.info("sofi_news_complete", inserted=inserted)

async def intel_news(start_date: date | None = None) -> None:
    inserted = await ingest_intel_news(start_date=start_date)
    log.info("intel_news_complete", inserted=inserted)

async def tracked_news() -> None:
    handlers = {"SOFI": ingest_sofi_news, "INTC": ingest_intel_news}
    for security in list_tracked_securities():
        handler = handlers.get(security.ticker)
        if handler is not None:
            inserted = await handler()
            log.info("tracked_news_complete", ticker=security.ticker, inserted=inserted)

async def sofi_insiders() -> None:
    inserted = await ingest_sofi_insider_transactions()
    log.info("sofi_insiders_complete", inserted=inserted)

async def sofi_congress(years: list[int] | None) -> None:
    inserted = await ingest_sofi_congress_trades(years=years)
    log.info("sofi_congress_complete", inserted=inserted)

async def executive_trades() -> None:
    inserted = await ingest_executive_trades()
    log.info("executive_trades_complete", inserted=inserted)

async def sofi_analyst_ratings() -> None:
    inserted = await ingest_sofi_analyst_ratings()
    log.info("sofi_analyst_ratings_complete", inserted=inserted)

async def analyst_ratings(symbols: list[str]) -> None:
    for symbol in symbols:
        inserted = await ingest_analyst_ratings(symbol)
        log.info("analyst_ratings_complete", symbol=symbol.upper(), inserted=inserted)

async def tracked_analyst_ratings() -> None:
    await analyst_ratings(
        [security.ticker for security in list_tracked_securities()]
    )

async def insiders(symbol: str, cik: str) -> None:
    inserted = await ingest_insider_transactions(symbol=symbol, cik=cik)
    log.info("insiders_complete", symbol=symbol.upper(), inserted=inserted)

async def tracked_insiders() -> None:
    for security in list_tracked_securities(require_cik=True):
        if security.cik is not None:
            await insiders(security.ticker, security.cik)

def main() -> None:
    configure_logging()
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("health")

    bars = sub.add_parser("stock-bars")
    bars.add_argument("symbols", nargs="+")
    bars.add_argument("--minutes", type=int, default=15)
    tracked_bars = sub.add_parser("tracked-stock-bars")
    tracked_bars.add_argument("--minutes", type=int, default=15)
    hourly_bars = sub.add_parser("stock-bars-1h")
    hourly_bars.add_argument("symbols", nargs="+")
    rollups = sub.add_parser("stock-bar-rollups")
    rollups.add_argument("symbols", nargs="+")
    rollups.add_argument("--provider", choices=("alpaca",), required=True)
    sub.add_parser("sofi-news")
    intel = sub.add_parser("intel-news")
    intel.add_argument("--start-date", type=date.fromisoformat)
    sub.add_parser("tracked-news")
    sub.add_parser("sofi-insiders")
    congress = sub.add_parser("sofi-congress")
    congress.add_argument("--year", type=int, action="append", dest="years")
    sub.add_parser("executive-trades")
    sub.add_parser("sofi-analyst-ratings")
    ratings = sub.add_parser("analyst-ratings")
    ratings.add_argument("symbols", nargs="+")
    sub.add_parser("tracked-analyst-ratings")
    insider = sub.add_parser("insiders")
    insider.add_argument("symbol")
    insider.add_argument("cik")
    sub.add_parser("tracked-insiders")

    args = parser.parse_args()
    if args.command == "health":
        health()
    elif args.command == "stock-bars":
        asyncio.run(stock_bars(args.symbols, args.minutes))
    elif args.command == "tracked-stock-bars":
        asyncio.run(tracked_stock_bars(args.minutes))
    elif args.command == "stock-bars-1h":
        stock_bars_1h(args.symbols)
    elif args.command == "stock-bar-rollups":
        stock_bar_rollups(args.symbols, args.provider)
    elif args.command == "sofi-news":
        asyncio.run(sofi_news())
    elif args.command == "intel-news":
        asyncio.run(intel_news(args.start_date))
    elif args.command == "tracked-news":
        asyncio.run(tracked_news())
    elif args.command == "sofi-insiders":
        asyncio.run(sofi_insiders())
    elif args.command == "sofi-congress":
        asyncio.run(sofi_congress(args.years))
    elif args.command == "executive-trades":
        asyncio.run(executive_trades())
    elif args.command == "sofi-analyst-ratings":
        asyncio.run(sofi_analyst_ratings())
    elif args.command == "analyst-ratings":
        asyncio.run(analyst_ratings(args.symbols))
    elif args.command == "tracked-analyst-ratings":
        asyncio.run(tracked_analyst_ratings())
    elif args.command == "insiders":
        asyncio.run(insiders(args.symbol, args.cik))
    elif args.command == "tracked-insiders":
        asyncio.run(tracked_insiders())

if __name__ == "__main__":
    main()
