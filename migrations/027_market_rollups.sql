BEGIN;

CREATE TABLE IF NOT EXISTS market.stock_bar_5m (
    security_id BIGINT NOT NULL REFERENCES core.security(security_id),
    ts TIMESTAMPTZ NOT NULL,
    open NUMERIC(18,6), high NUMERIC(18,6), low NUMERIC(18,6), close NUMERIC(18,6),
    volume BIGINT, trade_count BIGINT, vwap NUMERIC(18,6),
    source TEXT NOT NULL,
    PRIMARY KEY (security_id, ts, source)
);
CREATE INDEX IF NOT EXISTS idx_stock_bar_5m_ts ON market.stock_bar_5m(ts DESC);

CREATE TABLE IF NOT EXISTS market.stock_bar_15m (
    security_id BIGINT NOT NULL REFERENCES core.security(security_id),
    ts TIMESTAMPTZ NOT NULL,
    open NUMERIC(18,6), high NUMERIC(18,6), low NUMERIC(18,6), close NUMERIC(18,6),
    volume BIGINT, trade_count BIGINT, vwap NUMERIC(18,6),
    source TEXT NOT NULL,
    PRIMARY KEY (security_id, ts, source)
);
CREATE INDEX IF NOT EXISTS idx_stock_bar_15m_ts ON market.stock_bar_15m(ts DESC);

CREATE TABLE IF NOT EXISTS market.stock_bar_power_hour (
    security_id BIGINT NOT NULL REFERENCES core.security(security_id),
    session_date DATE NOT NULL,
    session_window TEXT NOT NULL CHECK (session_window IN ('open_2h', 'close_2h')),
    window_start TIMESTAMPTZ NOT NULL,
    window_end TIMESTAMPTZ NOT NULL,
    open NUMERIC(18,6), high NUMERIC(18,6), low NUMERIC(18,6), close NUMERIC(18,6),
    volume BIGINT, trade_count BIGINT, vwap NUMERIC(18,6),
    source TEXT NOT NULL,
    PRIMARY KEY (security_id, session_date, session_window, source)
);
CREATE INDEX IF NOT EXISTS idx_stock_bar_power_hour_date
    ON market.stock_bar_power_hour(session_date DESC);

CREATE TABLE IF NOT EXISTS market.stock_bar_1d (
    security_id BIGINT NOT NULL REFERENCES core.security(security_id),
    trading_date DATE NOT NULL,
    open NUMERIC(18,6), high NUMERIC(18,6), low NUMERIC(18,6), close NUMERIC(18,6),
    volume BIGINT, trade_count BIGINT, vwap NUMERIC(18,6),
    source TEXT NOT NULL,
    PRIMARY KEY (security_id, trading_date, source)
);

CREATE TABLE IF NOT EXISTS market.stock_bar_1mo (
    security_id BIGINT NOT NULL REFERENCES core.security(security_id),
    month_start DATE NOT NULL,
    open NUMERIC(18,6), high NUMERIC(18,6), low NUMERIC(18,6), close NUMERIC(18,6),
    volume BIGINT, trade_count BIGINT, vwap NUMERIC(18,6),
    source TEXT NOT NULL,
    PRIMARY KEY (security_id, month_start, source)
);

COMMENT ON TABLE market.stock_bar_power_hour IS
    'OHLCV for the first two and final two hours of each observed US trading session.';
COMMENT ON COLUMN market.stock_bar_power_hour.source IS
    'Input series used for the rollup, such as alpaca_1m.';

COMMIT;
