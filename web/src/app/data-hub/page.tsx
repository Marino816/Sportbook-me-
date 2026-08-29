"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  Database,
  Search,
  Lock,
  Ban,
  Heart,
  Send,
  Loader2,
  X,
  Zap,
  ChevronRight,
} from "lucide-react";
import {
  fetchDataHubSlate,
  fetchDFSSlates,
  fetchOptimalPct,
  type CanonicalPlayer,
  type DFSSlateSummary,
} from "@/lib/api";
import { useWorkspace } from "@/lib/workspace-context";
import { PlayerAvatar, TeamLogo } from "@/lib/assets";
import { LastFive } from "@/lib/last-five";
import { AppShell } from "@/components/app-shell";
import { buildOptimizerHandoffUrl } from "@/lib/ai-session";
import {
  filterCustomerVisibleSlates,
  formatSlateLockTime,
  getSlateDisplayStatus,
  normPlayerName,
  platformLabel,
  type SlateDisplayStatus,
} from "@/lib/dfs-slate-status";
import { useEvents } from "@/lib/use-events";
import {
  eventsWithMarketContext,
  formatKickoffEt,
  SCHEDULE_INTEL_NOTE,
  scheduleMatchupLabel,
  upcomingScheduleEvents,
} from "@/lib/upcoming-schedule";

/** DFS sports with a real slate pipeline — verified in backend/dfs/import_service.py */
const DFS_SPORTS = ["MLB", "NFL", "NBA", "NHL", "NCAAF", "NCAAB"] as const;
const DFS_PLATFORMS = ["draftkings", "fanduel"] as const;
const TABLE_LIMIT = 300;

function fmtNum(v: number | null | undefined, digits = 1): string {
  return v == null ? "—" : v.toFixed(digits);
}

function fmtProj(p: CanonicalPlayer): string {
  return p.projection_source === "UNAVAILABLE" ? "—" : p.projected_fp.toFixed(1);
}

function fmtValue(p: CanonicalPlayer): string {
  if (p.projection_source === "UNAVAILABLE" || !p.salary) return "—";
  return p.value.toFixed(2);
}

function statusPillClass(status: SlateDisplayStatus): string {
  if (status === "UNLOCKED") return "sbme-dhub-pill sbme-dhub-pill--unlocked";
  if (status === "LOCKED") return "sbme-dhub-pill sbme-dhub-pill--locked";
  if (status === "UPCOMING") return "sbme-dhub-pill sbme-dhub-pill--upcoming";
  return "sbme-dhub-pill sbme-dhub-pill--stale";
}

