BEGIN;

ALTER TABLE news.article
    ADD COLUMN IF NOT EXISTS category TEXT,
    ADD COLUMN IF NOT EXISTS sentiment_label TEXT,
    ADD COLUMN IF NOT EXISTS sentiment_score NUMERIC,
    ADD COLUMN IF NOT EXISTS classification_method TEXT;

CREATE INDEX IF NOT EXISTS article_category_published_idx
    ON news.article (category, published_at DESC);

CREATE INDEX IF NOT EXISTS article_sentiment_published_idx
    ON news.article (sentiment_label, published_at DESC);

COMMIT;
