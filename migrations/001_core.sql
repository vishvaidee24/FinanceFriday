BEGIN;
CREATE SCHEMA IF NOT EXISTS core;

CREATE TABLE IF NOT EXISTS core.company (
    company_id BIGSERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    legal_name TEXT,
    cik TEXT,
    lei TEXT,
    sector TEXT,
    industry TEXT,
    website TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_company_cik
ON core.company(cik) WHERE cik IS NOT NULL;

CREATE TABLE IF NOT EXISTS core.security (
    security_id BIGSERIAL PRIMARY KEY,
    company_id BIGINT REFERENCES core.company(company_id),
    ticker TEXT,
    exchange TEXT,
    security_type TEXT NOT NULL,
    cusip TEXT,
    isin TEXT,
    figi TEXT,
    currency CHAR(3) DEFAULT 'USD',
    valid_from DATE,
    valid_to DATE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_security_ticker_exchange
ON core.security(ticker, exchange);
COMMIT;
