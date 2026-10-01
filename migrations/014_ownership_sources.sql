BEGIN;

ALTER TABLE ownership.insider_transaction
    ADD COLUMN IF NOT EXISTS security_id BIGINT REFERENCES core.security(security_id),
    ADD COLUMN IF NOT EXISTS person_name TEXT,
    ADD COLUMN IF NOT EXISTS person_title TEXT,
    ADD COLUMN IF NOT EXISTS transaction_type TEXT,
    ADD COLUMN IF NOT EXISTS source_url TEXT,
    ADD COLUMN IF NOT EXISTS raw_document_hash TEXT,
    ADD COLUMN IF NOT EXISTS raw_s3_key TEXT,
    ADD COLUMN IF NOT EXISTS signal TEXT,
    ADD COLUMN IF NOT EXISTS provider_transaction_id TEXT;

CREATE UNIQUE INDEX IF NOT EXISTS insider_transaction_provider_id_idx
    ON ownership.insider_transaction(provider_transaction_id)
    WHERE provider_transaction_id IS NOT NULL;

ALTER TABLE ownership.congress_trade
    ADD COLUMN IF NOT EXISTS security_id BIGINT REFERENCES core.security(security_id),
    ADD COLUMN IF NOT EXISTS person_name TEXT,
    ADD COLUMN IF NOT EXISTS person_title TEXT,
    ADD COLUMN IF NOT EXISTS filing_date DATE,
    ADD COLUMN IF NOT EXISTS transaction_code TEXT,
    ADD COLUMN IF NOT EXISTS shares NUMERIC,
    ADD COLUMN IF NOT EXISTS price NUMERIC,
    ADD COLUMN IF NOT EXISTS amount_range TEXT,
    ADD COLUMN IF NOT EXISTS accession_number TEXT,
    ADD COLUMN IF NOT EXISTS raw_document_hash TEXT,
    ADD COLUMN IF NOT EXISTS raw_s3_key TEXT,
    ADD COLUMN IF NOT EXISTS signal TEXT;

COMMIT;
