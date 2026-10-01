from app.providers.fmp import FmpProvider


def test_parse_grades_maps_firm_rating_event() -> None:
    row = {
        "symbol": "SOFI",
        "date": "2026-09-24",
        "gradingCompany": "Example Research",
        "previousGrade": "Hold",
        "newGrade": "Buy",
        "action": "upgrade",
    }
    rating = FmpProvider.parse_grades([row])[0]
    assert rating.symbol == "SOFI"
    assert rating.firm == "Example Research"
    assert rating.analyst_name is None
    assert rating.prior_rating == "Hold"
    assert rating.new_rating == "Buy"
    assert rating.provider == "fmp_grades"


def test_record_key_is_deterministic_and_normalizes_symbol() -> None:
    first = {
        "symbol": "sofi",
        "date": "2026-09-24",
        "gradingCompany": "Example Research",
        "previousGrade": "Hold",
        "newGrade": "Buy",
        "action": "upgrade",
    }
    second = {**first, "symbol": "SOFI"}
    assert FmpProvider._record_key(first) == FmpProvider._record_key(second)
