import httpx
from app.config import get_settings

class PolymarketProvider:
    def __init__(self) -> None:
        self.base_url = get_settings().polymarket_gamma_base_url

    async def get_markets(self, limit: int = 100) -> list[dict]:
        async with httpx.AsyncClient(base_url=self.base_url, timeout=30) as client:
            response = await client.get("/markets", params={"limit": limit})
            response.raise_for_status()
            return response.json()
