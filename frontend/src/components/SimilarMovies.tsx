import { useQuery } from "@tanstack/react-query";
import { fetchRecommendations } from "../lib/api";
import type { Movie } from "../types";

interface Props {
  movie: Movie;
  onSelect: (movie: Movie) => void;
}

export function SimilarMovies({ movie, onSelect }: Props) {
  const { data, isLoading } = useQuery({
    queryKey: ["recommendations", [movie.id]],
    queryFn: () => fetchRecommendations([movie.id], 6),
  });

  const items = data?.items ?? [];
  if (!isLoading && items.length === 0) return null;

  return (
    <div className="similar">
      <h3 className="similar-title">More like this</h3>
      {isLoading ? (
        <span className="muted">Finding similar movies…</span>
      ) : (
        <div className="similar-row">
          {items.map(({ movie: m, reasons }) => (
            <button
              key={m.id}
              className="similar-card"
              onClick={() => onSelect(m)}
              title={reasons.join(" · ")}
            >
              <span className="similar-name">{m.title}</span>
              <span className="similar-meta">
                {m.year ?? "—"}
                {m.imdb_score != null && ` · ★ ${m.imdb_score.toFixed(1)}`}
              </span>
              {reasons[0] && <span className="similar-reason">{reasons[0]}</span>}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
