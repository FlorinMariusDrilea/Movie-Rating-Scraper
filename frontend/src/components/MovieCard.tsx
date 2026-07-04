import { useState } from "react";
import type { Movie } from "../types";
import { ScoreBadges } from "./ScoreBadges";

interface Props {
  movie: Movie;
  onSelect: (movie: Movie) => void;
}

export function MovieCard({ movie, onSelect }: Props) {
  const [imgError, setImgError] = useState(false);
  const showPoster = movie.poster_url && !imgError;

  return (
    <article
      className="card-movie"
      tabIndex={0}
      role="button"
      aria-label={`${movie.title} — details`}
      onClick={() => onSelect(movie)}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          onSelect(movie);
        }
      }}
    >
      <div className="poster">
        {showPoster ? (
          <img
            src={movie.poster_url!}
            alt={movie.title}
            loading="lazy"
            referrerPolicy="no-referrer"
            onError={() => setImgError(true)}
          />
        ) : (
          <div className="poster-placeholder" title={movie.title}>
            🎬
          </div>
        )}

        {/* Plot teaser revealed on hover */}
        {movie.plot && (
          <div className="poster-hover">
            <p className="poster-plot">{movie.plot}</p>
            <span className="poster-cta">View details →</span>
          </div>
        )}

        {/* Always-visible score strip over a bottom scrim */}
        <div className="poster-scrim">
          <ScoreBadges movie={movie} />
        </div>
      </div>

      <div className="card-body">
        <h3 className="card-title" title={movie.title}>
          {movie.title}
        </h3>
        <div className="card-meta">
          <span>
            {movie.year ?? "—"}
            {movie.runtime_minutes ? ` · ${movie.runtime_minutes} min` : ""}
          </span>
          <span className="card-genres">{movie.genres.slice(0, 2).join(" · ")}</span>
        </div>
      </div>
    </article>
  );
}
