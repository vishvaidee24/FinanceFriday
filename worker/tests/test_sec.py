from app.providers.sec import SecProvider

def test_normalize_cik() -> None:
    assert SecProvider.normalize_cik("50863") == "0000050863"
