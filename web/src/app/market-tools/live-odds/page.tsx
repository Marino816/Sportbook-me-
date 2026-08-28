"use client";

import { useState, useMemo } from "react";
import { TrendingUp, AlertTriangle, Search } from "lucide-react";
import { useLiveScores, ScoreBadge, GameStatusBadge, gameState, type GameState } from "@/lib/live-scores";
import { BookmakerLogo } from "@/lib/assets";
import type { SBEvent, SBMarket, SBBookLine } from "@/lib/sbevent";
import { ROOKIE_LEAGUES } from "@/lib/sgo-leagues";
import { filterEventsByStatus, filterMarkets, presentPeriodGroups, type LineMode, type PeriodGroup } from "@/lib/market-view";
import { LeagueChips, StatusChips, LineModeChips, PeriodChips, LastUpdated, FairOddsMark, ConsensusMark } from "@/components/market-controls";

const LEAGUES = ROOKIE_LEAGUES;
type League = (typeof LEAGUES)[number]["leagueID"];

function fmtOdds(v: number | null | undefined): string {
  if (v == null) return "—";
  return v > 0 ? `+${v}` : `${v}`;
}

function fmtSpread(v: number | null | undefined): string {
  if (v == null) return "—";
  return v > 0 ? `+${v}` : `${v}`;
}

function formatTime(iso: string | null): string {
  if (!iso) return "TBD";
  try {
    const d = new Date(iso);
    return d.toLocaleString([], {
      month: "short",
      day: "numeric",
      hour: "numeric",
      minute: "2-digit",
      timeZoneName: "short",
    });
  } catch {
    return iso;
  }
}

interface MergedBookRow {
  bookmaker: string;
  available: boolean;
  awayML: number | null;
  homeML: number | null;
  spread: number | null;
  totalOver: number | null;
  totalUnder: number | null;
}

/** Build per-bookmaker rows by merging across all market types for a single event. */
function buildBookmakerRows(markets: SBMarket[]): MergedBookRow[] {
  const marketMap = new Map<string, SBMarket>();
  for (const m of markets) {
    const key = `${m.bet_type}::${m.side}`;
    if (!marketMap.has(key) || m.is_main_line) marketMap.set(key, m);
  }

  const awayMLMarket = marketMap.get("moneyline::away");
  const homeMLMarket = marketMap.get("moneyline::home");
  const spreadMarket = marketMap.get("spread::away") ?? marketMap.get("spread::home") ?? marketMap.get("spread::") ;
  const totalOverMarket = marketMap.get("over_under::over") ?? marketMap.get("total::over");
  const totalUnderMarket = marketMap.get("over_under::under") ?? marketMap.get("total::under");

  // Collect all unique bookmakers
  const bookmakerSet = new Set<string>();
  for (const m of [awayMLMarket, homeMLMarket, spreadMarket, totalOverMarket, totalUnderMarket]) {
    if (!m) continue;
    for (const b of m.books) bookmakerSet.add(b.bookmaker);
  }

  const rows: MergedBookRow[] = [];
  for (const bookmaker of bookmakerSet) {
    const awayB = awayMLMarket?.books.find((b) => b.bookmaker === bookmaker);
    const homeB = homeMLMarket?.books.find((b) => b.bookmaker === bookmaker);
    const spreadB = spreadMarket?.books.find((b) => b.bookmaker === bookmaker);
    const overB = totalOverMarket?.books.find((b) => b.bookmaker === bookmaker);
    const underB = totalUnderMarket?.books.find((b) => b.bookmaker === bookmaker);

    rows.push({
      bookmaker,
      available:
        (awayB?.available ?? false) ||
        (homeB?.available ?? false) ||
        (spreadB?.available ?? false),
      awayML: awayB?.moneyline ?? null,
      homeML: homeB?.moneyline ?? null,
      spread: spreadB?.spread ?? null,
      totalOver: overB?.over_under ?? null,
      totalUnder: underB?.over_under ?? null,
    });
  }

  return rows;
}

