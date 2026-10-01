import csv
import hashlib
import html
import io
import re
from datetime import date, datetime
from typing import Any

import httpx
from pypdf import PdfReader
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.providers.congress import amount_bounds, parse_date, transaction_meaning

OGE_CATALOG_URL = "https://extapps2.oge.gov/201/Presiden.nsf/API.xsp/v2/rest"
DISCLOSED_CAPITOL_URL = (
    "https://raw.githubusercontent.com/disclosedcapitol/"
    "executive-branch-trades/main/data/executive_trades.csv"
)
EARLIEST_TRANSACTION_DATE = date(2016, 1, 1)
PDF_LINK_PATTERN = re.compile(r"href=['\"]([^'\"]+\.pdf)['\"]", re.IGNORECASE)
TICKER_PATTERN = re.compile(r"\(([A-Z][A-Z0-9.\-]{0,9})\)\s*$")
ROW_PATTERN = re.compile(
    r"^\s*\d+\s+(?P<asset>.+?)\s+"
    r"(?P<kind>Purchase|Sale|Exchange)\s+"
    r"(?P<date>\d{1,2}/\d{1,2}/\d{2,4})\s+"
    r"(?:Yes|No)\s+(?P<amount>Over\s+\$[\d,]+|\$[\d,]+\s*-\s*\$[\d,]+)\s*$",
    re.IGNORECASE,
)


def _filing_id(url: str, person_name: str, filing_date: date | None) -> str:
    match = re.search(r"/PAS\+Index/([^/]+)/", url, re.IGNORECASE)
    if match:
        return match.group(1).upper()
    value = f"{url}|{person_name}|{filing_date or ''}"
    return hashlib.sha256(value.encode()).hexdigest()


def _catalog_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value).date()
    except ValueError:
        return None


class OgeDisclosureProvider:
    def __init__(self) -> None:
        self.client = httpx.AsyncClient(
            follow_redirects=True,
            timeout=60,
            headers={"User-Agent": "FinanceFriday personal financial research"},
        )

    async def close(self) -> None:
        await self.client.aclose()

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(min=1, max=8),
        retry=retry_if_exception_type(httpx.HTTPError),
    )
    async def filings(self) -> list[dict[str, Any]]:
        response = await self.client.get(
            OGE_CATALOG_URL,
            params={"draw": 1, "start": 0, "length": 20000},
        )
        response.raise_for_status()
        filings: list[dict[str, Any]] = []
        for row in response.json().get("data", []):
            document_type = html.unescape(str(row.get("type") or ""))
            if "278 Transaction" not in document_type:
                continue
            link = PDF_LINK_PATTERN.search(document_type)
            source_url = html.unescape(link.group(1)) if link else None
            person_name = str(row.get("name") or "").strip()
            filing_date = _catalog_date(row.get("docDate"))
            filings.append(
                {
                    "filing_id": _filing_id(source_url or document_type, person_name, filing_date),
                    "person_name": person_name,
                    "person_title": (row.get("title") or None),
                    "agency": (row.get("agency") or None),
                    "filing_date": filing_date,
                    "url": source_url,
                    "access_status": "public_download" if source_url else "form_201_required",
                    "amended": bool(row.get("amended")) or "Amended" in document_type,
                }
            )
        return filings

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(min=1, max=8),
        retry=retry_if_exception_type(httpx.HTTPError),
    )
    async def document(self, url: str) -> bytes:
        response = await self.client.get(url)
        response.raise_for_status()
        return response.content

    @staticmethod
    def parse_document(content: bytes, filing: dict[str, Any]) -> list[dict[str, Any]]:
        reader = PdfReader(io.BytesIO(content))
        text = "\n".join(page.extract_text() or "" for page in reader.pages)
        results: list[dict[str, Any]] = []
        for line in text.splitlines():
            normalized = re.sub(r"\s+", " ", line).strip()
            match = ROW_PATTERN.match(normalized)
            if not match:
                continue
            asset_name = match.group("asset").strip()
            ticker_match = TICKER_PATTERN.search(asset_name)
            reported_ticker = ticker_match.group(1) if ticker_match else None
            transaction_type = match.group("kind").lower()
            code = {"purchase": "P", "sale": "S", "exchange": "E"}[transaction_type]
            _, signal = transaction_meaning(code)
            amount_range = match.group("amount")
            amount_min, amount_max = amount_bounds(amount_range)
            transaction_date = parse_date(match.group("date"))
            if transaction_date is None:
                continue
            filing_date = filing.get("filing_date")
            if transaction_date < EARLIEST_TRANSACTION_DATE:
                continue
            if filing_date is not None and transaction_date > filing_date:
                continue
            key = (
                f"oge:{filing['filing_id']}:{normalized}:"
                f"{filing['person_name']}:{transaction_date.isoformat()}"
            )
            results.append(
                {
                    "provider_transaction_id": hashlib.sha256(key.encode()).hexdigest(),
                    "person_name": filing["person_name"],
                    "person_title": filing.get("person_title"),
                    "agency": filing.get("agency"),
                    "transaction_date": transaction_date,
                    "filing_date": filing_date,
                    "transaction_type": transaction_type,
                    "amount_min": amount_min,
                    "amount_max": amount_max,
                    "amount_range": amount_range,
                    "asset_name": asset_name,
                    "reported_ticker": reported_ticker,
                    "owner": None,
                    "signal": signal,
                }
            )
        return results


