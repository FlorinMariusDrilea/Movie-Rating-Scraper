"""First-run library seeding for the Docker/compose stack.

Idempotent: if the database already contains movies, it does nothing. Only when
the library is empty does it populate — so `docker compose up` gives a
ready-to-use dashboard, and re-running the stack won't re-import.

Driven by ``SEED_*`` settings (see config.py):

* ``SEED_ON_START``  — master on/off (default true)
* ``SEED_CHARTS``    — import IMDb Top 250 + Most Popular (~350, with posters)
* ``SEED_RT_LIMIT``  — RT-enrich this many of the most popular
* ``SEED_DATASET``   — also mass-import the IMDb datasets (~32k, no posters)

Run standalone with::

    python -m app.scrapers.init_library
"""
from __future__ import annotations

import asyncio
import logging

from sqlalchemy import func, select

from app.config import settings
from app.database import SessionLocal
from app.models import Movie
from app.scrapers.imdb_dataset import run as dataset_run
from app.scrapers.service import scraper_service

logger = logging.getLogger(__name__)


async def main() -> None:
    logging.basicConfig(
        level=logging.INFO, format="%(levelname)s %(name)s: %(message)s"
    )

    if not settings.seed_on_start:
        print("[seed] SEED_ON_START=false — skipping")
        return

    async with SessionLocal() as db:
        count = await db.scalar(select(func.count(Movie.id)))

    if count and count > 0:
        print(f"[seed] library already has {count} movies — nothing to do")
        return

    print("[seed] empty library — populating (this runs only once)…")

    # Dataset first (fast, no browser); charts second so the popular titles
    # also get posters/plots and RT scores layered on top.
    if settings.seed_dataset:
        await dataset_run(
            settings.seed_dataset_min_rating,
            settings.seed_dataset_min_votes,
            include_tv_movies=False,
            refresh=False,
        )

    if settings.seed_charts:
        async with SessionLocal() as db:
            stats = await scraper_service.bulk_import(
                db, rt_limit=settings.seed_rt_limit
            )
        print(
            f"[seed] charts: imported {stats['imported']}, "
            f"RT-enriched {stats['rt_enriched']}"
        )

    print("[seed] done")


if __name__ == "__main__":
    asyncio.run(main())
