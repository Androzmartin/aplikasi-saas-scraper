"""Application settings loaded from environment / .env file."""
from functools import lru_cache
from typing import List

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    app_name: str = "UMKM Scraper SaaS"
    environment: str = "development"
    api_prefix: str = "/api"

    jwt_secret: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 720

    mongo_uri: str = "mongodb://localhost:27017"
    mongo_db: str = "umkm_scraper"

    cors_origins: List[str] = Field(
        default_factory=lambda: ["http://localhost:5173", "http://127.0.0.1:5173"]
    )

    storage_dir: str = "./storage"

    scraper_user_agent: str = "UMKMScraperBot/1.0 (+https://example.com/bot)"
    scraper_timeout_seconds: float = 20.0
    scraper_max_pages_per_site: int = 6
    scraper_delay_seconds: float = 1.0
    scraper_worker_concurrency: int = 3
    scraper_max_retries: int = 2
    scraper_respect_robots: bool = True

    default_monthly_job_quota: int = 500

    # Screenshots need Playwright plus a browser binary, so they stay opt-in.
    screenshot_enabled: bool = False
    screenshot_on_scrape: bool = False
    screenshot_timeout_seconds: float = 30.0
    screenshot_full_page: bool = False
    screenshot_browser_path: str = ""

    # When true, a redesign must be approved by an internal admin before the
    # tenant can download its index.html.
    require_redesign_approval: bool = False

    bootstrap_admin_email: str = "admin@example.com"
    bootstrap_admin_password: str = ""
    bootstrap_admin_name: str = "Internal Admin"

    ai_enabled: bool = False
    ai_provider: str = "anthropic"
    ai_api_key: str = ""
    ai_model: str = "claude-sonnet-5"

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_origins(cls, value):
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    @property
    def is_production(self) -> bool:
        return self.environment.lower() in {"production", "prod"}


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
