# 🎬 Movie Rating Scraper

A full-stack movie dashboard that scrapes ratings from **IMDb** and **Rotten
Tomatoes**, stores them in PostgreSQL, and serves a React UI to search, filter,
sort, and get **content-based recommendations** — IMDb and RT scores side by
side.

> ⚠️ **Note on scraping:** IMDb and Rotten Tomatoes do not permit scraping in
> their terms of service, and their HTML changes over time. The scrapers here
> are built defensively (rate limiting, retries, DB caching, stable JSON
> sources instead of brittle CSS selectors) and sit behind a clean interface so
> a licensed API (OMDb/TMDB) can be swapped in without touching the rest of the
> app. Personal/learning project — scrape gently.

## Features

- 🔍 **Search-to-scrape** — type a title; it's fetched from the DB cache or
  scraped live from both sites and stored
- 🗂️ **Browse** — poster grid with IMDb rating, RT Tomatometer, and RT audience
  score on every card, color-coded by quality
- 🎚️ **Filter & sort** — genres, min score per source, year range; sort by any
  score, popularity, year, or title
- 📊 **Detail view** — plot, cast, director, a rating-comparison chart with
  vote counts, links to both sites, and one-click re-scrape
- 🤝 **Recommendations** — explainable content-based engine (genre overlap +
  rating similarity + popularity): a "For You" picks view and "More like this"
  in every detail modal
- 🛡️ **Polite scraping** — randomized delays, concurrency cap, exponential
  backoff retries, rotating user agents, and a cache TTL so nothing is scraped
  twice needlessly

## Stack

| Layer     | Tech                                                           |
| --------- | -------------------------------------------------------------- |
| Backend   | Python 3.11, FastAPI, SQLAlchemy 2 (async), Alembic, Pydantic v2 |
| Scraping  | Playwright (Chromium), httpx                                   |
| Database  | PostgreSQL 16                                                  |
| Frontend  | React 19, Vite, TypeScript, TanStack Query, Recharts           |
| Infra     | Docker / docker-compose; nginx for the production frontend     |

## Architecture

```
React dashboard ──HTTP──▶ FastAPI ──▶ PostgreSQL (cache + library)
                             │
                             ├─▶ ScraperService ── merge + upsert
                             │     ├─ IMDbScraper  (suggestion API + JSON-LD)
                             │     └─ RTScraper    (Playwright + scorecard JSON)
                             └─▶ Recommendation engine (content-based)
```

A movie is scraped once and cached with a TTL (`SCRAPER_CACHE_TTL_HOURS`);
repeat searches hit the database, not the sites.

## Project layout

```
├── backend/
│   ├── app/
│   │   ├── main.py            FastAPI entrypoint + CORS
│   │   ├── config.py          env-driven settings
│   │   ├── database.py        async engine / session
│   │   ├── api/routes/        health, movies, recommendations
│   │   ├── models/            Movie, Rating, Genre (+ M2M)
│   │   ├── schemas/           Pydantic responses
│   │   ├── repositories/      filter/sort/paginate queries
│   │   ├── services/          recommendation engine
│   │   └── scrapers/          IMDb + RT scrapers, throttle, CLI
│   ├── alembic/               migrations
│   ├── scripts/               create_db, verify_schema, smoke tests
│   └── Dockerfile             python + chromium, auto-migrates on start
├── frontend/
│   ├── src/                   components, hooks, lib, types
│   ├── Dockerfile             multi-stage build → nginx
│   └── nginx.conf
└── docker-compose.yml         db + backend + frontend
```

## Getting started — full setup from zero

