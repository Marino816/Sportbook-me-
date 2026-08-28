"use client";

import { useState, useMemo } from "react";
import { GitCompare, Trophy, Search } from "lucide-react";
import { useEvents } from "@/lib/use-events";
import type { SBEvent, SBMarket, SBBookLine } from "@/lib/sbevent";
import { formatBookmakerName } from "@/lib/bookmakers";
import { MARKET_TOOL_LEAGUES, leagueLabel } from "@/lib/sgo-leagues";

const LEAGUES = MARKET_TOOL_LEAGUES;
type League = (typeof LEAGUES)[number];

type MarketTab = "moneyline" | "spread" | "total";

interface MarketTabDef {
  key: MarketTab;
  label: string;
}

const MARKET_TABS: MarketTabDef[] = [
  { key: "moneyline", label: "Moneyline" },
  { key: "spread", label: "Spread" },
  { key: "total", label: "Total" },
];

function fmtOdds(v: number | null | undefined): string {
  if (v == null) return "—";
  return v > 0 ? `+${v}` : `${v}`;
}

function fmtSpread(v: number | null | undefined): string {
  if (v == null) return "—";
  return v > 0 ? `+${v}` : `${v}`;
}

interface CompareRow {
  bookmaker: string;
  available: boolean;
  homeValue: number | null;
  awayValue: number | null;
}

/** Extract comparison rows for a given market type from SBEvent.markets */
function buildCompareRows(event: SBEvent | undefined, tab: MarketTab): CompareRow[] {
  if (!event) return [];

  const marketMap = new Map<string, SBMarket>();
  for (const m of event.markets) {
    const key = `${m.bet_type}::${m.side}`;
    marketMap.set(key, m);
  }

  let homeMarket: SBMarket | undefined;
  let awayMarket: SBMarket | undefined;
  let overMarket: SBMarket | undefined;
  let underMarket: SBMarket | undefined;

  switch (tab) {
    case "moneyline":
      homeMarket = marketMap.get("moneyline::home");
      awayMarket = marketMap.get("moneyline::away");
      break;
    case "spread":
      homeMarket = marketMap.get("spread::home");
      awayMarket = marketMap.get("spread::away");
      break;
    case "total":
      overMarket = marketMap.get("over_under::over");
      underMarket = marketMap.get("over_under::under");
      break;
  }

  // Collect all unique bookmakers
  const bookmakerSet = new Set<string>();
  for (const m of [homeMarket, awayMarket, overMarket, underMarket]) {
    if (!m) continue;
    for (const b of m.books) bookmakerSet.add(b.bookmaker);
  }

  const rows: CompareRow[] = [];
  for (const bookmaker of bookmakerSet) {
    let homeValue: number | null = null;
    let awayValue: number | null = null;

    if (tab === "moneyline") {
      homeValue = homeMarket?.books.find((b) => b.bookmaker === bookmaker)?.moneyline ?? null;
      awayValue = awayMarket?.books.find((b) => b.bookmaker === bookmaker)?.moneyline ?? null;
    } else if (tab === "spread") {
      homeValue = homeMarket?.books.find((b) => b.bookmaker === bookmaker)?.spread ?? null;
      awayValue = awayMarket?.books.find((b) => b.bookmaker === bookmaker)?.spread ?? null;
    } else if (tab === "total") {
      homeValue = overMarket?.books.find((b) => b.bookmaker === bookmaker)?.over_under ?? null;
      awayValue = underMarket?.books.find((b) => b.bookmaker === bookmaker)?.over_under ?? null;
    }

    const available =
      homeValue != null ||
      awayValue != null ||
      (homeMarket?.books.find((b) => b.bookmaker === bookmaker)?.available ?? false) ||
      (awayMarket?.books.find((b) => b.bookmaker === bookmaker)?.available ?? false) ||
      (overMarket?.books.find((b) => b.bookmaker === bookmaker)?.available ?? false) ||
      (underMarket?.books.find((b) => b.bookmaker === bookmaker)?.available ?? false);

    rows.push({ bookmaker, available, homeValue, awayValue });
  }

  return rows;
}

