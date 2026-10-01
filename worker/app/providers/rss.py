from dataclasses import dataclass
import feedparser

@dataclass(slots=True)
class FeedItem:
    title: str
    url: str
    summary: str | None

class RssProvider:
    def fetch(self, url: str) -> list[FeedItem]:
        parsed = feedparser.parse(url)
        return [
            FeedItem(
                title=e.get("title", ""),
                url=e.get("link", ""),
                summary=e.get("summary"),
            )
            for e in parsed.entries
        ]
