from app.providers.news import is_sofi_company_news


def test_accepts_sofi_company_and_stock_news() -> None:
    assert is_sofi_company_news("SoFi Technologies reports quarterly earnings")
    assert is_sofi_company_news("SOFI stock rises after analyst price target increase")
    assert is_sofi_company_news("Anthony Noto discusses SoFi member growth")
    assert is_sofi_company_news("Upstart and SoFi lend to the same borrowers")


def test_rejects_sofi_venue_and_sports_news() -> None:
    assert not is_sofi_company_news("SoFi Shamrock Classic basketball matchup")
    assert not is_sofi_company_news("Rams win at SoFi Stadium")
    assert not is_sofi_company_news("Concert announced at SoFi")
    assert not is_sofi_company_news("Chargers face Raiders at SoFi")
