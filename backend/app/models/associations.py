"""Association tables shared between models."""
from __future__ import annotations

from sqlalchemy import Column, ForeignKey, Table

from app.database import Base

# Many-to-many: a movie has many genres, a genre has many movies.
movie_genres = Table(
    "movie_genres",
    Base.metadata,
    Column(
        "movie_id",
        ForeignKey("movies.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "genre_id",
        ForeignKey("genres.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)
