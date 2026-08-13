"use client";

import { useState, useMemo } from "react";
import { UserCheck, Search, CheckCircle } from "lucide-react";
import { useEvents } from "@/lib/use-events";
import type { SBEvent, SBMarket, SBBookLine } from "@/lib/sbevent";

const LEAGUES = ["MLB", "NFL", "NBA", "NHL", "NCAAF", "NCAAB"] as const;
type League = (typeof LEAGUES)[number];

interface PropRow {
  playerId: string;
  playerName: string;
  teamAbbr: string;
  marketName: string;
  betType: string;
  side: string;
  line: number | null;
  overPrice: number | null;
  underPrice: number | null;
  bookmaker: string;
}

function fmtOdds(v: number | null | undefined): string {
  if (v == null) return "—";
  return v > 0 ? `+${v}` : `${v}`;
}

/** Extract player prop rows from SBEvent.markets, grouped by player_name. */
function extractPlayerProps(event: SBEvent): PropRow[] {
  const rows: PropRow[] = [];

  for (const market of event.markets) {
    if (market.bet_type !== "player_prop") continue;

    for (const book of market.books) {
      if (!book.available) continue;

      rows.push({
        playerId: market.player_id || "unknown",
        playerName: market.player_name || "Unknown",
        teamAbbr:
          event.home_team.team_id === market.stat_entity_id
            ? event.home_team.abbreviation
            : event.away_team.abbreviation,
        marketName: market.market_name,
        betType: market.bet_type,
        side: market.side,
        line: book.over_under ?? book.spread ?? null,
        overPrice: market.side === "over" ? book.moneyline : null,
        underPrice: market.side === "under" ? book.moneyline : null,
        bookmaker: book.bookmaker,
      });
    }
  }

  return rows;
}

/**
 * Merge player props — for over_under props, pair over/under sides together.
 * Returns a simplified view: Player | Team | Prop | Line | Over | Under | Book
 */
interface GroupedProp {
  playerName: string;
  teamAbbr: string;
  marketName: string;
  lines: { line: number | null; overPrice: number | null; underPrice: number | null; bookmaker: string }[];
}

function groupProps(rows: PropRow[]): GroupedProp[] {
  const groups = new Map<string, GroupedProp>();

  for (const row of rows) {
    const key = `${row.playerName}::${row.marketName}`;
    if (!groups.has(key)) {
      groups.set(key, {
        playerName: row.playerName,
        teamAbbr: row.teamAbbr,
        marketName: row.marketName,
        lines: [],
      });
    }

    const group = groups.get(key)!;

    // Try to pair with an existing line from the same bookmaker at the same line value
    const existing = group.lines.find(
      (l) => l.bookmaker === row.bookmaker && l.line === row.line
    );

    if (existing) {
      if (row.overPrice != null) existing.overPrice = row.overPrice;
      if (row.underPrice != null) existing.underPrice = row.underPrice;
    } else {
      group.lines.push({
        line: row.line,
        overPrice: row.overPrice,
        underPrice: row.underPrice,
        bookmaker: row.bookmaker,
      });
    }
  }

  return Array.from(groups.values());
}

/** Build player->props map for the UI */
function buildPlayerPropMap(
  events: SBEvent[],
  selectedEventId: string | null
): Map<string, GroupedProp[]> {
  const map = new Map<string, GroupedProp[]>();

  if (!selectedEventId) return map;

  const event = events.find((e) => e.id === selectedEventId);
  if (!event) return map;

  const rows = extractPlayerProps(event);
  const groups = groupProps(rows);

  for (const g of groups) {
    if (!map.has(g.playerName)) {
      map.set(g.playerName, []);
    }
    map.get(g.playerName)!.push(g);
  }

  return map;
}

