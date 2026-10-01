from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class NewsClassification:
    category: str
    sentiment_label: str
    sentiment_score: float
    method: str = "keyword_rules_v1"


CATEGORY_TERMS: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "geopolitical",
        (
            "war", "military", "conflict", "sanction", "geopolit", "nato",
            "missile", "invasion", "ceasefire", "tariff", "trade war",
        ),
    ),
    (
        "analyst_prediction",
        (
            "analyst", "price target", "upgrade", "downgrade", "forecast",
            "rating", "outperform", "underperform", "wall street says",
        ),
    ),
    (
        "earnings_financials",
        (
            "earnings", "revenue", "net income", "profit", "loss", "eps",
            "quarterly results", "guidance", "10-q", "10-k",
        ),
    ),
    (
        "regulatory_legal",
        (
            "sec filing", "regulator", "regulation", "lawsuit", "court",
            "investigation", "compliance", "8-k", "form 4",
        ),
    ),
    (
        "macro_economy",
        (
            "federal reserve", "the fed", "interest rate", "inflation", "cpi",
            "jobs report", "unemployment", "gdp", "treasury yield", "recession",
        ),
    ),
    (
        "broad_market",
        (
            "stock market", "s&p 500", "nasdaq", "dow jones", "market futures",
            "stocks rally", "stocks fall", "market selloff", "bull market",
            "bear market", "wall street",
        ),
    ),
    (
        "company_strategy",
        (
            "acquisition", "partnership", "launch", "product", "member growth",
            "expands", "platform", "chief executive", "anthony noto",
        ),
    ),
)

POSITIVE_TERMS = (
    "beat estimates", "record revenue", "profit", "growth", "upgrade", "outperform",
    "price target increase", "rally", "surge", "gain", "strong", "expands",
    "approval", "rate cut", "ceasefire", "recovery", "bull market",
)

NEGATIVE_TERMS = (
    "miss estimates", "net loss", "downgrade", "underperform", "price target cut",
    "selloff", "plunge", "decline", "weak", "lawsuit", "investigation", "recession",
    "inflation", "rate hike", "war", "invasion", "sanction", "tariff", "conflict",
)


def classify_news(title: str, summary: str | None = None) -> NewsClassification:
    text = f"{title} {summary or ''}".casefold()
    category = "company_news"
    for candidate, terms in CATEGORY_TERMS:
        if any(term in text for term in terms):
            category = candidate
            break

    positive = sum(term in text for term in POSITIVE_TERMS)
    negative = sum(term in text for term in NEGATIVE_TERMS)
    raw_score = positive - negative
    score = max(-1.0, min(1.0, raw_score / 3))
    if score > 0:
        label = "POSITIVE"
    elif score < 0:
        label = "NEGATIVE"
    else:
        label = "NEUTRAL"
    return NewsClassification(category, label, score)
