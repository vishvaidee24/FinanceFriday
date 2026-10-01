BEGIN;

-- Resolve issuers by stable identifiers so this migration also repairs databases
-- created from an older seed where company_id=1 was not SoFi.
UPDATE fixed_income.bond AS b
SET company_id = c.company_id
FROM core.company AS c
WHERE b.cusip IN ('83406FAA0', '83406FAC6')
  AND c.cik = '0001818874';

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM core.company AS c
        JOIN core.security AS s ON s.company_id = c.company_id
        WHERE c.cik = '0001818874'
          AND s.ticker = 'SOFI'
    ) THEN
        RAISE EXCEPTION 'SOFI company mapping is missing or inconsistent';
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

INSERT INTO fixed_income.bond_outstanding_balance (
    bond_id,
    as_of_date,
    outstanding_principal,
    source,
    source_filing_date,
    source_url
)
SELECT
    b.bond_id,
    DATE '2026-06-30',
    v.outstanding_principal,
    'SEC 10-Q',
    DATE '2026-08-06',
    'https://www.sec.gov/Archives/edgar/data/1818874/000181887426000054/sofi-20260630.htm'
FROM (
    VALUES
        ('83406FAA0'::TEXT, 428000000.00::NUMERIC),
        ('83406FAC6'::TEXT, 862500000.00::NUMERIC)
) AS v(cusip, outstanding_principal)
JOIN fixed_income.bond AS b ON b.cusip = v.cusip
ON CONFLICT (bond_id, as_of_date, source) DO UPDATE SET
    outstanding_principal = EXCLUDED.outstanding_principal,
    source_filing_date = EXCLUDED.source_filing_date,
    source_url = EXCLUDED.source_url;

-- Keep fixed_income.bond as the security master; balances belong in the
-- append-only snapshot table above.
ALTER TABLE fixed_income.bond
    DROP COLUMN IF EXISTS principal_outstanding,
    DROP COLUMN IF EXISTS source_url,
    DROP COLUMN IF EXISTS as_of_date;

DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'fixed_income' AND table_name = 'trade'
          AND column_name = 'execution_ts'
    ) AND NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'fixed_income' AND table_name = 'trade'
          AND column_name = 'trade_time'
    ) THEN
        ALTER TABLE fixed_income.trade RENAME COLUMN execution_ts TO trade_time;
    END IF;

    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'fixed_income' AND table_name = 'trade'
          AND column_name = 'price'
    ) AND NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'fixed_income' AND table_name = 'trade'
          AND column_name = 'price_pct_of_par'
    ) THEN
        ALTER TABLE fixed_income.trade RENAME COLUMN price TO price_pct_of_par;
    END IF;

    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'fixed_income' AND table_name = 'trade'
          AND column_name = 'quantity'
    ) AND NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'fixed_income' AND table_name = 'trade'
          AND column_name = 'par_quantity'
    ) THEN
        ALTER TABLE fixed_income.trade RENAME COLUMN quantity TO par_quantity;
    END IF;

    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'fixed_income' AND table_name = 'trade'
          AND column_name = 'yield'
    ) AND NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'fixed_income' AND table_name = 'trade'
          AND column_name = 'yield_to_worst'
    ) THEN
        ALTER TABLE fixed_income.trade RENAME COLUMN yield TO yield_to_worst;
    END IF;

    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'fixed_income' AND table_name = 'trade'
          AND column_name = 'provider'
    ) AND NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'fixed_income' AND table_name = 'trade'
          AND column_name = 'source'
    ) THEN
        ALTER TABLE fixed_income.trade RENAME COLUMN provider TO source;
    END IF;
END $$;

ALTER TABLE fixed_income.trade
    ADD COLUMN IF NOT EXISTS cusip TEXT,
    ADD COLUMN IF NOT EXISTS quantity_display TEXT,
    ADD COLUMN IF NOT EXISTS side TEXT,
    ADD COLUMN IF NOT EXISTS raw_record JSONB;

UPDATE fixed_income.trade AS t
SET cusip = b.cusip
FROM fixed_income.bond AS b
WHERE t.bond_id = b.bond_id
  AND t.cusip IS NULL;

ALTER TABLE fixed_income.trade
    ALTER COLUMN cusip SET NOT NULL;

CREATE INDEX IF NOT EXISTS fixed_income_trade_bond_time_idx
    ON fixed_income.trade (bond_id, trade_time DESC);

CREATE INDEX IF NOT EXISTS fixed_income_trade_cusip_time_idx
    ON fixed_income.trade (cusip, trade_time DESC);

COMMENT ON COLUMN fixed_income.trade.quantity_display IS
    'Provider display value such as 1MM+ when exact par quantity is capped.';

COMMENT ON COLUMN fixed_income.trade.raw_record IS
    'Unmodified provider record for inspection and reprocessing; raw payloads should also be archived to S3.';

COMMIT;
