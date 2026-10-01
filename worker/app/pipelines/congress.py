import hashlib
from datetime import datetime, timezone

import structlog

from app.common.s3 import RawArchive
from app.db.connection import get_connection
from app.db.pipeline import finish_run, start_run
from app.providers.congress import HouseDisclosureProvider, SenateDisclosureProvider


log = structlog.get_logger()


async def ingest_sofi_congress_trades(*, years: list[int] | None = None) -> int:
    now = datetime.now(timezone.utc)
    years = years or [now.year]
    run_id = start_run("sofi_congress_trades", "house_clerk+senate_efd")
    archive = RawArchive()
    house = HouseDisclosureProvider()
    senate = SenateDisclosureProvider()
    received = inserted = 0
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT s.security_id,c.company_id FROM core.security s JOIN core.company c ON c.company_id=s.company_id WHERE s.ticker='SOFI' ORDER BY s.valid_to NULLS FIRST,s.security_id DESC LIMIT 1")
                security = cur.fetchone()
                if security is None:
                    raise RuntimeError("SOFI security is missing")
                cur.execute("SELECT provider,filing_id FROM ownership.congress_filing")
                checked = {(row[0], row[1]) for row in cur.fetchall()}

            for year in years:
                for filing in await house.filings(year):
                    if ("house_clerk", filing["filing_id"]) in checked:
                        continue
                    content = await house.document(filing["url"])
                    digest = hashlib.sha256(content).hexdigest()
                    trades = house.parse_document(content, filing)
                    raw_key = None
                    # Personal-use compliance: archive only documents relevant to SOFI.
                    if trades:
                        raw_key = archive.put_json(
                            provider="house_clerk", dataset="sofi_congress_trades",
                            object_name=filing["filing_id"],
                            payload={"source_url": filing["url"], "sha256": digest}, observed_at=now,
                        )
                    received += len(trades)
                    with conn.cursor() as cur:
                        for trade in trades:
                            cur.execute(
                                """
                                INSERT INTO ownership.congress_trade (
                                    company_id,security_id,politician_name,person_name,person_title,chamber,
                                    transaction_date,disclosure_date,filing_date,transaction_type,transaction_code,
                                    amount_min,amount_max,amount_range,source,provider,source_url,accession_number,
                                    raw_document_hash,raw_s3_key,signal,provider_transaction_id,asset_name,owner
                                ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                                ON CONFLICT (provider_transaction_id) WHERE provider_transaction_id IS NOT NULL DO NOTHING
                                """,
                                (security[1],security[0],trade["person_name"],trade["person_name"],trade["person_title"],trade["chamber"],
                                 trade["transaction_date"],trade["disclosure_date"],trade["filing_date"],trade["transaction_type"],trade["transaction_code"],
                                 trade["amount_min"],trade["amount_max"],trade["amount_range"],"House Financial Disclosure", "house_clerk", filing["url"],filing["filing_id"],
                                 digest,raw_key,trade["signal"],trade["provider_transaction_id"],trade["asset_name"],trade["owner"]),
                            )
                            inserted += cur.rowcount
                        cur.execute(
                            "INSERT INTO ownership.congress_filing(provider,filing_id,chamber,person_name,filing_date,source_url,raw_document_hash,raw_s3_key) VALUES (%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING",
                            ("house_clerk",filing["filing_id"],"house",filing["person_name"],filing["filing_date"],filing["url"],digest,raw_key),
                        )
                    conn.commit()

            try:
                senate_filings = []
                for year in years:
                    end_date = now.date() if year == now.year else now.date().replace(year=year, month=12, day=31)
                    senate_filings.extend(await senate.search_ptrs(now.date().replace(year=year, month=1, day=1), end_date))
                for filing in senate_filings:
                    if not filing["electronic"] or ("senate_efd", filing["filing_id"]) in checked:
                        continue
                    content = await senate.document(filing["url"])
                    digest = hashlib.sha256(content).hexdigest()
                    trades = senate.parse_electronic_document(content, filing)
                    raw_key = None
                    if trades:
                        raw_key = archive.put_json(provider="senate_efd", dataset="sofi_congress_trades", object_name=filing["filing_id"], payload={"source_url": filing["url"], "sha256": digest}, observed_at=now)
                    received += len(trades)
                    with conn.cursor() as cur:
                        for trade in trades:
                            cur.execute(
                                """INSERT INTO ownership.congress_trade (company_id,security_id,politician_name,person_name,person_title,chamber,transaction_date,disclosure_date,filing_date,transaction_type,transaction_code,amount_min,amount_max,amount_range,source,provider,source_url,accession_number,raw_document_hash,raw_s3_key,signal,provider_transaction_id,asset_name,owner) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT (provider_transaction_id) WHERE provider_transaction_id IS NOT NULL DO NOTHING""",
                                (security[1],security[0],trade["person_name"],trade["person_name"],trade["person_title"],trade["chamber"],trade["transaction_date"],trade["disclosure_date"],trade["filing_date"],trade["transaction_type"],trade["transaction_code"],trade["amount_min"],trade["amount_max"],trade["amount_range"],"Senate eFD","senate_efd",filing["url"],filing["filing_id"],digest,raw_key,trade["signal"],trade["provider_transaction_id"],trade["asset_name"],trade["owner"]),
                            )
                            inserted += cur.rowcount
                        cur.execute("INSERT INTO ownership.congress_filing(provider,filing_id,chamber,person_name,filing_date,source_url,raw_document_hash,raw_s3_key) VALUES (%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING", ("senate_efd",filing["filing_id"],"senate",filing["person_name"],filing["filing_date"],filing["url"],digest,raw_key))
                    conn.commit()
            except Exception as exc:
                log.warning("senate_efd_unavailable", error=str(exc))

        finish_run(run_id,status="SUCCESS",records_received=received,records_inserted=inserted)
        return inserted
    except Exception as exc:
        finish_run(run_id,status="FAILED",error_message=str(exc))
        raise
    finally:
        await house.close()
        await senate.close()
