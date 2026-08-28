"use client";

import Link from "next/link";
import { useAuth } from "@/lib/auth";
import {
  Flame, MessageCircle, List, Activity, ChevronRight, Sparkles, BarChart3, Upload, Swords, Building2, Database, UserCheck,
} from "lucide-react";
import { useMemo, useState } from "react";
import { useLiveScores, gameState, type GameState } from "@/lib/live-scores";
import type { SBEvent } from "@/lib/sbevent";
import { formatBookmakerName } from "@/lib/bookmakers";
import { AppShell } from "@/components/app-shell";
import { LeagueChips, StatusChips, LastUpdated, FairOddsMark, ConsensusMark } from "@/components/market-controls";
import { filterEventsByStatus, filterMarkets } from "@/lib/market-view";

const QUICK = [
  { icon: Flame, label: "Optimizer", href: "/optimizer" },
  { icon: BarChart3, label: "Market Tools", href: "/market-tools" },
  { icon: Building2, label: "Bookmakers", href: "/market-tools/bookmakers" },
  { icon: Swords, label: "Parlay", href: "/market-tools/parlay" },
  { icon: UserCheck, label: "Props", href: "/market-tools/player-props" },
  { icon: Database, label: "Data Hub", href: "/data-hub" },
  { icon: MessageCircle, label: "SB ME AI", href: "/ai" },
  { icon: List, label: "Lineups", href: "/lineups" },
];

const C = { card: "#0a0f24", border: "#1e293b", text: "#f0f6fc", muted: "#94a3b8", subtle: "#64748b", gold: "#c9a84c" };

function fmtOdds(v: number | null | undefined) {
  if (v == null) return "\u2014";
  return v > 0 ? "+" + v : "" + v;
}

const EDT = "America/New_York";
function todayEDT(): string {
  return new Date().toLocaleDateString("en-US", { timeZone: EDT });
}
function tomorrowEDT(): string {
  const d = new Date();
  d.setDate(d.getDate() + 1);
  return d.toLocaleDateString("en-US", { timeZone: EDT });
}
function eventDateKey(iso: string | null): string {
  if (!iso) return "9999";
  return new Date(iso).toLocaleDateString("en-US", { timeZone: EDT });
}
function dateLabel(iso: string | null): string {
  const dk = eventDateKey(iso);
  if (!dk || dk === "9999") return "Upcoming";
  const ts = iso || "";
  if (dk === todayEDT())
    return "TODAY \u2014 " + new Date(ts).toLocaleDateString("en-US", { timeZone: EDT, weekday: "long", month: "long", day: "numeric" }).toUpperCase();
  if (dk === tomorrowEDT())
    return "TOMORROW \u2014 " + new Date(ts).toLocaleDateString("en-US", { timeZone: EDT, weekday: "long", month: "long", day: "numeric" }).toUpperCase();
  return new Date(ts).toLocaleDateString("en-US", { timeZone: EDT, weekday: "long", month: "long", day: "numeric" }).toUpperCase();
}
function timeEDT(iso: string | null): string {
  if (!iso) return "";
  return new Date(iso).toLocaleTimeString("en-US", { timeZone: EDT, hour: "numeric", minute: "2-digit" }) + " EDT";
}

function GameStrip({ event }: { event: SBEvent }) {
  const st = gameState(event);
  const live = st === "LIVE";
  const final = st === "FINAL";
  const t = timeEDT(event.start_time);
  const mainMarkets = filterMarkets(event.markets || [], { lineMode: "main", period: "full" });
  const ml = mainMarkets.find((m) => m.bet_type === "moneyline" && m.side === "home");
  const hasProps = (event.markets || []).some((m) => m.bet_type === "player_prop");
  const hasTeam = (event.markets || []).some((m) => m.bet_type === "team_prop");
  const hasAlt = (event.markets || []).some((m) => m.is_main_line === false);
  return (
    <div className={`sbme-evt${live ? " is-live" : ""}`}>
      <div className="sbme-evt-main">
        <span className="sbme-evt-status">
          {live ? "LIVE" : final ? "FINAL" : t || "UPCOMING"}
        </span>
        <span className="sbme-evt-teams">
          {event.away_team?.abbreviation || "AWY"} @ {event.home_team?.abbreviation || "HOM"}
        </span>
        {(event.home_score != null || event.away_score != null) && (
          <span className="sbme-evt-score">
            {event.away_score ?? 0}{"\u2013"}{event.home_score ?? 0}
          </span>
        )}
      </div>
      <div className="sbme-evt-meta">
        {event.bookmakers?.length > 0 && <span className="sbme-tag">{event.bookmakers.length} books</span>}
        {hasProps && <span className="sbme-tag is-gold">Player props</span>}
        {hasTeam && <span className="sbme-tag is-blue">Team props</span>}
        {hasAlt && <span className="sbme-tag">Alts</span>}
        {ml?.fair_odds != null && <FairOddsMark value={ml.fair_odds} />}
        {ml?.book_odds != null && <ConsensusMark value={ml.book_odds} />}
      </div>
    </div>
  );
}

