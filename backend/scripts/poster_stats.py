import asyncio
import asyncpg


async def main() -> None:
    c = await asyncpg.connect(host="localhost", port=5433, user="postgres",
                              password="postgres", database="movie_scraper")
    try:
        print("total movies:", await c.fetchval("SELECT count(*) FROM movies"))
        print("with poster:", await c.fetchval(
            "SELECT count(*) FROM movies WHERE poster_url IS NOT NULL"))
        print("backfill candidates (no poster, never scraped):", await c.fetchval(
            "SELECT count(*) FROM movies WHERE poster_url IS NULL "
            "AND imdb_id IS NOT NULL AND last_scraped_at IS NULL"))
    finally:
        await c.close()


if __name__ == "__main__":
    asyncio.run(main())
