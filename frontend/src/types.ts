export interface Rating {
  source: string;
  score: number;
  scale: number;
  votes: number | null;
  url: string | null;
}

export interface Movie {
  id: number;
  imdb_id: string | null;
  title: string;
  year: number | null;
  plot: string | null;
  runtime_minutes: number | null;
  poster_url: string | null;
  director: string | null;
  cast_members: string[] | null;
  popularity: number | null;
  imdb_url: string | null;
  rt_url: string | null;
  last_scraped_at: string | null;
  genres: string[];
  imdb_score: number | null;
  rt_tomatometer: number | null;
  rt_audience: number | null;
  ratings: Rating[];
}

export interface MovieListResponse {
  items: Movie[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
}

export interface SearchResponse {
  source: string;
  movie: Movie | null;
}

export interface Recommendation {
  movie: Movie;
  score: number;
  reasons: string[];
}

export interface RecommendationsResponse {
  seeds: Movie[];
  items: Recommendation[];
}

export type SortKey =
  | "popularity"
  | "imdb"
  | "rt_tomatometer"
  | "rt_audience"
  | "year"
  | "title";

export interface MovieFilters {
  q?: string;
  genre?: string[];
  year_from?: number;
  year_to?: number;
  min_popularity?: number;
  min_imdb?: number;
  min_tomatometer?: number;
  min_audience?: number;
  sort: SortKey;
  order: "asc" | "desc";
  page: number;
  page_size: number;
}
