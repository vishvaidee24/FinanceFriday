from datetime import date
from decimal import Decimal

from pydantic import BaseModel


class InsiderTransaction(BaseModel):
    provider_transaction_id: str
    insider_cik: str | None
    person_name: str
    person_title: str | None
    transaction_date: date | None
    filing_date: date
    transaction_code: str | None
    transaction_type: str
    security_type: str | None
    shares: Decimal | None
    price: Decimal | None
    transaction_value: Decimal | None
    shares_after: Decimal | None
    ownership_type: str | None
    accession_number: str
    source_url: str
    raw_document_hash: str
    signal: str
