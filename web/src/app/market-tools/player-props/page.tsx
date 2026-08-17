"use client";

import { useState, useMemo } from "react";
import { UserCheck, Search, RotateCcw } from "lucide-react";
import { useEvents } from "@/lib/use-events";
import type { SBEvent, SBMarket } from "@/lib/sbevent";
import { formatBookmakerName } from "@/lib/bookmakers";
import { LastFive } from "@/lib/last-five";

const LEAGUES = ["MLB", "NFL", "NBA", "NHL", "NCAAF", "NCAAB"] as const;
type League = (typeof LEAGUES)[number];

const PROP_TYPE_LABELS: Record<string, string> = {
  batting_RBI: "Runs Batted In",
  batting_hits: "Hits",
  batting_singles: "Singles",
  batting_homeRuns: "Home Runs",
  batting_totalBases: "Total Bases",
  batting_basesOnBalls: "Walks",
  batting_strikeouts: "Strikeouts",
  batting_stolenBases: "Stolen Bases",
  batting_doubles: "Doubles",
  "batting_hits+runs+rbi": "Hits + Runs + RBI",
  "batting_runs+rbi": "Runs + RBI",
  batting_triples: "Triples",
  batting_firstHomeRun: "First Home Run",
  fantasyScore: "Fantasy Score",
  pitching_earnedRuns: "Earned Runs",
  pitching_strikeouts: "Pitching Strikeouts",
  pitching_basesOnBalls: "Pitching Walks",
  pitching_hits: "Pitching Hits",
  pitching_outs: "Pitching Outs",
  points: "Points",
};

function fmtOdds(v: number | null | undefined): string {
  if (v == null) return "—";
  return v > 0 ? `+${v}` : `${v}`;
}

function propTypeLabel(statId: string): string {
  return PROP_TYPE_LABELS[statId] || statId || "Prop";
}

interface PlayerPoolEntry {
  playerId: string;
  playerName: string;
  teamAbbr: string;
  opponentAbbr: string;
  game: string;
  eventId: string;
  marketCount: number;
  markets: SBMarket[];
}

/**
 * Combine all prop-eligible players across every event, deduplicated by
 * player id. Team/opponent are resolved from the event's player→team map
 * (SGO stat_entity_id is the PLAYER id, not the team id).
 */
function buildPlayerPool(events: SBEvent[]): PlayerPoolEntry[] {
  const pool = new Map<string, PlayerPoolEntry>();

  for (const event of events) {
    // player_id -> team_id from the event roster
    const teamById = new Map<string, string>();
    for (const p of event.players ?? []) {
      if (p.player_id) teamById.set(p.player_id, p.team_id);
    }

    for (const market of event.markets ?? []) {
      if (market.bet_type !== "player_prop") continue;
      const pid = market.player_id || market.player_name;
      if (!pid) continue;

      const key = market.player_id || `name:${market.player_name}`;
      if (!pool.has(key)) {
        const playerTeamId = teamById.get(market.player_id) || "";
        const isHome = playerTeamId && event.home_team.team_id === playerTeamId;
        const teamAbbr = isHome ? event.home_team.abbreviation : event.away_team.abbreviation;
        const opponentAbbr = isHome ? event.away_team.abbreviation : event.home_team.abbreviation;
        pool.set(key, {
          playerId: market.player_id || market.player_name || "unknown",
          playerName: market.player_name || "Unknown",
          teamAbbr,
          opponentAbbr,
          game: `${event.away_team.abbreviation || "AWY"} @ ${event.home_team.abbreviation || "HOM"}`,
          eventId: event.id,
          marketCount: 0,
          markets: [],
        });
      }

      const entry = pool.get(key)!;
      entry.markets.push(market);
      entry.marketCount++;
    }
  }

  return Array.from(pool.values()).sort((a, b) => a.playerName.localeCompare(b.playerName));
}

interface MarketBookRow {
  propType: string;
  line: number | null;
  overPrice: number | null;
  underPrice: number | null;
  bookmaker: string;
  isBestOver: boolean;
  isBestUnder: boolean;
  fairOdds: number | null;
  consensus: number | null;
}

