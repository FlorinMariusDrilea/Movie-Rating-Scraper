"""Politeness controls shared by all scrapers.

Combines a global concurrency limit with a randomized per-request delay so we
never hammer a site. Used as an async context manager around each page load.
"""
from __future__ import annotations

import asyncio
import logging
import random

from app.config import settings

logger = logging.getLogger(__name__)

# Realistic desktop user agents, rotated per page to look less bot-like.
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
]


def random_user_agent() -> str:
    return random.choice(USER_AGENTS)


class Throttle:
    """Global concurrency + randomized delay gate."""

    def __init__(self) -> None:
        self._semaphore = asyncio.Semaphore(settings.scraper_max_concurrency)

    async def __aenter__(self) -> "Throttle":
        await self._semaphore.acquire()
        delay = random.uniform(
            settings.scraper_min_delay_seconds,
            settings.scraper_max_delay_seconds,
        )
        logger.debug("Throttle: sleeping %.2fs before request", delay)
        await asyncio.sleep(delay)
        return self

    async def __aexit__(self, *exc: object) -> None:
        self._semaphore.release()


# Shared instance used across scrapers within a process.
throttle = Throttle()
