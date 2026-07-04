"""Bulk-import CLI — populate the library from IMDb charts in one command.

Examples::

    python -m app.scrapers.bulk                      # Top 250 + Most Popular
    python -m app.scrapers.bulk --charts top         # just the Top 250
    python -m app.scrapers.bulk --rt-limit 25        # also RT-enrich top 25
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import time

from app.database import SessionLocal
from app.scrapers.imdb_charts import CHARTS
from app.scrapers.service import scraper_service


async def _run(charts: list[str], rt_limit: int) -> None:
    start = time.perf_counter()
    async with SessionLocal() as db:
        stats = await scraper_service.bulk_import(db, charts=charts, rt_limit=rt_limit)
    elapsed = time.perf_counter() - start
    print(
        f"Done in {elapsed:.1f}s — imported/updated {stats['imported']} movies, "
        f"RT-enriched {stats['rt_enriched']}."
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Bulk-import movies from IMDb charts (Top 250, Most Popular)"
    )
    parser.add_argument(
        "--charts",
        nargs="+",
        choices=sorted(CHARTS),
        default=["top", "popular"],
        help="Which charts to import (default: all)",
    )
    parser.add_argument(
        "--rt-limit",
        type=int,
        default=0,
        help="Also fetch Rotten Tomatoes scores for the N most popular "
        "imported movies that lack them (throttled; ~10s each). Default 0.",
    )
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
    )

    asyncio.run(_run(args.charts, args.rt_limit))


if __name__ == "__main__":
    main()
