BEGIN;
CREATE SCHEMA IF NOT EXISTS pipeline;

CREATE TABLE IF NOT EXISTS pipeline.ingestion_run (
    ingestion_run_id BIGSERIAL PRIMARY KEY,
    pipeline TEXT NOT NULL,
    provider TEXT NOT NULL,
    started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    completed_at TIMESTAMPTZ,
    status TEXT NOT NULL,
    records_requested INTEGER,
    records_received INTEGER,
    records_inserted INTEGER,
    records_updated INTEGER,
    error_message TEXT
);

CREATE TABLE IF NOT EXISTS pipeline.watermark (
    pipeline TEXT PRIMARY KEY,
    last_success_ts TIMESTAMPTZ,
    last_provider_id TEXT,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
COMMIT;
