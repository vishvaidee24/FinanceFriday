BEGIN;

COMMENT ON TABLE market.stock_bar_1h IS
    'Completed UTC clock-hour OHLCV bars derived from available one-minute observations.';

COMMENT ON COLUMN market.stock_bar_1h.ts IS
    'Inclusive start of the completed UTC clock-hour bucket.';

COMMENT ON COLUMN market.stock_bar_1h.vwap IS
    'Volume-weighted average of source one-minute VWAP values.';

COMMENT ON COLUMN market.stock_bar_1h.source IS
    'Derivation source; alpaca_1m identifies aggregation from Alpaca minute bars.';

COMMIT;
