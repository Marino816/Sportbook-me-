"use client";

import { useState, useEffect, useMemo, useCallback } from "react";
import { useRouter } from "next/navigation";
import { useMutation } from "@tanstack/react-query";
import { fetchDFSSlates, fetchDFSSlate, runOptimizer, type LineupResponse, type DFSSlatePlayer } from "@/lib/api";
import { Play, Loader2, Search, Save, RefreshCw, Trash2, List, Lock, Ban, Heart, X, ChevronDown, ChevronUp } from "lucide-react";
import { useEvents } from "@/lib/use-events";
import type { SBEvent, SBPlayer, SBMarket } from "@/lib/sbevent";

const SPORTS = ["MLB", "NFL", "NBA", "NHL", "NCAAF", "NCAAB"] as const;
const PLATFORMS = ["draftkings", "fanduel"] as const;
const STRATEGIES = ["balanced", "cash", "gpp", "aggressive"] as const;
const DK_SLOTS = ["P", "P", "C", "1B", "2B", "3B", "SS", "OF", "OF", "OF"] as const;
const FD_SLOTS = ["P", "C1B", "2B", "3B", "SS", "OF", "OF", "OF", "UTIL"] as const;
const MLB_POSITIONS = ["ALL", "P", "C", "1B", "2B", "3B", "SS", "OF"] as const;

type MainTab = "pool" | "saved" | "built";
type SubTab = "all" | "excluded" | "liked";

function liveClass(status: string): boolean {
  const s = (status || "").toUpperCase();
  return s === "LIVE" || s === "IN_PLAY" || s === "INPLAY";
}

function resolveTeamName(teamId: string, event: SBEvent): string {
  if (event.home_team?.team_id === teamId) return event.home_team.abbreviation || event.home_team.name;
  if (event.away_team?.team_id === teamId) return event.away_team.abbreviation || event.away_team.name;
  return teamId;
}

function opponentFor(player: SBPlayer, event: SBEvent): string {
  if (!event) return "";
  if (event.home_team?.team_id === player.team_id) return event.away_team?.abbreviation || event.away_team?.name || "";
  if (event.away_team?.team_id === player.team_id) return event.home_team?.abbreviation || event.home_team?.name || "";
  return "";
}

function countPlayerMarkets(playerId: string, markets: SBMarket[]): number {
  return (markets || []).filter((m) => m.player_id === playerId).length;
}

function normName(n: string): string {
  return (n || "").toLowerCase().replace(/[^a-z0-9]/g, "").trim();
}

function matchDFS(
  sgo: { name: string; team?: string; team_id?: string; position?: string },
  dfsPool: DFSSlatePlayer[],
): DFSSlatePlayer | null {
  const n = normName(sgo.name);
  if (!n) return null;
  const pos = (sgo.position || "").toUpperCase();
  for (const d of dfsPool) {
    if (normName(d.name) === n && d.position.toUpperCase() === pos) return d;
  }
  for (const d of dfsPool) {
    if (normName(d.name) === n) return d;
  }
  return null;
}

const SLOT_LABELS: Record<string, string> = { C1B: "C/1B", UTIL: "UTIL" };
function slotLabel(s: string): string { return SLOT_LABELS[s] || s; }

