"""FastAPI application entrypoint."""
from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response

from app.api.routes import health, movies, recommendations
from app.config import settings

app = FastAPI(
    title="Movie Rating Scraper API",
    description="Scrapes IMDb & Rotten Tomatoes ratings and serves a movie dashboard.",
    version="1.0.0",
)

# Only the configured origins may call the API from a browser. Credentials are
# disabled (the app uses no cookies/auth), and methods are limited to those in
# use — avoids a permissive `*` reflecting arbitrary requests.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
    max_age=600,
)


@app.middleware("http")
async def security_headers(request: Request, call_next) -> Response:
    """Add a few conservative security response headers."""
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "no-referrer")
    return response


app.include_router(health.router, prefix="/api")
app.include_router(movies.router, prefix="/api")
app.include_router(recommendations.router, prefix="/api")


@app.get("/")
async def root() -> dict[str, str]:
    return {"service": "movie-rating-scraper", "docs": "/docs"}
