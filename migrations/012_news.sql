BEGIN;

ALTER TABLE news.article
    ADD COLUMN IF NOT EXISTS fetched_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    ADD COLUMN IF NOT EXISTS content_hash TEXT,
    ADD COLUMN IF NOT EXISTS raw_payload_s3_key TEXT;

ALTER TABLE news.article_company
    ADD COLUMN IF NOT EXISTS match_method TEXT;

CREATE INDEX IF NOT EXISTS article_published_at_idx
    ON news.article (published_at DESC);

CREATE INDEX IF NOT EXISTS article_content_hash_idx
    ON news.article (content_hash);

COMMIT;
