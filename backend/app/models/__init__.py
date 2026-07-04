"""ORM models package.

Importing every model here ensures they are registered on ``Base.metadata``
so Alembic autogenerate and ``create_all`` can see them.
"""
from app.database import Base
from app.models.associations import movie_genres
from app.models.genre import Genre
from app.models.movie import Movie
from app.models.rating import Rating, RatingSource

__all__ = [
    "Base",
    "movie_genres",
    "Genre",
    "Movie",
    "Rating",
    "RatingSource",
]
