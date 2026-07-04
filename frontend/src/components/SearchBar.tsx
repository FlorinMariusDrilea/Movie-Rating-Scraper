import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { searchMovie } from "../lib/api";

interface Props {
  /** Called on every keystroke — drives the real-time library filter. */
  onType: (q: string) => void;
}

export function SearchBar({ onType }: Props) {
  const [query, setQuery] = useState("");
  const [message, setMessage] = useState<string | null>(null);
  const queryClient = useQueryClient();

  const mutation = useMutation({
    mutationFn: (q: string) => searchMovie(q),
    onSuccess: (res) => {
      if (res.source === "not_found" || !res.movie) {
        setMessage(`No results for “${query}”.`);
        return;
      }
      const verb = res.source === "cache" ? "Found (cached)" : "Scraped";
      setMessage(`${verb}: ${res.movie.title} (${res.movie.year ?? "—"})`);
      // Refresh the grid + genres so the new movie shows up.
      queryClient.invalidateQueries({ queryKey: ["movies"] });
      queryClient.invalidateQueries({ queryKey: ["genres"] });
    },
    onError: () => setMessage("Something went wrong while searching."),
  });

  const handleChange = (value: string) => {
    setQuery(value);
    setMessage(null);
    onType(value); // live-filter the grid as the user types
  };

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    const q = query.trim();
    if (q) mutation.mutate(q);
  };

  return (
    <form className="searchbar" onSubmit={submit}>
      <input
        type="text"
        placeholder="Type to search the library · Enter to scrape a new movie…"
        value={query}
        onChange={(e) => handleChange(e.target.value)}
      />
      <button type="submit" disabled={mutation.isPending}>
        {mutation.isPending ? "Scraping…" : "Scrape"}
      </button>
      {message && <span className="search-msg">{message}</span>}
    </form>
  );
}
