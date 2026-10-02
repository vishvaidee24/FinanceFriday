BEGIN;

INSERT INTO core.company (name, legal_name, cik, sector)
VALUES
    ('SPDR S&P 500 ETF Trust', 'SPDR S&P 500 ETF Trust', '0000884394', 'Exchange Traded Fund'),
    ('Invesco QQQ Trust', 'Invesco QQQ Trust, Series 1', '0001067839', 'Exchange Traded Fund'),
    ('Walmart', 'Walmart Inc.', '0000104169', 'Consumer Staples'),
    ('Disney', 'The Walt Disney Company', '0001744489', 'Communication Services')
ON CONFLICT (cik) WHERE cik IS NOT NULL DO UPDATE SET
    name = EXCLUDED.name,
    legal_name = EXCLUDED.legal_name,
    sector = EXCLUDED.sector,
    updated_at = now();

INSERT INTO core.security (company_id, ticker, exchange, security_type)
SELECT c.company_id, v.ticker, v.exchange, v.security_type
FROM (VALUES
    ('0000884394', 'SPY', 'NYSE ARCA', 'ETF'),
    ('0001067839', 'QQQ', 'NASDAQ', 'ETF'),
    ('0000104169', 'WMT', 'NYSE', 'COMMON_STOCK'),
    ('0001744489', 'DIS', 'NYSE', 'COMMON_STOCK')
) AS v(cik, ticker, exchange, security_type)
JOIN core.company c ON c.cik = v.cik
WHERE NOT EXISTS (
    SELECT 1 FROM core.security s
    WHERE s.ticker = v.ticker AND s.exchange = v.exchange
);

COMMIT;