export default function OptimizerPage() {
  const router = useRouter();

  // ── State ──
  const [sport, setSport] = useState<string>("MLB");
  const [platform, setPlatform] = useState<string>("draftkings");
  const [bookmakerSource, setBookmakerSource] = useState<string>("Best Available");
  const [strategy, setStrategy] = useState<string>("balanced");
  const [lineupCount, setLineupCount] = useState(4);
  const { events, loading: sgoLoading } = useEvents(sport);

  const [excludedGameIds, setExcludedGameIds] = useState<Set<string>>(new Set());
  const [likedIds, setLikedIds] = useState<Set<string>>(new Set());
  const [excludedPlayerIds, setExcludedPlayerIds] = useState<Set<string>>(new Set());
  const [lockedPlayerIds, setLockedPlayerIds] = useState<Set<string>>(new Set());

  const [playerSearch, setPlayerSearch] = useState("");
  const [posFilter, setPosFilter] = useState("ALL");
  const [mainTab, setMainTab] = useState<MainTab>("pool");
  const [subTab, setSubTab] = useState<SubTab>("all");

  const [lineups, setLineups] = useState<LineupResponse[]>([]);
  const [resolvedSlateId, setResolvedSlateId] = useState<number | null>(null);
  const [slatesLoading, setSlatesLoading] = useState(true);
  const [showStackingRules, setShowStackingRules] = useState(false);
  const [maxHittersPerTeam, setMaxHittersPerTeam] = useState<number | undefined>();
  const [stackSize, setStackSize] = useState<number | undefined>();
  const [pitcherConflict, setPitcherConflict] = useState<boolean>(true);
  const [minSalaryOverride, setMinSalaryOverride] = useState<number | undefined>();
  const [maxSalaryOverride, setMaxSalaryOverride] = useState<number | undefined>();
  const [globalMaxExposure, setGlobalMaxExposure] = useState<number | undefined>();
  const [savedNote, setSavedNote] = useState(false);
  const [lastGenMeta, setLastGenMeta] = useState<{ sport: string; platform: string; strategy: string; gameCount: number } | null>(null);

  // ── DFS slate ──
  useEffect(() => {
    let cancelled = false;
    async function load() {
      setSlatesLoading(true);
      try {
        const res = await fetchDFSSlates(platform, sport);
        const pub = (res?.data ?? []).filter((s: any) => s.status === "PUBLISHED");
        if (!cancelled) setResolvedSlateId(pub.length > 0 ? pub[0].id : null);
      } catch { if (!cancelled) setResolvedSlateId(null); }
      finally { if (!cancelled) setSlatesLoading(false); }
    }
    load();
    return () => { cancelled = true; };
  }, [sport, platform]);

  const [dfsPlayers, setDfsPlayers] = useState<DFSSlatePlayer[]>([]);
  useEffect(() => {
    if (!resolvedSlateId) { setDfsPlayers([]); return; }
    let cancelled = false;
    (async () => {
      try { const res = await fetchDFSSlate(resolvedSlateId); if (!cancelled) setDfsPlayers(res?.data?.players ?? []); }
      catch { if (!cancelled) setDfsPlayers([]); }
    })();
    return () => { cancelled = true; };
  }, [resolvedSlateId]);

  useEffect(() => { setPlayerSearch(""); setPosFilter("ALL"); setLineups([]); setLastGenMeta(null); }, [sport, platform]);

  // ── Derived ──
  const filteredEvents = useMemo(() => {
    if (excludedGameIds.size === 0) return events;
    return events.filter((e) => !excludedGameIds.has(e.id));
  }, [events, excludedGameIds]);

  const players = useMemo(() => {
    const seen = new Map<string, SBPlayer>();
    for (const evt of filteredEvents) {
      for (const p of evt.players ?? []) {
        if (!p.player_id || seen.has(p.player_id)) continue;
        seen.set(p.player_id, p);
      }
    }
    return Array.from(seen.values());
  }, [filteredEvents]);

  const markets = useMemo(() => {
    const out: SBMarket[] = [];
    for (const evt of filteredEvents) out.push(...(evt.markets ?? []));
    return out;
  }, [filteredEvents]);

  const bookmakers = useMemo(() => {
    const seen = new Set<string>();
    for (const evt of filteredEvents) { for (const b of evt.bookmakers ?? []) seen.add(b); }
    return Array.from(seen).sort();
  }, [filteredEvents]);

  const filteredPlayers = useMemo(() => {
    let pool = players;
    if (subTab === "excluded") pool = players.filter((p) => excludedPlayerIds.has(p.player_id));
    else if (subTab === "liked") pool = players.filter((p) => likedIds.has(p.player_id));
    else pool = players.filter((p) => !excludedPlayerIds.has(p.player_id));
    return pool.filter((p) => {
      if (posFilter !== "ALL" && p.position !== posFilter) return false;
      if (!playerSearch) return true;
      const q = playerSearch.toLowerCase();
      if (p.name.toLowerCase().includes(q)) return true;
      const evt = filteredEvents.find((e) => (e.players ?? []).some((ep) => ep.player_id === p.player_id));
      return evt ? resolveTeamName(p.team_id, evt).toLowerCase().includes(q) : false;
    });
  }, [players, subTab, excludedPlayerIds, likedIds, posFilter, playerSearch, filteredEvents]);

  const upcomingEvents = events.filter((e) => !liveClass(e.status));
  const canGenerate = !slatesLoading && resolvedSlateId != null && filteredEvents.length > 0;

  // ── Game toggles ──
  const selectAllGames = useCallback(() => setExcludedGameIds(new Set()), []);
  const removeAllGames = useCallback(() => setExcludedGameIds(new Set(events.map((e) => e.id))), [events]);
  const toggleGame = useCallback((id: string) => {
    setExcludedGameIds((prev) => { const n = new Set(prev); if (n.has(id)) n.delete(id); else n.add(id); return n; });
  }, []);

  // ── Player actions ──
  const toggleLike = useCallback((id: string) => {
    setLikedIds((prev) => { const n = new Set(prev); if (n.has(id)) n.delete(id); else n.add(id); return n; });
  }, []);
  const toggleExclude = useCallback((id: string) => {
    setExcludedPlayerIds((prev) => { const n = new Set(prev); if (n.has(id)) n.delete(id); else n.add(id); return n; });
    setLockedPlayerIds((prev) => { const n = new Set(prev); n.delete(id); return n; });
  }, []);
  const toggleLock = useCallback((id: string) => {
    setLockedPlayerIds((prev) => { const n = new Set(prev); if (n.has(id)) n.delete(id); else n.add(id); return n; });
    setExcludedPlayerIds((prev) => { const n = new Set(prev); n.delete(id); return n; });
  }, []);
  const excludeAll = useCallback(() => {
    setExcludedPlayerIds(new Set(players.map((p) => p.player_id)));
    setLockedPlayerIds(new Set());
  }, [players]);

  // ── Optimize ──
  const optimizeMutation = useMutation({
    mutationFn: () => {
      if (resolvedSlateId == null) throw new Error(`No ${platform === "draftkings" ? "DraftKings" : "FanDuel"} contest salary data.`);
      const setting: any = {
        sport, platform, strategy, num_lineups: lineupCount,
        locked_player_ids: Array.from(lockedPlayerIds),
        excluded_player_ids: Array.from(excludedPlayerIds),
      };
      if (maxHittersPerTeam != null) setting.max_hitters_per_team = maxHittersPerTeam;
      if (stackSize != null) setting.stack_size = stackSize;
      if (!pitcherConflict) setting.pitcher_conflict = false;
      if (minSalaryOverride != null) setting.min_salary = minSalaryOverride;
      if (maxSalaryOverride != null) setting.max_salary = maxSalaryOverride;
      if (globalMaxExposure != null) setting.max_exposure_pct = globalMaxExposure;
      return runOptimizer(resolvedSlateId, setting);
    },
    onSuccess: (res: unknown) => {
      try {
        if (!res || typeof res !== "object") { setLineups([]); return; }
        const r = res as Record<string, unknown>;
        const data = r?.data;
        if (!data) { setLineups([]); return; }
        if (Array.isArray(data)) setLineups(data as LineupResponse[]);
        else if (typeof data === "object" && data !== null) {
          const inner = (data as Record<string, unknown>)?.lineups;
          setLineups(Array.isArray(inner) ? (inner as LineupResponse[]) : []);
        } else setLineups([]);
      } catch { setLineups([]); }
      setLastGenMeta({ sport, platform, strategy, gameCount: filteredEvents.length });
      setMainTab("built");
    },
    onError: () => { setLineups([]); setLastGenMeta(null); },
  });

  const clearLineups = useCallback(() => { setLineups([]); setLastGenMeta(null); setSavedNote(false); }, []);
  const regenerate = useCallback(() => optimizeMutation.mutate(), [optimizeMutation]);
  const markSaved = useCallback(() => setSavedNote(true), []);

  const slots = platform === "fanduel" ? FD_SLOTS : DK_SLOTS;
  const lockedPlayers = players.filter((p) => lockedPlayerIds.has(p.player_id));

  return (
    <div style={{ background: "#060b1a", minHeight: "100vh", color: "#f0f6fc" }}>
      {/* HEADER */}
      <div style={{ padding: "20px 24px", borderBottom: "1px solid #1e293b", display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: 8 }}>
        <div>
          <h1 style={{ fontSize: 24, fontWeight: 900, color: "#c9a84c", fontStyle: "italic", margin: 0 }}>{sport} LINEUP OPTIMIZER</h1>
          <p style={{ color: "#64748b", fontSize: 12, margin: "4px 0 0" }}>
            SportsGameOdds Intelligence · CP-SAT Engine · {sgoLoading ? "Loading..." : `${events.length} events`} · Updated {new Date().toLocaleTimeString()}
          </p>
        </div>
        <div style={{ display: "flex", gap: 6 }}>
          {PLATFORMS.map((p) => (
            <button key={p} onClick={() => { setPlatform(p); setLineups([]); setLastGenMeta(null); }}
              style={{ padding: "10px 18px", borderRadius: 10, fontWeight: 700, fontSize: 13, background: platform === p ? "rgba(201,168,76,0.15)" : "#0a0f24", border: platform === p ? "1px solid #c9a84c" : "1px solid #1e293b", color: platform === p ? "#c9a84c" : "#94a3b8", cursor: "pointer", textTransform: "uppercase" }}>
              {p === "draftkings" ? "DraftKings" : "FanDuel"}
            </button>
          ))}
        </div>
      </div>

      {/* SLATE + CONTROLS */}
      <div style={{ padding: "12px 24px", borderBottom: "1px solid #1e293b", display: "flex", gap: 12, flexWrap: "wrap", alignItems: "center", justifyContent: "space-between" }}>
        <div style={{ display: "flex", gap: 12, flexWrap: "wrap", alignItems: "center" }}>
          <Selector label="Sport" value={sport} options={[...SPORTS]} onChange={setSport} />
          <Selector label="Bookmaker" value={bookmakerSource} options={["Best Available", "Book Consensus", ...bookmakers]} onChange={setBookmakerSource} />
          <Selector label="Strategy" value={strategy} options={[...STRATEGIES]} onChange={setStrategy} />
          <span style={{ fontSize: 11, color: "#64748b" }}>
            Slate: {slatesLoading ? "Loading..." : resolvedSlateId ? `${filteredEvents.length} Games · ${players.length} Players` : "No slate"}
          </span>
        </div>
        <button onClick={() => setShowStackingRules(!showStackingRules)} style={{ padding: "6px 12px", borderRadius: 8, fontSize: 11, fontWeight: 600, background: showStackingRules ? "rgba(201,168,76,0.15)" : "#0a0f24", border: showStackingRules ? "1px solid #c9a84c" : "1px solid #1e293b", color: showStackingRules ? "#c9a84c" : "#94a3b8", cursor: "pointer", display: "flex", alignItems: "center", gap: 6 }}>
          {showStackingRules ? <ChevronUp size={14} /> : <ChevronDown size={14} />} BUILD & STACKING RULES
        </button>
      </div>

      {/* STACKING RULES */}
      {showStackingRules && (
        <div style={{ padding: "14px 24px", borderBottom: "1px solid #1e293b", background: "#0a0f24", display: "flex", gap: 16, flexWrap: "wrap", alignItems: "center" }}>
          <RuleField label="Max Hitters/Team" value={maxHittersPerTeam} onChange={setMaxHittersPerTeam} placeholder="Any" />
          <RuleField label="Team Stack Size" value={stackSize} onChange={setStackSize} placeholder="Off" />
          <label style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 12, color: "#94a3b8", cursor: "pointer" }}>
            <input type="checkbox" checked={pitcherConflict} onChange={(e) => setPitcherConflict(e.target.checked)} style={{ accentColor: "#c9a84c" }} /> Pitcher/Opposing-Hitter conflict
          </label>
          <RuleField label="Min Salary" value={minSalaryOverride} onChange={setMinSalaryOverride} placeholder="Default" />
          <RuleField label="Max Salary" value={maxSalaryOverride} onChange={setMaxSalaryOverride} placeholder="Default" />
          <RuleField label="Max Exposure %" value={globalMaxExposure} onChange={setGlobalMaxExposure} placeholder="None" step={5} />
        </div>
      )}

      {/* GAME CARDS */}
      <div style={{ padding: "12px 24px", borderBottom: "1px solid #1e293b", display: "flex", gap: 6, alignItems: "center", flexWrap: "wrap" }}>
        <button onClick={selectAllGames} style={{ padding: "4px 10px", borderRadius: 6, fontSize: 10, fontWeight: 700, background: "#1a1f33", border: "1px solid #1e293b", color: "#94a3b8", cursor: "pointer" }}>SELECT ALL</button>
        <button onClick={removeAllGames} style={{ padding: "4px 10px", borderRadius: 6, fontSize: 10, fontWeight: 700, background: "#1a1f33", border: "1px solid #1e293b", color: "#ef4444", cursor: "pointer" }}>REMOVE ALL</button>
        <div style={{ display: "flex", gap: 6, overflowX: "auto", flex: 1, paddingBottom: 4 }}>
          {upcomingEvents.slice(0, 20).map((e) => {
            const excluded = excludedGameIds.has(e.id);
            return (
              <button key={e.id} onClick={() => toggleGame(e.id)}
                style={{ padding: "8px 14px", borderRadius: 10, fontSize: 11, fontWeight: 600, whiteSpace: "nowrap", background: excluded ? "rgba(239,68,68,0.06)" : "rgba(201,168,76,0.06)", border: excluded ? "1px solid rgba(239,68,68,0.3)" : "1px solid rgba(201,168,76,0.2)", color: excluded ? "#64748b" : "#94a3b8", cursor: "pointer", opacity: excluded ? 0.5 : 1 }}>
                {e.away_team?.abbreviation || "AWY"} @ {e.home_team?.abbreviation || "HOM"} · {e.start_time ? new Date(e.start_time).toLocaleString([], { hour: "numeric", minute: "2-digit" }) : ""}
              </button>
            );
          })}
        </div>
      </div>

      {/* MAIN WORKSPACE */}
      <div style={{ display: "flex", flex: 1, minHeight: 0 }}>
        {/* LEFT 75% */}
        <div style={{ flex: 3, minWidth: 0, display: "flex", flexDirection: "column", borderRight: "1px solid #1e293b" }}>
          <div style={{ display: "flex", borderBottom: "1px solid #1e293b" }}>
            <TabChip label="PLAYER POOL" active={mainTab === "pool"} onClick={() => setMainTab("pool")} />
            <TabChip label="SAVED LINEUPS" active={mainTab === "saved"} onClick={() => { setMainTab("saved"); router.push("/lineups"); }} />
            <TabChip label={`BUILT LINEUPS${lineups.length ? ` (${lineups.length})` : ""}`} active={mainTab === "built"} onClick={() => setMainTab("built")} />
          </div>

          {mainTab === "pool" && (
            <>
              <div style={{ display: "flex", padding: "8px 16px", gap: 8, borderBottom: "1px solid #1e293b", flexWrap: "wrap", alignItems: "center" }}>
                <div style={{ display: "flex", gap: 4 }}>
                  <SubTabChip label="ALL PLAYERS" active={subTab === "all"} onClick={() => setSubTab("all")} />
                  <SubTabChip label={`EXCLUDED${excludedPlayerIds.size ? ` (${excludedPlayerIds.size})` : ""}`} active={subTab === "excluded"} onClick={() => setSubTab("excluded")} />
                  <SubTabChip label={`LIKED${likedIds.size ? ` (${likedIds.size})` : ""}`} active={subTab === "liked"} onClick={() => setSubTab("liked")} />
                </div>
                <div style={{ flex: 1 }} />
                <button onClick={excludeAll} style={{ padding: "4px 10px", borderRadius: 6, fontSize: 10, fontWeight: 600, background: "#1a1f33", border: "1px solid #1e293b", color: "#ef4444", cursor: "pointer" }}>Exclude All</button>
                <span style={{ fontSize: 11, color: "#64748b" }}>{filteredPlayers.length} players</span>
              </div>
              <div style={{ display: "flex", padding: "6px 16px", gap: 4, borderBottom: "1px solid #1e293b", flexWrap: "wrap", alignItems: "center" }}>
                {MLB_POSITIONS.map((pos) => (
                  <button key={pos} onClick={() => setPosFilter(pos)} style={{ padding: "4px 10px", borderRadius: 6, fontSize: 10, fontWeight: 700, background: posFilter === pos ? "rgba(201,168,76,0.15)" : "#1a1f33", border: posFilter === pos ? "1px solid #c9a84c" : "1px solid #1e293b", color: posFilter === pos ? "#c9a84c" : "#94a3b8", cursor: "pointer" }}>{pos}</button>
                ))}
                <div style={{ position: "relative", flex: 1, maxWidth: 280, marginLeft: "auto" }}>
                  <Search size={14} style={{ position: "absolute", left: 10, top: "50%", transform: "translateY(-50%)", color: "#64748b" }} />
                  <input type="text" placeholder="Search players..." value={playerSearch} onChange={(e) => setPlayerSearch(e.target.value)} style={{ width: "100%", padding: "6px 10px 6px 30px", borderRadius: 8, fontSize: 12, background: "#0a0f24", border: "1px solid #1e293b", color: "#f0f6fc", outline: "none" }} />
                </div>
              </div>
              <div style={{ flex: 1, overflow: "auto" }}>
                {filteredPlayers.length === 0 ? (
                  <p style={{ color: "#64748b", textAlign: "center", padding: 40 }}>No players match the current filters.</p>
                ) : (
                  <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12 }}>
                    <thead>
                      <tr style={{ background: "#060b1a", position: "sticky", top: 0, zIndex: 1 }}>
                        <Th>Team</Th><Th>Opp</Th><Th>Start</Th><Th>Pos</Th><Th style={{ width: 28 }}>♥</Th><Th>Player</Th><Th>Salary</Th><Th>SB Proj</Th><Th>My Proj</Th><Th>Value</Th><Th>Exp%</Th><Th>Own%</Th><Th>Props</Th><Th>Action</Th>
                      </tr>
                    </thead>
                    <tbody>
                      {filteredPlayers.slice(0, 300).map((p) => {
                        const evt = filteredEvents.find((e) => (e.players ?? []).some((ep) => ep.player_id === p.player_id));
                        const teamName = evt ? resolveTeamName(p.team_id, evt) : "";
                        const opp = evt ? opponentFor(p, evt) : "";
                        const mCount = countPlayerMarkets(p.player_id, markets);
                        const dfs = matchDFS({ name: p.name, team_id: p.team_id, position: p.position }, dfsPlayers);
                        const isLiked = likedIds.has(p.player_id);
                        const isExcluded = excludedPlayerIds.has(p.player_id);
                        const isLocked = lockedPlayerIds.has(p.player_id);
                        const startT = evt?.start_time ? new Date(evt.start_time).toLocaleString([], { hour: "numeric", minute: "2-digit" }) : "";
                        return (
                          <tr key={p.player_id} style={{ borderBottom: "1px solid #1e293b20", opacity: isExcluded ? 0.35 : 1, background: isLocked ? "rgba(201,168,76,0.08)" : isLiked ? "rgba(201,168,76,0.03)" : "transparent" }}>
                            <Td>{teamName}</Td>
                            <Td style={{ color: "#64748b" }}>{opp || "—"}</Td>
                            <Td style={{ color: "#64748b", fontSize: 10 }}>{startT || "—"}</Td>
                            <Td style={{ color: "#c9a84c", fontWeight: 700, textTransform: "uppercase", fontSize: 10 }}>{p.position || "—"}</Td>
                            <Td>
                              <button onClick={() => toggleLike(p.player_id)} style={{ background: "none", border: "none", cursor: "pointer", padding: 0 }}>
                                <Heart size={14} color={isLiked ? "#c9a84c" : "#334155"} fill={isLiked ? "#c9a84c" : "none"} />
                              </button>
                            </Td>
                            <Td style={{ color: "#f0f6fc", fontWeight: 600 }}>{p.name}</Td>
                            <Td style={{ color: dfs ? "#c9a84c" : "#64748b", fontWeight: dfs ? 700 : 400 }}>{dfs ? `$${dfs.salary.toLocaleString()}` : "—"}</Td>
                            <Td style={{ color: "#64748b" }}>—</Td>
                            <Td style={{ color: "#64748b" }}>—</Td>
                            <Td style={{ color: "#64748b" }}>—</Td>
                            <Td style={{ color: "#64748b" }}>{isLocked || isExcluded ? "—" : "100%"}</Td>
                            <Td style={{ color: "#64748b" }}>—</Td>
                            <Td style={{ color: mCount ? "#c9a84c" : "#64748b" }}>{mCount || "—"}</Td>
                            <Td>
                              <div style={{ display: "flex", gap: 4 }}>
                                <IconBtn icon={<Lock size={12} />} active={isLocked} title="Lock player" onClick={() => toggleLock(p.player_id)} />
                                <IconBtn icon={<Ban size={12} />} active={isExcluded} title="Exclude player" onClick={() => toggleExclude(p.player_id)} />
                              </div>
                            </Td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                )}
              </div>
            </>
          )}

          {mainTab === "built" && (
            <div style={{ flex: 1, overflow: "auto", padding: 20 }}>
              {optimizeMutation.isPending ? <Center><Loader2 size={32} className="animate-spin" style={{ color: "#c9a84c" }} /><p style={{ color: "#94a3b8", marginTop: 8 }}>Running CP-SAT optimizer...</p></Center>
              : optimizeMutation.isError ? <Center><p style={{ color: "#ef4444", fontWeight: 700 }}>{optimizeMutation.error instanceof Error ? optimizeMutation.error.message : "Optimization failed"}</p></Center>
              : lineups.length === 0 ? <Center><p style={{ color: "#64748b" }}>No lineups yet. Click OPTIMIZE to generate.</p></Center>
              : (
                <>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16, flexWrap: "wrap", gap: 8 }}>
                    <h2 style={{ fontSize: 16, fontWeight: 800, color: "#c9a84c", margin: 0 }}>Built Lineups ({lineups.length})</h2>
                    <div style={{ display: "flex", gap: 6 }}>
                      <MiniBtn icon={<Save size={13} />} label={savedNote ? "Saved ✓" : "Save"} onClick={markSaved} />
                      <MiniBtn icon={<RefreshCw size={13} />} label="Regenerate" onClick={regenerate} disabled={optimizeMutation.isPending} />
                      <MiniBtn icon={<Trash2 size={13} />} label="Clear" onClick={clearLineups} />
                      <MiniBtn icon={<List size={13} />} label="View Saved" onClick={() => router.push("/lineups")} />
                    </div>
                  </div>
                  {lastGenMeta && <p style={{ fontSize: 11, color: "#64748b", marginBottom: 12 }}>Platform: {lastGenMeta.platform === "draftkings" ? "DraftKings" : "FanDuel"} · Strategy: {lastGenMeta.strategy} · {lastGenMeta.gameCount} games</p>}
                  {lineups.map((l, i) => <LineupCard key={i} index={i} lineup={l} platform={lastGenMeta?.platform || platform} />)}
                </>
              )}
            </div>
          )}

          {mainTab === "saved" && (
            <div style={{ flex: 1, padding: 20, textAlign: "center" }}><p style={{ color: "#64748b", marginTop: 40 }}>Redirecting to saved /lineups...</p></div>
          )}
        </div>

        {/* RIGHT 25% LINEUP BUILDER */}
        <div style={{ flex: 1, minWidth: 280, maxWidth: 380, background: "#0a0f24", display: "flex", flexDirection: "column", gap: 12, padding: 16, overflow: "auto" }}>
          <SectionTitle>LIVE LINEUP BUILDER</SectionTitle>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8 }}>
            <MetricBox label="Salary Remaining" value={platform === "fanduel" ? "$35,000" : "$50,000"} />
            <MetricBox label="Projected FP" value="—" />
            <MetricBox label="Value" value="—" />
            <MetricBox label="Proj Ownership" value="—" />
          </div>
          <SectionTitle>ROSTER · {platform === "fanduel" ? "FanDuel (9)" : "DraftKings (10)"}</SectionTitle>
          <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
            {slots.map((s, i) => {
              const lp = lockedPlayers[i];
              return (
                <div key={i} style={{ display: "flex", alignItems: "center", gap: 8, padding: "8px 12px", borderRadius: 10, background: lp ? "rgba(201,168,76,0.1)" : "#1a1f33", border: lp ? "1px solid #c9a84c" : "1px solid #1e293b", minHeight: 40 }}>
                  <span style={{ width: 50, fontSize: 10, fontWeight: 800, color: "#c9a84c", textTransform: "uppercase" }}>{slotLabel(s)}</span>
                  {lp ? <span style={{ fontSize: 12, fontWeight: 600, color: "#f0f6fc", flex: 1 }}>{lp.name}</span> : <span style={{ fontSize: 11, color: "#64748b", flex: 1 }}>Lock a player to fill</span>}
                  {lp && <button onClick={() => toggleLock(lp.player_id)} style={{ background: "none", border: "none", cursor: "pointer", padding: 0 }}><X size={14} color="#ef4444" /></button>}
                </div>
              );
            })}
          </div>
          <SectionTitle>LINEUP COUNT</SectionTitle>
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <input type="range" min={1} max={50} value={lineupCount} onChange={(e) => setLineupCount(+e.target.value)} style={{ flex: 1, accentColor: "#c9a84c" }} />
            <span style={{ fontSize: 14, fontWeight: 800, color: "#c9a84c", minWidth: 24, textAlign: "center" }}>{lineupCount}</span>
          </div>
          <button onClick={() => optimizeMutation.mutate()} disabled={!canGenerate || optimizeMutation.isPending} style={{ width: "100%", padding: "16px", borderRadius: 14, fontWeight: 900, fontSize: 16, textTransform: "uppercase", letterSpacing: 1, background: canGenerate ? "#c9a84c" : "#1e293b", color: canGenerate ? "#060b1a" : "#64748b", border: "none", cursor: canGenerate ? "pointer" : "not-allowed", boxShadow: canGenerate ? "0 4px 24px rgba(201,168,76,0.4)" : "none", marginTop: 8 }}>
            {optimizeMutation.isPending ? <><Loader2 size={18} className="animate-spin" /> SOLVING...</> : <>OPTIMIZE</>}
          </button>
          {!slatesLoading && resolvedSlateId == null && <Muted>No {platform === "draftkings" ? "DraftKings" : "FanDuel"} slate for {sport}. Generate unavailable.</Muted>}
          {(lockedPlayerIds.size > 0 || excludedPlayerIds.size > 0) && (
            <div style={{ fontSize: 10, color: "#64748b" }}>
              {lockedPlayerIds.size > 0 && <span>🔒 {lockedPlayerIds.size} locked · </span>}
              {excludedPlayerIds.size > 0 && <span>🚫 {excludedPlayerIds.size} excluded</span>}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// ── Sub-components ──────────────────────────────────────────

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

function SectionTitle({ children }: { children: React.ReactNode }) {
  return <p style={{ fontSize: 10, fontWeight: 800, color: "#64748b", textTransform: "uppercase", letterSpacing: 1, margin: 0 }}>{children}</p>;
}

function MetricBox({ label, value }: { label: string; value: string }) {
  return (
    <div style={{ padding: "10px 12px", borderRadius: 10, background: "#1a1f33", border: "1px solid #1e293b" }}>
      <div style={{ fontSize: 10, color: "#64748b", fontWeight: 700, textTransform: "uppercase" }}>{label}</div>
      <div style={{ fontSize: 16, fontWeight: 800, color: "#c9a84c", marginTop: 2 }}>{value}</div>
    </div>
  );
}

function RuleField({ label, value, onChange, placeholder, step }: { label: string; value: number | undefined; onChange: (v: number | undefined) => void; placeholder: string; step?: number }) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
      <span style={{ fontSize: 11, fontWeight: 600, color: "#94a3b8" }}>{label}</span>
      <input
        type="number"
        value={value ?? ""}
        step={step ?? 1}
        placeholder={placeholder}
        onChange={(e) => onChange(e.target.value === "" ? undefined : Number(e.target.value))}
        style={{ width: 70, padding: "6px 10px", borderRadius: 8, fontSize: 12, background: "#1a1f33", border: "1px solid #1e293b", color: "#f0f6fc", outline: "none" }}
      />
    </div>
  );
}

