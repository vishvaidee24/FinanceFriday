import httpx
import hashlib
import xml.etree.ElementTree as ET
from datetime import date
from decimal import Decimal
from tenacity import retry, stop_after_attempt, wait_exponential
from app.config import get_settings
from app.models.ownership import InsiderTransaction

class SecProvider:
    def __init__(self) -> None:
        self.headers = {
            "User-Agent": get_settings().sec_user_agent,
            "Accept-Encoding": "gzip, deflate",
        }

    @staticmethod
    def normalize_cik(cik: str) -> str:
        return cik.zfill(10)

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=8),
        reraise=True,
    )
    async def get_submissions(self, cik: str) -> dict:
        cik = self.normalize_cik(cik)
        url = f"https://data.sec.gov/submissions/CIK{cik}.json"
        async with httpx.AsyncClient(headers=self.headers, timeout=30) as client:
            response = await client.get(url)
            response.raise_for_status()
            return response.json()

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=8),
        reraise=True,
    )
    async def get_submission_file(self, filename: str) -> dict:
        if not filename.startswith("CIK") or not filename.endswith(".json") or "/" in filename:
            raise ValueError("invalid SEC submissions filename")
        url = f"https://data.sec.gov/submissions/{filename}"
        async with httpx.AsyncClient(headers=self.headers, timeout=30) as client:
            response = await client.get(url)
            response.raise_for_status()
            return response.json()

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=8),
        reraise=True,
    )
    async def get_company_facts(self, cik: str) -> dict:
        cik = self.normalize_cik(cik)
        url = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"
        async with httpx.AsyncClient(headers=self.headers, timeout=30) as client:
            response = await client.get(url)
            response.raise_for_status()
            return response.json()

    async def get_document(self, url: str) -> bytes:
        async with httpx.AsyncClient(headers=self.headers, timeout=30) as client:
            response = await client.get(url)
            response.raise_for_status()
            return response.content

    @staticmethod
    def ownership_filings(payload: dict) -> list[dict[str, str]]:
        recent = payload.get("filings", {}).get("recent", {})
        filings: list[dict[str, str]] = []
        forms = recent.get("form", [])
        for index, form in enumerate(forms):
            if form.removesuffix("/A") not in {"3", "4", "5"}:
                continue
            accession = recent["accessionNumber"][index]
            document = recent["primaryDocument"][index].rsplit("/", 1)[-1]
            accession_path = accession.replace("-", "")
            cik = int(str(payload["cik"]))
            filings.append(
                {
                    "form": form,
                    "accession_number": accession,
                    "filing_date": recent["filingDate"][index],
                    "url": (
                        f"https://www.sec.gov/Archives/edgar/data/{cik}/"
                        f"{accession_path}/{document}"
                    ),
                }
            )
        return filings

    @staticmethod
    def parse_ownership_document(
        content: bytes,
        *,
        accession_number: str,
        filing_date: str,
        source_url: str,
    ) -> list[InsiderTransaction]:
        root = ET.fromstring(content)

        def value(node: ET.Element, path: str) -> str | None:
            found = node.find(path)
            if found is None or found.text is None:
                return None
            return found.text.strip() or None

        owner = root.find("reportingOwner")
        owner_cik = value(owner, "reportingOwnerId/rptOwnerCik") if owner is not None else None
        owner_name = value(owner, "reportingOwnerId/rptOwnerName") if owner is not None else None
        title = value(owner, "reportingOwnerRelationship/officerTitle") if owner is not None else None
        if not title and owner is not None:
            if value(owner, "reportingOwnerRelationship/isDirector") == "1":
                title = "Director"
            elif value(owner, "reportingOwnerRelationship/isTenPercentOwner") == "1":
                title = "10% Owner"

        document_hash = hashlib.sha256(content).hexdigest()
        result: list[InsiderTransaction] = []
        nodes = list(root.findall("nonDerivativeTable/nonDerivativeTransaction"))
        nodes += list(root.findall("derivativeTable/derivativeTransaction"))
        for index, node in enumerate(nodes):
            code = value(node, "transactionCoding/transactionCode")
            acquired_disposed = value(
                node, "transactionAmounts/transactionAcquiredDisposedCode/value"
            )
            shares_text = value(node, "transactionAmounts/transactionShares/value")
            price_text = value(node, "transactionAmounts/transactionPricePerShare/value")
            shares = Decimal(shares_text) if shares_text else None
            price = Decimal(price_text) if price_text else None
            if code == "P" and acquired_disposed == "A":
                signal = "positive"
            elif code == "S":
                signal = "unclear"
            elif code in {"A", "M", "F", "G", "C"}:
                signal = "neutral"
            else:
                signal = "unclear"
            transaction_type = {
                "P": "open_market_purchase",
                "S": "sale",
                "A": "grant_award",
                "M": "option_exercise",
                "F": "tax_withholding",
                "G": "gift",
                "C": "conversion",
            }.get(code or "", "other")
            result.append(
                InsiderTransaction(
                    provider_transaction_id=f"{accession_number}:{index}",
                    insider_cik=owner_cik,
                    person_name=owner_name or "Unknown reporting owner",
                    person_title=title,
                    transaction_date=(
                        date.fromisoformat(value(node, "transactionDate/value"))
                        if value(node, "transactionDate/value")
                        else None
                    ),
                    filing_date=date.fromisoformat(filing_date),
                    transaction_code=code,
                    transaction_type=transaction_type,
                    security_type=value(node, "securityTitle/value"),
                    shares=shares,
                    price=price,
                    transaction_value=(shares * price if shares is not None and price is not None else None),
                    shares_after=(
                        Decimal(after)
                        if (after := value(node, "postTransactionAmounts/sharesOwnedFollowingTransaction/value"))
                        else None
                    ),
                    ownership_type=value(node, "ownershipNature/directOrIndirectOwnership/value"),
                    accession_number=accession_number,
                    source_url=source_url,
                    raw_document_hash=document_hash,
                    signal=signal,
                )
            )
        return result
