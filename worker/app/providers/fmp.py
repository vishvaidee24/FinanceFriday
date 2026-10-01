import hashlib
import json
from datetime import datetime, timezone
from typing import Any

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from app.config import get_settings
from app.models.analyst import AnalystRating


class FmpProvider:
    base_url = "https://financialmodelingprep.com/stable"

    def __init__(self, *, api_key: str | None = None) -> None:
        self.api_key = api_key or get_settings().fmp_api_key
        if not self.api_key:
            raise RuntimeError("FMP_API_KEY is required")

    @staticmethod
    def _record_key(row: dict[str, Any]) -> str:
        normalized = {
            "symbol": str(row.get("symbol") or "").strip().upper(),
            "firm": str(row.get("gradingCompany") or "").strip(),
            "date": str(row.get("date") or "").strip(),
            "action": str(row.get("action") or "").strip(),
            "previous_grade": str(row.get("previousGrade") or "").strip(),
            "new_grade": str(row.get("newGrade") or "").strip(),
        }
        body = json.dumps(normalized, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(body.encode("utf-8")).hexdigest()

    @classmethod
    def parse_grades(cls, payload: list[dict[str, Any]]) -> list[AnalystRating]:
        ratings: list[AnalystRating] = []
        for row in payload:
            published_at = datetime.fromisoformat(str(row["date"]))
            if published_at.tzinfo is None:
                published_at = published_at.replace(tzinfo=timezone.utc)
            ratings.append(
                AnalystRating(
                    symbol=str(row["symbol"]).upper(),
                    firm=str(row["gradingCompany"]),
                    published_at=published_at,
                    action=row.get("action"),
                    prior_rating=row.get("previousGrade"),
                    new_rating=row.get("newGrade"),
                    provider="fmp_grades",
                    provider_record_key=cls._record_key(row),
                )
            )
        return ratings

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=8),
        reraise=True,
    )
    async def get_grades(
        self, symbol: str
    ) -> tuple[list[dict[str, Any]], list[AnalystRating]]:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(
                f"{self.base_url}/grades",
                params={"symbol": symbol.upper(), "apikey": self.api_key},
            )
            response.raise_for_status()
            payload = response.json()
        if not isinstance(payload, list):
            raise RuntimeError("FMP grades returned an unexpected response")
        return payload, self.parse_grades(payload)
