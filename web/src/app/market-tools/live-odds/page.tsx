"use client";

import { useState, useEffect, useCallback } from "react";
import { TrendingUp, AlertTriangle, Search } from "lucide-react";
import { getApiBaseUrl } from "@/lib/api-base-url";

const API_BASE = getApiBaseUrl(process.env.NEXT_PUBLIC_API_URL);

const LEAGUES = ["MLB", "NFL", "NBA", "NHL", "NCAAF", "NCAAB"] as const;
type League = (typeof LEAGUES)[number];

interface SgoEvent {
  event_id: string;
  sport: string;
  league: string;
  home_team: { name: string; abbreviation: string };
  away_team: { name: string; abbreviation: string };
  start_time: string | null;
  status: string;
  home_score: number | null;
  away_score: number | null;
  period: string | null;
}

interface SgoBook {
  bookmaker: string;
  moneyline_home: number | null;
  moneyline_away: number | null;
  spread_home: number | null;
  spread_away: number | null;
  total_over: number | null;
  total_under: number | null;
}

interface OddsData {
  event_id: string;
  books: SgoBook[];
  book_count: number;
  consensus?: SgoBook;
  fair_odds?: { moneyline_home: number | null; moneyline_away: number | null; total: number | null };
}

function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("sbme_dfs_token");
}

async function sgoFetch<T>(endpoint: string): Promise<T | null> {
  try {
    const token = getToken();
    const res = await fetch(`${API_BASE}/sgo${endpoint}`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    });
    if (!res.ok) return null;
    const json = await res.json();
    return (json?.data ?? null) as T | null;
  } catch {
    return null;
  }
}

function fmtOdds(v: number | null | undefined): string {
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
    return d.toLocaleString([], { month: "short", day: "numeric", hour: "numeric", minute: "2-digit", timeZoneName: "short" });
  } catch {
    return iso;
  }
}

