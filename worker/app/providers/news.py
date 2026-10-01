import html
import re
import xml.etree.ElementTree as ET
from datetime import UTC, date, datetime
from email.utils import parsedate_to_datetime
from urllib.parse import quote, urljoin

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from app.config import get_settings
from app.models.news import NewsArticle

SOFI_TERMS = ("SOFI", "SoFi", "SoFi Technologies", "SoFi Technologies, Inc.")
GOOGLE_NEWS_URL = (
    "https://news.google.com/rss/search?"
    f"q={quote('\"SOFI stock\" OR \"SoFi Technologies\"')}&hl=en-US&gl=US&ceid=US:en"
)
SOFI_IR_URL = "https://investors.sofi.com/news/press-releases/default.aspx"
INTEL_IR_URL = "https://www.intc.com/news-events/press-releases"
MARKET_NEWS_URL = (
    "https://news.google.com/rss/search?"
    f"q={quote('\"stock market\" OR \"S&P 500\" OR \"Federal Reserve\"')}&hl=en-US&gl=US&ceid=US:en"
)
GEOPOLITICAL_NEWS_URL = (
    "https://news.google.com/rss/search?"
    f"q={quote('\"geopolitical risk\" markets OR sanctions OR tariffs OR oil')}&hl=en-US&gl=US&ceid=US:en"
)


def _clean(value: str | None) -> str | None:
    if not value:
        return None
    text = re.sub(r"<[^>]+>", " ", html.unescape(value))
    return re.sub(r"\s+", " ", text).strip()[:2000] or None


def _published(value: str | None) -> datetime | None:
    if not value:
        return None
    parsed = parsedate_to_datetime(value)
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def is_sofi_company_news(value: str) -> bool:
    folded = value.casefold()
    venue_context = (
        "sofi stadium", "sofi center", "rams", "chargers", "raiders",
        "nfl", "football", "super bowl", "giants", "packers", "76ers",
        "concert", "bts", "pregame", "field goal", "touchdown",
        "shamrock classic", "basketball", "athletics",
    )
    if "sofi" in folded and any(term in folded for term in venue_context):
        return False
    strong_company_identifiers = (
        "sofi technologies", "nasdaq: sofi", "nasdaq:sofi", "$sofi",
        "sofi stock", "sofi shares", "sofi bank",
    )
    if any(term in folded for term in strong_company_identifiers):
        return True
    company_context = (
        "stock", "nasdaq", "bank", "financial", "earnings", "shares",
        "investor", "loan", "fintech", "price target", "crypto", "revenue",
        "net income", "wall street", "valuation", "borrower", "deposit",
        "analyst", "sec filing", "quarter", "guidance", "anthony noto",
        "chief executive", "cfo", "acquisition", "member growth",
    )
    return "sofi" in folded and any(term in folded for term in company_context)


def is_intel_company_news(value: str) -> bool:
    folded = value.casefold()
    strong_identifiers = (
        "intel corporation", "nasdaq: intc", "nasdaq:intc", "$intc",
        "intc stock", "intel stock", "intel shares",
    )
    if any(term in folded for term in strong_identifiers):
        return True
    company_context = (
        "semiconductor", "chip", "foundry", "xeon", "core ultra", "gaudi",
        "panther lake", "earnings", "revenue", "guidance", "quarter",
        "price target", "analyst", "chief executive", "lip-bu tan",
        "sec filing", "manufacturing", "fab", "processor", "cpu", "ai pc",
    )
    return "intel" in folded and any(term in folded for term in company_context)


