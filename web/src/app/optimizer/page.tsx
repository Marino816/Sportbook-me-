"use client";

import { useState, useEffect, useMemo } from "react";
import { useMutation } from "@tanstack/react-query";
import { fetchDFSSlates, runOptimizer, type LineupResponse } from "@/lib/api";
import { Play, Loader2, Search, Filter } from "lucide-react";
import { useEvents } from "@/lib/use-events";
import type { SBEvent, SBPlayer, SBMarket } from "@/lib/sbevent";

const SPORTS = ["MLB", "NFL", "NBA", "NHL", "NCAAF", "NCAAB"] as const;
const PLATFORMS = ["draftkings", "fanduel"] as const;
const STRATEGIES = ["balanced", "cash", "gpp", "aggressive"] as const;

function liveClass(status: string): boolean {
  const s = (status || "").toUpperCase();
  return s === "LIVE" || s === "IN_PLAY" || s === "INPLAY";
}

/** Resolve team_id to display name from event's home/away teams */
function resolveTeamName(teamId: string, event: SBEvent): string {
  if (event.home_team?.team_id === teamId) return event.home_team.abbreviation || event.home_team.name;
  if (event.away_team?.team_id === teamId) return event.away_team.abbreviation || event.away_team.name;
  return teamId;
}

/** Count markets for a player in an event */
function countPlayerMarkets(playerId: string, markets: SBMarket[]): number {
  return (markets || []).filter((m) => m.player_id === playerId).length;
}

