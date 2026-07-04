"""Query layer for movies: filtering, sorting, and pagination.

Rating-based filters/sorts use per-source EXISTS / scalar subqueries so the
movies table isn't fanned out by the one-to-many ratings join.
"""
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import Select, and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Genre, Movie, Rating, RatingSource

# Sort keys the API accepts.
SORTABLE = {"title", "year", "popularity", "last_scraped_at",
            "imdb", "rt_tomatometer", "rt_audience"}


@dataclass
class MovieFilters:
    q: str | None = None
    genres: list[str] | None = None
    year_from: int | None = None
    year_to: int | None = None
    min_popularity: float | None = None
    min_imdb: float | None = None
    min_tomatometer: float | None = None
    min_audience: float | None = None
    sort: str = "popularity"
    order: str = "desc"
    page: int = 1
    page_size: int = 20


def _rating_exists(source: RatingSource, min_score: float):
    return Movie.ratings.any(and_(Rating.source == source, Rating.score >= min_score))


def _rating_score_subquery(source: RatingSource):
    """Correlated scalar subquery: this movie's score for the given source."""
    return (
        select(Rating.score)
        .where(Rating.movie_id == Movie.id, Rating.source == source)
        .scalar_subquery()
    )


def _escape_like(term: str) -> str:
    """Escape LIKE/ILIKE wildcards so user input matches literally."""
    return term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _apply_filters(stmt: Select, f: MovieFilters) -> Select:
    conditions = []
    if f.q:
        pattern = f"%{_escape_like(f.q)}%"
        conditions.append(Movie.title.ilike(pattern, escape="\\"))
    if f.genres:
        conditions.append(Movie.genres.any(Genre.name.in_(f.genres)))
    if f.year_from is not None:
        conditions.append(Movie.year >= f.year_from)
    if f.year_to is not None:
        conditions.append(Movie.year <= f.year_to)
    if f.min_popularity is not None:
        conditions.append(Movie.popularity >= f.min_popularity)
    if f.min_imdb is not None:
        conditions.append(_rating_exists(RatingSource.imdb, f.min_imdb))
    if f.min_tomatometer is not None:
        conditions.append(_rating_exists(RatingSource.rt_tomatometer, f.min_tomatometer))
    if f.min_audience is not None:
        conditions.append(_rating_exists(RatingSource.rt_audience, f.min_audience))
    if conditions:
        stmt = stmt.where(*conditions)
    return stmt


def _order_by(f: MovieFilters):
    columns = {
        "title": Movie.title,
        "year": Movie.year,
        "popularity": Movie.popularity,
        "last_scraped_at": Movie.last_scraped_at,
        "imdb": _rating_score_subquery(RatingSource.imdb),
        "rt_tomatometer": _rating_score_subquery(RatingSource.rt_tomatometer),
        "rt_audience": _rating_score_subquery(RatingSource.rt_audience),
    }
    col = columns.get(f.sort, Movie.popularity)
    direction = col.desc() if f.order.lower() == "desc" else col.asc()
    # Keep NULLs last regardless of direction, with a stable id tiebreaker.
    return direction.nulls_last(), Movie.id.desc()


async def list_movies(
    db: AsyncSession, f: MovieFilters
) -> tuple[list[Movie], int]:
    total = (
        await db.execute(_apply_filters(select(func.count(Movie.id)), f))
    ).scalar_one()

    stmt = _apply_filters(select(Movie), f).order_by(*_order_by(f))
    stmt = stmt.offset((f.page - 1) * f.page_size).limit(f.page_size)
    items = (await db.execute(stmt)).scalars().all()
    return list(items), total


async def get_movie(db: AsyncSession, movie_id: int) -> Movie | None:
    return (
        await db.execute(select(Movie).where(Movie.id == movie_id))
    ).scalar_one_or_none()


async def list_genres(db: AsyncSession) -> list[str]:
    rows = (
        await db.execute(select(Genre.name).order_by(Genre.name))
    ).scalars().all()
    return list(rows)