interface PropItem {
  player: string;
  matchup: string;
  market: string;
  line: number | null;
  odds: number | null;
  book: string;
  kind: "player" | "team";
}
function PropRow({ p }: { p: PropItem }) {
  return (
    <div className="sbme-prop">
      <div style={{ minWidth: 0 }}>
        <div className="sbme-prop-name">{p.player}</div>
        <div className="sbme-prop-sub">
          {p.kind === "team" ? "Team" : "Player"} {"\u00b7"} {p.market} {"\u00b7"} {p.matchup}
        </div>
      </div>
      <div style={{ display: "flex", alignItems: "center", gap: 10, flexShrink: 0 }}>
        <span style={{ fontSize: 13, fontWeight: 800, color: C.gold }}>{p.line ?? "\u2014"}</span>
        <span style={{ fontSize: 12, fontWeight: 600, color: C.muted, minWidth: 48, textAlign: "right" }}>{fmtOdds(p.odds)}</span>
        <span style={{ fontSize: 9, color: "#8b9cb3", minWidth: 60, textAlign: "right" }}>{p.book}</span>
      </div>
    </div>
  );
}

function MLRow({ book, home, away }: { book: string; home: number | null; away: number | null }) {
  return (
    <div className="sbme-ml">
      <span style={{ fontSize: 10, color: "#8b9cb3" }}>{book}</span>
      <span style={{ fontSize: 12, fontWeight: home != null ? 700 : 400, color: home != null ? C.text : C.muted, textAlign: "center" }}>{fmtOdds(home)}</span>
      <span style={{ fontSize: 12, fontWeight: away != null ? 700 : 400, color: away != null ? C.text : C.muted, textAlign: "center" }}>{fmtOdds(away)}</span>
    </div>
  );
}

