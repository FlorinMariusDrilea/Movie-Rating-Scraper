import { useEffect, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Bar,
  BarChart,
  Cell,
  LabelList,
  ResponsiveContainer,
  XAxis,
  YAxis,
} from "recharts";
import { api } from "../lib/api";
import type { Movie, SearchResponse } from "../types";
import { LEVEL_COLORS, formatVotes, normalize, scoreLevel } from "../lib/score";
import { SimilarMovies } from "./SimilarMovies";

interface Props {
  movie: Movie;
  onClose: () => void;
  onUpdated: (movie: Movie) => void;
}

interface ChartRow {
  name: string;
  pct: number;
  label: string;
  votes: string;
}

function buildChartData(movie: Movie): ChartRow[] {
  const rows: ChartRow[] = [];
  for (const r of movie.ratings) {
    const pct = normalize(r.score, r.scale);
    if (r.source === "imdb") {
      rows.push({ name: "IMDb", pct, label: `${r.score.toFixed(1)}/10`, votes: formatVotes(r.votes) });
    } else if (r.source === "rt_tomatometer") {
      rows.push({ name: "RT Critics", pct, label: `${r.score}%`, votes: formatVotes(r.votes) });
    } else if (r.source === "rt_audience") {
      rows.push({ name: "RT Audience", pct, label: `${r.score}%`, votes: formatVotes(r.votes) });
    }
  }
  return rows;
}

export function MovieDetail({ movie, onClose, onUpdated }: Props) {
  const [imgError, setImgError] = useState(false);
  const queryClient = useQueryClient();
  const chartData = buildChartData(movie);

  // Close on Escape.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  const rescrape = useMutation({
    mutationFn: async () => {
      const { data } = await api.post<SearchResponse>("/api/movies/scrape", {
        query: movie.title,
        force: true,
      });
      return data;
    },
    onSuccess: (res) => {
      if (res.movie) onUpdated(res.movie);
      queryClient.invalidateQueries({ queryKey: ["movies"] });
    },
  });

  const scrapedAgo = movie.last_scraped_at
    ? new Date(movie.last_scraped_at).toLocaleString()
    : "never";

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div
        className="modal"
        role="dialog"
        aria-modal="true"
        aria-label={movie.title}
        onClick={(e) => e.stopPropagation()}
      >
        <button className="modal-close" onClick={onClose} aria-label="Close">
          ✕
        </button>

        <div className="modal-grid">
          <div className="modal-poster">
            {movie.poster_url && !imgError ? (
              <img
                src={movie.poster_url}
                alt={movie.title}
                referrerPolicy="no-referrer"
                onError={() => setImgError(true)}
              />
            ) : (
              <div className="poster-placeholder">🎬</div>
            )}
          </div>

          <div className="modal-info">
            <h2>
              {movie.title}
              {movie.year != null && <span className="modal-year"> ({movie.year})</span>}
            </h2>

            <div className="modal-meta">
              {movie.runtime_minutes != null && <span>{movie.runtime_minutes} min</span>}
              {movie.director && <span>Dir. {movie.director}</span>}
            </div>

            <div className="genres">
              {movie.genres.map((g) => (
                <span key={g} className="genre-tag">
                  {g}
                </span>
              ))}
            </div>

            {chartData.length > 0 ? (
              <div className="chart-wrap">
                <ResponsiveContainer width="100%" height={chartData.length * 44 + 10}>
                  <BarChart
                    data={chartData}
                    layout="vertical"
                    margin={{ top: 0, right: 88, bottom: 0, left: 0 }}
                  >
                    <XAxis type="number" domain={[0, 100]} hide />
                    <YAxis
                      type="category"
                      dataKey="name"
                      width={92}
                      tickLine={false}
                      axisLine={false}
                      tick={{ fill: "#8b90a0", fontSize: 12 }}
                    />
                    <Bar dataKey="pct" barSize={16} radius={[4, 4, 4, 4]} background={{ fill: "#262a38", radius: 4 }}>
                      {chartData.map((row) => (
                        <Cell key={row.name} fill={LEVEL_COLORS[scoreLevel(row.pct)]} />
                      ))}
                      <LabelList
                        dataKey="label"
                        position="right"
                        style={{ fill: "#e6e8ee", fontSize: 12, fontWeight: 600 }}
                      />
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
                <div className="votes-row">
                  {chartData
                    .filter((r) => r.votes)
                    .map((r) => (
                      <span key={r.name} className="muted">
                        {r.name}: {r.votes} votes
                      </span>
                    ))}
                </div>
              </div>
            ) : (
              <p className="muted">No ratings scraped for this movie yet.</p>
            )}

            {movie.plot && <p className="modal-plot">{movie.plot}</p>}

            {movie.cast_members && movie.cast_members.length > 0 && (
              <div className="cast">
                <span className="cast-label">Cast</span>
                {movie.cast_members.map((c) => (
                  <span key={c} className="cast-chip">
                    {c}
                  </span>
                ))}
              </div>
            )}

            <SimilarMovies movie={movie} onSelect={onUpdated} />

            <div className="modal-footer">
              <div className="card-links">
                {movie.imdb_url && (
                  <a href={movie.imdb_url} target="_blank" rel="noreferrer">
                    IMDb ↗
                  </a>
                )}
                {movie.rt_url && (
                  <a href={movie.rt_url} target="_blank" rel="noreferrer">
                    Rotten Tomatoes ↗
                  </a>
                )}
              </div>
              <div className="scrape-info">
                <span className="muted">Scraped: {scrapedAgo}</span>
                <button
                  className="rescrape-btn"
                  onClick={() => rescrape.mutate()}
                  disabled={rescrape.isPending}
                >
                  {rescrape.isPending ? "Re-scraping…" : "↻ Re-scrape"}
                </button>
              </div>
              {rescrape.isError && (
                <span className="error-text">Re-scrape failed — try again later.</span>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
