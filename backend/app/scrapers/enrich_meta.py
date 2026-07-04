"""Backfill posters + plot/cast/director for movies imported from the datasets.

IMDb's downloadable datasets carry no posters or plots, so mass-imported movies
show a placeholder until scraped. This walks the library most-popular-first,
scrapes each movie's IMDb page directly (by its stored id), and fills in the
missing fields. Runs in bounded batches and resumes where it left off.

    python -m app.scrapers.enrich_meta --limit 100    # top 100 missing posters
    python -m app.scrapers.enrich_meta --limit 500    # next batch
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
        stats = await scraper_service.enrich_metadata(db, limit=limit)
    elapsed = time.perf_counter() - start
    print(
        f"Done in {elapsed:.0f}s — attempted {stats['attempted']}, "
        f"posters added {stats['enriched']}."
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Backfill posters/plot/cast for movies missing them"
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
