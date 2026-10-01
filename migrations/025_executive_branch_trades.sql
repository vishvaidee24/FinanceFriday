BEGIN;

CREATE TABLE IF NOT EXISTS ownership.executive_filing (
    provider TEXT NOT NULL,
    filing_id TEXT NOT NULL,
    person_name TEXT NOT NULL,
    person_title TEXT,
    agency TEXT,
    filing_date DATE,
    document_type TEXT NOT NULL DEFAULT 'OGE Form 278-T',
    source_url TEXT,
    access_status TEXT NOT NULL DEFAULT 'public_download',
    raw_document_hash TEXT,
    raw_s3_key TEXT,
    parser_version TEXT,
    checked_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (provider, filing_id),
    CHECK (access_status IN ('public_download', 'form_201_required'))
);

CREATE TABLE IF NOT EXISTS ownership.executive_trade (
    transaction_id BIGSERIAL PRIMARY KEY,
    company_id BIGINT REFERENCES core.company(company_id),
    security_id BIGINT REFERENCES core.security(security_id),
    person_name TEXT NOT NULL,
    person_title TEXT,
    agency TEXT,
    transaction_date DATE NOT NULL,
    filing_date DATE,
    transaction_type TEXT NOT NULL,
    amount_min NUMERIC,
    amount_max NUMERIC,
    amount_range TEXT,
    asset_name TEXT NOT NULL,
    reported_ticker TEXT,
    owner TEXT,
    source TEXT NOT NULL,
    provider TEXT NOT NULL,
    source_url TEXT NOT NULL,
    filing_id TEXT NOT NULL,
    raw_document_hash TEXT,
    raw_s3_key TEXT,
    signal TEXT,
    provider_transaction_id TEXT NOT NULL UNIQUE,
    FOREIGN KEY (provider, filing_id)
        REFERENCES ownership.executive_filing(provider, filing_id)
        DEFERRABLE INITIALLY DEFERRED
);

CREATE INDEX IF NOT EXISTS executive_trade_person_date_idx
    ON ownership.executive_trade (person_name, transaction_date DESC);

CREATE INDEX IF NOT EXISTS executive_trade_ticker_date_idx
    ON ownership.executive_trade (reported_ticker, transaction_date DESC)
    WHERE reported_ticker IS NOT NULL;

CREATE INDEX IF NOT EXISTS executive_filing_access_idx
    ON ownership.executive_filing (access_status, filing_date DESC);

COMMENT ON COLUMN ownership.executive_trade.transaction_date IS
    'Date the disclosed transaction occurred.';
COMMENT ON COLUMN ownership.executive_trade.filing_date IS
    'Date the disclosure became public or was added to the provider catalog.';
COMMENT ON COLUMN ownership.executive_trade.reported_ticker IS
    'Ticker printed on the disclosure; retained even when core.security has no match.';
COMMENT ON COLUMN ownership.executive_filing.access_status IS
    'Whether the document is directly public or requires an individual OGE Form 201 request.';

COMMIT;