function TabChip({ label, active, onClick }: { label: string; active: boolean; onClick: () => void }) {
  return (
    <button onClick={onClick} style={{ padding: "12px 18px", fontSize: 12, fontWeight: 800, letterSpacing: 1, background: active ? "#0a0f24" : "transparent", border: "none", borderBottom: active ? "2px solid #c9a84c" : "2px solid transparent", color: active ? "#c9a84c" : "#64748b", cursor: "pointer", textTransform: "uppercase" }}>
      {label}
    </button>
  );
}

function SubTabChip({ label, active, onClick }: { label: string; active: boolean; onClick: () => void }) {
  return (
    <button onClick={onClick} style={{ padding: "6px 12px", borderRadius: 8, fontSize: 11, fontWeight: 700, background: active ? "rgba(201,168,76,0.15)" : "#1a1f33", border: active ? "1px solid #c9a84c" : "1px solid #1e293b", color: active ? "#c9a84c" : "#94a3b8", cursor: "pointer" }}>
      {label}
    </button>
  );
}

function Th({ children, style }: { children: React.ReactNode; style?: React.CSSProperties }) {
  return <th style={{ padding: "8px 10px", textAlign: "left", fontSize: 10, fontWeight: 700, color: "#64748b", textTransform: "uppercase", whiteSpace: "nowrap", ...style }}>{children}</th>;
}

