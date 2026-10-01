# Ingestion Map

All scheduled jobs run on the private FinanceFriday EC2 worker as `systemd`
one-shot services. The runner scripts retrieve credentials from AWS Secrets
Manager, call the Python pipelines, and write normalized records to private RDS
PostgreSQL. Every pipeline records its result in `pipeline.ingestion_run`.

## Scheduled ingestions

| Ingestion | Scope | Source | Schedule (UTC) | How it runs | RDS destination | Raw S3 archive |
|---|---|---|---|---|---|---|
| One-minute stock bars | Every active ticker in `core.security` | Alpaca Market Data API (`1Min`) | Hourly, with up to 2 minutes randomized delay | `finance-sofi-hourly.timer` -> `scripts/run_hourly.py` -> `tracked-stock-bars`; upserts the latest 120 minutes | `market.stock_bar_1m` | None currently |
| One-hour stock bars | Same securities as the one-minute run | Derived from `market.stock_bar_1m` | During every hourly stock-bar run | SQL aggregation uses completed UTC clock hours and upserts OHLCV/VWAP | `market.stock_bar_1h` | Not applicable; derived data |
| Company news | Supported active tickers from `core.security` (`SOFI`, `INTC`) | Google News RSS, company Investor Relations, SEC EDGAR submissions | Hourly at minute 10 | `finance-sofi-news-hourly.timer` -> `scripts/run_news_hourly.py` -> `tracked-news`; classifies and links each article to a company | `news.article`, `news.article_company` | `raw/<source>/<ticker>_news/year=YYYY/month=MM/day=DD/` |
| Insider transactions | Every active ticker with a CIK in `core.security`/`core.company` | SEC EDGAR Forms 3, 4, and 5 | Every 15 minutes | `finance-sofi-insiders.timer` -> `scripts/run_insiders.py` -> `tracked-insiders`; fetches unseen filings and parses ownership XML | `fundamentals.sec_filing`, `ownership.insider_transaction` | `raw/sec_edgar/<ticker>_insider_transactions/year=YYYY/month=MM/day=DD/` |
| Congressional trades | Every active ticker in `core.security` | House Clerk disclosures and Senate eFD PTRs | Daily at 06:30, with up to 15 minutes randomized delay | `finance-sofi-congress.timer` -> `scripts/run_congress.py` -> `sofi-congress`; parses current-year filings and retains matching assets | `ownership.congress_filing`, `ownership.congress_trade` | `raw/house_clerk/congress_trades/...` and `raw/senate_efd/congress_trades/...` for relevant filings |
| Executive-branch trades | All disclosed assets; matched to securities when a reported ticker exists | U.S. OGE Form 278/278-T plus Disclosed Capitol's historical OGE-derived dataset | Daily at 07:00, with up to 15 minutes randomized delay | `finance-executive-trades.timer` -> `scripts/run_executive.py` -> `executive-trades`; parses current OGE filings and refreshes the historical snapshot | `ownership.executive_filing`, `ownership.executive_trade` | `raw/oge/executive_trades/...` and `raw/disclosed_capitol/executive_trades/...` |
| Analyst ratings | Every active ticker in `core.security` | Financial Modeling Prep grades API | Daily at 07:00, with up to 20 minutes randomized delay | `finance-sofi-analyst-ratings.timer` -> `scripts/run_analyst_ratings.py` -> `tracked-analyst-ratings` | `analyst.rating` | `raw/fmp/grades/year=YYYY/month=MM/day=DD/` |

## Manual and backfill ingestions

| Ingestion | Invocation | Coverage | Destination | Raw S3 archive |
|---|---|---|---|---|
| Historical stock bars | `scripts/run_stock_history.py` | Requested ticker and date range, limited by Alpaca availability | `market.stock_bar_1m`; completed hours are aggregated into `market.stock_bar_1h` | None currently |
| Intel historical news | `scripts/run_intel_news_backfill.py --start-date YYYY-MM-DD` | Intel IR archive and SEC submission history from the requested date; Google News remains current-feed coverage | `news.article`, `news.article_company` | Same Intel news paths used by the scheduled news ingestion |
| Congressional history | `scripts/run_congress.py --year YYYY` | Requested House and Senate disclosure year | `ownership.congress_filing`, `ownership.congress_trade` | Same congressional paths used by the daily job |

## Configuration-driven scope

Stock bars, insider transactions, analyst ratings, and congressional matching
read active securities from `core.security`; adding an active ticker expands
those jobs without editing their ticker lists. Company news also reads
`core.security`, but currently has provider handlers only for `SOFI` and `INTC`.
Executive disclosures ingest every parsed transaction and attach
`company_id`/`security_id` when the disclosed ticker matches an existing
security.

Bond reference data and outstanding balances are currently populated by SQL
migrations rather than a scheduled ingestion job.
