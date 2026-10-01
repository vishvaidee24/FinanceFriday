from datetime import datetime
from decimal import Decimal
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential
from app.config import get_settings
from app.models.market import StockBar
from app.providers.base import MarketDataProvider

class AlpacaMarketDataProvider(MarketDataProvider):
    base_url = "https://data.alpaca.markets"

    def __init__(self) -> None:
        settings = get_settings()
        if not settings.alpaca_api_key or not settings.alpaca_api_secret:
            raise RuntimeError("ALPACA_API_KEY and ALPACA_API_SECRET are required.")
        self.headers = {
            "APCA-API-KEY-ID": settings.alpaca_api_key,
            "APCA-API-SECRET-KEY": settings.alpaca_api_secret,
        }

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        reraise=True,
    )
    async def get_bars(
        self,
        *,
        symbols: list[str],
        start: datetime,
        end: datetime,
        timeframe: str = "1Min",
    ) -> list[StockBar]:
        params: dict[str, str | int] = {
            "symbols": ",".join(symbols),
            "timeframe": timeframe,
            "start": start.isoformat(),
            "end": end.isoformat(),
            "adjustment": "raw",
            "feed": "iex",
            "limit": 10000,
        }

        async with httpx.AsyncClient(
            base_url=self.base_url,
            headers=self.headers,
            timeout=30,
        ) as client:
            result: list[StockBar] = []
            while True:
                response = await client.get("/v2/stocks/bars", params=params)
                response.raise_for_status()
                payload = response.json()

                for symbol, bars in payload.get("bars", {}).items():
                    for item in bars:
                        result.append(
                            StockBar(
                                symbol=symbol,
                                timestamp=item["t"],
                                open=Decimal(str(item["o"])),
                                high=Decimal(str(item["h"])),
                                low=Decimal(str(item["l"])),
                                close=Decimal(str(item["c"])),
                                volume=int(item["v"]),
                                trade_count=item.get("n"),
                                vwap=(
                                    Decimal(str(item["vw"]))
                                    if item.get("vw") is not None
                                    else None
                                ),
                            )
                        )

                next_page_token = payload.get("next_page_token")
                if not next_page_token:
                    break
                params["page_token"] = next_page_token

        return result
