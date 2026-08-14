"use client";

import { useState, useEffect, useMemo, useCallback } from "react";
import { useRouter } from "next/navigation";
import { useMutation } from "@tanstack/react-query";
import { fetchDFSSlates, fetchDFSSlate, runOptimizer, type LineupResponse, type DFSSlatePlayer } from "@/lib/api";
import { Play, Loader2, Search, Filter, Save, RefreshCw, Trash2, List } from "lucide-react";
import { useEvents } from "@/lib/use-events";
import type { SBEvent, SBPlayer, SBMarket } from "@/lib/sbevent";

const SPORTS = ["MLB", "NFL", "NBA", "NHL", "NCAAF", "NCAAB"] as const;
const PLATFORMS = ["draftkings", "fanduel"] as const;
const STRATEGIES = ["balanced", "cash", "gpp", "aggressive"] as const;

function liveClass(status: string): boolean {
  const s = (status || "").toUpperCase();
  return s === "LIVE" || s === "IN_PLAY" || s === "INPLAY";
}

function resolveTeamName(teamId: string, event: SBEvent): string {
  if (event.home_team?.team_id === teamId) return event.home_team.abbreviation || event.home_team.name;
  if (event.away_team?.team_id === teamId) return event.away_team.abbreviation || event.away_team.name;
  return teamId;
}

function countPlayerMarkets(playerId: string, markets: SBMarket[]): number {
  return (markets || []).filter((m) => m.player_id === playerId).length;
}

/** Derive a player's opponent team from their event's home/away teams. */
function opponentFor(player: SBPlayer, event: SBEvent): string {
  if (!event) return "";
  if (event.home_team?.team_id === player.team_id) {
    return event.away_team?.abbreviation || event.away_team?.name || "";
  }
  if (event.away_team?.team_id === player.team_id) {
    return event.home_team?.abbreviation || event.home_team?.name || "";
  }
  return "";
}

/** Normalize a player name for fuzzy matching */
function normName(n: string): string {
  return (n || "").toLowerCase().replace(/[^a-z0-9]/g, "").trim();
}

/** Match a SGO player to a DFS slate player by name+team+position.
 *  Returns the DFS player (with salary) or null if no match. */
function matchDFS(
  sgo: { name: string; team?: string; team_id?: string; position?: string },
  dfsPool: DFSSlatePlayer[],
  event?: SBEvent,
): DFSSlatePlayer | null {
  const n = normName(sgo.name);
  if (!n) return null;
  const pos = (sgo.position || "").toUpperCase();
  const teamFull = event
    ? resolveTeamName(sgo.team_id || "", event)
    : sgo.team || sgo.team_id || "";
  for (const d of dfsPool) {
    if (normName(d.name) === n && d.position.toUpperCase() === pos) return d;
    // also try name match without position
  }
  for (const d of dfsPool) {
    if (normName(d.name) === n && d.team === teamFull) return d;
  }
  return null;
}

