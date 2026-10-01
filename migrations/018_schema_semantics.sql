BEGIN;

-- Static issuance terms belong on the security master.  Filing-to-filing
-- outstanding balances remain in fixed_income.bond_outstanding_balance.
ALTER TABLE fixed_income.bond
    ADD COLUMN IF NOT EXISTS original_issue_principal NUMERIC(20, 2)
        CHECK (original_issue_principal >= 0);

UPDATE fixed_income.bond
SET original_issue_principal = CASE cusip
    WHEN '83406FAA0' THEN 1200000000.00
    WHEN '83406FAC6' THEN 862500000.00
END
WHERE cusip IN ('83406FAA0', '83406FAC6')
  AND original_issue_principal IS NULL;

-- fixed_income.bond.convertible is the canonical flag.  Preserve any value
-- supplied through the temporary duplicate before removing it.
UPDATE fixed_income.bond
SET convertible = COALESCE(convertible, is_convertible)
WHERE is_convertible IS NOT NULL;

ALTER TABLE fixed_income.bond
    DROP COLUMN IF EXISTS is_convertible;

COMMENT ON COLUMN fixed_income.bond.original_issue_principal IS
    'Aggregate principal issued at origination, in currency units; static security term.';

COMMENT ON COLUMN fixed_income.bond.convertible IS
    'Whether the bond is convertible; canonical convertible flag.';

COMMENT ON COLUMN fixed_income.trade.price_pct_of_par IS
    'Executed price expressed as percent of par (for example, 99.68).';

COMMENT ON COLUMN fixed_income.trade.par_quantity IS
    'Executed par amount when FINRA publishes an exact numeric quantity.';

COMMENT ON COLUMN fixed_income.trade.yield_to_worst IS
    'Provider-reported yield to worst, in percentage points.';

-- Existing rows represent the former pipeline-wide cursor.  Retain them as
-- default/global cursors, then allow provider- and entity-specific progress.
ALTER TABLE pipeline.watermark
    ADD COLUMN IF NOT EXISTS provider TEXT NOT NULL DEFAULT 'default',
    ADD COLUMN IF NOT EXISTS entity_key TEXT NOT NULL DEFAULT 'global';

ALTER TABLE pipeline.watermark
    DROP CONSTRAINT IF EXISTS watermark_pkey;

ALTER TABLE pipeline.watermark
    ADD CONSTRAINT watermark_pkey PRIMARY KEY (pipeline, provider, entity_key);

COMMENT ON COLUMN pipeline.watermark.entity_key IS
    'Provider-specific entity cursor, such as a ticker, CIK, CUSIP, or global.';

-- Article-level fields describe the overall tone of the article.  The
-- news.sentiment table remains company-targeted and model-versioned.
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