export default function DashboardPage() {
  const { user } = useAuth();
  const [activeLeague, setActiveLeague] = useState("MLB");
  const [status, setStatus] = useState<GameState | "ALL">("ALL");
  const { events: rawEvents, loading, error, lastFetch } = useLiveScores(activeLeague);

  const events = useMemo(() => {
    const seen = new Set<string>();
    return filterEventsByStatus(
      rawEvents.filter((e) => {
        if (seen.has(e.id)) return false;
        seen.add(e.id);
        return true;
      }),
      status,
    );
  }, [rawEvents, status]);

  const dateGroups = useMemo(() => {
    const groups: Record<string, SBEvent[]> = {};
    for (const ev of events) {
      const dk = eventDateKey(ev.start_time) || "0000";
      if (!groups[dk]) groups[dk] = [];
      groups[dk].push(ev);
    }
    const sorted = Object.entries(groups).sort(([a], [b]) => {
      if (a === "9999") return 1;
      if (b === "9999") return -1;
      return new Date(a).getTime() - new Date(b).getTime();
    });
    for (const [, list] of sorted) {
      list.sort((a, b) => new Date(a.start_time || 0).getTime() - new Date(b.start_time || 0).getTime());
    }
    return sorted;
  }, [events]);

  const displayGroups = useMemo(() => {
    const td = todayEDT();
    const result: { label: string; events: SBEvent[] }[] = [];
    let count = 0;
    for (const [dk, list] of dateGroups) {
      if (dk === td) {
        result.push({ label: dateLabel(list[0].start_time), events: list });
        count += list.length;
        break;
      }
    }
    for (const [dk, list] of dateGroups) {
      if (dk === td) continue;
      if (count >= 10) break;
      result.push({ label: dateLabel(list[0].start_time), events: list.slice(0, 10 - count) });
      count += Math.min(list.length, 10 - count);
    }
    return result;
  }, [dateGroups]);

  const mlBooks = useMemo(() => {
    const map: Record<string, { home: number | null; away: number | null }> = {};
    for (const ev of events) {
      const mains = filterMarkets(ev.markets, { lineMode: "main", period: "full", betTypes: ["moneyline"] });
      for (const m of mains) {
        for (const b of m.books) {
          if (!b.available || b.moneyline == null) continue;
          const nm = formatBookmakerName(b.bookmaker);
          if (!map[nm]) map[nm] = { home: null, away: null };
          if (m.side === "home") map[nm].home = b.moneyline;
          if (m.side === "away") map[nm].away = b.moneyline;
        }
      }
    }
    const entries = Object.entries(map).filter(([, v]) => v.home != null || v.away != null);
    const teams = events.length > 0 ? events[0].away_team?.abbreviation + " @ " + events[0].home_team?.abbreviation : "";
    return { entries, teams };
  }, [events]);

  const allProps = useMemo((): PropItem[] => {
    const seen = new Set<string>();
    const items: PropItem[] = [];
    for (const ev of events) {
      for (const m of ev.markets) {
        if (m.bet_type !== "player_prop" && m.bet_type !== "team_prop") continue;
        for (const b of m.books) {
          if (!b.available || b.over_under == null) continue;
          const book = formatBookmakerName(b.bookmaker);
          const name = m.player_name || m.market_name || (m.bet_type === "team_prop" ? "Team" : "Prop");
          const key = [name, m.market_name, String(b.over_under), book].join("|");
          if (seen.has(key)) continue;
          seen.add(key);
          items.push({
            player: name,
            matchup: ev.away_team?.abbreviation + " @ " + ev.home_team?.abbreviation,
            market: m.market_name,
            line: b.over_under,
            odds: b.moneyline,
            book,
            kind: m.bet_type === "team_prop" ? "team" : "player",
          });
        }
      }
    }
    return items.slice(0, 6);
  }, [events]);

  const now = new Date();
  const dateStr = now.toLocaleDateString("en-US", { weekday: "long", month: "short", day: "numeric", timeZone: EDT });

  return (
    <AppShell>
      <div className="sbme-home">
        <div className="sbme-home-head">
          <div>
            <p className="sbme-home-kicker">Current sports intelligence</p>
            <h1>SB ME DFS AI</h1>
            <p className="sbme-home-sub">Sports intelligence dashboard</p>
            <p className="sbme-home-meta">
              {dateStr} {"\u00b7"} <LastUpdated fetchedAt={lastFetch ?? undefined} />
            </p>
          </div>
          {user && <span className="sbme-home-plan">{user.plan || "Free"} Plan</span>}
        </div>

        <div className="sbme-home-controls">
          <StatusChips value={status} onChange={setStatus} />
        </div>
        <div style={{ marginBottom: 14 }}>
          <LeagueChips value={activeLeague} onChange={setActiveLeague} grouped />
        </div>

        <Link href="/ai" className="sbme-ai">
          <span className="sbme-ai-icon"><Sparkles size={18} /></span>
          <div>
            <div className="sbme-ai-title">Ask SB ME AI</div>
            <div className="sbme-ai-copy">Ask about today&apos;s games, markets, props, scores or DFS slate. Answers use live SB ME data — never invented markets.</div>
          </div>
          <ChevronRight size={16} color="#c9a84c" style={{ marginLeft: "auto", flexShrink: 0 }} />
        </Link>

        <div className="sbme-mods">
          {QUICK.map((a) => {
            const Icon = a.icon;
            return (
              <Link key={a.href} href={a.href} className="sbme-mod">
                <span className="sbme-mod-icon"><Icon size={18} /></span>
                <span>{a.label}</span>
              </Link>
            );
          })}
        </div>

        <div className="sbme-home-split">
          <div className="sbme-panel">
            <div className="sbme-panel-h">
              <h2>{activeLeague} {"\u2014"} Games</h2>
              <Link href="/market-tools/live-odds" className="sbme-panel-link">
                Live odds <ChevronRight size={10} />
              </Link>
            </div>
            {loading ? (
              <div className="sbme-empty">
                <div className="sbme-empty-icon"><Activity size={18} /></div>
                <p>Loading {activeLeague} games...</p>
              </div>
            ) : error ? (
              <div className="sbme-empty is-err">
                <p>Unable to load {activeLeague} games</p>
              </div>
            ) : displayGroups.length === 0 ? (
              <div className="sbme-empty">
                <p>No {activeLeague} games for this filter.</p>
              </div>
            ) : (
              displayGroups.map((grp, gi) => (
                <div key={gi} style={{ marginBottom: gi < displayGroups.length - 1 ? 14 : 0 }}>
                  <div className="sbme-date">{grp.label}</div>
                  <div style={{ display: "grid", gap: 6 }}>
                    {grp.events.map((evt) => (
                      <GameStrip key={evt.id} event={evt} />
                    ))}
                  </div>
                </div>
              ))
            )}
          </div>

          <div className="sbme-panel">
            <div className="sbme-panel-h">
              <h2>Shortcuts</h2>
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
              <Link href="/market-tools/compare" className="sbme-shortcut">Odds Comparison</Link>
              <Link href="/market-tools/bookmakers" className="sbme-shortcut">Bookmakers</Link>
              <Link href="/data-hub" className="sbme-shortcut">Data Hub (DFS slates)</Link>
              <div className="sbme-note">
                <div style={{ fontSize: 10, color: "#8b9cb3", fontWeight: 700, textTransform: "uppercase", marginBottom: 1 }}>Top DFS Values</div>
                <div style={{ fontSize: 11, color: C.muted }}>Open Data Hub and upload a slate. Soccer and other SGO leagues are not DFS sports.</div>
              </div>
            </div>
          </div>
        </div>

        <div className="sbme-home-grid">
          <div className="sbme-panel">
            <div className="sbme-panel-h">
              <h3>Best Available Odds</h3>
              <Link href="/market-tools/compare" className="sbme-panel-link">Compare {"\u2192"}</Link>
            </div>
            {mlBooks.entries.length > 0 ? (
              <div>
                <div style={{ fontSize: 10, color: "#8b9cb3", marginBottom: 6, fontWeight: 600 }}>{mlBooks.teams || activeLeague + " Moneyline"}</div>
                <div className="sbme-ml" style={{ borderBottom: "1px solid rgba(201,168,76,0.25)", marginBottom: 4 }}>
                  <span style={{ fontSize: 9, color: C.gold, fontWeight: 700, textTransform: "uppercase" }}>Book</span>
                  <span style={{ fontSize: 9, color: C.gold, fontWeight: 700, textAlign: "center" }}>Home</span>
                  <span style={{ fontSize: 9, color: C.gold, fontWeight: 700, textAlign: "center" }}>Away</span>
                </div>
                {mlBooks.entries.slice(0, 6).map(([bk, v], i) => (
                  <MLRow key={i} book={bk} home={v.home} away={v.away} />
                ))}
              </div>
            ) : (
              <div className="sbme-empty">
                <p>No odds available for {activeLeague}</p>
              </div>
            )}
          </div>

          <div className="sbme-panel">
            <div className="sbme-panel-h">
              <h3>Featured Props</h3>
              <Link href="/market-tools/player-props" className="sbme-panel-link">View All {"\u2192"}</Link>
            </div>
            {allProps.length > 0 ? (
              <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                {allProps.map((p, i) => (
                  <PropRow key={i} p={p} />
                ))}
              </div>
            ) : (
              <div className="sbme-empty">
                <p>No props available for {activeLeague}</p>
              </div>
            )}
          </div>

          <div className="sbme-panel">
            <div className="sbme-panel-h">
              <h3>DFS Data Hub</h3>
              <Link href="/data-hub" className="sbme-panel-link">Open {"\u2192"}</Link>
            </div>
            <div style={{ textAlign: "center", padding: "18px 12px" }}>
              <div style={{ fontSize: 12, fontWeight: 700, color: "#8b9cb3", marginBottom: 4 }}>DFS slates stay on Data Hub</div>
              <div style={{ fontSize: 11, color: C.muted, marginBottom: 14 }}>MLB, NFL, NBA, NHL, NCAAF, NCAAB only. Soccer and other SGO leagues are market intelligence, not DFS slates.</div>
              <Link href="/data-hub" className="sbme-cta">
                <Upload size={13} /> Open Data Hub
              </Link>
            </div>
          </div>
        </div>
      </div>
    </AppShell>
  );
}
