BEGIN;
CREATE SCHEMA IF NOT EXISTS derived;

CREATE TABLE IF NOT EXISTS derived.option_anomaly (
    option_id BIGINT REFERENCES options.contract(option_id),
    ts TIMESTAMPTZ,
    volume BIGINT,
    prior_open_interest BIGINT,
    volume_oi_ratio NUMERIC,
    volume_zscore NUMERIC,
    notional_value NUMERIC,
    iv_change_1d NUMERIC,
    distance_from_spot NUMERIC,
    days_to_expiry INTEGER,
    anomaly_score NUMERIC,
    PRIMARY KEY(option_id, ts)
);

CREATE TABLE IF NOT EXISTS derived.company_event (
    event_id BIGSERIAL PRIMARY KEY,
    company_id BIGINT REFERENCES core.company(company_id),
    occurred_at TIMESTAMPTZ,
    available_at TIMESTAMPTZ NOT NULL,
    event_type TEXT NOT NULL,
    source_type TEXT,
    source_id TEXT,
    sentiment_score NUMERIC,
    importance_score NUMERIC,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE TABLE IF NOT EXISTS derived.company_features_hourly (
    company_id BIGINT REFERENCES core.company(company_id),
    ts TIMESTAMPTZ,
    stock_price NUMERIC,
    return_1h NUMERIC,
    return_4h NUMERIC,
    return_1d NUMERIC,
    volume NUMERIC,
    volume_zscore NUMERIC,
    call_volume NUMERIC,
    put_volume NUMERIC,
    call_put_ratio NUMERIC,
    call_open_interest NUMERIC,
    put_open_interest NUMERIC,
    unusual_call_score NUMERIC,
    unusual_put_score NUMERIC,
    avg_iv NUMERIC,
    iv_change NUMERIC,
    news_count INTEGER,
    news_sentiment NUMERIC,
    reddit_mentions INTEGER,
    reddit_sentiment NUMERIC,
    analyst_upgrade_count INTEGER,
    analyst_downgrade_count INTEGER,
    price_target_change NUMERIC,
    insider_buy_value_30d NUMERIC,
    insider_sell_value_30d NUMERIC,
    congress_buy_count_30d INTEGER,
    congress_sell_count_30d INTEGER,
    bond_yield NUMERIC,
    bond_yield_change NUMERIC,
    bond_volume NUMERIC,
    prediction_delta NUMERIC,
    PRIMARY KEY(company_id, ts)
);
COMMIT;