/** Flatten a player's prop markets into (prop, bookmaker) rows with fair data. */
function buildMarketRows(entry: PlayerPoolEntry): MarketBookRow[] {
  const byStat = new Map<string, SBMarket[]>();
  for (const m of entry.markets) {
    const key = m.stat_id || m.market_name;
    if (!byStat.has(key)) byStat.set(key, []);
    byStat.get(key)!.push(m);
  }

  const rows: MarketBookRow[] = [];

  for (const [statId, markets] of byStat) {
    const label = propTypeLabel(statId);
    const isOU = markets.some((m) => m.side === "over" || m.side === "under");
    const isYN = markets.some((m) => (m.market_name || "").toLowerCase().includes("yes/no"));

    const first = markets[0];
    const fairOdds = first?.fair_odds ?? null;
    const fairOverUnder = first?.fair_over_under ?? null;

    const bookLines = new Map<string, { over: number | null; under: number | null; line: number | null }>();
    for (const m of markets) {
      for (const book of m.books ?? []) {
        if (!book.available) continue;
        const bk = book.bookmaker || "Unknown";
        if (!bookLines.has(bk)) bookLines.set(bk, { over: null, under: null, line: null });
        const bl = bookLines.get(bk)!;
        if (book.over_under != null) bl.line = book.over_under;
        if (isOU) {
          if (m.side === "over" && book.moneyline != null) bl.over = book.moneyline;
          if (m.side === "under" && book.moneyline != null) bl.under = book.moneyline;
        } else if (isYN) {
          const oid = (m.odd_id || "").toLowerCase();
          if (oid.endsWith("-yes") && book.moneyline != null) bl.over = book.moneyline;
          if (oid.endsWith("-no") && book.moneyline != null) bl.under = book.moneyline;
        }
      }
    }

    let bestOver = -Infinity;
    let bestUnder = -Infinity;
    for (const bl of bookLines.values()) {
      if (bl.over != null && bl.over > bestOver) bestOver = bl.over;
      if (bl.under != null && bl.under > bestUnder) bestUnder = bl.under;
    }

    const sorted = Array.from(bookLines.entries()).sort((a, b) => a[0].localeCompare(b[0]));
    for (const [bookmaker, bl] of sorted) {
      rows.push({
        propType: label,
        line: bl.line ?? fairOverUnder,
        overPrice: bl.over,
        underPrice: bl.under,
        bookmaker,
        isBestOver: bl.over != null && bl.over === bestOver,
        isBestUnder: bl.under != null && bl.under === bestUnder,
        fairOdds,
        consensus: fairOverUnder,
      });
    }
  }

  return rows;
}

const thStyle: React.CSSProperties = {
  padding: "8px 12px",
  textAlign: "left",
  fontSize: 10,
  fontWeight: 700,
  color: "#64748b",
  textTransform: "uppercase",
  whiteSpace: "nowrap",
};
const tdStyle: React.CSSProperties = { padding: "9px 12px", whiteSpace: "nowrap", fontSize: 12 };

