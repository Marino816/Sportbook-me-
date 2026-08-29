/**
 * Canonical arbitrage scan over SBEvent markets.
 * Uses real SportsGameOdds book prices only. Never invents odds.
 *
 * Bookmaker identity reuses the same 55-platform catalog as Live Odds /
 * Bookmakers. Runtime imports stay type-only + JSON so Node tests can load
 * this file without a bundler.
 */

import type { SBEvent, SBBookLine, SBMarket } from "./sbevent";
import catalog from "./sbme-55-platforms.json" with { type: "json" };

type PlatformRow = { id: string; name: string; sgo_ids: string[] };
const PLATFORMS = catalog as PlatformRow[];
const CORE_OK = new Set(["moneyline", "spread", "total", "over_under"]);

function bookHasPrice(b: SBBookLine): boolean {
  return b.moneyline != null || b.spread != null || b.over_under != null;
}

/** Same availability rule as market-view.bookIsActive. */
function bookIsActive(b: SBBookLine | undefined | null): boolean {
  return Boolean(b && b.available !== false && bookHasPrice(b));
}

/** Same catalog collapse as platforms.canonicalBookmakerId. */
function canonicalBookmakerId(sgoId: string | null | undefined): string {
  const key = (sgoId || "").trim().toLowerCase();
  if (!key || key === "unknown") return "";
  const row = PLATFORMS.find((p) => p.sgo_ids.map((i) => i.toLowerCase()).includes(key));
  return row?.id ?? key;
}

export interface ArbOpportunity {
  key: string;
  event: string;
  event_id: string;
  league: string;
  sport: string;
  market: string;
  period: string;
  line: number | null;
  home_book: string;
  home_odds: number;
  away_book: string;
  away_odds: number;
  arb_pct: number;
  payout: number;
  profit: number;
  implied_total: number;
}

export function americanToDecimal(am: number): number {
  if (!Number.isFinite(am) || am === 0) return NaN;
  return am > 0 ? 1 + am / 100 : 1 + 100 / Math.abs(am);
}

export function twoWayArb(oddsA: number, oddsB: number, bankroll = 100): {
  implied: number;
  arb_pct: number;
  payout: number;
  profit: number;
} | null {
  const decA = americanToDecimal(oddsA);
  const decB = americanToDecimal(oddsB);
  if (!Number.isFinite(decA) || !Number.isFinite(decB) || decA <= 1 || decB <= 1) return null;
  const implied = (1 / decA + 1 / decB) * 100;
  if (!Number.isFinite(implied) || implied >= 100) return null;
  const arb = 100 - implied;
  const stakeA = (bankroll * (1 / decA)) / (implied / 100);
  const stakeB = (bankroll * (1 / decB)) / (implied / 100);
  const payout = Math.min(stakeA * decA, stakeB * decB);
  if (!Number.isFinite(payout) || payout <= bankroll) return null;
  return {
    implied,
    arb_pct: Math.round(arb * 100) / 100,
    payout: Math.round(payout * 100) / 100,
    profit: Math.round((payout - bankroll) * 100) / 100,
  };
}

function activeBooks(market: SBMarket | undefined, field: "moneyline" | "spread" | "over_under"): SBBookLine[] {
  if (!market) return [];
  return (market.books || []).filter((b) => {
    if (!bookIsActive(b)) return false;
    if (!canonicalBookmakerId(b.bookmaker)) return false;
    if (field === "moneyline") return b.moneyline != null;
    if (field === "spread") return b.spread != null;
    return b.over_under != null;
  });
}

function isThreeWayMoneyline(markets: SBMarket[]): boolean {
  return markets.some((m) => {
    const oid = (m.odd_id || "").toLowerCase();
    const side = (m.side || "").toLowerCase();
    return oid.includes("ml3way") || side === "draw" || side === "not_draw";
  });
}

