"""Rotten Tomatoes scraper.

RT is heavily client-rendered, so this uses Playwright throughout. The reliable
data sources on a movie page are:

* ``<script type="application/ld+json">`` — title, genres, plot, poster, cast.
* ``<script id="media-scorecard-json">`` — a JSON blob with ``criticsScore`` and
  ``audienceScore`` (score + review counts). This is far more stable than the
  rendered score widgets, which RT restyles frequently.

The search page (``search-page-media-row``) no longer exposes scores as
attributes, so we match the result row by title and read scores from the movie
page.
"""
from __future__ import annotations

import logging
import re

from app.models import RatingSource
from app.scrapers.base import BaseScraper
from app.scrapers.throttle import throttle
from app.scrapers.types import ScrapedMovie, ScrapedRating

logger = logging.getLogger(__name__)

SEARCH_URL = "https://www.rottentomatoes.com/search?search={query}"
BASE = "https://www.rottentomatoes.com"

# Read all search result rows (title + link; scores no longer in attributes).
_SEARCH_JS = """
() => {
  const rows = [...document.querySelectorAll('search-page-media-row')];
  return rows.map(r => {
    const link = r.querySelector('a[data-qa="info-name"], a[slot="title"]');
    return {
      year: r.getAttribute('releaseyear') || null,
      href: link ? link.getAttribute('href') : null,
      title: link ? link.textContent.trim() : null,
    };
  }).filter(x => x.href && x.href.includes('/m/'));
}
"""

# Movie-page extraction: JSON-LD metadata + scorecard JSON scores.
_MOVIE_JS = r"""
() => {
  const out = {title:null, genres:[], description:null, image:null, director:null,
               cast:[], year:null, critics:null, audience:null,
               criticsVotes:null, audienceVotes:null};

  const toInt = (v) => { if (v == null) return null;
    const m = String(v).match(/\d{1,3}/); return m ? parseInt(m[0], 10) : null; };
  const toCount = (v) => { if (v == null) return null;
    const n = parseInt(String(v).replace(/[^\d]/g, ''), 10); return isNaN(n) ? null : n; };

  for (const s of document.querySelectorAll('script[type="application/ld+json"]')) {
    try {
      const items = [].concat(JSON.parse(s.textContent));
      for (const o of items) {
        const t = String(o['@type'] || '');
        if (!(t.includes('Movie') || o.genre || o.aggregateRating)) continue;
        if (o.name) out.title = o.name;
        if (o.genre) out.genres = [].concat(o.genre).filter(g => typeof g === 'string');
        if (o.description) out.description = o.description;
        if (o.image) out.image = typeof o.image === 'string' ? o.image : (o.image.url || null);
        if (o.director) out.director = Array.isArray(o.director)
            ? (o.director[0] && o.director[0].name) : (o.director.name || null);
        if (o.actor) out.cast = [].concat(o.actor).map(a => a && a.name).filter(Boolean);
        const d = o.dateCreated || o.datePublished;
        if (d) { const m = String(d).match(/(19|20)\d{2}/); if (m) out.year = parseInt(m[0], 10); }
      }
    } catch (e) { /* ignore malformed blocks */ }
  }

  const scEl = document.getElementById('media-scorecard-json');
  if (scEl) {
    try {
      const sc = JSON.parse(scEl.textContent);
      if (sc.criticsScore) {
        out.critics = toInt(sc.criticsScore.score);
        out.criticsVotes = toCount(sc.criticsScore.reviewCount);
      }
      if (sc.audienceScore) {
        out.audience = toInt(sc.audienceScore.score);
        out.audienceVotes = toCount(sc.audienceScore.reviewCount
            || sc.audienceScore.ratingCount || sc.audienceScore.bandedRatingCount);
      }
    } catch (e) { /* ignore */ }
  }

  if (out.year === null) {
    const h = document.getElementById('media-hero-json');
    if (h) { try {
      const hj = JSON.parse(h.textContent);
      const m = String(hj.releaseYear || hj.year || '').match(/(19|20)\d{2}/);
      if (m) out.year = parseInt(m[0], 10);
    } catch (e) {} }
  }
  return out;
}
"""

_YEAR_RE = re.compile(r"(19|20)\d{2}")


class RottenTomatoesScraper(BaseScraper):
    name = "rotten_tomatoes"

    async def _search(
        self, page, query: str, year: int | None, title: str | None
    ) -> dict | None:
        await page.goto(
            SEARCH_URL.format(query=query.replace(" ", "%20")),
            wait_until="domcontentloaded",
        )
        try:
            await page.wait_for_selector("search-page-media-row", timeout=10000)
        except Exception:  # noqa: BLE001 - no results element appeared
            logger.info("[rt] no search rows for %r", query)
            return None

        rows = await page.evaluate(_SEARCH_JS)
        if not rows:
            return None

        # Prefer an exact title match, then a year match, else the top result.
        if title:
            target = title.strip().lower()
            for row in rows:
                if row.get("title") and row["title"].strip().lower() == target:
                    return row
        if year is not None:
            for row in rows:
                if row.get("year") and str(year) in row["year"]:
                    return row
        return rows[0]

    def _build_movie(self, page_data: dict, movie_url: str) -> ScrapedMovie:
        ratings: list[ScrapedRating] = []
        if page_data.get("critics") is not None:
            ratings.append(
                ScrapedRating(
                    RatingSource.rt_tomatometer,
                    float(page_data["critics"]),
                    100,
                    votes=page_data.get("criticsVotes"),
                    url=movie_url,
                )
            )
        if page_data.get("audience") is not None:
            ratings.append(
                ScrapedRating(
                    RatingSource.rt_audience,
                    float(page_data["audience"]),
                    100,
                    votes=page_data.get("audienceVotes"),
                    url=movie_url,
                )
            )

        return ScrapedMovie(
            title=page_data.get("title") or "Unknown",
            year=page_data.get("year"),
            plot=page_data.get("description"),
            poster_url=page_data.get("image"),
            director=page_data.get("director"),
            cast_members=page_data.get("cast") or [],
            genres=page_data.get("genres") or [],
            rt_url=movie_url,
            ratings=ratings,
        )

    async def fetch(
        self,
        query: str,
        year: int | None = None,
        title: str | None = None,
        **kwargs: object,
    ) -> ScrapedMovie | None:
        async with throttle:
            async with self.browser.page() as page:
                row = await self._search(page, query, year, title)
                if row is None:
                    return None
                href = row["href"]
                movie_url = href if href.startswith("http") else f"{BASE}{href}"

                await page.goto(movie_url, wait_until="domcontentloaded")
                try:
                    await page.wait_for_selector(
                        'script#media-scorecard-json, script[type="application/ld+json"]',
                        timeout=10000,
                    )
                except Exception:  # noqa: BLE001
                    pass
                page_data = await page.evaluate(_MOVIE_JS)

        return self._build_movie(page_data, movie_url)
