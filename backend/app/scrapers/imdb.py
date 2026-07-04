"""IMDb scraper.

Strategy (most stable first):
1. Resolve the query to an IMDb id (tconst) via IMDb's public suggestion JSON
   endpoint — far more stable than scraping the search results page.
2. Load the title page and parse its ``application/ld+json`` block, which IMDb
   has kept structurally stable for years (name, genres, aggregateRating,
   director, cast, description, poster, duration).
"""
from __future__ import annotations

import json
import logging
import re
from typing import Any
from urllib.parse import quote

import httpx

from app.scrapers.base import BaseScraper
from app.scrapers.throttle import random_user_agent, throttle
from app.scrapers.types import ScrapedMovie, ScrapedRating
from app.models import RatingSource

logger = logging.getLogger(__name__)

SUGGESTION_URL = "https://v3.sg.media-imdb.com/suggestion/x/{query}.json?includeVideos=0"
TITLE_URL = "https://www.imdb.com/title/{tconst}/"

# Suggestion entry types (the endpoint's "qid" vocabulary) that count as a
# scrapeable film/series. Note this differs from IMDb's search "titletype".
_TITLE_TYPES = {
    "movie",
    "tvSeries",
    "tvMovie",
    "tvMiniSeries",
    "tvSpecial",
    "short",
    "video",
}

_DURATION_RE = re.compile(r"PT(?:(\d+)H)?(?:(\d+)M)?")


def _parse_duration(iso: str | None) -> int | None:
    """Parse an ISO-8601 duration like 'PT2H22M' into total minutes."""
    if not iso:
        return None
    m = _DURATION_RE.fullmatch(iso.strip())
    if not m:
        return None
    hours = int(m.group(1) or 0)
    minutes = int(m.group(2) or 0)
    total = hours * 60 + minutes
    return total or None


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


class IMDbScraper(BaseScraper):
    name = "imdb"

    async def _resolve_tconst(self, query: str) -> tuple[str, str, int | None] | None:
        """Return (tconst, title, year) for the best matching title, or None."""
        url = SUGGESTION_URL.format(query=quote(query.strip()))
        headers = {
            "User-Agent": random_user_agent(),
            "Referer": "https://www.imdb.com/",
            "Accept": "application/json",
        }
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(url, headers=headers)
            resp.raise_for_status()
            data = resp.json()

        for entry in data.get("d", []):
            tconst = entry.get("id", "")
            if not tconst.startswith("tt"):
                continue
            if entry.get("qid") and entry["qid"] not in _TITLE_TYPES:
                continue
            return tconst, entry.get("l", query), entry.get("y")
        return None

    def _parse_ld_json(self, raw: str, tconst: str) -> ScrapedMovie | None:
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            logger.warning("[imdb] could not parse JSON-LD for %s", tconst)
            return None

        title = data.get("name")
        if not title:
            return None

        # Year from datePublished (YYYY-...) when present.
        year = None
        date_published = data.get("datePublished")
        if date_published and len(date_published) >= 4 and date_published[:4].isdigit():
            year = int(date_published[:4])

        director = None
        directors = _as_list(data.get("director"))
        if directors:
            director = directors[0].get("name") if isinstance(directors[0], dict) else None

        cast = [
            a.get("name")
            for a in _as_list(data.get("actor"))
            if isinstance(a, dict) and a.get("name")
        ]

        genres = [g for g in _as_list(data.get("genre")) if isinstance(g, str)]

        poster = data.get("image")
        if isinstance(poster, dict):
            poster = poster.get("url")

        ratings: list[ScrapedRating] = []
        popularity = None
        agg = data.get("aggregateRating")
        if isinstance(agg, dict) and agg.get("ratingValue") is not None:
            votes = agg.get("ratingCount")
            ratings.append(
                ScrapedRating(
                    source=RatingSource.imdb,
                    score=float(agg["ratingValue"]),
                    scale=10,
                    votes=int(votes) if votes is not None else None,
                    url=TITLE_URL.format(tconst=tconst),
                )
            )
            # Use IMDb vote count as a popularity proxy for sorting.
            popularity = float(votes) if votes is not None else None

        return ScrapedMovie(
            title=title,
            year=year,
            imdb_id=tconst,
            plot=data.get("description"),
            runtime_minutes=_parse_duration(data.get("duration")),
            poster_url=poster,
            director=director,
            cast_members=cast,
            genres=genres,
            popularity=popularity,
            imdb_url=TITLE_URL.format(tconst=tconst),
            ratings=ratings,
        )

    async def fetch_by_tconst(self, tconst: str) -> ScrapedMovie | None:
        """Scrape a title page directly by its IMDb id (no suggestion lookup).

        Used by the metadata backfill, which already knows each movie's tconst
        and just needs the richer fields (poster, plot, cast, director).
        """
        url = TITLE_URL.format(tconst=tconst)
        async with throttle:
            async with self.browser.page() as page:
                await page.goto(url, wait_until="domcontentloaded")
                locator = page.locator('script[type="application/ld+json"]').first
                raw = await locator.text_content()

        if not raw:
            logger.warning("[imdb] no JSON-LD on %s", url)
            return None
        return self._parse_ld_json(raw, tconst)

    async def fetch(self, query: str, **kwargs: object) -> ScrapedMovie | None:
        resolved = await self._resolve_tconst(query)
        if resolved is None:
            logger.info("[imdb] no suggestion match for %r", query)
            return None
        tconst, sug_title, sug_year = resolved
        url = TITLE_URL.format(tconst=tconst)

        movie = await self.fetch_by_tconst(tconst)
        if movie is None:
            logger.warning("[imdb] no JSON-LD on %s; using suggestion data", url)
            return ScrapedMovie(
                title=sug_title, year=sug_year, imdb_id=tconst, imdb_url=url
            )
        # Prefer suggestion year if JSON-LD lacked one.
        if movie.year is None:
            movie.year = sug_year
        return movie
