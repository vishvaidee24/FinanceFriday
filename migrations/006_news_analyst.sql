BEGIN;
CREATE SCHEMA IF NOT EXISTS news;
CREATE SCHEMA IF NOT EXISTS analyst;

CREATE TABLE IF NOT EXISTS news.article (
    article_id BIGSERIAL PRIMARY KEY,
    provider TEXT NOT NULL,
    provider_article_id TEXT,
    published_at TIMESTAMPTZ,
    discovered_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    title TEXT,
    summary TEXT,
    body TEXT,
    url TEXT,
    author TEXT,
    source_name TEXT,
    raw_s3_key TEXT,
    UNIQUE(provider, provider_article_id)
);

CREATE TABLE IF NOT EXISTS news.article_company (
    article_id BIGINT REFERENCES news.article(article_id) ON DELETE CASCADE,
    company_id BIGINT REFERENCES core.company(company_id),
    relevance_score NUMERIC,
    mention_count INTEGER,
    primary_company BOOLEAN,
    PRIMARY KEY(article_id, company_id)
);

CREATE TABLE IF NOT EXISTS news.sentiment (
    article_id BIGINT REFERENCES news.article(article_id) ON DELETE CASCADE,
    company_id BIGINT REFERENCES core.company(company_id),
    sentiment_score NUMERIC,
    bullish_score NUMERIC,
    bearish_score NUMERIC,
    uncertainty_score NUMERIC,
    event_type TEXT,
    model_name TEXT NOT NULL,
    model_version TEXT NOT NULL,
    analyzed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY(article_id, company_id, model_name, model_version)
);

CREATE TABLE IF NOT EXISTS analyst.rating (
    rating_id BIGSERIAL PRIMARY KEY,
    company_id BIGINT REFERENCES core.company(company_id),
    firm TEXT,
    analyst_name TEXT,
    published_at TIMESTAMPTZ,
    action TEXT,
    prior_rating TEXT,
    new_rating TEXT,
    prior_price_target NUMERIC,
    new_price_target NUMERIC,
    commentary TEXT,
    provider TEXT,
    source_url TEXT
);
COMMIT;