export default function PlayerPropsPage() {
  const [activeLeague, setActiveLeague] = useState<League>("MLB");
  const [selectedEventId, setSelectedEventId] = useState<string | null>(null);
  const [selectedPlayerName, setSelectedPlayerName] = useState<string | null>(null);
  const [search, setSearch] = useState("");

  const { events, loading, error } = useEvents(activeLeague);

  const playerPropMap = useMemo(
    () => buildPlayerPropMap(events, selectedEventId),
    [events, selectedEventId]
  );

  const playerNames = useMemo(() => Array.from(playerPropMap.keys()), [playerPropMap]);

  const filteredPlayers = useMemo(() => {
    if (!search) return playerNames;
    const q = search.toLowerCase();
    return playerNames.filter((n) => n.toLowerCase().includes(q));
  }, [playerNames, search]);

  const selectedProps = selectedPlayerName
    ? playerPropMap.get(selectedPlayerName) ?? []
    : [];

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
        <UserCheck size={26} color="#c9a84c" />
        <div style={{ flex: 1 }}>
          <h1 style={{ fontSize: 24, fontWeight: 900, color: "#c9a84c", margin: 0 }}>
            Player Props
          </h1>
          <p style={{ fontSize: 13, color: "#94a3b8", margin: "2px 0 0" }}>
            Prop bets across sportsbooks — SportsGameOdds
          </p>
        </div>
      </div>

      {/* League tabs */}
      <div style={{ display: "flex", gap: 8, marginBottom: 16, flexWrap: "wrap" }}>
        {LEAGUES.map((lg) => (
          <button
            key={lg}
            onClick={() => {
              setActiveLeague(lg);
              setSelectedEventId(null);
              setSelectedPlayerName(null);
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
            {lg}
          </button>
        ))}
      </div>

      {loading && (
        <div style={{ textAlign: "center", padding: 40, color: "#94a3b8" }}>
          Loading events...
        </div>
      )}
      {error && (
        <div style={{ textAlign: "center", padding: 40, color: "#ef4444" }}>{error}</div>
      )}

      {/* Event selector */}
      {!loading && (
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginBottom: 24 }}>
          {events.map((evt) => {
            const isSel = evt.id === selectedEventId;
            return (
              <button
                key={evt.id}
                onClick={() => {
                  setSelectedEventId(evt.id);
                  setSelectedPlayerName(null);
                }}
                style={{
                  padding: "10px 16px",
                  borderRadius: 12,
                  fontSize: 13,
                  fontWeight: 600,
                  border: isSel ? "1px solid #c9a84c" : "1px solid #1e293b",
                  background: isSel ? "rgba(201,168,76,0.1)" : "#0a0f24",
                  color: isSel ? "#c9a84c" : "#f0f6fc",
                  cursor: "pointer",
                }}
              >
                {(evt.away_team.abbreviation || "AWY").substring(0, 3)} @{" "}
                {(evt.home_team.abbreviation || "HOM").substring(0, 3)}
                <span
                  style={{ display: "block", fontSize: 10, color: "#64748b", marginTop: 2 }}
                >
                  {evt.away_team.name} @ {evt.home_team.name}
                </span>
              </button>
            );
          })}
        </div>
      )}

      {/* Player props display */}
      {selectedEventId && playerNames.length > 0 && (
        <>
          {/* Player selector with search */}
          <div style={{ marginBottom: 20 }}>
            <div style={{ position: "relative", marginBottom: 12 }}>
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
                placeholder="Search players..."
                value={search}
                onChange={(e) => {
                  setSearch(e.target.value);
                  setSelectedPlayerName(null);
                }}
                style={{
                  padding: "10px 14px 10px 32px",
                  borderRadius: 10,
                  fontSize: 14,
                  background: "#0a0f24",
                  border: "1px solid #1e293b",
                  color: "#f0f6fc",
                  outline: "none",
                  width: "100%",
                  maxWidth: 400,
                }}
              />
            </div>
            <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
              {filteredPlayers.slice(0, 40).map((name) => {
                const isSel = name === selectedPlayerName;
                const propCount = playerPropMap.get(name)?.length ?? 0;
                return (
                  <button
                    key={name}
                    onClick={() => setSelectedPlayerName(name)}
                    style={{
                      padding: "10px 16px",
                      borderRadius: 12,
                      fontSize: 13,
                      fontWeight: 700,
                      border: isSel ? "1px solid #c9a84c" : "1px solid #1e293b",
                      background: isSel ? "rgba(201,168,76,0.1)" : "#0a0f24",
                      color: isSel ? "#c9a84c" : "#f0f6fc",
                      cursor: "pointer",
                    }}
                  >
                    {name}
                    <span
                      style={{
                        display: "block",
                        fontSize: 10,
                        color: "#64748b",
                        marginTop: 2,
                      }}
                    >
                      {propCount} market{propCount !== 1 ? "s" : ""}
                    </span>
                  </button>
                );
              })}
            </div>
          </div>

          {/* Selected player props */}
          {selectedProps.length > 0 ? (
            <div style={{ display: "grid", gap: 14 }}>
              {selectedProps.map((prop, pi) => {
                // Find best over/under across all lines
                let bestOverPrice = -Infinity;
                let bestUnderPrice = -Infinity;
                for (const l of prop.lines) {
                  if (l.overPrice != null && l.overPrice > bestOverPrice)
                    bestOverPrice = l.overPrice;
                  if (l.underPrice != null && l.underPrice > bestUnderPrice)
                    bestUnderPrice = l.underPrice;
                }

                // Compute line range
                const lines = prop.lines.map((l) => l.line).filter((l) => l != null) as number[];
                const lineRange =
                  lines.length > 0
                    ? Math.min(...lines) === Math.max(...lines)
                      ? `${Math.min(...lines)}`
                      : `${Math.min(...lines)} – ${Math.max(...lines)}`
                    : "—";

                return (
                  <div
                    key={pi}
                    style={{
                      background: "#0a0f24",
                      borderRadius: 14,
                      border: "1px solid #1e293b",
                      padding: "18px 20px",
                    }}
                  >
                    <div
                      style={{
                        display: "flex",
                        justifyContent: "space-between",
                        alignItems: "center",
                        marginBottom: 12,
                      }}
                    >
                      <span style={{ fontSize: 15, fontWeight: 700, color: "#f0f6fc" }}>
                        {prop.marketName}
                      </span>
                      {prop.lines.length > 1 && (
                        <span
                          style={{
                            display: "flex",
                            alignItems: "center",
                            gap: 4,
                            fontSize: 11,
                            color: "#c9a84c",
                            fontWeight: 600,
                          }}
                        >
                          <CheckCircle size={12} /> {prop.lines.length} books
                        </span>
                      )}
                    </div>

                    {/* Best over + line range */}
                    <div
                      style={{
                        display: "grid",
                        gridTemplateColumns: "1fr 1fr",
                        gap: 12,
                        marginBottom: 12,
                      }}
                    >
                      <div
                        style={{
                          background: "rgba(201,168,76,0.05)",
                          borderRadius: 8,
                          padding: "8px 12px",
                        }}
                      >
                        <div style={{ fontSize: 10, color: "#64748b", marginBottom: 2 }}>
                          Line Range
                        </div>
                        <div style={{ fontSize: 13, fontWeight: 700, color: "#c9a84c" }}>
                          {lineRange}
                        </div>
                      </div>
                      <div
                        style={{
                          background: "rgba(201,168,76,0.05)",
                          borderRadius: 8,
                          padding: "8px 12px",
                        }}
                      >
                        <div style={{ fontSize: 10, color: "#64748b", marginBottom: 2 }}>
                          Books
                        </div>
                        <div style={{ fontSize: 13, fontWeight: 700, color: "#c9a84c" }}>
                          {prop.lines.length} bookmaker{prop.lines.length !== 1 ? "s" : ""}
                        </div>
                      </div>
                    </div>

                    {/* Bookmaker lines table */}
                    <div style={{ borderTop: "1px solid #1e293b", paddingTop: 10 }}>
                      {/* Header */}
                      <div
                        style={{
                          display: "grid",
                          gridTemplateColumns: "2fr 1fr 1fr",
                          padding: "6px 0",
                          borderBottom: "1px solid #1e293b",
                          fontSize: 10,
                          fontWeight: 700,
                          color: "#64748b",
                          textTransform: "uppercase",
                        }}
                      >
                        <span>Bookmaker</span>
                        <span style={{ textAlign: "center" }}>Line</span>
                        <span style={{ textAlign: "right" }}>O / U</span>
                      </div>
                      {prop.lines.slice(0, 12).map((line, li) => {
                        const isBestOver =
                          line.overPrice != null &&
                          bestOverPrice !== -Infinity &&
                          line.overPrice === bestOverPrice;
                        const isBestUnder =
                          line.underPrice != null &&
                          bestUnderPrice !== -Infinity &&
                          line.underPrice === bestUnderPrice;

                        return (
                          <div
                            key={li}
                            style={{
                              display: "grid",
                              gridTemplateColumns: "2fr 1fr 1fr",
                              padding: "8px 0",
                              borderBottom: "1px solid #1e293b20",
                              alignItems: "center",
                            }}
                          >
                            <span style={{ fontSize: 12, color: "#94a3b8" }}>
                              {line.bookmaker}
                            </span>
                            <span
                              style={{
                                fontSize: 13,
                                fontWeight: 700,
                                color: "#f0f6fc",
                                textAlign: "center",
                              }}
                            >
                              {line.line ?? "—"}
                            </span>
                            <span style={{ fontSize: 12, textAlign: "right" }}>
                              <span
                                style={{
                                  color: isBestOver ? "#c9a84c" : "#94a3b8",
                                  fontWeight: isBestOver ? 800 : 400,
                                }}
                              >
                                O {fmtOdds(line.overPrice)}
                              </span>
                              {" / "}
                              <span
                                style={{
                                  color: isBestUnder ? "#c9a84c" : "#94a3b8",
                                  fontWeight: isBestUnder ? 800 : 400,
                                }}
                              >
                                U {fmtOdds(line.underPrice)}
                              </span>
                            </span>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                );
              })}
            </div>
          ) : selectedPlayerName ? (
            <div style={{ textAlign: "center", padding: 60, color: "#64748b" }}>
              No props available for this player.
            </div>
          ) : (
            <div style={{ textAlign: "center", padding: 60, color: "#64748b" }}>
              Select a player to view their prop markets.
            </div>
          )}
        </>
      )}

      {selectedEventId && playerNames.length === 0 && !loading && (
        <div style={{ textAlign: "center", padding: 60, color: "#64748b" }}>
          No player props available for this event.
        </div>
      )}

      {!selectedEventId && !loading && (
        <div style={{ textAlign: "center", padding: 60, color: "#64748b" }}>
          Select an event to view player props.
        </div>
      )}
    </div>
  );
}