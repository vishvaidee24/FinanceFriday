BEGIN;
CREATE SCHEMA IF NOT EXISTS fixed_income;

CREATE TABLE IF NOT EXISTS fixed_income.bond (
    bond_id BIGSERIAL PRIMARY KEY,
    company_id BIGINT REFERENCES core.company(company_id),
    cusip TEXT UNIQUE,
    isin TEXT,
    figi TEXT,
    issue_date DATE,
    maturity_date DATE,
    coupon_rate NUMERIC,
    coupon_type TEXT,
    seniority TEXT,
    callable BOOLEAN,
    convertible BOOLEAN,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS fixed_income.trade (
    bond_trade_id BIGSERIAL PRIMARY KEY,
    bond_id BIGINT NOT NULL REFERENCES fixed_income.bond(bond_id),
    execution_ts TIMESTAMPTZ NOT NULL,
    price NUMERIC,
    yield NUMERIC,
    quantity NUMERIC,
    provider TEXT NOT NULL,
    provider_trade_id TEXT,
    UNIQUE(provider, provider_trade_id)
);
COMMIT;
