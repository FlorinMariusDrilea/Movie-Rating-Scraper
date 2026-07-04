import asyncio
import asyncpg


async def main() -> None:
    c = await asyncpg.connect(host="localhost", port=5433, user="postgres",
                              password="postgres", database="movie_scraper")
    try:
        print("rt_checked_at set:", await c.fetchval(
            "SELECT count(*) FROM movies WHERE rt_checked_at IS NOT NULL"))
        print("movies with RT tomatometer:", await c.fetchval(
            "SELECT count(DISTINCT movie_id) FROM ratings WHERE source='rt_tomatometer'"))
        print("--- LOTR ---")
        rows = await c.fetch(
            "SELECT m.title, r.source, r.score FROM movies m "
            "JOIN ratings r ON r.movie_id=m.id "
            "WHERE m.title LIKE 'The Lord of the Rings%' "
            "ORDER BY m.title, r.source")
        for r in rows:
            print(f"  {r['title'][:42]:42} {r['source']:16} {r['score']}")
    finally:
        await c.close()


if __name__ == "__main__":
    asyncio.run(main())
