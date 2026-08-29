/**
 * Customer-facing market filters over canonical SBEvent markets.
 * Never invents odds, fair odds, or bookmaker availability.
 */

import type { SBEvent, SBMarket, SBBookLine } from "./sbevent";

export type LineMode = "main" | "alt" | "all";
export type PeriodGroup = "full" | "1h" | "2h" | "quarter" | "period" | "inning" | "other";
export type GameState = "LIVE" | "UPCOMING" | "FINAL";

const FULL_GAME = new Set(["", "game", "ft", "full", "regulation", "reg"]);
const CORE_BET_TYPES = new Set(["moneyline", "spread", "total", "over_under"]);

export const PREFERRED_PAGE_SIZE = 12;
/** Hard ceiling for a customer-facing results page (Live Odds / Arbitrage). */
export const MAX_PAGE_SIZE = 15;
/** Two pages at max density: 15 × 2. Default board fill target is 2 × 12. */
export const MAX_BOARD_ITEMS = 30;
export const BOARD_FILL_TO = PREFERRED_PAGE_SIZE * 2;

export function periodGroup(periodId: string | null | undefined): PeriodGroup {
  const p = (periodId || "").trim().toLowerCase();
  if (FULL_GAME.has(p)) return "full";
  if (p === "1h" || p === "1sthalf" || p === "firsthalf") return "1h";
  if (p === "2h" || p === "2ndhalf" || p === "secondhalf") return "2h";
  if (/^\d+q$/.test(p) || p.includes("quarter")) return "quarter";
  if (/^\d+p$/.test(p) || p.includes("period")) return "period";
  if (/^\d+i$/.test(p) || p.includes("inning") || /^1ix\d+$/.test(p)) return "inning";
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

export function bookHasPrice(b: SBBookLine | undefined | null): boolean {
  if (!b) return false;
  return b.moneyline != null || b.spread != null || b.over_under != null;
}

export function bookIsActive(b: SBBookLine | undefined | null): boolean {
  return Boolean(b && b.available !== false && bookHasPrice(b));
}

export function marketHasActivePrices(m: SBMarket | undefined | null): boolean {
  if (!m) return false;
  return (m.books || []).some((b) => bookIsActive(b));
}

export function marketIsMain(m: SBMarket): boolean {
  return Boolean(m.is_main_line || (m.books || []).some((b) => b.is_main_line));
}

export function eventHasActivePrices(evt: SBEvent | null | undefined): boolean {
  if (!evt) return false;
  return (evt.markets || []).some((m) => marketHasActivePrices(m));
}

export function filterMarkets(
  markets: SBMarket[],
  opts: { lineMode?: LineMode; period?: PeriodGroup | "all"; betTypes?: string[] } = {},
): SBMarket[] {
  const lineMode = opts.lineMode ?? "main";
  const period = opts.period ?? "full";
  const betTypes = opts.betTypes;
  const scoped = markets.filter((m) => {
    if (betTypes && !betTypes.includes(m.bet_type)) return false;
    const grp = periodGroup(m.period_id);
    if (period !== "all" && grp !== period) return false;
    return true;
  });
  if (lineMode === "all") return scoped;
  const anyMain = scoped.some((m) => marketIsMain(m));
  if (lineMode === "main") {
    if (anyMain) return scoped.filter((m) => marketIsMain(m));
    // SGO live payloads often omit isMainLine on byBookmaker. Do not hide
    // priced core markets just because the flag is missing.
    return scoped.filter((m) => CORE_BET_TYPES.has(m.bet_type) && marketHasActivePrices(m));
  }
  if (lineMode === "alt") {
    if (!anyMain) return [];
    return scoped.filter((m) => !marketIsMain(m));
  }
  return scoped;
}

/** If the selected period/main filter empties a priced event, relax period then line mode. */
export function marketsForExpandedEvent(
  evt: SBEvent,
  opts: { lineMode?: LineMode; period?: PeriodGroup | "all" } = {},
): { markets: SBMarket[]; relaxedPeriod: boolean; providerEmpty: boolean } {
  const lineMode = opts.lineMode ?? "main";
  const period = opts.period ?? "full";
  const providerEmpty = !eventHasActivePrices(evt);
  if (providerEmpty) return { markets: [], relaxedPeriod: false, providerEmpty: true };
  let markets = filterMarkets(evt.markets || [], { lineMode, period });
  if (markets.some((m) => marketHasActivePrices(m))) {
    return { markets, relaxedPeriod: false, providerEmpty: false };
  }
  if (period !== "all") {
    markets = filterMarkets(evt.markets || [], { lineMode, period: "all" });
    if (markets.some((m) => marketHasActivePrices(m))) {
      return { markets, relaxedPeriod: true, providerEmpty: false };
    }
  }
  markets = filterMarkets(evt.markets || [], { lineMode: "all", period: period === "all" ? "all" : period });
  if (markets.some((m) => marketHasActivePrices(m))) {
    return { markets, relaxedPeriod: period !== "all", providerEmpty: false };
  }
  markets = filterMarkets(evt.markets || [], { lineMode: "all", period: "all" });
  return { markets, relaxedPeriod: true, providerEmpty: false };
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

export function eventGameState(evt: SBEvent | null | undefined): GameState {
  const s = (evt?.status || "").toUpperCase();
  if (s === "LIVE" || s === "IN_PROGRESS") return "LIVE";
  if (s === "FINAL" || s === "COMPLETED" || s === "FINALIZED") return "FINAL";
  return "UPCOMING";
}

export function filterEventsByStatus(events: SBEvent[], status: GameState | "ALL"): SBEvent[] {
  if (status === "ALL") return events;
  return events.filter((e) => eventGameState(e) === status);
}

/** Parsed `start_time` only. Returns null when missing or unparseable — never invented. */
export function eventStartMs(evt: SBEvent | null | undefined): number | null {
  if (!evt?.start_time) return null;
  const ms = Date.parse(evt.start_time);
  return Number.isFinite(ms) ? ms : null;
}

function startOfLocalDay(ms: number): number {
  const d = new Date(ms);
  d.setHours(0, 0, 0, 0);
  return d.getTime();
}

export function isLocalCalendarDay(ms: number, nowMs: number): boolean {
  return startOfLocalDay(ms) === startOfLocalDay(nowMs);
}

export function eventMatchesQuery(evt: SBEvent, query: string): boolean {
  const q = query.trim().toLowerCase();
  if (!q) return true;
  const hn = evt.home_team.name.toLowerCase();
  const an = evt.away_team.name.toLowerCase();
  const ha = evt.home_team.abbreviation.toLowerCase();
  const aa = evt.away_team.abbreviation.toLowerCase();
  return hn.includes(q) || an.includes(q) || ha.includes(q) || aa.includes(q);
}

function bySoonestStart(a: SBEvent, b: SBEvent): number {
  const am = eventStartMs(a);
  const bm = eventStartMs(b);
  if (am == null && bm == null) return 0;
  if (am == null) return 1;
  if (bm == null) return -1;
  return am - bm;
}

function byRecentStart(a: SBEvent, b: SBEvent): number {
  return bySoonestStart(b, a);
}

export interface LiveOddsBoard<T = SBEvent> {
  items: T[];
  hidden: number;
  total: number;
  searched: boolean;
}

/**
 * Default Live Odds board: LIVE, then today's upcoming (local calendar of
 * real `start_time`), then the nearest upcoming events needed to fill a
 * normal two-page board. Distant schedule stays loaded for search.
 */
export function selectLiveOddsBoard(
  events: SBEvent[],
  opts: {
    search?: string;
    status?: GameState | "ALL";
    now?: number;
    fillTo?: number;
    maxBoard?: number;
  } = {},
): LiveOddsBoard {
  const now = opts.now ?? Date.now();
  const fillTo = opts.fillTo ?? BOARD_FILL_TO;
  const maxBoard = opts.maxBoard ?? MAX_BOARD_ITEMS;
  const q = (opts.search || "").trim();
  const status = opts.status ?? "ALL";
  const total = events.length;

  if (q) {
    const matched = events.filter((e) => eventMatchesQuery(e, q)).sort((a, b) => {
      const ga = eventGameState(a);
      const gb = eventGameState(b);
      const rank = (g: GameState) => (g === "LIVE" ? 0 : g === "UPCOMING" ? 1 : 2);
      const d = rank(ga) - rank(gb);
      if (d !== 0) return d;
      return bySoonestStart(a, b);
    });
    const items = matched.slice(0, maxBoard);
    return { items, hidden: matched.length - items.length, total: matched.length, searched: true };
  }

  if (status === "FINAL") {
    const items = [...events].sort(byRecentStart).slice(0, maxBoard);
    return { items, hidden: events.length - items.length, total, searched: false };
  }
  if (status === "LIVE") {
    const items = [...events].sort(bySoonestStart).slice(0, maxBoard);
    return { items, hidden: events.length - items.length, total, searched: false };
  }

  const live = events.filter((e) => eventGameState(e) === "LIVE").sort(bySoonestStart);
  const upcoming = events.filter((e) => eventGameState(e) === "UPCOMING");
  const todayUpcoming = upcoming
    .filter((e) => {
      const ms = eventStartMs(e);
      return ms != null && isLocalCalendarDay(ms, now);
    })
    .sort(bySoonestStart);

  const selected: SBEvent[] = [];
  const seen = new Set<string>();
  const take = (list: SBEvent[]) => {
    for (const e of list) {
      if (selected.length >= maxBoard) return;
      if (seen.has(e.id)) continue;
      seen.add(e.id);
      selected.push(e);
    }
  };

  take(live);
  take(todayUpcoming);

  if (selected.length < fillTo) {
    for (const e of upcoming.filter((e) => !seen.has(e.id)).sort(bySoonestStart)) {
      if (selected.length >= fillTo) break;
      seen.add(e.id);
      selected.push(e);
    }
  }

  return { items: selected, hidden: total - selected.length, total, searched: false };
}

export function capCustomerList<T>(items: T[], max = MAX_BOARD_ITEMS): LiveOddsBoard<T> {
  const total = items.length;
  const capped = items.slice(0, max);
  return { items: capped, hidden: total - capped.length, total, searched: false };
}

export function booksWithLine(market: SBMarket | undefined): SBBookLine[] {
  if (!market) return [];
  return market.books.filter((b) => bookIsActive(b));
}

export interface MergedBookRow {
  bookmaker: string;
  available: boolean;
  awayML: number | null;
  homeML: number | null;
  spread: number | null;
  totalOver: number | null;
  totalUnder: number | null;
}

/** Build per-bookmaker rows by merging across core market types for a single event. */
export function buildBookmakerRows(markets: SBMarket[]): MergedBookRow[] {
  const marketMap = new Map<string, SBMarket>();
  for (const m of markets) {
    const key = `${m.bet_type}::${m.side}`;
    if (!marketMap.has(key) || m.is_main_line || marketIsMain(m)) marketMap.set(key, m);
  }

  const awayMLMarket = marketMap.get("moneyline::away");
  const homeMLMarket = marketMap.get("moneyline::home");
  const spreadMarket = marketMap.get("spread::away") ?? marketMap.get("spread::home") ?? marketMap.get("spread::");
  const totalOverMarket = marketMap.get("over_under::over") ?? marketMap.get("total::over");
  const totalUnderMarket = marketMap.get("over_under::under") ?? marketMap.get("total::under");

  const bookmakerSet = new Set<string>();
  for (const m of [awayMLMarket, homeMLMarket, spreadMarket, totalOverMarket, totalUnderMarket]) {
    if (!m) continue;
    for (const b of m.books) {
      if (b.bookmaker && b.bookmaker.toLowerCase() !== "unknown") bookmakerSet.add(b.bookmaker);
    }
  }

  const rows: MergedBookRow[] = [];
  for (const bookmaker of bookmakerSet) {
    const awayB = awayMLMarket?.books.find((b) => b.bookmaker === bookmaker);
    const homeB = homeMLMarket?.books.find((b) => b.bookmaker === bookmaker);
    const spreadB = spreadMarket?.books.find((b) => b.bookmaker === bookmaker);
    const overB = totalOverMarket?.books.find((b) => b.bookmaker === bookmaker);
    const underB = totalUnderMarket?.books.find((b) => b.bookmaker === bookmaker);
    const available =
      bookIsActive(awayB) || bookIsActive(homeB) || bookIsActive(spreadB) || bookIsActive(overB) || bookIsActive(underB);
    if (!available) continue;
    rows.push({
      bookmaker,
      available: true,
      awayML: awayB?.moneyline ?? null,
      homeML: homeB?.moneyline ?? null,
      spread: spreadB?.spread ?? null,
      totalOver: overB?.over_under ?? null,
      totalUnder: underB?.over_under ?? null,
    });
  }
  return rows;
}

export interface TwoPageWindow<T> {
  items: T[];
  page: number;
  pages: number;
  pageSize: number;
  total: number;
  dense: boolean;
}

/**
 * Cap any result list at two customer pages.
 * Default: ~12/page, never above MAX_PAGE_SIZE (15).
 * Catalog mode (`allowDense`) may split a compact directory (e.g. 55 books) across two pages.
 */
export function twoPageWindow<T>(
  items: T[],
  page: number,
  preferred = PREFERRED_PAGE_SIZE,
  opts: { allowDense?: boolean } = {},
): TwoPageWindow<T> {
  const n = items.length;
  if (n === 0) {
    return { items: [], page: 1, pages: 1, pageSize: preferred, total: 0, dense: false };
  }
  let pageSize = preferred;
  let pages = 1;
  if (n <= preferred) {
    pageSize = n;
    pages = 1;
  } else if (n <= preferred * 2) {
    pageSize = preferred;
    pages = 2;
  } else if (opts.allowDense) {
    pageSize = Math.ceil(n / 2);
    pages = 2;
  } else {
    pageSize = Math.min(MAX_PAGE_SIZE, Math.ceil(Math.min(n, MAX_BOARD_ITEMS) / 2));
    pages = 2;
  }
  const safePage = Math.min(Math.max(1, page), pages);
  const start = (safePage - 1) * pageSize;
  return {
    items: items.slice(start, start + pageSize),
    page: safePage,
    pages,
    pageSize,
    total: n,
    dense: pageSize > preferred,
  };
}
