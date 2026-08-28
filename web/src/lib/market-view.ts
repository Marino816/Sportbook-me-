/**
 * Customer-facing market filters over canonical SBEvent markets.
 * Never invents odds, fair odds, or bookmaker availability.
 */

import type { SBEvent, SBMarket, SBBookLine } from "./sbevent";
import { gameState, type GameState } from "./live-scores";

export type LineMode = "main" | "alt" | "all";
export type PeriodGroup = "full" | "1h" | "2h" | "quarter" | "period" | "inning" | "other";

const FULL_GAME = new Set(["", "game", "ft", "full", "regulation"]);

export function periodGroup(periodId: string | null | undefined): PeriodGroup {
  const p = (periodId || "").trim().toLowerCase();
  if (FULL_GAME.has(p)) return "full";
  if (p === "1h" || p === "1sthalf" || p === "firsthalf") return "1h";
  if (p === "2h" || p === "2ndhalf" || p === "secondhalf") return "2h";
  if (/^\d+q$/.test(p) || p.includes("quarter")) return "quarter";
  if (/^\d+p$/.test(p) || p.includes("period")) return "period";
  if (/^\d+i$/.test(p) || p.includes("inning")) return "inning";
  if (p) return "other";
  return "full";
}

export function periodLabelForId(periodId: string | null | undefined): string {
  const g = periodGroup(periodId);
  const p = (periodId || "").toLowerCase();
  if (g === "full") return "Full Game";
  if (g === "1h") return "1st Half";
  if (g === "2h") return "2nd Half";
  return p.toUpperCase() || "Other";
}

export function filterMarkets(
  markets: SBMarket[],
  opts: { lineMode?: LineMode; period?: PeriodGroup | "all"; betTypes?: string[] } = {},
): SBMarket[] {
  const lineMode = opts.lineMode ?? "main";
  const period = opts.period ?? "full";
  const betTypes = opts.betTypes;
  return markets.filter((m) => {
    if (betTypes && !betTypes.includes(m.bet_type)) return false;
    const grp = periodGroup(m.period_id);
    if (period !== "all" && grp !== period) return false;
    if (lineMode === "main") return m.is_main_line || m.books.some((b) => b.is_main_line);
    if (lineMode === "alt") return !m.is_main_line && !m.books.some((b) => b.is_main_line);
    return true;
  });
}

export function presentPeriodGroups(markets: SBMarket[]): PeriodGroup[] {
  const seen = new Set<PeriodGroup>();
  for (const m of markets) seen.add(periodGroup(m.period_id));
  const order: PeriodGroup[] = ["full", "1h", "2h", "quarter", "period", "inning", "other"];
  return order.filter((g) => seen.has(g));
}

export function eventLastUpdated(evt: SBEvent | null | undefined): string | null {
  if (!evt) return null;
  let latest: string | null = null;
  for (const m of evt.markets || []) {
    for (const b of m.books || []) {
      if (b.last_updated && (!latest || b.last_updated > latest)) latest = b.last_updated;
    }
  }
  return latest;
}

export function formatFreshness(iso: string | null | undefined, fetchedAt?: number): string {
  const ms = iso ? Date.parse(iso) : fetchedAt;
  if (!ms || Number.isNaN(ms)) return "";
  const ago = Math.max(0, Date.now() - ms);
  if (ago < 60_000) return "Just now";
  if (ago < 3_600_000) return `${Math.round(ago / 60_000)} min ago`;
  return new Date(ms).toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
}

export function fairOddsForMarket(m: SBMarket | undefined): number | null {
  if (!m) return null;
  return m.fair_odds ?? null;
}

export function bookOddsForMarket(m: SBMarket | undefined): number | null {
  if (!m) return null;
  return m.book_odds ?? null;
}

export function filterEventsByStatus(events: SBEvent[], status: GameState | "ALL"): SBEvent[] {
  if (status === "ALL") return events;
  return events.filter((e) => gameState(e) === status);
}

export function booksWithLine(market: SBMarket | undefined): SBBookLine[] {
  if (!market) return [];
  return market.books.filter((b) => b.available !== false && (b.moneyline != null || b.spread != null || b.over_under != null));
}
