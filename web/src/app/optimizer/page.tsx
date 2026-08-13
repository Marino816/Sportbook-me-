"use client";

import { useState, useEffect } from "react";
import { useMutation } from "@tanstack/react-query";
import { Play, Loader2, Search, Filter } from "lucide-react";
import { getApiBaseUrl } from "@/lib/api-base-url";
import { fetchDFSSlates, runOptimizer, type LineupResponse } from "@/lib/api";

const API_BASE = getApiBaseUrl(process.env.NEXT_PUBLIC_API_URL);

const SPORTS = ["MLB", "NFL", "NBA", "NHL", "NCAAF", "NCAAB"] as const;
const PLATFORMS = ["draftkings", "fanduel"] as const;
const STRATEGIES = ["balanced", "cash", "gpp", "aggressive"] as const;

interface SgoEvent {
  event_id: string;
  home_team: { name: string; abbreviation: string };
  away_team: { name: string; abbreviation: string };
  start_time: string | null;
  status: string;
  home_score: number | null;
  away_score: number | null;
  period: string | null;
}

interface SgoPlayer {
  player_id: string;
  name: string;
  team: string;
  position: string;
  league: string;
  sport: string;
}

interface PlayerProp {
  player_id: string;
  markets: Array<{
    market: string;
    lines: Array<{ bookmaker: string; line: number; over_price: number | null; under_price: number | null }>;
  }>;
}

