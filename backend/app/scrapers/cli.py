"""Standalone scraper CLI — test scraping without running the API.

Examples::

    python -m app.scrapers.cli "The Matrix"
    python -m app.scrapers.cli "Dune" --save
    python -m app.scrapers.cli "Oppenheimer" --no-headless
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging

from app.scrapers.service import scraper_service


async def _run(query: str, save: bool) -> None:
    if save:
        from app.database import SessionLocal

        async with SessionLocal() as db:
            movie, source = await scraper_service.get_or_scrape(db, query, force=True)
            if movie is None:
                print(f"No result for {query!r} (source={source})")
                return
            print(f"[{source}] stored movie id={movie.id}: {movie.title} ({movie.year})")
            print(f"  genres: {[g.name for g in movie.genres]}")
            for r in movie.ratings:
                print(f"  {r.source.value}: {r.score}/{r.scale} (votes={r.votes})")
    else:
        result = await scraper_service.scrape(query)
        if result is None:
            print(f"No result for {query!r}")
            return
        print(json.dumps(result.to_dict(), indent=2, ensure_ascii=False))


def main() -> None:
    parser = argparse.ArgumentParser(description="Scrape a movie from IMDb + Rotten Tomatoes")
    parser.add_argument("query", help="Movie title to search for")
    parser.add_argument("--save", action="store_true", help="Persist the result to the database")
    parser.add_argument("--no-headless", action="store_true", help="Show the browser window")
    parser.add_argument("-v", "--verbose", action="store_true", help="Debug logging")
    args = parser.parse_args()

    if args.no_headless:
        # Override before the browser launches.
        from app.config import settings

        settings.scraper_headless = False

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
    )

    asyncio.run(_run(args.query, args.save))


if __name__ == "__main__":
    main()
