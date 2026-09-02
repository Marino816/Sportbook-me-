"use client";

import { useState, useEffect, useMemo, useCallback, useRef } from "react";
import { useRouter } from "next/navigation";
import { useMutation } from "@tanstack/react-query";
import { fetchDFSSlates, fetchDFSSlate, runOptimizer, fetchDataHubSlate, fetchOptimalPct, saveLineupHistory, type LineupResponse, type DFSSlatePlayer, type DFSSlateSummary, type CanonicalPlayer } from "@/lib/api";
import { formatOptPctCell, lookupOptimalPct, mapOptimalPctResponse } from "@/lib/optimal-pct";
import { extractOptimizerLineups, optimizerGenerationNote, requestedNumLineups } from "@/lib/optimizer-results";
import { Loader2, Search, Save, RefreshCw, Trash2, List, Lock, Ban, Heart, BarChart3, Download, ArrowUpDown } from "lucide-react";
import { useEvents } from "@/lib/use-events";
import type { SBEvent, SBPlayer, SBMarket } from "@/lib/sbevent";
import { useWorkspace } from "@/lib/workspace-context";
import { formatBookmakerName } from "@/lib/bookmakers";
import { LastFive } from "@/lib/last-five";
import { parseOptimizerHandoff } from "@/lib/ai-session";
import { averageRemainingPerPlayer, getRoster, slotEligible, slotLabel, UNIQUE_LINEUP_UNAVAILABLE } from "@/lib/dfs-roster";
import { filterCustomerVisibleSlates, getSlateDisplayStatus, platformLabel } from "@/lib/dfs-slate-status";
import {
  formatKickoffEt,
  SCHEDULE_INTEL_NOTE,
  scheduleMatchupLabel,
  upcomingScheduleEvents,
} from "@/lib/upcoming-schedule";
import { AppShell } from "@/components/app-shell";

const SPORTS = ["MLB", "NFL", "NBA", "NHL", "NCAAF", "NCAAB"] as const;
const PLATFORMS = ["draftkings", "fanduel"] as const;
const STRATEGIES = ["balanced", "cash", "gpp", "aggressive"] as const;

type MainTab = "pool" | "saved" | "built";
type SubTab = "all" | "excluded" | "liked";
type SortField = "salary" | "fppg" | "optimal";
type SortDir = "desc" | "asc";

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

