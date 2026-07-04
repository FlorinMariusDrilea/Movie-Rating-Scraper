# ------------------------------------------------------------------
# Movie Rating Scraper - developer tasks
# Run `make help` for the list of targets.
# Works on Windows (GnuWin32/choco make, cmd shell) and Linux/macOS.
# ------------------------------------------------------------------

ifeq ($(OS),Windows_NT)
SHELL    := cmd.exe
SYS_PY   := python
VENV_PY  := .venv\Scripts\python
RMRF     := rmdir /s /q
DIST     := frontend\dist
# Create the venv only if missing (recreating fails while a server runs from it)
VENV_CREATE := if not exist .venv $(SYS_PY) -m venv .venv
else
SYS_PY   := python3
VENV_PY  := .venv/bin/python
RMRF     := rm -rf
DIST     := frontend/dist
VENV_CREATE := test -d .venv || $(SYS_PY) -m venv .venv
endif

BACKEND  := backend
FRONTEND := frontend
PORT     ?= 8000

q ?= The Matrix
m ?= update schema
RT ?= 0
RATING ?= 6
VOTES ?= 1000
N ?= 100

.DEFAULT_GOAL := help
.PHONY: help install venv db migrate migration backend frontend dev-info \
        build typecheck scrape scrape-save seed bulk dataset populate \
        enrich-rt enrich-meta docker-up docker-down clean

help:
	@echo Movie Rating Scraper - targets:
	@echo   make install       - create venv, install backend + frontend deps + Chromium
	@echo   make db            - create the movie_scraper database and run migrations
	@echo   make migrate       - apply pending Alembic migrations
	@echo   make migration m=  - autogenerate a new migration with message m
	@echo   make backend       - run the FastAPI dev server on port $(PORT)
	@echo   make frontend      - run the Vite dev server on port 5173
	@echo   make build         - production frontend build
	@echo   make typecheck     - TypeScript check of the frontend
	@echo   make scrape q=     - scrape a movie and print JSON, e.g. make scrape q="Dune"
	@echo   make scrape-save q=- scrape a movie and store it in the DB
	@echo   make seed          - scrape + store a starter set of movies
	@echo   make bulk          - import IMDb Top 250 + Most Popular; RT=25 also adds RT scores
	@echo   make dataset       - mass-import IMDb official datasets; RATING=6 VOTES=1000
	@echo   make populate      - full library: dataset + charts + RT scores, e.g. make populate RT=25
	@echo   make enrich-rt     - backfill RT scores for IMDb-only movies: make enrich-rt N=100
	@echo   make enrich-meta   - backfill posters/plot/cast for movies missing them: make enrich-meta N=100
	@echo   make docker-up     - build and start the full stack with Docker
	@echo   make docker-down   - stop the Docker stack
	@echo   make clean         - remove build artifacts
	@echo Run backend and frontend in two separate terminals for local dev.

install: venv ## Install all dependencies (backend venv + Chromium + frontend)
	cd $(BACKEND) && $(VENV_PY) -m pip install -r requirements.txt
	cd $(BACKEND) && $(VENV_PY) -m playwright install chromium
	cd $(FRONTEND) && npm install

venv: ## Create the backend virtualenv if missing
	cd $(BACKEND) && $(VENV_CREATE)

db: ## Create the database and apply migrations
	cd $(BACKEND) && $(VENV_PY) scripts/create_db.py
	cd $(BACKEND) && $(VENV_PY) -m alembic upgrade head

migrate: ## Apply pending Alembic migrations
	cd $(BACKEND) && $(VENV_PY) -m alembic upgrade head

migration: ## Autogenerate a migration: make migration m="message"
	cd $(BACKEND) && $(VENV_PY) -m alembic revision --autogenerate -m "$(m)"

backend: ## Run the FastAPI dev server (reload) on PORT (default 8000)
	cd $(BACKEND) && $(VENV_PY) -m uvicorn app.main:app --reload --port $(PORT)

frontend: ## Run the Vite dev server
	cd $(FRONTEND) && npm run dev

build: ## Production frontend build (frontend/dist)
	cd $(FRONTEND) && npm run build

typecheck: ## TypeScript check
	cd $(FRONTEND) && npx tsc -b

scrape: ## Scrape a movie and print JSON: make scrape q="Title"
	cd $(BACKEND) && $(VENV_PY) -m app.scrapers.cli "$(q)"

scrape-save: ## Scrape a movie and store it: make scrape-save q="Title"
	cd $(BACKEND) && $(VENV_PY) -m app.scrapers.cli "$(q)" --save

bulk: ## Import IMDb Top 250 + Most Popular charts: make bulk RT=25
	cd $(BACKEND) && $(VENV_PY) -m app.scrapers.bulk --rt-limit $(RT)

dataset: ## Mass-import from IMDb official datasets: make dataset RATING=6 VOTES=1000
	cd $(BACKEND) && $(VENV_PY) -m app.scrapers.imdb_dataset --min-rating $(RATING) --min-votes $(VOTES)

populate: ## One-shot full library: dataset (~32k movies) + charts (posters/plots for ~350 popular) + RT scores for the top RT: make populate RT=25
	cd $(BACKEND) && $(VENV_PY) -m app.scrapers.imdb_dataset --min-rating $(RATING) --min-votes $(VOTES)
	cd $(BACKEND) && $(VENV_PY) -m app.scrapers.bulk --rt-limit $(RT)

enrich-rt: ## Backfill RT scores for the N most-popular IMDb-only movies: make enrich-rt N=100
	cd $(BACKEND) && $(VENV_PY) -m app.scrapers.enrich_rt --limit $(N)

enrich-meta: ## Backfill posters/plot/cast for the N most-popular movies missing them: make enrich-meta N=100
	cd $(BACKEND) && $(VENV_PY) -m app.scrapers.enrich_meta --limit $(N)

seed: ## Scrape + store a starter library
	cd $(BACKEND) && $(VENV_PY) -m app.scrapers.cli "The Matrix" --save
	cd $(BACKEND) && $(VENV_PY) -m app.scrapers.cli "Inception" --save
	cd $(BACKEND) && $(VENV_PY) -m app.scrapers.cli "Oppenheimer" --save
	cd $(BACKEND) && $(VENV_PY) -m app.scrapers.cli "Interstellar" --save
	cd $(BACKEND) && $(VENV_PY) -m app.scrapers.cli "The Dark Knight" --save

docker-up: ## Build and start db + backend + frontend with Docker
	docker compose up --build -d

docker-down: ## Stop the Docker stack
	docker compose down

clean: ## Remove build artifacts
	-$(RMRF) $(DIST)
