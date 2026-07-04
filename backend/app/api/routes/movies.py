"""Movie endpoints: list/filter/sort, detail, search, scrape, and genres."""
from __future__ import annotations

import math

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.rate_limit import scrape_limiter, search_limiter
from app.repositories import movies as repo
from app.repositories.movies import SORTABLE, MovieFilters
from app.schemas import MovieListResponse, MovieOut, ScrapeRequest, SearchResponse
from app.scrapers.service import scraper_service

router = APIRouter(prefix="/movies", tags=["movies"])


@router.get("", response_model=MovieListResponse)
async def list_movies(
    db: AsyncSession = Depends(get_db),
    q: str | None = Query(
        None, max_length=200, description="Title contains (case-insensitive)"
    ),
    genre: list[str] | None = Query(
        None, max_length=20, description="Filter by genre (repeatable)"
    ),
    year_from: int | None = Query(None, ge=1870),
    year_to: int | None = Query(None, le=2100),
    min_popularity: float | None = Query(None, ge=0),
    min_imdb: float | None = Query(None, ge=0, le=10),
    min_tomatometer: float | None = Query(None, ge=0, le=100),
    min_audience: float | None = Query(None, ge=0, le=100),
    sort: str = Query("popularity"),
    order: str = Query("desc", pattern="^(asc|desc)$"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> MovieListResponse:
    if sort not in SORTABLE:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid sort '{sort}'. Allowed: {sorted(SORTABLE)}",
        )

    filters = MovieFilters(
        q=q,
        genres=genre,
        year_from=year_from,
        year_to=year_to,
        min_popularity=min_popularity,
        min_imdb=min_imdb,
        min_tomatometer=min_tomatometer,
        min_audience=min_audience,
        sort=sort,
        order=order,
        page=page,
        page_size=page_size,
    )
    items, total = await repo.list_movies(db, filters)
    return MovieListResponse(
        items=[MovieOut.from_model(m) for m in items],
        total=total,
        page=page,
        page_size=page_size,
        pages=math.ceil(total / page_size) if page_size else 0,
    )


@router.get("/genres", response_model=list[str])
async def list_genres(db: AsyncSession = Depends(get_db)) -> list[str]:
    return await repo.list_genres(db)


# Scraping endpoints are tightly limited: each can launch a browser and hit
# external sites, so a flood would exhaust resources and risk an IP ban.
@router.get(
    "/search",
    response_model=SearchResponse,
    dependencies=[Depends(search_limiter)],
)
async def search_movie(
    q: str = Query(..., min_length=1, max_length=200, description="Movie title to find"),
    db: AsyncSession = Depends(get_db),
) -> SearchResponse:
    """DB-first search; scrapes and stores on a cache miss."""
    movie, source = await scraper_service.get_or_scrape(db, q, force=False)
    return SearchResponse(
        source=source,
        movie=MovieOut.from_model(movie) if movie else None,
    )


@router.post(
    "/scrape",
    response_model=SearchResponse,
    dependencies=[Depends(scrape_limiter)],
)
async def scrape_movie(
    payload: ScrapeRequest,
    db: AsyncSession = Depends(get_db),
) -> SearchResponse:
    """On-demand scrape. ``force=true`` bypasses the cache and refreshes."""
    movie, source = await scraper_service.get_or_scrape(
        db, payload.query, force=payload.force
    )
    return SearchResponse(
        source=source,
        movie=MovieOut.from_model(movie) if movie else None,
    )


@router.get("/{movie_id}", response_model=MovieOut)
async def get_movie(
    movie_id: int, db: AsyncSession = Depends(get_db)
) -> MovieOut:
    movie = await repo.get_movie(db, movie_id)
    if movie is None:
        raise HTTPException(status_code=404, detail="Movie not found")
    return MovieOut.from_model(movie)
