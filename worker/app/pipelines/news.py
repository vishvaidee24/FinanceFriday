import hashlib
from datetime import datetime, timezone

from psycopg.rows import dict_row

from app.common.s3 import RawArchive
from app.common.news_classification import classify_news
from app.db.connection import get_connection
from app.db.pipeline import finish_run, start_run
from app.models.news import NewsArticle
from app.providers.news import SofiNewsProvider
from app.providers.sec import SecProvider


def _content_hash(article: NewsArticle) -> str:
    content = "\n".join((article.title, article.summary or "", article.url))
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


async def ingest_sofi_news() -> int:
    run_id = start_run("sofi_news", "multi_source")
    fetched_at = datetime.now(timezone.utc)
    provider = SofiNewsProvider()
    archive = RawArchive()

    try:
        google_payload, google_articles = await provider.fetch_google_news()
        market_payload, market_articles = await provider.fetch_market_news()
        geopolitical_payload, geopolitical_articles = (
            await provider.fetch_geopolitical_news()
        )
        ir_payload, ir_articles = await provider.fetch_investor_relations()
        sec_payload = await SecProvider().get_submissions("1818874")
        sec_articles = provider.sec_articles(sec_payload)

        source_batches = [
            ("google_news", google_payload, google_articles),
            ("google_market_news", market_payload, market_articles),
            (
                "google_geopolitical_news",
                geopolitical_payload,
                geopolitical_articles,
            ),
            ("sofi_ir", ir_payload, ir_articles),
            ("sec_edgar", sec_payload, sec_articles),
        ]
        articles: list[tuple[NewsArticle, str]] = []
        for source, payload, batch in source_batches:
            raw_key = archive.put_json(
                provider=source,
                dataset="sofi_news",
                object_name=f"run-{run_id}",
                payload=payload,
                observed_at=fetched_at,
            )
            articles.extend((article, raw_key) for article in batch)

        with get_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    """
                    SELECT c.company_id
                    FROM core.company AS c
                    JOIN core.security AS s ON s.company_id = c.company_id
                    WHERE s.ticker = 'SOFI'
                    ORDER BY s.valid_to NULLS FIRST, s.security_id DESC
                    LIMIT 1
                    """
                )
                company = cur.fetchone()
                if company is None:
                    raise RuntimeError("SOFI company row is missing")

                inserted = 0
                for article, raw_key in articles:
                    classification = classify_news(article.title, article.summary)
                    cur.execute(
                        """
                        INSERT INTO news.article (
                            provider, provider_article_id, source_name, title,
                            summary, url, published_at, discovered_at, fetched_at,
                            content_hash, raw_s3_key, raw_payload_s3_key,
                            category, overall_sentiment_label,
                            overall_sentiment_score, overall_sentiment_method
                        ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                        ON CONFLICT (provider, provider_article_id) DO UPDATE SET
                            source_name=EXCLUDED.source_name,
                            title=EXCLUDED.title,
                            summary=EXCLUDED.summary,
                            url=EXCLUDED.url,
                            published_at=EXCLUDED.published_at,
                            fetched_at=EXCLUDED.fetched_at,
                            content_hash=EXCLUDED.content_hash,
                            raw_s3_key=EXCLUDED.raw_s3_key,
                            raw_payload_s3_key=EXCLUDED.raw_payload_s3_key
                            ,category=EXCLUDED.category
                            ,overall_sentiment_label=EXCLUDED.overall_sentiment_label
                            ,overall_sentiment_score=EXCLUDED.overall_sentiment_score
                            ,overall_sentiment_method=EXCLUDED.overall_sentiment_method
                        RETURNING article_id, (xmax = 0) AS was_inserted
                        """,
                        (
                            article.provider,
                            article.provider_article_id,
                            article.source_name,
                            article.title,
                            article.summary,
                            article.url,
                            article.published_at,
                            fetched_at,
                            fetched_at,
                            _content_hash(article),
                            raw_key,
                            raw_key,
                            classification.category,
                            classification.sentiment_label,
                            classification.sentiment_score,
                            classification.method,
                        ),
                    )
                    row = cur.fetchone()
                    inserted += int(row["was_inserted"])
                    cur.execute(
                        """
                        INSERT INTO news.article_company (
                            article_id, company_id, match_method,
                            relevance_score, mention_count, primary_company
                        ) VALUES (%s,%s,%s,%s,%s,TRUE)
                        ON CONFLICT (article_id, company_id) DO UPDATE SET
                            match_method=EXCLUDED.match_method,
                            relevance_score=EXCLUDED.relevance_score,
                            mention_count=EXCLUDED.mention_count,
                            primary_company=TRUE
                        """,
                        (
                            row["article_id"],
                            company["company_id"],
                            article.match_method,
                            article.relevance_score,
                            1,
                        ),
                    )

                cur.execute(
                    """
                    SELECT DISTINCT a.article_id, a.title, a.summary
                    FROM news.article AS a
                    JOIN news.article_company AS ac ON ac.article_id = a.article_id
                    WHERE ac.company_id = %s
                      AND a.overall_sentiment_method IS DISTINCT FROM 'keyword_rules_v1'
                    """,
                    (company["company_id"],),
                )
                for existing in cur.fetchall():
                    classification = classify_news(
                        existing["title"], existing["summary"]
                    )
                    cur.execute(
                        """
                        UPDATE news.article
                        SET category=%s, overall_sentiment_label=%s,
                            overall_sentiment_score=%s,
                            overall_sentiment_method=%s
                        WHERE article_id=%s
                        """,
                        (
                            classification.category,
                            classification.sentiment_label,
                            classification.sentiment_score,
                            classification.method,
                            existing["article_id"],
                        ),
                    )
            conn.commit()

        finish_run(
            run_id,
            status="SUCCESS",
            records_received=len(articles),
            records_inserted=inserted,
        )
        return inserted
    except Exception as exc:
        finish_run(run_id, status="FAILED", error_message=str(exc))
        raise
