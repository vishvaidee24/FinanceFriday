from datetime import datetime, timezone

from app.common.s3 import RawArchive
from app.db.connection import get_connection
from app.db.pipeline import finish_run, start_run
from app.providers.sec import SecProvider


async def ingest_insider_transactions(*, symbol: str, cik: str) -> int:
    symbol = symbol.upper()
    run_id = start_run(f"{symbol.lower()}_insider_transactions", "sec_edgar")
    provider = SecProvider()
    archive = RawArchive()
    try:
        submissions = await provider.get_submissions(cik)
        filings = provider.ownership_filings(submissions)
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT s.security_id,c.company_id FROM core.security s JOIN core.company c ON c.company_id=s.company_id WHERE s.ticker=%s ORDER BY s.valid_to NULLS FIRST,s.security_id DESC LIMIT 1",
                    (symbol,),
                )
                security = cur.fetchone()
                if security is None:
                    raise RuntimeError(f"{symbol} security is missing")
                cur.execute(
                    "SELECT accession_number FROM fundamentals.sec_filing WHERE accession_number = ANY(%s)",
                    ([filing["accession_number"] for filing in filings],),
                )
                existing = {row[0] for row in cur.fetchall()}

            received = 0
            inserted = 0
            for filing in filings:
                if filing["accession_number"] in existing:
                    continue
                content = await provider.get_document(filing["url"])
                transactions = provider.parse_ownership_document(
                    content,
                    accession_number=filing["accession_number"],
                    filing_date=filing["filing_date"],
                    source_url=filing["url"],
                )
                raw_key = archive.put_json(
                    provider="sec_edgar",
                    dataset=f"{symbol.lower()}_insider_transactions",
                    object_name=filing["accession_number"],
                    payload={"source_url": filing["url"], "xml": content.decode("utf-8", errors="replace")},
                    observed_at=datetime.now(timezone.utc),
                )
                received += len(transactions)
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO fundamentals.sec_filing (
                            company_id,accession_number,form_type,filing_date,
                            document_url,raw_s3_key
                        ) VALUES (%s,%s,%s,%s,%s,%s)
                        ON CONFLICT (accession_number) DO UPDATE SET
                            form_type=EXCLUDED.form_type,
                            filing_date=EXCLUDED.filing_date,
                            document_url=EXCLUDED.document_url,
                            raw_s3_key=EXCLUDED.raw_s3_key
                        """,
                        (
                            security[1],filing["accession_number"],filing["form"],
                            filing["filing_date"],filing["url"],raw_key,
                        ),
                    )
                    for transaction in transactions:
                        cur.execute(
                            """
                            INSERT INTO ownership.insider_transaction (
                                company_id,security_id,insider_cik,insider_name,insider_title,
                                person_name,person_title,transaction_date,filing_date,
                                transaction_code,transaction_type,security_type,shares,price,
                                transaction_value,shares_after,ownership_type,accession_number,
                                source_url,raw_document_hash,raw_s3_key,signal,provider_transaction_id
                            ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                            ON CONFLICT (provider_transaction_id)
                            WHERE provider_transaction_id IS NOT NULL
                            DO NOTHING
                            """,
                            (
                                security[1],security[0],transaction.insider_cik,
                                transaction.person_name,transaction.person_title,
                                transaction.person_name,transaction.person_title,
                                transaction.transaction_date,transaction.filing_date,
                                transaction.transaction_code,transaction.transaction_type,
                                transaction.security_type,transaction.shares,transaction.price,
                                transaction.transaction_value,transaction.shares_after,
                                transaction.ownership_type,transaction.accession_number,
                                transaction.source_url,transaction.raw_document_hash,raw_key,
                                transaction.signal,transaction.provider_transaction_id,
                            ),
                        )
                        inserted += cur.rowcount
                conn.commit()

        finish_run(run_id,status="SUCCESS",records_received=received,records_inserted=inserted)
        return inserted
    except Exception as exc:
        finish_run(run_id,status="FAILED",error_message=str(exc))
        raise


async def ingest_sofi_insider_transactions() -> int:
    return await ingest_insider_transactions(symbol="SOFI", cik="1818874")
