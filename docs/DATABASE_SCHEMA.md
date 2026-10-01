# Database Schema Summary

## Core
- `core.company`
- `core.security`

## Market
- `market.stock_bar_1m`
- `market.stock_bar_1h`

## Options
- `options.contract`
- `options.snapshot`

## Fixed Income
- `fixed_income.bond`
- `fixed_income.bond_outstanding_balance` — dated outstanding-principal snapshots
- `fixed_income.trade`

## News / Analysts
- `news.article` — article-level classification and overall sentiment
- `news.article_company`
- `news.sentiment` — company-targeted, model-versioned sentiment
- `analyst.rating`

## Social
- `social.post`
- `social.post_company`
- `social.sentiment`

## Prediction Markets
- `prediction.market`
- `prediction.market_snapshot`
- `prediction.market_company`

## Ownership / Fundamentals
- `ownership.insider_transaction`
- `ownership.congress_trade`
- `fundamentals.sec_filing`
- `fundamentals.company_fact`

## Pipeline
- `pipeline.ingestion_run`
- `pipeline.watermark` — cursor keyed by pipeline, provider, and entity

## Derived
- `derived.option_anomaly`
- `derived.company_event`
- `derived.company_features_hourly`
