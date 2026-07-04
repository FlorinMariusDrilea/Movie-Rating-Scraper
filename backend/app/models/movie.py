"""Movie model — the central entity, cached from scraping."""
from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.associations import movie_genres

if TYPE_CHECKING:
    from app.models.genre import Genre
    from app.models.rating import Rating


class Movie(Base):
    __tablename__ = "movies"

    id: Mapped[int] = mapped_column(primary_key=True)

    # IMDb's tconst (e.g. "tt0111161"); unique when known.
    imdb_id: Mapped[str | None] = mapped_column(String(20), unique=True, index=True)

    title: Mapped[str] = mapped_column(String(512), index=True)
    year: Mapped[int | None] = mapped_column(Integer, index=True)
    plot: Mapped[str | None] = mapped_column(Text)
    runtime_minutes: Mapped[int | None] = mapped_column(Integer)
    poster_url: Mapped[str | None] = mapped_column(String(1024))
    director: Mapped[str | None] = mapped_column(String(256))
    cast_members: Mapped[list[str] | None] = mapped_column(ARRAY(String))

    # IMDb popularity/MOVIEmeter-derived score; used for sorting.
    popularity: Mapped[float | None] = mapped_column(index=True)

    imdb_url: Mapped[str | None] = mapped_column(String(1024))
    rt_url: Mapped[str | None] = mapped_column(String(1024))

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    # When the movie was last (re)scraped; drives the cache-TTL check.
    last_scraped_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # When Rotten Tomatoes enrichment was last attempted (found or not), so the
    # backfill never re-scrapes a movie that simply isn't on RT.
    rt_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    genres: Mapped[list["Genre"]] = relationship(
        secondary=movie_genres,
        back_populates="movies",
        lazy="selectin",
    )
    ratings: Mapped[list["Rating"]] = relationship(
        back_populates="movie",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Movie {self.title!r} ({self.year})>"
