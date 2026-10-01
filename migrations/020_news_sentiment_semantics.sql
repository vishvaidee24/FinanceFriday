BEGIN;

-- Keep this migration independent of the fixed-income and watermark changes in
-- 018 so news deployments can be repaired without altering unrelated schemas.
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'news' AND table_name = 'article'
          AND column_name = 'sentiment_label'
    ) AND NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'news' AND table_name = 'article'
          AND column_name = 'overall_sentiment_label'
    ) THEN
        ALTER TABLE news.article
            RENAME COLUMN sentiment_label TO overall_sentiment_label;
    END IF;

    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'news' AND table_name = 'article'
          AND column_name = 'sentiment_score'
    ) AND NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'news' AND table_name = 'article'
          AND column_name = 'overall_sentiment_score'
    ) THEN
        ALTER TABLE news.article
            RENAME COLUMN sentiment_score TO overall_sentiment_score;
    END IF;

    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'news' AND table_name = 'article'
          AND column_name = 'classification_method'
    ) AND NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'news' AND table_name = 'article'
          AND column_name = 'overall_sentiment_method'
    ) THEN
        ALTER TABLE news.article
            RENAME COLUMN classification_method TO overall_sentiment_method;
    END IF;
END $$;

COMMENT ON COLUMN news.article.overall_sentiment_label IS
    'General sentiment of the full article, not sentiment toward a specific company.';

COMMENT ON COLUMN news.article.overall_sentiment_score IS
    'General article sentiment score; company-targeted scores belong in news.sentiment.';

COMMENT ON TABLE news.sentiment IS
    'Model-versioned sentiment toward a specific company mentioned in an article.';

COMMIT;
