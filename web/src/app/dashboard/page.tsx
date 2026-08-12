"use client";

import Link from "next/link";
import Image from "next/image";
import { useAuth } from "@/lib/auth";
import { Flame, MessageCircle, List, TrendingUp, Activity, Clock } from "lucide-react";
import { useEffect, useState } from "react";
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

interface SgoPropLine {
  bookmaker: string;
  line: number | null;
  over_price: number | null;
  under_price: number | null;
}

interface SgoPropMarket {
  market: string;
  lines: SgoPropLine[];
}

interface SgoPlayerProps {
  player_id: string;
  markets: SgoPropMarket[];
}

const QUICK = [
  { icon: Flame, label: "Build Lineup", href: "/optimizer" },
  { icon: TrendingUp, label: "Market Tools", href: "/market-tools" },
  { icon: List, label: "Saved Lineups", href: "/lineups" },
  { icon: MessageCircle, label: "Ask SB ME AI", href: "/ai" },
];

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

function isCompleted(status: string): boolean {
  const s = status?.toUpperCase() || "";
  return s === "COMPLETED" || s === "FINAL" || s === "FINISHED" || s === "CLOSED";
}

function formatTime(iso: string | null): string {
  if (!iso) return "TBD";
  try {
    const d = new Date(iso);
    return d.toLocaleTimeString([], { hour: "numeric", minute: "2-digit", timeZoneName: "short" });
  } catch {
    return iso;
  }
}