Follow these steps in order the first time; afterwards you only need
**step 5** (run) and occasionally **step 6** (populate). If you have Docker,
`docker compose up --build` replaces steps 1–5 entirely (see [Docker](#docker)).

> **TL;DR (with GNU Make):**
> ```bash
> make install                              # deps: venv + pip + Chromium + npm
> copy backend\.env.example backend\.env    # cp on Linux/macOS; edit DB creds
> copy frontend\.env.example frontend\.env
> make db                                   # create database + tables
> make backend                              # terminal 1 → http://localhost:8000
> make frontend                             # terminal 2 → http://localhost:5173
> make bulk RT=25                           # populate: ~350 movies w/ posters
> ```

### 1. Prerequisites

| Tool           | Version | Check                | Get it                                  |
| -------------- | ------- | -------------------- | --------------------------------------- |
| Python         | 3.11+   | `python --version`   | <https://python.org/downloads>          |
| Node.js        | 20+     | `node --version`     | <https://nodejs.org>                    |
| PostgreSQL     | 14+     | `psql --version` or check your services | <https://postgresql.org/download> |
| GNU Make       | any     | `make --version`     | optional — `choco install make` on Windows; every target has a manual equivalent below |

PostgreSQL must be **running** and you need its superuser (or any
role that can create databases) name, password, and **port** — the default is
`5432`, but a second installed version often takes `5433` (this repo's dev
machine runs PG16 on 5433).

### 2. Configure environment files

```bash
# Windows: copy   |   Linux/macOS: cp
copy backend\.env.example backend\.env
copy frontend\.env.example frontend\.env
```

Open `backend/.env` and set the two database URLs to match your Postgres
**user, password, and port** (same values, different driver prefixes):

```ini
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5433/movie_scraper
ALEMBIC_DATABASE_URL=postgresql+psycopg2://postgres:postgres@localhost:5433/movie_scraper
```

`frontend/.env` only points at the API (`VITE_API_BASE_URL=http://localhost:8000`)
and needs no changes for local dev.

### 3. Install dependencies

`make install`, or manually:

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate                      # Windows | source .venv/bin/activate elsewhere
pip install -r requirements.txt
python -m playwright install chromium       # one-time ~150 MB browser download

cd ../frontend
npm install
```

> If you edited the Postgres credentials in `backend/.env` but `create_db.py`
> fails in the next step, also update the constants at the top of
> [backend/scripts/create_db.py](backend/scripts/create_db.py) — it connects
> with its own defaults (postgres/postgres @ 5433).

### 4. Create the database and tables

`make db`, or manually:

```bash
cd backend
python scripts/create_db.py                 # creates the movie_scraper database
alembic upgrade head                        # creates all tables
```

### 5. Run it (two terminals)

| Terminal | Command                                | Manual equivalent |
| -------- | -------------------------------------- | ----------------- |
| 1        | `make backend`                         | `cd backend && uvicorn app.main:app --reload --port 8000` (venv active) |
| 2        | `make frontend`                        | `cd frontend && npm run dev` |

Open <http://localhost:5173> — the dashboard loads (empty on first run).
API docs live at <http://localhost:8000/docs>.

### 6. Populate the library (pick one or combine)

| Command | What you get | Time |
| ------- | ------------ | ---- |
| type a title in the UI + Enter | that one movie, fully detailed (IMDb + RT + poster + cast) | ~30 s |
| `make scrape-save q="Title"` | same, from the terminal | ~30 s |
| `make seed` | 5 classics, fully detailed | ~3 min |
| `make bulk` / `make bulk RT=25` | IMDb Top 250 + Most Popular (~350 movies with posters/plots; `RT=25` adds RT scores for the top 25) | 30 s / ~5 min |
| `make dataset` | **every IMDb movie rated ≥ 6 with ≥ 1000 votes** (~32k movies; no posters until individually scraped) | ~2 min after a ~210 MB one-time download |
| `make dataset RATING=7 VOTES=5000` | a stricter, smaller cut | same |
| `make populate RT=25` | **everything above in one shot**: dataset + charts + RT for the top 25 | ~8 min first run |

Manual equivalents: `python -m app.scrapers.cli "Title" --save`,
`python -m app.scrapers.bulk --rt-limit 25`,
`python -m app.scrapers.imdb_dataset --min-rating 6 --min-votes 1000`
(all from `backend/` with the venv active).

Why the split: IMDb chart pages embed full data (posters included) for a few
hundred titles in one page load, and IMDb's **official datasets**
(<https://datasets.imdbws.com>) legally cover *every* rated title but carry no
posters/plots. Rotten Tomatoes has no bulk source at all, so RT scores arrive
lazily — via `--rt-limit`, a title search, or the detail modal's **Re-scrape**
button (which also fills in posters, cast, and director for dataset rows).

**Backfill missing RT scores** — because the bulk/dataset sources are
IMDb-only, most imported movies start with just an IMDb rating. Fill in Rotten
Tomatoes for them, most-popular-first, in bounded batches:

```bash
python -m app.scrapers.enrich_rt --limit 100   # top 100 movies missing RT
# or: make enrich-rt N=100
```

Each movie is a throttled RT scrape (a few seconds), so run it in batches and
re-run to keep going — every attempt is marked (`rt_checked_at`), so it resumes
where it left off and never re-scrapes a title that isn't on RT. Movies
genuinely absent from Rotten Tomatoes will keep showing only their IMDb score,
which is expected.

**Backfill missing posters/details** — dataset rows have no poster, plot, or
cast (they show the 🎬 placeholder). Fill them in from each movie's IMDb page,
most-popular-first:

```bash
python -m app.scrapers.enrich_meta --limit 100   # top 100 missing posters
# or: make enrich-meta N=100
```

Same batched, resumable pattern: each scrape stamps `last_scraped_at`, so
re-runs continue with the next most-popular movies and never retry one already
done. Also fills in plot, cast, and director.

### 7. Verify everything works

```bash
curl http://localhost:8000/api/health       # {"status":"ok"}
curl http://localhost:8000/api/health/db    # {"status":"ok","database":"connected"}
```

…and the dashboard's movie grid renders with the imported titles.

### Troubleshooting

| Symptom | Fix |
| ------- | --- |
| `/api/health/db` says `database "movie_scraper" does not exist` | run step 4 (`make db`) |
| `connection refused` on 5433/5432 | Postgres not running, or wrong port in `backend/.env` |
| `password authentication failed` | fix user/password in **both** URLs in `backend/.env` |
| CORS errors in the browser console | `CORS_ORIGINS` in `backend/.env` must include `http://localhost:5173` |
| Scrapes fail with "Executable doesn't exist" | run `python -m playwright install chromium` in the venv |
| First `/api/movies` request takes ~2 s | one-time query planning; subsequent requests are ~35 ms |
| Movie has no poster/cast | it came from the dataset import — open it and hit **Re-scrape** |

Run `make help` for the full target list (`scrape`, `migration`, `typecheck`,
`build`, `docker-up`, …).

## API

Interactive docs at `http://localhost:8000/docs`.

| Method | Path                    | Purpose                                              |
| ------ | ----------------------- | ---------------------------------------------------- |
| GET    | `/api/movies`           | List with filter/sort/paginate (params below)        |
| GET    | `/api/movies/{id}`      | Movie detail                                         |
| GET    | `/api/movies/genres`    | All genre names                                      |
| GET    | `/api/movies/search?q=` | DB-first search; scrapes + stores on a cache miss    |
| POST   | `/api/movies/scrape`    | On-demand scrape `{"query": "...", "force": bool}`   |
| GET    | `/api/recommendations`  | Content-based recs `?based_on=<id>` (repeatable), `limit` |
| GET    | `/api/health`, `/api/health/db` | Liveness / DB readiness probes               |

`GET /api/movies` params: `q`, `genre` (repeatable), `year_from`, `year_to`,
`min_popularity`, `min_imdb` (0–10), `min_tomatometer` / `min_audience`
(0–100), `sort`
(`title|year|popularity|last_scraped_at|imdb|rt_tomatometer|rt_audience`),
`order` (`asc|desc`), `page`, `page_size` (≤100).

## How the scraping works

- **IMDb** — the query is resolved to a title id via IMDb's public suggestion
  endpoint, then the title page's `application/ld+json` block (stable for
  years) provides rating, votes, genres, director, cast, plot, runtime, and
  poster. IMDb vote count doubles as the popularity signal.
- **Rotten Tomatoes** — Playwright searches the site, matches the result by
  title/year, and reads scores from the page's embedded
  `media-scorecard-json` blob (far more stable than the rendered widgets),
  plus JSON-LD for metadata.
- Results are merged (IMDb as the base) and **upserted by `imdb_id`** —
  re-scraping updates in place, never duplicates.

## How recommendations work

Explainable weighted blend, computed over your library — no ML training:

| Signal            | Weight | Definition                                            |
| ----------------- | ------ | ----------------------------------------------------- |
| Genre overlap     | 0.5    | Jaccard similarity: seeds' genres ∪ vs candidate      |
| Rating similarity | 0.3    | Closeness of average normalized (0–100) scores        |
| Popularity        | 0.2    | log₁₀ vote count relative to the library's most popular |

Each result includes `reasons` (e.g. *"Shares Action, Sci-Fi"*, *"Similar
rating profile"*) shown as chips in the UI.

## Configuration

All backend settings are env-driven — see [backend/.env.example](backend/.env.example).
Scraper safeguards: `SCRAPER_MIN/MAX_DELAY_SECONDS`, `SCRAPER_MAX_CONCURRENCY`,
`SCRAPER_MAX_RETRIES`, `SCRAPER_CACHE_TTL_HOURS`, `SCRAPER_ENABLED` (kill
switch), `SCRAPER_HEADLESS`.

## Docker / Podman

```bash
docker compose up --build      # or: podman-compose up --build
```

Brings up Postgres (healthchecked, host port **5434** to avoid clashing with a
locally installed Postgres), the API on `:8000` (waits for the DB, runs
`alembic upgrade head` automatically), the nginx-served production frontend on
`:5173`, and a one-shot **seeder** that populates the library on first run. The
frontend bakes `VITE_API_BASE_URL` at build time — override it as a build arg
for other hosts.

**Auto-seeding:** the `seeder` service waits for the backend to be healthy
(migrations done), then — *only if the database is empty* — imports the IMDb
Top 250 + Most Popular charts (~350 movies with posters) and adds Rotten
Tomatoes scores for the 25 most popular, then exits. It's **idempotent**:
re-running `compose up` does nothing once movies exist. Tune it via the
`SEED_*` env vars on that service in `docker-compose.yml`:

| Var | Default | Effect |
| --- | ------- | ------ |
| `SEED_ON_START` | `true`  | master on/off |
| `SEED_CHARTS`   | `true`  | import Top 250 + Most Popular (posters included) |
| `SEED_RT_LIMIT` | `25`    | RT-enrich this many of the most popular |
| `SEED_DATASET`  | `false` | also mass-import ~32k dataset movies (no posters) |

To reseed from scratch, drop the data volume first:
`docker compose down -v && docker compose up --build`.

The backend image builds from `mcr.microsoft.com/playwright/python`, which
ships Chromium and all its system libraries — keep its tag in sync with the
`playwright` version in [backend/requirements.txt](backend/requirements.txt)
when upgrading.

## Deploying to the cloud

The two halves deploy differently:

**Frontend (static)** — deploys anywhere static hosting works (Vercel,
Netlify, Cloudflare Pages):

```bash
cd frontend && vercel deploy   # set VITE_API_BASE_URL env to your API's URL first
```

**Backend (long-lived container)** — the scraper needs a real Chromium
process and scrapes take 20–60 s, so **serverless platforms (Vercel/Lambda)
are not a fit**. Use a container host — Railway, Render, Fly.io, or any VPS:

1. Point the platform at `backend/Dockerfile` (Chromium is installed in the
   image; migrations run on boot).
2. Provision a managed Postgres (Neon, Supabase, Railway, RDS…) and set
   `DATABASE_URL` (asyncpg) + `ALEMBIC_DATABASE_URL` (psycopg2) accordingly.
3. Set `CORS_ORIGINS` to your frontend's deployed URL.
4. Keep the scraper polite: leave the default delays/concurrency, and consider
   `SCRAPER_ENABLED=false` if you only want to serve the existing library.

## Roadmap

- [x] **Phase 1** — Scaffold: FastAPI + React + Postgres, verified end-to-end
- [x] **Phase 2** — Data model (`movies`, `ratings`, `genres`) + Alembic
- [x] **Phase 3** — IMDb & RT scrapers (throttled, retried, cached, CLI)
- [x] **Phase 4** — API: list/filter/sort/paginate, search, scrape, genres
- [x] **Phase 5** — Dashboard: search, filter sidebar, sortable poster grid
- [x] **Phase 6** — Detail modal with rating chart, re-scrape, skeletons
- [x] **Phase 7** — Content-based recommendations ("For You" + "More like this")
- [x] **Phase 8** — Production builds, Docker, deployment docs

**Ideas for later:** watchlist + user accounts, TF-IDF plot similarity in the
recommender, scheduled re-scrapes of stale movies, OMDb/TMDB API source as a
scraping alternative, e2e tests (Playwright against the UI).