export default function LiveOddsPage() {
  const [activeLeague, setActiveLeague] = useState<League>("MLB");
  const [search, setSearch] = useState("");
  const [expanded, setExpanded] = useState<Record<string, boolean>>({});
  const [status, setStatus] = useState<GameState | "ALL">("ALL");
  const [lineMode, setLineMode] = useState<LineMode>("main");
  const [period, setPeriod] = useState<PeriodGroup | "all">("full");

  const { events, loading, error, lastFetch } = useLiveScores(activeLeague);

  const toggleExpand = (eventId: string) => {
    setExpanded((prev) => ({ ...prev, [eventId]: !prev[eventId] }));
  };

  const filtered = useMemo(() => {
    const byStatus = filterEventsByStatus(events, status);
    if (!search) return byStatus;
    const q = search.toLowerCase();
    return byStatus.filter((e) => {
      const hn = e.home_team.name.toLowerCase();
      const an = e.away_team.name.toLowerCase();
      const ha = e.home_team.abbreviation.toLowerCase();
      const aa = e.away_team.abbreviation.toLowerCase();
      return hn.includes(q) || an.includes(q) || ha.includes(q) || aa.includes(q);
    });
  }, [events, search, status]);

  const periodOptions = useMemo(() => {
    const all: SBMarket[] = [];
    for (const e of filtered) all.push(...(e.markets || []));
    return presentPeriodGroups(all);
  }, [filtered]);

  return (
    <div style={{ maxWidth: 1200, margin: "0 auto", padding: "32px 24px" }}>
      {/* Header */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 14,
          marginBottom: 28,
          background: "#0a0f24",
          borderRadius: 14,
          border: "1px solid #1e293b",
          padding: "20px 24px",
        }}
      >
        <TrendingUp size={26} color="#c9a84c" />
        <div style={{ flex: 1 }}>
          <h1 style={{ fontSize: 24, fontWeight: 900, color: "#c9a84c", margin: 0 }}>
            Live Odds
          </h1>
          <p style={{ fontSize: 13, color: "#94a3b8", margin: "2px 0 0" }}>
            Odds, spreads, and totals from SportsGameOdds. Finalized events are scores/results, not current markets.
          </p>
        </div>
        <LastUpdated fetchedAt={lastFetch ?? undefined} />
      </div>

      <div style={{ display: "flex", flexDirection: "column", gap: 10, marginBottom: 16 }}>
        <LeagueChips value={activeLeague} onChange={(id) => setActiveLeague(id as League)} />
        <StatusChips value={status} onChange={setStatus} />
        <LineModeChips value={lineMode} onChange={setLineMode} />
        {periodOptions.length > 0 && (
          <PeriodChips value={period} options={periodOptions} onChange={setPeriod} />
        )}
        <div style={{ position: "relative", marginLeft: "auto", width: "100%", maxWidth: 240 }}>
          <Search
            size={14}
            style={{
              position: "absolute",
              left: 10,
              top: "50%",
              transform: "translateY(-50%)",
              color: "#64748b",
            }}
          />
          <input
            type="text"
            placeholder="Search teams..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            style={{
              padding: "8px 14px 8px 32px",
              borderRadius: 10,
              fontSize: 13,
              background: "#0a0f24",
              border: "1px solid #1e293b",
              color: "#f0f6fc",
              outline: "none",
              minWidth: 200,
            }}
          />
        </div>
      </div>

      {loading && (
        <div style={{ textAlign: "center", padding: 60, color: "#94a3b8", fontSize: 14 }}>
          Loading events...
        </div>
      )}
      {error && (
        <div style={{ textAlign: "center", padding: 40, color: "#ef4444" }}>{error}</div>
      )}

      {/* Event cards */}
      <div style={{ display: "grid", gap: 12 }}>
        {filtered.map((evt) => {
          const live = gameState(evt) === "LIVE";
          const final = gameState(evt) === "FINAL";
          const isExpanded = expanded[evt.id];
          const rows = buildBookmakerRows(filterMarkets(evt.markets, { lineMode, period }));
          const mlHome = filterMarkets(evt.markets, { lineMode, period, betTypes: ["moneyline"] }).find((m) => m.side === "home");

          // Compute best values across all bookmakers
          let bestAwayML = -Infinity;
          let bestHomeML = -Infinity;
          let bestSpread = -Infinity;
          let bestTotalOver = -Infinity;
          let bestTotalUnder = -Infinity;

          for (const r of rows) {
            if (r.awayML != null && r.awayML > bestAwayML) bestAwayML = r.awayML;
            if (r.homeML != null && r.homeML > bestHomeML) bestHomeML = r.homeML;
            if (r.spread != null && r.spread > bestSpread) bestSpread = r.spread;
            if (r.totalOver != null && r.totalOver > bestTotalOver) bestTotalOver = r.totalOver;
            if (r.totalUnder != null && r.totalUnder > bestTotalUnder) bestTotalUnder = r.totalUnder;
          }

          return (
            <div
              key={evt.id}
              style={{
                background: live ? "rgba(201,168,76,0.04)" : "#0a0f24",
                borderRadius: 14,
                border: live ? "1px solid rgba(201,168,76,0.2)" : "1px solid #1e293b",
                overflow: "hidden",
              }}
            >
              {/* Event row — clickable */}
              <button
                onClick={() => toggleExpand(evt.id)}
                style={{
                  width: "100%",
                  padding: "16px 20px",
                  background: "none",
                  border: "none",
                  cursor: "pointer",
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                  color: "#f0f6fc",
                  textAlign: "left",
                }}
              >
                <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
                  {live && (
                    <span
                      style={{
                        padding: "3px 8px",
                        borderRadius: 6,
                        fontSize: 10,
                        fontWeight: 800,
                        background: "rgba(239,68,68,0.15)",
                        color: "#ef4444",
                        textTransform: "uppercase",
                        flexShrink: 0,
                      }}
                    >
                      ● LIVE
                    </span>
                  )}
                  {final && (
                    <span
                      style={{
                        padding: "3px 8px",
                        borderRadius: 6,
                        fontSize: 10,
                        fontWeight: 800,
                        background: "rgba(100,116,139,0.2)",
                        color: "#94a3b8",
                        textTransform: "uppercase",
                        flexShrink: 0,
                      }}
                    >
                      FINAL
                    </span>
                  )}
                  <div>
                    <div style={{ fontSize: 15, fontWeight: 700 }}>
                      {evt.away_team.abbreviation || evt.away_team.name} @{" "}
                      {evt.home_team.abbreviation || evt.home_team.name}
                    </div>
                    <div style={{ fontSize: 11, color: "#64748b", marginTop: 2 }}>
                      {evt.away_team.name} @ {evt.home_team.name}
                      {evt.start_time && <> · {formatTime(evt.start_time)}</>}
                    </div>
                  </div>
                </div>
                {/* Live score + expand icon */}
                <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                  {live && (evt.home_score != null || evt.away_score != null) ? (
                    <ScoreBadge evt={evt} />
                  ) : (
                    <GameStatusBadge evt={evt} />
                  )}
                  <span style={{ color: "#64748b", fontSize: 18 }}>
                    {isExpanded ? "▲" : "▼"}
                  </span>
                </div>
              </button>

              {/* Expanded odds panel */}
              {isExpanded && (
                <div style={{ borderTop: "1px solid #1e293b", padding: "16px 20px" }}>
                  {final && (
                    <div style={{ fontSize: 12, color: "#f59e0b", marginBottom: 10 }}>
                      Finalized event — shown for scores and results, not as a current bettable market.
                    </div>
                  )}
                  <div style={{ display: "flex", gap: 16, marginBottom: 12, flexWrap: "wrap" }}>
                    <span style={{ fontSize: 11, color: "#94a3b8" }}>Bookmaker Price is the sportsbook line.</span>
                    <FairOddsMark value={mlHome?.fair_odds ?? null} />
                    <ConsensusMark value={mlHome?.book_odds ?? null} />
                  </div>
                  {rows.length > 0 ? (
                    <div style={{ overflowX: "auto" }}>
                      <div
                        style={{
                          display: "grid",
                          gridTemplateColumns: "1.3fr 1fr 1fr 1fr 1fr 1fr",
                          gap: 4,
                          padding: "8px 0",
                          borderBottom: "1px solid #1e293b",
                          fontSize: 10,
                          fontWeight: 700,
                          color: "#64748b",
                          textTransform: "uppercase",
                          minWidth: 620,
                        }}
                      >
                        <span>Bookmaker</span>
                        <span style={{ textAlign: "center" }}>
                          {evt.away_team.abbreviation || "Away"} ML
                        </span>
                        <span style={{ textAlign: "center" }}>
                          {evt.home_team.abbreviation || "Home"} ML
                        </span>
                        <span style={{ textAlign: "center" }}>Spread</span>
                        <span style={{ textAlign: "center" }}>Total O</span>
                        <span style={{ textAlign: "center" }}>Total U</span>
                      </div>
                      {rows.map((r, i) => {
                        const isBestAway =
                          r.awayML != null &&
                          bestAwayML !== -Infinity &&
                          r.awayML === bestAwayML;
                        const isBestHome =
                          r.homeML != null &&
                          bestHomeML !== -Infinity &&
                          r.homeML === bestHomeML;
                        const isBestSpread =
                          r.spread != null &&
                          bestSpread !== -Infinity &&
                          r.spread === bestSpread;
                        const isBestOver =
                          r.totalOver != null &&
                          bestTotalOver !== -Infinity &&
                          r.totalOver === bestTotalOver;
                        const isBestUnder =
                          r.totalUnder != null &&
                          bestTotalUnder !== -Infinity &&
                          r.totalUnder === bestTotalUnder;

                        return (
                          <div
                            key={i}
                            style={{
                              display: "grid",
                              gridTemplateColumns: "1.3fr 1fr 1fr 1fr 1fr 1fr",
                              gap: 4,
                              padding: "10px 0",
                              borderBottom: "1px solid #1e293b20",
                              alignItems: "center",
                              minWidth: 620,
                            }}
                          >
                            <span
                              style={{ fontSize: 12, color: "#94a3b8", fontWeight: 500 }}
                            >
                              <BookmakerLogo bookmaker={r.bookmaker} />
                            </span>
                            <span
                              style={{
                                fontSize: 13,
                                fontWeight: isBestAway ? 800 : 600,
                                color: isBestAway ? "#c9a84c" : "#f0f6fc",
                                textAlign: "center",
                              }}
                            >
                              {fmtOdds(r.awayML)}
                            </span>
                            <span
                              style={{
                                fontSize: 13,
                                fontWeight: isBestHome ? 800 : 600,
                                color: isBestHome ? "#c9a84c" : "#f0f6fc",
                                textAlign: "center",
                              }}
                            >
                              {fmtOdds(r.homeML)}
                            </span>
                            <span
                              style={{
                                fontSize: 13,
                                fontWeight: isBestSpread ? 800 : 600,
                                color: isBestSpread ? "#c9a84c" : "#94a3b8",
                                textAlign: "center",
                              }}
                            >
                              {fmtSpread(r.spread)}
                            </span>
                            <span
                              style={{
                                fontSize: 13,
                                fontWeight: isBestOver ? 800 : 600,
                                color: isBestOver ? "#c9a84c" : "#94a3b8",
                                textAlign: "center",
                              }}
                            >
                              {r.totalOver != null ? `O${r.totalOver}` : "—"}
                            </span>
                            <span
                              style={{
                                fontSize: 13,
                                fontWeight: isBestUnder ? 800 : 600,
                                color: isBestUnder ? "#c9a84c" : "#94a3b8",
                                textAlign: "center",
                              }}
                            >
                              {r.totalUnder != null ? `U${r.totalUnder}` : "—"}
                            </span>
                          </div>
                        );
                      })}
                    </div>
                  ) : (
                    <div style={{ textAlign: "center", padding: 24, color: "#64748b" }}>
                      No bookmaker data available for this event.
                    </div>
                  )}
                </div>
              )}
            </div>
          );
        })}
      </div>

      {!loading && filtered.length === 0 && (
        <div style={{ textAlign: "center", padding: 60, color: "#64748b" }}>
          <AlertTriangle size={32} style={{ marginBottom: 12 }} />
          <p>No events found for {activeLeague}.</p>
        </div>
      )}
    </div>
  );
}