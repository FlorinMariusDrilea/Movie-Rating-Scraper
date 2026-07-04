import { lazy, Suspense, useMemo, useState } from "react";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { fetchMovies } from "./lib/api";
import type { Movie, MovieFilters, SortKey } from "./types";
import { useDebounce } from "./hooks/useDebounce";
import { SearchBar } from "./components/SearchBar";
import { FilterSidebar } from "./components/FilterSidebar";
import { MovieCard } from "./components/MovieCard";
import { RecommendationsView } from "./components/RecommendationsView";
import { SkeletonCard } from "./components/SkeletonCard";
import "./App.css";

// Lazy-loaded so Recharts lands in its own chunk, off the initial bundle.
const MovieDetail = lazy(() =>
  import("./components/MovieDetail").then((m) => ({ default: m.MovieDetail })),
);

const DEFAULT_FILTERS: MovieFilters = {
  sort: "popularity",
  order: "desc",
  page: 1,
  page_size: 24,
};

const PAGE_SIZES = [12, 24, 48, 96];

const SORT_OPTIONS: { key: SortKey; label: string }[] = [
  { key: "popularity", label: "Popularity" },
  { key: "imdb", label: "IMDb rating" },
  { key: "rt_tomatometer", label: "RT critics" },
  { key: "rt_audience", label: "RT audience" },
  { key: "year", label: "Year" },
  { key: "title", label: "Title" },
];

function countActiveFilters(f: MovieFilters): number {
  let n = 0;
  if (f.q) n++;
  if (f.genre?.length) n += f.genre.length;
  if (f.year_from != null) n++;
  if (f.year_to != null) n++;
  if (f.min_imdb != null) n++;
  if (f.min_tomatometer != null) n++;
  if (f.min_audience != null) n++;
  if (f.min_popularity != null) n++;
  return n;
}

function App() {
  const [filters, setFilters] = useState<MovieFilters>(DEFAULT_FILTERS);
  const [selected, setSelected] = useState<Movie | null>(null);
  const [view, setView] = useState<"browse" | "forYou">("browse");
  const debouncedFilters = useDebounce(filters, 350);

  const patch = (p: Partial<MovieFilters>) =>
    setFilters((prev) => ({ ...prev, ...p }));

  const query = useQuery({
    queryKey: ["movies", debouncedFilters],
    queryFn: () => fetchMovies(debouncedFilters),
    placeholderData: keepPreviousData,
  });

  const data = query.data;
  const movies = data?.items ?? [];
  const activeFilters = countActiveFilters(filters);

  const rangeLabel = useMemo(() => {
    if (!data || data.total === 0) return "No movies";
    const start = (data.page - 1) * data.page_size + 1;
    const end = Math.min(data.page * data.page_size, data.total);
    return `${start}–${end} of ${data.total}`;
  }, [data]);

  return (
    <div className="layout">
      <header className="topbar">
        <div className="brand">
          <h1>🎬 Movie Rating Scraper</h1>
          <p>IMDb &amp; Rotten Tomatoes, side by side</p>
        </div>
        <nav className="tabs">
          <button
            className={`tab ${view === "browse" ? "active" : ""}`}
            onClick={() => setView("browse")}
          >
            Browse
          </button>
          <button
            className={`tab ${view === "forYou" ? "active" : ""}`}
            onClick={() => setView("forYou")}
          >
            For You
          </button>
        </nav>
        <SearchBar
          onType={(q) => {
            setView("browse");
            patch({ q: q.trim() || undefined, page: 1 });
          }}
        />
      </header>

      {view === "forYou" ? (
        <RecommendationsView onSelect={setSelected} />
      ) : (
      <div className="main">
        <FilterSidebar
          filters={filters}
          onChange={patch}
          onReset={() => setFilters(DEFAULT_FILTERS)}
        />

        <main className="content">
          <div className="toolbar">
            <span className="range-label">
              {rangeLabel}
              {activeFilters > 0 && (
                <span className="filter-count">
                  {activeFilters} filter{activeFilters > 1 ? "s" : ""} active
                </span>
              )}
            </span>
            <div className="sort-controls">
              <label>Sort by</label>
              <select
                value={filters.sort}
                onChange={(e) =>
                  patch({ sort: e.target.value as SortKey, page: 1 })
                }
              >
                {SORT_OPTIONS.map((o) => (
                  <option key={o.key} value={o.key}>
                    {o.label}
                  </option>
                ))}
              </select>
              <button
                className="order-btn"
                title="Toggle order"
                onClick={() =>
                  patch({
                    order: filters.order === "desc" ? "asc" : "desc",
                    page: 1,
                  })
                }
              >
                {filters.order === "desc" ? "↓ Desc" : "↑ Asc"}
              </button>
              <label>Show</label>
              <select
                value={filters.page_size}
                onChange={(e) =>
                  patch({ page_size: Number(e.target.value), page: 1 })
                }
              >
                {PAGE_SIZES.map((n) => (
                  <option key={n} value={n}>
                    {n}
                  </option>
                ))}
              </select>
            </div>
          </div>

          {query.isError && (
            <div className="state-msg error">
              Couldn’t load movies. Is the API running on :8000?
            </div>
          )}

          {!query.isError && movies.length === 0 && !query.isLoading && (
            <div className="state-msg">
              {filters.q ? (
                <>
                  <p className="state-title">No matches for “{filters.q}”</p>
                  <p>
                    Not in the library yet — press Enter (or hit Scrape) to
                    fetch it from IMDb &amp; Rotten Tomatoes.
                  </p>
                </>
              ) : (
                <>
                  <p className="state-title">Nothing here yet</p>
                  <p>
                    Use the search bar above to scrape a movie, or reset your
                    filters.
                  </p>
                </>
              )}
            </div>
          )}

          <div className={`grid ${query.isFetching ? "grid-fetching" : ""}`}>
            {query.isLoading
              ? Array.from({ length: 12 }, (_, i) => <SkeletonCard key={i} />)
              : movies.map((m) => (
                  <MovieCard key={m.id} movie={m} onSelect={setSelected} />
                ))}
          </div>

          {data && data.pages > 1 && (
            <div className="pagination">
              <button
                disabled={data.page <= 1}
                onClick={() => patch({ page: data.page - 1 })}
              >
                ← Prev
              </button>
              <span>
                Page {data.page} / {data.pages}
              </span>
              <button
                disabled={data.page >= data.pages}
                onClick={() => patch({ page: data.page + 1 })}
              >
                Next →
              </button>
            </div>
          )}
        </main>
      </div>
      )}

      {selected && (
        <Suspense fallback={null}>
          <MovieDetail
            movie={selected}
            onClose={() => setSelected(null)}
            onUpdated={setSelected}
          />
        </Suspense>
      )}
    </div>
  );
}

export default App;
