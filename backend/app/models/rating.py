"""Rating model — one row per (movie, source)."""
from __future__ import annotations

import enum
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.movie import Movie


class RatingSource(str, enum.Enum):
    """Where a rating came from.

    Rotten Tomatoes exposes two scores, so it gets two members.
    """

    imdb = "imdb"
    rt_tomatometer = "rt_tomatometer"  # critics score (0-100)
    rt_audience = "rt_audience"  # audience score (0-100)


class Rating(Base):
    __tablename__ = "ratings"
    __table_args__ = (
        UniqueConstraint("movie_id", "source", name="uq_rating_movie_source"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    movie_id: Mapped[int] = mapped_column(
        ForeignKey("movies.id", ondelete="CASCADE"), index=True
    )
    source: Mapped[RatingSource] = mapped_column(
        Enum(RatingSource, name="rating_source")
    )
    score: Mapped[float] = mapped_column(Float)
    # Max value of the score: 10 for IMDb, 100 for the RT percentages.
    scale: Mapped[int] = mapped_column(Integer, default=100)
    votes: Mapped[int | None] = mapped_column(Integer)
    url: Mapped[str | None] = mapped_column(String(1024))
    scraped_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    movie: Mapped["Movie"] = relationship(back_populates="ratings")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Rating {self.source.value}={self.score}/{self.scale}>"
