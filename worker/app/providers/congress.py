import csv
import hashlib
import io
import json
import re
from datetime import date, datetime
from decimal import Decimal
from typing import Any
from html.parser import HTMLParser

import httpx
from pypdf import PdfReader
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential


SOFI_PATTERN = re.compile(r"(?:\bSOFI\b|SoFi\s+Technologies)", re.IGNORECASE)
DATE_PATTERN = re.compile(r"\b(\d{1,2}/\d{1,2}/\d{2,4})\b")
AMOUNT_PATTERN = re.compile(r"\$[\d,]+\s*-\s*\$[\d,]+|Over\s+\$[\d,]+", re.IGNORECASE)


def parse_date(value: str | None) -> date | None:
    if not value:
        return None
    for fmt in ("%m/%d/%Y", "%m/%d/%y"):
        try:
            return datetime.strptime(value.strip(), fmt).date()
        except ValueError:
            pass
    return None


def amount_bounds(value: str | None) -> tuple[Decimal | None, Decimal | None]:
    if not value:
        return None, None
    numbers = [Decimal(x.replace(",", "")) for x in re.findall(r"\$([\d,]+)", value)]
    if not numbers:
        return None, None
    return numbers[0], numbers[1] if len(numbers) > 1 else None


def transaction_meaning(code: str) -> tuple[str, str]:
    normalized = code.strip().upper()
    if normalized.startswith("P"):
        return "purchase", "positive"
    if normalized.startswith("S"):
        return "sale", "negative"
    if normalized.startswith("E"):
        return "exchange", "neutral"
    return normalized.lower() or "unclear", "unclear"


class HouseDisclosureProvider:
    base = "https://disclosures-clerk.house.gov"

    def __init__(self) -> None:
        self.client = httpx.AsyncClient(
            follow_redirects=True,
            timeout=45,
            headers={"User-Agent": "FinanceFriday personal financial research"},
        )

    async def close(self) -> None:
        await self.client.aclose()

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=8), retry=retry_if_exception_type(httpx.HTTPError))
    async def filings(self, year: int) -> list[dict[str, Any]]:
        url = f"{self.base}/public_disc/financial-pdfs/{year}FD.txt"
        response = await self.client.get(url)
        response.raise_for_status()
        rows = csv.DictReader(io.StringIO(response.text.replace("\r\r\n", "\n")), delimiter="\t")
        filings = []
        for row in rows:
            if row.get("FilingType") != "P":
                continue
            filing_id = (row.get("DocID") or "").strip()
            filings.append({
                "filing_id": filing_id,
                "person_name": " ".join(filter(None, [(row.get("Prefix") or "").strip(), (row.get("First") or "").strip(), (row.get("Last") or "").strip(), (row.get("Suffix") or "").strip()])),
                "filing_date": parse_date(row.get("FilingDate")),
                "url": f"{self.base}/public_disc/ptr-pdfs/{year}/{filing_id}.pdf",
            })
        return filings

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=8), retry=retry_if_exception_type(httpx.HTTPError))
    async def document(self, url: str) -> bytes:
        response = await self.client.get(url)
        response.raise_for_status()
        return response.content

    @staticmethod
    def parse_document(content: bytes, filing: dict[str, Any]) -> list[dict[str, Any]]:
        text = "\n".join(page.extract_text() or "" for page in PdfReader(io.BytesIO(content)).pages)
        if not SOFI_PATTERN.search(text):
            return []
        lines = [re.sub(r"\s+", " ", line).strip() for line in text.splitlines() if line.strip()]
        results = []
        consumed: set[int] = set()
        for index, line in enumerate(lines):
            if index in consumed or not SOFI_PATTERN.search(line):
                continue
            asset_lines = [line]
            if "SOFI" not in line.upper() and index + 1 < len(lines) and "SOFI" in lines[index + 1].upper():
                asset_lines.append(lines[index + 1])
                consumed.add(index + 1)
            elif index > 0 and SOFI_PATTERN.search(lines[index - 1]):
                continue
            window = " | ".join(lines[index:index + 8])
            dates = DATE_PATTERN.findall(window)
            amount_match = AMOUNT_PATTERN.search(window)
            code_match = re.search(r"(?:Transaction Type\s*)?\b(P|S|E)(?:\s*\([^)]+\))?\b", window, re.IGNORECASE)
            if not dates or not code_match:
                continue
            transaction_type, signal = transaction_meaning(code_match.group(1))
            amount_range = amount_match.group(0) if amount_match else None
            amount_min, amount_max = amount_bounds(amount_range)
            asset_name = " ".join(asset_lines)
            key = f"house:{filing['filing_id']}:{index}:{asset_name}:{dates[0]}:{code_match.group(1)}"
            results.append({
                "provider_transaction_id": hashlib.sha256(key.encode()).hexdigest(),
                "person_name": filing["person_name"], "person_title": "U.S. Representative",
                "chamber": "house", "transaction_date": parse_date(dates[0]),
                "disclosure_date": parse_date(dates[1]) if len(dates) > 1 else filing["filing_date"],
                "filing_date": filing["filing_date"], "transaction_type": transaction_type,
                "transaction_code": code_match.group(1).upper(), "amount_range": amount_range,
                "amount_min": amount_min, "amount_max": amount_max, "asset_name": asset_name,
                "owner": None, "signal": signal,
            })
        return results


