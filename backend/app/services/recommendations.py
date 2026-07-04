"""Content-based movie recommendations.

Scores every stored movie against one or more "seed" movies the user likes.
No ML training — an explainable weighted blend of:

* **Genre overlap** (weight 0.5) — Jaccard similarity between the union of the
  seeds' genres and the candidate's genres.
* **Rating similarity** (weight 0.3) — how close the candidate's average
  normalized score (0–100 across IMDb/RT) is to the seeds' average.
* **Popularity** (weight 0.2) — log-scaled vote count relative to the most
  popular movie in the library, so blockbusters don't drown everything.

Each recommendation carries human-readable ``reasons`` for the UI.

Works in-memory over the whole library — fine for a personal collection
(thousands of rows); revisit with pgvector/SQL scoring if it ever grows huge.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Movie

GENRE_WEIGHT = 0.5
RATING_WEIGHT = 0.3
POPULARITY_WEIGHT = 0.2


@dataclass
class Recommendation:
    movie: Movie
    score: float
    reasons: list[str]


def _avg_normalized_score(movie: Movie) -> float | None:
    """Average of all ratings normalized to 0–100, or None if unrated."""
    values = [r.score / r.scale * 100 for r in movie.ratings if r.scale]
    return sum(values) / len(values) if values else None


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def score_candidates(
    seeds: list[Movie], candidates: list[Movie], limit: int = 10
) -> list[Recommendation]:
    seed_ids = {m.id for m in seeds}
    seed_genres: set[str] = {g.name.lower() for m in seeds for g in m.genres}

    seed_avgs = [s for s in (_avg_normalized_score(m) for m in seeds) if s is not None]
    seed_avg = sum(seed_avgs) / len(seed_avgs) if seed_avgs else None

    max_pop = max((m.popularity or 0 for m in candidates), default=0)
    log_max_pop = math.log10(max_pop + 1) if max_pop > 0 else 0

    results: list[Recommendation] = []
    for cand in candidates:
        if cand.id in seed_ids:
            continue

        cand_genres = {g.name.lower() for g in cand.genres}
        genre_sim = _jaccard(seed_genres, cand_genres)

        cand_avg = _avg_normalized_score(cand)
        if cand_avg is not None and seed_avg is not None:
            rating_sim = max(0.0, 1 - abs(cand_avg - seed_avg) / 100)
        else:
            rating_sim = 0.0

        if log_max_pop > 0:
            pop_score = math.log10((cand.popularity or 0) + 1) / log_max_pop
        else:
            pop_score = 0.0

        total = (
            GENRE_WEIGHT * genre_sim
            + RATING_WEIGHT * rating_sim
            + POPULARITY_WEIGHT * pop_score
        )
        if total <= 0:
            continue

        # Human-readable explanations, most informative first.
        reasons: list[str] = []
        shared = sorted(seed_genres & cand_genres)
        if shared:
            pretty = [g.title() for g in shared[:3]]
            reasons.append(f"Shares {', '.join(pretty)}")
        if cand_avg is not None and seed_avg is not None and abs(cand_avg - seed_avg) <= 10:
            reasons.append("Similar rating profile")
        if cand_avg is not None and cand_avg >= 75:
            reasons.append("Highly rated")
        if max_pop > 0 and (cand.popularity or 0) >= max_pop * 0.5:
            reasons.append("Very popular")

        results.append(Recommendation(movie=cand, score=round(total, 4), reasons=reasons))

    results.sort(key=lambda r: r.score, reverse=True)
    return results[:limit]


# With a mass-imported library, scoring every stored movie per request gets
# slow; the most popular slice is where recommendations come from anyway.
MAX_CANDIDATES = 5000


async def recommend(
    db: AsyncSession, seed_ids: list[int], limit: int = 10
) -> tuple[list[Movie], list[Recommendation]]:
    """Return (found_seeds, recommendations) for the given seed movie ids."""
    seeds = list(
        (await db.execute(select(Movie).where(Movie.id.in_(seed_ids)))).scalars()
    )
    if not seeds:
        return [], []

    candidates = list(
        (
            await db.execute(
                select(Movie)
                .order_by(Movie.popularity.desc().nulls_last())
                .limit(MAX_CANDIDATES)
            )
        ).scalars()
    )
    return seeds, score_candidates(seeds, candidates, limit)
