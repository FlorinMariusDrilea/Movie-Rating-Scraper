"""Mass import from IMDb's official downloadable datasets.

IMDb publishes daily TSV dumps (https://datasets.imdbws.com/, free for
personal/non-commercial use) covering every title on the site. This importer
downloads two of them:

* ``title.ratings.tsv.gz`` (~7 MB)   — averageRating + numVotes per title
* ``title.basics.tsv.gz``  (~200 MB) — type, title, year, runtime, genres

filters to movies matching ``--min-rating`` / ``--min-votes``, and bulk-upserts
them with set-based ``INSERT … ON CONFLICT`` statements (thousands of rows per
statement — not per-row ORM commits).

The datasets carry no posters/plots/cast; those fields stay empty until a
movie is individually scraped (detail modal → Re-scrape, or a title search).
``last_scraped_at`` is deliberately left NULL so such a lookup enriches the
record instead of trusting the cache.

Usage::

    python -m app.scrapers.imdb_dataset                       # rating>=6, votes>=1000
    python -m app.scrapers.imdb_dataset --min-rating 7 --min-votes 5000
    python -m app.scrapers.imdb_dataset --min-votes 0         # EVERYTHING >=6 (huge)
"""
from __future__ import annotations

import argparse
import asyncio
import csv
import gzip
import logging
import sys
import time
from pathlib import Path
from typing import Iterator

import httpx
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy import func, select

from app.database import SessionLocal
from app.models import Genre, Movie, Rating

logger = logging.getLogger(__name__)

BASE_URL = "https://datasets.imdbws.com"
FILES = {
    "ratings": "title.ratings.tsv.gz",
    "basics": "title.basics.tsv.gz",
}
DATA_DIR = Path(__file__).resolve().parents[2] / "data"

BATCH = 1000
TITLE_URL = "https://www.imdb.com/title/{tconst}/"


# --------------------------------------------------------------- download

async def download(name: str, refresh: bool = False) -> Path:
    """Download a dataset file unless a copy already exists."""
    DATA_DIR.mkdir(exist_ok=True)
    dest = DATA_DIR / FILES[name]
    if dest.exists() and not refresh:
        print(f"[dataset] using cached {dest.name} ({dest.stat().st_size // 1_048_576} MB)")
        return dest

    url = f"{BASE_URL}/{FILES[name]}"
    print(f"[dataset] downloading {url} …")
    async with httpx.AsyncClient(timeout=None, follow_redirects=True) as client:
        async with client.stream("GET", url) as resp:
            resp.raise_for_status()
            total = int(resp.headers.get("content-length", 0))
            done = 0
            with open(dest, "wb") as fh:
                async for chunk in resp.aiter_bytes(1 << 20):
                    fh.write(chunk)
                    done += len(chunk)
                    if total:
                        pct = done * 100 // total
                        print(f"\r[dataset] {dest.name}: {pct}% ({done >> 20} MB)", end="")
    print()
    return dest


# --------------------------------------------------------------- parsing

def load_ratings(path: Path, min_rating: float, min_votes: int) -> dict[str, tuple[float, int]]:
    """tconst -> (rating, votes) for titles passing the thresholds."""
    wanted: dict[str, tuple[float, int]] = {}
    with gzip.open(path, "rt", encoding="utf-8", newline="") as fh:
        reader = csv.reader(fh, delimiter="\t", quoting=csv.QUOTE_NONE)
        next(reader)  # header: tconst averageRating numVotes
        for row in reader:
            try:
                rating = float(row[1])
                votes = int(row[2])
            except (ValueError, IndexError):
                continue
            if rating >= min_rating and votes >= min_votes:
                wanted[row[0]] = (rating, votes)
    return wanted


def iter_movies(
    path: Path, wanted: dict[str, tuple[float, int]], include_tv_movies: bool
) -> Iterator[dict]:
    """Yield movie dicts from title.basics for tconsts in ``wanted``."""
    types = {"movie"} | ({"tvMovie"} if include_tv_movies else set())
    with gzip.open(path, "rt", encoding="utf-8", newline="") as fh:
        reader = csv.reader(fh, delimiter="\t", quoting=csv.QUOTE_NONE)
        next(reader)  # tconst titleType primaryTitle originalTitle isAdult startYear endYear runtimeMinutes genres
        for row in reader:
            if len(row) < 9:
                continue
            tconst = row[0]
            if tconst not in wanted or row[1] not in types or row[4] == "1":
                continue
            rating, votes = wanted[tconst]
            yield {
                "imdb_id": tconst,
                "title": row[2][:512],
                "year": int(row[5]) if row[5].isdigit() else None,
                "runtime_minutes": int(row[7]) if row[7].isdigit() else None,
                "genres": [] if row[8] in ("\\N", "") else row[8].split(","),
                "rating": rating,
                "votes": votes,
            }


# --------------------------------------------------------------- importing

