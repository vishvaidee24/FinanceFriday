BEGIN;
CREATE SCHEMA IF NOT EXISTS social;
CREATE SCHEMA IF NOT EXISTS prediction;

CREATE TABLE IF NOT EXISTS social.post (
    post_id BIGSERIAL PRIMARY KEY,
    platform TEXT NOT NULL,
    platform_post_id TEXT NOT NULL,
    author_id TEXT,
    published_at TIMESTAMPTZ,
    discovered_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    body TEXT,
    url TEXT,
    like_count INTEGER,
    reply_count INTEGER,
    repost_count INTEGER,
    view_count INTEGER,
    raw_s3_key TEXT,
    UNIQUE(platform, platform_post_id)
);

CREATE TABLE IF NOT EXISTS social.post_company (
    post_id BIGINT REFERENCES social.post(post_id) ON DELETE CASCADE,
    company_id BIGINT REFERENCES core.company(company_id),
    relevance_score NUMERIC,
    PRIMARY KEY(post_id, company_id)
);

CREATE TABLE IF NOT EXISTS social.sentiment (
    post_id BIGINT REFERENCES social.post(post_id) ON DELETE CASCADE,
    company_id BIGINT REFERENCES core.company(company_id),
    sentiment_score NUMERIC,
    bullish_score NUMERIC,
    bearish_score NUMERIC,
    confidence NUMERIC,
    model_name TEXT NOT NULL,
    model_version TEXT NOT NULL,
    analyzed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY(post_id, company_id, model_name, model_version)
);

CREATE TABLE IF NOT EXISTS prediction.market (
    market_id BIGSERIAL PRIMARY KEY,
    platform TEXT NOT NULL,
    platform_market_id TEXT NOT NULL,
    title TEXT,
    description TEXT,
    opens_at TIMESTAMPTZ,
    closes_at TIMESTAMPTZ,
    resolves_at TIMESTAMPTZ,
    status TEXT,
    UNIQUE(platform, platform_market_id)
);

CREATE TABLE IF NOT EXISTS prediction.market_snapshot (
    market_id BIGINT REFERENCES prediction.market(market_id) ON DELETE CASCADE,
    ts TIMESTAMPTZ NOT NULL,
    yes_price NUMERIC,
    no_price NUMERIC,
    volume NUMERIC,
    open_interest NUMERIC,
    PRIMARY KEY(market_id, ts)
);

CREATE TABLE IF NOT EXISTS prediction.market_company (
    market_id BIGINT REFERENCES prediction.market(market_id) ON DELETE CASCADE,
    company_id BIGINT REFERENCES core.company(company_id),
    relevance_score NUMERIC,
    relationship_type TEXT,
    PRIMARY KEY(market_id, company_id)
);
COMMIT;
