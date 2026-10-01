from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel


class AnalystRating(BaseModel):
    symbol: str
    firm: str
    analyst_name: str | None = None
    published_at: datetime
    action: str | None = None
    prior_rating: str | None = None
    new_rating: str | None = None
    prior_price_target: Decimal | None = None
    new_price_target: Decimal | None = None
    source_url: str | None = None
    provider: str
    provider_record_key: str
