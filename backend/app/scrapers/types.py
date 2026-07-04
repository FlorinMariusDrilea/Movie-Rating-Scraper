"""Normalized data structures returned by scrapers.

Scrapers never touch the ORM directly — they return these plain dataclasses,
which the persistence layer maps onto Movie/Rating/Genre. This keeps the
scraping logic decoupled from storage and makes an API-based source swappable.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from app.models import RatingSource


@dataclass
class ScrapedRating:
    source: RatingSource
    score: float
    scale: int
    votes: int | None = None
    url: str | None = None


@dataclass
class ScrapedMovie:
    title: str
    year: int | None = None
    imdb_id: str | None = None
    plot: str | None = None
    runtime_minutes: int | None = None
    poster_url: str | None = None
    director: str | None = None
    cast_members: list[str] = field(default_factory=list)
    genres: list[str] = field(default_factory=list)
    popularity: float | None = None
    imdb_url: str | None = None
    rt_url: str | None = None
    ratings: list[ScrapedRating] = field(default_factory=list)

    def merge(self, other: "ScrapedMovie") -> "ScrapedMovie":
        """Merge another source's result into this one.

        ``self`` is treated as the base (IMDb); non-empty fields from ``other``
        fill gaps, and ratings/genres are unioned.
        """
        for key, value in asdict(other).items():
            if key in {"ratings", "genres", "cast_members"}:
                continue
            if not getattr(self, key) and value:
                setattr(self, key, value)

        # Union genres (case-insensitive) preserving order.
        seen = {g.lower() for g in self.genres}
        for g in other.genres:
            if g.lower() not in seen:
                self.genres.append(g)
                seen.add(g.lower())

        if not self.cast_members:
            self.cast_members = other.cast_members

        # Ratings are keyed by source; keep existing, add new sources.
        existing_sources = {r.source for r in self.ratings}
        for r in other.ratings:
            if r.source not in existing_sources:
                self.ratings.append(r)

        return self

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["ratings"] = [
            {**asdict(r), "source": r.source.value} for r in self.ratings
        ]
        return data