/** Solver accepts DFS player ids OR player names (case-insensitive). */
function solverPlayerKeys(
  names: string[],
  dfsPool: DFSSlatePlayer[],
): string[] {
  const keys = new Set<string>();
  for (const name of names) {
    const trimmed = (name || "").trim();
    if (!trimmed) continue;
    keys.add(trimmed);
    const dfs = matchDFS({ name: trimmed }, dfsPool);
    if (dfs?.player_id) keys.add(String(dfs.player_id));
  }
  return Array.from(keys);
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

function formatFetchedAt(ms: number | null | undefined): string {
  if (!ms || !Number.isFinite(ms)) return "";
  const ago = Math.max(0, Date.now() - ms);
  if (ago < 60_000) return "Just now";
  if (ago < 3_600_000) return `${Math.round(ago / 60_000)} min ago`;
  return new Date(ms).toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
}

export default function OptimizerPage() {
  const router = useRouter();
  const ws = useWorkspace();
  const sport = ws.sport;
  const platform = ws.platform;
  const resolvedSlateId = ws.slateId;
  const roster = useMemo(() => getRoster(sport, platform), [sport, platform]);
  const regenFromRef = useRef<string[][] | null>(null);
  const [historySaved, setHistorySaved] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [uniqueLineupError, setUniqueLineupError] = useState<string | null>(null);

  // ── State ──
  const [bookmakerSource, setBookmakerSource] = useState<string>("Best Available");
  const [strategy, setStrategy] = useState<string>("balanced");
  const strategyRef = useRef(strategy);
  strategyRef.current = strategy;
  const [lineupCount, setLineupCount] = useState(4);
  const { events, loading: sgoLoading, lastFetch } = useEvents(sport);

  const [canonicalPool, setCanonicalPool] = useState<Record<string, CanonicalPlayer>>({});
  const [optPctStatus, setOptPctStatus] = useState<string>("NOT_RUN");
  const [optPctMap, setOptPctMap] = useState<Record<string, number>>({});

  const [excludedGameIds, setExcludedGameIds] = useState<Set<string>>(new Set());

  const [playerSearch, setPlayerSearch] = useState("");
  const [posFilter, setPosFilter] = useState("ALL");
  const [sortField, setSortField] = useState<SortField>("salary");
  const [sortDir, setSortDir] = useState<SortDir>("desc");
  const [mainTab, setMainTab] = useState<MainTab>("pool");
  const [subTab, setSubTab] = useState<SubTab>("all");

  const [lineups, setLineups] = useState<LineupResponse[]>([]);
  const [slates, setSlates] = useState<DFSSlateSummary[]>([]);
  const [slatesLoading, setSlatesLoading] = useState(true);
  const [hasStaleSlates, setHasStaleSlates] = useState(false);
  const [maxHittersPerTeam, setMaxHittersPerTeam] = useState<number | undefined>();
  const [stackSize, setStackSize] = useState<number | undefined>();
  const [pitcherConflict, setPitcherConflict] = useState<boolean>(true);
  const [minSalaryOverride, setMinSalaryOverride] = useState<number | undefined>();
  const [maxSalaryOverride, setMaxSalaryOverride] = useState<number | undefined>();
  const [globalMaxExposure, setGlobalMaxExposure] = useState<number | undefined>();
  const [savedNote, setSavedNote] = useState(false);
  const [lastGenMeta, setLastGenMeta] = useState<{ sport: string; platform: string; strategy: string; gameCount: number; generationWarning?: string | null } | null>(null);
  const [selectedLineupIndex, setSelectedLineupIndex] = useState(0);
  const [projPool, setProjPool] = useState<Record<string, { projected_fp: number; salary: number; position: string; team: string; opponent: string; projection_source: string }>>({});
  const handoffApplied = useRef(false);

  useEffect(() => {
    if (handoffApplied.current || typeof window === "undefined") return;
    const handoff = parseOptimizerHandoff(window.location.search);
    if (!handoff.sport && !handoff.platform && !handoff.slateId && !handoff.lockedNames.length) return;
    handoffApplied.current = true;
    if (handoff.sport) ws.setSport(handoff.sport);
    if (handoff.platform) ws.setPlatform(handoff.platform);
    if (handoff.slateId) ws.setSlateId(handoff.slateId);
    if (handoff.lockedNames.length) ws.setLockedIds(handoff.lockedNames);
  }, [ws]);

  // ── DFS slate ──
  useEffect(() => {
    let cancelled = false;
    async function load() {
      setSlatesLoading(true);
      try {
        const res = await fetchDFSSlates(platform, sport);
        const pub = filterCustomerVisibleSlates(res?.data ?? [], sport);
        if (!cancelled) {
          setSlates(pub);
          const urlSlate = typeof window !== "undefined"
            ? Number(new URLSearchParams(window.location.search).get("slate"))
            : NaN;
          const urlOk = Number.isFinite(urlSlate) && pub.some((s: any) => s.id === urlSlate);
          const existingOk = ws.slateId != null && pub.some((s: any) => s.id === ws.slateId);
          if (urlOk) {
            ws.setSlateId(urlSlate);
          } else if (!existingOk) {
            const main = pub.find((s: any) => s.slate_name.toLowerCase().includes("main"));
            const defaultId = main?.id ?? (pub.length > 0 ? pub[0].id : null);
            ws.setSlateId(defaultId);
          }
          setHasStaleSlates((res?.data ?? []).some((s: any) => s.freshness === "STALE" || s.is_current === false));
        }
      } catch { if (!cancelled) { setSlates([]); ws.setSlateId(null); setHasStaleSlates(false); } }
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
            const nm = normName(p.name);
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

  // Optimal% — poll cached background simulation result from GET /api/optimal-pct.
  // Interval is armed synchronously so an in-flight fetch cannot drop the poll chain.
  useEffect(() => {
    if (!resolvedSlateId) { setOptPctStatus("NOT_RUN"); setOptPctMap({}); return; }
    let cancelled = false;
    let intervalId: ReturnType<typeof setInterval> | null = null;
    const POLL_MS = 5000;
    const PENDING = new Set(["QUEUED", "RUNNING"]);
    async function load() {
      try {
        const res = await fetchOptimalPct(resolvedSlateId!, platform, sport);
        if (cancelled) return;
        const mapped = mapOptimalPctResponse(res);
        setOptPctStatus(mapped.status);
        setOptPctMap(mapped.map);
        if (!PENDING.has(mapped.status) && intervalId) {
          clearInterval(intervalId);
          intervalId = null;
        }
      } catch {
        if (!cancelled) {
          setOptPctStatus("NOT_RUN");
          setOptPctMap({});
          if (intervalId) {
            clearInterval(intervalId);
            intervalId = null;
          }
        }
      }
    }
    load();
    intervalId = setInterval(load, POLL_MS);
    return () => { cancelled = true; if (intervalId) clearInterval(intervalId); };
  }, [resolvedSlateId, platform, sport]);

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
    if (subTab === "excluded") pool = players.filter((p) => ws.excludedIds.includes(p.name));
    else if (subTab === "liked") pool = players.filter((p) => ws.likedIds.includes(p.name));
    else pool = players.filter((p) => !ws.excludedIds.includes(p.name));
    pool = pool.filter((p) => {
      if (posFilter !== "ALL") {
        let eligible = normalizePosForFilter(p.position);
        const dfs = matchDFS({ name: p.name, team_id: p.team_id, position: p.position }, dfsPlayers);
        if (dfs) {
          const dfsEligible = (dfs.eligible_positions || [dfs.position]).flatMap((ep) => normalizePosForFilter(ep));
          eligible = Array.from(new Set([...eligible, ...dfsEligible]));
        }
        if (!eligible.includes(posFilter)) {
          if (!((posFilter === "DST" || posFilter === "DEF") && eligible.some((p) => p === "DST" || p === "DEF"))) {
            return false;
          }
        }
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
      const poolA = projPool[normName(a.name)];
      const poolB = projPool[normName(b.name)];
      const fpA = poolA?.projected_fp != null && poolA?.projection_source !== "UNAVAILABLE" ? poolA.projected_fp : null;
      const fpB = poolB?.projected_fp != null && poolB?.projection_source !== "UNAVAILABLE" ? poolB.projected_fp : null;
      if (sortField === "salary") {
        const salA = dfsA?.salary ?? 0;
        const salB = dfsB?.salary ?? 0;
        return sortDir === "desc" ? salB - salA : salA - salB;
      }
      if (sortField === "optimal") {
        const optA = lookupOptimalPct(optPctMap, [a.name, dfsA?.name, dfsA?.player_id]);
        const optB = lookupOptimalPct(optPctMap, [b.name, dfsB?.name, dfsB?.player_id]);
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
  }, [players, subTab, ws.excludedIds, ws.likedIds, posFilter, playerSearch, filteredEvents, dfsPlayers, projPool, optPctMap, sortField, sortDir]);

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

    // Find SGO events where BOTH home AND away teams are in this slate.
    // Using OR would pull in cross-over events (e.g. SF@ATL when SF is
    // in the slate but ATL is not), contaminating the SGO player pool.
    const slateEvents = events.filter((e) => {
      const ha = (e.home_team?.abbreviation || "").toUpperCase();
      const aa = (e.away_team?.abbreviation || "").toUpperCase();
      return slateTeamAbbrs.has(ha) && slateTeamAbbrs.has(aa);
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

  const canGenerate = !slatesLoading && resolvedSlateId != null && dfsPlayers.length > 0 && slateIntegrity.healthy && Boolean(roster) && (roster?.salaryCap != null || maxSalaryOverride != null);

  // ── Game toggles ──
  const selectAllGames = useCallback(() => setExcludedGameIds(new Set()), []);
  const removeAllGames = useCallback(() => setExcludedGameIds(new Set(events.map((e) => e.id))), [events]);
  const toggleGame = useCallback((id: string) => {
    setExcludedGameIds((prev) => { const n = new Set(prev); if (n.has(id)) n.delete(id); else n.add(id); return n; });
  }, []);

  // ── Player actions ──
  const toggleLike = useCallback((name: string) => {
    ws.toggleLike(name);
  }, [ws]);
  const toggleExclude = useCallback((name: string) => {
    ws.toggleExclude(name);
  }, [ws]);
  const toggleLock = useCallback((name: string) => {
    ws.toggleLock(name);
  }, [ws]);
  const excludeAll = useCallback(() => {
    ws.setExcludedIds(players.map((p) => p.name));
    ws.setLockedIds([]);
  }, [players, ws]);

  // ── Optimize ──
  const optimizeMutation = useMutation({
    mutationFn: (vars?: { strategy?: string; num_lineups?: number }) => {
      if (resolvedSlateId == null) throw new Error(`No ${platform === "draftkings" ? "DraftKings" : "FanDuel"} contest salary data.`);
      const appliedStrategy = vars?.strategy ?? strategyRef.current;
      strategyRef.current = appliedStrategy;
      const numLineups = requestedNumLineups(vars?.num_lineups ?? lineupCount);
      const setting: any = {
        sport, platform, strategy: appliedStrategy, num_lineups: numLineups,
        locked_player_ids: solverPlayerKeys(ws.lockedIds, dfsPlayers),
        excluded_player_ids: solverPlayerKeys(ws.excludedIds, dfsPlayers),
      };
      if (maxHittersPerTeam != null) setting.max_hitters_per_team = maxHittersPerTeam;
      if (stackSize != null) setting.stack_size = stackSize;
      if (!pitcherConflict) setting.pitcher_conflict = false;
      if (minSalaryOverride != null) setting.min_salary = minSalaryOverride;
      if (maxSalaryOverride != null) setting.max_salary = maxSalaryOverride;
      if (globalMaxExposure != null) setting.max_exposure_pct = globalMaxExposure;
      // My Proj overrides — send player name + custom projection to the solver
      const overrides = Object.entries(ws.projOverrides)
        .map(([name, proj]) => ({ name, projected_fp: proj }))
        .filter((x) => x.name && x.projected_fp != null && !Number.isNaN(x.projected_fp));
      if (overrides.length > 0) setting.projection_overrides = overrides;
      if (roster?.minUniqueDefault) setting.min_uniqueness = roster.minUniqueDefault;
      const regen = regenFromRef.current;
      if (regen && regen.length > 0) setting.regenerate_from_ids = regen;
      return runOptimizer(resolvedSlateId, setting);
    },
    onSuccess: (res: unknown) => {
      regenFromRef.current = null;
      setUniqueLineupError(null);
      setSaveError(null);
      try {
        if (!res || typeof res !== "object") { setLineups([]); return; }
        const r = res as Record<string, unknown>;
        const data = r?.data;
        const extracted = extractOptimizerLineups(res);
        setLineups(extracted as LineupResponse[]);
        if (data && typeof data === "object" && !Array.isArray(data)) {
          setHistorySaved(Boolean((data as Record<string, unknown>)?.history_saved));
          setSavedNote(Boolean((data as Record<string, unknown>)?.history_saved));
        }

        // Store projection pool (keyed by name for frontend matching)
        const pool = (data && typeof data === "object" && !Array.isArray(data))
          ? (data as Record<string, unknown>)?.pool
          : undefined;
        if (Array.isArray(pool)) {
          const poolMap: Record<string, any> = {};
          for (const p of pool) {
            const nm = (p?.name || "").toLowerCase().trim();
            if (nm) poolMap[nm] = p;
          }
          setProjPool(poolMap);
        } else { setProjPool({}); }
        const warn = optimizerGenerationNote(res, extracted.length);
        setLastGenMeta({
          sport, platform, strategy: strategyRef.current,
          gameCount: dfsPlayers.length > 0 ? (new Set(dfsPlayers.map(p => p.team)).size / 2) : 0,
          generationWarning: warn,
        });
      } catch { setLineups([]); setProjPool({}); setLastGenMeta({ sport, platform, strategy: strategyRef.current, gameCount: 0 }); }
      setMainTab("built");
      setSelectedLineupIndex(0);
    },
    onError: (err) => {
      const msg = err instanceof Error ? err.message : "";
      if (msg.includes("No additional unique lineup")) {
        setUniqueLineupError(UNIQUE_LINEUP_UNAVAILABLE);
      } else {
        setUniqueLineupError(null);
        setLineups([]);
        setLastGenMeta(null);
      }
      setMainTab("built");
    },
  });

  const applyStrategy = useCallback((next: string) => {
    if (next === strategyRef.current) return;
    setStrategy(next);
    strategyRef.current = next;
    setUniqueLineupError(null);
    const stale = lineups.length > 0;
    setLineups([]);
    setLastGenMeta(null);
    setSelectedLineupIndex(0);
    if (stale && canGenerate) {
      optimizeMutation.mutate({ strategy: next, num_lineups: lineupCount });
    }
  }, [lineups.length, canGenerate, optimizeMutation, lineupCount]);
  const clearLineups = useCallback(() => { setLineups([]); setLastGenMeta(null); setSavedNote(false); setHistorySaved(false); setSaveError(null); setUniqueLineupError(null); }, []);
  const regenerate = useCallback(() => {
    regenFromRef.current = lineups.map((lu) =>
      ((lu.players as any[]) || []).map((p) => String(p.id || p.name || "")).filter(Boolean)
    );
    setUniqueLineupError(null);
    optimizeMutation.mutate({ strategy, num_lineups: lineupCount });
  }, [optimizeMutation, lineups, strategy, lineupCount]);
  const markSaved = useCallback(async () => {
    if (historySaved || savedNote) return;
    if (!lineups.length) return;
    setSaveError(null);
    try {
      const res = await saveLineupHistory({
        sport,
        platform,
        slate_id: resolvedSlateId,
        strategy,
        lineups,
      });
      if (!res?.data?.saved) {
        setHistorySaved(false);
        setSavedNote(false);
        setSaveError("Could not save lineup.");
        return;
      }
      setHistorySaved(true);
      setSavedNote(true);
    } catch (err) {
      setHistorySaved(false);
      setSavedNote(false);
      setSaveError(err instanceof Error ? err.message : "Could not save lineup.");
    }
  }, [historySaved, savedNote, lineups, sport, platform, resolvedSlateId, strategy]);

  const slots = roster?.slots ?? [];
  const lockedPlayers = players.filter((p) => ws.lockedIds.includes(p.name));

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
        if (roster && slotEligible(lp.position || (dfs?.position ?? ""), slots[i], roster)) {
          rows[i] = { slot: slots[i], name: lp.name, salary: dfs?.salary || 0, proj: 0, opponent: opp, team: evt ? resolveTeamName(lp.team_id, evt) : "" };
          used.add(i);
          break;
        }
      }
    }
    return rows;
  }, [selectedSlotPlayers, slots, lockedPlayers, filteredEvents, dfsPlayers, roster]);

  // Right-side metrics
  const builderMetrics = useMemo(() => {
    if (!selectedLineup) {
      const cap = roster?.salaryCap ?? 0;
      const lockedSal = lockedPlayers.reduce((s, lp) => {
        const dfs = matchDFS({ name: lp.name, team_id: lp.team_id, position: lp.position }, dfsPlayers);
        return s + (dfs?.salary || 0);
      }, 0);
      return { cap, remaining: cap - lockedSal, projFP: 0, value: "—", ownership: "N/A" };
    }
    const cap = roster?.salaryCap ?? selectedLineup.total_salary ?? 0;
    const rem = (selectedLineup as any).remaining_salary ?? (cap - selectedLineup.total_salary);
    const fp = selectedLineup.projected_score;
    const val = selectedLineup.total_salary > 0 ? (fp / (selectedLineup.total_salary / 1000)).toFixed(2) : "—";
    return { cap, remaining: rem, projFP: fp, value: val, ownership: "N/A" };
  }, [selectedLineup, roster, lockedPlayers, dfsPlayers]);

  const remainingSlots = rosterRows.filter((r) => !r.name).length;
  const avgRemaining = averageRemainingPerPlayer(builderMetrics.remaining, remainingSlots);
  const scheduleEvents = useMemo(() => upcomingScheduleEvents(events), [events]);
  const selectedSlate = useMemo(
    () => slates.find((s) => s.id === resolvedSlateId) ?? null,
    [slates, resolvedSlateId],
  );
  const filledSlots = rosterRows.filter((r) => Boolean(r.name)).length;
  const capUsed = Math.max(0, (builderMetrics.cap || 0) - (builderMetrics.remaining || 0));
  const capPct = builderMetrics.cap > 0 ? Math.min(120, (capUsed / builderMetrics.cap) * 100) : 0;
  const slateStatusLabel = selectedSlate
    ? getSlateDisplayStatus(selectedSlate)
    : resolvedSlateId == null
      ? "NONE"
      : "LOADED";
  const engineLabel = canGenerate ? "CP-SAT READY" : resolvedSlateId == null ? "CP-SAT STANDBY" : "CP-SAT BLOCKED";
  const maxSbProj = useMemo(() => {
    let m = 0;
    for (const p of filteredPlayers) {
      const entry = projPool[normName(p.name)];
      if (entry?.projected_fp != null && entry.projection_source !== "UNAVAILABLE") {
        m = Math.max(m, Number(entry.projected_fp) || 0);
      }
    }
    return m;
  }, [filteredPlayers, projPool]);
  const avgPerSlot = roster && roster.salaryCap != null && roster.slots.length
    ? Math.round(roster.salaryCap / roster.slots.length)
    : null;
  const gameCount = dfsPlayers.length > 0 ? Math.round(new Set(dfsPlayers.map((p) => p.team)).size / 2) : 0;
  const projectionsUnavailable = resolvedSlateId != null && Object.values(projPool).length > 0
    && !Object.values(projPool).some((e) => e.projected_fp != null && e.projection_source !== "UNAVAILABLE");
  const rosterPct = slots.length ? Math.round((filledSlots / slots.length) * 100) : null;
  const dataFresh = lastFetch && Number.isFinite(lastFetch) && Date.now() - lastFetch < 60_000;

  return (
    <AppShell atmosphere="app">
    <div className="sbme-opt">
      <header className="sbme-opt-head">
        <div className="sbme-opt-brand">
          <p className="sbme-opt-kicker">SPORTBOOK ME <span>DFS.AI</span></p>
          <h1>OPTIMIZER</h1>
          <p className="sbme-opt-head-copy">
            {sport} command center · {platformLabel(platform)} roster rules · CP-SAT engine.
            {sgoLoading ? " Loading SportsGameOdds events…" : ` ${events.length} loaded events.`}
            {lastFetch ? ` Events fetched ${formatFetchedAt(lastFetch)}.` : ""}
          </p>
        </div>
        <div className="sbme-opt-strip" aria-label="Optimizer status">
          <span className="sbme-opt-chip sbme-opt-chip--gold">{sport}</span>
          <span className="sbme-opt-chip">{platformLabel(platform)}</span>
          <span className={`sbme-opt-chip${canGenerate ? " sbme-opt-chip--live sbme-opt-chip--pulse" : ""}`}>{engineLabel}</span>
          <span className={`sbme-opt-chip${resolvedSlateId == null ? " sbme-opt-chip--warn" : " sbme-opt-chip--gold"}`}>
            {resolvedSlateId == null ? "NO ACTIVE DFS SLATE" : `SLATE ${slateStatusLabel}`}
          </span>
          <span className="sbme-opt-chip">PLAYER POOL {dfsPlayers.length}</span>
          {roster?.salaryCap != null && (
            <span className="sbme-opt-chip sbme-opt-chip--gold">SALARY CAP ${roster.salaryCap.toLocaleString()}</span>
          )}
          <span className={`sbme-opt-chip${dataFresh ? " sbme-opt-chip--live sbme-opt-chip--pulse" : lastFetch ? " sbme-opt-chip--info" : ""}`}>
            {dataFresh ? "LIVE DATA" : lastFetch ? `DATA ${formatFetchedAt(lastFetch)}` : "DATA —"}
          </span>
        </div>
      </header>

      <div className="sbme-opt-modes">
        <div className="sbme-opt-mode">
          <div className="sbme-opt-mode-label">Sport</div>
          <div className="sbme-opt-tabs" role="tablist" aria-label="Sport">
            {SPORTS.map((s) => (
              <button key={s} type="button" role="tab" aria-selected={sport === s} className={`sbme-opt-tab${sport === s ? " is-on" : ""}`} onClick={() => ws.setSport(s)}>{s}</button>
            ))}
          </div>
        </div>
        <div className="sbme-opt-mode">
          <div className="sbme-opt-mode-label">Operating mode</div>
          <div className="sbme-opt-plat" role="group" aria-label="DFS platform">
            {PLATFORMS.map((p) => (
              <button key={p} type="button" aria-pressed={platform === p} className={platform === p ? "is-on" : ""} onClick={() => { ws.setPlatform(p); setLineups([]); setLastGenMeta(null); }}>
                {p === "draftkings" ? "DraftKings" : "FanDuel"}
              </button>
            ))}
          </div>
        </div>
        <div className="sbme-opt-mode">
          <div className="sbme-opt-mode-label">Slate</div>
          <Selector label="Slate" value={resolvedSlateId == null ? "" : String(resolvedSlateId)} options={slates.length ? slates.map((s) => String(s.id)) : [""]} onChange={(v) => ws.setSlateId(v ? Number(v) : null)} format={(v) => { if (!v) return "No DFS slate currently available"; const s = slates.find((x) => String(x.id) === v); if (!s) return v; const t = s.start_time ? new Date(s.start_time).toLocaleString([], { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" }) : ""; return `${s.slate_name}${t ? ` · ${t}` : ""} (${s.player_count})`; }} />
          <div style={{ marginTop: 8 }}>
            <Selector label="Bookmaker" value={bookmakerSource} options={["Best Available", "Book Consensus", ...bookmakers]} onChange={setBookmakerSource} format={(v) => (v === "Best Available" || v === "Book Consensus" ? v : formatBookmakerName(v))} />
          </div>
          <div style={{ marginTop: 8 }}>
            <Selector label="Strategy" value={strategy} options={[...STRATEGIES]} onChange={applyStrategy} />
          </div>
        </div>
      </div>

      <div className="sbme-opt-metrics" aria-label="Intelligence metrics">
        <div className="sbme-opt-metric"><b>{roster?.salaryCap != null ? `$${roster.salaryCap.toLocaleString()}` : "—"}</b><span>Salary cap</span></div>
        <div className="sbme-opt-metric"><b>{avgPerSlot != null ? `$${avgPerSlot.toLocaleString()}` : "—"}</b><span>Avg / slot</span></div>
        <div className="sbme-opt-metric"><b>{slots.length || "—"}</b><span>Roster size</span></div>
        <div className="sbme-opt-metric"><b>{dfsPlayers.length || "—"}</b><span>Player pool</span></div>
        <div className="sbme-opt-metric"><b>{resolvedSlateId == null ? "NONE" : slateStatusLabel}</b><span>Slate status</span></div>
        <div className="sbme-opt-metric"><b>{selectedSlate?.data_source || "—"}</b><span>Data source</span></div>
      </div>

      <section className="sbme-opt-schedule" aria-label="Schedule intelligence">
        {resolvedSlateId == null && (
          <div className="sbme-opt-banner" role="status">
            <h3>NO ACTIVE DFS SLATE</h3>
            <p>
              No DFS slate currently available. No valid {platform === "draftkings" ? "DraftKings" : "FanDuel"} slate is currently available for this sport.
              Upcoming games are schedule intelligence only. Optimization will activate when a valid DFS slate is available.
            </p>
          </div>
        )}
        {resolvedSlateId != null && (
          <div className="sbme-opt-rail-wrap sbme-opt-rail-wrap--slate">
            <div className="sbme-opt-rail-head">
              <h2>SLATE GAMES</h2>
              <div style={{ display: "flex", gap: 6 }}>
                <button type="button" className="sbme-opt-ghost" onClick={selectAllGames}>SELECT ALL</button>
                <button type="button" className="sbme-opt-ghost" onClick={removeAllGames} style={{ color: "#ef4444" }}>REMOVE ALL</button>
              </div>
            </div>
            <div className="sbme-opt-rail">
              {filteredEvents.length === 0 ? (
                <span style={{ fontSize: 11, color: "#64748b", padding: "8px 0" }}>No games attached to this slate yet. SGO schedule alone is not a slate.</span>
              ) : filteredEvents.slice(0, 20).map((e) => {
                const excluded = excludedGameIds.has(e.id);
                return (
                  <button type="button" key={e.id} onClick={() => toggleGame(e.id)} className={`sbme-opt-game${excluded ? " is-off" : ""}`}>
                    {e.away_team?.abbreviation || "AWY"} @ {e.home_team?.abbreviation || "HOM"}
                    <time>{e.start_time ? new Date(e.start_time).toLocaleString([], { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" }) : ""}</time>
                  </button>
                );
              })}
            </div>
          </div>
        )}
        <div className="sbme-opt-rail-wrap sbme-opt-rail-wrap--sched">
          <div className="sbme-opt-rail-head">
            <h2>UPCOMING SCHEDULE</h2>
            <p className="sbme-opt-rail-note">{SCHEDULE_INTEL_NOTE}</p>
          </div>
          <ScheduleChips events={scheduleEvents} />
        </div>
      </section>

      <div className="sbme-opt-workspace">
        <section className="sbme-opt-pool" aria-label="Player pool">
          <div style={{ display: "flex", borderBottom: "1px solid #1e293b" }}>
            <TabChip label="PLAYER POOL" active={mainTab === "pool"} onClick={() => setMainTab("pool")} />
            <TabChip label="SAVED LINEUPS" active={mainTab === "saved"} onClick={() => { setMainTab("saved"); router.push("/lineups"); }} />
            <TabChip label={`BUILT LINEUPS${lineups.length ? ` (${lineups.length})` : ""}`} active={mainTab === "built"} onClick={() => setMainTab("built")} />
          </div>

          {mainTab === "pool" && (
            <>
              <div className="sbme-opt-toolbar">
                <div style={{ display: "flex", gap: 4, flexWrap: "wrap" }}>
                  <SubTabChip label="ALL PLAYERS" active={subTab === "all"} onClick={() => setSubTab("all")} />
                  <SubTabChip label={`EXCLUDED${ws.excludedIds.length ? ` (${ws.excludedIds.length})` : ""}`} active={subTab === "excluded"} onClick={() => setSubTab("excluded")} />
                  <SubTabChip label={`LIKED${ws.likedIds.length ? ` (${ws.likedIds.length})` : ""}`} active={subTab === "liked"} onClick={() => setSubTab("liked")} />
                </div>
                <button type="button" className="sbme-opt-ghost" onClick={excludeAll} style={{ color: "#ef4444" }}>Exclude All</button>
                <span style={{ fontSize: 11, color: "#64748b" }}>{filteredPlayers.length} players</span>
              </div>
              <div className="sbme-opt-toolbar">
                {["ALL", ...(roster?.filterPositions ?? [])].map((pos) => (
                  <button key={pos} type="button" onClick={() => setPosFilter(pos)} className={`sbme-opt-tab${posFilter === pos ? " is-on" : ""}`}>{pos}</button>
                ))}
                <div style={{ display: "flex", alignItems: "center", gap: 4 }}>
                  <ArrowUpDown size={12} style={{ color: "#64748b" }} />
                  <select
                    value={sortField + "|" + sortDir}
                    onChange={(e) => {
                      const [f, d] = e.target.value.split("|") as [SortField, SortDir];
                      setSortField(f); setSortDir(d);
                    }}
                    className="sbme-opt-select"
                    style={{ width: "auto" }}
                    aria-label="Sort player pool"
                  >
                    <option value="salary|desc">Salary — High to Low</option>
                    <option value="salary|asc">Salary — Low to High</option>
                    <option value="fppg|desc">SB Projection — High to Low</option>
                    <option value="fppg|asc">SB Projection — Low to High</option>
                    <option value="optimal|desc">Optimal% — High to Low</option>
                    <option value="optimal|asc">Optimal% — Low to High</option>
                  </select>
                </div>
                <label className="sbme-opt-search">
                  <Search size={14} style={{ position: "absolute", left: 10, top: "50%", transform: "translateY(-50%)", color: "#64748b" }} />
                  <input type="search" placeholder="Search players..." value={playerSearch} onChange={(e) => setPlayerSearch(e.target.value)} aria-label="Search players" />
                </label>
              </div>
              <div className="sbme-opt-table-wrap">
                {filteredPlayers.length === 0 ? (
                  <div className="sbme-opt-empty" style={{ margin: 16 }}>
                    <h3>NO PLAYERS AVAILABLE</h3>
                    <p>{resolvedSlateId == null ? "A valid DFS slate is required before the player pool can load." : "No players match the current filters."}</p>
                  </div>
                ) : (
                  <table className="sbme-opt-table">
                    <thead>
                      <tr>
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
                        const isLiked = ws.likedIds.includes(p.name);
                        const isExcluded = ws.excludedIds.includes(p.name);
                        const isLocked = ws.lockedIds.includes(p.name);
                        const startT = evt?.start_time ? new Date(evt.start_time).toLocaleString([], { hour: "numeric", minute: "2-digit" }) : "";
                        const poolEntry = projPool[normName(p.name)];
                        const sbProj = poolEntry?.projected_fp != null && poolEntry?.projection_source !== "UNAVAILABLE" ? poolEntry.projected_fp : null;
                        const salary = dfs?.salary ?? 0;
                        const effectiveProj = ws.projOverrides[p.name] != null ? ws.projOverrides[p.name] : sbProj;
                        const value = salary > 0 && effectiveProj != null ? (effectiveProj / (salary / 1000)).toFixed(2) : "—";
                        const canon = canonicalPool[normName(p.name)];
                        const ownPct = canon?.sbme_ownership_pct ?? null;
                        const leverage = canon?.leverage ?? null;
                        const ceiling = canon?.ceiling ?? null;
                        const floor = canon?.floor ?? null;
                        const optPct = lookupOptimalPct(optPctMap, [p.name, dfs?.name, dfs?.player_id, canon?.id, canon?.dfs_player_id]);
                        const rowClass = [isLocked ? "is-locked" : "", isLiked ? "is-liked" : "", isExcluded ? "is-excluded" : ""].filter(Boolean).join(" ");
                        return (
                          <tr key={p.player_id} className={rowClass || undefined}>
                            <Td>{teamName}</Td>
                            <Td style={{ color: "#64748b" }}>{opp || "—"}</Td>
                            <Td style={{ color: "#64748b", fontSize: 10 }}>{startT || "—"}</Td>
                            <Td style={{ color: "#c9a84c", fontWeight: 700, textTransform: "uppercase", fontSize: 10 }}>{dfs?.position || p.position || "—"}</Td>
                            <Td>
                              <button type="button" onClick={() => toggleLike(p.name)} aria-label={isLiked ? "Unlike player" : "Like player"} style={{ background: "none", border: "none", cursor: "pointer", padding: 0 }}>
                                <Heart size={14} color={isLiked ? "#c9a84c" : "#334155"} fill={isLiked ? "#c9a84c" : "none"} />
                              </button>
                            </Td>
                            <Td style={{ color: "#f0f6fc", fontWeight: 600 }}>{p.name}</Td>
                            <Td style={{ color: dfs ? "#c9a84c" : "#64748b", fontWeight: dfs ? 700 : 400 }}>{dfs ? `$${dfs.salary.toLocaleString()}` : "—"}</Td>
                            <Td style={{ color: dfs?.fppg != null ? "#94a3b8" : "#64748b", fontWeight: dfs?.fppg != null ? 600 : 400 }}>{dfs?.fppg != null ? dfs.fppg.toFixed(1) : "N/A"}</Td>
                            <Td style={{ color: sbProj != null ? "#c9a84c" : "#64748b", fontWeight: sbProj != null ? 700 : 400 }}>
                              {sbProj != null ? sbProj.toFixed(1) : "N/A"}
                              {sbProj != null && maxSbProj > 0 && (
                                <span className="sbme-opt-bar" aria-hidden><span style={{ width: `${Math.max(6, Math.round((sbProj / maxSbProj) * 100))}%` }} /></span>
                              )}
                            </Td>
                            <Td>
                              <input type="number" step="0.1" value={ws.projOverrides[p.name] ?? sbProj ?? ""} placeholder={sbProj != null ? "" : "—"} onChange={(e) => ws.setProjOverride(p.name, Number(e.target.value))} aria-label={`My projection for ${p.name}`} style={{ width: 56, padding: "4px 6px", borderRadius: 6, fontSize: 11, background: "#1a1f33", border: "1px solid #1e293b", color: "#f0f6fc", outline: "none" }} />
                            </Td>
                            <Td style={{ color: value !== "—" ? "#c9a84c" : "#64748b", fontWeight: value !== "—" ? 700 : 400 }}>{value}</Td>
                            <Td style={{ color: ownPct != null ? "#94a3b8" : "#64748b" }}>{ownPct != null ? `${ownPct.toFixed(1)}%` : "N/A"}</Td>
                            <Td style={{ color: leverage != null ? (leverage > 0 ? "#4ade80" : "#f87171") : "#64748b" }}>{leverage != null ? leverage.toFixed(1) : "N/A"}</Td>
                            <Td style={{ color: optPct != null ? "#c9a84c" : "#64748b", fontWeight: optPct != null ? 700 : 400 }}>{formatOptPctCell(optPct, optPctStatus)}</Td>
                            <Td style={{ color: ceiling != null ? "#94a3b8" : "#64748b" }}>{ceiling != null ? ceiling.toFixed(1) : "N/A"}</Td>
                            <Td style={{ color: floor != null ? "#94a3b8" : "#64748b" }}>{floor != null ? floor.toFixed(1) : "N/A"}</Td>
                            <Td style={{ color: mCount ? "#c9a84c" : "#64748b" }}>{mCount || "—"}</Td>
                            <Td>
                              <div style={{ display: "flex", gap: 4 }}>
                                <IconBtn icon={<Lock size={12} />} active={isLocked} title="Lock player" onClick={() => toggleLock(p.name)} />
                                <IconBtn icon={<Ban size={12} />} active={isExcluded} title="Exclude player" onClick={() => toggleExclude(p.name)} />
                              </div>
                              <LastFive player={{ name: p.name, player_id: p.player_id, team: teamName, sport }} platform={platform} />
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
              : optimizeMutation.isError && !uniqueLineupError ? <Center><p style={{ color: "#ef4444", fontWeight: 700 }}>{optimizeMutation.error instanceof Error ? optimizeMutation.error.message : "Optimization failed"}</p></Center>
              : lineups.length === 0 && !uniqueLineupError ? (
                <div className="sbme-opt-empty">
                  <h3>NO LINEUP GENERATED</h3>
                  <p>No lineups yet. Click BUILD OPTIMAL LINEUP to generate from the current slate and locks.</p>
                </div>
              )
              : uniqueLineupError && lineups.length === 0 ? <Center><p style={{ color: "#f87171", fontWeight: 700 }}>{uniqueLineupError}</p></Center>
              : (
                <>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16, flexWrap: "wrap", gap: 8 }}>
                    <h2 style={{ fontSize: 16, fontWeight: 800, color: "#c9a84c", margin: 0 }}>Built Lineups ({lineups.length})</h2>
                    <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
                      <MiniBtn icon={<Save size={13} />} label={savedNote || historySaved ? "Saved ✓" : "Save Lineup"} onClick={() => { void markSaved(); }} />
                      <MiniBtn icon={<RefreshCw size={13} />} label="Regenerate" onClick={regenerate} disabled={optimizeMutation.isPending} />
                      <MiniBtn icon={<BarChart3 size={13} />} label="Simulate" onClick={() => { ws.setPendingLineups(lineups); router.push("/sims"); }} />
                      <MiniBtn icon={<Download size={13} />} label="Export" onClick={() => exportLineups(lineups, lastGenMeta)} />
                      <MiniBtn icon={<Trash2 size={13} />} label="Clear" onClick={clearLineups} />
                      <MiniBtn icon={<List size={13} />} label="View Saved" onClick={() => router.push("/lineups")} />
                    </div>
                  </div>
                  {uniqueLineupError && <p style={{ fontSize: 12, color: "#f87171", marginBottom: 12 }}>{uniqueLineupError}</p>}
                  {saveError && <p style={{ fontSize: 12, color: "#f87171", marginBottom: 12 }}>{saveError}</p>}
                  {lastGenMeta?.generationWarning && <p style={{ fontSize: 12, color: "#f87171", marginBottom: 12 }}>{lastGenMeta.generationWarning}</p>}
                  {lastGenMeta && <p style={{ fontSize: 11, color: "#64748b", marginBottom: 12 }}>Platform: {lastGenMeta.platform === "draftkings" ? "DraftKings" : "FanDuel"} · Strategy: {lastGenMeta.strategy} · {lastGenMeta.gameCount} games</p>}
                  {lineups.map((l, i) => <LineupCard key={i} index={i} lineup={l} platform={lastGenMeta?.platform || platform} />)}
                </>
              )}
            </div>
          )}

          {mainTab === "saved" && (
            <div style={{ flex: 1, padding: 20, textAlign: "center" }}><p style={{ color: "#64748b", marginTop: 40 }}>Redirecting to saved /lineups...</p></div>
          )}
        </section>

        <aside className="sbme-opt-builder" aria-label="Live lineup builder">
          <div className="sbme-opt-builder-head">
            <p className="sbme-opt-panel-title">LIVE LINEUP BUILDER</p>
            {rosterPct != null && <span className="sbme-opt-complete">{filledSlots} / {slots.length} FILLED · {rosterPct}%</span>}
          </div>
          <div className="sbme-opt-fp">
            <span>Projected FP</span>
            <b>{builderMetrics.projFP ? builderMetrics.projFP.toFixed(1) : "—"}</b>
          </div>
          <div className="sbme-opt-meter">
            <div className="sbme-opt-meter-top">
              <span>SALARY {builderMetrics.cap ? `$${capUsed.toLocaleString()} / $${builderMetrics.cap.toLocaleString()}` : "—"}</span>
              <span>REMAINING ${Math.max(0, builderMetrics.remaining).toLocaleString()}</span>
            </div>
            <div className="sbme-opt-meter-track" role="meter" aria-valuemin={0} aria-valuemax={builderMetrics.cap || 0} aria-valuenow={capUsed} aria-label="Salary used">
              <div className={`sbme-opt-meter-fill${capPct >= 100 ? " is-over" : capPct >= 90 ? " is-warn" : ""}`} style={{ width: `${Math.min(100, capPct)}%` }} />
            </div>
          </div>
          <div className="sbme-opt-builder-stats">
            <MetricBox label="Avg Remaining / Player" value={remainingSlots > 0 ? `$${avgRemaining.toLocaleString()}` : "—"} />
            <MetricBox label="Value" value={String(builderMetrics.value)} />
          </div>
          {projectionsUnavailable && (
            <div className="sbme-opt-empty" style={{ marginBottom: 12, padding: 12 }}>
              <h3>PROJECTIONS UNAVAILABLE</h3>
              <p>No SB ME projections are loaded for this slate. Projected FP stays blank until real projections arrive.</p>
            </div>
          )}

          {lineups.length > 1 && (
            <>
              <p className="sbme-opt-panel-title">BUILT LINE</p>
              <div style={{ display: "flex", gap: 4, flexWrap: "wrap", marginBottom: 10 }}>
                {lineups.map((_, i) => (
                  <button key={i} type="button" onClick={() => setSelectedLineupIndex(i)} className={`sbme-opt-tab${selectedLineupIndex === i ? " is-on" : ""}`}>Line {i + 1}</button>
                ))}
              </div>
            </>
          )}

          <p className="sbme-opt-panel-title">ROSTER · {platform === "fanduel" ? "FanDuel" : "DraftKings"} ({slots.length || "—"})</p>
          <div>
            {rosterRows.map((row, i) => (
              <div key={i} className={`sbme-opt-slot${row.name ? " is-filled" : ""}`}>
                <span className="sbme-opt-slot-pos">{slotLabel(row.slot, roster)}</span>
                {row.name ? (
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ fontSize: 12, fontWeight: 600, color: "#f0f6fc", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{row.name}</div>
                    <div style={{ fontSize: 10, color: "#64748b" }}>{row.team}{row.opponent ? ` vs ${row.opponent}` : ""}{row.salary ? ` · $${row.salary.toLocaleString()}` : ""}{row.proj ? ` · ${row.proj.toFixed(1)}` : ""}</div>
                  </div>
                ) : (
                  <span style={{ fontSize: 11, color: "#64748b", flex: 1 }}>Select player</span>
                )}
              </div>
            ))}
          </div>
          <p className="sbme-opt-panel-title">LINEUP COUNT</p>
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <input type="range" min={1} max={50} value={lineupCount} onChange={(e) => setLineupCount(+e.target.value)} aria-label="Lineup count" style={{ flex: 1, accentColor: "#c9a84c" }} />
            <span style={{ fontSize: 14, fontWeight: 800, color: "#c9a84c", minWidth: 24, textAlign: "center" }}>{lineupCount}</span>
          </div>
          <button type="button" className="sbme-opt-cmd" onClick={() => optimizeMutation.mutate({ strategy, num_lineups: lineupCount })} disabled={!canGenerate || optimizeMutation.isPending}>
            {optimizeMutation.isPending ? <><Loader2 size={18} className="animate-spin" /> SOLVING...</> : <>BUILD OPTIMAL LINEUP</>}
          </button>
          {optimizeMutation.isError && !optimizeMutation.isPending && (
            <p style={{ fontSize: 12, color: "#f87171", fontWeight: 700, marginTop: 8 }}>
              {optimizeMutation.error instanceof Error ? optimizeMutation.error.message : "Optimization failed"}
            </p>
          )}
          {roster && roster.salaryCap == null && maxSalaryOverride == null && (
            <div className="sbme-opt-empty" style={{ marginTop: 12 }}>
              <h3>SALARY CAP UNAVAILABLE</h3>
              <p>{sport} {platform === "fanduel" ? "FanDuel" : "DraftKings"} salary cap is not in verified platform configuration. Optimization is blocked until a verified cap is configured.</p>
            </div>
          )}
          {resolvedSlateId != null && !slateIntegrity.healthy && (
            <div style={{ marginTop: 12, padding: "14px 18px", borderRadius: 12, background: "rgba(239,68,68,0.05)", border: "1px solid rgba(239,68,68,0.2)", fontSize: 11 }}>
              <div style={{ fontWeight: 800, color: "#ef4444", marginBottom: 6, display: "flex", alignItems: "center", gap: 6 }}>
                <Ban size={13} /> SLATE INTEGRITY FAILURE — OPTIMIZE DISABLED
              </div>
              <div style={{ color: "#94a3b8", marginBottom: 4 }}>
                Only {slateIntegrity.matched} of {slateIntegrity.total} SGO players in this slate&apos;s games ({Number(slateIntegrity.matchRate * 100).toFixed(1)}%) matched against DFS records. Minimum threshold: 85%.
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
            <div className="sbme-opt-empty" style={{ marginTop: 12 }}>
              <h3>No DFS slate currently available</h3>
              <p>
                SB ME has not received an active {platform === "draftkings" ? "DraftKings" : "FanDuel"} contest slate for this sport yet.
              </p>
              <p style={{ marginTop: 8, color: "#64748b" }}>
                Optimizer unavailable until a DFS slate is available.
              </p>
              {hasStaleSlates && (
                <p style={{ marginTop: 6, fontSize: 10, color: "#64748b" }}>
                  One or more {platform === "draftkings" ? "DraftKings" : "FanDuel"} slates exist but are for past dates and have been blocked by freshness protection.
                </p>
              )}
            </div>
          )}
        </aside>
      </div>

      <div className="sbme-opt-lower">
        <section className="sbme-opt-intel sbme-opt-intel--stack">
          <p className="sbme-opt-panel-title">STACKING INTELLIGENCE</p>
          <div style={{ display: "flex", gap: 10, flexWrap: "wrap", alignItems: "center" }}>
            <RuleField label="Max Hitters/Team" value={maxHittersPerTeam} onChange={setMaxHittersPerTeam} placeholder="Any" />
            <RuleField label="Team Stack Size" value={stackSize} onChange={setStackSize} placeholder="Off" />
            <label style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 12, color: "#94a3b8", cursor: "pointer" }}>
              <input type="checkbox" checked={pitcherConflict} onChange={(e) => setPitcherConflict(e.target.checked)} style={{ accentColor: "#c9a84c" }} /> Pitcher/Opposing-Hitter conflict
            </label>
            <RuleField label="Min Salary" value={minSalaryOverride} onChange={setMinSalaryOverride} placeholder="Default" />
            <RuleField label="Max Salary" value={maxSalaryOverride} onChange={setMaxSalaryOverride} placeholder="Default" />
            <RuleField label="Max Exposure %" value={globalMaxExposure} onChange={setGlobalMaxExposure} placeholder="None" step={5} />
          </div>
          <p style={{ fontSize: 11, color: "#64748b", margin: "8px 0 0" }}>Existing solver constraints only. No additional stack rules are implied.</p>
        </section>
        <section className="sbme-opt-intel sbme-opt-intel--insights">
          <p className="sbme-opt-panel-title">OPTIMIZER INSIGHTS</p>
          <p className="sbme-opt-insight">Salary remaining <b>${Math.max(0, builderMetrics.remaining).toLocaleString()}</b></p>
          <p className="sbme-opt-insight">Lineup projection <b>{builderMetrics.projFP ? builderMetrics.projFP.toFixed(1) : "unavailable"}</b></p>
          <p className="sbme-opt-insight">Locked <b>{ws.lockedIds.length}</b> · Excluded <b>{ws.excludedIds.length}</b></p>
          <p className="sbme-opt-insight">Roster <b>{filledSlots} / {slots.length || 0}</b></p>
          <p className="sbme-opt-insight">Stack size <b>{stackSize ?? "off"}</b> · Max hitters/team <b>{maxHittersPerTeam ?? "any"}</b></p>
          <p className="sbme-opt-insight">Pitcher conflict <b>{pitcherConflict ? "on" : "off"}</b></p>
        </section>
        <section className="sbme-opt-intel sbme-opt-intel--slate">
          <p className="sbme-opt-panel-title">SLATE INTELLIGENCE</p>
          <p className="sbme-opt-insight">Slate <b>{selectedSlate?.slate_name || "No DFS slate currently available"}</b></p>
          <p className="sbme-opt-insight">Sport <b>{sport}</b> · Platform <b>{platformLabel(platform)}</b></p>
          <p className="sbme-opt-insight">Games <b>{selectedSlate ? (selectedSlate.game_count ?? gameCount) : "—"}</b> · Players <b>{selectedSlate ? (selectedSlate.player_count ?? dfsPlayers.length) : "—"}</b></p>
          <p className="sbme-opt-insight">Status <b>{resolvedSlateId == null ? "NONE" : slateStatusLabel}</b></p>
          <p className="sbme-opt-insight">SGO events <b>{sgoLoading ? "Loading..." : events.length}</b>{lastFetch ? ` · fetched ${formatFetchedAt(lastFetch)}` : ""}</p>
          <p className="sbme-opt-insight">Source <b>{selectedSlate?.data_source || "—"}</b></p>
        </section>
      </div>
    </div>
    </AppShell>
  );
}

// ── Sub-components ──────────────────────────────────────────

function ScheduleChips({ events }: { events: SBEvent[] }) {
  if (events.length === 0) {
    return <span style={{ fontSize: 11, color: "#64748b" }}>No upcoming schedule games are available.</span>;
  }
  return (
    <div className="sbme-opt-rail">
      {events.slice(0, 24).map((e) => (
        <div key={e.id} className="sbme-opt-sched">
          <div>{scheduleMatchupLabel(e)}</div>
          <time>{formatKickoffEt(e.start_time)}</time>
        </div>
      ))}
    </div>
  );
}

function Selector({ label, value, options, onChange, format }: { label: string; value: string; options: string[]; onChange: (v: string) => void; format?: (v: string) => string }) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
      <span style={{ fontSize: 10, fontWeight: 700, color: "#64748b", textTransform: "uppercase" }}>{label}</span>
      <select value={value} onChange={(e) => onChange(e.target.value)} className="sbme-opt-select" aria-label={label}>
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
    <button type="button" onClick={onClick} aria-pressed={active} style={{ padding: "12px 18px", fontSize: 12, fontWeight: 800, letterSpacing: 1, background: active ? "#0a0f24" : "transparent", border: "none", borderBottom: active ? "2px solid #c9a84c" : "2px solid transparent", color: active ? "#c9a84c" : "#64748b", cursor: "pointer", textTransform: "uppercase" }}>
      {label}
    </button>
  );
}

function SubTabChip({ label, active, onClick }: { label: string; active: boolean; onClick: () => void }) {
  return (
    <button type="button" onClick={onClick} aria-pressed={active} style={{ padding: "6px 12px", borderRadius: 8, fontSize: 11, fontWeight: 700, background: active ? "rgba(201,168,76,0.15)" : "#1a1f33", border: active ? "1px solid #c9a84c" : "1px solid #1e293b", color: active ? "#c9a84c" : "#94a3b8", cursor: "pointer" }}>
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
    <button type="button" onClick={onClick} title={title} aria-label={title} aria-pressed={active} style={{ padding: 4, borderRadius: 6, background: active ? "rgba(201,168,76,0.2)" : "transparent", border: active ? "1px solid #c9a84c" : "1px solid transparent", cursor: "pointer", color: active ? "#c9a84c" : "#64748b", display: "flex" }}>
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
    <button type="button" onClick={onClick} disabled={disabled} style={{ display: "flex", alignItems: "center", gap: 6, padding: "8px 14px", borderRadius: 10, background: "#0a0f24", border: "1px solid #1e293b", color: "#94a3b8", fontSize: 12, fontWeight: 600, cursor: disabled ? "not-allowed" : "pointer", opacity: disabled ? 0.5 : 1 }}>
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