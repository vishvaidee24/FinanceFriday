import hashlib
from datetime import UTC, date, datetime

from psycopg.rows import dict_row

from app.common.news_classification import classify_news
from app.common.s3 import RawArchive
from app.db.connection import get_connection
from app.db.pipeline import finish_run, start_run
from app.models.news import NewsArticle
from app.providers.news import IntelNewsProvider, SofiNewsProvider
from app.providers.sec import SecProvider


def _content_hash(article: NewsArticle) -> str:
    content = "\n".join((article.title, article.summary or "", article.url))
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


async def ingest_company_news(
    *, ticker: str, cik: str, provider: SofiNewsProvider, start_date: date | None = None
) -> int:
    ticker = ticker.upper()
    run_id = start_run(f"{ticker.lower()}_news", "multi_source")
    fetched_at = datetime.now(UTC)
    archive = RawArchive()

    try:
        google_payload, google_articles = await provider.fetch_google_news()
        market_payload, market_articles = await provider.fetch_market_news()
        geopolitical_payload, geopolitical_articles = (
            await provider.fetch_geopolitical_news()
        )
        if start_date and isinstance(provider, IntelNewsProvider):
            ir_payload, ir_articles = await provider.fetch_investor_relations_history(start_date.year)
        else:
            ir_payload, ir_articles = await provider.fetch_investor_relations()
        sec_provider = SecProvider()
        sec_payload = await sec_provider.get_submissions(cik)
        sec_payloads = [sec_payload]
        if start_date:
            for item in sec_payload.get("filings", {}).get("files", []):
                filing_to = date.fromisoformat(item["filingTo"])
                if filing_to >= start_date:
                    sec_payloads.append(await sec_provider.get_submission_file(item["name"]))
        sec_articles = [
            article
            for payload in sec_payloads
            for article in provider.sec_articles(
                payload, cik=cik, published_since=start_date
            )
        ]

        source_batches = [
            ("google_news", google_payload, google_articles),
            ("google_market_news", market_payload, market_articles),
            (
                "google_geopolitical_news",
                geopolitical_payload,
                geopolitical_articles,
            ),
            (f"{ticker.lower()}_ir", ir_payload, ir_articles),
            ("sec_edgar", sec_payloads, sec_articles),
        ]
        articles: list[tuple[NewsArticle, str]] = []
        for source, payload, batch in source_batches:
            raw_key = archive.put_json(
                provider=source,
                dataset=f"{ticker.lower()}_news",
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
                    WHERE upper(s.ticker) = %s
                    ORDER BY s.valid_to NULLS FIRST, s.security_id DESC
                    LIMIT 1
                    """,
                    (ticker,),
                )
                company = cur.fetchone()
                if company is None:
                    raise RuntimeError(f"{ticker} company row is missing")

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


async def ingest_sofi_news() -> int:
    return await ingest_company_news(
        ticker="SOFI", cik="1818874", provider=SofiNewsProvider()
    )


async def ingest_intel_news(start_date: date | None = None) -> int:
    return await ingest_company_news(
        ticker="INTC", cik="50863", provider=IntelNewsProvider(), start_date=start_date
    )
