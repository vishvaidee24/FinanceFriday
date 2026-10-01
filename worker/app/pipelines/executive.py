import hashlib
from datetime import UTC, datetime

from app.common.s3 import RawArchive
from app.db.connection import get_connection
from app.db.pipeline import finish_run, start_run
from app.providers.executive import (
    DISCLOSED_CAPITOL_URL,
    DisclosedCapitolProvider,
    OgeDisclosureProvider,
)

PARSER_VERSION = "oge_278t_v2"
ARCHIVE_PARSER_VERSION = "disclosed_capitol_v1"


async def ingest_executive_trades() -> int:
    now = datetime.now(UTC)
    run_id = start_run("executive_branch_trades", "oge")
    archive = RawArchive()
    provider = OgeDisclosureProvider()
    archive_provider = DisclosedCapitolProvider()
    received = inserted = 0
    try:
        filings = await provider.filings()
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """SELECT DISTINCT ON (upper(ticker)) upper(ticker),security_id,company_id
                       FROM core.security
                       WHERE ticker IS NOT NULL
                       ORDER BY upper(ticker),valid_to NULLS FIRST,security_id DESC"""
                )
                security_by_ticker = {
                    row[0]: (row[1], row[2]) for row in cur.fetchall()
                }
                cur.execute(
                    "SELECT provider,filing_id,parser_version FROM ownership.executive_filing"
                )
                checked = {(row[0], row[1]): row[2] for row in cur.fetchall()}

            for filing in filings:
                source_url = filing.get("url")
                if filing["access_status"] == "form_201_required":
                    with conn.cursor() as cur:
                        _upsert_filing(cur, filing, None, None)
                    conn.commit()
                    continue
                if checked.get(("oge", filing["filing_id"])) == PARSER_VERSION:
                    continue
                if not source_url:
                    continue
                content = await provider.document(source_url)
                digest = hashlib.sha256(content).hexdigest()
                trades = provider.parse_document(content, filing)
                raw_key = archive.put_json(
                    provider="oge",
                    dataset="executive_trades",
                    object_name=filing["filing_id"],
                    payload={
                        "source_url": source_url,
                        "sha256": digest,
                        "filing": filing,
                        "transactions": trades,
                    },
                    observed_at=now,
                )
                received += len(trades)
                with conn.cursor() as cur:
                    _upsert_filing(cur, filing, digest, raw_key)
                    for trade in trades:
                        security = security_by_ticker.get(trade["reported_ticker"])
                        cur.execute(
                            """INSERT INTO ownership.executive_trade (
                                   company_id,security_id,person_name,person_title,agency,
                                   transaction_date,filing_date,transaction_type,
                                   amount_min,amount_max,amount_range,asset_name,reported_ticker,
                                   owner,source,provider,source_url,filing_id,
                                   raw_document_hash,raw_s3_key,signal,provider_transaction_id
                               ) VALUES (
                                   %s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s
                               ) ON CONFLICT (provider_transaction_id) DO NOTHING""",
                            (
                                security[1] if security else None,
                                security[0] if security else None,
                                trade["person_name"], trade["person_title"], trade["agency"],
                                trade["transaction_date"], trade["filing_date"],
                                trade["transaction_type"], trade["amount_min"], trade["amount_max"],
                                trade["amount_range"], trade["asset_name"], trade["reported_ticker"],
                                trade["owner"], "OGE Form 278-T", "oge", source_url,
                                filing["filing_id"], digest, raw_key, trade["signal"],
                                trade["provider_transaction_id"],
                            ),
                        )
                        inserted += cur.rowcount
                conn.commit()

        archive_inserted, archive_received = await _ingest_archive(
            archive_provider, archive, now
        )
        inserted += archive_inserted
        received += archive_received
        finish_run(
            run_id,
            status="SUCCESS",
            records_received=received,
            records_inserted=inserted,
        )
        return inserted
    except Exception as exc:
        finish_run(run_id, status="FAILED", error_message=str(exc))
        raise
    finally:
        await provider.close()
        await archive_provider.close()