class SofiNewsProvider:
    def __init__(self) -> None:
        self.headers = {"User-Agent": get_settings().sec_user_agent}

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=8),
        reraise=True,
    )
    async def _fetch_google_feed(
        self,
        url: str,
        *,
        require_sofi: bool,
        match_method: str,
        relevance_score: float,
    ) -> tuple[str, list[NewsArticle]]:
        async with httpx.AsyncClient(headers=self.headers, timeout=30) as client:
            response = await client.get(url)
            response.raise_for_status()
        root = ET.fromstring(response.text)
        articles: list[NewsArticle] = []
        for item in root.findall("./channel/item"):
            title = item.findtext("title", "").strip()
            summary = _clean(item.findtext("description"))
            searchable = f"{title} {summary or ''}"
            if require_sofi and not is_sofi_company_news(searchable):
                continue
            url = item.findtext("link", "").strip()
            article_id = item.findtext("guid", "").strip() or url
            source = item.find("source")
            articles.append(
                NewsArticle(
                    provider="google_news",
                    provider_article_id=article_id,
                    source_name=(source.text or "Google News") if source is not None else "Google News",
                    title=title,
                    summary=summary,
                    url=url,
                    published_at=_published(item.findtext("pubDate")),
                    match_method=match_method,
                    relevance_score=relevance_score,
                )
            )
        return response.text, articles

    async def fetch_google_news(self) -> tuple[str, list[NewsArticle]]:
        return await self._fetch_google_feed(
            GOOGLE_NEWS_URL,
            require_sofi=True,
            match_method="company_keyword",
            relevance_score=0.8,
        )

    async def fetch_market_news(self) -> tuple[str, list[NewsArticle]]:
        return await self._fetch_google_feed(
            MARKET_NEWS_URL,
            require_sofi=False,
            match_method="broad_market_context",
            relevance_score=0.35,
        )

    async def fetch_geopolitical_news(self) -> tuple[str, list[NewsArticle]]:
        return await self._fetch_google_feed(
            GEOPOLITICAL_NEWS_URL,
            require_sofi=False,
            match_method="geopolitical_context",
            relevance_score=0.25,
        )

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=8),
        reraise=True,
    )
    async def fetch_investor_relations(self) -> tuple[str, list[NewsArticle]]:
        return await self._fetch_investor_relations(
            SOFI_IR_URL, provider_name="sofi_ir", source_name="SoFi Investor Relations"
        )

    async def _fetch_investor_relations(
        self, url: str, *, provider_name: str, source_name: str
    ) -> tuple[str, list[NewsArticle]]:
        async with httpx.AsyncClient(headers=self.headers, timeout=30, follow_redirects=True) as client:
            response = await client.get(url)
            response.raise_for_status()
        pattern = re.compile(
            r'<a[^>]+href=["\'](?P<url>[^"\']*(?:/news/news-details/|/news-events/press-releases/detail/)[^"\']+)["\'][^>]*>(?P<title>.*?)</a>',
            re.IGNORECASE | re.DOTALL,
        )
        seen: set[str] = set()
        articles: list[NewsArticle] = []
        for match in pattern.finditer(response.text):
            article_url = urljoin(url, html.unescape(match.group("url")))
            title = _clean(match.group("title")) or ""
            if not title or article_url in seen:
                continue
            seen.add(article_url)
            articles.append(
                NewsArticle(
                    provider=provider_name,
                    provider_article_id=article_url,
                    source_name=source_name,
                    title=title,
                    url=article_url,
                    match_method="official_company_source",
                    relevance_score=1.0,
                )
            )
        return response.text, articles

    @staticmethod
    def sec_articles(
        payload: dict, *, cik: str | None = None, published_since: date | None = None
    ) -> list[NewsArticle]:
        recent = payload.get("filings", {}).get("recent", payload)
        cik = str(cik or payload.get("cik", "1818874"))
        articles: list[NewsArticle] = []
        for index, accession in enumerate(recent.get("accessionNumber", [])):
            form = recent.get("form", [])[index]
            primary_document = recent.get("primaryDocument", [])[index]
            filing_date = recent.get("filingDate", [])[index]
            if published_since and date.fromisoformat(filing_date) < published_since:
                continue
            accession_path = accession.replace("-", "")
            url = f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{accession_path}/{primary_document}"
            articles.append(
                NewsArticle(
                    provider="sec_edgar",
                    provider_article_id=accession,
                    source_name="SEC EDGAR",
                    title=f"SoFi Technologies filing: {form}",
                    summary=f"Official {form} filing submitted to the SEC.",
                    url=url,
                    published_at=datetime.fromisoformat(filing_date).replace(tzinfo=UTC),
                    match_method="cik",
                    relevance_score=1.0,
                )
            )
        return articles


