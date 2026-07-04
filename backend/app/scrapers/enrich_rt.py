"""Backfill Rotten Tomatoes scores for movies that only have IMDb ratings.

Chart/dataset imports are IMDb-only; RT has no bulk source, so RT scores are
added by scraping each movie. This walks the library most-popular-first,
scrapes RT for movies missing it, and marks each as checked so re-runs resume
where they left off (and never re-hammer titles that aren't on RT).

Each movie takes a few seconds (throttled), so run it in bounded batches::

    python -m app.scrapers.enrich_rt --limit 100    # top 100 missing RT
    python -m app.scrapers.enrich_rt --limit 500    # keep going next batch
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import time

from app.database import SessionLocal
from app.scrapers.service import scraper_service


async def _run(limit: int) -> None:
    start = time.perf_counter()
    async with SessionLocal() as db:
        stats = await scraper_service.enrich_rt(db, limit=limit)
    elapsed = time.perf_counter() - start
    print(
        f"Done in {elapsed:.0f}s — attempted {stats['attempted']}, "
        f"RT-enriched {stats['enriched']} "
        f"({stats['attempted'] - stats['enriched']} not on RT)."
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Backfill Rotten Tomatoes scores for IMDb-only movies"
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=100,
        help="How many movies to attempt this run (most popular first). "
        "Default 100.",
    )
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
    )
    asyncio.run(_run(args.limit))


if __name__ == "__main__":
    main()
