import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { fetchMovies, fetchRecommendations } from "../lib/api";
import type { Movie } from "../types";
import { MovieCard } from "./MovieCard";
import { SkeletonCard } from "./SkeletonCard";

interface Props {
  onSelect: (movie: Movie) => void;
}

export function RecommendationsView({ onSelect }: Props) {
  const [picked, setPicked] = useState<number[]>([]);

  // The 100 most popular movies as pickable chips — with a mass-imported
  // library, alphabetical order would surface obscure titles first.
  const library = useQuery({
    queryKey: ["movies", "library"],
    queryFn: () =>
      fetchMovies({ sort: "popularity", order: "desc", page: 1, page_size: 100 }),
  });

  const recs = useQuery({
    queryKey: ["recommendations", picked],
    queryFn: () => fetchRecommendations(picked, 12),
    enabled: picked.length > 0,
  });

  const toggle = (id: number) =>
    setPicked((prev) =>
      prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id],
    );

  const items = recs.data?.items ?? [];

  return (
    <main className="content">
      <section className="picks">
        <h2 className="picks-title">Pick movies you like</h2>
        <p className="muted">
          Recommendations blend genre overlap, rating similarity, and
          popularity.
        </p>
        <div className="picks-chips">
          {library.isLoading && <span className="muted">Loading library…</span>}
          {library.data?.items.map((m) => (
            <button
              key={m.id}
              className={`pick-chip ${picked.includes(m.id) ? "picked" : ""}`}
              onClick={() => toggle(m.id)}
            >
              {picked.includes(m.id) ? "✓ " : ""}
              {m.title}
              {m.year != null && <span className="pick-year"> {m.year}</span>}
            </button>
          ))}
        </div>
      </section>

      {picked.length === 0 ? (
        <div className="state-msg">
          <p className="state-title">Pick at least one movie</p>
          <p>Select a few favorites above to get tailored suggestions.</p>
        </div>
      ) : (
        <>
          <h2 className="picks-title">
            Recommended for you{" "}
            {recs.isFetching && <span className="muted">updating…</span>}
          </h2>
          {recs.isLoading ? (
            <div className="grid">
              {Array.from({ length: 4 }, (_, i) => (
                <SkeletonCard key={i} />
              ))}
            </div>
          ) : items.length === 0 ? (
            <div className="state-msg">
              <p className="state-title">No recommendations yet</p>
              <p>
                Your library may be too small — scrape a few more movies from
                the Browse tab.
              </p>
            </div>
          ) : (
            <div className="grid">
              {items.map(({ movie, reasons, score }) => (
                <div key={movie.id} className="rec-item">
                  <MovieCard movie={movie} onSelect={onSelect} />
                  <div className="rec-reasons" title={`Match score ${(score * 100).toFixed(0)}%`}>
                    {reasons.slice(0, 2).map((r) => (
                      <span key={r} className="reason-chip">
                        {r}
                      </span>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          )}
        </>
      )}
    </main>
  );
}