export default function DashboardPage() {
  const { user } = useAuth();
  const name = user?.email?.split("@")[0] || "Player";
  const [activeLeague, setActiveLeague] = useState<League>("MLB");
  const [events, setEvents] = useState<SgoEvent[]>([]);
  const [loading, setLoading] = useState(true);

  // Load events for active league
  useEffect(() => {
    let cancelled = false;
    async function load() {
      setLoading(true);
      const data = await sgoFetch<{ events: SgoEvent[]; league: string; count: number }>(
        `/events?league=${activeLeague}`
      );
      if (!cancelled) {
        setEvents(data?.events ?? []);
        setLoading(false);
      }
    }
    load();
    return () => { cancelled = true; };
  }, [activeLeague]);

  // Split events into live and upcoming
  const liveEvents = events.filter((e) => isLive(e.status));
  const upcomingEvents = events.filter((e) => !isLive(e.status) && !isCompleted(e.status));
  const completedEvents = events.filter((e) => isCompleted(e.status));

  // Featured player props section — uses the first upcoming event's props
  const [featuredProps, setFeaturedProps] = useState<SgoPlayerProps[]>([]);
  const [propsLoading, setPropsLoading] = useState(false);
  const [propsEventId, setPropsEventId] = useState<string | null>(null);

  useEffect(() => {
    const firstUpcoming = upcomingEvents[0];
    if (!firstUpcoming || firstUpcoming.event_id === propsEventId) return;
    let cancelled = false;
    async function loadProps() {
      setPropsLoading(true);
      setPropsEventId(firstUpcoming.event_id);
      const data = await sgoFetch<{
        event_id: string; players: SgoPlayerProps[]; player_count: number; prop_count: number;
      }>(`/events/${firstUpcoming.event_id}/props`);
      if (!cancelled) {
        setFeaturedProps(data?.players?.slice(0, 6) ?? []);
        setPropsLoading(false);
      }
    }
    loadProps();
    return () => { cancelled = true; };
  }, [upcomingEvents]);

  // Best odds for first live event (or first upcoming)
  const [bestOdds, setBestOdds] = useState<{
    event_id: string; books: SgoBook[]; consensus?: SgoBook;
  } | null>(null);
  const [oddsLoading, setOddsLoading] = useState(false);
  const [oddsEventId, setOddsEventId] = useState<string | null>(null);

  useEffect(() => {
    const target = liveEvents[0] || upcomingEvents[0];
    if (!target || target.event_id === oddsEventId) return;
    let cancelled = false;
    async function loadOdds() {
      setOddsLoading(true);
      setOddsEventId(target.event_id);
      const data = await sgoFetch<{
        event_id: string; books: SgoBook[]; book_count: number; consensus?: SgoBook;
      }>(`/events/${target.event_id}/odds`);
      if (!cancelled) {
        setBestOdds(data ?? null);
        setOddsLoading(false);
      }
    }
    loadOdds();
    return () => { cancelled = true; };
  }, [liveEvents, upcomingEvents]);

  const greeting =
    new Date().getHours() < 12
      ? "morning"
      : new Date().getHours() < 17
        ? "afternoon"
        : "evening";

  return (
    <div style={{ maxWidth: 1200, margin: "0 auto", padding: "40px 24px", color: "#f0f6fc" }}>
      {/* Hero */}
      <div style={{ textAlign: "center", marginBottom: 40 }}>
        <Image src="/logo.png" alt="SB ME DFS.AI" width={200} height={105} priority style={{ margin: "0 auto" }} />
        <p style={{ fontSize: 20, fontWeight: 700, color: "#94a3b8", marginTop: 16 }}>
          Good {greeting}, {name}.
        </p>
        <p style={{ fontSize: 16, color: "#64748b", marginTop: 4 }}>
          SB ME Intelligent AI™ is ready.
        </p>
        {user && (
          <span
            style={{
              display: "inline-block", marginTop: 12, padding: "6px 16px", borderRadius: 20,
              background: "rgba(201,168,76,0.1)", border: "1px solid rgba(201,168,76,0.3)",
              color: "#c9a84c", fontSize: 13, fontWeight: 600,
            }}
          >
            {user.plan || "Free"} Plan
          </span>
        )}
      </div>

      {/* Quick Actions */}
      <h2 style={{ fontSize: 13, fontWeight: 700, color: "#64748b", textTransform: "uppercase", letterSpacing: 2, marginBottom: 16 }}>
        Quick Actions
      </h2>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(160px, 1fr))", gap: 12, marginBottom: 40 }}>
        {QUICK.map((a, i) => {
          const Icon = a.icon;
          return (
            <Link
              key={i} href={a.href}
              style={{
                background: "#0a0f24", borderRadius: 16, border: "1px solid #1e293b",
                padding: "24px 16px", textAlign: "center", textDecoration: "none",
                display: "flex", flexDirection: "column", alignItems: "center", gap: 10,
              }}
            >
              <Icon size={28} color="#c9a84c" />
              <span style={{ fontSize: 13, fontWeight: 600, color: "#94a3b8", lineHeight: 1.3 }}>{a.label}</span>
            </Link>
          );
        })}
      </div>

      {/* ─── SPORT TABS ─── */}
      <div style={{ display: "flex", gap: 6, marginBottom: 24, flexWrap: "wrap" }}>
        {LEAGUES.map((lg) => (
          <button
            key={lg}
            onClick={() => setActiveLeague(lg)}
            style={{
              padding: "8px 18px", borderRadius: 10, fontSize: 13, fontWeight: 700,
              background: activeLeague === lg ? "rgba(201,168,76,0.1)" : "#0a0f24",
              border: activeLeague === lg ? "1px solid #c9a84c" : "1px solid #1e293b",
              color: activeLeague === lg ? "#c9a84c" : "#94a3b8",
              cursor: "pointer",
            }}
          >
            {lg}
          </button>
        ))}
      </div>

      {/* ─── LIVE GAMES ─── */}
      <h2 style={{ fontSize: 13, fontWeight: 700, color: "#64748b", textTransform: "uppercase", letterSpacing: 2, marginBottom: 14 }}>
        {liveEvents.length > 0 ? "● LIVE GAMES" : "UPCOMING GAMES"}
      </h2>

      {loading ? (
        <LoadingCard />
      ) : liveEvents.length === 0 && upcomingEvents.length === 0 ? (
        <EmptyCard message="Data currently unavailable" />
      ) : (
        <div style={{ display: "grid", gap: 12, marginBottom: 36 }}>
          {/* LIVE events first */}
          {liveEvents.map((evt) => (
            <EventCard key={evt.event_id} event={evt} />
          ))}
          {/* Upcoming events */}
          {upcomingEvents.map((evt) => (
            <EventCard key={evt.event_id} event={evt} />
          ))}
        </div>
      )}

      {/* ─── BEST AVAILABLE ODDS ─── */}
      <h2 style={{ fontSize: 13, fontWeight: 700, color: "#64748b", textTransform: "uppercase", letterSpacing: 2, marginBottom: 14 }}>
        BEST AVAILABLE ODDS
      </h2>
      {oddsLoading ? (
        <LoadingCard />
      ) : bestOdds && bestOdds.books.length > 0 ? (
        <BestOddsPanel odds={bestOdds} />
      ) : (
        <EmptyCard message="Data currently unavailable" />
      )}

      {/* ─── FEATURED PLAYER PROPS ─── */}
      <h2 style={{ fontSize: 13, fontWeight: 700, color: "#64748b", textTransform: "uppercase", letterSpacing: 2, marginTop: 36, marginBottom: 14 }}>
        FEATURED PLAYER PROPS
      </h2>
      {propsLoading ? (
        <LoadingCard />
      ) : featuredProps.length > 0 ? (
        <FeaturedPropsPanel players={featuredProps} />
      ) : (
        <EmptyCard message="Data currently unavailable" />
      )}

      {/* ─── RECENT RESULTS ─── */}
      {completedEvents.length > 0 && (
        <>
          <h2 style={{ fontSize: 13, fontWeight: 700, color: "#64748b", textTransform: "uppercase", letterSpacing: 2, marginTop: 36, marginBottom: 14 }}>
            RECENT RESULTS
          </h2>
          <div style={{ display: "grid", gap: 12, marginBottom: 36 }}>
            {completedEvents.slice(0, 5).map((evt) => (
              <CompletedCard key={evt.event_id} event={evt} />
            ))}
          </div>
        </>
      )}
    </div>
  );
}