class SenateDisclosureProvider:
    base = "https://efdsearch.senate.gov"

    def __init__(self) -> None:
        self.client = httpx.AsyncClient(follow_redirects=True, timeout=45, headers={"User-Agent": "FinanceFriday personal financial research"})

    async def close(self) -> None:
        await self.client.aclose()

    async def search_ptrs(self, start_date: date, end_date: date) -> list[dict[str, Any]]:
        home = await self.client.get(f"{self.base}/search/home/")
        home.raise_for_status()
        token_match = re.search(r'name="csrfmiddlewaretoken" value="([^"]+)', home.text)
        if not token_match:
            raise RuntimeError("Senate eFD agreement token was not available")
        agreed = await self.client.post(str(home.url), data={"csrfmiddlewaretoken": token_match.group(1), "prohibition_agreement": "1"}, headers={"Referer": str(home.url)})
        agreed.raise_for_status()
        search_token = re.search(r'name="csrfmiddlewaretoken" value="([^"]+)', agreed.text)
        if not search_token:
            raise RuntimeError("Senate eFD search token was not available")
        searched = await self.client.post(str(agreed.url), data={
            "csrfmiddlewaretoken": search_token.group(1), "filer_type": "1", "report_type": "11",
            "submitted_start_date": start_date.strftime("%m/%d/%Y"), "submitted_end_date": end_date.strftime("%m/%d/%Y"),
        }, headers={"Referer": str(agreed.url)})
        searched.raise_for_status()
        csrf = self.client.cookies.get("csrftoken")
        payload = {
            "draw": "1", "start": "0", "length": "1000", "search[value]": "", "search[regex]": "false",
            "report_types": "[11]", "filer_types": "[1]",
            "submitted_start_date": start_date.strftime("%m/%d/%Y 00:00:00"), "submitted_end_date": end_date.strftime("%m/%d/%Y 23:59:59"),
            "candidate_state": "", "senator_state": "", "office_id": "", "first_name": "", "last_name": "",
            "order[0][column]": "1", "order[0][dir]": "asc",
        }
        for index in range(5):
            payload.update({f"columns[{index}][data]": str(index), f"columns[{index}][name]": "", f"columns[{index}][searchable]": "true", f"columns[{index}][orderable]": "true", f"columns[{index}][search][value]": "", f"columns[{index}][search][regex]": "false"})
        result_rows = []
        while True:
            response = await self.client.post(f"{self.base}/search/report/data/", data=payload, headers={"Referer": str(searched.url), "X-CSRFToken": csrf or "", "X-Requested-With": "XMLHttpRequest"})
            if response.status_code == 503:
                raise RuntimeError("Senate eFD is temporarily unavailable")
            response.raise_for_status()
            result = response.json()
            page_rows = result.get("data", [])
            result_rows.extend(page_rows)
            if len(result_rows) >= result.get("recordsFiltered", 0) or not page_rows:
                break
            payload["start"] = str(len(result_rows))
        filings = []
        for row in result_rows:
            href = re.search(r'href="([^"]+)"', row[3])
            if href:
                path = href.group(1)
                filings.append({"filing_id": path.rstrip("/").rsplit("/", 1)[-1], "person_name": re.sub(r"\s*\(Senator\)\s*$", "", row[2]).strip(), "filing_date": parse_date(row[4]), "url": f"{self.base}{path}", "electronic": "/ptr/" in path})
        return filings

    async def document(self, url: str) -> bytes:
        response = await self.client.get(url)
        response.raise_for_status()
        return response.content

    @staticmethod
    def parse_electronic_document(content: bytes, filing: dict[str, Any]) -> list[dict[str, Any]]:
        parser = _TableParser()
        parser.feed(content.decode("utf-8", errors="replace"))
        results = []
        for cells in parser.rows:
            if len(cells) < 9 or cells[0] == "#":
                continue
            ticker, asset_name = cells[3].strip(), cells[4].strip()
            if ticker.upper() != "SOFI" and not SOFI_PATTERN.search(asset_name):
                continue
            label = cells[6].strip()
            if label.lower().startswith("purchase"):
                code, signal = "P", "positive"
            elif label.lower().startswith("sale"):
                code, signal = "S", "negative"
            elif label.lower().startswith("exchange"):
                code, signal = "E", "neutral"
            else:
                code, signal = None, "unclear"
            amount_range = cells[7].strip()
            amount_min, amount_max = amount_bounds(amount_range)
            key = f"senate:{filing['filing_id']}:{cells[0]}:{cells[1]}:{asset_name}:{label}"
            results.append({"provider_transaction_id": hashlib.sha256(key.encode()).hexdigest(), "person_name": filing["person_name"], "person_title": "U.S. Senator", "chamber": "senate", "transaction_date": parse_date(cells[1]), "disclosure_date": filing["filing_date"], "filing_date": filing["filing_date"], "transaction_type": label, "transaction_code": code, "amount_range": amount_range, "amount_min": amount_min, "amount_max": amount_max, "asset_name": asset_name, "owner": cells[2].strip() or None, "signal": signal})
        return results


class _TableParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.rows: list[list[str]] = []
        self.row: list[str] | None = None
        self.cell: list[str] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "tr": self.row = []
        elif tag in {"td", "th"} and self.row is not None: self.cell = []

    def handle_data(self, data: str) -> None:
        if self.cell is not None: self.cell.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag in {"td", "th"} and self.cell is not None and self.row is not None:
            self.row.append(re.sub(r"\s+", " ", " ".join(self.cell)).strip()); self.cell = None
        elif tag == "tr" and self.row is not None:
            if self.row: self.rows.append(self.row)
            self.row = None