export default function CompareOddsPage() {
  const [activeLeague, setActiveLeague] = useState<League>("MLB");
  const [search, setSearch] = useState("");
  const [selectedEventId, setSelectedEventId] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<MarketTab>("moneyline");

  const { events, loading, error } = useEvents(activeLeague);

  const selectedEvent = useMemo(
    () => events.find((e) => e.id === selectedEventId) ?? null,
    [events, selectedEventId]
  );

  const rows = useMemo(
    () => buildCompareRows(selectedEvent ?? undefined, activeTab),
    [selectedEvent, activeTab]
  );

  // Compute best values for highlighting
  const { bestHome, bestAway } = useMemo(() => {
    let bh: number | null = null;
    let ba: number | null = null;

    if (activeTab === "moneyline") {
      // For moneyline, best = highest
      for (const r of rows) {
        if (r.homeValue != null && (bh === null || r.homeValue > bh)) bh = r.homeValue;
        if (r.awayValue != null && (ba === null || r.awayValue > ba)) ba = r.awayValue;
      }
    } else if (activeTab === "spread") {
      // For spreads, prefer most favorable to each side
      for (const r of rows) {
        if (r.homeValue != null && (bh === null || r.homeValue > bh)) bh = r.homeValue;
        if (r.awayValue != null && (ba === null || r.awayValue > ba)) ba = r.awayValue;
      }
    } else {
      // For total: just find max for both
      for (const r of rows) {
        if (r.homeValue != null && (bh === null || r.homeValue > bh)) bh = r.homeValue;
        if (r.awayValue != null && (ba === null || r.awayValue > ba)) ba = r.awayValue;
      }
    }

    return { bestHome: bh, bestAway: ba };
  }, [rows, activeTab]);

  const filteredEvents = useMemo(() => {
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

  // Column labels based on market type
  const homeLabel =
    activeTab === "total"
      ? "Over"
      : selectedEvent?.home_team.abbreviation || "Home";
  const awayLabel =
    activeTab === "total"
      ? "Under"
      : selectedEvent?.away_team.abbreviation || "Away";

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
        <GitCompare size={26} color="#c9a84c" />
        <div style={{ flex: 1 }}>
          <h1 style={{ fontSize: 24, fontWeight: 900, color: "#c9a84c", margin: 0 }}>
            Compare Odds
          </h1>
          <p style={{ fontSize: 13, color: "#94a3b8", margin: "2px 0 0" }}>
            Best price highlighted across all bookmakers — SportsGameOdds
          </p>
        </div>
      </div>

      {/* League tabs */}
      <div
        style={{
          display: "flex",
          gap: 8,
          marginBottom: 16,
          flexWrap: "wrap",
          alignItems: "center",
        }}
      >
        {LEAGUES.map((lg) => (
          <button
            key={lg}
            onClick={() => {
              setActiveLeague(lg);
              setSelectedEventId(null);
            }}
            style={{
              padding: "8px 14px",
              borderRadius: 10,
              fontSize: 12,
              fontWeight: 700,
              background: activeLeague === lg ? "rgba(201,168,76,0.1)" : "#0a0f24",
              border: activeLeague === lg ? "1px solid #c9a84c" : "1px solid #1e293b",
              color: activeLeague === lg ? "#c9a84c" : "#94a3b8",
              cursor: "pointer",
            }}
          >
            {leagueLabel(lg)}
          </button>
        ))}
      </div>

      {loading && (
        <div style={{ textAlign: "center", padding: 60, color: "#94a3b8" }}>
          Loading events...
        </div>
      )}
      {error && (
        <div style={{ textAlign: "center", padding: 40, color: "#ef4444" }}>{error}</div>
      )}

      {/* Event selector + search */}
      {!loading && (
        <div
          style={{
            display: "flex",
            gap: 10,
            marginBottom: 20,
            flexWrap: "wrap",
            alignItems: "center",
          }}
        >
          <div style={{ position: "relative" }}>
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
          {filteredEvents.map((evt) => {
            const isSel = evt.id === selectedEventId;
            return (
              <button
                key={evt.id}
                onClick={() => setSelectedEventId(evt.id)}
                style={{
                  padding: "8px 14px",
                  borderRadius: 10,
                  fontSize: 12,
                  fontWeight: 600,
                  border: isSel ? "1px solid #c9a84c" : "1px solid #1e293b",
                  background: isSel ? "rgba(201,168,76,0.1)" : "#0a0f24",
                  color: isSel ? "#c9a84c" : "#94a3b8",
                  cursor: "pointer",
                  whiteSpace: "nowrap",
                }}
              >
                {(evt.away_team.abbreviation || "AWY").substring(0, 3)} @{" "}
                {(evt.home_team.abbreviation || "HOM").substring(0, 3)}
              </button>
            );
          })}
        </div>
      )}

      {/* Market type selector */}
      {selectedEvent && (
        <div style={{ display: "flex", gap: 6, marginBottom: 20 }}>
          {MARKET_TABS.map((t) => (
            <button
              key={t.key}
              onClick={() => setActiveTab(t.key)}
              style={{
                padding: "8px 16px",
                borderRadius: 10,
                fontSize: 12,
                fontWeight: 600,
                border: activeTab === t.key ? "1px solid #c9a84c" : "1px solid #1e293b",
                background:
                  activeTab === t.key ? "rgba(201,168,76,0.1)" : "#0a0f24",
                color: activeTab === t.key ? "#c9a84c" : "#94a3b8",
                cursor: "pointer",
              }}
            >
              {t.label}
            </button>
          ))}
        </div>
      )}

      {/* Comparison table */}
      {selectedEvent && rows.length > 0 && (
        <div
          style={{
            background: "#0a0f24",
            borderRadius: 14,
            border: "1px solid #1e293b",
            overflow: "hidden",
          }}
        >
          {/* Table header */}
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "2fr 1fr 1fr 80px",
              padding: "12px 20px",
              background: "rgba(201,168,76,0.08)",
              borderBottom: "1px solid #1e293b",
              fontSize: 11,
              fontWeight: 700,
              color: "#c9a84c",
              textTransform: "uppercase",
            }}
          >
            <span>Bookmaker</span>
            <span style={{ textAlign: "center" }}>{homeLabel}</span>
            <span style={{ textAlign: "center" }}>{awayLabel}</span>
            <span style={{ textAlign: "center" }}>Best</span>
          </div>

          {rows.map((row, i) => {
            const homeIsBest =
              row.homeValue != null && row.homeValue === bestHome;
            const awayIsBest =
              row.awayValue != null && row.awayValue === bestAway;

            const displayHome =
              activeTab === "spread"
                ? fmtSpread(row.homeValue)
                : activeTab === "total"
                ? row.homeValue != null
                  ? `O ${row.homeValue}`
                  : "—"
                : fmtOdds(row.homeValue);

            const displayAway =
              activeTab === "spread"
                ? fmtSpread(row.awayValue)
                : activeTab === "total"
                ? row.awayValue != null
                  ? `U ${row.awayValue}`
                  : "—"
                : fmtOdds(row.awayValue);

            return (
              <div
                key={i}
                style={{
                  display: "grid",
                  gridTemplateColumns: "2fr 1fr 1fr 80px",
                  padding: "14px 20px",
                  borderBottom: "1px solid #1e293b20",
                  alignItems: "center",
                }}
              >
                <span
                  style={{ fontSize: 13, color: "#94a3b8", fontWeight: 500 }}
                >
                  {row.bookmaker}
                </span>
                <span
                  style={{
                    fontSize: 14,
                    fontWeight: homeIsBest ? 800 : 500,
                    color: homeIsBest ? "#c9a84c" : "#f0f6fc",
                    textAlign: "center",
                  }}
                >
                  {displayHome}
                </span>
                <span
                  style={{
                    fontSize: 14,
                    fontWeight: awayIsBest ? 800 : 500,
                    color: awayIsBest ? "#c9a84c" : "#f0f6fc",
                    textAlign: "center",
                  }}
                >
                  {displayAway}
                </span>
                <span style={{ textAlign: "center" }}>
                  {homeIsBest || awayIsBest ? (
                    <Trophy size={16} color="#c9a84c" />
                  ) : null}
                </span>
              </div>
            );
          })}
        </div>
      )}

      {selectedEvent && rows.length === 0 && !loading && (
        <div
          style={{
            textAlign: "center",
            padding: 60,
            color: "#64748b",
            background: "#0a0f24",
            borderRadius: 14,
            border: "1px solid #1e293b",
          }}
        >
          No {activeTab} data available for this event.
        </div>
      )}

      {!selectedEvent && !loading && (
        <div style={{ textAlign: "center", padding: 60, color: "#64748b" }}>
          Select an event to compare odds across bookmakers.
        </div>
      )}
    </div>
  );
}