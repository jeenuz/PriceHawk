from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # Database
    db_host: str = "localhost"
    db_port: int = 5432
    db_name: str = "pricehawk"
    db_user: str = "postgres"
    db_password: str = ""

    # Redis
    redis_url: str = "redis://localhost:6379"

    # API
    secret_key: str = "change-this-in-production"
    access_token_expire_minutes: int = 60

    # Scraper
    scrape_interval_minutes: int = 15
    request_delay: float = 2.0
    max_retries: int = 3

    # Alerts
    slack_webhook_url: str = ""

    class Config:
        env_file = ".env"


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()


