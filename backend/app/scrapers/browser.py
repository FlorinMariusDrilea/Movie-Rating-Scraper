"""Playwright browser lifecycle management.

A single Chromium instance is launched lazily and reused; each scrape gets its
own browser context (fresh cookies + a rotated user agent). Use as::

    async with BrowserManager() as bm:
        async with bm.page() as page:
            await page.goto(url)
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

from playwright.async_api import Browser, Page, async_playwright

from app.config import settings
from app.scrapers.throttle import random_user_agent

logger = logging.getLogger(__name__)


class BrowserManager:
    def __init__(self) -> None:
        self._pw = None
        self._browser: Browser | None = None

    async def __aenter__(self) -> "BrowserManager":
        self._pw = await async_playwright().start()
        self._browser = await self._pw.chromium.launch(
            headless=settings.scraper_headless,
            args=["--disable-blink-features=AutomationControlled"],
        )
        logger.debug("Chromium launched (headless=%s)", settings.scraper_headless)
        return self

    async def __aexit__(self, *exc: object) -> None:
        if self._browser is not None:
            await self._browser.close()
        if self._pw is not None:
            await self._pw.stop()

    @asynccontextmanager
    async def page(self) -> AsyncIterator[Page]:
        if self._browser is None:
            raise RuntimeError("BrowserManager must be entered before use")
        context = await self._browser.new_context(
            user_agent=random_user_agent(),
            locale="en-US",
            viewport={"width": 1366, "height": 768},
        )
        context.set_default_timeout(settings.scraper_timeout_ms)
        page = await context.new_page()
        try:
            yield page
        finally:
            await context.close()
