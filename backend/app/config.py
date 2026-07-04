"""Application configuration loaded from environment / .env file."""
from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Database
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5433/movie_scraper"
    alembic_database_url: str = (
        "postgresql+psycopg2://postgres:postgres@localhost:5433/movie_scraper"
    )

    # API
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    # Scraper safeguards
    scraper_enabled: bool = True
    scraper_min_delay_seconds: float = 2.0
    scraper_max_delay_seconds: float = 5.0
    scraper_max_concurrency: int = 2
    scraper_max_retries: int = 3
    scraper_cache_ttl_hours: int = 168
    scraper_headless: bool = True
    scraper_timeout_ms: int = 30000

    # First-run seeding (used by the docker-compose 'seeder' service). Runs
    # once when the library is empty, so `docker compose up` yields a populated
    # dashboard with no manual steps.
    seed_on_start: bool = True
    seed_charts: bool = True  # IMDb Top 250 + Most Popular (~350, with posters)
    seed_rt_limit: int = 25  # RT-enrich this many of the most popular
    seed_dataset: bool = False  # also mass-import IMDb datasets (~32k, no posters)
    seed_dataset_min_rating: float = 6.0
    seed_dataset_min_votes: int = 1000

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
