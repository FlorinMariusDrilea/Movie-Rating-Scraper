"""Pydantic response/request schemas for the movie API."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models import Movie, RatingSource


class RatingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True, use_enum_values=True)

    source: RatingSource
    score: float
    scale: int
    votes: int | None = None
    url: str | None = None


class MovieOut(BaseModel):
    id: int
    imdb_id: str | None
    title: str
    year: int | None
    plot: str | None
    runtime_minutes: int | None
    poster_url: str | None
    director: str | None
    cast_members: list[str] | None
    popularity: float | None
    imdb_url: str | None
    rt_url: str | None
    last_scraped_at: datetime | None
    genres: list[str]

    # Flattened scores for convenient table columns (derived from ratings).
    imdb_score: float | None
    rt_tomatometer: float | None
    rt_audience: float | None

    ratings: list[RatingOut]

    @classmethod
    def from_model(cls, m: Movie) -> "MovieOut":
        scores = {r.source: r.score for r in m.ratings}
        return cls(
            id=m.id,
            imdb_id=m.imdb_id,
            title=m.title,
            year=m.year,
            plot=m.plot,
            runtime_minutes=m.runtime_minutes,
            poster_url=m.poster_url,
            director=m.director,
            cast_members=m.cast_members,
            popularity=m.popularity,
            imdb_url=m.imdb_url,
            rt_url=m.rt_url,
            last_scraped_at=m.last_scraped_at,
            genres=[g.name for g in m.genres],
            imdb_score=scores.get(RatingSource.imdb),
            rt_tomatometer=scores.get(RatingSource.rt_tomatometer),
            rt_audience=scores.get(RatingSource.rt_audience),
            ratings=[RatingOut.model_validate(r) for r in m.ratings],
        )


class MovieListResponse(BaseModel):
    items: list[MovieOut]
    total: int
    page: int
    page_size: int
    pages: int


class SearchResponse(BaseModel):
    """Result of a search/scrape — ``source`` is 'cache', 'scraped', or 'not_found'."""

    source: str
    movie: MovieOut | None = None


class ScrapeRequest(BaseModel):
    query: str = Field(
        min_length=1, max_length=200, description="Movie title to scrape"
    )
    force: bool = Field(default=False, description="Bypass the cache and re-scrape")


class RecommendationOut(BaseModel):
    movie: MovieOut
    score: float
    reasons: list[str]


class RecommendationsResponse(BaseModel):
    seeds: list[MovieOut]
    items: list[RecommendationOut]
