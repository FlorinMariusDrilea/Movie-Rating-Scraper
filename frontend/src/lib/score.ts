/** Normalize any rating to 0–100 (IMDb is 0–10, RT is already 0–100). */
export function normalize(score: number, scale: number): number {
  return Math.round((score / scale) * 100);
}

/** Quality bucket used for color coding. */
export function scoreLevel(pct: number): "good" | "ok" | "bad" {
  if (pct >= 70) return "good";
  if (pct >= 50) return "ok";
  return "bad";
}

/** Chart color per quality bucket (matches the CSS variables). */
export const LEVEL_COLORS: Record<ReturnType<typeof scoreLevel>, string> = {
  good: "#21c07a",
  ok: "#f5c518",
  bad: "#e5484d",
};

export function formatVotes(votes: number | null | undefined): string {
  if (votes == null) return "";
  if (votes >= 1_000_000) return `${(votes / 1_000_000).toFixed(1)}M`;
  if (votes >= 1_000) return `${Math.round(votes / 1_000)}K`;
  return String(votes);
}
