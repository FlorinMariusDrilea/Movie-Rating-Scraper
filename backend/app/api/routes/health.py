"""Health-check endpoints, including a live database connectivity probe."""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db

logger = logging.getLogger(__name__)

router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> dict[str, str]:
    """Liveness probe — does not touch the database."""
    return {"status": "ok"}


@router.get("/health/db")
async def health_db(db: AsyncSession = Depends(get_db)) -> dict[str, str]:
    """Readiness probe — verifies the database is reachable."""
    try:
        await db.execute(text("SELECT 1"))
        return {"status": "ok", "database": "connected"}
    except Exception:  # noqa: BLE001
        # Log the real error server-side; don't leak connection details
        # (host/credentials can appear in DB exception messages) to clients.
        logger.exception("Database health check failed")
        return {"status": "error", "database": "unavailable"}