export default function OptimizerPage() {
  const router = useRouter();

  // ── State ──────────────────────────────────────────────────
  const [sport, setSport] = useState<string>("MLB");
  const [platform, setPlatform] = useState<string>("draftkings");
  const [bookmakerSource, setBookmakerSource] = useState<string>("Best Available");
  const [strategy, setStrategy] = useState<string>("balanced");
  const [lineupCount, setLineupCount] = useState(1);

  const { events, loading: sgoLoading } = useEvents(sport);

  // Multi-game selection — empty Set = ALL GAMES
  const [selectedGameIds, setSelectedGameIds] = useState<Set<string>>(new Set());

  // Filters
  const [playerSearch, setPlayerSearch] = useState("");
  const [posFilter, setPosFilter] = useState("ALL");
  const [teamFilter, setTeamFilter] = useState<string>("ALL");

  // Results
  const [lineups, setLineups] = useState<LineupResponse[]>([]);
  const [resolvedSlateId, setResolvedSlateId] = useState<number | null>(null);
  const [slatesLoading, setSlatesLoading] = useState(true);
  const [lastGenMeta, setLastGenMeta] = useState<{
    sport: string;
    platform: string;
    strategy: string;
    gameCount: number;
  } | null>(null);
  const [savedNote, setSavedNote] = useState(false);

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

  // ── Fetch DFS players for salary matching ──────────────────
  const [dfsPlayers, setDfsPlayers] = useState<DFSSlatePlayer[]>([]);
  useEffect(() => {
    if (!resolvedSlateId) { setDfsPlayers([]); return; }
    let cancelled = false;
    (async () => {
      try {
        const res = await fetchDFSSlate(resolvedSlateId);
        if (!cancelled) setDfsPlayers(res?.data?.players ?? []);
      } catch {
        if (!cancelled) setDfsPlayers([]);
      }
    })();
    return () => { cancelled = true; };
  }, [resolvedSlateId]);

  // Reset filters / results on sport or platform change
  useEffect(() => {
    setPlayerSearch("");
    setPosFilter("ALL");
    setTeamFilter("ALL");
    setLineups([]);
    setLastGenMeta(null);
  }, [sport, platform]);

  // ── Optimize mutation ──────────────────────────────────────
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
      setLastGenMeta({
        sport,
        platform,
        strategy,
        gameCount: filteredEvents.length,
      });
    },
    onError: () => {
      setLineups([]);
      setLastGenMeta(null);
    },
  });

  // ── Derived data ───────────────────────────────────────────
  const allMode = selectedGameIds.size === 0;
  const filteredEvents = useMemo(() => {
    if (allMode) return events;
    const ids = selectedGameIds;
    return events.filter((e) => ids.has(e.id));
  }, [events, allMode, selectedGameIds]);

  // Aggregate players from all selected events (deduped by player_id)
  const players = useMemo(() => {
    const seen = new Map<string, SBPlayer>();
    for (const evt of filteredEvents) {
      for (const p of evt.players ?? []) {
        const pid = p.player_id;
        if (!pid || seen.has(pid)) continue;
        seen.set(pid, p);
      }
    }
    return Array.from(seen.values());
  }, [filteredEvents]);

  // Aggregate markets
  const markets = useMemo(() => {
    const out: SBMarket[] = [];
    for (const evt of filteredEvents) {
      for (const m of evt.markets ?? []) out.push(m);
    }
    return out;
  }, [filteredEvents]);

  // Aggregate bookmakers
  const bookmakers = useMemo(() => {
    const seen = new Set<string>();
    for (const evt of filteredEvents) {
      for (const b of evt.bookmakers ?? []) seen.add(b);
    }
    return Array.from(seen).sort();
  }, [filteredEvents]);

  const teams = useMemo(() => {
    const seen = new Set<string>();
    for (const p of players) {
      const evt = filteredEvents.find((e) =>
        (e.players ?? []).some((ep) => ep.player_id === p.player_id),
      );
      if (evt) seen.add(resolveTeamName(p.team_id, evt));
    }
    return Array.from(seen).sort();
  }, [players, filteredEvents]);

  const positions = useMemo(
    () => [...new Set(players.map((p) => p.position).filter(Boolean))].sort(),
    [players],
  );

  const filteredPlayers = useMemo(() => {
    return players.filter((p) => {
      const evt = filteredEvents.find((e) =>
        (e.players ?? []).some((ep) => ep.player_id === p.player_id),
      );
      const teamName = evt ? resolveTeamName(p.team_id, evt) : "";
      if (teamFilter !== "ALL" && teamName !== teamFilter) return false;
      if (posFilter !== "ALL" && p.position !== posFilter) return false;
      if (playerSearch) {
        const q = playerSearch.toLowerCase();
        if (!p.name.toLowerCase().includes(q) && !teamName.toLowerCase().includes(q)) return false;
      }
      return true;
    });
  }, [players, filteredEvents, teamFilter, posFilter, playerSearch]);

  const liveEvents = events.filter((e) => liveClass(e.status));
  const upcomingEvents = events.filter((e) => !liveClass(e.status));

  const canGenerate = !slatesLoading && resolvedSlateId != null && filteredEvents.length > 0;

  // ── Game toggle helpers ────────────────────────────────────
  const toggleGame = useCallback((id: string) => {
    setSelectedGameIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  }, []);

  const selectAllGames = useCallback(() => {
    setSelectedGameIds(new Set());
  }, []);

  // ── Lineup actions ─────────────────────────────────────────
  const clearLineups = useCallback(() => {
    setLineups([]);
    setLastGenMeta(null);
    setSavedNote(false);
  }, []);

  const regenerate = useCallback(() => {
    optimizeMutation.mutate();
  }, [optimizeMutation]);

  const markSaved = useCallback(() => {
    setSavedNote(true);
  }, []);

  // ── Render ────────────────────────────────────────────────
  return (
    <div style={{ background: "#060b1a", minHeight: "100vh", color: "#f0f6fc" }}>
      {/* Header */}
      <div style={{ padding: "20px 24px", borderBottom: "1px solid #1e293b" }}>
        <h1 style={{ fontSize: 22, fontWeight: 900, color: "#c9a84c", fontStyle: "italic", margin: 0 }}>
          Lineup Optimizer
        </h1>
        <p style={{ color: "#64748b", fontSize: 13, margin: "4px 0 0" }}>
          SportsGameOdds Intelligence · Native DFS · CP-SAT Engine
        </p>
      </div>

      {/* Selector bar */}
      <div
        style={{
          padding: "16px 24px",
          borderBottom: "1px solid #1e293b",
          display: "flex",
          gap: 12,
          flexWrap: "wrap",
          alignItems: "center",
        }}
      >
        <Selector label="Sport" value={sport} options={[...SPORTS]} onChange={setSport} />
        <Selector
          label="Platform"
          value={platform}
          options={[...PLATFORMS]}
          onChange={setPlatform}
          format={(v) => (v === "draftkings" ? "DraftKings" : "FanDuel")}
        />
        <Selector label="Bookmaker" value={bookmakerSource} options={["Best Available", "Book Consensus", ...bookmakers]} onChange={setBookmakerSource} />
        <Selector label="Strategy" value={strategy} options={[...STRATEGIES]} onChange={setStrategy} />
      </div>

      {/* Main layout */}
      <div style={{ display: "flex", flex: 1, minHeight: 0 }}>
        {/* ── LEFT PANEL ── */}
        <div
          style={{
            width: 340,
            flexShrink: 0,
            borderRight: "1px solid #1e293b",
            overflow: "auto",
            padding: 16,
            display: "flex",
            flexDirection: "column",
            gap: 14,
          }}
        >
          {/* Games */}
          <Section title={`Games (${filteredEvents.length})`}>
            {sgoLoading ? (
              <div style={{ display: "flex", alignItems: "center", gap: 8, color: "#94a3b8" }}>
                <Loader2 size={16} className="animate-spin" /> Loading from SportsGameOdds...
              </div>
            ) : events.length === 0 ? (
              <Muted>No events for {sport}</Muted>
            ) : (
              <>
                {/* ALL GAMES master switch */}
                <button
                  onClick={selectAllGames}
                  style={{
                    width: "100%",
                    padding: "10px 12px",
                    borderRadius: 10,
                    textAlign: "left",
                    fontSize: 13,
                    fontWeight: 800,
                    background: allMode ? "rgba(201,168,76,0.15)" : "#0a0f24",
                    border: allMode ? "1px solid #c9a84c" : "1px solid #1e293b",
                    color: allMode ? "#c9a84c" : "#94a3b8",
                    cursor: "pointer",
                    marginBottom: 6,
                  }}
                >
                  ⬜ ALL GAMES
                </button>
                {liveEvents.length > 0 && (
                  <>
                    <Label>● LIVE</Label>
                    {liveEvents.map((e) => (
                      <GameToggle
                        key={e.id}
                        event={e}
                        active={!allMode && selectedGameIds.has(e.id)}
                        onClick={() => toggleGame(e.id)}
                      />
                    ))}
                  </>
                )}
                <Label>Upcoming</Label>
                {upcomingEvents.slice(0, 16).map((e) => (
                  <GameToggle
                    key={e.id}
                    event={e}
                    active={!allMode && selectedGameIds.has(e.id)}
                    onClick={() => toggleGame(e.id)}
                  />
                ))}
              </>
            )}
          </Section>

          {/* Generate controls */}
          <Section title="Lineups">
            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: 8,
                justifyContent: "space-between",
              }}
            >
              <input
                type="range"
                min={1}
                max={50}
                value={lineupCount}
                onChange={(e) => setLineupCount(+e.target.value)}
                style={{ flex: 1, accentColor: "#c9a84c" }}
              />
              <span style={{ fontSize: 12, fontWeight: 700, color: "#c9a84c" }}>{lineupCount}</span>
            </div>
            <button
              onClick={() => optimizeMutation.mutate()}
              disabled={!canGenerate || optimizeMutation.isPending}
              style={{
                width: "100%",
                padding: "14px",
                borderRadius: 14,
                fontWeight: 800,
                fontSize: 15,
                textTransform: "uppercase",
                background: canGenerate ? "#c9a84c" : "#1e293b",
                color: canGenerate ? "#060b1a" : "#64748b",
                border: "none",
                cursor: canGenerate ? "pointer" : "not-allowed",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                gap: 8,
                boxShadow: canGenerate ? "0 4px 20px rgba(201,168,76,0.3)" : "none",
              }}
            >
              {optimizeMutation.isPending ? (
                <>
                  <Loader2 size={18} className="animate-spin" /> Solving...
                </>
              ) : (
                <>
                  <Play size={18} /> Generate
                </>
              )}
            </button>
            {!slatesLoading && resolvedSlateId == null && (
              <Muted>
                No {platform === "draftkings" ? "DraftKings" : "FanDuel"} contest salary data
                for {sport} — Generate is unavailable until a {platform} slate is published.
              </Muted>
            )}
          </Section>
        </div>

        {/* ── RIGHT PANEL ── */}
        <div style={{ flex: 1, overflow: "auto", padding: 24 }}>
          {/* Selected games summary */}
          <div
            style={{
              background: "#0a0f24",
              borderRadius: 14,
              border: "1px solid #1e293b",
              padding: "16px 20px",
              marginBottom: 20,
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              flexWrap: "wrap",
              gap: 8,
            }}
          >
            <div>
              <div style={{ fontSize: 17, fontWeight: 800, color: "#f0f6fc" }}>
                {allMode ? "ALL GAMES" : `${selectedGameIds.size} Game${selectedGameIds.size > 1 ? "s" : ""}`}
              </div>
              <div style={{ fontSize: 12, color: "#64748b", marginTop: 4 }}>
                {sport} · {filteredEvents.length} event{filteredEvents.length !== 1 ? "s" : ""} ·{" "}
                {players.length} players · {dfsPlayers.length > 0 ? `${dfsPlayers.length} DFS salaries` : "salary data pending"}
              </div>
            </div>
            {lastGenMeta && (
              <span style={{ fontSize: 11, color: "#64748b" }}>
                Last: {lastGenMeta.strategy} · {lastGenMeta.gameCount} games · {lastGenMeta.platform}
              </span>
            )}
          </div>

          {/* Player pool */}
          <div
            style={{
              display: "flex",
              gap: 10,
              marginBottom: 16,
              flexWrap: "wrap",
              alignItems: "center",
            }}
          >
            <div style={{ position: "relative", flex: 1, maxWidth: 300 }}>
              <Search
                size={14}
                style={{ position: "absolute", left: 10, top: "50%", transform: "translateY(-50%)", color: "#64748b" }}
              />
              <input
                type="text"
                placeholder="Search players..."
                value={playerSearch}
                onChange={(e) => setPlayerSearch(e.target.value)}
                style={{
                  width: "100%",
                  padding: "8px 14px 8px 32px",
                  borderRadius: 10,
                  fontSize: 13,
                  background: "#0a0f24",
                  border: "1px solid #1e293b",
                  color: "#f0f6fc",
                  outline: "none",
                }}
              />
            </div>
            <Filter size={14} color="#64748b" />
            <select
              value={teamFilter}
              onChange={(e) => setTeamFilter(e.target.value)}
              style={{
                padding: "8px 12px",
                borderRadius: 10,
                fontSize: 12,
                background: "#0a0f24",
                border: "1px solid #1e293b",
                color: "#f0f6fc",
              }}
            >
              <option value="ALL">All Teams</option>
              {teams.map((t) => (
                <option key={t} value={t}>
                  {t}
                </option>
              ))}
            </select>
            <select
              value={posFilter}
              onChange={(e) => setPosFilter(e.target.value)}
              style={{
                padding: "8px 12px",
                borderRadius: 10,
                fontSize: 12,
                background: "#0a0f24",
                border: "1px solid #1e293b",
                color: "#f0f6fc",
              }}
            >
              <option value="ALL">All Positions</option>
              {positions.map((p) => (
                <option key={p} value={p}>
                  {p}
                </option>
              ))}
            </select>
            <span style={{ fontSize: 12, color: "#64748b", marginLeft: "auto" }}>
              {filteredPlayers.length} players · SportsGameOdds
            </span>
          </div>

          {filteredPlayers.length === 0 ? (
            <div
              style={{
                background: "#0a0f24",
                borderRadius: 14,
                border: "1px solid #1e293b",
                padding: 28,
                textAlign: "center",
                color: "#64748b",
              }}
            >
              No player data available for the selected games.
            </div>
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
              {/* Column header */}
              <div
                style={{
                  display: "grid",
                  gridTemplateColumns: "60px 1fr 70px 70px 90px 70px 80px",
                  gap: 8,
                  padding: "0 16px 6px",
                  fontSize: 10,
                  fontWeight: 700,
                  color: "#64748b",
                  textTransform: "uppercase",
                }}
              >
                <span>Pos</span>
                <span>Player</span>
                <span>Team</span>
                <span>Opp</span>
                <span>SGO Mkts</span>
                <span>Props</span>
                <span>Salary</span>
              </div>
              {filteredPlayers.slice(0, 200).map((p) => {
                const evt = filteredEvents.find((e) =>
                  (e.players ?? []).some((ep) => ep.player_id === p.player_id),
                );
                const teamName = evt ? resolveTeamName(p.team_id, evt) : "";
                const opp = evt ? opponentFor(p, evt) : "";
                const mCount = countPlayerMarkets(p.player_id, markets);
                const dfs = matchDFS(
                  { name: p.name, team_id: p.team_id, position: p.position },
                  dfsPlayers,
                  evt || undefined,
                );
                return (
                  <div
                    key={p.player_id}
                    style={{
                      display: "grid",
                      gridTemplateColumns: "60px 1fr 70px 70px 90px 70px 80px",
                      gap: 8,
                      padding: "10px 16px",
                      background: "#0a0f24",
                      borderRadius: 10,
                      border: "1px solid #1e293b",
                      alignItems: "center",
                      fontSize: 13,
                    }}
                  >
                    <span
                      style={{
                        color: "#c9a84c",
                        fontWeight: 700,
                        fontSize: 11,
                        textTransform: "uppercase",
                      }}
                    >
                      {p.position || "—"}
                    </span>
                    <span style={{ color: "#f0f6fc", fontWeight: 600 }}>{p.name}</span>
                    <span style={{ color: "#94a3b8", fontSize: 11 }}>{teamName}</span>
                    <span style={{ color: "#64748b", fontSize: 11 }}>{opp || "—"}</span>
                    <span style={{ color: "#94a3b8", fontSize: 11 }}>
                      {mCount > 0 ? `${mCount} markets` : "—"}
                    </span>
                    <span style={{ color: "#c9a84c", fontSize: 11 }}>
                      {mCount > 0 ? `${mCount} props` : "—"}
                    </span>
                    <span
                      style={{
                        color: dfs ? "#c9a84c" : "#64748b",
                        fontSize: 11,
                        fontWeight: dfs ? 700 : 400,
                      }}
                    >
                      {dfs ? `$${dfs.salary.toLocaleString()}` : "—"}
                    </span>
                  </div>
                );
              })}
            </div>
          )}

          {/* ── RESULTS ── */}
          {optimizeMutation.isPending ? (
            <Center>
              <Loader2 size={32} className="animate-spin" style={{ color: "#c9a84c" }} />
              <p style={{ color: "#94a3b8", marginTop: 16 }}>Running CP-SAT optimizer...</p>
            </Center>
          ) : optimizeMutation.isError ? (
            <Center>
              <p style={{ color: "#ef4444", fontWeight: 700, fontSize: 16 }}>
                {optimizeMutation.error instanceof Error
                  ? optimizeMutation.error.message
                  : "Optimization failed"}
              </p>
            </Center>
          ) : lineups.length > 0 ? (
            <div style={{ marginTop: 24 }}>
              {/* Results header with actions */}
              <div
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                  marginBottom: 16,
                  flexWrap: "wrap",
                  gap: 8,
                }}
              >
                <h2 style={{ fontSize: 18, fontWeight: 800, color: "#c9a84c", margin: 0 }}>
                  Generated Lineups ({lineups.length})
                </h2>
                <div style={{ display: "flex", gap: 8 }}>
                  <ActionBtn
                    icon={<Save size={14} />}
                    label={savedNote ? "Saved ✓" : "Save"}
                    onClick={markSaved}
                  />
                  <ActionBtn
                    icon={<RefreshCw size={14} />}
                    label="Regenerate"
                    onClick={regenerate}
                    disabled={optimizeMutation.isPending}
                  />
                  <ActionBtn icon={<Trash2 size={14} />} label="Clear" onClick={clearLineups} />
                  <ActionBtn
                    icon={<List size={14} />}
                    label="View Saved Lineups"
                    onClick={() => router.push("/lineups")}
                  />
                </div>
              </div>
              {lastGenMeta && (
                <div
                  style={{ fontSize: 11, color: "#64748b", marginBottom: 14 }}
                >
                  Platform: {lastGenMeta.platform === "draftkings" ? "DraftKings" : "FanDuel"} · Strategy:{" "}
                  {lastGenMeta.strategy} · {lastGenMeta.gameCount} games
                </div>
              )}
              <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
                {lineups.map((l, i) => (
                  <LineupCard key={i} index={i} lineup={l} platform={lastGenMeta?.platform || platform} />
                ))}
              </div>
            </div>
          ) : null}
        </div>
      </div>
    </div>
  );
}