export default function PlayerPropsPage() {
  const [activeLeague, setActiveLeague] = useState<League>("MLB");
  const [selectedEventId, setSelectedEventId] = useState<string | null>(null);
  const [selectedPlayerId, setSelectedPlayerId] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [teamFilter, setTeamFilter] = useState<string>("");
  const [propTypeFilter, setPropTypeFilter] = useState<string>("");
  const [bookmakerFilter, setBookmakerFilter] = useState<string>("");

  const { events, loading, error } = useEvents(activeLeague);

  // Full deduplicated player pool (ALL GAMES by default)
  const pool = useMemo(() => buildPlayerPool(events), [events]);

  // Game filter: null = ALL GAMES
  const filteredEvents = useMemo(() => {
    if (!selectedEventId) return events;
    return events.filter((e) => e.id === selectedEventId);
  }, [events, selectedEventId]);

  // Player pool filtered by game + team + search
  const visiblePool = useMemo(() => {
    const q = search.toLowerCase();
    return pool.filter((p) => {
      if (selectedEventId && p.eventId !== selectedEventId) return false;
      if (teamFilter && p.teamAbbr !== teamFilter) return false;
      if (q && !p.playerName.toLowerCase().includes(q)) return false;
      return true;
    });
  }, [pool, selectedEventId, teamFilter, search]);

  // Team options from the full pool
  const teamOptions = useMemo(() => {
    const set = new Set<string>();
    for (const p of pool) if (p.teamAbbr) set.add(p.teamAbbr);
    return Array.from(set).sort();
  }, [pool]);

  // Bookmaker options from visible events
  const bookmakerOptions = useMemo(() => {
    const set = new Set<string>();
    for (const e of events) for (const b of e.bookmakers ?? []) if (b) set.add(b);
    return Array.from(set).sort();
  }, [events]);

  const selectedPlayer = useMemo(
    () => pool.find((p) => p.playerId === selectedPlayerId) ?? null,
    [pool, selectedPlayerId]
  );

  // Market rows for the selected player, filtered by prop type + bookmaker
  const marketRows = useMemo(() => {
    if (!selectedPlayer) return [];
    return buildMarketRows(selectedPlayer).filter((r) => {
      if (propTypeFilter && r.propType !== propTypeFilter) return false;
      if (bookmakerFilter && r.bookmaker !== bookmakerFilter) return false;
      return true;
    });
  }, [selectedPlayer, propTypeFilter, bookmakerFilter]);

  // Prop type options for the selected player
  const propTypeOptions = useMemo(() => {
    if (!selectedPlayer) return [];
    const set = new Set<string>();
    for (const r of buildMarketRows(selectedPlayer)) set.add(r.propType);
    return Array.from(set).sort();
  }, [selectedPlayer]);

  const resetFilters = () => {
    setSelectedEventId(null);
    setSelectedPlayerId(null);
    setSearch("");
    setTeamFilter("");
    setPropTypeFilter("");
    setBookmakerFilter("");
  };

  return (
    <div style={{ maxWidth: 1280, margin: "0 auto", padding: "32px 24px" }}>
      {/* Header */}
      <div style={{ display: "flex", alignItems: "center", gap: 14, marginBottom: 28, background: "#0a0f24", borderRadius: 14, border: "1px solid #1e293b", padding: "20px 24px" }}>
        <UserCheck size={26} color="#c9a84c" />
        <div style={{ flex: 1 }}>
          <h1 style={{ fontSize: 24, fontWeight: 900, color: "#c9a84c", margin: 0 }}>Player Props</h1>
          <p style={{ fontSize: 13, color: "#94a3b8", margin: "2px 0 0" }}>
            Prop bets across sportsbooks — SportsGameOdds
          </p>
        </div>
      </div>

      {/* League tabs */}
      <div style={{ display: "flex", gap: 8, marginBottom: 16, flexWrap: "wrap" }}>
        {LEAGUES.map((lg) => (
          <button key={lg} onClick={() => { setActiveLeague(lg); resetFilters(); }}
            style={{ padding: "8px 14px", borderRadius: 10, fontSize: 12, fontWeight: 700, background: activeLeague === lg ? "rgba(201,168,76,0.1)" : "#0a0f24", border: activeLeague === lg ? "1px solid #c9a84c" : "1px solid #1e293b", color: activeLeague === lg ? "#c9a84c" : "#94a3b8", cursor: "pointer" }}>
            {lg}
          </button>
        ))}
      </div>

      {loading && <div style={{ textAlign: "center", padding: 40, color: "#94a3b8" }}>Loading events...</div>}
      {error && <div style={{ textAlign: "center", padding: 40, color: "#ef4444" }}>{error}</div>}

      {!loading && !error && (
        <>
          {/* Game filter — ALL GAMES default */}
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginBottom: 16, alignItems: "center" }}>
            <button onClick={() => { setSelectedEventId(null); setSelectedPlayerId(null); }}
              style={{ padding: "10px 16px", borderRadius: 12, fontSize: 13, fontWeight: 800, border: selectedEventId === null ? "1px solid #c9a84c" : "1px solid #1e293b", background: selectedEventId === null ? "rgba(201,168,76,0.1)" : "#0a0f24", color: selectedEventId === null ? "#c9a84c" : "#f0f6fc", cursor: "pointer" }}>
              ALL GAMES
            </button>
            {events.map((evt) => {
              const isSel = evt.id === selectedEventId;
              return (
                <button key={evt.id} onClick={() => { setSelectedEventId(evt.id); setSelectedPlayerId(null); }}
                  style={{ padding: "10px 16px", borderRadius: 12, fontSize: 13, fontWeight: 600, border: isSel ? "1px solid #c9a84c" : "1px solid #1e293b", background: isSel ? "rgba(201,168,76,0.1)" : "#0a0f24", color: isSel ? "#c9a84c" : "#f0f6fc", cursor: "pointer" }}>
                  {(evt.away_team.abbreviation || "AWY").substring(0, 3)} @ {(evt.home_team.abbreviation || "HOM").substring(0, 3)}
                </button>
              );
            })}
          </div>

          {/* Filters */}
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginBottom: 20, alignItems: "center" }}>
            <button onClick={resetFilters} title="Reset all filters"
              style={{ display: "flex", alignItems: "center", gap: 6, padding: "8px 12px", borderRadius: 10, fontSize: 12, fontWeight: 700, background: "#0a0f24", border: "1px solid #1e293b", color: "#94a3b8", cursor: "pointer" }}>
              <RotateCcw size={13} /> All Players
            </button>
            <FilterSelect label="Team" value={teamFilter} options={teamOptions} onChange={setTeamFilter} />
            <FilterSelect label="Prop Type" value={propTypeFilter} options={propTypeOptions} onChange={setPropTypeFilter} />
            <FilterSelect label="Bookmaker" value={bookmakerFilter} options={bookmakerOptions} onChange={setBookmakerFilter} formatLabel={formatBookmakerName} />
            <div style={{ position: "relative", marginLeft: "auto" }}>
              <Search size={14} style={{ position: "absolute", left: 10, top: "50%", transform: "translateY(-50%)", color: "#64748b" }} />
              <input type="text" placeholder="Search players..." value={search} onChange={(e) => setSearch(e.target.value)}
                style={{ padding: "8px 14px 8px 32px", borderRadius: 10, fontSize: 13, background: "#0a0f24", border: "1px solid #1e293b", color: "#f0f6fc", outline: "none", width: 220 }} />
            </div>
          </div>

          {/* Player pool table */}
          <div style={{ background: "#0a0f24", borderRadius: 14, border: "1px solid #1e293b", overflow: "hidden", marginBottom: 24 }}>
            <table style={{ width: "100%", borderCollapse: "collapse" }}>
              <thead>
                <tr style={{ borderBottom: "1px solid #1e293b" }}>
                  <th style={thStyle}>Player</th>
                  <th style={thStyle}>Team</th>
                  <th style={thStyle}>Opponent</th>
                  <th style={thStyle}>Game</th>
                  <th style={{ ...thStyle, textAlign: "right" }}>Markets</th>
                </tr>
              </thead>
              <tbody>
                {visiblePool.length === 0 ? (
                  <tr><td colSpan={5} style={{ ...tdStyle, textAlign: "center", color: "#64748b", padding: 40 }}>No players match the current filters.</td></tr>
                ) : (
                  visiblePool.slice(0, 300).map((p) => {
                    const isSel = p.playerId === selectedPlayerId;
                    return (
                      <tr key={p.playerId} onClick={() => setSelectedPlayerId(isSel ? null : p.playerId)}
                        style={{ cursor: "pointer", borderBottom: "1px solid #1e293b20", background: isSel ? "rgba(201,168,76,0.08)" : "transparent" }}>
                        <td style={{ ...tdStyle, color: "#f0f6fc", fontWeight: 700 }}>{p.playerName}</td>
                        <td style={{ ...tdStyle, color: "#c9a84c", fontWeight: 700 }}>{p.teamAbbr || "—"}</td>
                        <td style={{ ...tdStyle, color: "#94a3b8" }}>{p.opponentAbbr || "—"}</td>
                        <td style={{ ...tdStyle, color: "#64748b" }}>{p.game}</td>
                        <td style={{ ...tdStyle, color: "#c9a84c", fontWeight: 700, textAlign: "right" }}>{p.marketCount}</td>
                      </tr>
                    );
                  })
                )}
              </tbody>
            </table>
          </div>

          {/* Selected player's prop markets */}
          {selectedPlayer ? (
            <div style={{ background: "#0a0f24", borderRadius: 14, border: "1px solid #1e293b", padding: "20px 22px" }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
                <div>
                  <h2 style={{ fontSize: 18, fontWeight: 800, color: "#c9a84c", margin: 0 }}>{selectedPlayer.playerName}</h2>
                  <p style={{ fontSize: 12, color: "#64748b", margin: "2px 0 0" }}>
                    {selectedPlayer.teamAbbr} vs {selectedPlayer.opponentAbbr} · {selectedPlayer.game}
                  </p>
                </div>
                <button onClick={() => setSelectedPlayerId(null)} style={{ padding: "6px 12px", borderRadius: 8, fontSize: 11, fontWeight: 700, background: "#1a1f33", border: "1px solid #1e293b", color: "#94a3b8", cursor: "pointer" }}>Close</button>
              </div>

              {marketRows.length === 0 ? (
                <div style={{ textAlign: "center", padding: 40, color: "#64748b" }}>No prop markets match the current filters.</div>
              ) : (
                <div style={{ overflowX: "auto" }}>
                  <table style={{ width: "100%", borderCollapse: "collapse", minWidth: 760 }}>
                    <thead>
                      <tr style={{ borderBottom: "1px solid #1e293b" }}>
                        <th style={thStyle}>Prop</th>
                        <th style={thStyle}>Line</th>
                        <th style={{ ...thStyle, textAlign: "center" }}>Over</th>
                        <th style={{ ...thStyle, textAlign: "center" }}>Under</th>
                        <th style={thStyle}>Bookmaker</th>
                        <th style={{ ...thStyle, textAlign: "center" }}>Best Price</th>
                        <th style={{ ...thStyle, textAlign: "center" }}>Fair Odds</th>
                        <th style={{ ...thStyle, textAlign: "center" }}>Consensus</th>
                      </tr>
                    </thead>
                    <tbody>
                      {marketRows.map((r, i) => (
                        <tr key={i} style={{ borderBottom: "1px solid #1e293b20" }}>
                          <td style={{ ...tdStyle, color: "#f0f6fc", fontWeight: 600 }}>{r.propType}</td>
                          <td style={{ ...tdStyle, color: "#c9a84c", fontWeight: 700 }}>{r.line ?? "—"}</td>
                          <td style={{ ...tdStyle, textAlign: "center", color: r.isBestOver ? "#c9a84c" : "#94a3b8", fontWeight: r.isBestOver ? 800 : 400 }}>O {fmtOdds(r.overPrice)}</td>
                          <td style={{ ...tdStyle, textAlign: "center", color: r.isBestUnder ? "#c9a84c" : "#94a3b8", fontWeight: r.isBestUnder ? 800 : 400 }}>U {fmtOdds(r.underPrice)}</td>
                          <td style={{ ...tdStyle, color: "#94a3b8" }}>{formatBookmakerName(r.bookmaker)}</td>
                          <td style={{ ...tdStyle, textAlign: "center", color: "#c9a84c", fontWeight: 700, fontSize: 11 }}>
                            {r.overPrice != null || r.underPrice != null ? `O ${fmtOdds(r.overPrice)} · U ${fmtOdds(r.underPrice)}` : "—"}
                          </td>
                          <td style={{ ...tdStyle, textAlign: "center", color: "#94a3b8" }}>{fmtOdds(r.fairOdds)}</td>
                          <td style={{ ...tdStyle, textAlign: "center", color: "#94a3b8" }}>{r.consensus ?? "—"}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
              <div style={{ marginTop: 12 }}>
                <LastFive player={{ name: selectedPlayer.playerName, player_id: selectedPlayer.playerId }} platform="draftkings" />
              </div>
            </div>
          ) : null}
        </>
      )}
    </div>
  );
}

function FilterSelect({ label, value, options, onChange, formatLabel }: { label: string; value: string; options: string[]; onChange: (v: string) => void; formatLabel?: (v: string) => string }) {
  const fmt = formatLabel ?? ((v: string) => v);
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
      <span style={{ fontSize: 10, fontWeight: 700, color: "#64748b", textTransform: "uppercase" }}>{label}</span>
      <select value={value} onChange={(e) => onChange(e.target.value)}
        style={{ padding: "8px 10px", borderRadius: 10, fontSize: 12, fontWeight: 600, background: "#0a0f24", border: "1px solid #1e293b", color: value ? "#c9a84c" : "#94a3b8", cursor: "pointer" }}>
        <option value="">All</option>
        {options.map((o) => <option key={o} value={o}>{fmt(o)}</option>)}
      </select>
    </div>
  );
}