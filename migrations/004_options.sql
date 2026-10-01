BEGIN;
CREATE SCHEMA IF NOT EXISTS options;

CREATE TABLE IF NOT EXISTS options.contract (
    option_id BIGSERIAL PRIMARY KEY,
    underlying_id BIGINT NOT NULL REFERENCES core.security(security_id),
    occ_symbol TEXT NOT NULL UNIQUE,
    expiration_date DATE NOT NULL,
    strike NUMERIC(18,4) NOT NULL,
    option_type CHAR(1) NOT NULL CHECK (option_type IN ('C','P')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS options.snapshot (
    option_id BIGINT NOT NULL REFERENCES options.contract(option_id),
    ts TIMESTAMPTZ NOT NULL,
    bid NUMERIC(18,6),
    ask NUMERIC(18,6),
    last NUMERIC(18,6),
    volume BIGINT,
    open_interest BIGINT,
    implied_volatility NUMERIC(12,8),
    delta NUMERIC(12,8),
    gamma NUMERIC(12,8),
    theta NUMERIC(12,8),
    vega NUMERIC(12,8),
    underlying_price NUMERIC(18,6),
    provider TEXT NOT NULL,
    PRIMARY KEY(option_id, ts, provider)
);
COMMIT;
