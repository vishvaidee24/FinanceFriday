from datetime import date
from decimal import Decimal

from app.providers.congress import SenateDisclosureProvider, amount_bounds, parse_date, transaction_meaning


def test_house_value_helpers() -> None:
    assert parse_date("01/02/2025") == date(2025, 1, 2)
    assert parse_date("01/02/25") == date(2025, 1, 2)
    assert amount_bounds("$1,001 - $15,000") == (Decimal("1001"), Decimal("15000"))


def test_congress_signals() -> None:
    assert transaction_meaning("P") == ("purchase", "positive")
    assert transaction_meaning("S") == ("sale", "negative")
    assert transaction_meaning("E") == ("exchange", "neutral")


def test_senate_electronic_ptr_parser() -> None:
    html = b"""<table><tr><th>#</th><th>Transaction Date</th><th>Owner</th><th>Ticker</th><th>Asset Name</th><th>Asset Type</th><th>Type</th><th>Amount</th><th>Comment</th></tr><tr><td>1</td><td>08/20/2026</td><td>Spouse</td><td>SOFI</td><td>SoFi Technologies Common Stock</td><td>Stock</td><td>Purchase</td><td>$1,001 - $15,000</td><td>--</td></tr></table>"""
    filing = {"filing_id": "abc", "person_name": "Example Senator", "filing_date": date(2026, 9, 1)}
    rows = SenateDisclosureProvider.parse_electronic_document(html, filing)
    assert len(rows) == 1
    assert rows[0]["signal"] == "positive"
    assert rows[0]["owner"] == "Spouse"
    assert rows[0]["ticker"] == "SOFI"


def test_senate_parser_uses_tracked_ticker_universe() -> None:
    html = b"""<table><tr><td>1</td><td>08/20/2026</td><td>Self</td><td>INTC</td><td>Intel Corporation</td><td>Stock</td><td>Sale</td><td>$15,001 - $50,000</td><td>--</td></tr></table>"""
    filing = {"filing_id": "intel", "person_name": "Example Senator", "filing_date": date(2026, 9, 1)}
    rows = SenateDisclosureProvider.parse_electronic_document(
        html, filing, ("INTC", "SOFI")
    )
    assert len(rows) == 1
    assert rows[0]["ticker"] == "INTC"
    assert rows[0]["signal"] == "negative"
