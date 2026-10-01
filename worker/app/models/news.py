from datetime import datetime

from pydantic import BaseModel


class NewsArticle(BaseModel):
    provider: str
    provider_article_id: str
    source_name: str
    title: str
    summary: str | None = None
    url: str
    published_at: datetime | None = None
    match_method: str
    relevance_score: float