// ── Reusable sub-components ─────────────────────────────────

function Selector({
  label,
  value,
  options,
  onChange,
  format,
}: {
  label: string;
  value: string;
  options: string[];
  onChange: (v: string) => void;
  format?: (v: string) => string;
}) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
      <span style={{ fontSize: 10, fontWeight: 700, color: "#64748b", textTransform: "uppercase" }}>
        {label}
      </span>
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        style={{
          padding: "8px 12px",
          borderRadius: 10,
          fontSize: 12,
          fontWeight: 600,
          background: "#0a0f24",
          border: "1px solid #1e293b",
          color: "#c9a84c",
          cursor: "pointer",
        }}
      >
        {options.map((o) => (
          <option key={o} value={o}>
            {format ? format(o) : o}
          </option>
        ))}
      </select>
    </div>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div>
      <p
        style={{
          fontSize: 10,
          fontWeight: 700,
          color: "#64748b",
          textTransform: "uppercase",
          marginBottom: 8,
        }}
      >
        {title}
      </p>
      {children}
    </div>
  );
}

function Label({ children }: { children: React.ReactNode }) {
  return (
    <p style={{ fontSize: 10, fontWeight: 600, color: "#64748b", margin: "6px 0" }}>{children}</p>
  );
}

function Muted({ children }: { children: React.ReactNode }) {
  return <p style={{ color: "#64748b", fontSize: 13 }}>{children}</p>;
}

