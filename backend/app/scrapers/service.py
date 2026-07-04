"""Scraper orchestration + persistence.

Ties the per-source scrapers together, applies the cache-TTL policy, and upserts
results into the database. This is the single entry point the API and the CLI
use.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, not_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import Genre, Movie, Rating, RatingSource
from app.scrapers.browser import BrowserManager
from app.scrapers.imdb import IMDbScraper
from app.scrapers.imdb_charts import IMDbChartScraper
from app.scrapers.rt import RottenTomatoesScraper
from app.scrapers.types import ScrapedMovie

logger = logging.getLogger(__name__)

# Caps how many API-triggered scrapes launch a browser at once, server-wide.
# Without this, a burst of /search or /scrape requests would spawn one Chromium
# each and exhaust memory. Lazily created so it binds to the running loop.
_scrape_gate: asyncio.Semaphore | None = None


def _get_scrape_gate() -> asyncio.Semaphore:
    global _scrape_gate
    if _scrape_gate is None:
        _scrape_gate = asyncio.Semaphore(settings.scraper_max_concurrency)
    return _scrape_gate


class ScraperService:
    async def scrape(self, query: str) -> ScrapedMovie | None:
        """Run every source for ``query`` and merge into one ScrapedMovie.

        IMDb is the base (it resolves the canonical id/year); Rotten Tomatoes is
        matched using IMDb's year and merged in.
        """
        if not settings.scraper_enabled:
            logger.warning("Scraping is disabled (SCRAPER_ENABLED=false)")
            return None

        async with _get_scrape_gate():
            async with BrowserManager() as browser:
                imdb = IMDbScraper(browser)
                rt = RottenTomatoesScraper(browser)

                base = await imdb.fetch_with_retry(query)
                # Search RT with IMDb's canonical title/year for a better match.
                rt_query = base.title if base and base.title else query
                year = base.year if base else None
                title = base.title if base else None
                rt_result = await rt.fetch_with_retry(
                    rt_query, year=year, title=title
                )

        if base is None:
            return rt_result
        if rt_result is not None:
            base.merge(rt_result)
        return base

    async def bulk_import(
        self,
        db: AsyncSession,
        charts: list[str] | None = None,
        rt_limit: int = 0,
    ) -> dict[str, int]:
        """Import every movie from the given IMDb charts in a few page loads.

        ``rt_limit`` > 0 additionally enriches that many movies (most popular
        first, skipping ones that already have RT scores) with Rotten Tomatoes
        ratings — each enrich is a throttled RT search + page load, so keep it
        bounded.
        """
        if not settings.scraper_enabled:
            logger.warning("Scraping is disabled (SCRAPER_ENABLED=false)")
            return {"imported": 0, "rt_enriched": 0}

        charts = charts or ["top", "popular"]
        stats = {"imported": 0, "rt_enriched": 0}

        async with BrowserManager() as browser:
            chart_scraper = IMDbChartScraper(browser)

            # Dedupe across charts by imdb_id (top and popular overlap).
            by_id: dict[str, ScrapedMovie] = {}
            for chart in charts:
                for movie in await chart_scraper.fetch_chart_with_retry(chart):
                    if movie.imdb_id and movie.imdb_id not in by_id:
                        by_id[movie.imdb_id] = movie

            logger.info("[bulk] importing %d unique movies", len(by_id))
            for movie in by_id.values():
                await self._upsert(db, movie)
                stats["imported"] += 1

            if rt_limit > 0:
                rt = RottenTomatoesScraper(browser)
                candidates = sorted(
                    by_id.values(), key=lambda m: m.popularity or 0, reverse=True
                )
                for scraped in candidates:
                    if stats["rt_enriched"] >= rt_limit:
                        break
                    stored = (
                        await db.execute(
                            select(Movie).where(Movie.imdb_id == scraped.imdb_id)
                        )
                    ).scalar_one_or_none()
                    if stored is None:
                        continue
                    if any(
                        r.source != RatingSource.imdb for r in stored.ratings
                    ):
                        continue  # already has RT data
                    rt_result = await rt.fetch_with_retry(
                        scraped.title, year=scraped.year, title=scraped.title
                    )
                    if rt_result is None or not rt_result.ratings:
                        logger.info("[bulk] no RT match for %r", scraped.title)
                        continue
                    scraped.merge(rt_result)
                    await self._upsert(db, scraped)
                    stats["rt_enriched"] += 1
                    logger.info(
                        "[bulk] RT enriched %s (%d/%d)",
                        scraped.title,
                        stats["rt_enriched"],
                        rt_limit,
                    )

        return stats

    async def enrich_metadata(
        self, db: AsyncSession, limit: int = 100
    ) -> dict[str, int]:
        """Backfill posters + plot/cast/director for dataset-only movies.

        Targets movies with an ``imdb_id``, no poster, and no prior scrape
        (``last_scraped_at IS NULL``) — most popular first. Each is scraped
        directly by its IMDb id; ``_upsert`` fills the empty fields and stamps
        ``last_scraped_at``, so re-runs make forward progress and never retry a
        title whose IMDb page genuinely lacks a poster.
        """
        if not settings.scraper_enabled:
            logger.warning("Scraping is disabled (SCRAPER_ENABLED=false)")
            return {"attempted": 0, "enriched": 0}

        stmt = (
            select(Movie)
            .where(
                Movie.imdb_id.is_not(None),
                Movie.poster_url.is_(None),
                Movie.last_scraped_at.is_(None),
            )
            .order_by(Movie.popularity.desc().nulls_last())
            .limit(limit)
        )
        candidates = list((await db.execute(stmt)).scalars())
        logger.info("[meta-backfill] %d candidates", len(candidates))

        stats = {"attempted": 0, "enriched": 0}
        if not candidates:
            return stats

        async with BrowserManager() as browser:
            imdb = IMDbScraper(browser)
            for movie in candidates:
                tconst = movie.imdb_id
                scraped = None
                try:
                    scraped = await imdb.fetch_by_tconst(tconst)
                except Exception:  # noqa: BLE001 - keep the batch going
                    logger.exception("[meta-backfill] %s failed", tconst)

                stats["attempted"] += 1
                if scraped is None:
                    # Stamp it so we don't retry a page with no usable data.
                    movie.last_scraped_at = datetime.now(timezone.utc)
                    await db.commit()
                    logger.info("[meta-backfill] %s -> no data", movie.title)
                    continue

                await self._upsert(db, scraped)  # fills gaps, commits, stamps
                if scraped.poster_url:
                    stats["enriched"] += 1
                    logger.info(
                        "[meta-backfill] %s -> poster (%d/%d)",
                        movie.title,
                        stats["enriched"],
                        stats["attempted"],
                    )
                else:
                    logger.info("[meta-backfill] %s -> no poster on IMDb", movie.title)

        return stats

    async def enrich_rt(
        self, db: AsyncSession, limit: int = 100
    ) -> dict[str, int]:
        """Backfill Rotten Tomatoes scores for IMDb-only movies.

        Targets movies that have an IMDb rating, no RT ratings, and have never
        been RT-checked — most popular first. Every attempt stamps
        ``rt_checked_at`` (match or not) so re-runs make forward progress
        instead of re-scraping titles that aren't on RT.
        """
        if not settings.scraper_enabled:
            logger.warning("Scraping is disabled (SCRAPER_ENABLED=false)")
            return {"attempted": 0, "enriched": 0}

        rt_sources = (RatingSource.rt_tomatometer, RatingSource.rt_audience)
        stmt = (
            select(Movie)
            .where(
                Movie.rt_checked_at.is_(None),
                Movie.ratings.any(Rating.source == RatingSource.imdb),
                not_(Movie.ratings.any(Rating.source.in_(rt_sources))),
            )
            .order_by(Movie.popularity.desc().nulls_last())
            .limit(limit)
        )
        candidates = list((await db.execute(stmt)).scalars())
        logger.info("[rt-backfill] %d candidates", len(candidates))

        stats = {"attempted": 0, "enriched": 0}
        if not candidates:
            return stats

        async with BrowserManager() as browser:
            rt = RottenTomatoesScraper(browser)
            for movie in candidates:
                result = await rt.fetch_with_retry(
                    movie.title, year=movie.year, title=movie.title
                )
                movie.rt_checked_at = datetime.now(timezone.utc)
                stats["attempted"] += 1

                if result and result.ratings:
                    for sr in result.ratings:
                        movie.ratings.append(
                            Rating(
                                source=sr.source,
                                score=sr.score,
                                scale=sr.scale,
                                votes=sr.votes,
                                url=sr.url,
                            )
                        )
                    if result.rt_url and not movie.rt_url:
                        movie.rt_url = result.rt_url
                    stats["enriched"] += 1
                    logger.info(
                        "[rt-backfill] %s -> RT found (%d/%d enriched)",
                        movie.title,
                        stats["enriched"],
                        stats["attempted"],
                    )
                else:
                    logger.info("[rt-backfill] %s -> no RT match", movie.title)

                # Commit per movie so a long run is resumable if interrupted.
                await db.commit()

        return stats

    async def get_or_scrape(
        self, db: AsyncSession, query: str, force: bool = False
    ) -> tuple[Movie | None, str]:
        """Return a stored Movie, scraping only when needed.

        Returns ``(movie, source)`` where source is 'cache', 'scraped', or
        'not_found'.
        """
        if not force:
            cached = await self._find_fresh(db, query)
            if cached is not None:
                logger.info("[cache hit] %r -> movie %s", query, cached.id)
                return cached, "cache"

        scraped = await self.scrape(query)
        if scraped is None:
            return None, "not_found"

        movie = await self._upsert(db, scraped)
        return movie, "scraped"

    async def _find_fresh(self, db: AsyncSession, query: str) -> Movie | None:
        """Find a movie whose title matches the query and is within the TTL."""
        cutoff = datetime.now(timezone.utc) - timedelta(
            hours=settings.scraper_cache_ttl_hours
        )
        stmt = (
            select(Movie)
            .where(
                func.lower(Movie.title) == query.strip().lower(),
                Movie.last_scraped_at.is_not(None),
                Movie.last_scraped_at >= cutoff,
            )
            .limit(1)
        )
        return (await db.execute(stmt)).scalar_one_or_none()

    async def _get_or_create_genres(
        self, db: AsyncSession, names: list[str]
    ) -> list[Genre]:
        if not names:
            return []
        # De-dupe case-insensitively.
        wanted = {n.strip(): n.strip() for n in names if n.strip()}
        existing = (
            await db.execute(
                select(Genre).where(Genre.name.in_(list(wanted.values())))
            )
        ).scalars().all()
        by_name = {g.name.lower(): g for g in existing}

        result: list[Genre] = []
        for name in wanted.values():
            genre = by_name.get(name.lower())
            if genre is None:
                genre = Genre(name=name)
                db.add(genre)
                by_name[name.lower()] = genre
            result.append(genre)
        return result

    async def _upsert(self, db: AsyncSession, scraped: ScrapedMovie) -> Movie:
        movie: Movie | None = None
        if scraped.imdb_id:
            movie = (
                await db.execute(
                    select(Movie).where(Movie.imdb_id == scraped.imdb_id)
                )
            ).scalar_one_or_none()
        if movie is None:
            movie = (
                await db.execute(
                    select(Movie).where(
                        func.lower(Movie.title) == scraped.title.lower(),
                        Movie.year == scraped.year,
                    )
                )
            ).scalar_one_or_none()
        if movie is None:
            movie = Movie(title=scraped.title)
            db.add(movie)

        # Update scalar fields, preferring freshly-scraped non-empty values.
        movie.title = scraped.title or movie.title
        movie.year = scraped.year or movie.year
        movie.imdb_id = scraped.imdb_id or movie.imdb_id
        movie.plot = scraped.plot or movie.plot
        movie.runtime_minutes = scraped.runtime_minutes or movie.runtime_minutes
        movie.poster_url = scraped.poster_url or movie.poster_url
        movie.director = scraped.director or movie.director
        movie.cast_members = scraped.cast_members or movie.cast_members
        movie.popularity = scraped.popularity or movie.popularity
        movie.imdb_url = scraped.imdb_url or movie.imdb_url
        movie.rt_url = scraped.rt_url or movie.rt_url

        if scraped.genres:
            movie.genres = await self._get_or_create_genres(db, scraped.genres)

        # Upsert ratings keyed by source.
        now = datetime.now(timezone.utc)
        by_source = {r.source: r for r in movie.ratings}
        for sr in scraped.ratings:
            existing = by_source.get(sr.source)
            if existing is not None:
                existing.score = sr.score
                existing.scale = sr.scale
                existing.votes = sr.votes
                existing.url = sr.url
                existing.scraped_at = now
            else:
                movie.ratings.append(
                    Rating(
                        source=sr.source,
                        score=sr.score,
                        scale=sr.scale,
                        votes=sr.votes,
                        url=sr.url,
                    )
                )

        movie.last_scraped_at = now
        await db.commit()
        await db.refresh(movie)
        return movie


scraper_service = ScraperService()
