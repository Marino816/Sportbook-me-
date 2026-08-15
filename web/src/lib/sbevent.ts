/**
 * Shared SB Event TypeScript interface — ONE shape consumed by all pages.
 *
 * Matches the canonical backend /api/sgo/events SBEvent JSON output
 * built from the official SportsGameOdds SDK models.
 *
 * Every consumer MUST pass raw JSON through `normalizeEvents()` (or
 * `normalizeEvent()`) so that one bad/missing SGO field can never crash
 * the React tree. The backend contract is best-effort; the frontend is
 * the last line of defense.
 */

export interface SBTeam {
  name: string;
  abbreviation: string;
  team_id: string;
  logo_url?: string | null;
}

export interface SBPlayer {
  player_id: string;
  name: string;
  team_id: string;
  position: string;
  headshot_url?: string | null;
}

export interface SBBookLine {
  bookmaker: string;
  available: boolean;
  moneyline: number | null;
  spread: number | null;
  over_under: number | null;
  is_main_line: boolean;
}

export interface SBMarket {
  odd_id: string;
  market_name: string;
  bet_type: string;
  side: string;
  player_id: string;
  player_name: string;
  stat_entity_id: string;
  stat_id: string;
  fair_odds: number | null;
  fair_spread: number | null;
  fair_over_under: number | null;
  books: SBBookLine[];
}

export interface SBEvent {
  id: string;
  sport: string;
  league: string;
  start_time: string | null;
  status: string;
  status_display: string;
  venue: string;
  home_team: SBTeam;
  away_team: SBTeam;
  home_score: number | null;
  away_score: number | null;
  period: string | null;
  players: SBPlayer[];
  markets: SBMarket[];
  bookmakers: string[];
}

/* ── Defensive normalization helpers ─────────────────────────────── */

/** Coerce any value to a string, or fall back to `fallback`. */
function asStr(v: unknown, fallback = ""): string {
  if (typeof v === "string") return v;
  if (v === null || v === undefined) return fallback;
  return String(v);
}

/** Coerce any value to a finite number, or null. */
function asNum(v: unknown): number | null {
  if (v === null || v === undefined || v === "") return null;
  const n = typeof v === "number" ? v : Number(v);
  return Number.isFinite(n) ? n : null;
}

/** Coerce any value to a boolean. */
function asBool(v: unknown, fallback = false): boolean {
  if (typeof v === "boolean") return v;
  if (v === null || v === undefined) return fallback;
  return Boolean(v);
}

/** Coerce any value to an array, or []. */
function asArray(v: unknown): unknown[] {
  return Array.isArray(v) ? v : [];
}

function asTeam(v: unknown): SBTeam {
  const t = (v && typeof v === "object" ? v : {}) as Record<string, unknown>;
  const name = asStr(t.name);
  const abbreviation = asStr(t.abbreviation);
  return {
    name,
    abbreviation: abbreviation || name,
    team_id: asStr(t.team_id ?? t.id),
    logo_url: (t.logo_url as string) || null,
  };
}

function asPlayer(v: unknown): SBPlayer {
  const p = (v && typeof v === "object" ? v : {}) as Record<string, unknown>;
  return {
    player_id: asStr(p.player_id ?? p.id),
    name: asStr(p.name ?? p.player_name),
    team_id: asStr(p.team_id ?? p.team),
    position: asStr(p.position),
    headshot_url: (p.headshot_url as string) || null,
  };
}

/** Extract a numeric score from either a number or an SGO score dict {points}. */
function asScore(v: unknown): number | null {
  if (v === null || v === undefined || v === "") return null;
  if (typeof v === "number") return Number.isFinite(v) ? v : null;
  if (typeof v === "object") {
    const d = v as Record<string, unknown>;
    const pts = d.points;
    if (typeof pts === "number") return pts;
    if (pts !== null && pts !== undefined) {
      const n = Number(pts);
      return Number.isFinite(n) ? n : null;
    }
    return null;
  }
  const n = Number(v);
  return Number.isFinite(n) ? n : null;
}

function asBook(v: unknown): SBBookLine {
  const b = (v && typeof v === "object" ? v : {}) as Record<string, unknown>;
  return {
    bookmaker: asStr(b.bookmaker),
    available: asBool(b.available, true),
    moneyline: asNum(b.moneyline),
    spread: asNum(b.spread),
    over_under: asNum(b.over_under),
    is_main_line: asBool(b.is_main_line, false),
  };
}

function asMarket(v: unknown): SBMarket {
  const m = (v && typeof v === "object" ? v : {}) as Record<string, unknown>;
  return {
    odd_id: asStr(m.odd_id ?? m.id),
    market_name: asStr(m.market_name ?? m.name),
    bet_type: asStr(m.bet_type),
    side: asStr(m.side),
    player_id: asStr(m.player_id),
    player_name: asStr(m.player_name),
    stat_entity_id: asStr(m.stat_entity_id),
    stat_id: asStr(m.stat_id),
    fair_odds: asNum(m.fair_odds),
    fair_spread: asNum(m.fair_spread),
    fair_over_under: asNum(m.fair_over_under),
    books: asArray(m.books)
      .filter((b): b is Record<string, unknown> => b !== null && typeof b === "object")
      .map(asBook),
  };
}

/**
 * Normalize a single raw event object into a safe SBEvent.
 * Guarantees every array/object field is present; never throws.
 */
export function normalizeEvent(v: unknown): SBEvent | null {
  if (!v || typeof v !== "object") return null;
  const e = v as Record<string, unknown>;
  const id = asStr(e.id ?? e.event_id ?? e.eventID);
  if (!id) return null; // An event with no id cannot be keyed — drop it.

  return {
    id,
    sport: asStr(e.sport),
    league: asStr(e.league),
    start_time: typeof e.start_time === "string" ? e.start_time : null,
    status: asStr(e.status, "SCHEDULED"),
    status_display: asStr(e.status_display),
    venue: asStr(e.venue),
    home_team: asTeam(e.home_team),
    away_team: asTeam(e.away_team),
    home_score: asScore(e.home_score),
    away_score: asScore(e.away_score),
    period: typeof e.period === "string" ? e.period : null,
    players: asArray(e.players)
      .filter((p): p is Record<string, unknown> => p !== null && typeof p === "object")
      .map(asPlayer),
    markets: asArray(e.markets)
      .filter((m): m is Record<string, unknown> => m !== null && typeof m === "object")
      .map(asMarket),
    bookmakers: asArray(e.bookmakers)
      .map((b) => asStr(b))
      .filter(Boolean),
  };
}

/**
 * Normalize a raw events payload (array) into a safe SBEvent[].
 * Non-object entries and events without an id are dropped silently.
 */
export function normalizeEvents(raw: unknown): SBEvent[] {
  return asArray(raw)
    .map(normalizeEvent)
    .filter((e): e is SBEvent => e !== null);
}
