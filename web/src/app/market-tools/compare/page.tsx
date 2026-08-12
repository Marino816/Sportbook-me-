"use client";

import { useState, useEffect, useCallback } from "react";
import { GitCompare, Trophy, Search } from "lucide-react";
import { getApiBaseUrl } from "@/lib/api-base-url";

const API_BASE = getApiBaseUrl(process.env.NEXT_PUBLIC_API_URL);

const LEAGUES = ["MLB", "NFL", "NBA", "NHL", "NCAAF", "NCAAB"] as const;
type League = (typeof LEAGUES)[number];
type TabKey = "moneyline" | "spread" | "total";

const TABS: { key: TabKey; label: string }[] = [
  { key: "moneyline", label: "Moneyline" },
  { key: "spread", label: "Spread" },
  { key: "total", label: "Total" },
];

interface SgoEvent {
  event_id: string;
  home_team: { name: string; abbreviation: string };
  away_team: { name: string; abbreviation: string };
  start_time: string | null;
  status: string;
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

interface OddsData {
  event_id: string;
  books: SgoBook[];
  book_count: number;
  consensus?: SgoBook;
}

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

function fmtSpread(v: number | null | undefined): string {
  if (v == null) return "—";
  return v > 0 ? `+${v}` : `${v}`;
}

export default function CompareOddsPage() {
  const [activeLeague, setActiveLeague] = useState<League>("MLB");
  const [events, setEvents] = useState<SgoEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");

  const [selectedEventId, setSelectedEventId] = useState<string | null>(null);
  const [selectedEvent, setSelectedEvent] = useState<SgoEvent | null>(null);
  const [oddsData, setOddsData] = useState<OddsData | null>(null);
  const [comparing, setComparing] = useState(false);
  const [activeTab, setActiveTab] = useState<TabKey>("moneyline");

  const loadEvents = useCallback(async () => {
    setLoading(true);
    const data = await sgoFetch<{ events: SgoEvent[]; league: string; count: number }>(
      `/events?league=${activeLeague}`
    );
    setEvents(data?.events ?? []);
    setSelectedEventId(null);
    setSelectedEvent(null);
    setOddsData(null);
    setLoading(false);
  }, [activeLeague]);

  useEffect(() => { loadEvents(); }, [loadEvents]);

  const loadCompare = async (evt: SgoEvent) => {
    setSelectedEventId(evt.event_id);
    setSelectedEvent(evt);
    setComparing(true);
    const data = await sgoFetch<OddsData>(`/events/${evt.event_id}/odds`);
    setOddsData(data);
    setComparing(false);
  };

  const filtered = events.filter((e) => {
    if (!search) return true;
    const q = search.toLowerCase();
    return (
      (e.home_team.name || "").toLowerCase().includes(q) ||
      (e.away_team.name || "").toLowerCase().includes(q) ||
      (e.home_team.abbreviation || "").toLowerCase().includes(q) ||
      (e.away_team.abbreviation || "").toLowerCase().includes(q)
    );
  });

  const books = oddsData?.books ?? [];

  // Find best value for current tab
  const getBestKey = (tab: TabKey, side: "home" | "away"): number | null => {
    if (books.length === 0) return null;
    if (tab === "moneyline") {
      const key = side === "home" ? "moneyline_home" : "moneyline_away";
      let best = -Infinity;
      for (const b of books) {
        const v = b[key] as number | null;
        if (v != null && v > best) best = v;
      }
      return best === -Infinity ? null : best;
    }
    if (tab === "spread") {
      const key = side === "home" ? "spread_home" : "spread_away";
      let best: number | null = null;
      for (const b of books) {
        const v = b[key] as number | null;
        if (v == null) continue;
        if (best === null) { best = v; continue; }
        // For spreads, best is most favorable (higher for underdog, lower for favorite)
        if (side === "home" ? v > best : v < best) best = v;
      }
      return best;
    }
    if (tab === "total") {
      let bestOver = -Infinity;
      for (const b of books) {
        if (b.total_over != null && b.total_over > bestOver) bestOver = b.total_over;
      }
      return bestOver === -Infinity ? null : bestOver;
    }
    return null;
  };

  const bestHome = getBestKey(activeTab, "home");
  const bestAway = getBestKey(activeTab, "away");

  const getValue = (book: SgoBook, tab: TabKey, side: "home" | "away"): number | null => {
    if (tab === "moneyline") return side === "home" ? book.moneyline_home : book.moneyline_away;
    if (tab === "spread") return side === "home" ? book.spread_home : book.spread_away;
    if (tab === "total") return side === "home" ? book.total_over : book.total_under;
    return null;
  };

  return (
    <div style={{ maxWidth: 1200, margin: "0 auto", padding: "32px 24px" }}>
      {/* Header */}
      <div style={{
        display: "flex", alignItems: "center", gap: 14, marginBottom: 28,
        background: "#0a0f24", borderRadius: 14, border: "1px solid #1e293b", padding: "20px 24px",
      }}>
        <GitCompare size={26} color="#c9a84c" />
        <div style={{ flex: 1 }}>
          <h1 style={{ fontSize: 24, fontWeight: 900, color: "#c9a84c", margin: 0 }}>Compare Odds</h1>
          <p style={{ fontSize: 13, color: "#94a3b8", margin: "2px 0 0" }}>
            Best price highlighted across all bookmakers — SportsGameOdds
          </p>
        </div>
      </div>

      {/* League + event selector */}
      <div style={{ display: "flex", gap: 8, marginBottom: 16, flexWrap: "wrap", alignItems: "center" }}>
        {LEAGUES.map((lg) => (
          <button key={lg} onClick={() => setActiveLeague(lg)} style={{
            padding: "8px 14px", borderRadius: 10, fontSize: 12, fontWeight: 700,
            background: activeLeague === lg ? "rgba(201,168,76,0.1)" : "#0a0f24",
            border: activeLeague === lg ? "1px solid #c9a84c" : "1px solid #1e293b",
            color: activeLeague === lg ? "#c9a84c" : "#94a3b8",
            cursor: "pointer",
          }}>{lg}</button>
        ))}
      </div>

      <div style={{ display: "flex", gap: 10, marginBottom: 20, flexWrap: "wrap", alignItems: "center" }}>
        <div style={{ position: "relative" }}>
          <Search size={14} style={{ position: "absolute", left: 10, top: "50%", transform: "translateY(-50%)", color: "#64748b" }} />
          <input
            type="text" placeholder="Search teams..." value={search}
            onChange={(e) => setSearch(e.target.value)}
            style={{
              padding: "8px 14px 8px 32px", borderRadius: 10, fontSize: 13,
              background: "#0a0f24", border: "1px solid #1e293b",
              color: "#f0f6fc", outline: "none", minWidth: 200,
            }}
          />
        </div>
        {filtered.map((evt) => {
          const isSel = evt.event_id === selectedEventId;
          return (
            <button key={evt.event_id} onClick={() => loadCompare(evt)} style={{
              padding: "8px 14px", borderRadius: 10, fontSize: 12, fontWeight: 600,
              border: isSel ? "1px solid #c9a84c" : "1px solid #1e293b",
              background: isSel ? "rgba(201,168,76,0.1)" : "#0a0f24",
              color: isSel ? "#c9a84c" : "#94a3b8",
              cursor: "pointer", whiteSpace: "nowrap",
            }}>
              {(evt.away_team.abbreviation || "AWY").substring(0, 3)} @ {(evt.home_team.abbreviation || "HOM").substring(0, 3)}
            </button>
          );
        })}
      </div>

      {comparing && (
        <div style={{ textAlign: "center", padding: 60, color: "#94a3b8" }}>Loading comparison data...</div>
      )}

      {oddsData && !comparing && (
        <>
          {/* Tab selector */}
          <div style={{ display: "flex", gap: 6, marginBottom: 20 }}>
            {TABS.map((t) => (
              <button key={t.key} onClick={() => setActiveTab(t.key)} style={{
                padding: "8px 16px", borderRadius: 10, fontSize: 12, fontWeight: 600,
                border: activeTab === t.key ? "1px solid #c9a84c" : "1px solid #1e293b",
                background: activeTab === t.key ? "rgba(201,168,76,0.1)" : "#0a0f24",
                color: activeTab === t.key ? "#c9a84c" : "#94a3b8",
                cursor: "pointer",
              }}>{t.label}</button>
            ))}
          </div>

          {books.length > 0 ? (
            <div style={{ background: "#0a0f24", borderRadius: 14, border: "1px solid #1e293b", overflow: "hidden" }}>
              {/* Table header */}
              <div style={{
                display: "grid", gridTemplateColumns: "2fr 1fr 1fr 80px",
                padding: "12px 20px", background: "rgba(201,168,76,0.08)",
                borderBottom: "1px solid #1e293b", fontSize: 11, fontWeight: 700,
                color: "#c9a84c", textTransform: "uppercase",
              }}>
                <span>Bookmaker</span>
                <span style={{ textAlign: "center" }}>{selectedEvent?.home_team.abbreviation || "Home"}</span>
                <span style={{ textAlign: "center" }}>{selectedEvent?.away_team.abbreviation || "Away"}</span>
                <span style={{ textAlign: "center" }}>Best</span>
              </div>

              {books.map((book, i) => {
                const hv = getValue(book, activeTab, "home");
                const av = getValue(book, activeTab, "away");
                const homeIsBest = hv != null && hv === bestHome;
                const awayIsBest = av != null && av === bestAway;

                const displayHome = activeTab === "spread" ? fmtSpread(hv) : fmtOdds(hv);
                const displayAway = activeTab === "spread" ? fmtSpread(av) : fmtOdds(av);

                return (
                  <div key={i} style={{
                    display: "grid", gridTemplateColumns: "2fr 1fr 1fr 80px",
                    padding: "14px 20px", borderBottom: "1px solid #1e293b20",
                    alignItems: "center",
                  }}>
                    <span style={{ fontSize: 13, color: "#94a3b8", fontWeight: 500 }}>{book.bookmaker}</span>
                    <span style={{
                      fontSize: 14, fontWeight: homeIsBest ? 800 : 500,
                      color: homeIsBest ? "#c9a84c" : "#f0f6fc", textAlign: "center",
                    }}>{displayHome}</span>
                    <span style={{
                      fontSize: 14, fontWeight: awayIsBest ? 800 : 500,
                      color: awayIsBest ? "#c9a84c" : "#f0f6fc", textAlign: "center",
                    }}>{displayAway}</span>
                    <span style={{ textAlign: "center" }}>
                      {homeIsBest || awayIsBest ? <Trophy size={16} color="#c9a84c" /> : "—"}
                    </span>
                  </div>
                );
              })}
            </div>
          ) : (
            <div style={{ textAlign: "center", padding: 60, color: "#64748b", background: "#0a0f24", borderRadius: 14, border: "1px solid #1e293b" }}>
              Data currently unavailable
            </div>
          )}
        </>
      )}

      {!oddsData && !comparing && !loading && (
        <div style={{ textAlign: "center", padding: 60, color: "#64748b" }}>
          Select an event to compare odds across bookmakers.
        </div>
      )}
    </div>
  );
}