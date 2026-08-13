"use client";

import Link from "next/link";
import Image from "next/image";
import { useAuth } from "@/lib/auth";
import { Flame, MessageCircle, List, TrendingUp, Activity, Clock } from "lucide-react";
import { useState, useMemo } from "react";
import { useEvents } from "@/lib/use-events";
import type { SBEvent, SBMarket } from "@/lib/sbevent";

// ── leagues as surfaced by SGO ──
const LEAGUES = ["MLB", "NFL", "NBA", "NHL"] as const;
type League = (typeof LEAGUES)[number];

const QUICK = [
  { icon: Flame, label: "Build Lineup", href: "/optimizer" },
  { icon: TrendingUp, label: "Market Tools", href: "/market-tools" },
  { icon: List, label: "Saved Lineups", href: "/lineups" },
  { icon: MessageCircle, label: "Ask SB ME AI", href: "/ai" },
];

// ── helpers ──

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
    return d.toLocaleTimeString([], {
      hour: "numeric",
      minute: "2-digit",
      timeZoneName: "short",
    });
  } catch {
    return iso;
  }
}

// ── main page ──

export default function DashboardPage() {
  const { user } = useAuth();
  const name = user?.email?.split("@")[0] || "Player";
  const [activeLeague, setActiveLeague] = useState<League>("MLB");
  const { events, loading, error } = useEvents(activeLeague);

  const liveEvents = useMemo(
    () => events.filter((e) => isLive(e.status)),
    [events],
  );
  const upcomingEvents = useMemo(
    () => events.filter((e) => !isLive(e.status) && !isCompleted(e.status)),
    [events],
  );
  const completedEvents = useMemo(
    () => events.filter((e) => isCompleted(e.status)),
    [events],
  );

  // ── BEST AVAILABLE ODDS (moneyline markets across ALL events) ──
  const moneylineOdds = useMemo(() => {
    const result: {
      bookmaker: string;
      home_team: string;
      away_team: string;
      home_ml: number | null;
      away_ml: number | null;
    }[] = [];
    for (const evt of events) {
      const mlMarkets = evt.markets.filter(
        (m) => m.bet_type === "moneyline",
      );
      for (const mkt of mlMarkets) {
        for (const book of mkt.books) {
          if (!book.available) continue;
          const existing = result.find((r) => r.bookmaker === book.bookmaker);
          if (!existing) {
            result.push({
              bookmaker: book.bookmaker,
              home_team: evt.home_team.abbreviation || evt.home_team.name,
              away_team: evt.away_team.abbreviation || evt.away_team.name,
              home_ml: mkt.side === "home" ? book.moneyline : null,
              away_ml: mkt.side === "away" ? book.moneyline : null,
            });
          } else {
            if (mkt.side === "home" && existing.home_ml == null)
              existing.home_ml = book.moneyline;
            if (mkt.side === "away" && existing.away_ml == null)
              existing.away_ml = book.moneyline;
          }
        }
      }
    }
    // keep only those with at least one moneyline
    return result.filter((r) => r.home_ml != null || r.away_ml != null);
  }, [events]);

  // ── FEATURED PLAYER PROPS (top 6 across all events) ──
  const featuredProps = useMemo(() => {
    const props: {
      player_name: string;
      market_name: string;
      best_line: number | null;
      best_odds: number | null;
      bookmaker: string;
      event_label: string;
    }[] = [];
    for (const evt of events) {
      const propMarkets = evt.markets.filter(
        (m) => m.bet_type === "player_prop",
      );
      for (const mkt of propMarkets) {
        let bestLine: number | null = null;
        let bestOdds: number | null = null;
        let bestBook = "";
        for (const b of mkt.books) {
          if (!b.available) continue;
          if (
            b.over_under != null &&
            (bestLine == null || b.moneyline != null)
          ) {
            bestLine = b.over_under;
            bestOdds = b.moneyline;
            bestBook = b.bookmaker;
          }
        }
        if (!mkt.player_name) continue;
        props.push({
          player_name: mkt.player_name,
          market_name: mkt.market_name,
          best_line: bestLine,
          best_odds: bestOdds,
          bookmaker: bestBook,
          event_label: `${evt.away_team.abbreviation || evt.away_team.name} @ ${evt.home_team.abbreviation || evt.home_team.name}`,
        });
      }
    }
    return props.slice(0, 6);
  }, [events]);

  const greeting =
    new Date().getHours() < 12
      ? "morning"
      : new Date().getHours() < 17
        ? "afternoon"
        : "evening";

  const hasGames = liveEvents.length > 0 || upcomingEvents.length > 0;

  return (
    <div
      style={{
        maxWidth: 1200,
        margin: "0 auto",
        padding: "40px 24px",
        color: "#f0f6fc",
      }}
    >
      {/* Hero */}
      <div style={{ textAlign: "center", marginBottom: 40 }}>
        <Image
          src="/logo.png"
          alt="SB ME DFS.AI"
          width={200}
          height={105}
          priority
          style={{ margin: "0 auto" }}
        />
        <p
          style={{
            fontSize: 20,
            fontWeight: 700,
            color: "#94a3b8",
            marginTop: 16,
          }}
        >
          Good {greeting}, {name}.
        </p>
        <p style={{ fontSize: 16, color: "#64748b", marginTop: 4 }}>
          SB ME Intelligent AI™ is ready.
        </p>
        {user && (
          <span
            style={{
              display: "inline-block",
              marginTop: 12,
              padding: "6px 16px",
              borderRadius: 20,
              background: "rgba(201,168,76,0.1)",
              border: "1px solid rgba(201,168,76,0.3)",
              color: "#c9a84c",
              fontSize: 13,
              fontWeight: 600,
            }}
          >
            {user.plan || "Free"} Plan
          </span>
        )}
      </div>

      {/* Quick Actions */}
      <h2
        style={{
          fontSize: 13,
          fontWeight: 700,
          color: "#64748b",
          textTransform: "uppercase",
          letterSpacing: 2,
          marginBottom: 16,
        }}
      >
        Quick Actions
      </h2>
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fill, minmax(160px, 1fr))",
          gap: 12,
          marginBottom: 40,
        }}
      >
        {QUICK.map((a, i) => {
          const Icon = a.icon;
          return (
            <Link
              key={i}
              href={a.href}
              style={{
                background: "#0a0f24",
                borderRadius: 16,
                border: "1px solid #1e293b",
                padding: "24px 16px",
                textAlign: "center",
                textDecoration: "none",
                display: "flex",
                flexDirection: "column",
                alignItems: "center",
                gap: 10,
              }}
            >
              <Icon size={28} color="#c9a84c" />
              <span
                style={{
                  fontSize: 13,
                  fontWeight: 600,
                  color: "#94a3b8",
                  lineHeight: 1.3,
                }}
              >
                {a.label}
              </span>
            </Link>
          );
        })}
      </div>

      {/* ─── SPORT TABS ─── */}
      <div
        style={{
          display: "flex",
          gap: 6,
          marginBottom: 24,
          flexWrap: "wrap",
        }}
      >
        {LEAGUES.map((lg) => (
          <button
            key={lg}
            onClick={() => setActiveLeague(lg)}
            style={{
              padding: "8px 18px",
              borderRadius: 10,
              fontSize: 13,
              fontWeight: 700,
              background:
                activeLeague === lg ? "rgba(201,168,76,0.1)" : "#0a0f24",
              border:
                activeLeague === lg
                  ? "1px solid #c9a84c"
                  : "1px solid #1e293b",
              color: activeLeague === lg ? "#c9a84c" : "#94a3b8",
              cursor: "pointer",
            }}
          >
            {lg}
          </button>
        ))}
      </div>

      {/* ─── LIVE & UPCOMING GAMES ─── */}
      <SectionHeading
        label={
          liveEvents.length > 0 ? "● LIVE GAMES" : "UPCOMING GAMES"
        }
      />

      {loading ? (
        <LoadingCard />
      ) : error ? (
        <EmptyCard message={`Unable to load games: ${error}`} />
      ) : !hasGames ? (
        <EmptyCard message={`No ${activeLeague} games available right now.`} />
      ) : (
        <div style={{ display: "grid", gap: 12, marginBottom: 36 }}>
          {liveEvents.map((evt) => (
            <EventCard key={evt.id} event={evt} />
          ))}
          {upcomingEvents.map((evt) => (
            <EventCard key={evt.id} event={evt} />
          ))}
        </div>
      )}

      {/* ─── LIVE SCORES (live events with scores) ─── */}
      {liveEvents.filter(
        (e) => e.home_score != null || e.away_score != null,
      ).length > 0 && (
        <>
          <SectionHeading label="LIVE SCORES" />
          <div style={{ display: "grid", gap: 12, marginBottom: 36 }}>
            {liveEvents
              .filter((e) => e.home_score != null || e.away_score != null)
              .map((evt) => (
                <LiveScoreCard key={evt.id} event={evt} />
              ))}
          </div>
        </>
      )}

      {/* ─── BEST AVAILABLE ODDS ─── */}
      <SectionHeading label="BEST AVAILABLE ODDS" />
      {loading ? (
        <LoadingCard />
      ) : moneylineOdds.length > 0 ? (
        <BestOddsPanel odds={moneylineOdds} />
      ) : (
        <EmptyCard message="No moneyline odds available for this league." />
      )}

      {/* ─── FEATURED PLAYER PROPS ─── */}
      <h2
        style={{
          fontSize: 13,
          fontWeight: 700,
          color: "#64748b",
          textTransform: "uppercase",
          letterSpacing: 2,
          marginTop: 36,
          marginBottom: 14,
        }}
      >
        FEATURED PLAYER PROPS
      </h2>
      {loading ? (
        <LoadingCard />
      ) : featuredProps.length > 0 ? (
        <FeaturedPropsPanel props={featuredProps} />
      ) : (
        <EmptyCard message="No player props available for this league." />
      )}

      {/* ─── RECENT RESULTS ─── */}
      {completedEvents.length > 0 && (
        <>
          <h2
            style={{
              fontSize: 13,
              fontWeight: 700,
              color: "#64748b",
              textTransform: "uppercase",
              letterSpacing: 2,
              marginTop: 36,
              marginBottom: 14,
            }}
          >
            RECENT RESULTS
          </h2>
          <div style={{ display: "grid", gap: 12, marginBottom: 36 }}>
            {completedEvents.slice(0, 5).map((evt) => (
              <CompletedCard key={evt.id} event={evt} />
            ))}
          </div>
        </>
      )}
    </div>
  );
}

