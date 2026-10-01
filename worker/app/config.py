from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "local"
    aws_region: str = "us-east-1"
    database_url: str = "postgresql://finance:finance@localhost:5432/finance"
    raw_bucket_name: str = "finance-v1-raw"

    alpaca_api_key: str | None = None
    alpaca_api_secret: str | None = None
    fmp_api_key: str | None = None

    sec_user_agent: str = "FinanceResearch/0.1 contact@example.com"

    reddit_client_id: str | None = None
    reddit_client_secret: str | None = None
    reddit_user_agent: str = "finance-platform/0.1"

    kalshi_base_url: str = "https://api.elections.kalshi.com/trade-api/v2"
    polymarket_gamma_base_url: str = "https://gamma-api.polymarket.com"

@lru_cache
def get_settings() -> Settings:
    return Settings()