function GameToggle({
  event,
  active,
  onClick,
}: {
  event: SBEvent;
  active: boolean;
  onClick: () => void;
}) {
  const isLive = liveClass(event.status);
  return (
    <button
      onClick={onClick}
      style={{
        width: "100%",
        padding: "8px 12px",
        borderRadius: 10,
        textAlign: "left",
        fontSize: 12,
        fontWeight: 600,
        background: active
          ? "rgba(201,168,76,0.1)"
          : isLive
            ? "rgba(239,68,68,0.06)"
            : "#0a0f24",
        border: active
          ? "1px solid rgba(201,168,76,0.4)"
          : isLive
            ? "1px solid rgba(239,68,68,0.2)"
            : "1px solid #1e293b",
        color: active ? "#c9a84c" : "#94a3b8",
        cursor: "pointer",
        marginBottom: 4,
      }}
    >
      {isLive && (
        <span style={{ color: "#ef4444", fontSize: 10, fontWeight: 800, marginRight: 6 }}>
          ●
        </span>
      )}
      {active ? "☑" : "☐"}{" "}
      {event.away_team?.abbreviation || event.away_team?.name} @{" "}
      {event.home_team?.abbreviation || event.home_team?.name}
    </button>
  );
}

function Center({ children }: { children: React.ReactNode }) {
  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        minHeight: 200,
        textAlign: "center",
      }}
    >
      {children}
    </div>
  );
}

