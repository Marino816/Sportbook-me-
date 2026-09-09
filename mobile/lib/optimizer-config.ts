export const OPTIMIZER_SPORTS = ["mlb", "nba", "nfl"] as const;

export const STRATEGIES = [
  { id: "balanced", label: "Balanced" },
  { id: "cash", label: "Cash" },
  { id: "gpp", label: "GPP" },
  { id: "aggressive", label: "Aggressive" },
  { id: "nuclear", label: "Nuclear" },
] as const;

export const MLB_STACK_OPTIONS = [
  { id: 0, label: "Off" },
  { id: 2, label: "2" },
  { id: 3, label: "3" },
  { id: 4, label: "4" },
  { id: 5, label: "5" },
] as const;

export const EXPOSURE_OPTIONS = [
  { id: 0, label: "Off" },
  { id: 20, label: "20%" },
  { id: 30, label: "30%" },
  { id: 40, label: "40%" },
  { id: 50, label: "50%" },
] as const;

export function salaryCapFor(sport: string, platform: string): number {
  const s = (sport || "").toUpperCase();
  const p = (platform || "").toLowerCase();
  if (s === "MLB" && p === "fanduel") return 35000;
  if ((s === "NFL" || s === "NCAAF") && p === "fanduel") return 60000;
  return 50000;
}

export function formatSalary(n: number | null | undefined): string {
  if (n == null || Number.isNaN(Number(n))) return "—";
  const v = Number(n);
  if (v >= 1000) return `$${(v / 1000).toFixed(v % 1000 === 0 ? 0 : 1)}K`;
  return `$${v.toLocaleString()}`;
}

export { formatSourceLabel, formatProjectionSource, lineupProjectionIntegrity } from "./source-label.mjs";
