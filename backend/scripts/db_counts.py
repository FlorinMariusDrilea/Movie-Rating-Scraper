import asyncio

import asyncpg


async def main() -> None:
    c = await asyncpg.connect(host="localhost", port=5433, user="postgres",
                              password="postgres", database="movie_scraper")
    try:
        for tbl in ("movies", "ratings", "genres", "movie_genres"):
            n = await c.fetchval(f"SELECT count(*) FROM {tbl}")
            print(f"{tbl}: {n}")
        print("--- movies ---")
        rows = await c.fetch("SELECT id, imdb_id, title, year, popularity FROM movies ORDER BY id")
        for r in rows:
            print(dict(r))
        print("--- ratings per movie ---")
        rows = await c.fetch(
            "SELECT movie_id, source, score, scale, votes FROM ratings ORDER BY movie_id, source"
        )
        for r in rows:
            print(dict(r))
    finally:
        await c.close()


if __name__ == "__main__":
    asyncio.run(main())