async def import_rows(rows: list[dict]) -> int:
    """Bulk-upsert movies + genres + IMDb ratings. Returns imported count."""
    async with SessionLocal() as db:
        # 1) Genres: tiny distinct set, upsert once, map name -> id.
        names = sorted({g for r in rows for g in r["genres"]})
        if names:
            stmt = pg_insert(Genre.__table__).values([{"name": n} for n in names])
            await db.execute(stmt.on_conflict_do_nothing(index_elements=["name"]))
        genre_ids = dict(
            (await db.execute(select(Genre.name, Genre.id))).all()
        )

        movies_tbl = Movie.__table__
        ratings_tbl = Rating.__table__
        assoc = Movie.genres.property.secondary

        total = 0
        for start in range(0, len(rows), BATCH):
            batch = rows[start : start + BATCH]

            # 2) Movies — fill gaps on conflict, never clobber scraped data.
            stmt = pg_insert(movies_tbl).values(
                [
                    {
                        "imdb_id": r["imdb_id"],
                        "title": r["title"],
                        "year": r["year"],
                        "runtime_minutes": r["runtime_minutes"],
                        "popularity": float(r["votes"]),
                        "imdb_url": TITLE_URL.format(tconst=r["imdb_id"]),
                    }
                    for r in batch
                ]
            )
            stmt = stmt.on_conflict_do_update(
                index_elements=["imdb_id"],
                set_={
                    "year": func.coalesce(movies_tbl.c.year, stmt.excluded.year),
                    "runtime_minutes": func.coalesce(
                        movies_tbl.c.runtime_minutes, stmt.excluded.runtime_minutes
                    ),
                    "popularity": stmt.excluded.popularity,
                },
            )
            await db.execute(stmt)

            # Map tconst -> movie id for this batch.
            ids = dict(
                (
                    await db.execute(
                        select(Movie.imdb_id, Movie.id).where(
                            Movie.imdb_id.in_([r["imdb_id"] for r in batch])
                        )
                    )
                ).all()
            )

            # 3) IMDb rating rows.
            rating_values = [
                {
                    "movie_id": ids[r["imdb_id"]],
                    "source": "imdb",
                    "score": r["rating"],
                    "scale": 10,
                    "votes": r["votes"],
                    "url": TITLE_URL.format(tconst=r["imdb_id"]),
                }
                for r in batch
                if r["imdb_id"] in ids
            ]
            if rating_values:
                rstmt = pg_insert(ratings_tbl).values(rating_values)
                rstmt = rstmt.on_conflict_do_update(
                    constraint="uq_rating_movie_source",
                    set_={
                        "score": rstmt.excluded.score,
                        "votes": rstmt.excluded.votes,
                    },
                )
                await db.execute(rstmt)

            # 4) Genre links.
            link_values = [
                {"movie_id": ids[r["imdb_id"]], "genre_id": genre_ids[g]}
                for r in batch
                if r["imdb_id"] in ids
                for g in r["genres"]
                if g in genre_ids
            ]
            if link_values:
                lstmt = pg_insert(assoc).values(link_values)
                await db.execute(lstmt.on_conflict_do_nothing())

            total += len(batch)
            print(f"\r[dataset] imported {total}/{len(rows)}", end="")

        await db.commit()
    print()
    return total


async def run(
    min_rating: float, min_votes: int, include_tv_movies: bool, refresh: bool
) -> None:
    start = time.perf_counter()

    ratings_path = await download("ratings", refresh)
    basics_path = await download("basics", refresh)

    print(f"[dataset] filtering ratings >= {min_rating} with >= {min_votes} votes …")
    wanted = load_ratings(ratings_path, min_rating, min_votes)
    print(f"[dataset] {len(wanted)} titles pass the rating/vote thresholds")

    print("[dataset] scanning title.basics for movies (11M+ rows, be patient) …")
    rows = list(iter_movies(basics_path, wanted, include_tv_movies))
    print(f"[dataset] {len(rows)} movies to import")

    if not rows:
        print("[dataset] nothing to import")
        return

    total = await import_rows(rows)
    elapsed = time.perf_counter() - start
    print(f"Done in {elapsed:.0f}s — imported/updated {total} movies.")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Mass-import movies from IMDb's official datasets"
    )
    parser.add_argument("--min-rating", type=float, default=6.0)
    parser.add_argument(
        "--min-votes",
        type=int,
        default=1000,
        help="Vote floor; 0 imports every rated title above min-rating "
        "(hundreds of thousands, mostly obscure). Default 1000.",
    )
    parser.add_argument("--include-tv-movies", action="store_true")
    parser.add_argument(
        "--refresh", action="store_true", help="Re-download dataset files"
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    asyncio.run(
        run(args.min_rating, args.min_votes, args.include_tv_movies, args.refresh)
    )


if __name__ == "__main__":
    sys.exit(main())