class DisclosedCapitolProvider:
    def __init__(self) -> None:
        self.client = httpx.AsyncClient(
            follow_redirects=True,
            timeout=90,
            headers={"User-Agent": "FinanceFriday personal financial research"},
        )

    async def close(self) -> None:
        await self.client.aclose()

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(min=1, max=8),
        retry=retry_if_exception_type(httpx.HTTPError),
    )
    async def dataset(self) -> bytes:
        response = await self.client.get(DISCLOSED_CAPITOL_URL)
        response.raise_for_status()
        return response.content

    @staticmethod
    def parse_dataset(content: bytes) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        reader = csv.DictReader(io.StringIO(content.decode("utf-8-sig")))
        for source in reader:
            transaction_date = date.fromisoformat(source["transaction_date"])
            if transaction_date < EARLIEST_TRANSACTION_DATE:
                continue
            filing_date = (
                date.fromisoformat(source["filing_date"])
                if source.get("filing_date")
                else None
            )
            transaction_type = source["transaction_type"].strip().lower()
            if transaction_type.startswith(("buy", "purchase")):
                signal = "positive"
            elif transaction_type.startswith(("sale", "sell")):
                signal = "negative"
            elif transaction_type.startswith("exchange"):
                signal = "neutral"
            else:
                signal = "unclear"
            amount_range = source.get("amount_range") or None
            amount_min, amount_max = amount_bounds(amount_range)
            filing_id = (source.get("source_filing_id") or "").strip()
            if not filing_id:
                identity = "|".join(
                    (
                        source["filer_name"], source.get("filing_date") or "",
                        source.get("filing_type") or "", source["transaction_date"],
                    )
                )
                filing_id = hashlib.sha256(identity.encode()).hexdigest()
            identity = "|".join(
                source.get(field, "")
                for field in (
                    "filer_name", "ticker", "asset_description", "transaction_type",
                    "transaction_date", "amount_range", "filing_date", "filing_type",
                    "source_filing_id",
                )
            )
            ticker = (source.get("ticker") or "").strip().upper() or None
            rows.append(
                {
                    "provider_transaction_id": hashlib.sha256(identity.encode()).hexdigest(),
                    "filing_id": filing_id,
                    "person_name": source["filer_name"].strip(),
                    "person_title": (source.get("role_title") or None),
                    "agency": (source.get("agency") or None),
                    "transaction_date": transaction_date,
                    "filing_date": filing_date,
                    "filing_type": source.get("filing_type") or "278-T",
                    "transaction_type": transaction_type,
                    "amount_min": amount_min,
                    "amount_max": amount_max,
                    "amount_range": amount_range,
                    "asset_name": source["asset_description"].strip(),
                    "reported_ticker": ticker,
                    "owner": None,
                    "signal": signal,
                    "source_url": source.get("disclosedcapitol_url") or DISCLOSED_CAPITOL_URL,
                }
            )
        return rows
