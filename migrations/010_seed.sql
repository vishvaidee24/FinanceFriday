BEGIN;

INSERT INTO core.company (company_id, name, legal_name, cik, sector)
VALUES
(1, 'SoFi Technologies', 'SoFi Technologies, Inc.', '0001818874', 'Financials')
ON CONFLICT (company_id) DO UPDATE SET
    name = EXCLUDED.name,
    legal_name = EXCLUDED.legal_name,
    cik = EXCLUDED.cik,
    sector = EXCLUDED.sector,
    updated_at = now();

SELECT setval(
    pg_get_serial_sequence('core.company', 'company_id'),
    GREATEST((SELECT MAX(company_id) FROM core.company), 1),
    TRUE
);

INSERT INTO core.security (company_id, ticker, exchange, security_type)
SELECT company_id, 'SOFI', 'NASDAQ', 'COMMON_STOCK'
FROM core.company
WHERE cik = '0001818874'
AND NOT EXISTS (
  SELECT 1 FROM core.security WHERE ticker='SOFI' AND exchange='NASDAQ'
);

COMMIT;