/* ── Sub-Components ── */

function EventCard({ event }: { event: SgoEvent }) {
  const live = isLive(event.status);
  return (
    <div
      style={{
        background: live ? "rgba(201,168,76,0.05)" : "#0a0f24",
        borderRadius: 14, border: live ? "1px solid rgba(201,168,76,0.2)" : "1px solid #1e293b",
        padding: "16px 20px", display: "flex", justifyContent: "space-between", alignItems: "center",
      }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
        {/* Status badge */}
        {live && (
          <span style={{
            padding: "3px 10px", borderRadius: 6, fontSize: 10, fontWeight: 800,
            background: "rgba(239,68,68,0.15)", color: "#ef4444", textTransform: "uppercase",
            flexShrink: 0,
          }}>
            ● LIVE
          </span>
        )}
        {!live && event.start_time && (
          <span style={{
            padding: "3px 10px", borderRadius: 6, fontSize: 10, fontWeight: 600,
            background: "rgba(100,116,139,0.12)", color: "#94a3b8", flexShrink: 0,
            display: "flex", alignItems: "center", gap: 4,
          }}>
            <Clock size={11} /> {formatTime(event.start_time)}
          </span>
        )}
        {/* Matchup */}
        <div>
          <div style={{ fontSize: 15, fontWeight: 700, color: "#f0f6fc" }}>
            <span style={{ color: live ? "#c9a84c" : "#f0f6fc" }}>{event.away_team.abbreviation || event.away_team.name}</span>
            {" @ "}
            <span style={{ color: live ? "#c9a84c" : "#f0f6fc" }}>{event.home_team.abbreviation || event.home_team.name}</span>
          </div>
        </div>
      </div>
      {/* Score if live */}
      {live && (event.home_score != null || event.away_score != null) && (
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <span style={{ fontSize: 18, fontWeight: 800, color: "#c9a84c" }}>
            {event.away_score ?? 0} – {event.home_score ?? 0}
          </span>
          {event.period && (
            <span style={{ fontSize: 11, color: "#64748b" }}>{event.period}</span>
          )}
        </div>
      )}
    </div>
  );
}

function CompletedCard({ event }: { event: SgoEvent }) {
  return (
    <div style={{
      background: "#0a0f24", borderRadius: 14, border: "1px solid #1e293b",
      padding: "16px 20px", display: "flex", justifyContent: "space-between", alignItems: "center",
    }}>
      <div style={{ fontSize: 15, fontWeight: 600, color: "#94a3b8" }}>
        {event.away_team.abbreviation || event.away_team.name} @ {event.home_team.abbreviation || event.home_team.name}
      </div>
      <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
        <span style={{ fontSize: 18, fontWeight: 800, color: "#f0f6fc" }}>
          {event.away_score ?? "—"} – {event.home_score ?? "—"}
        </span>
        <span style={{
          padding: "3px 8px", borderRadius: 4, fontSize: 10, fontWeight: 700,
          background: "rgba(100,116,139,0.15)", color: "#64748b", textTransform: "uppercase",
        }}>
          FINAL
        </span>
      </div>
    </div>
  );
}

function BestOddsPanel({ odds }: { odds: { event_id: string; books: SgoBook[]; consensus?: SgoBook } }) {
  const topBooks = odds.books.slice(0, 6);

  // Best moneyline home/away across books
  let bestMlHome = -Infinity, bestMlAway = -Infinity;
  let bestMlHomeBook = "", bestMlAwayBook = "";
  for (const b of odds.books) {
    if ((b.moneyline_home ?? -Infinity) > bestMlHome) { bestMlHome = b.moneyline_home!; bestMlHomeBook = b.bookmaker; }
    if ((b.moneyline_away ?? -Infinity) > bestMlAway) { bestMlAway = b.moneyline_away!; bestMlAwayBook = b.bookmaker; }
  }

  return (
    <div style={{
      background: "#0a0f24", borderRadius: 16, border: "1px solid #1e293b",
      padding: 20, overflow: "hidden",
    }}>
      {/* Best prices highlight */}
      <div style={{
        display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16, marginBottom: 18,
      }}>
        <div style={{ background: "rgba(201,168,76,0.06)", borderRadius: 10, padding: "12px 16px", textAlign: "center" }}>
          <div style={{ fontSize: 10, color: "#64748b", textTransform: "uppercase", marginBottom: 4 }}>Best Home ML</div>
          <div style={{ fontSize: 18, fontWeight: 800, color: "#c9a84c" }}>{fmtOdds(bestMlHome)}</div>
          <div style={{ fontSize: 11, color: "#64748b", marginTop: 2 }}>{bestMlHomeBook}</div>
        </div>
        <div style={{ background: "rgba(201,168,76,0.06)", borderRadius: 10, padding: "12px 16px", textAlign: "center" }}>
          <div style={{ fontSize: 10, color: "#64748b", textTransform: "uppercase", marginBottom: 4 }}>Best Away ML</div>
          <div style={{ fontSize: 18, fontWeight: 800, color: "#c9a84c" }}>{fmtOdds(bestMlAway)}</div>
          <div style={{ fontSize: 11, color: "#64748b", marginTop: 2 }}>{bestMlAwayBook}</div>
        </div>
      </div>

      {/* Bookmaker comparison table */}
      <div style={{ overflowX: "auto" }}>
        <div style={{
          display: "grid", gridTemplateColumns: "1.5fr 1fr 1fr 1fr", gap: 4,
          padding: "8px 0", borderBottom: "1px solid #1e293b",
          fontSize: 10, fontWeight: 700, color: "#64748b", textTransform: "uppercase",
        }}>
          <span>Bookmaker</span>
          <span style={{ textAlign: "center" }}>ML Home</span>
          <span style={{ textAlign: "center" }}>ML Away</span>
          <span style={{ textAlign: "center" }}>Spread/Total</span>
        </div>
        {topBooks.map((b, i) => (
          <div key={i} style={{
            display: "grid", gridTemplateColumns: "1.5fr 1fr 1fr 1fr", gap: 4,
            padding: "10px 0", borderBottom: "1px solid #1e293b20", alignItems: "center",
          }}>
            <span style={{ fontSize: 12, color: "#94a3b8", fontWeight: 500 }}>{b.bookmaker}</span>
            <span style={{
              fontSize: 13, fontWeight: b.moneyline_home === bestMlHome ? 800 : 500,
              color: b.moneyline_home === bestMlHome ? "#c9a84c" : "#f0f6fc",
              textAlign: "center",
            }}>
              {fmtOdds(b.moneyline_home)}
            </span>
            <span style={{
              fontSize: 13, fontWeight: b.moneyline_away === bestMlAway ? 800 : 500,
              color: b.moneyline_away === bestMlAway ? "#c9a84c" : "#f0f6fc",
              textAlign: "center",
            }}>
              {fmtOdds(b.moneyline_away)}
            </span>
            <span style={{ fontSize: 11, color: "#64748b", textAlign: "center" }}>
              {b.spread_home != null ? (b.spread_home > 0 ? "+" : "") + b.spread_home : "—"} /{" "}
              {b.total_over != null ? `O${b.total_over}` : "—"}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

function FeaturedPropsPanel({ players }: { players: SgoPlayerProps[] }) {
  return (
    <div style={{
      display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(280px, 1fr))", gap: 14,
    }}>
      {players.map((p) => {
        const firstMarket = p.markets[0];
        if (!firstMarket) return null;
        const bestLine = firstMarket.lines[0];
        return (
          <div key={p.player_id} style={{
            background: "#0a0f24", borderRadius: 14, border: "1px solid #1e293b",
            padding: "16px 18px",
          }}>
            <div style={{ fontSize: 14, fontWeight: 700, color: "#f0f6fc", marginBottom: 10 }}>
              {p.player_id}
            </div>
            <div style={{ fontSize: 11, color: "#64748b", textTransform: "uppercase", marginBottom: 6 }}>
              {firstMarket.market}
            </div>
            <div style={{ display: "flex", gap: 12 }}>
              <div style={{ flex: 1, background: "rgba(201,168,76,0.06)", borderRadius: 8, padding: "8px 12px", textAlign: "center" }}>
                <div style={{ fontSize: 10, color: "#64748b" }}>Line</div>
                <div style={{ fontSize: 16, fontWeight: 800, color: "#c9a84c" }}>{bestLine?.line ?? "—"}</div>
              </div>
              <div style={{ flex: 1, background: "rgba(201,168,76,0.06)", borderRadius: 8, padding: "8px 12px", textAlign: "center" }}>
                <div style={{ fontSize: 10, color: "#64748b" }}>Over</div>
                <div style={{ fontSize: 16, fontWeight: 800, color: "#c9a84c" }}>{fmtOdds(bestLine?.over_price)}</div>
              </div>
            </div>
            {bestLine && (
              <div style={{ fontSize: 10, color: "#64748b", marginTop: 8 }}>{bestLine.bookmaker}</div>
            )}
          </div>
        );
      })}
    </div>
  );
}

function LoadingCard() {
  return (
    <div style={{ background: "#0a0f24", borderRadius: 14, border: "1px solid #1e293b", padding: 32, textAlign: "center", color: "#94a3b8" }}>
      <Activity size={22} style={{ marginBottom: 8, opacity: 0.5, animation: "spin 2s linear infinite" }} />
      <p style={{ margin: 0, fontSize: 14 }}>Loading SGO data...</p>
    </div>
  );
}

function EmptyCard({ message }: { message: string }) {
  return (
    <div style={{ background: "#0a0f24", borderRadius: 14, border: "1px solid #1e293b", padding: 28, textAlign: "center" }}>
      <p style={{ color: "#64748b", fontSize: 14, margin: 0 }}>{message}</p>
    </div>
  );
}