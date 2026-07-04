import axios from "axios";
import type {
  MovieFilters,
  MovieListResponse,
  Movie,
  RecommendationsResponse,
  SearchResponse,
} from "../types";

export const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

export const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 120000, // scraping can take a while
});

function buildParams(filters: MovieFilters): URLSearchParams {
  const params = new URLSearchParams();
  if (filters.q) params.set("q", filters.q);
  filters.genre?.forEach((g) => params.append("genre", g));
  if (filters.year_from != null) params.set("year_from", String(filters.year_from));
  if (filters.year_to != null) params.set("year_to", String(filters.year_to));
  if (filters.min_popularity != null)
    params.set("min_popularity", String(filters.min_popularity));
  if (filters.min_imdb != null) params.set("min_imdb", String(filters.min_imdb));
  if (filters.min_tomatometer != null)
    params.set("min_tomatometer", String(filters.min_tomatometer));
  if (filters.min_audience != null)
    params.set("min_audience", String(filters.min_audience));
  params.set("sort", filters.sort);
  params.set("order", filters.order);
  params.set("page", String(filters.page));
  params.set("page_size", String(filters.page_size));
  return params;
}

export async function fetchMovies(
  filters: MovieFilters,
): Promise<MovieListResponse> {
  const { data } = await api.get<MovieListResponse>("/api/movies", {
    params: buildParams(filters),
  });
  return data;
}

export async function fetchGenres(): Promise<string[]> {
  const { data } = await api.get<string[]>("/api/movies/genres");
  return data;
}

export async function fetchMovie(id: number): Promise<Movie> {
  const { data } = await api.get<Movie>(`/api/movies/${id}`);
  return data;
}

/** Cache-first search that scrapes and stores on a miss. */
export async function searchMovie(q: string): Promise<SearchResponse> {
  const { data } = await api.get<SearchResponse>("/api/movies/search", {
    params: { q },
  });
  return data;
}

/** Content-based recommendations seeded on one or more movie ids. */
export async function fetchRecommendations(
  seedIds: number[],
  limit = 10,
): Promise<RecommendationsResponse> {
  const params = new URLSearchParams();
  seedIds.forEach((id) => params.append("based_on", String(id)));
  params.set("limit", String(limit));
  const { data } = await api.get<RecommendationsResponse>(
    "/api/recommendations",
    { params },
  );
  return data;
}