export default function DataHubPage() {
  const router = useRouter();
  const ws = useWorkspace();

  const [slates, setSlates] = useState<DFSSlateSummary[]>([]);
  const [hasStaleSlates, setHasStaleSlates] = useState(false);
  const [players, setPlayers] = useState<CanonicalPlayer[]>([]);
  const [meta, setMeta] = useState<Record<string, unknown> | null>(null);
  const [loading, setLoading] = useState(false);
  const [slatesLoading, setSlatesLoading] = useState(false);
  const [optPctStatus, setOptPctStatus] = useState<string>("NOT_RUN");
  const [optPctMap, setOptPctMap] = useState<Record<string, number>>({});
  const [error, setError] = useState<string | null>(null);

  const [search, setSearch] = useState("");
  const [teamFilter, setTeamFilter] = useState("");
  const [posFilter, setPosFilter] = useState("ALL");
  const [drawerPlayer, setDrawerPlayer] = useState<CanonicalPlayer | null>(null);
  const { events } = useEvents(ws.sport);

  const selectedSlate = useMemo(
    () => slates.find((s) => s.id === ws.slateId) ?? null,
    [slates, ws.slateId],
  );

  const selectedStatus = selectedSlate ? getSlateDisplayStatus(selectedSlate) : null;

  // Load published slates — preserve valid workspace selection (optimizer-aligned)
  useEffect(() => {
    let cancelled = false;
    (async () => {
      setSlatesLoading(true);
      setError(null);
      try {
        const res = await fetchDFSSlates(ws.platform, ws.sport);
        const published = filterCustomerVisibleSlates(res?.data ?? [], ws.sport);
        const current = published.filter((s) => s.freshness === "CURRENT" || s.is_current === true);
        if (!cancelled) {
          setSlates(published);
          setHasStaleSlates((res?.data ?? []).some((s) => s.freshness === "STALE" || s.is_current === false));
          const existingOk = ws.slateId != null && published.some((s) => s.id === ws.slateId);
          if (!existingOk) {
            const pool = current.length > 0 ? current : published;
            const main = pool.find((s) => s.slate_name.toLowerCase().includes("main"));
            const defaultId = main?.id ?? pool[0]?.id ?? null;
            ws.setSlateId(defaultId);
          }
        }
      } catch (e: unknown) {
        if (!cancelled) {
          setError(e instanceof Error ? e.message : "Failed to load slates");
          setSlates([]);
          setHasStaleSlates(false);
        }
      } finally {
        if (!cancelled) setSlatesLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [ws.sport, ws.platform]);

  // Canonical player pool
  useEffect(() => {
    if (!ws.slateId) {
      setPlayers([]);
      setMeta(null);
      return;
    }
    let cancelled = false;
    (async () => {
      setLoading(true);
      setError(null);
      try {
        const res = await fetchDataHubSlate(ws.slateId!, ws.platform);
        if (!cancelled) {
          setPlayers(res?.data?.players ?? []);
          setMeta(res?.data?.metadata ?? null);
        }
      } catch (e: unknown) {
        if (!cancelled) setError(e instanceof Error ? e.message : "Failed to load player pool");
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [ws.slateId, ws.platform]);

  // Optimal% from cached background sim (same path as Optimizer)
  useEffect(() => {
    if (!ws.slateId) {
      setOptPctStatus("NOT_RUN");
      setOptPctMap({});
      return;
    }
    let cancelled = false;
    (async () => {
      try {
        const res = await fetchOptimalPct(ws.slateId!, ws.platform, ws.sport);
        if (cancelled) return;
        const status = res?.data?.status ?? "NOT_RUN";
        setOptPctStatus(status);
        if (status === "COMPLETE" && res?.data?.result?.players) {
          const m: Record<string, number> = {};
          for (const p of res.data.result.players) {
            const nm = normPlayerName(p.name);
            if (nm) m[nm] = p.optimal_pct;
          }
          setOptPctMap(m);
        } else {
          setOptPctMap({});
        }
      } catch {
        if (!cancelled) {
          setOptPctStatus("NOT_RUN");
          setOptPctMap({});
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [ws.slateId, ws.platform, ws.sport]);

  const positionOptions = useMemo(() => {
    const s = new Set<string>();
    for (const p of players) {
      if (p.roster_position) s.add(p.roster_position);
    }
    return ["ALL", ...Array.from(s).sort()];
  }, [players]);

  const teamOptions = useMemo(() => {
    const s = new Set<string>();
    for (const p of players) if (p.team) s.add(p.team);
    return Array.from(s).sort();
  }, [players]);

  const filtered = useMemo(() => {
    return players.filter((p) => {
      if (posFilter !== "ALL" && p.roster_position !== posFilter) return false;
      if (teamFilter && p.team !== teamFilter) return false;
      if (search) {
        const q = search.toLowerCase();
        if (!p.name.toLowerCase().includes(q)) return false;
      }
      return true;
    });
  }, [players, posFilter, teamFilter, search]);

  const projectionCoverage = useMemo(() => {
    if (!players.length) return null;
    const withProj = players.filter((p) => p.projection_source !== "UNAVAILABLE").length;
    return { withProj, total: players.length };
  }, [players]);

  const scheduleEvents = useMemo(() => upcomingScheduleEvents(events), [events]);
  const marketEvents = useMemo(() => eventsWithMarketContext(scheduleEvents), [scheduleEvents]);
  const hasActiveSlate = slates.length > 0 && ws.slateId != null;

  const optimizerHref = buildOptimizerHandoffUrl({
    sport: ws.sport,
    platform: ws.platform,
    slate_id: ws.slateId,
    slate_name: selectedSlate?.slate_name ?? null,
    locked_players: ws.lockedIds.map((name) => ({ name })),
  });

  const metaError = meta && typeof meta.error === "string" ? meta.error : null;
  const generatedAt = meta?.generated_at ? String(meta.generated_at) : null;

  return (
    <AppShell>
      <div className="sbme-dhub">
        <header className="sbme-dhub-head">
          <span className="sbme-dhub-mark">
            <Database size={22} />
          </span>
          <div>
            <h1>Data Hub</h1>
            <p>
              DFS slate, player-pool, projection, and metrics workspace for DraftKings and FanDuel.
              Canonical SB ME player model — DFS sports only (MLB, NFL, NBA, NHL, NCAAF, NCAAB).
            </p>
          </div>
        </header>

        <p className="sbme-dhub-kicker">Workspace Selection</p>
        <div className="sbme-dhub-controls">
          <div className="sbme-dhub-ctl">
            <span className="sbme-dhub-ctl-step">1 · Sport</span>
            <label className="sbme-dhub-ctl-label" htmlFor="dh-sport">DFS Sport</label>
            <select
              id="dh-sport"
              className="sbme-dhub-select"
              value={ws.sport}
              onChange={(e) => ws.setSport(e.target.value)}
            >
              {DFS_SPORTS.map((s) => (
                <option key={s} value={s}>{s}</option>
              ))}
            </select>
          </div>
          <div className="sbme-dhub-ctl">
            <span className="sbme-dhub-ctl-step">2 · Platform</span>
            <label className="sbme-dhub-ctl-label" htmlFor="dh-platform">Platform</label>
            <select
              id="dh-platform"
              className="sbme-dhub-select"
              value={ws.platform}
              onChange={(e) => ws.setPlatform(e.target.value)}
            >
              {DFS_PLATFORMS.map((p) => (
                <option key={p} value={p}>{platformLabel(p)}</option>
              ))}
            </select>
          </div>
          <div className="sbme-dhub-ctl">
            <span className="sbme-dhub-ctl-step">{slates.length === 0 ? "3 · No Active Slate" : "3 · Slate"}</span>
            <label className="sbme-dhub-ctl-label" htmlFor="dh-slate">Active Slate</label>
            <select
              id="dh-slate"
              className="sbme-dhub-select"
              value={ws.slateId == null ? "" : String(ws.slateId)}
              onChange={(e) => ws.setSlateId(e.target.value ? Number(e.target.value) : null)}
              disabled={slatesLoading || slates.length === 0}
            >
              {slates.length === 0 ? (
                <option value="">No active slate</option>
              ) : (
                slates.map((s) => (
                  <option key={s.id} value={String(s.id)}>
                    {s.slate_name} · {getSlateDisplayStatus(s)}
                  </option>
                ))
              )}
            </select>
          </div>
          <div className="sbme-dhub-ctl">
            <span className="sbme-dhub-ctl-step">{slates.length === 0 ? "4 · Waiting for DFS Slate" : "4 · Analyze"}</span>
            <label className="sbme-dhub-ctl-label">Next Step</label>
            <button
              type="button"
              className="sbme-dhub-btn sbme-dhub-btn--gold"
              style={{ width: "100%", marginTop: 2 }}
              disabled={!hasActiveSlate}
              onClick={() => { if (hasActiveSlate) router.push(optimizerHref); }}
            >
              <Send size={14} /> Open Optimizer
            </button>
            {!hasActiveSlate && !slatesLoading && (
              <p className="sbme-dhub-muted" style={{ fontSize: 10, marginTop: 6, lineHeight: 1.4 }}>
                Optimizer unavailable until a DFS slate is available.
              </p>
            )}
          </div>
        </div>

        {hasStaleSlates && (
          <div className="sbme-dhub-banner sbme-dhub-banner--warn">
            Prior-date slates are listed for reference. Current-day slates are preferred for live analysis.
          </div>
        )}

        {error && <div className="sbme-dhub-banner sbme-dhub-banner--err">{error}</div>}

        {slatesLoading ? (
          <div className="sbme-dhub-loading"><Loader2 size={24} className="animate-spin" /></div>
        ) : slates.length === 0 ? (
          <div className="sbme-dhub-empty">
            <strong>NO DFS SLATE CURRENTLY AVAILABLE</strong>
            SB ME has not received an active {platformLabel(ws.platform)} contest slate for this sport yet.
            <p className="sbme-dhub-muted" style={{ marginTop: 10, fontSize: 11 }}>
              Optimizer unavailable until a DFS slate is available.
            </p>
            {scheduleEvents.length > 0 && (
              <div className="sbme-dhub-sched">
                <div className="sbme-dhub-sched-label">UPCOMING SCHEDULE</div>
                <p className="sbme-dhub-sched-note">{SCHEDULE_INTEL_NOTE}</p>
                <div className="sbme-dhub-sched-chips">
                  {scheduleEvents.slice(0, 24).map((e) => (
                    <div key={e.id} className="sbme-dhub-sched-chip">
                      <div>{scheduleMatchupLabel(e)}</div>
                      <div className="sbme-dhub-sched-time">{formatKickoffEt(e.start_time)}</div>
                    </div>
                  ))}
                </div>
              </div>
            )}
            {marketEvents.length > 0 && (
              <div className="sbme-dhub-sched" style={{ marginTop: 16 }}>
                <div className="sbme-dhub-sched-label">MARKET CONTEXT</div>
                <p className="sbme-dhub-sched-note">
                  {marketEvents.length} game{marketEvents.length !== 1 ? "s" : ""} currently have SportsGameOdds market data in cache. This is not a DFS contest slate.
                </p>
              </div>
            )}
          </div>
        ) : (
          <>
            <p className="sbme-dhub-kicker">Slate Directory</p>
            <div className="sbme-dhub-slate-dir">
              <table className="sbme-dhub-slate-table">
                <thead>
                  <tr>
                    <th>Slate</th>
                    <th>Platform</th>
                    <th>Lock / Start</th>
                    <th>Games</th>
                    <th>Players</th>
                    <th>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {slates.map((s) => {
                    const st = getSlateDisplayStatus(s);
                    const isSelected = s.id === ws.slateId;
                    return (
                      <tr
                        key={s.id}
                        className={`sbme-dhub-slate-row${isSelected ? " is-selected" : ""}${st === "STALE" ? " is-stale" : ""}`}
                        onClick={() => ws.setSlateId(s.id)}
                      >
                        <td>
                          <span className="sbme-dhub-gold">{s.slate_name}</span>
                          <span className="sbme-dhub-muted" style={{ marginLeft: 6, fontSize: 10 }}>{s.sport}</span>
                        </td>
                        <td>{platformLabel(s.platform)}</td>
                        <td>{formatSlateLockTime(s.start_time)}</td>
                        <td>{s.game_count > 0 ? s.game_count : "—"}</td>
                        <td>{s.player_count > 0 ? s.player_count : "—"}</td>
                        <td><span className={statusPillClass(st)}>{st}</span></td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </>
        )}

        {selectedSlate && (
          <section className="sbme-dhub-slate-intel">
            <div>
              <h2 className="sbme-dhub-slate-title">{selectedSlate.slate_name}</h2>
              <p className="sbme-dhub-slate-sub">
                {ws.sport} · {platformLabel(selectedSlate.platform)} · Locks {formatSlateLockTime(selectedSlate.start_time)}
                {selectedStatus && (
                  <> · <span className={statusPillClass(selectedStatus)}>{selectedStatus}</span></>
                )}
              </p>
              <div className="sbme-dhub-stat-grid">
                <div className="sbme-dhub-stat">
                  <div className="sbme-dhub-stat-label">Games</div>
                  <div className="sbme-dhub-stat-val">{selectedSlate.game_count > 0 ? selectedSlate.game_count : "—"}</div>
                </div>
                <div className="sbme-dhub-stat">
                  <div className="sbme-dhub-stat-label">Players</div>
                  <div className="sbme-dhub-stat-val">
                    {players.length > 0 ? players.length : selectedSlate.player_count > 0 ? selectedSlate.player_count : "—"}
                  </div>
                </div>
                <div className="sbme-dhub-stat">
                  <div className="sbme-dhub-stat-label">SB Projections</div>
                  <div className="sbme-dhub-stat-val">
                    {projectionCoverage
                      ? projectionCoverage.withProj === projectionCoverage.total
                        ? `${projectionCoverage.withProj} / ${projectionCoverage.total}`
                        : `${projectionCoverage.withProj} / ${projectionCoverage.total} (partial)`
                      : loading ? "…" : "—"}
                  </div>
                </div>
                <div className="sbme-dhub-stat">
                  <div className="sbme-dhub-stat-label">Optimal%</div>
                  <div className="sbme-dhub-stat-val">
                    {optPctStatus === "COMPLETE" ? "Available"
                      : optPctStatus === "LOCKED" ? "Locked slate"
                      : optPctStatus === "RUNNING" || optPctStatus === "QUEUED" ? "Calculating…"
                      : optPctStatus === "FAILED" ? "Unavailable"
                      : "Not run"}
                  </div>
                </div>
                <div className="sbme-dhub-stat">
                  <div className="sbme-dhub-stat-label">Pool Updated</div>
                  <div className="sbme-dhub-stat-val" style={{ fontSize: 11 }}>
                    {generatedAt ? new Date(generatedAt).toLocaleTimeString() : "—"}
                  </div>
                </div>
              </div>
              {metaError && (
                <p className="sbme-dhub-muted" style={{ fontSize: 11, marginTop: 10 }}>{metaError}</p>
              )}
            </div>
            <div className="sbme-dhub-actions">
              <button type="button" className="sbme-dhub-btn sbme-dhub-btn--gold" onClick={() => router.push(optimizerHref)}>
                <Send size={14} /> Open Optimizer
              </button>
              <Link href="/ai" className="sbme-dhub-btn">
                <Zap size={14} /> SB ME Intelligence
              </Link>
            </div>
          </section>
        )}

        {ws.slateId && slates.length > 0 && (
          <>
            <div className="sbme-dhub-toolbar">
              {positionOptions.map((pos) => (
                <button
                  key={pos}
                  type="button"
                  className={`sbme-dhub-pos-chip${posFilter === pos ? " is-on" : ""}`}
                  onClick={() => setPosFilter(pos)}
                >
                  {pos}
                </button>
              ))}
              <select
                className="sbme-dhub-select"
                style={{ width: "auto", minWidth: 100 }}
                value={teamFilter}
                onChange={(e) => setTeamFilter(e.target.value)}
              >
                <option value="">All teams</option>
                {teamOptions.map((t) => (
                  <option key={t} value={t}>{t}</option>
                ))}
              </select>
              <div className="sbme-dhub-search">
                <Search size={14} className="sbme-dhub-search-icon" />
                <input
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  placeholder="Search players…"
                />
              </div>
              <span className="sbme-dhub-count">
                {filtered.length} player{filtered.length !== 1 ? "s" : ""}
                {filtered.length > TABLE_LIMIT ? ` · showing ${TABLE_LIMIT}` : ""}
              </span>
            </div>

            <div className="sbme-dhub-table-wrap">
              {loading ? (
                <div className="sbme-dhub-loading"><Loader2 size={28} className="animate-spin" /></div>
              ) : players.length === 0 ? (
                <div className="sbme-dhub-empty">
                  <strong>No player pool</strong>
                  {metaError
                    ? metaError
                    : "This slate has no published player data yet, or the pool is below the minimum size."}
                </div>
              ) : filtered.length === 0 ? (
                <div className="sbme-dhub-empty">No players match the current filters.</div>
              ) : (
                <table className="sbme-dhub-table">
                  <thead>
                    <tr>
                      {["Player", "Pos", "Team", "Opp", "Salary", "FPPG", "SB Proj", "My Proj", "Value", "SB Own%", "Lev", "Opt%", "Ceil", "Floor", "Map", ""].map((h) => (
                        <th key={h || "act"}>{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {filtered.slice(0, TABLE_LIMIT).map((p) => {
                      const locked = ws.lockedIds.includes(p.name);
                      const excluded = ws.excludedIds.includes(p.name);
                      const liked = ws.likedIds.includes(p.name);
                      const myProj = ws.projOverrides[p.name];
                      const optPct = optPctMap[normPlayerName(p.name)] ?? null;
                      const hasProj = p.projection_source !== "UNAVAILABLE";
                      return (
                        <tr
                          key={p.id}
                          className={`${locked ? "is-locked" : ""}${excluded ? " is-excluded" : ""}`}
                          onClick={() => setDrawerPlayer(p)}
                        >
                          <td>
                            <div className="sbme-dhub-player">
                              <PlayerAvatar player={{ name: p.name, player_id: p.id }} size={22} />
                              {p.name}
                              {liked && <Heart size={11} style={{ color: "#c9a84c", fill: "#c9a84c" }} />}
                            </div>
                          </td>
                          <td className="sbme-dhub-gold" style={{ fontSize: 10, textTransform: "uppercase" }}>{p.roster_position || "—"}</td>
                          <td>
                            <span style={{ display: "inline-flex", alignItems: "center", gap: 4 }}>
                              <TeamLogo team={{ abbreviation: p.team, name: p.team }} size={16} />
                              {p.team || "—"}
                            </span>
                          </td>
                          <td className="sbme-dhub-muted">{p.opponent || "—"}</td>
                          <td>{p.salary ? `$${p.salary.toLocaleString()}` : "—"}</td>
                          <td className="sbme-dhub-muted">{p.fppg != null ? p.fppg.toFixed(1) : "—"}</td>
                          <td className={hasProj ? "sbme-dhub-gold" : "sbme-dhub-na"}>{fmtProj(p)}</td>
                          <td>
                            <input
                              type="number"
                              step="0.1"
                              value={myProj != null ? myProj : hasProj ? p.projected_fp : ""}
                              placeholder={hasProj ? "" : "N/A"}
                              onChange={(e) => {
                                const v = e.target.value;
                                if (v === "") return;
                                const n = Number(v);
                                if (Number.isFinite(n)) ws.setProjOverride(p.name, n);
                              }}
                              onClick={(e) => e.stopPropagation()}
                              style={{
                                width: 52,
                                padding: "3px 5px",
                                borderRadius: 6,
                                fontSize: 11,
                                background: "rgba(10,15,36,0.9)",
                                border: "1px solid rgba(30,41,59,0.95)",
                                color: "#f0f6fc",
                                outline: "none",
                              }}
                            />
                          </td>
                          <td className={hasProj ? "sbme-dhub-gold" : "sbme-dhub-na"}>{fmtValue(p)}</td>
                          <td className="sbme-dhub-muted">{fmtNum(p.sbme_ownership_pct, 1)}{p.sbme_ownership_pct != null ? "%" : ""}</td>
                          <td className={p.leverage == null ? "sbme-dhub-muted" : p.leverage > 0 ? "sbme-dhub-lev-up" : "sbme-dhub-lev-down"}>
                            {fmtNum(p.leverage, 1)}
                          </td>
                          <td className={optPct != null ? "sbme-dhub-gold" : "sbme-dhub-na"}>
                            {optPct != null
                              ? `${optPct.toFixed(1)}%`
                              : optPctStatus === "LOCKED"
                                ? "—"
                                : optPctStatus === "RUNNING" || optPctStatus === "QUEUED"
                                  ? "…"
                                  : "—"}
                          </td>
                          <td className="sbme-dhub-muted">{hasProj ? fmtNum(p.ceiling, 1) : "—"}</td>
                          <td className="sbme-dhub-muted">{hasProj ? fmtNum(p.floor, 1) : "—"}</td>
                          <td style={{ fontSize: 10, color: p.mapping_status === "MATCHED" ? "#4ade80" : "#64748b" }}>
                            {p.mapping_status || "—"}
                          </td>
                          <td>
                            <div style={{ display: "flex", gap: 4 }} onClick={(e) => e.stopPropagation()}>
                              <IconBtn title="Lock" active={locked} onClick={() => ws.toggleLock(p.name)}><Lock size={13} /></IconBtn>
                              <IconBtn title="Exclude" active={excluded} onClick={() => ws.toggleExclude(p.name)}><Ban size={13} /></IconBtn>
                              <IconBtn title="Like" active={liked} onClick={() => ws.toggleLike(p.name)}><Heart size={13} /></IconBtn>
                            </div>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              )}
            </div>
          </>
        )}

        {!ws.slateId && slates.length > 0 && (
          <div className="sbme-dhub-empty">
            <strong>Select a slate</strong>
            Choose a sport, platform, and slate above to inspect the player pool and projections.
          </div>
        )}

        <Link href="/ai" className="sbme-dhub-intel">
          <span className="sbme-dhub-intel-icon"><Zap size={18} /></span>
          <span className="sbme-dhub-intel-copy">
            <span className="sbme-dhub-intel-title">SB ME Intelligence™</span>
            <p>Ask about DFS slate metrics, projections, and market context — uses the canonical conversation context.</p>
          </span>
          <ChevronRight size={18} style={{ color: "#c9a84c", flexShrink: 0 }} />
        </Link>
      </div>

      {drawerPlayer && (
        <div className="sbme-dhub-drawer-backdrop" onClick={() => setDrawerPlayer(null)}>
          <div className="sbme-dhub-drawer" onClick={(e) => e.stopPropagation()}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <h2>{drawerPlayer.name}</h2>
              <button type="button" onClick={() => setDrawerPlayer(null)} style={{ background: "none", border: "none", color: "#94a3b8", cursor: "pointer" }}>
                <X size={18} />
              </button>
            </div>
            <div className="sbme-dhub-drawer-grid">
              <DrawerStat label="Matchup" value={`${drawerPlayer.team} vs ${drawerPlayer.opponent || "—"}`} />
              <DrawerStat label="Position" value={drawerPlayer.roster_position || "—"} />
              <DrawerStat label="Salary" value={drawerPlayer.salary ? `$${drawerPlayer.salary.toLocaleString()}` : "—"} />
              <DrawerStat label="FPPG" value={drawerPlayer.fppg != null ? drawerPlayer.fppg.toFixed(1) : "—"} />
              <DrawerStat label="SB Projection" value={fmtProj(drawerPlayer)} />
              <DrawerStat label="Value" value={fmtValue(drawerPlayer)} />
              <DrawerStat label="SB Own%" value={drawerPlayer.sbme_ownership_pct != null ? `${fmtNum(drawerPlayer.sbme_ownership_pct, 1)}%` : "—"} />
              <DrawerStat label="Leverage" value={fmtNum(drawerPlayer.leverage, 1)} />
              <DrawerStat label="Ceiling / Floor" value={drawerPlayer.projection_source !== "UNAVAILABLE" ? `${fmtNum(drawerPlayer.ceiling, 0)} / ${fmtNum(drawerPlayer.floor, 0)}` : "—"} />
              <DrawerStat label="Projection Source" value={drawerPlayer.projection_source || "—"} />
              <DrawerStat label="Game Total" value={drawerPlayer.sbme_game_total != null ? String(drawerPlayer.sbme_game_total) : "—"} />
              <DrawerStat label="Implied Team Total" value={drawerPlayer.sbme_implied_team_total != null ? String(drawerPlayer.sbme_implied_team_total) : "—"} />
              {drawerPlayer.sgo_prop_lines?.hits_line != null && (
                <DrawerStat label="Hits O/U" value={String(drawerPlayer.sgo_prop_lines.hits_line)} />
              )}
              {drawerPlayer.sgo_prop_lines?.hr_line != null && (
                <DrawerStat label="HR O/U" value={String(drawerPlayer.sgo_prop_lines.hr_line)} />
              )}
              {drawerPlayer.sgo_prop_lines?.strikeouts_line != null && (
                <DrawerStat label="K O/U" value={String(drawerPlayer.sgo_prop_lines.strikeouts_line)} />
              )}
            </div>
            {drawerPlayer.sbme_environment_note && (
              <p className="sbme-dhub-muted" style={{ fontSize: 10, marginBottom: 12 }}>{drawerPlayer.sbme_environment_note}</p>
            )}
            <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginBottom: 16 }}>
              <ActionBtn label={ws.lockedIds.includes(drawerPlayer.name) ? "Unlock" : "Lock"} icon={<Lock size={14} />} onClick={() => ws.toggleLock(drawerPlayer.name)} />
              <ActionBtn label={ws.excludedIds.includes(drawerPlayer.name) ? "Un-exclude" : "Exclude"} icon={<Ban size={14} />} onClick={() => ws.toggleExclude(drawerPlayer.name)} />
              <ActionBtn label={ws.likedIds.includes(drawerPlayer.name) ? "Unlike" : "Like"} icon={<Heart size={14} />} onClick={() => ws.toggleLike(drawerPlayer.name)} />
              <ActionBtn label="Open Optimizer" icon={<Send size={14} />} gold onClick={() => router.push(optimizerHref)} />
            </div>
            <LastFive
              player={{
                name: drawerPlayer.name,
                player_id: drawerPlayer.sgo_player_id || drawerPlayer.id,
                sgo_player_id: drawerPlayer.sgo_player_id,
                team: drawerPlayer.team,
                sport: ws.sport,
                slate_id: ws.slateId ?? undefined,
              }}
              platform={ws.platform}
            />
          </div>
        </div>
      )}
    </AppShell>
  );
}

function IconBtn({ title, active, onClick, children }: { title: string; active: boolean; onClick: () => void; children: React.ReactNode }) {
  return (
    <button type="button" title={title} onClick={onClick} className={`sbme-dhub-icon-btn${active ? " is-on" : ""}`}>
      {children}
    </button>
  );
}

function DrawerStat({ label, value }: { label: string; value: string }) {
  return (
    <div className="sbme-dhub-drawer-stat">
      <div className="sbme-dhub-drawer-stat-label">{label}</div>
      <div className="sbme-dhub-drawer-stat-val">{value}</div>
    </div>
  );
}

function ActionBtn({ label, icon, onClick, gold: isGold }: { label: string; icon: React.ReactNode; onClick: () => void; gold?: boolean }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`sbme-dhub-btn${isGold ? " sbme-dhub-btn--gold" : ""}`}
    >
      {icon}{label}
    </button>
  );
}
