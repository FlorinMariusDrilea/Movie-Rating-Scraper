"""Create the application database if it does not already exist.

Usage:
    python scripts/create_db.py

Reads connection info from ALEMBIC_DATABASE_URL / DATABASE_URL when available,
falling back to the local PostgreSQL 16 defaults (port 5433, postgres/postgres).
"""
from __future__ import annotations

import asyncio

import asyncpg

HOST = "localhost"
PORT = 5433
USER = "postgres"
PASSWORD = "postgres"
DB_NAME = "movie_scraper"


async def main() -> None:
    conn = await asyncpg.connect(
        host=HOST, port=PORT, user=USER, password=PASSWORD, database="postgres"
    )
    try:
        exists = await conn.fetchval(
            "SELECT 1 FROM pg_database WHERE datname = $1", DB_NAME
        )
        if exists:
            print(f"Database '{DB_NAME}' already exists.")
        else:
            await conn.execute(f'CREATE DATABASE "{DB_NAME}"')
            print(f"Created database '{DB_NAME}'.")
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
