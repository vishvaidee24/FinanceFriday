from datetime import date
from decimal import Decimal
from typing import ClassVar

from app.providers.executive import (
    DisclosedCapitolProvider,
    OgeDisclosureProvider,
    _catalog_date,
)


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


def test_disclosed_capitol_parser_keeps_2016_and_biden_rows() -> None:
    content = b"""filer_name,role_title,agency,ticker,asset_description,transaction_type,transaction_date,amount_range,filing_date,filing_type,source_filing_id,disclosedcapitol_url
Old Official,Secretary,Agency,ABC,ABC Inc. (ABC),Sale,2015-12-31,"$1,001 - $15,000",2016-01-15,278-T,old,https://example.test/old
Biden Official,Secretary,Agency,XYZ,XYZ Inc. (XYZ),Buy,2022-03-04,"$15,001 - $50,000",2022-03-20,278-T,biden,https://example.test/biden
"""
    rows = DisclosedCapitolProvider.parse_dataset(content)
    assert len(rows) == 1
    assert rows[0]["person_name"] == "Biden Official"
    assert rows[0]["reported_ticker"] == "XYZ"
    assert rows[0]["signal"] == "positive"
