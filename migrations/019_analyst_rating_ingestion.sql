BEGIN;

ALTER TABLE analyst.rating
    ADD COLUMN IF NOT EXISTS provider_record_key TEXT,
    ADD COLUMN IF NOT EXISTS raw_s3_key TEXT,
    ADD COLUMN IF NOT EXISTS ingested_at TIMESTAMPTZ NOT NULL DEFAULT now();

CREATE UNIQUE INDEX IF NOT EXISTS analyst_rating_provider_record_key_idx
    ON analyst.rating (provider, provider_record_key)
    WHERE provider_record_key IS NOT NULL;

CREATE INDEX IF NOT EXISTS analyst_rating_company_published_idx
    ON analyst.rating (company_id, published_at DESC);

COMMIT;
