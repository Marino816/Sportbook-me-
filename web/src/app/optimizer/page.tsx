"use client";

import { useState, useEffect, useMemo, useCallback } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { useMutation } from "@tanstack/react-query";
import { fetchDFSSlates, fetchDFSSlate, runOptimizer, fetchDataHubSlate, fetchOptimalPct, type LineupResponse, type DFSSlatePlayer, type DFSSlateSummary, type CanonicalPlayer } from "@/lib/api";
import { Play, Loader2, Search, Save, RefreshCw, Trash2, List, Lock, Ban, Heart, X, ChevronDown, ChevronUp, BarChart3, Download, ArrowUpDown } from "lucide-react";
import { useEvents } from "@/lib/use-events";
import type { SBEvent, SBPlayer, SBMarket } from "@/lib/sbevent";
import { useWorkspace } from "@/lib/workspace-context";
import { formatBookmakerName } from "@/lib/bookmakers";
import { LastFive } from "@/lib/last-five";

const SPORTS = ["MLB", "NFL", "NBA", "NHL", "NCAAF", "NCAAB"] as const;
const PLATFORMS = ["draftkings", "fanduel"] as const;
const STRATEGIES = ["balanced", "cash", "gpp", "aggressive"] as const;
const DK_SLOTS = ["P", "P", "C", "1B", "2B", "3B", "SS", "OF", "OF", "OF"] as const;
const FD_SLOTS = ["P", "C1B", "2B", "3B", "SS", "OF", "OF", "OF", "UTIL"] as const;
const MLB_POSITIONS = ["ALL", "P", "C", "1B", "2B", "3B", "SS", "OF"] as const;

type MainTab = "pool" | "saved" | "built";
type SubTab = "all" | "excluded" | "liked";
type SortField = "salary" | "fppg" | "optimal";
type SortDir = "desc" | "asc";

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

/** Normalize a position for MLB filter matching. Returns array of eligible filter labels. */
function normalizePosForFilter(pos: string | undefined | null): string[] {
  const p = (pos || "").toUpperCase().trim();
  if (!p) return [];
  if (p.includes("/")) return p.split("/").map((s) => s.trim()).filter(Boolean);
  if (p === "SP" || p === "RP" || p === "P") return ["P"];
  if (p === "LF" || p === "RF" || p === "CF" || p === "DH") return ["OF"];
  return [p];
}

function countPlayerMarkets(playerId: string, markets: SBMarket[]): number {
  return (markets || []).filter((m) => m.player_id === playerId).length;
}

