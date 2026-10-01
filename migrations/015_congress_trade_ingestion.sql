BEGIN;

CREATE TABLE IF NOT EXISTS ownership.congress_filing (
    provider TEXT NOT NULL,
    filing_id TEXT NOT NULL,
    chamber TEXT NOT NULL,
    person_name TEXT,
    filing_date DATE,
    source_url TEXT NOT NULL,
    raw_document_hash TEXT,
    raw_s3_key TEXT,
    checked_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (provider, filing_id)
);

ALTER TABLE ownership.congress_trade
    ADD COLUMN IF NOT EXISTS provider TEXT,
    ADD COLUMN IF NOT EXISTS provider_transaction_id TEXT,
    ADD COLUMN IF NOT EXISTS asset_name TEXT,
    ADD COLUMN IF NOT EXISTS owner TEXT;

CREATE UNIQUE INDEX IF NOT EXISTS congress_trade_provider_id_idx
    ON ownership.congress_trade(provider_transaction_id)
    WHERE provider_transaction_id IS NOT NULL;

COMMIT;