/* ── Sub-Components ── */

function SectionHeading({ label }: { label: string }) {
  return (
    <h2
      style={{
        fontSize: 13,
        fontWeight: 700,
        color: "#64748b",
        textTransform: "uppercase",
        letterSpacing: 2,
        marginBottom: 14,
      }}
    >
      {label}
    </h2>
  );
}

function EventCard({ event }: { event: SBEvent }) {
  const live = isLive(event.status);
  return (
    <div
      style={{
        background: live ? "rgba(201,168,76,0.05)" : "#0a0f24",
        borderRadius: 14,
        border: live
          ? "1px solid rgba(201,168,76,0.2)"
          : "1px solid #1e293b",
        padding: "16px 20px",
        display: "flex",
        justifyContent: "space-between",
        alignItems: "center",
        flexWrap: "wrap",
        gap: 8,
      }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
        {/* Status badge */}
        {live ? (
          <span
            style={{
              padding: "3px 10px",
              borderRadius: 6,
              fontSize: 10,
              fontWeight: 800,
              background: "rgba(239,68,68,0.15)",
              color: "#ef4444",
              textTransform: "uppercase",
              flexShrink: 0,
            }}
          >
            ● LIVE
          </span>
        ) : (
          <span
            style={{
              padding: "3px 10px",
              borderRadius: 6,
              fontSize: 10,
              fontWeight: 600,
              background: "rgba(100,116,139,0.12)",
              color: "#94a3b8",
              flexShrink: 0,
              display: "flex",
              alignItems: "center",
              gap: 4,
            }}
          >
            <Clock size={11} /> {formatTime(event.start_time)}
          </span>
        )}
        {/* Matchup */}
        <div>
          <div
            style={{
              fontSize: 15,
              fontWeight: 700,
              color: "#f0f6fc",
            }}
          >
            <span style={{ color: live ? "#c9a84c" : "#f0f6fc" }}>
              {event.away_team.abbreviation || event.away_team.name}
            </span>
            {" @ "}
            <span style={{ color: live ? "#c9a84c" : "#f0f6fc" }}>
              {event.home_team.abbreviation || event.home_team.name}
            </span>
          </div>
          <div style={{ fontSize: 11, color: "#64748b", marginTop: 2 }}>
            {event.venue && `${event.venue} · `}
            {event.status_display}
          </div>
        </div>
      </div>
      {/* Score if live */}
      {live && (event.home_score != null || event.away_score != null) && (
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <span
            style={{ fontSize: 18, fontWeight: 800, color: "#c9a84c" }}
          >
            {event.away_score ?? 0} – {event.home_score ?? 0}
          </span>
          {event.period && (
            <span style={{ fontSize: 11, color: "#64748b" }}>
              {event.period}
            </span>
          )}
        </div>
      )}
    </div>
  );
}

function LiveScoreCard({ event }: { event: SBEvent }) {
  return (
    <div
      style={{
        background: "rgba(201,168,76,0.05)",
        borderRadius: 14,
        border: "1px solid rgba(201,168,76,0.2)",
        padding: "16px 20px",
        display: "flex",
        justifyContent: "space-between",
        alignItems: "center",
        flexWrap: "wrap",
        gap: 10,
      }}
    >
      <div>
        <div
          style={{ fontSize: 15, fontWeight: 700, color: "#f0f6fc" }}
        >
          <span style={{ color: "#c9a84c" }}>
            {event.away_team.abbreviation || event.away_team.name}
          </span>
          {" @ "}
          <span style={{ color: "#c9a84c" }}>
            {event.home_team.abbreviation || event.home_team.name}
          </span>
        </div>
        <div style={{ fontSize: 11, color: "#64748b", marginTop: 2 }}>
          {event.period || event.status_display}
        </div>
      </div>
      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
        <span style={{ fontSize: 22, fontWeight: 800, color: "#c9a84c" }}>
          {event.away_score ?? 0} – {event.home_score ?? 0}
        </span>
      </div>
    </div>
  );
}

function CompletedCard({ event }: { event: SBEvent }) {
  return (
    <div
      style={{
        background: "#0a0f24",
        borderRadius: 14,
        border: "1px solid #1e293b",
        padding: "16px 20px",
        display: "flex",
        justifyContent: "space-between",
        alignItems: "center",
      }}
    >
      <div
        style={{ fontSize: 15, fontWeight: 600, color: "#94a3b8" }}
      >
        {event.away_team.abbreviation || event.away_team.name} @{" "}
        {event.home_team.abbreviation || event.home_team.name}
      </div>
      <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
        <span
          style={{ fontSize: 18, fontWeight: 800, color: "#f0f6fc" }}
        >
          {event.away_score ?? "—"} – {event.home_score ?? "—"}
        </span>
        <span
          style={{
            padding: "3px 8px",
            borderRadius: 4,
            fontSize: 10,
            fontWeight: 700,
            background: "rgba(100,116,139,0.15)",
            color: "#64748b",
            textTransform: "uppercase",
          }}
        >
          FINAL
        </span>
      </div>
    </div>
  );
}

function BestOddsPanel({
  odds,
}: {
  odds: {
    bookmaker: string;
    home_team: string;
    away_team: string;
    home_ml: number | null;
    away_ml: number | null;
  }[];
}) {
  // find best home and away moneyline across all books
  let bestHome = -Infinity;
  let bestAway = -Infinity;
  let bestHomeBook = "";
  let bestAwayBook = "";
  for (const o of odds) {
    if ((o.home_ml ?? -Infinity) > bestHome) {
      bestHome = o.home_ml!;
      bestHomeBook = o.bookmaker;
    }
    if ((o.away_ml ?? -Infinity) > bestAway) {
      bestAway = o.away_ml!;
      bestAwayBook = o.bookmaker;
    }
  }

  const first = odds[0]; // for team labels

  return (
    <div
      style={{
        background: "#0a0f24",
        borderRadius: 16,
        border: "1px solid #1e293b",
        padding: 20,
        overflow: "hidden",
      }}
    >
      {/* Best prices highlight */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "1fr 1fr",
          gap: 16,
          marginBottom: 18,
        }}
      >
        <div
          style={{
            background: "rgba(201,168,76,0.06)",
            borderRadius: 10,
            padding: "12px 16px",
            textAlign: "center",
          }}
        >
          <div
            style={{
              fontSize: 10,
              color: "#64748b",
              textTransform: "uppercase",
              marginBottom: 4,
            }}
          >
            Best Home ML ({first?.home_team ?? "—"})
          </div>
          <div
            style={{ fontSize: 18, fontWeight: 800, color: "#c9a84c" }}
          >
            {fmtOdds(bestHome)}
          </div>
          <div style={{ fontSize: 11, color: "#64748b", marginTop: 2 }}>
            {bestHomeBook}
          </div>
        </div>
        <div
          style={{
            background: "rgba(201,168,76,0.06)",
            borderRadius: 10,
            padding: "12px 16px",
            textAlign: "center",
          }}
        >
          <div
            style={{
              fontSize: 10,
              color: "#64748b",
              textTransform: "uppercase",
              marginBottom: 4,
            }}
          >
            Best Away ML ({first?.away_team ?? "—"})
          </div>
          <div
            style={{ fontSize: 18, fontWeight: 800, color: "#c9a84c" }}
          >
            {fmtOdds(bestAway)}
          </div>
          <div style={{ fontSize: 11, color: "#64748b", marginTop: 2 }}>
            {bestAwayBook}
          </div>
        </div>
      </div>

      {/* Bookmaker comparison table */}
      <div style={{ overflowX: "auto" }}>
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "1.5fr 1fr 1fr",
            gap: 4,
            padding: "8px 0",
            borderBottom: "1px solid #1e293b",
            fontSize: 10,
            fontWeight: 700,
            color: "#64748b",
            textTransform: "uppercase",
          }}
        >
          <span>Bookmaker</span>
          <span style={{ textAlign: "center" }}>Home ML</span>
          <span style={{ textAlign: "center" }}>Away ML</span>
        </div>
        {odds.slice(0, 10).map((b, i) => (
          <div
            key={i}
            style={{
              display: "grid",
              gridTemplateColumns: "1.5fr 1fr 1fr",
              gap: 4,
              padding: "10px 0",
              borderBottom: "1px solid #1e293b20",
              alignItems: "center",
            }}
          >
            <span
              style={{
                fontSize: 12,
                color: "#94a3b8",
                fontWeight: 500,
              }}
            >
              {b.bookmaker}
            </span>
            <span
              style={{
                fontSize: 13,
                fontWeight: b.home_ml === bestHome ? 800 : 500,
                color:
                  b.home_ml === bestHome ? "#c9a84c" : "#f0f6fc",
                textAlign: "center",
              }}
            >
              {fmtOdds(b.home_ml)}
            </span>
            <span
              style={{
                fontSize: 13,
                fontWeight: b.away_ml === bestAway ? 800 : 500,
                color:
                  b.away_ml === bestAway ? "#c9a84c" : "#f0f6fc",
                textAlign: "center",
              }}
            >
              {fmtOdds(b.away_ml)}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

function FeaturedPropsPanel({
  props,
}: {
  props: {
    player_name: string;
    market_name: string;
    best_line: number | null;
    best_odds: number | null;
    bookmaker: string;
    event_label: string;
  }[];
}) {
  return (
    <div
      style={{
        display: "grid",
        gridTemplateColumns: "repeat(auto-fill, minmax(280px, 1fr))",
        gap: 14,
      }}
    >
      {props.map((p, i) => (
        <div
          key={i}
          style={{
            background: "#0a0f24",
            borderRadius: 14,
            border: "1px solid #1e293b",
            padding: "16px 18px",
          }}
        >
          <div
            style={{
              fontSize: 14,
              fontWeight: 700,
              color: "#f0f6fc",
              marginBottom: 4,
            }}
          >
            {p.player_name}
          </div>
          <div
            style={{
              fontSize: 11,
              color: "#64748b",
              marginBottom: 4,
            }}
          >
            {p.event_label}
          </div>
          <div
            style={{
              fontSize: 11,
              color: "#64748b",
              textTransform: "uppercase",
              marginBottom: 6,
            }}
          >
            {p.market_name}
          </div>
          <div style={{ display: "flex", gap: 12 }}>
            <div
              style={{
                flex: 1,
                background: "rgba(201,168,76,0.06)",
                borderRadius: 8,
                padding: "8px 12px",
                textAlign: "center",
              }}
            >
              <div style={{ fontSize: 10, color: "#64748b" }}>Line</div>
              <div
                style={{
                  fontSize: 16,
                  fontWeight: 800,
                  color: "#c9a84c",
                }}
              >
                {p.best_line ?? "—"}
              </div>
            </div>
            <div
              style={{
                flex: 1,
                background: "rgba(201,168,76,0.06)",
                borderRadius: 8,
                padding: "8px 12px",
                textAlign: "center",
              }}
            >
              <div style={{ fontSize: 10, color: "#64748b" }}>Odds</div>
              <div
                style={{
                  fontSize: 16,
                  fontWeight: 800,
                  color: "#c9a84c",
                }}
              >
                {fmtOdds(p.best_odds)}
              </div>
            </div>
          </div>
          {p.bookmaker && (
            <div
              style={{ fontSize: 10, color: "#64748b", marginTop: 8 }}
            >
              {p.bookmaker}
            </div>
          )}
        </div>
      ))}
    </div>
  );
}

function LoadingCard() {
  return (
    <div
      style={{
        background: "#0a0f24",
        borderRadius: 14,
        border: "1px solid #1e293b",
        padding: 32,
        textAlign: "center",
        color: "#94a3b8",
      }}
    >
      <Activity
        size={22}
        style={{ marginBottom: 8, opacity: 0.5 }}
      />
      <p style={{ margin: 0, fontSize: 14 }}>
        Loading SGO data...
      </p>
    </div>
  );
}

function EmptyCard({ message }: { message: string }) {
  return (
    <div
      style={{
        background: "#0a0f24",
        borderRadius: 14,
        border: "1px solid #1e293b",
        padding: 28,
        textAlign: "center",
      }}
    >
      <p style={{ color: "#64748b", fontSize: 14, margin: 0 }}>
        {message}
      </p>
    </div>
  );
}