import type { Movie } from "../types";
import { normalize, scoreLevel } from "../lib/score";

export function ScoreBadges({ movie }: { movie: Movie }) {
  return (
    <div className="scores">
      {movie.imdb_score != null && (
        <span
          className={`score lvl-${scoreLevel(normalize(movie.imdb_score, 10))}`}
          title="IMDb rating"
        >
          <b>IMDb</b> {movie.imdb_score.toFixed(1)}
        </span>
      )}
      {movie.rt_tomatometer != null && (
        <span
          className={`score lvl-${scoreLevel(movie.rt_tomatometer)}`}
          title="Rotten Tomatoes — Tomatometer (critics)"
        >
          🍅 {movie.rt_tomatometer}%
        </span>
      )}
      {movie.rt_audience != null && (
        <span
          className={`score lvl-${scoreLevel(movie.rt_audience)}`}
          title="Rotten Tomatoes — Audience score"
        >
          🍿 {movie.rt_audience}%
        </span>
      )}
    </div>
  );
}
