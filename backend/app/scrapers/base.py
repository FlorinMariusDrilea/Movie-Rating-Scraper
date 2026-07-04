"""Common scraper interface.

Every rating source implements ``fetch(query)`` and returns a partial
``ScrapedMovie`` (or ``None`` if nothing was found). The service layer merges
the partial results from each source into a single movie record.
"""
from __future__ import annotations

import abc
import logging

from playwright.async_api import Error as PlaywrightError
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.config import settings
from app.scrapers.browser import BrowserManager
from app.scrapers.types import ScrapedMovie

logger = logging.getLogger(__name__)


class BaseScraper(abc.ABC):
    #: Human-readable source name, e.g. "imdb" / "rotten_tomatoes".
    name: str = "base"

    def __init__(self, browser: BrowserManager) -> None:
        self.browser = browser

    @abc.abstractmethod
    async def fetch(self, query: str, **kwargs: object) -> ScrapedMovie | None:
        """Search for ``query`` and return whatever this source knows."""

    async def fetch_with_retry(
        self, query: str, **kwargs: object
    ) -> ScrapedMovie | None:
        """``fetch`` wrapped with exponential-backoff retries.

        Retries only transient browser/navigation errors; a clean "not found"
        (``None``) is returned immediately without retrying.
        """

        @retry(
            stop=stop_after_attempt(settings.scraper_max_retries),
            wait=wait_exponential(multiplier=1, min=1, max=10),
            retry=retry_if_exception_type((PlaywrightError, TimeoutError)),
            reraise=True,
        )
        async def _run() -> ScrapedMovie | None:
            return await self.fetch(query, **kwargs)

        try:
            return await _run()
        except Exception:  # noqa: BLE001 - log and degrade gracefully
            logger.exception("[%s] failed to scrape %r after retries", self.name, query)
            return None
