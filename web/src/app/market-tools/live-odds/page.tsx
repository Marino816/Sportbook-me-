"use client";

import { useState, useMemo } from "react";
import { TrendingUp, AlertTriangle, Search } from "lucide-react";
import { useEvents } from "@/lib/use-events";
import type { SBEvent, SBMarket, SBBookLine } from "@/lib/sbevent";

const LEAGUES = ["MLB", "NFL", "NBA", "NHL", "NCAAF", "NCAAB"] as const;
type League = (typeof LEAGUES)[number];

function fmtOdds(v: number | null | undefined): string {
  if (v == null) return "—";
  return v > 0 ? `+${v}` : `${v}`;
}

function fmtSpread(v: number | null | undefined): string {
  if (v == null) return "—";
  return v > 0 ? `+${v}` : `${v}`;
}

function isLive(status: string): boolean {
  const s = status?.toUpperCase() || "";
  return s === "LIVE" || s === "IN_PLAY" || s === "INPLAY";
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
  // Index markets by bet_type+side for quick lookup
  const marketMap = new Map<string, SBMarket>();
  for (const m of markets) {
    const key = `${m.bet_type}::${m.side}`;
    marketMap.set(key, m);
  }

  const awayMLMarket = marketMap.get("moneyline::away");
  const homeMLMarket = marketMap.get("moneyline::home");
  const spreadMarket = marketMap.get("spread::away") ?? marketMap.get("spread::home") ?? marketMap.get("spread::") ;
  const totalOverMarket = marketMap.get("over_under::over");
  const totalUnderMarket = marketMap.get("over_under::under");

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

  const { events, loading, error } = useEvents(activeLeague);

  const toggleExpand = (eventId: string) => {
    setExpanded((prev) => ({ ...prev, [eventId]: !prev[eventId] }));
  };

  const filtered = useMemo(() => {
    if (!search) return events;
    const q = search.toLowerCase();
    return events.filter((e) => {
      const hn = e.home_team.name.toLowerCase();
      const an = e.away_team.name.toLowerCase();
      const ha = e.home_team.abbreviation.toLowerCase();
      const aa = e.away_team.abbreviation.toLowerCase();
      return hn.includes(q) || an.includes(q) || ha.includes(q) || aa.includes(q);
    });
  }, [events, search]);

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
            Real-time odds, spreads, and totals — SportsGameOdds
          </p>
        </div>
      </div>

      {/* League tabs + search */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 8,
          marginBottom: 20,
          flexWrap: "wrap",
        }}
      >
        {LEAGUES.map((lg) => (
          <button
            key={lg}
            onClick={() => setActiveLeague(lg)}
            style={{
              padding: "8px 16px",
              borderRadius: 10,
              fontSize: 12,
              fontWeight: 700,
              background: activeLeague === lg ? "rgba(201,168,76,0.1)" : "#0a0f24",
              border: activeLeague === lg ? "1px solid #c9a84c" : "1px solid #1e293b",
              color: activeLeague === lg ? "#c9a84c" : "#94a3b8",
              cursor: "pointer",
            }}
          >
            {lg}
          </button>
        ))}
        <div style={{ position: "relative", marginLeft: "auto" }}>
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
          const live = isLive(evt.status);
          const isExpanded = expanded[evt.id];
          const rows = buildBookmakerRows(evt.markets);

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
                  {live && (evt.home_score != null || evt.away_score != null) && (
                    <span style={{ fontSize: 16, fontWeight: 800, color: "#c9a84c" }}>
                      {evt.away_score ?? 0} – {evt.home_score ?? 0}
                      {evt.period && (
                        <span style={{ fontSize: 10, color: "#64748b", marginLeft: 4 }}>
                          {evt.period}
                        </span>
                      )}
                    </span>
                  )}
                  <span style={{ color: "#64748b", fontSize: 18 }}>
                    {isExpanded ? "▲" : "▼"}
                  </span>
                </div>
              </button>

              {/* Expanded odds panel */}
              {isExpanded && (
                <div style={{ borderTop: "1px solid #1e293b", padding: "16px 20px" }}>
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
                              {r.bookmaker}
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