export default function LiveOddsPage() {
  const [activeLeague, setActiveLeague] = useState<League>("MLB");
  const [events, setEvents] = useState<SgoEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState("");

  // Odds for each expanded event
  const [expandedOdds, setExpandedOdds] = useState<Record<string, OddsData | null>>({});
  const [loadingOdds, setLoadingOdds] = useState<Record<string, boolean>>({});
  const [expanded, setExpanded] = useState<Record<string, boolean>>({});

  const loadEvents = useCallback(async () => {
    setLoading(true);
    setError(null);
    const data = await sgoFetch<{ events: SgoEvent[]; league: string; count: number }>(
      `/events?league=${activeLeague}`
    );
    if (data === null) {
      setError("Unable to load events. SportsGameOdds data may be temporarily unavailable.");
      setEvents([]);
    } else {
      setEvents(data.events ?? []);
    }
    setExpandedOdds({});
    setExpanded({});
    setLoading(false);
  }, [activeLeague]);

  useEffect(() => { loadEvents(); }, [loadEvents]);

  const toggleExpand = async (eventId: string) => {
    if (expanded[eventId]) {
      setExpanded((prev) => ({ ...prev, [eventId]: false }));
      return;
    }
    setExpanded((prev) => ({ ...prev, [eventId]: true }));
    if (expandedOdds[eventId] !== undefined) return; // already loaded
    setLoadingOdds((prev) => ({ ...prev, [eventId]: true }));
    const data = await sgoFetch<OddsData>(`/events/${eventId}/odds`);
    setExpandedOdds((prev) => ({ ...prev, [eventId]: data }));
    setLoadingOdds((prev) => ({ ...prev, [eventId]: false }));
  };

  const filtered = events.filter((e) => {
    if (!search) return true;
    const q = search.toLowerCase();
    const hn = e.home_team.name.toLowerCase();
    const an = e.away_team.name.toLowerCase();
    const ha = e.home_team.abbreviation.toLowerCase();
    const aa = e.away_team.abbreviation.toLowerCase();
    return hn.includes(q) || an.includes(q) || ha.includes(q) || aa.includes(q);
  });

  return (
    <div style={{ maxWidth: 1200, margin: "0 auto", padding: "32px 24px" }}>
      {/* Header */}
      <div style={{
        display: "flex", alignItems: "center", gap: 14, marginBottom: 28,
        background: "#0a0f24", borderRadius: 14, border: "1px solid #1e293b", padding: "20px 24px",
      }}>
        <TrendingUp size={26} color="#c9a84c" />
        <div style={{ flex: 1 }}>
          <h1 style={{ fontSize: 24, fontWeight: 900, color: "#c9a84c", margin: 0 }}>Live Odds</h1>
          <p style={{ fontSize: 13, color: "#94a3b8", margin: "2px 0 0" }}>
            Real-time odds, spreads, and totals — SportsGameOdds
          </p>
        </div>
        <button onClick={loadEvents} style={{
          padding: "8px 16px", borderRadius: 10, background: "rgba(201,168,76,0.1)",
          border: "1px solid rgba(201,168,76,0.3)", color: "#c9a84c", fontWeight: 600,
          cursor: "pointer", fontSize: 13,
        }}>Refresh</button>
      </div>

      {/* League tabs + search */}
      <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 20, flexWrap: "wrap" }}>
        {LEAGUES.map((lg) => (
          <button key={lg} onClick={() => setActiveLeague(lg)} style={{
            padding: "8px 16px", borderRadius: 10, fontSize: 12, fontWeight: 700,
            background: activeLeague === lg ? "rgba(201,168,76,0.1)" : "#0a0f24",
            border: activeLeague === lg ? "1px solid #c9a84c" : "1px solid #1e293b",
            color: activeLeague === lg ? "#c9a84c" : "#94a3b8",
            cursor: "pointer",
          }}>{lg}</button>
        ))}
        <div style={{ position: "relative", marginLeft: "auto" }}>
          <Search size={14} style={{ position: "absolute", left: 10, top: "50%", transform: "translateY(-50%)", color: "#64748b" }} />
          <input
            type="text" placeholder="Search teams..." value={search}
            onChange={(e) => setSearch(e.target.value)}
            style={{
              padding: "8px 14px 8px 32px", borderRadius: 10, fontSize: 13,
              background: "#0a0f24", border: "1px solid #1e293b",
              color: "#f0f6fc", outline: "none", minWidth: 200,
            }}
          />
        </div>
      </div>

      {loading && (
        <div style={{ textAlign: "center", padding: 60, color: "#94a3b8", fontSize: 14 }}>Loading events...</div>
      )}
      {error && (
        <div style={{ textAlign: "center", padding: 40, color: "#ef4444" }}>{error}</div>
      )}

      {/* Event cards */}
      <div style={{ display: "grid", gap: 12 }}>
        {filtered.map((evt) => {
          const live = isLive(evt.status);
          const isExpanded = expanded[evt.event_id];
          const odds = expandedOdds[evt.event_id];
          const odsLoading = loadingOdds[evt.event_id];
          const consensus = odds?.consensus;

          return (
            <div key={evt.event_id} style={{
              background: live ? "rgba(201,168,76,0.04)" : "#0a0f24",
              borderRadius: 14, border: live ? "1px solid rgba(201,168,76,0.2)" : "1px solid #1e293b",
              overflow: "hidden",
            }}>
              {/* Event row — clickable */}
              <button onClick={() => toggleExpand(evt.event_id)} style={{
                width: "100%", padding: "16px 20px", background: "none", border: "none",
                cursor: "pointer", display: "flex", justifyContent: "space-between", alignItems: "center",
                color: "#f0f6fc", textAlign: "left",
              }}>
                <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
                  {live && (
                    <span style={{
                      padding: "3px 8px", borderRadius: 6, fontSize: 10, fontWeight: 800,
                      background: "rgba(239,68,68,0.15)", color: "#ef4444", textTransform: "uppercase",
                      flexShrink: 0,
                    }}>● LIVE</span>
                  )}
                  <div>
                    <div style={{ fontSize: 15, fontWeight: 700 }}>
                      {evt.away_team.abbreviation || evt.away_team.name} @ {evt.home_team.abbreviation || evt.home_team.name}
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
                      {evt.period && <span style={{ fontSize: 10, color: "#64748b", marginLeft: 4 }}>{evt.period}</span>}
                    </span>
                  )}
                  <span style={{ color: "#64748b", fontSize: 18 }}>{isExpanded ? "▲" : "▼"}</span>
                </div>
              </button>

              {/* Expanded odds panel */}
              {isExpanded && (
                <div style={{ borderTop: "1px solid #1e293b", padding: "16px 20px" }}>
                  {odsLoading ? (
                    <div style={{ textAlign: "center", padding: 24, color: "#94a3b8" }}>Loading odds...</div>
                  ) : odds === null ? (
                    <div style={{ textAlign: "center", padding: 24, color: "#64748b" }}>Data currently unavailable</div>
                  ) : odds && odds.books.length > 0 ? (
                    <>
                      {/* Consensus */}
                      {consensus && (
                        <div style={{
                          display: "flex", alignItems: "center", gap: 10, marginBottom: 16,
                          background: "rgba(201,168,76,0.06)", borderRadius: 8, padding: "10px 14px",
                        }}>
                          <span style={{ fontSize: 11, color: "#c9a84c", fontWeight: 700, textTransform: "uppercase" }}>Consensus</span>
                          <span style={{ fontSize: 13, color: "#f0f6fc", fontWeight: 600 }}>
                            ML: {fmtOdds(consensus.moneyline_home)}/{fmtOdds(consensus.moneyline_away)}
                          </span>
                          {consensus.spread_home != null && (
                            <span style={{ fontSize: 13, color: "#94a3b8" }}>
                              Spread: {consensus.spread_home > 0 ? "+" : ""}{consensus.spread_home}
                            </span>
                          )}
                          {consensus.total_over != null && (
                            <span style={{ fontSize: 13, color: "#94a3b8" }}>
                              Total: O{consensus.total_over}/U{consensus.total_under}
                            </span>
                          )}
                        </div>
                      )}

                      {/* Bookmaker comparison table */}
                      <div style={{ overflowX: "auto" }}>
                        <div style={{
                          display: "grid", gridTemplateColumns: "1.5fr 1fr 1fr 1fr 1fr 1fr", gap: 4,
                          padding: "8px 0", borderBottom: "1px solid #1e293b",
                          fontSize: 10, fontWeight: 700, color: "#64748b", textTransform: "uppercase",
                          minWidth: 600,
                        }}>
                          <span>Bookmaker</span>
                          <span style={{ textAlign: "center" }}>ML Home</span>
                          <span style={{ textAlign: "center" }}>ML Away</span>
                          <span style={{ textAlign: "center" }}>Spread H</span>
                          <span style={{ textAlign: "center" }}>Spread A</span>
                          <span style={{ textAlign: "center" }}>Total O/U</span>
                        </div>
                        {odds.books.map((b, i) => (
                          <div key={i} style={{
                            display: "grid", gridTemplateColumns: "1.5fr 1fr 1fr 1fr 1fr 1fr", gap: 4,
                            padding: "10px 0", borderBottom: "1px solid #1e293b20", alignItems: "center",
                            minWidth: 600,
                          }}>
                            <span style={{ fontSize: 12, color: "#94a3b8", fontWeight: 500 }}>{b.bookmaker}</span>
                            <span style={{ fontSize: 13, fontWeight: 600, color: "#f0f6fc", textAlign: "center" }}>
                              {fmtOdds(b.moneyline_home)}
                            </span>
                            <span style={{ fontSize: 13, fontWeight: 600, color: "#f0f6fc", textAlign: "center" }}>
                              {fmtOdds(b.moneyline_away)}
                            </span>
                            <span style={{ fontSize: 13, color: "#94a3b8", textAlign: "center" }}>
                              {b.spread_home != null ? (b.spread_home > 0 ? "+" : "") + b.spread_home : "—"}
                            </span>
                            <span style={{ fontSize: 13, color: "#94a3b8", textAlign: "center" }}>
                              {b.spread_away != null ? (b.spread_away > 0 ? "+" : "") + b.spread_away : "—"}
                            </span>
                            <span style={{ fontSize: 13, color: "#94a3b8", textAlign: "center" }}>
                              {b.total_over != null ? `O${b.total_over}/U${b.total_under}` : "—"}
                            </span>
                          </div>
                        ))}
                      </div>
                    </>
                  ) : (
                    <div style={{ textAlign: "center", padding: 24, color: "#64748b" }}>Data currently unavailable</div>
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