async function sgoGet<T>(endpoint: string): Promise<T | null> {
  try {
    const token = localStorage.getItem("sbme_dfs_token");
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

function liveClass(status: string): boolean {
  const s = (status || "").toUpperCase();
  return s === "LIVE" || s === "IN_PLAY" || s === "INPLAY";
}

function fmtOdds(v: number | null | undefined): string {
  if (v == null) return "—";
  return v > 0 ? `+${v}` : `${v}`;
}

export default function OptimizerPage() {
  // ── State ──────────────────────────────────────────────────
  const [sport, setSport] = useState<string>("MLB");
  const [platform, setPlatform] = useState<string>("draftkings");
  const [bookmakerSource, setBookmakerSource] = useState<string>("Best Available");
  const [strategy, setStrategy] = useState<string>("balanced");
  const [lineupCount, setLineupCount] = useState(1);

  // SGO data
  const [events, setEvents] = useState<SgoEvent[]>([]);
  const [selectedEvent, setSelectedEvent] = useState<SgoEvent | null>(null);
  const [players, setPlayers] = useState<SgoPlayer[]>([]);
  const [props, setProps] = useState<PlayerProp[]>([]);
  const [bookmakers, setBookmakers] = useState<string[]>([]);
  const [sgoLoading, setSgoLoading] = useState(false);
  const [playersLoading, setPlayersLoading] = useState(false);

  // Filters
  const [playerSearch, setPlayerSearch] = useState("");
  const [posFilter, setPosFilter] = useState("ALL");
  const [teamFilter, setTeamFilter] = useState<string>("ALL");

  // Results
  const [lineups, setLineups] = useState<LineupResponse[]>([]);
  const [resolvedSlateId, setResolvedSlateId] = useState<number | null>(null);

  // ── Load SGO events when sport changes ─────────────────────
  useEffect(() => {
    async function load() {
      setSgoLoading(true);
      setSelectedEvent(null);
      setPlayers([]);
      setProps([]);
      const [eventsData, bkData] = await Promise.all([
        sgoGet<{ events: SgoEvent[] }>(`/events?league=${sport}`),
        sgoGet<{ bookmakers: string[] }>(`/bookmakers?league=${sport}`),
      ]);
      setEvents(eventsData?.events ?? []);
      setBookmakers(bkData?.bookmakers ?? []);
      setSgoLoading(false);
    }
    load();
  }, [sport]);

  // ── Resolve DFS slate silently (contest-rules/salary layer only) ──
  useEffect(() => {
    async function load() {
      try {
        const res = await fetchDFSSlates(platform, sport);
        const pub = (res?.data ?? []).filter((s: any) => s.status === "PUBLISHED");
        setResolvedSlateId(pub.length > 0 ? pub[0].id : null);
      } catch {
        setResolvedSlateId(null);
      }
    }
    load();
  }, [sport, platform]);

  // ── Load players + props when event selected ───────────────
  useEffect(() => {
    if (!selectedEvent) return;
    async function load() {
      setPlayersLoading(true);
      const [playersData, propsData] = await Promise.all([
        sgoGet<{ players: SgoPlayer[] }>(`/players?league=${sport}`),
        sgoGet<{ players: PlayerProp[] }>(`/events/${selectedEvent!.event_id}/props`),
      ]);
      setPlayers(playersData?.players ?? []);
      const propList = propsData?.players ?? [];
      setProps(Array.isArray(propList) ? propList : []);
      setPlayersLoading(false);
    }
    load();
  }, [selectedEvent, sport]);

  // ── Optimize mutation ─────────────────────────────────────
  const optimizeMutation = useMutation({
    mutationFn: () => runOptimizer(resolvedSlateId ?? 1, {
      sport,
      platform,
      strategy,
      num_lineups: lineupCount,
      event_id: selectedEvent?.event_id ?? null,
    }),
    onSuccess: (res) => {
      if (res?.data) setLineups(Array.isArray(res.data) ? res.data : (res.data as any)?.lineups ?? []);
    },
  });

  // ── Derived ────────────────────────────────────────────────
  const liveEvents = events.filter(e => liveClass(e.status));
  const upcomingEvents = events.filter(e => !liveClass(e.status));
  const teams = [...new Set(players.map(p => p.team).filter(Boolean))].sort();
  const positions = [...new Set(players.map(p => p.position).filter(Boolean))].sort();

  const filteredPlayers = players.filter(p => {
    if (teamFilter !== "ALL" && p.team !== teamFilter) return false;
    if (posFilter !== "ALL" && p.position !== posFilter) return false;
    if (playerSearch) {
      const q = playerSearch.toLowerCase();
      if (!p.name.toLowerCase().includes(q) && !p.team.toLowerCase().includes(q)) return false;
    }
    return true;
  });

  // ── Render ────────────────────────────────────────────────
  return (
    <div style={{ background: "#060b1a", minHeight: "100vh", color: "#f0f6fc" }}>
      {/* Header */}
      <div style={{ padding: "20px 24px", borderBottom: "1px solid #1e293b" }}>
        <h1 style={{ fontSize: 22, fontWeight: 900, color: "#c9a84c", fontStyle: "italic", margin: 0 }}>Lineup Optimizer</h1>
        <p style={{ color: "#64748b", fontSize: 13, margin: "4px 0 0" }}>
          SportsGameOdds Intelligence · Native DFS · CP-SAT Engine
        </p>
      </div>

      {/* Selector Bar */}
      <div style={{ padding: "16px 24px", borderBottom: "1px solid #1e293b", display: "flex", gap: 12, flexWrap: "wrap", alignItems: "center" }}>
        <Selector label="Sport" value={sport} options={[...SPORTS]} onChange={setSport} />
        <Selector label="Platform" value={platform} options={[...PLATFORMS]} onChange={setPlatform} format={(v: string) => v === "draftkings" ? "DraftKings" : "FanDuel"} />
        <Selector label="Bookmaker" value={bookmakerSource} options={["Best Available", "Book Consensus", ...bookmakers.filter(b => b)]} onChange={setBookmakerSource} />
        <Selector label="Strategy" value={strategy} options={[...STRATEGIES]} onChange={setStrategy} />
      </div>

      <div style={{ display: "flex", flex: 1, minHeight: 0 }}>
        {/* Sidebar — Games (SGO primary) */}
        <div style={{ width: 340, flexShrink: 0, borderRight: "1px solid #1e293b", overflow: "auto", padding: 16, display: "flex", flexDirection: "column", gap: 14 }}>
          <Section title="Games">
            {sgoLoading ? (
              <div style={{ display: "flex", alignItems: "center", gap: 8, color: "#94a3b8" }}>
                <Loader2 size={16} className="animate-spin" /> Loading from SportsGameOdds...
              </div>
            ) : events.length === 0 ? (
              <Muted>No events for {sport}</Muted>
            ) : (
              <>
                {liveEvents.length > 0 && (
                  <>
                    <Label>● LIVE</Label>
                    {liveEvents.map(e => <GameChip key={e.event_id} event={e} active={selectedEvent?.event_id === e.event_id} onClick={() => setSelectedEvent(e)} />)}
                  </>
                )}
                <Label>Upcoming</Label>
                {upcomingEvents.slice(0, 16).map(e => <GameChip key={e.event_id} event={e} active={selectedEvent?.event_id === e.event_id} onClick={() => setSelectedEvent(e)} />)}
              </>
            )}
          </Section>

          <Section title="Lineups">
            <div style={{ display: "flex", alignItems: "center", gap: 8, justifyContent: "space-between" }}>
              <input type="range" min={1} max={50} value={lineupCount} onChange={e => setLineupCount(+e.target.value)}
                style={{ flex: 1, accentColor: "#c9a84c" }} />
              <span style={{ fontSize: 12, fontWeight: 700, color: "#c9a84c" }}>{lineupCount}</span>
            </div>
            <button onClick={() => optimizeMutation.mutate()} disabled={!selectedEvent || optimizeMutation.isPending}
              style={{
                width: "100%", padding: "14px", borderRadius: 14, fontWeight: 800, fontSize: 15, textTransform: "uppercase",
                background: selectedEvent ? "#c9a84c" : "#1e293b", color: selectedEvent ? "#060b1a" : "#64748b",
                border: "none", cursor: selectedEvent ? "pointer" : "not-allowed",
                display: "flex", alignItems: "center", justifyContent: "center", gap: 8,
                boxShadow: selectedEvent ? "0 4px 20px rgba(201,168,76,0.3)" : "none",
              }}>
              {optimizeMutation.isPending ? <><Loader2 size={18} className="animate-spin" /> Solving...</> : <><Play size={18} /> Generate</>}
            </button>
            {!resolvedSlateId && <Muted>No contest salary data for {platform} {sport} — projections only.</Muted>}
          </Section>
        </div>

        {/* Main */}
        <div style={{ flex: 1, overflow: "auto", padding: 24 }}>
          {/* Selected game header */}
          {selectedEvent ? (
            <div style={{ background: "#0a0f24", borderRadius: 14, border: "1px solid #1e293b", padding: "16px 20px", marginBottom: 20, display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <div>
                <div style={{ fontSize: 17, fontWeight: 800, color: "#f0f6fc" }}>
                  {selectedEvent.away_team.name} @ {selectedEvent.home_team.name}
                </div>
                <div style={{ fontSize: 12, color: "#64748b", marginTop: 4 }}>
                  {selectedEvent.away_team.abbreviation} @ {selectedEvent.home_team.abbreviation}
                  {selectedEvent.start_time && ` · ${new Date(selectedEvent.start_time).toLocaleString([], { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" })}`}
                </div>
              </div>
              {liveClass(selectedEvent.status) && (
                <span style={{ padding: "4px 12px", borderRadius: 8, background: "rgba(239,68,68,0.15)", color: "#ef4444", fontWeight: 800, fontSize: 12 }}>
                  ● LIVE {selectedEvent.home_score}–{selectedEvent.away_score}
                </span>
              )}
            </div>
          ) : (
            <div style={{ background: "#0a0f24", borderRadius: 14, border: "1px solid #1e293b", padding: "24px", marginBottom: 20, textAlign: "center", color: "#64748b" }}>
              Select a game from the left to view teams and available players.
            </div>
          )}

          {/* Player Pool (SGO) */}
          {selectedEvent && (
            <>
              <div style={{ display: "flex", gap: 10, marginBottom: 16, flexWrap: "wrap", alignItems: "center" }}>
                <div style={{ position: "relative", flex: 1, maxWidth: 300 }}>
                  <Search size={14} style={{ position: "absolute", left: 10, top: "50%", transform: "translateY(-50%)", color: "#64748b" }} />
                  <input type="text" placeholder="Search players..." value={playerSearch} onChange={e => setPlayerSearch(e.target.value)}
                    style={{ width: "100%", padding: "8px 14px 8px 32px", borderRadius: 10, fontSize: 13, background: "#0a0f24", border: "1px solid #1e293b", color: "#f0f6fc", outline: "none" }} />
                </div>
                <Filter size={14} color="#64748b" />
                <select value={teamFilter} onChange={e => setTeamFilter(e.target.value)}
                  style={{ padding: "8px 12px", borderRadius: 10, fontSize: 12, background: "#0a0f24", border: "1px solid #1e293b", color: "#f0f6fc" }}>
                  <option value="ALL">All Teams</option>
                  {teams.map(t => <option key={t} value={t}>{t}</option>)}
                </select>
                <select value={posFilter} onChange={e => setPosFilter(e.target.value)}
                  style={{ padding: "8px 12px", borderRadius: 10, fontSize: 12, background: "#0a0f24", border: "1px solid #1e293b", color: "#f0f6fc" }}>
                  <option value="ALL">All Positions</option>
                  {positions.map(p => <option key={p} value={p}>{p}</option>)}
                </select>
                <span style={{ fontSize: 12, color: "#64748b", marginLeft: "auto" }}>
                  {filteredPlayers.length} players · SportsGameOdds
                </span>
              </div>

              {playersLoading ? (
                <Center><Loader2 size={24} className="animate-spin" style={{ color: "#c9a84c" }} /></Center>
              ) : filteredPlayers.length === 0 ? (
                <div style={{ background: "#0a0f24", borderRadius: 14, border: "1px solid #1e293b", padding: 28, textAlign: "center", color: "#64748b" }}>
                  No player data available for this game.
                </div>
              ) : (
                <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                  {filteredPlayers.slice(0, 150).map(p => {
                    const playerProps = props.find(pp => pp.player_id === p.player_id || pp.player_id === p.name);
                    const bestProp = playerProps?.markets?.[0];
                    const bestLine = bestProp?.lines?.[0];
                    return (
                      <div key={p.player_id} style={{
                        display: "grid", gridTemplateColumns: "70px 1fr 90px 120px 90px", gap: 8,
                        padding: "10px 16px", background: "#0a0f24", borderRadius: 10, border: "1px solid #1e293b",
                        alignItems: "center", fontSize: 13,
                      }}>
                        <span style={{ color: "#c9a84c", fontWeight: 700, fontSize: 11, textTransform: "uppercase" }}>{p.position || "—"}</span>
                        <div>
                          <span style={{ color: "#f0f6fc", fontWeight: 600 }}>{p.name}</span>
                          <span style={{ color: "#64748b", fontSize: 11, marginLeft: 8 }}>{p.team}</span>
                        </div>
                        <span style={{ color: "#94a3b8", textAlign: "right", fontSize: 11 }}>
                          {playerProps ? `${playerProps.markets.length} markets` : "—"}
                        </span>
                        <span style={{ color: "#c9a84c", textAlign: "right", fontWeight: 600 }}>
                          {bestProp ? bestProp.market : "—"}{bestLine ? ` ${bestLine.line} (${fmtOdds(bestLine.over_price)})` : ""}
                        </span>
                        <span style={{ color: "#64748b", textAlign: "right", fontSize: 11 }}>{bestLine?.bookmaker || ""}</span>
                      </div>
                    );
                  })}
                </div>
              )}
            </>
          )}

          {/* Results */}
          {optimizeMutation.isPending ? (
            <Center>
              <Loader2 size={32} className="animate-spin" style={{ color: "#c9a84c" }} />
              <p style={{ color: "#94a3b8", marginTop: 16 }}>Running CP-SAT optimizer...</p>
            </Center>
          ) : optimizeMutation.isError ? (
            <Center>
              <p style={{ color: "#ef4444", fontWeight: 700, fontSize: 16 }}>
                {optimizeMutation.error instanceof Error ? optimizeMutation.error.message : "Optimization failed"}
              </p>
            </Center>
          ) : lineups.length > 0 ? (
            <div style={{ display: "flex", flexDirection: "column", gap: 16, marginTop: 24 }}>
              {lineups.map((l, i) => (
                <div key={i} style={{ background: "#0a0f24", borderRadius: 16, border: "1px solid #1e293b", overflow: "hidden" }}>
                  <div style={{ height: 4, background: "#c9a84c" }} />
                  <div style={{ padding: "16px 20px", display: "flex", justifyContent: "space-between", borderBottom: "1px solid #1e293b" }}>
                    <span style={{ fontWeight: 800, color: "#f0f6fc" }}>Lineup {i + 1}</span>
                    <div style={{ display: "flex", gap: 16 }}>
                      <span style={{ color: "#94a3b8", fontSize: 13 }}>Salary: <strong style={{ color: "#f0f6fc" }}>${l.total_salary?.toLocaleString()}</strong></span>
                      <span style={{ color: "#c9a84c", fontSize: 13, fontWeight: 700 }}>Proj: {l.projected_score}</span>
                    </div>
                  </div>
                  <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
                    <tbody>
                      {l.players.map((p, j) => (
                        <tr key={j} style={{ borderBottom: j < l.players.length - 1 ? "1px solid #1e293b30" : "none" }}>
                          <td style={{ padding: "10px 20px", width: 70, color: "#c9a84c", fontWeight: 700, textTransform: "uppercase", fontSize: 11 }}>{p.roster_position}</td>
                          <td style={{ padding: "10px 0", fontWeight: 600, color: "#f0f6fc" }}>{p.name || `Player #${p.id}`}</td>
                          <td style={{ padding: "10px 0", color: "#64748b", fontSize: 12 }}>{p.team || ""}</td>
                          <td style={{ padding: "10px 20px", color: "#94a3b8", textAlign: "right" }}>${(p.salary || 0).toLocaleString()}</td>
                          <td style={{ padding: "10px 20px", color: "#c9a84c", fontWeight: 700, textAlign: "right" }}>{(p.projected_fp || 0).toFixed(1)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ))}
            </div>
          ) : null}
        </div>
      </div>
    </div>
  );
}

// ── Reusable components ─────────────────────────────────────

function Selector({ label, value, options, onChange, format }: {
  label: string; value: string; options: string[]; onChange: (v: string) => void; format?: (v: string) => string;
}) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
      <span style={{ fontSize: 10, fontWeight: 700, color: "#64748b", textTransform: "uppercase" }}>{label}</span>
      <select value={value} onChange={e => onChange(e.target.value)}
        style={{ padding: "8px 12px", borderRadius: 10, fontSize: 12, fontWeight: 600, background: "#0a0f24", border: "1px solid #1e293b", color: "#c9a84c", cursor: "pointer" }}>
        {options.map(o => <option key={o} value={o}>{format ? format(o) : o}</option>)}
      </select>
    </div>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div>
      <p style={{ fontSize: 10, fontWeight: 700, color: "#64748b", textTransform: "uppercase", marginBottom: 8 }}>{title}</p>
      {children}
    </div>
  );
}

function Label({ children }: { children: React.ReactNode }) {
  return <p style={{ fontSize: 10, fontWeight: 600, color: "#64748b", margin: "6px 0" }}>{children}</p>;
}

function Muted({ children }: { children: React.ReactNode }) {
  return <p style={{ color: "#64748b", fontSize: 13 }}>{children}</p>;
}

function GameChip({ event, active, onClick }: { event: SgoEvent; active: boolean; onClick: () => void }) {
  const isLive = liveClass(event.status);
  return (
    <button onClick={onClick} style={{
      width: "100%", padding: "8px 12px", borderRadius: 10, textAlign: "left", fontSize: 12, fontWeight: 600,
      background: active ? "rgba(201,168,76,0.1)" : isLive ? "rgba(239,68,68,0.06)" : "#0a0f24",
      border: active ? "1px solid rgba(201,168,76,0.3)" : isLive ? "1px solid rgba(239,68,68,0.2)" : "1px solid #1e293b",
      color: active ? "#c9a84c" : "#94a3b8", cursor: "pointer", marginBottom: 4,
    }}>
      {isLive && <span style={{ color: "#ef4444", fontSize: 10, fontWeight: 800, marginRight: 6 }}>●</span>}
      {event.away_team.abbreviation || event.away_team.name} @ {event.home_team.abbreviation || event.home_team.name}
    </button>
  );
}

function Center({ children }: { children: React.ReactNode }) {
  return (
    <div style={{ display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", height: 200, textAlign: "center" }}>
      {children}
    </div>
  );
}