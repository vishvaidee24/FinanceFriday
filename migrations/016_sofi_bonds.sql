BEGIN;

ALTER TABLE fixed_income.bond
    ADD COLUMN IF NOT EXISTS trace_symbol TEXT,
    ADD COLUMN IF NOT EXISTS description TEXT,
    ADD COLUMN IF NOT EXISTS is_convertible BOOLEAN,
    ADD COLUMN IF NOT EXISTS principal_outstanding NUMERIC,
    ADD COLUMN IF NOT EXISTS status TEXT,
    ADD COLUMN IF NOT EXISTS source_url TEXT,
    ADD COLUMN IF NOT EXISTS as_of_date DATE;

DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'fixed_income' AND table_name = 'trade' AND column_name = 'bond_trade_id'
    ) AND NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'fixed_income' AND table_name = 'trade' AND column_name = 'trade_id'
    ) THEN
        ALTER TABLE fixed_income.trade RENAME COLUMN bond_trade_id TO trade_id;
    END IF;
END $$;

ALTER TABLE fixed_income.trade
    ADD COLUMN IF NOT EXISTS source_trade_id TEXT,
    ADD COLUMN IF NOT EXISTS ingested_at TIMESTAMPTZ NOT NULL DEFAULT now();

CREATE UNIQUE INDEX IF NOT EXISTS fixed_income_trade_source_id_idx
    ON fixed_income.trade(provider, source_trade_id)
    WHERE source_trade_id IS NOT NULL;

INSERT INTO fixed_income.bond (
    company_id, cusip, isin, issue_date, maturity_date, coupon_rate,
    coupon_type, seniority, callable, convertible, is_convertible,
    description, principal_outstanding, status, source_url, as_of_date
) SELECT
    c.company_id, v.cusip, v.isin, v.issue_date, v.maturity_date, v.coupon_rate,
    v.coupon_type, v.seniority, v.callable, v.convertible, v.is_convertible,
    v.description, v.principal_outstanding, v.status, v.source_url, v.as_of_date
FROM core.company AS c
CROSS JOIN (VALUES
    (
        '83406FAA0', 'US83406FAA03', DATE '2021-10-04', DATE '2026-10-15', 0,
        'zero coupon', 'senior unsecured', TRUE, TRUE, TRUE,
        '0% Convertible Senior Notes due October 15, 2026', 428022000,
        'outstanding',
        'https://www.sec.gov/Archives/edgar/data/1818874/000181887426000054/sofi-20260630.htm',
        DATE '2026-06-30'
    ),
    (
        '83406FAC6', 'US83406FAC68', DATE '2024-03-08', DATE '2029-03-15', 1.25,
        'fixed', 'senior unsecured', TRUE, TRUE, TRUE,
        '1.25% Convertible Senior Notes due March 15, 2029', 862500000,
        'outstanding',
        'https://www.sec.gov/Archives/edgar/data/1818874/000181887426000054/sofi-20260630.htm',
        DATE '2026-06-30'
    )
) AS v(
    cusip, isin, issue_date, maturity_date, coupon_rate, coupon_type, seniority,
    callable, convertible, is_convertible, description, principal_outstanding,
    status, source_url, as_of_date
)
WHERE c.cik = '0001818874'
ON CONFLICT (cusip) DO UPDATE SET
    company_id = EXCLUDED.company_id,
    isin = EXCLUDED.isin,
    issue_date = EXCLUDED.issue_date,
    maturity_date = EXCLUDED.maturity_date,
    coupon_rate = EXCLUDED.coupon_rate,
    coupon_type = EXCLUDED.coupon_type,
    seniority = EXCLUDED.seniority,
    callable = EXCLUDED.callable,
    convertible = EXCLUDED.convertible,
    is_convertible = EXCLUDED.is_convertible,
    description = EXCLUDED.description,
    principal_outstanding = EXCLUDED.principal_outstanding,
    status = EXCLUDED.status,
    source_url = EXCLUDED.source_url,
    as_of_date = EXCLUDED.as_of_date;

COMMIT;
