"""Recommendation endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.rate_limit import recommend_limiter
from app.schemas import MovieOut, RecommendationOut, RecommendationsResponse
from app.services.recommendations import recommend

router = APIRouter(prefix="/recommendations", tags=["recommendations"])


@router.get(
    "",
    response_model=RecommendationsResponse,
    dependencies=[Depends(recommend_limiter)],
)
async def get_recommendations(
    based_on: list[int] = Query(
        ..., min_length=1, max_length=20, description="Seed movie id(s)"
    ),
    limit: int = Query(10, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
) -> RecommendationsResponse:
    seeds, recs = await recommend(db, based_on, limit)
    if not seeds:
        raise HTTPException(status_code=404, detail="No seed movies found")
    return RecommendationsResponse(
        seeds=[MovieOut.from_model(m) for m in seeds],
        items=[
            RecommendationOut(
                movie=MovieOut.from_model(r.movie),
                score=r.score,
                reasons=r.reasons,
            )
            for r in recs
        ],
    )
