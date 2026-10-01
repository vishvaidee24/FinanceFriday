BEGIN;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM core.company AS c
        JOIN core.security AS s ON s.company_id = c.company_id
        WHERE c.cik = '0000050863' AND s.ticker = 'INTC'
    ) THEN
        RAISE EXCEPTION 'INTC company mapping is missing or inconsistent';
    END IF;
END $$;

CREATE TABLE IF NOT EXISTS fixed_income.bond_outstanding_balance (
    bond_outstanding_balance_id BIGSERIAL PRIMARY KEY,
    bond_id BIGINT NOT NULL REFERENCES fixed_income.bond(bond_id),
    as_of_date DATE NOT NULL,
    outstanding_principal NUMERIC(20, 2) NOT NULL
        CHECK (outstanding_principal >= 0),
    source TEXT NOT NULL,
    source_filing_date DATE,
    source_url TEXT,
    ingested_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (bond_id, as_of_date, source)
);

CREATE INDEX IF NOT EXISTS bond_outstanding_balance_latest_idx
    ON fixed_income.bond_outstanding_balance (bond_id, as_of_date DESC);

INSERT INTO fixed_income.bond (
    company_id, cusip, isin, issue_date, maturity_date, coupon_rate,
    coupon_type, seniority, callable, convertible, is_convertible,
    description, status
)
SELECT
    c.company_id, v.cusip, v.isin, DATE '2026-04-30', v.maturity_date,
    v.coupon_rate, 'fixed', 'senior unsecured', TRUE, FALSE, FALSE,
    v.description, 'outstanding'
FROM core.company AS c
CROSS JOIN (VALUES
    ('458140CQ1', 'US458140CQ17', DATE '2031-06-01', 4.650,
     '4.650% Senior Notes due June 1, 2031'),
    ('458140CR9', 'US458140CR99', DATE '2033-08-15', 5.000,
     '5.000% Senior Notes due August 15, 2033'),
    ('458140CS7', 'US458140CS72', DATE '2036-05-15', 5.300,
     '5.300% Senior Notes due May 15, 2036'),
    ('458140CU2', 'US458140CU29', DATE '2056-05-15', 6.125,
     '6.125% Senior Notes due May 15, 2056'),
    ('458140CV0', 'US458140CV02', DATE '2066-05-15', 6.200,
     '6.200% Senior Notes due May 15, 2066')
) AS v(cusip, isin, maturity_date, coupon_rate, description)
WHERE c.cik = '0000050863'
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
    status = EXCLUDED.status;

INSERT INTO fixed_income.bond_outstanding_balance (
    bond_id, as_of_date, outstanding_principal, source,
    source_filing_date, source_url
)
SELECT
    b.bond_id,
    DATE '2026-06-27',
    v.outstanding_principal,
    'SEC 10-Q',
    DATE '2026-07-24',
    'https://www.sec.gov/Archives/edgar/data/50863/000005086326000157/intc-20260627.htm'
FROM (VALUES
    ('458140CQ1'::TEXT, 1000000000.00::NUMERIC),
    ('458140CR9'::TEXT, 1000000000.00::NUMERIC),
    ('458140CS7'::TEXT, 2250000000.00::NUMERIC),
    ('458140CU2'::TEXT, 1750000000.00::NUMERIC),
    ('458140CV0'::TEXT,  500000000.00::NUMERIC)
) AS v(cusip, outstanding_principal)
JOIN fixed_income.bond AS b ON b.cusip = v.cusip
ON CONFLICT (bond_id, as_of_date, source) DO UPDATE SET
    outstanding_principal = EXCLUDED.outstanding_principal,
    source_filing_date = EXCLUDED.source_filing_date,
    source_url = EXCLUDED.source_url;

COMMIT;