function bestPair(
  homeBooks: SBBookLine[],
  awayBooks: SBBookLine[],
  price: (b: SBBookLine) => number | null,
): { home: SBBookLine; away: SBBookLine; math: NonNullable<ReturnType<typeof twoWayArb>> } | null {
  let best: { home: SBBookLine; away: SBBookLine; math: NonNullable<ReturnType<typeof twoWayArb>> } | null = null;
  for (const hb of homeBooks) {
    const hp = price(hb);
    if (hp == null) continue;
    const hCanon = canonicalBookmakerId(hb.bookmaker);
    for (const ab of awayBooks) {
      const ap = price(ab);
      if (ap == null) continue;
      const aCanon = canonicalBookmakerId(ab.bookmaker);
      if (!hCanon || !aCanon || hCanon === aCanon) continue;
      const math = twoWayArb(hp, ap);
      if (!math) continue;
      if (
        !best ||
        math.arb_pct > best.math.arb_pct ||
        (math.arb_pct === best.math.arb_pct && math.profit > best.math.profit)
      ) {
        best = { home: hb, away: ab, math };
      }
    }
  }
  return best;
}

function matchupName(evt: SBEvent): string {
  return `${evt.away_team.abbreviation || "AWY"} @ ${evt.home_team.abbreviation || "HOM"}`;
}

function lineKey(v: number): string {
  return (Math.round(v * 100) / 100).toFixed(2);
}

export function canonicalArbKey(parts: {
  eventId: string;
  league: string;
  market: string;
  period: string;
  line: number | null;
}): string {
  const line = parts.line == null ? "ml" : lineKey(parts.line);
  return [parts.eventId, parts.league, parts.market, parts.period || "game", line].join("|");
}

function consider(
  found: Map<string, ArbOpportunity>,
  evt: SBEvent,
  market: string,
  period: string,
  line: number | null,
  pair: NonNullable<ReturnType<typeof bestPair>>,
): void {
  const key = canonicalArbKey({
    eventId: evt.id,
    league: evt.league || "",
    market,
    period,
    line,
  });
  const opp: ArbOpportunity = {
    key,
    event: matchupName(evt),
    event_id: evt.id,
    league: evt.league || "",
    sport: evt.sport || "",
    market,
    period,
    line,
    home_book: pair.home.bookmaker,
    home_odds: pair.home.moneyline as number,
    away_book: pair.away.bookmaker,
    away_odds: pair.away.moneyline as number,
    arb_pct: pair.math.arb_pct,
    payout: pair.math.payout,
    profit: pair.math.profit,
    implied_total: Math.round(pair.math.implied * 100) / 100,
  };
  const prior = found.get(key);
  if (!prior || opp.arb_pct > prior.arb_pct || (opp.arb_pct === prior.arb_pct && opp.profit > prior.profit)) {
    found.set(key, opp);
  }
}

/**
 * Scan events for 2-way mathematical arbs.
 * Dedupes permutations of the same event/market/period/line to the best executable books.
 */
