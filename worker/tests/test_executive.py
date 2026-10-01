from datetime import date
from decimal import Decimal
from typing import ClassVar

from app.providers.executive import OgeDisclosureProvider, _catalog_date


def test_catalog_date() -> None:
    assert _catalog_date("2025-06-07T04:06:35") == date(2025, 6, 7)


def test_parse_integrity_ptr_rows() -> None:
    class Page:
        def extract_text(self) -> str:
            return (
                "Transactions\n"
                "1 Walmart, Inc. (WMT) Sale 03/24/2025 No $1,001 - $15,000\n"
                "2 Tesla, Inc. (TSLA) Purchase 06/10/2025 No $15,001 - $50,000"
            )

    class Reader:
        pages: ClassVar = [Page()]

    filing = {
        "filing_id": "abc",
        "person_name": "Hegseth, Pete",
        "person_title": "Secretary",
        "agency": "Department of Defense",
        "filing_date": date(2025, 6, 20),
    }
    original = __import__("app.providers.executive", fromlist=["PdfReader"]).PdfReader
    module = __import__("app.providers.executive", fromlist=["PdfReader"])
    module.PdfReader = lambda _: Reader()
    try:
        rows = OgeDisclosureProvider.parse_document(b"pdf", filing)
    finally:
        module.PdfReader = original

    assert len(rows) == 2
    assert rows[0]["reported_ticker"] == "WMT"
    assert rows[0]["transaction_type"] == "sale"
    assert rows[1]["amount_min"] == Decimal(15001)
    assert rows[1]["signal"] == "positive"


def test_parser_rejects_ocr_dates_outside_supported_window() -> None:
    class Page:
        def extract_text(self) -> str:
            return (
                "1 Bad Past (BAD) Sale 08/12/2001 No $1,001 - $15,000\n"
                "2 Bad Future (BAD) Sale 04/04/2225 No $1,001 - $15,000"
            )

    class Reader:
        pages: ClassVar = [Page()]

    filing = {
        "filing_id": "bad-dates",
        "person_name": "Example, Official",
        "filing_date": date(2025, 6, 7),
    }
    module = __import__("app.providers.executive", fromlist=["PdfReader"])
    original = module.PdfReader
    module.PdfReader = lambda _: Reader()
    try:
        rows = OgeDisclosureProvider.parse_document(b"pdf", filing)
    finally:
        module.PdfReader = original
    assert rows == []
