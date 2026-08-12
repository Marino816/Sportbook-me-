"use client";

import { useState, useEffect, useCallback } from "react";
import { TrendingUp, Clock, AlertTriangle } from "lucide-react";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "https://sportbook-me-production.up.railway.app/api";

interface Game {
  game_id: string;
  home_team_name: string;
  away_team_name: string;
  start_time?: string;
  status?: string;
  total_line?: number | null;
  spread_line?: number | null;
  moneyline_home?: number | null;
  moneyline_away?: number | null;
  odds?: any[];
  slate_name?: string;
}

const MOVE_META: Record<string, { color: string; label: string }> = {
  LINE_MOVE: { color: "#fbbf24", label: "Line Move" },
  STEAM_MOVE: { color: "#f97316", label: "Steam Move" },
  REVERSAL: { color: "#ef4444", label: "Reversal" },
};

export default function LiveOddsPage() {
  const [games, setGames] = useState<Game[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [slateId, setSlateId] = useState(1);
  const [search, setSearch] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const token = typeof window !== "undefined" ? localStorage.getItem("sbme_dfs_token") : null;
      const res = await fetch(`${API_URL}/market-tools/live-odds?slate_id=${slateId}`, {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const json = await res.json();
      setGames(json.data?.games || json.games || []);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, [slateId]);

  useEffect(() => { load(); }, [load]);

  const filtered = games.filter((g) => {
    if (!search) return true;
    const q = search.toLowerCase();
    return (
      (g.home_team_name || "").toLowerCase().includes(q) ||
      (g.away_team_name || "").toLowerCase().includes(q)
    );
  });

  const getMovement = (game: Game) => {
    const odds = game.odds || [];
    for (const o of odds) {
      const moves = o?.movements || o?.alerts || [];
      for (const m of moves) {
        const key = m?.type || m?.alert || "";
        if (MOVE_META[key]) return MOVE_META[key];
      }
    }
    return null;
  };

  const fmt = (v: number | null | undefined) => {
    if (v == null) return "—";
    return v > 0 ? `+${v}` : `${v}`;
  };

  const isLive = (g: Game) => g.status === "IN_PLAY" || g.status === "LIVE";

  return (
    <div style={{ maxWidth: 1200, margin: "0 auto", padding: "32px 24px" }}>
      {/* Header */}
      <div
        style={{
          display: "flex", alignItems: "center", gap: 14,
          marginBottom: 28,
          background: "#0a0f24", borderRadius: 14,
          border: "1px solid #1e293b", padding: "20px 24px",
        }}
      >
        <TrendingUp size={26} color="#c9a84c" />
        <div style={{ flex: 1 }}>
          <h1 style={{ fontSize: 24, fontWeight: 900, color: "#c9a84c", margin: 0 }}>
            Live Odds
          </h1>
          <p style={{ fontSize: 13, color: "#94a3b8", margin: "2px 0 0" }}>
            Real-time odds, spreads, and totals with line movement alerts
          </p>
        </div>
        <button
          onClick={load}
          style={{
            padding: "8px 16px", borderRadius: 10,
            background: "rgba(201,168,76,0.1)", border: "1px solid rgba(201,168,76,0.3)",
            color: "#c9a84c", fontWeight: 600, cursor: "pointer", fontSize: 13,
          }}
        >
          Refresh
        </button>
      </div>

      {/* Slate selector + search */}
      <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 20, flexWrap: "wrap" }}>
        {[1, 2, 3].map((id) => (
          <button
            key={id}
            onClick={() => setSlateId(id)}
            style={{
              padding: "8px 18px", borderRadius: 10, fontSize: 13, fontWeight: 600,
              border: slateId === id ? "1px solid #c9a84c" : "1px solid #1e293b",
              background: slateId === id ? "rgba(201,168,76,0.1)" : "#0a0f24",
              color: slateId === id ? "#c9a84c" : "#94a3b8",
              cursor: "pointer",
            }}
          >
            {id === 1 ? "Main Slate" : id === 2 ? "Evening" : "Late"}
          </button>
        ))}
        <input
          type="text"
          placeholder="Search teams..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          style={{
            padding: "8px 14px", borderRadius: 10, fontSize: 13,
            background: "#0a0f24", border: "1px solid #1e293b",
            color: "#f0f6fc", outline: "none", minWidth: 220,
          }}
        />
        <span style={{ fontSize: 12, color: "#64748b", marginLeft: "auto" }}>
          {filtered.length} game{filtered.length !== 1 ? "s" : ""}
        </span>
      </div>

      {loading && (
        <div style={{ textAlign: "center", padding: 60, color: "#94a3b8", fontSize: 14 }}>
          Loading live odds...
        </div>
      )}
      {error && (
        <div style={{ textAlign: "center", padding: 40, color: "#ef4444" }}>{error}</div>
      )}

      {/* Game cards */}
      <div style={{ display: "grid", gap: 14 }}>
        {filtered.map((game, i) => {
          const movement = getMovement(game);
          return (
            <div
              key={game.game_id || i}
              style={{
                background: "#0a0f24", borderRadius: 14,
                border: "1px solid #1e293b", padding: "18px 20px",
              }}
            >
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
                <div>
                  <div style={{ fontSize: 16, fontWeight: 700, color: "#f0f6fc" }}>
                    {game.away_team_name || "Away"} @ {game.home_team_name || "Home"}
                  </div>
                  <div style={{ display: "flex", alignItems: "center", gap: 10, marginTop: 4 }}>
                    {isLive(game) && (
                      <span
                        style={{
                          padding: "2px 8px", borderRadius: 4, fontSize: 10,
                          fontWeight: 700, background: "rgba(239,68,68,0.15)",
                          color: "#ef4444", textTransform: "uppercase",
                        }}
                      >
                        ● LIVE
                      </span>
                    )}
                    {game.start_time && (
                      <span style={{ fontSize: 12, color: "#64748b", display: "flex", alignItems: "center", gap: 4 }}>
                        <Clock size={12} /> {game.start_time}
                      </span>
                    )}
                  </div>
                </div>
                {movement && (
                  <span
                    style={{
                      padding: "4px 10px", borderRadius: 6, fontSize: 11, fontWeight: 700,
                      background: `${movement.color}20`, color: movement.color,
                      border: `1px solid ${movement.color}44`,
                    }}
                  >
                    {movement.label}
                  </span>
                )}
              </div>

              {/* Market odds */}
              <div
                style={{
                  display: "grid", gridTemplateColumns: "repeat(3, 1fr)",
                  gap: 12, marginTop: 14,
                  background: "rgba(201,168,76,0.05)", borderRadius: 10,
                  padding: "12px 16px",
                }}
              >
                <div style={{ textAlign: "center" }}>
                  <div style={{ fontSize: 10, color: "#64748b", textTransform: "uppercase", marginBottom: 4 }}>
                    Moneyline
                  </div>
                  <div style={{ fontSize: 15, fontWeight: 700, color: "#c9a84c" }}>
                    {fmt(game.moneyline_away)} / {fmt(game.moneyline_home)}
                  </div>
                </div>
                <div
                  style={{
                    textAlign: "center",
                    borderLeft: "1px solid #1e293b", borderRight: "1px solid #1e293b",
                  }}
                >
                  <div style={{ fontSize: 10, color: "#64748b", textTransform: "uppercase", marginBottom: 4 }}>
                    Spread
                  </div>
                  <div style={{ fontSize: 15, fontWeight: 700, color: "#c9a84c" }}>
                    {game.spread_line != null
                      ? `${game.spread_line > 0 ? "+" : ""}${game.spread_line}`
                      : "—"}
                  </div>
                </div>
                <div style={{ textAlign: "center" }}>
                  <div style={{ fontSize: 10, color: "#64748b", textTransform: "uppercase", marginBottom: 4 }}>
                    Total
                  </div>
                  <div style={{ fontSize: 15, fontWeight: 700, color: "#c9a84c" }}>
                    {game.total_line != null ? `O/U ${game.total_line}` : "—"}
                  </div>
                </div>
              </div>

              {/* Bookmaker chips */}
              {game.odds && game.odds.length > 0 && (
                <div style={{ display: "flex", gap: 8, marginTop: 12, flexWrap: "wrap" }}>
                  {game.odds.slice(0, 5).map((book: any, bi: number) => (
                    <div
                      key={bi}
                      style={{
                        padding: "6px 12px", borderRadius: 8,
                        background: "#1a1f33", border: "1px solid #1e293b",
                      }}
                    >
                      <span style={{ fontSize: 10, color: "#64748b" }}>
                        {book.bookmaker_name || book.sportsbook || `Book ${bi + 1}`}
                      </span>
                      <span style={{ marginLeft: 6, fontSize: 12, fontWeight: 700, color: "#c9a84c" }}>
                        {fmt(book.moneyline_home)} / {fmt(book.moneyline_away)}
                      </span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          );
        })}
      </div>

      {!loading && filtered.length === 0 && (
        <div style={{ textAlign: "center", padding: 60, color: "#64748b" }}>
          <AlertTriangle size={32} style={{ marginBottom: 12 }} />
          <p>No games available for this slate.</p>
        </div>
      )}
    </div>
  );
}