function ActionBtn({
  icon,
  label,
  onClick,
  disabled,
}: {
  icon: React.ReactNode;
  label: string;
  onClick: () => void;
  disabled?: boolean;
}) {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      style={{
        display: "flex",
        alignItems: "center",
        gap: 6,
        padding: "8px 14px",
        borderRadius: 10,
        background: "#0a0f24",
        border: "1px solid #1e293b",
        color: "#94a3b8",
        fontSize: 12,
        fontWeight: 600,
        cursor: disabled ? "not-allowed" : "pointer",
        opacity: disabled ? 0.5 : 1,
      }}
    >
      {icon}
      {label}
    </button>
  );
}

function LineupCard({
  index,
  lineup,
  platform,
}: {
  index: number;
  lineup: LineupResponse;
  platform: string;
}) {
  const rem = (lineup as any).remaining_salary ?? 0;
  return (
    <div
      style={{
        background: "#0a0f24",
        borderRadius: 16,
        border: "1px solid #1e293b",
        overflow: "hidden",
      }}
    >
      <div style={{ height: 4, background: "#c9a84c" }} />
      <div
        style={{
          padding: "16px 20px",
          display: "flex",
          justifyContent: "space-between",
          borderBottom: "1px solid #1e293b",
          flexWrap: "wrap",
          gap: 8,
        }}
      >
        <span style={{ fontWeight: 800, color: "#f0f6fc" }}>Lineup {index + 1}</span>
        <div style={{ display: "flex", gap: 16, flexWrap: "wrap" }}>
          <span style={{ color: "#94a3b8", fontSize: 13 }}>
            Platform:{" "}
            <strong style={{ color: "#f0f6fc" }}>
              {platform === "draftkings" ? "DraftKings" : "FanDuel"}
            </strong>
          </span>
          <span style={{ color: "#94a3b8", fontSize: 13 }}>
            Salary:{" "}
            <strong style={{ color: "#f0f6fc" }}>
              ${lineup.total_salary?.toLocaleString()}
            </strong>
          </span>
          <span style={{ color: "#94a3b8", fontSize: 13 }}>
            Remaining:{" "}
            <strong style={{ color: "#c9a84c" }}>${rem.toLocaleString()}</strong>
          </span>
          <span style={{ color: "#c9a84c", fontSize: 13, fontWeight: 700 }}>
            Proj: {lineup.projected_score}
          </span>
        </div>
      </div>
      <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
        <thead>
          <tr style={{ background: "#060b1a" }}>
            <th
              style={{
                padding: "8px 20px",
                textAlign: "left",
                fontSize: 10,
                fontWeight: 700,
                color: "#64748b",
                textTransform: "uppercase",
                width: 70,
              }}
            >
              Pos
            </th>
            <th
              style={{
                padding: "8px 0",
                textAlign: "left",
                fontSize: 10,
                fontWeight: 700,
                color: "#64748b",
                textTransform: "uppercase",
              }}
            >
              Player
            </th>
            <th
              style={{
                padding: "8px 0",
                textAlign: "left",
                fontSize: 10,
                fontWeight: 700,
                color: "#64748b",
                textTransform: "uppercase",
              }}
            >
              Team
            </th>
            <th
              style={{
                padding: "8px 0",
                textAlign: "left",
                fontSize: 10,
                fontWeight: 700,
                color: "#64748b",
                textTransform: "uppercase",
              }}
            >
              Opp
            </th>
            <th
              style={{
                padding: "8px 20px",
                textAlign: "right",
                fontSize: 10,
                fontWeight: 700,
                color: "#64748b",
                textTransform: "uppercase",
              }}
            >
              Salary
            </th>
            <th
              style={{
                padding: "8px 20px",
                textAlign: "right",
                fontSize: 10,
                fontWeight: 700,
                color: "#64748b",
                textTransform: "uppercase",
              }}
            >
              Proj
            </th>
          </tr>
        </thead>
        <tbody>
          {(lineup.players || []).map((p: any, j: number) => (
            <tr
              key={j}
              style={{
                borderBottom:
                  j < (lineup.players || []).length - 1 ? "1px solid #1e293b30" : "none",
              }}
            >
              <td
                style={{
                  padding: "10px 20px",
                  width: 70,
                  color: "#c9a84c",
                  fontWeight: 700,
                  textTransform: "uppercase",
                  fontSize: 11,
                }}
              >
                {p.roster_position || p.roster_slot || "—"}
              </td>
              <td style={{ padding: "10px 0", fontWeight: 600, color: "#f0f6fc" }}>
                {p.name || `Player #${p.id}`}
              </td>
              <td style={{ padding: "10px 0", color: "#64748b", fontSize: 12 }}>
                {p.team || ""}
              </td>
              <td style={{ padding: "10px 0", color: "#64748b", fontSize: 12 }}>
                {p.opponent || ""}
              </td>
              <td
                style={{
                  padding: "10px 20px",
                  color: "#94a3b8",
                  textAlign: "right",
                }}
              >
                ${(p.salary || 0).toLocaleString()}
              </td>
              <td
                style={{
                  padding: "10px 20px",
                  color: "#c9a84c",
                  fontWeight: 700,
                  textAlign: "right",
                }}
              >
                {(p.projected_fp || 0).toFixed(1)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}