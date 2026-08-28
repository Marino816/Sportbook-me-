"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { SBEvent, normalizeEvents } from "./sbevent";
import { getApiBaseUrl } from "./api-base-url";
import { TeamLogo } from "./assets";

/**
 * Shared live-score layer built on the canonical SGO event model.
 *
 * ONE fetch per league serves every page (module-level cache + in-flight
 * dedup). Auto-refreshes on a short interval while any game is LIVE, and a
 * much longer interval otherwise — respecting SGO account limits and the
 * backend Redis cache.
 */

const API_BASE = getApiBaseUrl(typeof process !== "undefined" ? process.env.NEXT_PUBLIC_API_URL : undefined);
const LIVE_INTERVAL_MS = 90_000;
const IDLE_INTERVAL_MS = 180_000;

const cache: Record<string, { events: SBEvent[]; lastFetch: number; hasLive: boolean }> = {};
const inflight: Record<string, Promise<SBEvent[]> | undefined> = {};

function getToken(): string | null {
  if (typeof window === "undefined") return null;
  try { return localStorage.getItem("sbme_dfs_token"); } catch { return null; }
}

async function fetchLeague(league: string): Promise<SBEvent[]> {
  if (inflight[league]) return inflight[league];
  inflight[league] = (async () => {
    const token = getToken();
    const res = await fetch(`${API_BASE}/sgo/events?league=${league}`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const json = await res.json();
    return normalizeEvents(json?.data);
  })();
  try { return await inflight[league]; } finally { delete inflight[league]; }
}

export interface LiveScoresResult {
  events: SBEvent[];
  loading: boolean;
  error: string | null;
  hasLive: boolean;
  lastFetch: number | null;
  refresh: () => void;
}

export function useLiveScores(league: string): LiveScoresResult {
  const [events, setEvents] = useState<SBEvent[]>(() => cache[league]?.events ?? []);
  const [loading, setLoading] = useState<boolean>(() => !cache[league]);
  const [error, setError] = useState<string | null>(null);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const leagueRef = useRef(league);

  const refresh = useCallback(async () => {
    try {
      const evs = await fetchLeague(leagueRef.current);
      const hasLive = evs.some((e) => e.status === "LIVE");
      cache[leagueRef.current] = { events: evs, lastFetch: Date.now(), hasLive };
      setEvents(evs);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load scores");
    } finally {
      setLoading(false);
    }
  }, []); // stable reference — reads league from ref

  // Sync state when league changes: swap to cached data immediately,
  // then fetch fresh. Prevents stale events from previous sport lingering.
  useEffect(() => {
    leagueRef.current = league;
    const entry = cache[league];
    if (entry) {
      setEvents(entry.events);
      setError(null);
      setLoading(false);
    } else {
      setEvents([]);
      setError(null);
      setLoading(true);
    }
    // Always refresh on league switch
    refresh();
  }, [league, refresh]);

  useEffect(() => {
    let cancelled = false;

    const schedule = (delay: number) => {
      if (timerRef.current) clearTimeout(timerRef.current);
      timerRef.current = setTimeout(async () => {
        await refresh();
        if (cancelled) return;
        const c = cache[league];
        schedule(c?.hasLive ? LIVE_INTERVAL_MS : IDLE_INTERVAL_MS);
      }, delay);
    };

    if (!cache[league]) {
      setLoading(true);
      refresh();
    }
    const initial = cache[league]?.hasLive ? LIVE_INTERVAL_MS : IDLE_INTERVAL_MS;
    schedule(initial);

    return () => {
      cancelled = true;
      if (timerRef.current) clearTimeout(timerRef.current);
    };
  }, [league, refresh]);

  return {
    events,
    loading,
    error,
    hasLive: events.some((e) => e.status === "LIVE"),
    lastFetch: cache[league]?.lastFetch ?? null,
    refresh,
  };
}

/* ── Sport-aware status helpers ──────────────────────────────── */

export type GameState = "UPCOMING" | "LIVE" | "FINAL";

export function gameState(evt: SBEvent | null | undefined): GameState {
  const s = (evt?.status || "").toUpperCase();
  if (s === "LIVE" || s === "IN_PROGRESS") return "LIVE";
  if (s === "FINAL" || s === "COMPLETED" || s === "FINALIZED") return "FINAL";
  return "UPCOMING";
}

/** Sport-aware human-readable period (falls back to status_display / "LIVE"). */
export function periodLabel(evt: SBEvent | null | undefined): string {
  if (!evt) return "";
  const league = (evt.league || evt.sport || "").toUpperCase();
  const display = evt.status_display || "";
  const period = evt.period || "";

  // Prefer SGO's human-readable status_display (already sport-aware).
  if (display && !/^(Upcoming|Scheduled)$/i.test(display)) return display;

  if (period) {
    // Coded periods: "6i" (6th inning), "2q" (2nd quarter), "3p" (3rd period)
    const m = period.match(/^(\d+)([a-z]+)$/i);
    if (m) {
      const n = m[1];
      const unit = m[2].toLowerCase();
      if (unit === "i") return `${n}${ordinal(n)} Inning`;
      if (unit === "q") return `${n}${ordinal(n)} Quarter`;
      if (unit === "p") return `${n}${ordinal(n)} Period`;
      if (unit === "h") return `${n}${ordinal(n)} Half`;
    }
    return period;
  }
  return "";
}

function ordinal(n: string): string {
  const num = parseInt(n, 10);
  if (num === 1) return "st";
  if (num === 2) return "nd";
  if (num === 3) return "rd";
  return "th";
}

/* ── UI components ───────────────────────────────────────────── */

export function GameStatusBadge({ evt }: { evt: SBEvent | null | undefined }) {
  const state = gameState(evt);
  const label = state === "LIVE" ? "LIVE" : state === "FINAL" ? "FINAL" : "UPCOMING";
  const color = state === "LIVE" ? "#ef4444" : state === "FINAL" ? "#64748b" : "#94a3b8";
  return (
    <span style={{ display: "inline-flex", alignItems: "center", gap: 5, fontSize: 10, fontWeight: 800, letterSpacing: 0.5, color, textTransform: "uppercase" }}>
      {state === "LIVE" && <span style={{ width: 6, height: 6, borderRadius: "50%", background: "#ef4444", animation: "sbme-pulse 1.5s ease-in-out infinite" }} />}
      {label}
    </span>
  );
}

export function ScoreBadge({ evt, size = "md" }: { evt: SBEvent | null | undefined; size?: "sm" | "md" }) {
  if (!evt) return null;
  const state = gameState(evt);
  const home = evt.home_score;
  const away = evt.away_score;
  const showScore = state !== "UPCOMING" && home != null && away != null;
  const per = periodLabel(evt);
  const logo = size === "md" ? 20 : 16;
  const teamSize = size === "md" ? 13 : 11;

  return (
    <div style={{ display: "inline-flex", alignItems: "center", gap: 8, padding: "6px 10px", borderRadius: 10, background: "#0a0f24", border: state === "LIVE" ? "1px solid #ef444450" : "1px solid #1e293b", whiteSpace: "nowrap" }}>
      <TeamLogo team={evt.away_team} size={logo} />
      <span style={{ fontSize: teamSize, color: "#94a3b8" }}>{evt.away_team?.abbreviation || "AWY"}</span>
      {showScore && <span style={{ fontSize: size === "md" ? 16 : 13, fontWeight: 800, color: "#f0f6fc" }}>{away}</span>}

      <span style={{ color: "#334155", fontWeight: 700 }}>–</span>

      {showScore && <span style={{ fontSize: size === "md" ? 16 : 13, fontWeight: 800, color: "#f0f6fc" }}>{home}</span>}
      <span style={{ fontSize: teamSize, color: "#94a3b8" }}>{evt.home_team?.abbreviation || "HOM"}</span>
      <TeamLogo team={evt.home_team} size={logo} />

      {state === "LIVE" && (
        <span style={{ display: "inline-flex", alignItems: "center", gap: 4, fontSize: 10, fontWeight: 800, color: "#ef4444", textTransform: "uppercase" }}>
          <span style={{ width: 5, height: 5, borderRadius: "50%", background: "#ef4444", animation: "sbme-pulse 1.5s ease-in-out infinite" }} />
          LIVE
          {per ? <span style={{ color: "#f87171" }}>• {per}</span> : null}
        </span>
      )}
      {state === "FINAL" && <span style={{ fontSize: 10, fontWeight: 700, color: "#64748b", textTransform: "uppercase" }}>FINAL</span>}
    </div>
  );
}