async def _ingest_archive(
    provider: DisclosedCapitolProvider,
    archive: RawArchive,
    observed_at: datetime,
) -> tuple[int, int]:
    content = await provider.dataset()
    digest = hashlib.sha256(content).hexdigest()
    rows = provider.parse_dataset(content)
    raw_key = archive.put_json(
        provider="disclosed_capitol",
        dataset="executive_trades",
        object_name=f"snapshot-{digest[:16]}",
        payload={
            "source_url": DISCLOSED_CAPITOL_URL,
            "sha256": digest,
            "license": "CC BY 4.0",
            "transactions": rows,
        },
        observed_at=observed_at,
    )
    inserted = 0
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT DISTINCT ON (upper(ticker)) upper(ticker),security_id,company_id
                   FROM core.security WHERE ticker IS NOT NULL
                   ORDER BY upper(ticker),valid_to NULLS FIRST,security_id DESC"""
            )
            securities = {row[0]: (row[1], row[2]) for row in cur.fetchall()}
            archive_filing_ids = {row["filing_id"].lower() for row in rows}
            cur.execute(
                """DELETE FROM ownership.executive_trade
                   WHERE provider='oge' AND lower(filing_id)=ANY(%s)""",
                (list(archive_filing_ids),),
            )
            filing_rows: dict[str, dict] = {}
            for row in rows:
                filing_rows.setdefault(row["filing_id"], row)
            for filing_id, row in filing_rows.items():
                cur.execute(
                    """INSERT INTO ownership.executive_filing (
                           provider,filing_id,person_name,person_title,agency,filing_date,
                           document_type,source_url,access_status,raw_document_hash,
                           raw_s3_key,parser_version
                       ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,'public_download',%s,%s,%s)
                       ON CONFLICT (provider,filing_id) DO UPDATE SET
                           person_name=EXCLUDED.person_name,person_title=EXCLUDED.person_title,
                           agency=EXCLUDED.agency,filing_date=EXCLUDED.filing_date,
                           document_type=EXCLUDED.document_type,source_url=EXCLUDED.source_url,
                           raw_document_hash=EXCLUDED.raw_document_hash,
                           raw_s3_key=EXCLUDED.raw_s3_key,
                           parser_version=EXCLUDED.parser_version,checked_at=now()""",
                    (
                        "disclosed_capitol", filing_id, row["person_name"],
                        row["person_title"], row["agency"], row["filing_date"],
                        f"OGE Form {row['filing_type']}", row["source_url"], digest,
                        raw_key, ARCHIVE_PARSER_VERSION,
                    ),
                )
            for row in rows:
                security = securities.get(row["reported_ticker"])
                cur.execute(
                    """INSERT INTO ownership.executive_trade (
                           company_id,security_id,person_name,person_title,agency,
                           transaction_date,filing_date,transaction_type,amount_min,
                           amount_max,amount_range,asset_name,reported_ticker,owner,
                           source,provider,source_url,filing_id,raw_document_hash,
                           raw_s3_key,signal,provider_transaction_id
                       ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                       ON CONFLICT (provider_transaction_id) DO NOTHING""",
                    (
                        security[1] if security else None,
                        security[0] if security else None,
                        row["person_name"], row["person_title"], row["agency"],
                        row["transaction_date"], row["filing_date"],
                        row["transaction_type"], row["amount_min"], row["amount_max"],
                        row["amount_range"], row["asset_name"], row["reported_ticker"],
                        row["owner"], "Disclosed Capitol archive of official OGE filings",
                        "disclosed_capitol", row["source_url"], row["filing_id"],
                        digest, raw_key, row["signal"], row["provider_transaction_id"],
                    ),
                )
                inserted += cur.rowcount
        conn.commit()
    return inserted, len(rows)


def _upsert_filing(cur, filing: dict, digest: str | None, raw_key: str | None) -> None:
    cur.execute(
        """INSERT INTO ownership.executive_filing (
               provider,filing_id,person_name,person_title,agency,filing_date,
               source_url,access_status,raw_document_hash,raw_s3_key,parser_version
           ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
           ON CONFLICT (provider,filing_id) DO UPDATE SET
               person_name=EXCLUDED.person_name,
               person_title=EXCLUDED.person_title,
               agency=EXCLUDED.agency,
               filing_date=EXCLUDED.filing_date,
               source_url=EXCLUDED.source_url,
               access_status=EXCLUDED.access_status,
               raw_document_hash=COALESCE(EXCLUDED.raw_document_hash,ownership.executive_filing.raw_document_hash),
               raw_s3_key=COALESCE(EXCLUDED.raw_s3_key,ownership.executive_filing.raw_s3_key),
               parser_version=COALESCE(EXCLUDED.parser_version,ownership.executive_filing.parser_version),
               checked_at=now()""",
        (
            "oge", filing["filing_id"], filing["person_name"],
            filing.get("person_title"), filing.get("agency"), filing.get("filing_date"),
            filing.get("url"), filing["access_status"], digest, raw_key,
            PARSER_VERSION if digest else None,
        ),
    )
