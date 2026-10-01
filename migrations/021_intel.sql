BEGIN;

INSERT INTO core.company (name, legal_name, cik, sector)
VALUES ('Intel', 'Intel Corporation', '0000050863', 'Information Technology')
ON CONFLICT (cik) WHERE cik IS NOT NULL DO UPDATE SET
    name = EXCLUDED.name,
    legal_name = EXCLUDED.legal_name,
    sector = EXCLUDED.sector,
    updated_at = now();

INSERT INTO core.security (company_id, ticker, exchange, security_type)
SELECT company_id, 'INTC', 'NASDAQ', 'COMMON_STOCK'
FROM core.company
WHERE cik = '0000050863'
AND NOT EXISTS (
    SELECT 1 FROM core.security WHERE ticker = 'INTC' AND exchange = 'NASDAQ'
);

COMMIT;
