BEGIN;
CREATE SCHEMA IF NOT EXISTS ownership;
CREATE SCHEMA IF NOT EXISTS fundamentals;

CREATE TABLE IF NOT EXISTS fundamentals.sec_filing (
    filing_id BIGSERIAL PRIMARY KEY,
    company_id BIGINT REFERENCES core.company(company_id),
    accession_number TEXT NOT NULL UNIQUE,
    form_type TEXT,
    filing_date DATE,
    report_date DATE,
    accepted_at TIMESTAMPTZ,
    document_url TEXT,
    raw_s3_key TEXT
);

CREATE TABLE IF NOT EXISTS fundamentals.company_fact (
    company_fact_id BIGSERIAL PRIMARY KEY,
    company_id BIGINT REFERENCES core.company(company_id),
    taxonomy TEXT NOT NULL,
    concept TEXT NOT NULL,
    unit TEXT,
    fiscal_year INTEGER,
    fiscal_period TEXT,
    period_start DATE,
    period_end DATE,
    value NUMERIC,
    accession_number TEXT,
    filed_at DATE
);

CREATE TABLE IF NOT EXISTS ownership.insider_transaction (
    transaction_id BIGSERIAL PRIMARY KEY,
    company_id BIGINT REFERENCES core.company(company_id),
    insider_cik TEXT,
    insider_name TEXT,
    insider_title TEXT,
    transaction_date DATE,
    filing_date DATE,
    transaction_code TEXT,
    security_type TEXT,
    shares NUMERIC,
    price NUMERIC,
    transaction_value NUMERIC,
    shares_after NUMERIC,
    ownership_type TEXT,
    accession_number TEXT
);

CREATE TABLE IF NOT EXISTS ownership.congress_trade (
    transaction_id BIGSERIAL PRIMARY KEY,
    company_id BIGINT REFERENCES core.company(company_id),
    politician_name TEXT,
    chamber TEXT,
    transaction_date DATE,
    disclosure_date DATE,
    transaction_type TEXT,
    amount_min NUMERIC,
    amount_max NUMERIC,
    source TEXT,
    source_url TEXT
);
COMMIT;
