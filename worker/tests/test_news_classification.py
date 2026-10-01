from app.common.news_classification import classify_news


def test_classifies_geopolitical_negative_news() -> None:
    result = classify_news("War and sanctions trigger global market selloff")
    assert result.category == "geopolitical"
    assert result.sentiment_label == "NEGATIVE"


def test_classifies_positive_analyst_news() -> None:
    result = classify_news("Analyst upgrade raises SOFI price target")
    assert result.category == "analyst_prediction"
    assert result.sentiment_label == "POSITIVE"


def test_keeps_ambiguous_filings_neutral() -> None:
    result = classify_news("SoFi Technologies filing: Form 4")
    assert result.category == "regulatory_legal"
    assert result.sentiment_label == "NEUTRAL"
