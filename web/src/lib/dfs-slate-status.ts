import type { DFSSlateSummary } from "@/lib/api";

/** Display status for slate directory — mirrors backend lock/freshness semantics. */
export type SlateDisplayStatus = "UNLOCKED" | "LOCKED" | "UPCOMING" | "STALE";

export function normPlayerName(name: string): string {
  return (name || "").trim().toLowerCase();
}

/** Lock time has passed (or start_time missing → treat as locked). */
export function isSlateLocked(startTime: string | null | undefined): boolean {
  if (!startTime) return true;
  const ms = Date.parse(startTime);
  if (!Number.isFinite(ms)) return true;
  return Date.now() >= ms;
}

/**
 * UNLOCKED — today's slate, lock time not reached
 * LOCKED  — now >= start_time (or missing start_time)
 * UPCOMING — future slate date, not yet locked
 * STALE   — prior-date slate still published (not current, not upcoming)
 */
export function getSlateDisplayStatus(slate: DFSSlateSummary): SlateDisplayStatus {
  if (isSlateLocked(slate.start_time)) return "LOCKED";
  if (slate.is_current) return "UNLOCKED";
  const startMs = slate.start_time ? Date.parse(slate.start_time) : NaN;
  if (Number.isFinite(startMs) && startMs > Date.now()) return "UPCOMING";
  return "STALE";
}

export function formatSlateLockTime(startTime: string | null | undefined): string {
  if (!startTime) return "—";
  const d = new Date(startTime);
  if (Number.isNaN(d.getTime())) return "—";
  return d.toLocaleString([], {
    weekday: "short",
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

export function platformLabel(platform: string): string {
  if (platform === "draftkings") return "DraftKings";
  if (platform === "fanduel") return "FanDuel";
  return platform;
}
