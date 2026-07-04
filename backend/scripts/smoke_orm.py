"""Smoke-test the async ORM: create a movie with genres + ratings, read it back
through the relationships, then roll back so nothing is persisted."""
from __future__ import annotations

import asyncio

from sqlalchemy import select

from app.database import SessionLocal
from app.models import Genre, Movie, Rating, RatingSource


async def main() -> None:
    async with SessionLocal() as session:
        movie = Movie(
            imdb_id="tt0111161",
            title="The Shawshank Redemption",
            year=1994,
            director="Frank Darabont",
            cast_members=["Tim Robbins", "Morgan Freeman"],
            genres=[Genre(name="Drama"), Genre(name="Crime")],
            ratings=[
                Rating(source=RatingSource.imdb, score=9.3, scale=10, votes=2_900_000),
                Rating(source=RatingSource.rt_tomatometer, score=89, scale=100),
                Rating(source=RatingSource.rt_audience, score=98, scale=100),
            ],
        )
        session.add(movie)
        await session.flush()  # assigns PKs, exercises FKs — no commit

        loaded = (
            await session.execute(select(Movie).where(Movie.id == movie.id))
        ).scalar_one()

        print(f"Movie: {loaded.title} ({loaded.year})  id={loaded.id}")
        print(f"  cast: {loaded.cast_members}")
        print(f"  genres: {sorted(g.name for g in loaded.genres)}")
        for r in sorted(loaded.ratings, key=lambda x: x.source.value):
            print(f"  rating[{r.source.value}] = {r.score}/{r.scale} votes={r.votes}")

        await session.rollback()  # discard the test data
        print("Rolled back — no rows persisted. ORM round-trip OK.")


if __name__ == "__main__":
    asyncio.run(main())
