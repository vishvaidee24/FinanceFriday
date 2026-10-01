from abc import ABC, abstractmethod
from datetime import datetime
from app.models.market import StockBar

class MarketDataProvider(ABC):
    @abstractmethod
    async def get_bars(
        self,
        *,
        symbols: list[str],
        start: datetime,
        end: datetime,
        timeframe: str = "1Min",
    ) -> list[StockBar]:
        raise NotImplementedError