class IntelNewsProvider(SofiNewsProvider):
    async def fetch_google_news(self) -> tuple[str, list[NewsArticle]]:
        url = (
            "https://news.google.com/rss/search?"
            f"q={quote('\"INTC stock\" OR \"Intel Corporation\"')}&hl=en-US&gl=US&ceid=US:en"
        )
        payload, articles = await self._fetch_google_feed(
            url,
            require_sofi=False,
            match_method="company_keyword",
            relevance_score=0.8,
        )
        return payload, [
            article
            for article in articles
            if is_intel_company_news(f"{article.title} {article.summary or ''}")
        ]

    async def fetch_investor_relations(self) -> tuple[str, list[NewsArticle]]:
        return await self._fetch_investor_relations(
            INTEL_IR_URL,
            provider_name="intel_ir",
            source_name="Intel Investor Relations",
        )

    async def fetch_investor_relations_history(
        self, start_year: int
    ) -> tuple[dict[str, str], list[NewsArticle]]:
        payloads: dict[str, str] = {}
        articles: list[NewsArticle] = []
        seen: set[str] = set()
        pattern = re.compile(
            r'<article[^>]+class=["\'][^"\']*media-container[^"\']*["\'][^>]*>(?P<body>.*?)</article>',
            re.IGNORECASE | re.DOTALL,
        )
        link_pattern = re.compile(
            r'<div[^>]+class=["\'][^"\']*media-title[^"\']*["\'][^>]*>\s*'
            r'<a[^>]+href=["\'](?P<url>[^"\']*/news-events/press-releases/detail/[^"\']+)["\'][^>]*>'
            r'(?P<title>.*?)</a>',
            re.IGNORECASE | re.DOTALL,
        )
        time_pattern = re.compile(r'<time[^>]+datetime=["\'](?P<date>[^"\']+)["\']', re.IGNORECASE)
        async with httpx.AsyncClient(headers=self.headers, timeout=30, follow_redirects=True) as client:
            for year in range(start_year, datetime.now(UTC).year + 1):
                for page in range(1, 31):
                    url = f"{INTEL_IR_URL}?year={year}&page={page}"
                    response = await client.get(url)
                    response.raise_for_status()
                    key = str(response.url)
                    payloads[key] = response.text
                    page_articles = 0
                    for block in pattern.finditer(response.text):
                        link = link_pattern.search(block.group("body"))
                        published = time_pattern.search(block.group("body"))
                        if not link:
                            continue
                        article_url = urljoin(INTEL_IR_URL, html.unescape(link.group("url")))
                        title = _clean(link.group("title")) or ""
                        if not title or article_url in seen:
                            continue
                        seen.add(article_url)
                        page_articles += 1
                        published_at = None
                        if published:
                            published_at = datetime.fromisoformat(published.group("date")).replace(tzinfo=UTC)
                        articles.append(NewsArticle(
                            provider="intel_ir", provider_article_id=article_url,
                            source_name="Intel Investor Relations", title=title,
                            url=article_url, published_at=published_at,
                            match_method="official_company_source", relevance_score=1.0,
                        ))
                    if page_articles == 0:
                        break
        return payloads, articles

    @staticmethod
    def sec_articles(
        payload: dict, *, cik: str | None = None, published_since: date | None = None
    ) -> list[NewsArticle]:
        articles = SofiNewsProvider.sec_articles(
            payload, cik=cik, published_since=published_since
        )
        for article in articles:
            article.title = article.title.replace("SoFi Technologies", "Intel Corporation")
        return articles
