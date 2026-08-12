"use client";

import { useState, useEffect } from "react";
import { GitCompare, Trophy, Search } from "lucide-react";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "https://sportbook-me-production.up.railway.app/api";

type TabKey = "moneyline" | "spread" | "total" | "props";
const TABS: { key: TabKey; label: string }[] = [
  { key: "moneyline", label: "Moneyline" },
  { key: "spread", label: "Spread" },
  { key: "total", label: "Total" },
  { key: "props", label: "Player Props" },
];

export default function CompareOddsPage() {
  const [games, setGames] = useState<any[]>([]);
  const [selectedGameId, setSelectedGameId] = useState<string | null>(null);
  const [compareData, setCompareData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [comparing, setComparing] = useState(false);
  const [activeTab, setActiveTab] = useState<TabKey>("moneyline");
  const [search, setSearch] = useState("");

  useEffect(() => {
    (async () => {
      try {
        const token = typeof window !== "undefined" ? localStorage.getItem("sbme_dfs_token") : null;
        const res = await fetch(`${API_URL}/market-tools/live-odds?slate_id=1`, {
          headers: token ? { Authorization: `Bearer ${token}` } : {},
        });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const json = await res.json();
        setGames(json.data?.games || json.games || []);
      } catch (e) {
        console.error(e);
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  const loadCompare = async (gameId: string) => {
    setSelectedGameId(gameId);
    setComparing(true);
    try {
      const token = typeof window !== "undefined" ? localStorage.getItem("sbme_dfs_token") : null;
      const res = await fetch(`${API_URL}/market-tools/compare?event_id=${gameId}`, {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const json = await res.json();
      setCompareData(json.data || json);
    } catch (e) {
      console.error(e);
    } finally {
      setComparing(false);
    }
  };

  const filteredGames = games.filter((g) => {
    if (!search) return true;
    const q = search.toLowerCase();
    return (
      (g.home_team_name || "").toLowerCase().includes(q) ||
      (g.away_team_name || "").toLowerCase().includes(q)
    );
  });

  const getBestPrice = (prices: any[]): any => {
    if (!prices?.length) return null;
    return prices.reduce((best, p) => {
      return (p.price || p.odds || 0) > (best.price || best.odds || 0) ? p : best;
    }, prices[0]);
  };

  const fmt = (v: number | null | undefined) => {
    if (v == null) return "—";
    return v > 0 ? `+${v}` : `${v}`;
  };

  const books = compareData?.bookmakers || compareData?.books || [];

  return (
    <div style={{ maxWidth: 1200, margin: "0 auto", padding: "32px 24px" }}>
      {/* Header */}
      <div
        style={{
          display: "flex", alignItems: "center", gap: 14, marginBottom: 28,
          background: "#0a0f24", borderRadius: 14,
          border: "1px solid #1e293b", padding: "20px 24px",
        }}
      >
        <GitCompare size={26} color="#c9a84c" />
        <div style={{ flex: 1 }}>
          <h1 style={{ fontSize: 24, fontWeight: 900, color: "#c9a84c", margin: 0 }}>
            Compare Odds
          </h1>
          <p style={{ fontSize: 13, color: "#94a3b8", margin: "2px 0 0" }}>
            Best price highlighted across all bookmakers — side by side
          </p>
        </div>
      </div>

      {/* Event Selector */}
      <div style={{ display: "flex", gap: 10, marginBottom: 20, flexWrap: "wrap", alignItems: "center" }}>
        <div style={{ position: "relative" }}>
          <Search size={14} style={{ position: "absolute", left: 10, top: "50%", transform: "translateY(-50%)", color: "#64748b" }} />
          <input
            type="text"
            placeholder="Search teams..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            style={{
              padding: "8px 14px 8px 32px", borderRadius: 10, fontSize: 13,
              background: "#0a0f24", border: "1px solid #1e293b",
              color: "#f0f6fc", outline: "none", minWidth: 200,
            }}
          />
        </div>
        {filteredGames.map((g, i) => {
          const isSelected = g.game_id === selectedGameId;
          return (
            <button
              key={g.game_id || i}
              onClick={() => loadCompare(g.game_id || g.id)}
              style={{
                padding: "8px 14px", borderRadius: 10, fontSize: 12, fontWeight: 600,
                border: isSelected ? "1px solid #c9a84c" : "1px solid #1e293b",
                background: isSelected ? "rgba(201,168,76,0.1)" : "#0a0f24",
                color: isSelected ? "#c9a84c" : "#94a3b8",
                cursor: "pointer", whiteSpace: "nowrap",
              }}
            >
              {(g.away_team_name || "AWY")?.substring(0, 3)} @ {(g.home_team_name || "HOM")?.substring(0, 3)}
            </button>
          );
        })}
      </div>

      {comparing && (
        <div style={{ textAlign: "center", padding: 60, color: "#94a3b8" }}>
          Loading comparison data...
        </div>
      )}

      {compareData && !comparing && (
        <>
          {/* Market tabs */}
          <div style={{ display: "flex", gap: 6, marginBottom: 20 }}>
            {TABS.map((t) => (
              <button
                key={t.key}
                onClick={() => setActiveTab(t.key)}
                style={{
                  padding: "8px 16px", borderRadius: 10, fontSize: 12, fontWeight: 600,
                  border: activeTab === t.key ? "1px solid #c9a84c" : "1px solid #1e293b",
                  background: activeTab === t.key ? "rgba(201,168,76,0.1)" : "#0a0f24",
                  color: activeTab === t.key ? "#c9a84c" : "#94a3b8",
                  cursor: "pointer",
                }}
              >
                {t.label}
              </button>
            ))}
          </div>

          {/* Comparison table */}
          {activeTab !== "props" && books.length > 0 && (
            <div
              style={{
                background: "#0a0f24", borderRadius: 14,
                border: "1px solid #1e293b", overflow: "hidden",
              }}
            >
              <div
                style={{
                  display: "grid", gridTemplateColumns: "2fr 1fr 1fr 80px",
                  padding: "12px 20px", background: "rgba(201,168,76,0.08)",
                  borderBottom: "1px solid #1e293b", fontSize: 11, fontWeight: 700,
                  color: "#c9a84c", textTransform: "uppercase",
                }}
              >
                <span>Bookmaker</span>
                <span style={{ textAlign: "center" }}>
                  {compareData?.home_team || "Home"}
                </span>
                <span style={{ textAlign: "center" }}>
                  {compareData?.away_team || "Away"}
                </span>
                <span style={{ textAlign: "center" }}>Best</span>
              </div>

              {(() => {
                const bestHome = getBestPrice(
                  books.map((b: any) => ({
                    price: activeTab === "spread" ? b?.spread_home
                          : activeTab === "total" ? b?.total
                          : b?.moneyline_home,
                  }))
                );
                const bestAway = getBestPrice(
                  books.map((b: any) => ({
                    price: activeTab === "spread" ? b?.spread_away
                          : activeTab === "total" ? b?.total
                          : b?.moneyline_away,
                  }))
                );

                return books.map((book: any, i: number) => {
                  const hv = activeTab === "spread" ? book?.spread_home
                          : activeTab === "total" ? book?.total
                          : book?.moneyline_home;
                  const av = activeTab === "spread" ? book?.spread_away
                          : activeTab === "total" ? book?.total
                          : book?.moneyline_away;
                  const homeIsBest = bestHome?.price === hv && hv != null;
                  const awayIsBest = bestAway?.price === av && av != null;

                  return (
                    <div
                      key={i}
                      style={{
                        display: "grid", gridTemplateColumns: "2fr 1fr 1fr 80px",
                        padding: "14px 20px",
                        borderBottom: "1px solid #1e293b20",
                        alignItems: "center",
                      }}
                    >
                      <span style={{ fontSize: 13, color: "#94a3b8", fontWeight: 500 }}>
                        {book.bookmaker_name || book.sportsbook || book.name || `Book ${i + 1}`}
                      </span>
                      <span
                        style={{
                          fontSize: 14, fontWeight: homeIsBest ? 800 : 500,
                          color: homeIsBest ? "#c9a84c" : "#f0f6fc",
                          textAlign: "center",
                        }}
                      >
                        {fmt(hv)}{activeTab === "spread" && hv != null ? "" : ""}
                      </span>
                      <span
                        style={{
                          fontSize: 14, fontWeight: awayIsBest ? 800 : 500,
                          color: awayIsBest ? "#c9a84c" : "#f0f6fc",
                          textAlign: "center",
                        }}
                      >
                        {fmt(av)}
                      </span>
                      <span style={{ textAlign: "center" }}>
                        {homeIsBest || awayIsBest ? (
                          <Trophy size={16} color="#c9a84c" />
                        ) : (
                          "—"
                        )}
                      </span>
                    </div>
                  );
                });
              })()}
            </div>
          )}

          {/* Props tab */}
          {activeTab === "props" && (
            <div
              style={{
                background: "#0a0f24", borderRadius: 14,
                border: "1px solid #1e293b", padding: 24, textAlign: "center",
              }}
            >
              <p style={{ color: "#94a3b8", fontSize: 13 }}>
                Full player props comparison available on the{" "}
                <a href="/market-tools/player-props" style={{ color: "#c9a84c" }}>Player Props</a> screen.
              </p>
            </div>
          )}
        </>
      )}

      {!compareData && !comparing && !loading && (
        <div style={{ textAlign: "center", padding: 60, color: "#64748b" }}>
          Select an event to compare odds across bookmakers.
        </div>
      )}
    </div>
  );
}