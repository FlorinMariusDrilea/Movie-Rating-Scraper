"""Print the tables, the alembic version, and the rating_source enum values."""
from __future__ import annotations

import asyncio

import asyncpg


async def main() -> None:
    conn = await asyncpg.connect(
        host="localhost", port=5433, user="postgres",
        password="postgres", database="movie_scraper",
    )
    try:
        tables = await conn.fetch(
            "SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename"
        )
        print("Tables:", [r["tablename"] for r in tables])

        version = await conn.fetchval("SELECT version_num FROM alembic_version")
        print("Alembic version:", version)

        enum_vals = await conn.fetch(
            "SELECT e.enumlabel FROM pg_enum e "
            "JOIN pg_type t ON t.oid = e.enumtypid "
            "WHERE t.typname = 'rating_source' ORDER BY e.enumsortorder"
        )
        print("rating_source enum:", [r["enumlabel"] for r in enum_vals])
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