export default function OptimizerPage() {
  // ── State ──────────────────────────────────────────────────
  const [sport, setSport] = useState<string>("MLB");
  const [platform, setPlatform] = useState<string>("draftkings");
  const [bookmakerSource, setBookmakerSource] = useState<string>("Best Available");
  const [strategy, setStrategy] = useState<string>("balanced");
  const [lineupCount, setLineupCount] = useState(1);

  // SGO via shared hook
  const { events, loading: sgoLoading } = useEvents(sport);
  const [selectedEventId, setSelectedEventId] = useState<string | null>(null);
  const selectedEvent = useMemo(
    () => events.find((e) => e.id === selectedEventId) ?? null,
    [events, selectedEventId],
  );

  // Filters
  const [playerSearch, setPlayerSearch] = useState("");
  const [posFilter, setPosFilter] = useState("ALL");
  const [teamFilter, setTeamFilter] = useState<string>("ALL");

  // Results
  const [lineups, setLineups] = useState<LineupResponse[]>([]);
  const [resolvedSlateId, setResolvedSlateId] = useState<number | null>(null);
  const [slatesLoading, setSlatesLoading] = useState(true);

  // ── Resolve DFS slate ──────────────────────────────────────
  useEffect(() => {
    let cancelled = false;
    async function load() {
      setSlatesLoading(true);
      try {
        const res = await fetchDFSSlates(platform, sport);
        const pub = (res?.data ?? []).filter((s: any) => s.status === "PUBLISHED");
        if (!cancelled) setResolvedSlateId(pub.length > 0 ? pub[0].id : null);
      } catch {
        if (!cancelled) setResolvedSlateId(null);
      } finally {
        if (!cancelled) setSlatesLoading(false);
      }
    }
    load();
    return () => { cancelled = true; };
  }, [sport, platform]);

  // ── Optimize mutation (defensive onSuccess) ──────────────
  const optimizeMutation = useMutation({
    mutationFn: () => {
      if (resolvedSlateId == null) {
        throw new Error(
          `No ${platform === "draftkings" ? "DraftKings" : "FanDuel"} contest salary data for ${sport}.`,
        );
      }
      return runOptimizer(resolvedSlateId, {
        sport,
        platform,
        strategy,
        num_lineups: lineupCount,
        event_id: selectedEvent?.id ?? null,
      });
    },
    onSuccess: (res: unknown) => {
      try {
        if (!res || typeof res !== "object") { setLineups([]); return; }
        const r = res as Record<string, unknown>;
        const data = r?.data;
        if (!data) { setLineups([]); return; }
        if (Array.isArray(data)) {
          setLineups(data as LineupResponse[]);
        } else if (typeof data === "object" && data !== null) {
          const inner = (data as Record<string, unknown>)?.lineups;
          setLineups(Array.isArray(inner) ? (inner as LineupResponse[]) : []);
        } else {
          setLineups([]);
        }
      } catch { setLineups([]); }
    },
    onError: () => setLineups([]),
  });

  // ── Derived data from SBEvent ──────────────────────────────
  const players: SBPlayer[] = selectedEvent?.players ?? [];
  const markets: SBMarket[] = selectedEvent?.markets ?? [];
  const bookmakers: string[] = selectedEvent?.bookmakers ?? [];

  useEffect(() => {
    setPlayerSearch("");
    setPosFilter("ALL");
    setTeamFilter("ALL");
    setLineups([]);
  }, [selectedEventId]);

  const teams = useMemo(() => {
    if (!selectedEvent) return [];
    return [...new Set(players.map((p) => resolveTeamName(p.team_id, selectedEvent)).filter(Boolean))].sort();
  }, [players, selectedEvent]);

  const positions = useMemo(
    () => [...new Set(players.map((p) => p.position).filter(Boolean))].sort(),
    [players],
  );

  const filteredPlayers = useMemo(() => {
    if (!selectedEvent) return [];
    return players.filter((p) => {
      const teamName = resolveTeamName(p.team_id, selectedEvent);
      if (teamFilter !== "ALL" && teamName !== teamFilter) return false;
      if (posFilter !== "ALL" && p.position !== posFilter) return false;
      if (playerSearch) {
        const q = playerSearch.toLowerCase();
        if (!p.name.toLowerCase().includes(q) && !teamName.toLowerCase().includes(q)) return false;
      }
      return true;
    });
  }, [players, selectedEvent, teamFilter, posFilter, playerSearch]);

  const liveEvents = events.filter((e) => liveClass(e.status));
  const upcomingEvents = events.filter((e) => !liveClass(e.status));

  const canGenerate = !!selectedEvent && !slatesLoading && resolvedSlateId != null;

  // ── Render ────────────────────────────────────────────────
  return (
    <div style={{ background: "#060b1a", minHeight: "100vh", color: "#f0f6fc" }}>
      <div style={{ padding: "20px 24px", borderBottom: "1px solid #1e293b" }}>
        <h1 style={{ fontSize: 22, fontWeight: 900, color: "#c9a84c", fontStyle: "italic", margin: 0 }}>Lineup Optimizer</h1>
        <p style={{ color: "#64748b", fontSize: 13, margin: "4px 0 0" }}>SportsGameOdds Intelligence · Native DFS · CP-SAT Engine</p>
      </div>
      <div style={{ padding: "16px 24px", borderBottom: "1px solid #1e293b", display: "flex", gap: 12, flexWrap: "wrap", alignItems: "center" }}>
        <Selector label="Sport" value={sport} options={[...SPORTS]} onChange={setSport} />
        <Selector label="Platform" value={platform} options={[...PLATFORMS]} onChange={setPlatform} format={(v) => v === "draftkings" ? "DraftKings" : "FanDuel"} />
        <Selector label="Bookmaker" value={bookmakerSource} options={["Best Available", "Book Consensus", ...bookmakers.filter((b) => b)]} onChange={setBookmakerSource} />
        <Selector label="Strategy" value={strategy} options={[...STRATEGIES]} onChange={setStrategy} />
      </div>
      <div style={{ display: "flex", flex: 1, minHeight: 0 }}>
        <div style={{ width: 340, flexShrink: 0, borderRight: "1px solid #1e293b", overflow: "auto", padding: 16, display: "flex", flexDirection: "column", gap: 14 }}>
          <Section title="Games">
            {sgoLoading ? <div style={{ display: "flex", alignItems: "center", gap: 8, color: "#94a3b8" }}><Loader2 size={16} className="animate-spin" /> Loading from SportsGameOdds...</div>
            : events.length === 0 ? <Muted>No events for {sport}</Muted>
            : <>{liveEvents.length > 0 && <><Label>● LIVE</Label>{liveEvents.map((e) => <GameChip key={e.id} event={e} active={selectedEventId === e.id} onClick={() => setSelectedEventId(e.id)} />)}</>}<Label>Upcoming</Label>{upcomingEvents.slice(0, 16).map((e) => <GameChip key={e.id} event={e} active={selectedEventId === e.id} onClick={() => setSelectedEventId(e.id)} />)}</>}
          </Section>
          <Section title="Lineups">
            <div style={{ display: "flex", alignItems: "center", gap: 8, justifyContent: "space-between" }}>
              <input type="range" min={1} max={50} value={lineupCount} onChange={(e) => setLineupCount(+e.target.value)} style={{ flex: 1, accentColor: "#c9a84c" }} />
              <span style={{ fontSize: 12, fontWeight: 700, color: "#c9a84c" }}>{lineupCount}</span>
            </div>
            <button onClick={() => optimizeMutation.mutate()} disabled={!canGenerate || optimizeMutation.isPending} style={{ width: "100%", padding: "14px", borderRadius: 14, fontWeight: 800, fontSize: 15, textTransform: "uppercase", background: canGenerate ? "#c9a84c" : "#1e293b", color: canGenerate ? "#060b1a" : "#64748b", border: "none", cursor: canGenerate ? "pointer" : "not-allowed", display: "flex", alignItems: "center", justifyContent: "center", gap: 8, boxShadow: canGenerate ? "0 4px 20px rgba(201,168,76,0.3)" : "none" }}>
              {optimizeMutation.isPending ? <><Loader2 size={18} className="animate-spin" /> Solving...</> : <><Play size={18} /> Generate</>}
            </button>
            {!slatesLoading && resolvedSlateId == null && <Muted>No {platform === "draftkings" ? "DraftKings" : "FanDuel"} contest salary data for {sport} — Generate is unavailable until a {platform} slate is published.</Muted>}
          </Section>
        </div>
        <div style={{ flex: 1, overflow: "auto", padding: 24 }}>
          {selectedEvent ? <div style={{ background: "#0a0f24", borderRadius: 14, border: "1px solid #1e293b", padding: "16px 20px", marginBottom: 20, display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <div><div style={{ fontSize: 17, fontWeight: 800, color: "#f0f6fc" }}>{selectedEvent.away_team.name} @ {selectedEvent.home_team.name}</div><div style={{ fontSize: 12, color: "#64748b", marginTop: 4 }}>{selectedEvent.away_team.abbreviation} @ {selectedEvent.home_team.abbreviation}{selectedEvent.start_time && ` · ${new Date(selectedEvent.start_time).toLocaleString([], { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" })}`}</div></div>
            {liveClass(selectedEvent.status) && <span style={{ padding: "4px 12px", borderRadius: 8, background: "rgba(239,68,68,0.15)", color: "#ef4444", fontWeight: 800, fontSize: 12 }}>● LIVE {selectedEvent.home_score}–{selectedEvent.away_score}</span>}
          </div> : <div style={{ background: "#0a0f24", borderRadius: 14, border: "1px solid #1e293b", padding: "24px", marginBottom: 20, textAlign: "center", color: "#64748b" }}>Select a game from the left to view teams and available players.</div>}
          {selectedEvent && <><div style={{ display: "flex", gap: 10, marginBottom: 16, flexWrap: "wrap", alignItems: "center" }}>
            <div style={{ position: "relative", flex: 1, maxWidth: 300 }}><Search size={14} style={{ position: "absolute", left: 10, top: "50%", transform: "translateY(-50%)", color: "#64748b" }} /><input type="text" placeholder="Search players..." value={playerSearch} onChange={(e) => setPlayerSearch(e.target.value)} style={{ width: "100%", padding: "8px 14px 8px 32px", borderRadius: 10, fontSize: 13, background: "#0a0f24", border: "1px solid #1e293b", color: "#f0f6fc", outline: "none" }} /></div>
            <Filter size={14} color="#64748b" />
            <select value={teamFilter} onChange={(e) => setTeamFilter(e.target.value)} style={{ padding: "8px 12px", borderRadius: 10, fontSize: 12, background: "#0a0f24", border: "1px solid #1e293b", color: "#f0f6fc" }}><option value="ALL">All Teams</option>{teams.map((t) => <option key={t} value={t}>{t}</option>)}</select>
            <select value={posFilter} onChange={(e) => setPosFilter(e.target.value)} style={{ padding: "8px 12px", borderRadius: 10, fontSize: 12, background: "#0a0f24", border: "1px solid #1e293b", color: "#f0f6fc" }}><option value="ALL">All Positions</option>{positions.map((p) => <option key={p} value={p}>{p}</option>)}</select>
            <span style={{ fontSize: 12, color: "#64748b", marginLeft: "auto" }}>{filteredPlayers.length} players · SportsGameOdds</span>
          </div>
          {filteredPlayers.length === 0 ? <div style={{ background: "#0a0f24", borderRadius: 14, border: "1px solid #1e293b", padding: 28, textAlign: "center", color: "#64748b" }}>No player data available for this game.</div>
          : <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>{filteredPlayers.slice(0, 150).map((p) => { const teamName = resolveTeamName(p.team_id, selectedEvent); const mCount = countPlayerMarkets(p.player_id, markets); return <div key={p.player_id} style={{ display: "grid", gridTemplateColumns: "70px 1fr 90px 120px 90px", gap: 8, padding: "10px 16px", background: "#0a0f24", borderRadius: 10, border: "1px solid #1e293b", alignItems: "center", fontSize: 13 }}><span style={{ color: "#c9a84c", fontWeight: 700, fontSize: 11, textTransform: "uppercase" }}>{p.position || "—"}</span><div><span style={{ color: "#f0f6fc", fontWeight: 600 }}>{p.name}</span><span style={{ color: "#64748b", fontSize: 11, marginLeft: 8 }}>{teamName}</span></div><span style={{ color: "#94a3b8", textAlign: "right", fontSize: 11 }}>{mCount > 0 ? `${mCount} SGO markets` : "—"}</span><span style={{ color: "#c9a84c", textAlign: "right", fontWeight: 600 }}>{mCount > 0 ? `${mCount} props` : "—"}</span><span style={{ color: "#64748b", textAlign: "right", fontSize: 11 }}>{teamName}</span></div>; })}</div>}</>}
          {optimizeMutation.isPending ? <Center><Loader2 size={32} className="animate-spin" style={{ color: "#c9a84c" }} /><p style={{ color: "#94a3b8", marginTop: 16 }}>Running CP-SAT optimizer...</p></Center>
          : optimizeMutation.isError ? <Center><p style={{ color: "#ef4444", fontWeight: 700, fontSize: 16 }}>{optimizeMutation.error instanceof Error ? optimizeMutation.error.message : "Optimization failed"}</p></Center>
          : lineups.length > 0 ? <div style={{ display: "flex", flexDirection: "column", gap: 16, marginTop: 24 }}>{lineups.map((l, i) => <LineupCard key={i} index={i} lineup={l} />)}</div> : null}
        </div>
      </div>
    </div>
  );
}

// ── Reusable sub-components ─────────────────────────────────

function Selector({ label, value, options, onChange, format }: { label: string; value: string; options: string[]; onChange: (v: string) => void; format?: (v: string) => string }) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
      <span style={{ fontSize: 10, fontWeight: 700, color: "#64748b", textTransform: "uppercase" }}>{label}</span>
      <select value={value} onChange={(e) => onChange(e.target.value)} style={{ padding: "8px 12px", borderRadius: 10, fontSize: 12, fontWeight: 600, background: "#0a0f24", border: "1px solid #1e293b", color: "#c9a84c", cursor: "pointer" }}>
        {options.map((o) => <option key={o} value={o}>{format ? format(o) : o}</option>)}
      </select>
    </div>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return <div><p style={{ fontSize: 10, fontWeight: 700, color: "#64748b", textTransform: "uppercase", marginBottom: 8 }}>{title}</p>{children}</div>;
}

function Label({ children }: { children: React.ReactNode }) {
  return <p style={{ fontSize: 10, fontWeight: 600, color: "#64748b", margin: "6px 0" }}>{children}</p>;
}

function Muted({ children }: { children: React.ReactNode }) {
  return <p style={{ color: "#64748b", fontSize: 13 }}>{children}</p>;
}

function GameChip({ event, active, onClick }: { event: SBEvent; active: boolean; onClick: () => void }) {
  const isLive = liveClass(event.status);
  return (
    <button onClick={onClick} style={{ width: "100%", padding: "8px 12px", borderRadius: 10, textAlign: "left", fontSize: 12, fontWeight: 600, background: active ? "rgba(201,168,76,0.1)" : isLive ? "rgba(239,68,68,0.06)" : "#0a0f24", border: active ? "1px solid rgba(201,168,76,0.3)" : isLive ? "1px solid rgba(239,68,68,0.2)" : "1px solid #1e293b", color: active ? "#c9a84c" : "#94a3b8", cursor: "pointer", marginBottom: 4 }}>
      {isLive && <span style={{ color: "#ef4444", fontSize: 10, fontWeight: 800, marginRight: 6 }}>●</span>}
      {event.away_team.abbreviation || event.away_team.name} @ {event.home_team.abbreviation || event.home_team.name}
    </button>
  );
}

function Center({ children }: { children: React.ReactNode }) {
  return <div style={{ display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", height: 200, textAlign: "center" }}>{children}</div>;
}

function LineupCard({ index, lineup }: { index: number; lineup: LineupResponse }) {
  return (
    <div style={{ background: "#0a0f24", borderRadius: 16, border: "1px solid #1e293b", overflow: "hidden" }}>
      <div style={{ height: 4, background: "#c9a84c" }} />
      <div style={{ padding: "16px 20px", display: "flex", justifyContent: "space-between", borderBottom: "1px solid #1e293b" }}>
        <span style={{ fontWeight: 800, color: "#f0f6fc" }}>Lineup {index + 1}</span>
        <div style={{ display: "flex", gap: 16 }}>
          <span style={{ color: "#94a3b8", fontSize: 13 }}>Salary: <strong style={{ color: "#f0f6fc" }}>${lineup.total_salary?.toLocaleString()}</strong></span>
          <span style={{ color: "#c9a84c", fontSize: 13, fontWeight: 700 }}>Proj: {lineup.projected_score}</span>
        </div>
      </div>
      <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
        <tbody>
          {(lineup.players || []).map((p, j) => (
            <tr key={j} style={{ borderBottom: j < (lineup.players || []).length - 1 ? "1px solid #1e293b30" : "none" }}>
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
  );
}