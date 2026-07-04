"""Bulk import from IMDb chart pages.

The Top 250 and Most Popular chart pages embed their full dataset in the
``script#__NEXT_DATA__`` JSON blob — title, year, poster, IMDb rating, vote
count, runtime, plot, and genres for every entry. That means one polite page
load yields hundreds of fully-populated movies, instead of scraping hundreds
of individual title pages.

Director/cast are not in the chart payload; they get filled in whenever a
movie is re-scraped individually (detail modal → Re-scrape).
"""
from __future__ import annotations

import json
import logging
from typing import Any

from app.models import RatingSource
from app.scrapers.base import BaseScraper
from app.scrapers.throttle import throttle
from app.scrapers.types import ScrapedMovie, ScrapedRating

logger = logging.getLogger(__name__)

CHARTS = {
    "top": "https://www.imdb.com/chart/top/",  # IMDb Top 250
    "popular": "https://www.imdb.com/chart/moviemeter/",  # Most Popular (100)
}

TITLE_URL = "https://www.imdb.com/title/{tconst}/"


def _find_edges(obj: Any) -> list[dict] | None:
    """Locate the chart's ``edges`` list wherever it sits in the page JSON."""
    if isinstance(obj, dict):
        edges = obj.get("edges")
        if isinstance(edges, list) and edges and "node" in edges[0]:
            return edges
        for value in obj.values():
            found = _find_edges(value)
            if found:
                return found
    return None


def _parse_node(node: dict) -> ScrapedMovie | None:
    tconst = node.get("id")
    title = (node.get("titleText") or {}).get("text")
    if not tconst or not title:
        return None

    year = (node.get("releaseYear") or {}).get("year")

    runtime_minutes = None
    runtime_s = (node.get("runtime") or {}).get("seconds")
    if runtime_s:
        runtime_minutes = round(runtime_s / 60)

    poster = (node.get("primaryImage") or {}).get("url")
    plot = (((node.get("plot") or {}).get("plotText")) or {}).get("plainText")

    genres = [
        g["genre"]["text"]
        for g in ((node.get("titleGenres") or {}).get("genres") or [])
        if g.get("genre", {}).get("text")
    ]

    ratings: list[ScrapedRating] = []
    popularity = None
    summary = node.get("ratingsSummary") or {}
    if summary.get("aggregateRating") is not None:
        votes = summary.get("voteCount")
        ratings.append(
            ScrapedRating(
                source=RatingSource.imdb,
                score=float(summary["aggregateRating"]),
                scale=10,
                votes=int(votes) if votes is not None else None,
                url=TITLE_URL.format(tconst=tconst),
            )
        )
        popularity = float(votes) if votes is not None else None

    return ScrapedMovie(
        title=title,
        year=year,
        imdb_id=tconst,
        plot=plot,
        runtime_minutes=runtime_minutes,
        poster_url=poster,
        genres=genres,
        popularity=popularity,
        imdb_url=TITLE_URL.format(tconst=tconst),
        ratings=ratings,
    )


class IMDbChartScraper(BaseScraper):
    name = "imdb_charts"

    async def fetch(self, query: str, **kwargs: object) -> ScrapedMovie | None:
        raise NotImplementedError("Use fetch_chart() for bulk imports")

    async def fetch_chart(self, chart: str) -> list[ScrapedMovie]:
        """Fetch every movie on a chart page ('top' or 'popular')."""
        url = CHARTS[chart]
        async with throttle:
            async with self.browser.page() as page:
                await page.goto(url, wait_until="domcontentloaded")
                # Wait for the full document (the JSON blob can still be
                # streaming right after domcontentloaded — reading it early
                # yields truncated JSON).
                await page.wait_for_load_state("load")
                await page.wait_for_selector(
                    "script#__NEXT_DATA__", state="attached", timeout=15000
                )
                raw = await page.evaluate(
                    "() => document.getElementById('__NEXT_DATA__').textContent"
                )

        data = json.loads(raw)  # raises on truncation -> retried by caller
        edges = _find_edges(data.get("props", {}).get("pageProps", {}))
        if not edges:
            logger.warning("[imdb_charts] no edges found on %s", url)
            return []

        movies = []
        for edge in edges:
            movie = _parse_node(edge.get("node") or {})
            if movie is not None:
                movies.append(movie)
        logger.info("[imdb_charts] %s: parsed %d movies", chart, len(movies))
        return movies

    async def fetch_chart_with_retry(self, chart: str) -> list[ScrapedMovie]:
        """Chart fetch with the same backoff policy as single scrapes."""
        from tenacity import retry, stop_after_attempt, wait_exponential

        from app.config import settings

        @retry(
            stop=stop_after_attempt(settings.scraper_max_retries),
            wait=wait_exponential(multiplier=1, min=1, max=10),
            reraise=True,
        )
        async def _run() -> list[ScrapedMovie]:
            return await self.fetch_chart(chart)

        try:
            return await _run()
        except Exception:  # noqa: BLE001
            logger.exception("[imdb_charts] failed to fetch %r after retries", chart)
            return []
