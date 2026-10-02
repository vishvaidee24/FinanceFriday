BEGIN;
CREATE SCHEMA IF NOT EXISTS market;

CREATE TABLE IF NOT EXISTS market.stock_bar_1m (
    security_id BIGINT NOT NULL REFERENCES core.security(security_id),
    ts TIMESTAMPTZ NOT NULL,
    open NUMERIC(18,6),
    high NUMERIC(18,6),
    low NUMERIC(18,6),
    close NUMERIC(18,6),
    volume BIGINT,
    trade_count INTEGER,
    vwap NUMERIC(18,6),
    provider TEXT NOT NULL,
    ingested_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (security_id, ts, provider)
);

CREATE INDEX IF NOT EXISTS idx_stock_bar_1m_ts
ON market.stock_bar_1m(ts DESC);

CREATE TABLE IF NOT EXISTS market.stock_bar_1h (
    security_id BIGINT NOT NULL REFERENCES core.security(security_id),
    ts TIMESTAMPTZ NOT NULL,
    open NUMERIC(18,6),
    high NUMERIC(18,6),
    low NUMERIC(18,6),
    close NUMERIC(18,6),
    volume BIGINT,
    trade_count BIGINT,
    vwap NUMERIC(18,6),
    source TEXT NOT NULL DEFAULT 'derived',
    PRIMARY KEY (security_id, ts, source)
);
COMMIT;
