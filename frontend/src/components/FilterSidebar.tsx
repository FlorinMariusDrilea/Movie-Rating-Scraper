import { useQuery } from "@tanstack/react-query";
import { fetchGenres } from "../lib/api";
import type { MovieFilters } from "../types";

interface Props {
  filters: MovieFilters;
  onChange: (patch: Partial<MovieFilters>) => void;
  onReset: () => void;
}

export function FilterSidebar({ filters, onChange, onReset }: Props) {
  const { data: genres = [] } = useQuery({
    queryKey: ["genres"],
    queryFn: fetchGenres,
  });

  const toggleGenre = (g: string) => {
    const current = filters.genre ?? [];
    const next = current.includes(g)
      ? current.filter((x) => x !== g)
      : [...current, g];
    onChange({ genre: next.length ? next : undefined, page: 1 });
  };

  return (
    <aside className="sidebar">
      <div className="sidebar-head">
        <h2>Filters</h2>
        <button className="link-btn" onClick={onReset}>
          Reset
        </button>
      </div>

      <section className="filter-group">
        <label>Min IMDb: {filters.min_imdb ?? 0}</label>
        <input
          type="range"
          min={0}
          max={10}
          step={0.5}
          value={filters.min_imdb ?? 0}
          onChange={(e) =>
            onChange({
              min_imdb: Number(e.target.value) || undefined,
              page: 1,
            })
          }
        />
      </section>

      <section className="filter-group">
        <label>Min Tomatometer: {filters.min_tomatometer ?? 0}%</label>
        <input
          type="range"
          min={0}
          max={100}
          step={5}
          value={filters.min_tomatometer ?? 0}
          onChange={(e) =>
            onChange({
              min_tomatometer: Number(e.target.value) || undefined,
              page: 1,
            })
          }
        />
      </section>

      <section className="filter-group">
        <label>Min Audience: {filters.min_audience ?? 0}%</label>
        <input
          type="range"
          min={0}
          max={100}
          step={5}
          value={filters.min_audience ?? 0}
          onChange={(e) =>
            onChange({
              min_audience: Number(e.target.value) || undefined,
              page: 1,
            })
          }
        />
      </section>

      <section className="filter-group">
        <label>Year range</label>
        <div className="year-range">
          <input
            type="number"
            placeholder="From"
            value={filters.year_from ?? ""}
            onChange={(e) =>
              onChange({
                year_from: e.target.value ? Number(e.target.value) : undefined,
                page: 1,
              })
            }
          />
          <span>–</span>
          <input
            type="number"
            placeholder="To"
            value={filters.year_to ?? ""}
            onChange={(e) =>
              onChange({
                year_to: e.target.value ? Number(e.target.value) : undefined,
                page: 1,
              })
            }
          />
        </div>
      </section>

      <section className="filter-group">
        <label>Genres</label>
        <div className="genre-list">
          {genres.length === 0 && <span className="muted">No genres yet</span>}
          {genres.map((g) => (
            <label key={g} className="genre-check">
              <input
                type="checkbox"
                checked={filters.genre?.includes(g) ?? false}
                onChange={() => toggleGenre(g)}
              />
              {g}
            </label>
          ))}
        </div>
      </section>
    </aside>
  );
}
