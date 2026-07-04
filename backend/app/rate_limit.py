"""Lightweight per-client (IP) rate limiting.

Used as a FastAPI dependency so it never touches route signatures (avoids the
body-parsing quirks of decorator-based limiters). In-memory sliding window, so
limits are per-process — front with a reverse proxy or shared store (Redis) if
you run multiple instances.

Guards the scrape/search endpoints in particular: each launches a browser and
hits external sites, so an unbounded flood would exhaust resources and risk the
host IP being blocked by IMDb/RT.

(No ``from __future__ import annotations`` here: FastAPI must see the real
``Request`` type on ``__call__`` to inject it rather than treat it as a query
parameter.)
"""
import time
from collections import defaultdict, deque
from typing import Deque, Dict

from fastapi import HTTPException, Request, status


class RateLimiter:
    def __init__(self, times: int, seconds: int) -> None:
        self.times = times
        self.seconds = seconds
        self._hits: Dict[str, Deque[float]] = defaultdict(deque)

    async def __call__(self, request: Request) -> None:
        client = request.client.host if request.client else "unknown"
        now = time.monotonic()
        window = self._hits[client]

        # Drop timestamps older than the window.
        cutoff = now - self.seconds
        while window and window[0] <= cutoff:
            window.popleft()

        if len(window) >= self.times:
            retry = int(window[0] + self.seconds - now) + 1
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Rate limit exceeded — please slow down.",
                headers={"Retry-After": str(retry)},
            )
        window.append(now)


# Tight limits on the expensive scraping endpoints; looser on recommendations.
scrape_limiter = RateLimiter(times=10, seconds=60)
search_limiter = RateLimiter(times=15, seconds=60)
recommend_limiter = RateLimiter(times=60, seconds=60)