export function scanArbitrage(events: SBEvent[]): ArbOpportunity[] {
  const found = new Map<string, ArbOpportunity>();

  for (const evt of events) {
    const groups = new Map<string, SBMarket[]>();
    for (const m of evt.markets || []) {
      if (!CORE_OK.has(m.bet_type)) continue;
      const period = m.period_id || "game";
      const gkey = `${m.bet_type}|${period}`;
      const list = groups.get(gkey) || [];
      list.push(m);
      groups.set(gkey, list);
    }

    for (const [gkey, markets] of groups) {
      const [betType, period] = gkey.split("|");
      if (betType === "moneyline") {
        if (isThreeWayMoneyline(markets)) continue;
        const home = markets.find((m) => (m.side || "").toLowerCase() === "home");
        const away = markets.find((m) => (m.side || "").toLowerCase() === "away");
        const pair = bestPair(activeBooks(home, "moneyline"), activeBooks(away, "moneyline"), (b) => b.moneyline);
        if (pair) consider(found, evt, "moneyline", period, null, pair);
      } else if (betType === "spread") {
        const homeMkts = markets.filter((m) => (m.side || "").toLowerCase() === "home");
        const awayMkts = markets.filter((m) => (m.side || "").toLowerCase() === "away");
        const homeByLine = groupBySpread(homeMkts);
        for (const [lineStr, homeBooks] of homeByLine) {
          const homeLine = Number(lineStr);
          const awayBooks = booksAtSpread(awayMkts, -homeLine);
          const pair = bestPair(homeBooks, awayBooks, (b) => b.moneyline);
          if (pair && pair.home.moneyline != null && pair.away.moneyline != null) {
            consider(found, evt, "spread", period, homeLine, pair);
          }
        }
      } else if (betType === "total" || betType === "over_under") {
        const overMkts = markets.filter((m) => (m.side || "").toLowerCase() === "over");
        const underMkts = markets.filter((m) => (m.side || "").toLowerCase() === "under");
        const overByLine = groupByTotal(overMkts);
        for (const [lineStr, overBooks] of overByLine) {
          const line = Number(lineStr);
          const underBooks = booksAtTotal(underMkts, line);
          const pair = bestPair(overBooks, underBooks, (b) => b.moneyline);
          if (pair && pair.home.moneyline != null && pair.away.moneyline != null) {
            consider(found, evt, "total", period, line, pair);
          }
        }
      }
    }
  }

  return [...found.values()].sort((a, b) => b.arb_pct - a.arb_pct || b.profit - a.profit);
}

function groupBySpread(markets: SBMarket[]): Map<string, SBBookLine[]> {
  const map = new Map<string, SBBookLine[]>();
  for (const m of markets) {
    for (const b of activeBooks(m, "spread")) {
      if (b.spread == null || b.moneyline == null) continue;
      const k = lineKey(b.spread);
      const list = map.get(k) || [];
      list.push(b);
      map.set(k, list);
    }
  }
  return map;
}

function booksAtSpread(markets: SBMarket[], want: number): SBBookLine[] {
  const out: SBBookLine[] = [];
  const wantK = lineKey(want);
  for (const m of markets) {
    for (const b of activeBooks(m, "spread")) {
      if (b.spread == null || b.moneyline == null) continue;
      if (lineKey(b.spread) === wantK) out.push(b);
    }
  }
  return out;
}

function groupByTotal(markets: SBMarket[]): Map<string, SBBookLine[]> {
  const map = new Map<string, SBBookLine[]>();
  for (const m of markets) {
    for (const b of activeBooks(m, "over_under")) {
      if (b.over_under == null || b.moneyline == null) continue;
      const k = lineKey(b.over_under);
      const list = map.get(k) || [];
      list.push(b);
      map.set(k, list);
    }
  }
  return map;
}

function booksAtTotal(markets: SBMarket[], want: number): SBBookLine[] {
  const out: SBBookLine[] = [];
  const wantK = lineKey(want);
  for (const m of markets) {
    for (const b of activeBooks(m, "over_under")) {
      if (b.over_under == null || b.moneyline == null) continue;
      if (lineKey(b.over_under) === wantK) out.push(b);
    }
  }
  return out;
}

export function filterOpportunities(
  opps: ArbOpportunity[],
  opts: { search?: string; sport?: string } = {},
): ArbOpportunity[] {
  const q = (opts.search || "").trim().toLowerCase();
  const sport = (opts.sport || "").trim().toLowerCase();
  return opps.filter((o) => {
    if (sport && sport !== "all" && (o.league || "").toLowerCase() !== sport && (o.sport || "").toLowerCase() !== sport) {
      return false;
    }
    if (!q) return true;
    return (
      o.event.toLowerCase().includes(q) ||
      o.market.toLowerCase().includes(q) ||
      o.home_book.toLowerCase().includes(q) ||
      o.away_book.toLowerCase().includes(q)
    );
  });
}