function Td({ children, style }: { children: React.ReactNode; style?: React.CSSProperties }) {
  return <td style={{ padding: "8px 10px", whiteSpace: "nowrap", ...style }}>{children}</td>;
}

function IconBtn({ icon, active, title, onClick }: { icon: React.ReactNode; active: boolean; title: string; onClick: () => void }) {
  return (
    <button onClick={onClick} title={title} style={{ padding: 4, borderRadius: 6, background: active ? "rgba(201,168,76,0.2)" : "transparent", border: active ? "1px solid #c9a84c" : "1px solid transparent", cursor: "pointer", color: active ? "#c9a84c" : "#64748b", display: "flex" }}>
      {icon}
    </button>
  );
}

function Center({ children }: { children: React.ReactNode }) {
  return <div style={{ display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", minHeight: 200, textAlign: "center" }}>{children}</div>;
}

function Muted({ children }: { children: React.ReactNode }) {
  return <p style={{ color: "#64748b", fontSize: 12 }}>{children}</p>;
}

function MiniBtn({ icon, label, onClick, disabled }: { icon: React.ReactNode; label: string; onClick: () => void; disabled?: boolean }) {
  return (
    <button onClick={onClick} disabled={disabled} style={{ display: "flex", alignItems: "center", gap: 6, padding: "8px 14px", borderRadius: 10, background: "#0a0f24", border: "1px solid #1e293b", color: "#94a3b8", fontSize: 12, fontWeight: 600, cursor: disabled ? "not-allowed" : "pointer", opacity: disabled ? 0.5 : 1 }}>
      {icon}{label}
    </button>
  );
}

function LineupCard({ index, lineup, platform }: { index: number; lineup: LineupResponse; platform: string }) {
  const rem = (lineup as any).remaining_salary ?? 0;
  return (
    <div style={{ background: "#0a0f24", borderRadius: 16, border: "1px solid #1e293b", overflow: "hidden", marginBottom: 12 }}>
      <div style={{ height: 4, background: "#c9a84c" }} />
      <div style={{ padding: "14px 18px", display: "flex", justifyContent: "space-between", borderBottom: "1px solid #1e293b", flexWrap: "wrap", gap: 8 }}>
        <span style={{ fontWeight: 800, color: "#f0f6fc" }}>Line {index + 1}</span>
        <div style={{ display: "flex", gap: 14, flexWrap: "wrap" }}>
          <span style={{ color: "#94a3b8", fontSize: 12 }}>Platform: <strong style={{ color: "#f0f6fc" }}>{platform === "draftkings" ? "DraftKings" : "FanDuel"}</strong></span>
          <span style={{ color: "#94a3b8", fontSize: 12 }}>Salary: <strong style={{ color: "#f0f6fc" }}>${lineup.total_salary?.toLocaleString()}</strong></span>
          <span style={{ color: "#94a3b8", fontSize: 12 }}>Remaining: <strong style={{ color: "#c9a84c" }}>${rem.toLocaleString()}</strong></span>
          <span style={{ color: "#c9a84c", fontSize: 12, fontWeight: 700 }}>Proj FP: {lineup.projected_score}</span>
        </div>
      </div>
      <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12 }}>
        <thead>
          <tr style={{ background: "#060b1a" }}>
            <Th>Pos</Th><Th>Player</Th><Th>Team</Th><Th>Opp</Th><Th>Salary</Th><Th>Proj</Th>
          </tr>
        </thead>
        <tbody>
          {(lineup.players || []).map((p: any, j: number) => (
            <tr key={j} style={{ borderBottom: j < (lineup.players || []).length - 1 ? "1px solid #1e293b30" : "none" }}>
              <Td style={{ color: "#c9a84c", fontWeight: 700, textTransform: "uppercase", fontSize: 10 }}>{p.roster_position || p.roster_slot || "—"}</Td>
              <Td style={{ color: "#f0f6fc", fontWeight: 600 }}>{p.name || `Player #${p.id}`}</Td>
              <Td style={{ color: "#64748b" }}>{p.team || ""}</Td>
              <Td style={{ color: "#64748b" }}>{p.opponent || ""}</Td>
              <Td style={{ color: "#94a3b8" }}>${(p.salary || 0).toLocaleString()}</Td>
              <Td style={{ color: "#c9a84c", fontWeight: 700 }}>{(p.projected_fp || 0).toFixed(1)}</Td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}