function normName(n: string): string {
  // Normalize Unicode accents FIRST (NFD decomposes é → e + combining mark),
  // then strip non-[a-z0-9] characters.  Prevents name mismatch between
  // SGO ("Jesús Luzardo") and BC DFS ("Jesus Luzardo").
  return (n || "").normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase().replace(/[^a-z0-9]/g, "").trim();
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

/** Determine if a player (with SGO or DFS position) is eligible for a roster slot. */
function slotEligible(pos: string | undefined | null, slot: string): boolean {
  const eligible = normalizePosForFilter(pos);
  if (slot === "UTIL") return eligible.length > 0 && !eligible.every((p) => p === "P");
  if (slot === "C1B") return eligible.some((p) => p === "C" || p === "1B");
  return eligible.includes(slot);
}

// DFS → SGO team abbreviation reconciliation (canonical identity layer).
const TEAM_ABBR_MAP: Record<string, string> = {
  ATH: "OAK", // Athletics (DFS "ATH" ↔ SGO "OAK")
  LAA: "LAA", ARI: "ARI", ATL: "ATL", BAL: "BAL", BOS: "BOS", CHC: "CHC",
  CIN: "CIN", CLE: "CLE", COL: "COL", CWS: "CWS", DET: "DET", HOU: "HOU",
  KC: "KC", LAD: "LAD", MIA: "MIA", MIL: "MIL", MIN: "MIN", NYM: "NYM",
  NYY: "NYY", PHI: "PHI", PIT: "PIT", SD: "SD", SEA: "SEA", SF: "SF",
  STL: "STL", TB: "TB", TEX: "TEX", TOR: "TOR", WSH: "WSH",
};
function mapTeamAbbr(abbr: string | null | undefined): string {
  const a = (abbr || "").toUpperCase();
  return TEAM_ABBR_MAP[a] || a;
}

function exportLineups(lineups: any[], meta: any): void {
  if (!lineups.length) return;
  const rows = [["Lineup","Total Salary","Projected FP","Players"].join(",")];
  lineups.forEach((lu, i) => {
    const players = (lu.players || []).map((p: any) => `${p.roster_slot || p.position} ${p.name}`).join(" | ");
    rows.push([i + 1, lu.total_salary, (lu.projected_score || 0).toFixed(1), `"${players}"`].join(","));
  });
  const blob = new Blob([rows.join("\n")], { type: "text/csv" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `lineups_${meta?.sport || "sbme"}_${new Date().toISOString().slice(0, 10)}.csv`;
  a.click();
  URL.revokeObjectURL(url);
}

export default function OptimizerPage() {
  const router = useRouter();
  const ws = useWorkspace();

  // ── State ──
  const [sport, setSport] = useState<string>("MLB");
  const [platform, setPlatform] = useState<string>("draftkings");
  const [bookmakerSource, setBookmakerSource] = useState<string>("Best Available");
  const [strategy, setStrategy] = useState<string>("balanced");
  const [lineupCount, setLineupCount] = useState(4);
  const { events, loading: sgoLoading } = useEvents(sport);

  const [canonicalPool, setCanonicalPool] = useState<Record<string, CanonicalPlayer>>({});
  const [optPctStatus, setOptPctStatus] = useState<string>("NOT_RUN");
  const [optPctMap, setOptPctMap] = useState<Record<string, number>>({});

  const [excludedGameIds, setExcludedGameIds] = useState<Set<string>>(new Set());
  const [likedIds, setLikedIds] = useState<Set<string>>(new Set());
  const [excludedPlayerIds, setExcludedPlayerIds] = useState<Set<string>>(new Set());
  const [lockedPlayerIds, setLockedPlayerIds] = useState<Set<string>>(new Set());

  const [playerSearch, setPlayerSearch] = useState("");
  const [posFilter, setPosFilter] = useState("ALL");
  const [sortField, setSortField] = useState<SortField>("salary");
  const [sortDir, setSortDir] = useState<SortDir>("desc");
  const [mainTab, setMainTab] = useState<MainTab>("pool");
  const [subTab, setSubTab] = useState<SubTab>("all");

  const [lineups, setLineups] = useState<LineupResponse[]>([]);
  const [slates, setSlates] = useState<DFSSlateSummary[]>([]);
  const [resolvedSlateId, setResolvedSlateId] = useState<number | null>(null);
  const [slatesLoading, setSlatesLoading] = useState(true);
  const [hasStaleSlates, setHasStaleSlates] = useState(false);
  const [showStackingRules, setShowStackingRules] = useState(false);
  const [maxHittersPerTeam, setMaxHittersPerTeam] = useState<number | undefined>();
  const [stackSize, setStackSize] = useState<number | undefined>();
  const [pitcherConflict, setPitcherConflict] = useState<boolean>(true);
  const [minSalaryOverride, setMinSalaryOverride] = useState<number | undefined>();
  const [maxSalaryOverride, setMaxSalaryOverride] = useState<number | undefined>();
  const [globalMaxExposure, setGlobalMaxExposure] = useState<number | undefined>();
  const [savedNote, setSavedNote] = useState(false);
  const [lastGenMeta, setLastGenMeta] = useState<{ sport: string; platform: string; strategy: string; gameCount: number } | null>(null);
  const [selectedLineupIndex, setSelectedLineupIndex] = useState(0);
  const [projPool, setProjPool] = useState<Record<string, { projected_fp: number; salary: number; position: string; team: string; opponent: string; projection_source: string }>>({});
  const [myProj, setMyProj] = useState<Record<string, number>>({});

  // ── DFS slate ──
  useEffect(() => {
    let cancelled = false;
    async function load() {
      setSlatesLoading(true);
      try {
        const res = await fetchDFSSlates(platform, sport);
        const pub = (res?.data ?? []).filter((s: any) => s.status === "PUBLISHED");
        // Only CURRENT slates are eligible for optimization.
        // Stale (prior-date) slates are blocked by freshness protection
        // so today's SGO games are never enriched onto an old slate.
        const current = pub.filter((s: any) => s.is_current !== false);
        if (!cancelled) {
          setSlates(current);
          // Auto-select: prefer Main slate, then first available
          const main = current.find((s: any) => s.slate_name.toLowerCase().includes("main"));
          const defaultId = main?.id ?? (current.length > 0 ? current[0].id : null);
          setResolvedSlateId(defaultId);
          setHasStaleSlates(pub.length > current.length);
        }
      } catch { if (!cancelled) { setSlates([]); setResolvedSlateId(null); setHasStaleSlates(false); } }
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

  // Canonical pool (Own% / Leverage / Ceiling / Floor / SB Projections / VALUE)
  useEffect(() => {
    if (!resolvedSlateId) { setCanonicalPool({}); setProjPool(prev => Object.keys(prev).length > 0 ? prev : {}); return; }
    let cancelled = false;
    (async () => {
      try {
        const res = await fetchDataHubSlate(resolvedSlateId, platform);
        if (!cancelled) {
          const map: Record<string, CanonicalPlayer> = {};
          const projMap: Record<string, any> = {};
          for (const p of res?.data?.players ?? []) {
            const nm = (p.name || "").toLowerCase().trim();
            if (nm) {
              map[nm] = p;
              // Seed projPool from canonical pool so SB PROJ & VALUE display before OPTIMIZE
              projMap[nm] = {
                projected_fp: p.projected_fp,
                projection_source: p.projection_source,
                salary: p.salary,
                position: p.roster_position || p.position,
                team: p.team,
                opponent: p.opponent,
              };
            }
          }
          setCanonicalPool(map);
          setProjPool(prev => {
            // Merge canonical projections with any existing (from prior OPTIMIZE click)
            return { ...projMap, ...prev };
          });
        }
      } catch { if (!cancelled) { setCanonicalPool({}); } }
    })();
    return () => { cancelled = true; };
  }, [resolvedSlateId, platform]);

  // Optimal% — poll cached background simulation result
  useEffect(() => {
    if (!resolvedSlateId) { setOptPctStatus("NOT_RUN"); setOptPctMap({}); return; }
    let cancelled = false;
    (async () => {
      try {
        const res = await fetchOptimalPct(resolvedSlateId, platform);
        if (cancelled) return;
        const status = res?.data?.status ?? "NOT_RUN";
        setOptPctStatus(status);
        if (status === "COMPLETE" && res?.data?.result?.players) {
          const m: Record<string, number> = {};
          for (const p of res.data.result.players) {
            const nm = (p.name || "").toLowerCase().trim();
            if (nm) m[nm] = p.optimal_pct;
          }
          setOptPctMap(m);
        } else {
          setOptPctMap({});
        }
      } catch {
        if (!cancelled) { setOptPctStatus("NOT_RUN"); setOptPctMap({}); }
      }
    })();
    return () => { cancelled = true; };
  }, [resolvedSlateId, platform]);

  useEffect(() => { setPlayerSearch(""); setPosFilter("ALL"); setLineups([]); setLastGenMeta(null); }, [sport, platform]);

  // ── Derived ──
  // DFS slate membership: the set of team abbreviations present in the
  // selected contest slate. SGO events/players are then filtered to ONLY
  // those teams so an SGO game can never leak into a DK/FD slate simply
  // because it shares a sport.
  const slateTeamAbbrs = useMemo(() => {
    const s = new Set<string>();
    for (const p of dfsPlayers) {
      if (p.team) s.add(mapTeamAbbr(p.team));
      if (p.opponent) s.add(mapTeamAbbr(p.opponent));
    }
    return s;
  }, [dfsPlayers]);

  const filteredEvents = useMemo(() => {
    // ── Slate guard: if no slate is selected, show no events/players ──
    // Prevents ALL SGO games from leaking in when the slate dropdown is empty.
    if (resolvedSlateId == null) return [];

    let evts = events;
    if (slateTeamAbbrs.size > 0) {
      evts = events.filter((e) => {
        const h = mapTeamAbbr(e.home_team?.abbreviation);
        const a = mapTeamAbbr(e.away_team?.abbreviation);
        return slateTeamAbbrs.has(h) || slateTeamAbbrs.has(a);
      });
    }
    if (excludedGameIds.size === 0) return evts;
    return evts.filter((e) => !excludedGameIds.has(e.id));
  }, [events, excludedGameIds, resolvedSlateId, slateTeamAbbrs]);

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
    pool = pool.filter((p) => {
      if (posFilter !== "ALL") {
        let eligible = normalizePosForFilter(p.position);
        const dfs = matchDFS({ name: p.name, team_id: p.team_id, position: p.position }, dfsPlayers);
        if (dfs) {
          const dfsEligible = (dfs.eligible_positions || [dfs.position]).flatMap((ep) => normalizePosForFilter(ep));
          eligible = Array.from(new Set([...eligible, ...dfsEligible]));
        }
        if (!eligible.includes(posFilter)) return false;
      }
      if (!playerSearch) return true;
      const q = playerSearch.toLowerCase();
      if (p.name.toLowerCase().includes(q)) return true;
      const evt = filteredEvents.find((e) => (e.players ?? []).some((ep) => ep.player_id === p.player_id));
      return evt ? resolveTeamName(p.team_id, evt).toLowerCase().includes(q) : false;
    });
    // ── Sorting ──
    const sorted = [...pool].sort((a, b) => {
      const dfsA = matchDFS({ name: a.name, team_id: a.team_id, position: a.position }, dfsPlayers);
      const dfsB = matchDFS({ name: b.name, team_id: b.team_id, position: b.position }, dfsPlayers);
      const poolA = projPool[a.name.toLowerCase()];
      const poolB = projPool[b.name.toLowerCase()];
      const fpA = poolA?.projected_fp != null && poolA?.projection_source !== "UNAVAILABLE" ? poolA.projected_fp : null;
      const fpB = poolB?.projected_fp != null && poolB?.projection_source !== "UNAVAILABLE" ? poolB.projected_fp : null;
      if (sortField === "salary") {
        const salA = dfsA?.salary ?? 0;
        const salB = dfsB?.salary ?? 0;
        return sortDir === "desc" ? salB - salA : salA - salB;
      }
      if (sortField === "optimal") {
        const optA = optPctMap[a.name.toLowerCase()] ?? null;
        const optB = optPctMap[b.name.toLowerCase()] ?? null;
        if (optA == null && optB == null) return 0;
        if (optA == null) return 1;
        if (optB == null) return -1;
        return sortDir === "desc" ? optB - optA : optA - optB;
      }
      // FPPG: unavailable projections sort to bottom
      if (fpA == null && fpB == null) return 0;
      if (fpA == null) return 1;
      if (fpB == null) return -1;
      return sortDir === "desc" ? fpB - fpA : fpA - fpB;
    });
    return sorted;
  }, [players, subTab, excludedPlayerIds, likedIds, posFilter, playerSearch, filteredEvents, dfsPlayers, projPool, optPctMap, sortField, sortDir]);

  const upcomingEvents = events.filter((e) => !liveClass(e.status));

  // Slate integrity: bidirectional SGO↔DFS match rate scoped to this slate's games.
  // SGO only returns bettable players (~8 per game), NOT full rosters (~92 per game).
  // Comparing all 459 DFS players against the full-league SGO pool is incorrect.
  // Instead: (1) scope SGO events to the teams in this slate, (2) count SGO players
  // from those events, (3) measure how many of those SGO players match DFS, and (4)
  // measure how many DFS players from those SGO-covered games match SGO players.
  const slateIntegrity = useMemo(() => {
    if (!resolvedSlateId || dfsPlayers.length === 0) return { matchRate: 1.0, matched: 0, total: 0, sgoPlayerCount: 0, dfsScopeCount: 0, dfsToSgoMatchRate: 0, dfsToSgoMatched: 0, missingPlayers: [] as string[], healthy: true };

    // Get unique team abbreviations from the slate DFS pool
    const slateTeamAbbrs = new Set(dfsPlayers.map((dp) => (dp.team || "").toUpperCase()).filter(Boolean));

    // Find SGO events whose home/away teams are in this slate
    const slateEvents = events.filter((e) => {
      const ha = (e.home_team?.abbreviation || "").toUpperCase();
      const aa = (e.away_team?.abbreviation || "").toUpperCase();
      return slateTeamAbbrs.has(ha) || slateTeamAbbrs.has(aa);
    });

    // Build team_id → abbreviation map from these events
    const teamIdToAbbr: Record<string, string> = {};
    for (const e of slateEvents) {
      if (e.home_team?.team_id && e.home_team?.abbreviation)
        teamIdToAbbr[e.home_team.team_id.toUpperCase()] = e.home_team.abbreviation.toUpperCase();
      if (e.away_team?.team_id && e.away_team?.abbreviation)
        teamIdToAbbr[e.away_team.team_id.toUpperCase()] = e.away_team.abbreviation.toUpperCase();
    }

    // Collect SGO players ONLY from slate-scoped events
    const slateSgoPlayers = slateEvents.flatMap((e) => e.players || []);
    const sgoTotal = slateSgoPlayers.length;

    if (sgoTotal === 0) return { matchRate: 1.0, matched: 0, total: 0, sgoPlayerCount: 0, dfsScopeCount: 0, dfsToSgoMatchRate: 1, dfsToSgoMatched: 0, missingPlayers: [] as string[], healthy: true };

    // SGO→DFS: of the SGO players in slate games, how many have a DFS record
    // with matching name AND team?
    const sgoToDfsMatched = slateSgoPlayers.filter((sp) => {
      const sgoTeamAbbr = teamIdToAbbr[(sp.team_id || "").toUpperCase()] || "";
      return dfsPlayers.some((dp) =>
        normName(dp.name) === normName(sp.name) &&
        (dp.team || "").toUpperCase() === sgoTeamAbbr
      );
    }).length;
    const sgoMatchRate = sgoToDfsMatched / sgoTotal;

    // DFS→SGO: of the DFS players whose teams are in the scoped SGO events,
    // how many match an SGO player? This flags missing SGO coverage.
    const dfsScopePlayers = dfsPlayers.filter((dp) => slateTeamAbbrs.has((dp.team || "").toUpperCase()));
    const dfsToSgoMatched = dfsScopePlayers.filter((dp) => {
      const dpTeam = (dp.team || "").toUpperCase();
      return slateSgoPlayers.some((sp) => {
        const sgoTeamAbbr = teamIdToAbbr[(sp.team_id || "").toUpperCase()] || "";
        return normName(sp.name) === normName(dp.name) && sgoTeamAbbr === dpTeam;
      });
    }).length;
    const dfsMatchRate = dfsScopePlayers.length > 0 ? dfsToSgoMatched / dfsScopePlayers.length : 1.0;

    // Missing DFS players from SGO (scoped to slate games only)
    const missingPlayers = dfsScopePlayers
      .filter((dp) => {
        const dpTeam = (dp.team || "").toUpperCase();
        return !slateSgoPlayers.some((sp) => {
          const sgoTeamAbbr = teamIdToAbbr[(sp.team_id || "").toUpperCase()] || "";
          return normName(sp.name) === normName(dp.name) && sgoTeamAbbr === dpTeam;
        });
      })
      .map((dp) => dp.name)
      .slice(0, 20);

    // Primary gate: SGO→DFS must be ≥ 85%. If the SGO players in slate games
    // don't match DFS records, the slate date/teams are out of sync.
    const healthy = sgoMatchRate >= 0.85;

    return {
      matchRate: sgoMatchRate,
      matched: sgoToDfsMatched,
      total: sgoTotal,
      sgoPlayerCount: sgoTotal,
      dfsScopeCount: dfsScopePlayers.length,
      dfsToSgoMatchRate: dfsMatchRate,
      dfsToSgoMatched,
      missingPlayers,
      healthy,
    };
  }, [resolvedSlateId, dfsPlayers, players, events]);

  const canGenerate = !slatesLoading && resolvedSlateId != null && filteredEvents.length > 0 && slateIntegrity.healthy;

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
      // My Proj overrides — send player name + custom projection to the solver
      const overrides = Object.entries(myProj)
        .map(([pid, proj]) => ({ name: players.find((x) => x.player_id === pid)?.name, projected_fp: proj }))
        .filter((x) => x.name && x.projected_fp != null && !Number.isNaN(x.projected_fp));
      if (overrides.length > 0) setting.projection_overrides = overrides;
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

        // Store projection pool (keyed by name for frontend matching)
        const pool = (data as Record<string, unknown>)?.pool;
        if (Array.isArray(pool)) {
          const poolMap: Record<string, any> = {};
          for (const p of pool) {
            const nm = (p?.name || "").toLowerCase().trim();
            if (nm) poolMap[nm] = p;
          }
          setProjPool(poolMap);
        } else { setProjPool({}); }
      } catch { setLineups([]); setProjPool({}); }
      setLastGenMeta({ sport, platform, strategy, gameCount: filteredEvents.length });
      setMainTab("built");
      setSelectedLineupIndex(0);
    },
    onError: () => { setLineups([]); setLastGenMeta(null); },
  });

  const clearLineups = useCallback(() => { setLineups([]); setLastGenMeta(null); setSavedNote(false); }, []);
  const regenerate = useCallback(() => optimizeMutation.mutate(), [optimizeMutation]);
  const markSaved = useCallback(() => setSavedNote(true), []);

  const slots = platform === "fanduel" ? FD_SLOTS : DK_SLOTS;
  const lockedPlayers = players.filter((p) => lockedPlayerIds.has(p.player_id));

  // Selected generated lineup (for right-side builder)
  const selectedLineup = lineups[selectedLineupIndex] ?? null;
  const selectedSlotPlayers = (selectedLineup?.players as any[]) ?? [];

  // Roster rows: generated lineup populates slots; manual locks fill them before optimize.
  const rosterRows = useMemo(() => {
    if (selectedSlotPlayers.length > 0) {
      return slots.map((slot, i) => {
        const p = selectedSlotPlayers[i] ?? null;
        return p ? { slot, name: p.name || `#${p.id}`, salary: p.salary || 0, proj: p.projected_fp || 0, opponent: p.opponent || "", team: p.team || "" } : { slot, name: "", salary: 0, proj: 0, opponent: "", team: "" };
      });
    }
    // Manual locks — assign to first eligible slot
    const rows = slots.map((s) => ({ slot: s, name: "", salary: 0, proj: 0, opponent: "", team: "" }));
    const used = new Set<number>();
    for (const lp of lockedPlayers) {
      const evt = filteredEvents.find((e) => (e.players ?? []).some((ep) => ep.player_id === lp.player_id));
      const opp = evt ? opponentFor(lp, evt) : "";
      const dfs = matchDFS({ name: lp.name, team_id: lp.team_id, position: lp.position }, dfsPlayers);
      for (let i = 0; i < slots.length; i++) {
        if (used.has(i)) continue;
        if (slotEligible(lp.position || (dfs?.position ?? ""), slots[i])) {
          rows[i] = { slot: slots[i], name: lp.name, salary: dfs?.salary || 0, proj: 0, opponent: opp, team: evt ? resolveTeamName(lp.team_id, evt) : "" };
          used.add(i);
          break;
        }
      }
    }
    return rows;
  }, [selectedSlotPlayers, slots, lockedPlayers, filteredEvents, dfsPlayers]);

  // Right-side metrics
  const builderMetrics = useMemo(() => {
    if (!selectedLineup) {
      const cap = platform === "fanduel" ? 35000 : 50000;
      const lockedSal = lockedPlayers.reduce((s, lp) => {
        const dfs = matchDFS({ name: lp.name, team_id: lp.team_id, position: lp.position }, dfsPlayers);
        return s + (dfs?.salary || 0);
      }, 0);
      return { cap, remaining: cap - lockedSal, projFP: 0, value: "—", ownership: "N/A" };
    }
    const cap = platform === "fanduel" ? 35000 : 50000;
    const rem = (selectedLineup as any).remaining_salary ?? (cap - selectedLineup.total_salary);
    const fp = selectedLineup.projected_score;
    const val = selectedLineup.total_salary > 0 ? (fp / (selectedLineup.total_salary / 1000)).toFixed(2) : "—";
    return { cap, remaining: rem, projFP: fp, value: val, ownership: "N/A" };
  }, [selectedLineup, platform, lockedPlayers, dfsPlayers]);

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
          <Selector label="Slate" value={resolvedSlateId == null ? "" : String(resolvedSlateId)} options={slates.map((s) => String(s.id))} onChange={(v) => setResolvedSlateId(v ? Number(v) : null)} format={(v) => { const s = slates.find((x) => String(x.id) === v); return s ? `${s.slate_name} (${s.player_count})` : v; }} />
          <Selector label="Bookmaker" value={bookmakerSource} options={["Best Available", "Book Consensus", ...bookmakers]} onChange={setBookmakerSource} format={(v) => (v === "Best Available" || v === "Book Consensus" ? v : formatBookmakerName(v))} />
          <Selector label="Strategy" value={strategy} options={[...STRATEGIES]} onChange={setStrategy} />
          <span style={{ fontSize: 11, color: "#64748b" }}>
            Slate: {slatesLoading ? "Loading..." : resolvedSlateId ? `${(new Set(dfsPlayers.map(p => p.team)).size / 2).toFixed(0)} Games · ${dfsPlayers.length} Players · SGO {${slateIntegrity.total} players, ${(slateIntegrity.matchRate * 100).toFixed(0)}% matched}` : slates.length === 0 ? `No current ${platform === "draftkings" ? "DraftKings" : "FanDuel"} ${sport} slate is available yet` : "Select a slate"}
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
                <div style={{ width: 1, height: 20, background: "#1e293b", margin: "0 4px" }} />
                <div style={{ display: "flex", alignItems: "center", gap: 4 }}>
                  <ArrowUpDown size={12} style={{ color: "#64748b" }} />
                  <select
                    value={sortField + "|" + sortDir}
                    onChange={(e) => {
                      const [f, d] = e.target.value.split("|") as [SortField, SortDir];
                      setSortField(f); setSortDir(d);
                    }}
                    style={{ padding: "4px 8px", borderRadius: 6, fontSize: 10, fontWeight: 700, background: "#1a1f33", border: "1px solid #1e293b", color: "#c9a84c", cursor: "pointer", outline: "none" }}
                  >
                    <option value="salary|desc">Salary — High to Low</option>
                    <option value="salary|asc">Salary — Low to High</option>
                    <option value="fppg|desc">SB Projection — High to Low</option>
                    <option value="fppg|asc">SB Projection — Low to High</option>
                    <option value="optimal|desc">Optimal% — High to Low</option>
                    <option value="optimal|asc">Optimal% — Low to High</option>
                  </select>
                </div>
                <div style={{ width: 1, height: 20, background: "#1e293b", margin: "0 4px" }} />
                <div style={{ position: "relative", flex: 1, maxWidth: 260 }}>
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
                        <Th>Team</Th><Th>Opp</Th><Th>Start</Th><Th>Pos</Th><Th style={{ width: 28 }}>♥</Th><Th>Player</Th><Th>Salary</Th><Th><TTip help="Blue Collar DFS independently calculated fantasy-points projection. Not a DraftKings FPPG metric. Independent external estimate, not an SB ME projection.">BC Proj</TTip></Th><Th>SB Proj</Th><Th>My Proj</Th><Th>Value</Th>
                        <Th><TTip help="SB ME projected field ownership estimate. Not actual contest ownership.">SB OWN%</TTip></Th>
                        <Th><TTip help="Positive values indicate players projected to provide stronger value relative to modeled ownership.">LEV</TTip></Th>
                        <Th><TTip help={optPctStatus === "LOCKED" ? "Optimal% is not available for locked/in-progress slates." : "Percentage of SB ME simulations in which this player appeared in the highest-scoring legal lineup for the simulated slate outcome."}>OPT%</TTip></Th>
                        <Th><TTip help="Modeled estimate: SB Projection × 1.35">CEIL</TTip></Th>
                        <Th><TTip help="Modeled estimate: SB Projection × 0.65">FLOOR</TTip></Th>
                        <Th><TTip help="Number of available player prop markets from SGO.">PROPS</TTip></Th>
                        <Th>Action</Th>
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
                        const poolEntry = projPool[p.name.toLowerCase()];
                        const sbProj = poolEntry?.projected_fp != null && poolEntry?.projection_source !== "UNAVAILABLE" ? poolEntry.projected_fp : null;
                        const salary = dfs?.salary ?? 0;
                        const effectiveProj = myProj[p.player_id] != null ? myProj[p.player_id] : sbProj;
                        const value = salary > 0 && effectiveProj != null ? (effectiveProj / (salary / 1000)).toFixed(2) : "—";
                        const canon = canonicalPool[p.name.toLowerCase()];
                        const ownPct = canon?.sbme_ownership_pct ?? null;
                        const leverage = canon?.leverage ?? null;
                        const ceiling = canon?.ceiling ?? null;
                        const floor = canon?.floor ?? null;
                        const optPct = optPctMap[p.name.toLowerCase()] ?? null;
                        return (
                          <tr key={p.player_id} style={{ borderBottom: "1px solid #1e293b20", opacity: isExcluded ? 0.35 : 1, background: isLocked ? "rgba(201,168,76,0.08)" : isLiked ? "rgba(201,168,76,0.03)" : "transparent" }}>
                            <Td>{teamName}</Td>
                            <Td style={{ color: "#64748b" }}>{opp || "—"}</Td>
                            <Td style={{ color: "#64748b", fontSize: 10 }}>{startT || "—"}</Td>
                            <Td style={{ color: "#c9a84c", fontWeight: 700, textTransform: "uppercase", fontSize: 10 }}>{dfs?.position || p.position || "—"}</Td>
                            <Td>
                              <button onClick={() => toggleLike(p.player_id)} style={{ background: "none", border: "none", cursor: "pointer", padding: 0 }}>
                                <Heart size={14} color={isLiked ? "#c9a84c" : "#334155"} fill={isLiked ? "#c9a84c" : "none"} />
                              </button>
                            </Td>
                            <Td style={{ color: "#f0f6fc", fontWeight: 600 }}>{p.name}</Td>
                            <Td style={{ color: dfs ? "#c9a84c" : "#64748b", fontWeight: dfs ? 700 : 400 }}>{dfs ? `$${dfs.salary.toLocaleString()}` : "—"}</Td>
                            <Td style={{ color: dfs?.fppg != null ? "#94a3b8" : "#64748b", fontWeight: dfs?.fppg != null ? 600 : 400 }}>{dfs?.fppg != null ? dfs.fppg.toFixed(1) : "N/A"}</Td>
                            <Td style={{ color: sbProj != null ? "#c9a84c" : "#64748b", fontWeight: sbProj != null ? 700 : 400 }}>{sbProj != null ? sbProj.toFixed(1) : "N/A"}</Td>
                            <Td>
                              <input type="number" step="0.1" value={myProj[p.player_id] ?? sbProj ?? ""} placeholder={sbProj != null ? "" : "—"} onChange={(e) => setMyProj((prev) => ({ ...prev, [p.player_id]: Number(e.target.value) }))} style={{ width: 56, padding: "4px 6px", borderRadius: 6, fontSize: 11, background: "#1a1f33", border: "1px solid #1e293b", color: "#f0f6fc", outline: "none" }} />
                            </Td>
                            <Td style={{ color: value !== "—" ? "#c9a84c" : "#64748b", fontWeight: value !== "—" ? 700 : 400 }}>{value}</Td>
                            <Td style={{ color: ownPct != null ? "#94a3b8" : "#64748b" }}>{ownPct != null ? `${ownPct.toFixed(1)}%` : "N/A"}</Td>
                            <Td style={{ color: leverage != null ? (leverage > 0 ? "#4ade80" : "#f87171") : "#64748b" }}>{leverage != null ? leverage.toFixed(1) : "N/A"}</Td>
                            <Td style={{ color: optPct != null ? "#c9a84c" : "#64748b", fontWeight: optPct != null ? 700 : 400 }}>{optPct != null ? `${optPct.toFixed(1)}%` : optPctStatus === "LOCKED" ? "—" : optPctStatus === "COMPLETE" ? "—" : optPctStatus === "RUNNING" || optPctStatus === "QUEUED" ? "Calculating…" : "—"}</Td>
                            <Td style={{ color: ceiling != null ? "#94a3b8" : "#64748b" }}>{ceiling != null ? ceiling.toFixed(1) : "N/A"}</Td>
                            <Td style={{ color: floor != null ? "#94a3b8" : "#64748b" }}>{floor != null ? floor.toFixed(1) : "N/A"}</Td>
                            <Td style={{ color: mCount ? "#c9a84c" : "#64748b" }}>{mCount || "—"}</Td>
                            <Td>
                              <div style={{ display: "flex", gap: 4 }}>
                                <IconBtn icon={<Lock size={12} />} active={isLocked} title="Lock player" onClick={() => toggleLock(p.player_id)} />
                                <IconBtn icon={<Ban size={12} />} active={isExcluded} title="Exclude player" onClick={() => toggleExclude(p.player_id)} />
                              </div>
                              <LastFive player={{ name: p.name, player_id: p.player_id }} platform={platform} />
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
                      <MiniBtn icon={<BarChart3 size={13} />} label="Simulate" onClick={() => { ws.setPendingLineups(lineups); router.push("/sims"); }} />
                      <MiniBtn icon={<Download size={13} />} label="Export" onClick={() => exportLineups(lineups, lastGenMeta)} />
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
            <MetricBox label="Salary Remaining" value={`$${(builderMetrics.remaining >= 0 ? builderMetrics.remaining : 0).toLocaleString()}`} />
            <MetricBox label="Projected FP" value={builderMetrics.projFP ? builderMetrics.projFP.toFixed(1) : "—"} />
            <MetricBox label="Value" value={String(builderMetrics.value)} />
            <MetricBox label="Proj Ownership" value={builderMetrics.ownership} />
          </div>

          {/* Lineup switcher (after generate) */}
          {lineups.length > 1 && (
            <>
              <SectionTitle>BUILT LINE</SectionTitle>
              <div style={{ display: "flex", gap: 4, flexWrap: "wrap" }}>
                {lineups.map((_, i) => (
                  <button key={i} onClick={() => setSelectedLineupIndex(i)} style={{ padding: "6px 10px", borderRadius: 8, fontSize: 11, fontWeight: 700, background: selectedLineupIndex === i ? "rgba(201,168,76,0.2)" : "#1a1f33", border: selectedLineupIndex === i ? "1px solid #c9a84c" : "1px solid #1e293b", color: selectedLineupIndex === i ? "#c9a84c" : "#94a3b8", cursor: "pointer" }}>Line {i + 1}</button>
                ))}
              </div>
            </>
          )}

          <SectionTitle>ROSTER · {platform === "fanduel" ? "FanDuel (9)" : "DraftKings (10)"}</SectionTitle>
          <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
            {rosterRows.map((row, i) => (
              <div key={i} style={{ display: "flex", alignItems: "center", gap: 8, padding: "8px 12px", borderRadius: 10, background: row.name ? "rgba(201,168,76,0.1)" : "#1a1f33", border: row.name ? "1px solid #c9a84c" : "1px solid #1e293b", minHeight: 40 }}>
                <span style={{ width: 50, fontSize: 10, fontWeight: 800, color: "#c9a84c", textTransform: "uppercase" }}>{slotLabel(row.slot)}</span>
                {row.name ? (
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ fontSize: 12, fontWeight: 600, color: "#f0f6fc", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{row.name}</div>
                    <div style={{ fontSize: 10, color: "#64748b" }}>{row.team} vs {row.opponent || "—"}{row.salary ? ` · $${row.salary.toLocaleString()}` : ""}</div>
                  </div>
                ) : (
                  <span style={{ fontSize: 11, color: "#64748b", flex: 1 }}>{selectedLineup ? "" : "Lock a player to fill"}</span>
                )}
              </div>
            ))}
          </div>
          <SectionTitle>LINEUP COUNT</SectionTitle>
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <input type="range" min={1} max={50} value={lineupCount} onChange={(e) => setLineupCount(+e.target.value)} style={{ flex: 1, accentColor: "#c9a84c" }} />
            <span style={{ fontSize: 14, fontWeight: 800, color: "#c9a84c", minWidth: 24, textAlign: "center" }}>{lineupCount}</span>
          </div>
          <button onClick={() => optimizeMutation.mutate()} disabled={!canGenerate || optimizeMutation.isPending} style={{ width: "100%", padding: "16px", borderRadius: 14, fontWeight: 900, fontSize: 16, textTransform: "uppercase", letterSpacing: 1, background: canGenerate ? "#c9a84c" : "#1e293b", color: canGenerate ? "#060b1a" : "#64748b", border: "none", cursor: canGenerate ? "pointer" : "not-allowed", boxShadow: canGenerate ? "0 4px 24px rgba(201,168,76,0.4)" : "none", marginTop: 8 }}>
            {optimizeMutation.isPending ? <><Loader2 size={18} className="animate-spin" /> SOLVING...</> : <>OPTIMIZE</>}
          </button>
          {resolvedSlateId != null && !slateIntegrity.healthy && (
            <div style={{ marginTop: 12, padding: "14px 18px", borderRadius: 12, background: "rgba(239,68,68,0.05)", border: "1px solid rgba(239,68,68,0.2)", fontSize: 11 }}>
              <div style={{ fontWeight: 800, color: "#ef4444", marginBottom: 6, display: "flex", alignItems: "center", gap: 6 }}>
                <Ban size={13} /> SLATE INTEGRITY FAILURE — OPTIMIZE DISABLED
              </div>
              <div style={{ color: "#94a3b8", marginBottom: 4 }}>
                Only {slateIntegrity.matched} of {slateIntegrity.total} SGO players in this slate's games ({Number(slateIntegrity.matchRate * 100).toFixed(1)}%) matched against DFS records. Minimum threshold: 85%.
                ({slateIntegrity.dfsToSgoMatched} of {slateIntegrity.dfsScopeCount} DFS players matched back to SGO.)
              </div>
              {slateIntegrity.missingPlayers.length > 0 && (
                <div style={{ color: "#64748b", marginTop: 4 }}>
                  DFS players without SGO match (from scoped games): {slateIntegrity.missingPlayers.join(", ")}
                </div>
              )}
            </div>
          )}
          {!slatesLoading && resolvedSlateId == null && (
            <div style={{ marginTop: 12, padding: "16px 18px", borderRadius: 12, background: "rgba(201,168,76,0.04)", border: "1px solid rgba(201,168,76,0.12)", textAlign: "center" }}>
              <div style={{ fontSize: 24, marginBottom: 8, opacity: 0.4 }}>⏳</div>
              <div style={{ fontSize: 14, fontWeight: 800, color: "#c9a84c", marginBottom: 4 }}>
                No Current {platform === "draftkings" ? "DraftKings" : "FanDuel"} Slate Available
              </div>
              <div style={{ fontSize: 11, color: "#94a3b8", marginBottom: 2, lineHeight: 1.5 }}>
                A current {platform === "draftkings" ? "DraftKings" : "FanDuel"} salary slate is required before optimization can run.
              </div>
              {hasStaleSlates && (
                <div style={{ fontSize: 10, color: "#64748b", marginTop: 6 }}>
                  One or more {platform === "draftkings" ? "DraftKings" : "FanDuel"} slates exist but are for past dates and have been blocked by freshness protection.
                </div>
              )}
              <Link href="/admin/dfs-import" style={{ display: "inline-block", marginTop: 10, padding: "6px 16px", borderRadius: 8, background: "rgba(201,168,76,0.1)", border: "1px solid rgba(201,168,76,0.25)", color: "#c9a84c", fontSize: 11, fontWeight: 700, textDecoration: "none" }}>
                Upload Today's DKSalaries.csv
              </Link>
            </div>
          )}
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

/** Tooltip wrapper for column headers. Renders a small '?' icon with hover text. */
function TTip({ children, help }: { children: React.ReactNode; help: string }) {
  return (
    <span style={{ display: "inline-flex", alignItems: "center", gap: 2, cursor: "help" }}>
      {children}
      <span title={help} style={{ fontSize: 9, color: "#64748b", lineHeight: 1 }}>ⓘ</span>
    </span>
  );
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