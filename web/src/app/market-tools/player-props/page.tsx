"use client";

import { useState, useEffect, useCallback } from "react";
import { UserCheck, Search, CheckCircle } from "lucide-react";
import { getApiBaseUrl } from "@/lib/api-base-url";

const API_BASE = getApiBaseUrl(process.env.NEXT_PUBLIC_API_URL);

const LEAGUES = ["MLB", "NFL", "NBA", "NHL", "NCAAF", "NCAAB"] as const;
type League = (typeof LEAGUES)[number];

interface SgoEvent {
  event_id: string;
  home_team: { name: string; abbreviation: string };
  away_team: { name: string; abbreviation: string };
  start_time: string | null;
  status: string;
}

interface PropLine {
  bookmaker: string;
  line: number | null;
  over_price: number | null;
  under_price: number | null;
}

interface PropMarket {
  market: string;
  lines: PropLine[];
}

interface PlayerProps {
  player_id: string;
  markets: PropMarket[];
}

interface PropsData {
  event_id: string;
  players: PlayerProps[];
  player_count: number;
  prop_count: number;
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

function getBestOver(lines: PropLine[]): { bookmaker: string; price: number | null } {
  if (!lines.length) return { bookmaker: "—", price: null };
  let best = lines[0];
  for (const l of lines) {
    if ((l.over_price ?? -Infinity) > (best.over_price ?? -Infinity)) best = l;
  }
  return { bookmaker: best.bookmaker, price: best.over_price };
}

function getLineRange(lines: PropLine[]): string {
  if (!lines.length) return "—";
  let min = Infinity, max = -Infinity;
  for (const l of lines) {
    if (l.line != null) {
      if (l.line < min) min = l.line;
      if (l.line > max) max = l.line;
    }
  }
  if (min === Infinity) return "—";
  return min === max ? `${min}` : `${min} – ${max}`;
}

export default function PlayerPropsPage() {
  const [activeLeague, setActiveLeague] = useState<League>("MLB");
  const [events, setEvents] = useState<SgoEvent[]>([]);
  const [loading, setLoading] = useState(true);

  const [selectedEvent, setSelectedEvent] = useState<SgoEvent | null>(null);
  const [propsData, setPropsData] = useState<PropsData | null>(null);
  const [propsLoading, setPropsLoading] = useState(false);

  // Player selection within props
  const [selectedPlayerId, setSelectedPlayerId] = useState<string | null>(null);
  const [search, setSearch] = useState("");

  const loadEvents = useCallback(async () => {
    setLoading(true);
    const data = await sgoFetch<{ events: SgoEvent[]; league: string; count: number }>(
      `/events?league=${activeLeague}`
    );
    setEvents(data?.events ?? []);
    setSelectedEvent(null);
    setPropsData(null);
    setSelectedPlayerId(null);
    setLoading(false);
  }, [activeLeague]);

  useEffect(() => { loadEvents(); }, [loadEvents]);

  const loadProps = async (evt: SgoEvent) => {
    setSelectedEvent(evt);
    setSelectedPlayerId(null);
    setPropsLoading(true);
    const data = await sgoFetch<PropsData>(`/events/${evt.event_id}/props`);
    setPropsData(data);
    setPropsLoading(false);
  };

  const selectedPlayer = propsData?.players.find((p) => p.player_id === selectedPlayerId) ?? null;

  return (
    <div style={{ maxWidth: 1200, margin: "0 auto", padding: "32px 24px" }}>
      {/* Header */}
      <div style={{
        display: "flex", alignItems: "center", gap: 14, marginBottom: 28,
        background: "#0a0f24", borderRadius: 14, border: "1px solid #1e293b", padding: "20px 24px",
      }}>
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
          <button key={lg} onClick={() => setActiveLeague(lg)} style={{
            padding: "8px 14px", borderRadius: 10, fontSize: 12, fontWeight: 700,
            background: activeLeague === lg ? "rgba(201,168,76,0.1)" : "#0a0f24",
            border: activeLeague === lg ? "1px solid #c9a84c" : "1px solid #1e293b",
            color: activeLeague === lg ? "#c9a84c" : "#94a3b8",
            cursor: "pointer",
          }}>{lg}</button>
        ))}
      </div>

      {/* Event selector */}
      <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginBottom: 24 }}>
        {events.map((evt) => {
          const isSel = selectedEvent?.event_id === evt.event_id;
          return (
            <button key={evt.event_id} onClick={() => loadProps(evt)} style={{
              padding: "10px 16px", borderRadius: 12, fontSize: 13, fontWeight: 600,
              border: isSel ? "1px solid #c9a84c" : "1px solid #1e293b",
              background: isSel ? "rgba(201,168,76,0.1)" : "#0a0f24",
              color: isSel ? "#c9a84c" : "#f0f6fc",
              cursor: "pointer",
            }}>
              {(evt.away_team.abbreviation || "AWY").substring(0, 3)} @ {(evt.home_team.abbreviation || "HOM").substring(0, 3)}
              <span style={{ display: "block", fontSize: 10, color: "#64748b", marginTop: 2 }}>
                {evt.away_team.name} @ {evt.home_team.name}
              </span>
            </button>
          );
        })}
      </div>

      {propsLoading && (
        <div style={{ textAlign: "center", padding: 40, color: "#94a3b8" }}>Loading player props...</div>
      )}

      {propsData && !propsLoading && (
        <>
          {/* Player selector */}
          <div style={{ marginBottom: 20 }}>
            <div style={{ position: "relative", marginBottom: 12 }}>
              <Search size={14} style={{ position: "absolute", left: 10, top: "50%", transform: "translateY(-50%)", color: "#64748b" }} />
              <input
                type="text" placeholder="Search players..." value={search}
                onChange={(e) => { setSearch(e.target.value); setSelectedPlayerId(null); }}
                style={{
                  padding: "10px 14px 10px 32px", borderRadius: 10, fontSize: 14,
                  background: "#0a0f24", border: "1px solid #1e293b",
                  color: "#f0f6fc", outline: "none", width: "100%", maxWidth: 400,
                }}
              />
            </div>
            <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
              {propsData.players
                .filter((p) => !search || p.player_id.toLowerCase().includes(search.toLowerCase()))
                .slice(0, 40)
                .map((p) => {
                  const isSel = p.player_id === selectedPlayerId;
                  const marketCount = p.markets.length;
                  return (
                    <button key={p.player_id} onClick={() => setSelectedPlayerId(p.player_id)} style={{
                      padding: "10px 16px", borderRadius: 12, fontSize: 13, fontWeight: 700,
                      border: isSel ? "1px solid #c9a84c" : "1px solid #1e293b",
                      background: isSel ? "rgba(201,168,76,0.1)" : "#0a0f24",
                      color: isSel ? "#c9a84c" : "#f0f6fc",
                      cursor: "pointer",
                    }}>
                      {p.player_id}
                      <span style={{ display: "block", fontSize: 10, color: "#64748b", marginTop: 2 }}>
                        {marketCount} market{marketCount !== 1 ? "s" : ""}
                      </span>
                    </button>
                  );
                })}
            </div>
          </div>

          {/* Selected player props */}
          {selectedPlayer ? (
            <div style={{ display: "grid", gap: 14 }}>
              {selectedPlayer.markets.map((market, mi) => (
                <div key={mi} style={{
                  background: "#0a0f24", borderRadius: 14, border: "1px solid #1e293b", padding: "18px 20px",
                }}>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
                    <span style={{ fontSize: 15, fontWeight: 700, color: "#f0f6fc" }}>{market.market}</span>
                    {market.lines.length > 1 && (
                      <span style={{
                        display: "flex", alignItems: "center", gap: 4,
                        fontSize: 11, color: "#c9a84c", fontWeight: 600,
                      }}>
                        <CheckCircle size={12} /> {market.lines.length} books
                      </span>
                    )}
                  </div>

                  {/* Best over + line range */}
                  {(() => {
                    const best = getBestOver(market.lines);
                    return (
                      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12, marginBottom: 12 }}>
                        <div style={{ background: "rgba(201,168,76,0.05)", borderRadius: 8, padding: "8px 12px" }}>
                          <div style={{ fontSize: 10, color: "#64748b", marginBottom: 2 }}>Best Over Price</div>
                          <div style={{ fontSize: 13, fontWeight: 700, color: "#c9a84c" }}>
                            {best.bookmaker} {fmtOdds(best.price)}
                          </div>
                        </div>
                        <div style={{ background: "rgba(201,168,76,0.05)", borderRadius: 8, padding: "8px 12px" }}>
                          <div style={{ fontSize: 10, color: "#64748b", marginBottom: 2 }}>Line Range</div>
                          <div style={{ fontSize: 13, fontWeight: 700, color: "#c9a84c" }}>{getLineRange(market.lines)}</div>
                        </div>
                      </div>
                    );
                  })()}

                  {/* Bookmaker lines */}
                  <div style={{ borderTop: "1px solid #1e293b", paddingTop: 10 }}>
                    {market.lines.slice(0, 8).map((line, li) => (
                      <div key={li} style={{
                        display: "grid", gridTemplateColumns: "2fr 80px 1fr",
                        padding: "6px 0", alignItems: "center",
                      }}>
                        <span style={{ fontSize: 12, color: "#94a3b8" }}>{line.bookmaker}</span>
                        <span style={{ fontSize: 13, fontWeight: 700, color: "#f0f6fc", textAlign: "center" }}>
                          {line.line ?? "—"}
                        </span>
                        <span style={{ fontSize: 12, color: "#c9a84c", textAlign: "right" }}>
                          O {fmtOdds(line.over_price)} / U {fmtOdds(line.under_price)}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div style={{ textAlign: "center", padding: 60, color: "#64748b" }}>
              Select a player to view their prop markets.
            </div>
          )}
        </>
      )}

      {!propsData && !propsLoading && !loading && (
        <div style={{ textAlign: "center", padding: 60, color: "#64748b" }}>
          Select an event to view player props.
        </div>
      )}
    </div>
  );
}