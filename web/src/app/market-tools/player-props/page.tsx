"use client";

import { useState, useEffect } from "react";
import { UserCheck, Search, TrendingUp, CheckCircle } from "lucide-react";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "https://sportbook-me-production.up.railway.app/api";

export default function PlayerPropsPage() {
  const [players, setPlayers] = useState<any[]>([]);
  const [selectedPlayer, setSelectedPlayer] = useState<any>(null);
  const [props, setProps] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [propsLoading, setPropsLoading] = useState(false);
  const [search, setSearch] = useState("");

  useEffect(() => {
    (async () => {
      try {
        const token = typeof window !== "undefined" ? localStorage.getItem("sbme_dfs_token") : null;
        const res = await fetch(`${API_URL}/intelligence/slate/1`, {
          headers: token ? { Authorization: `Bearer ${token}` } : {},
        });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const json = await res.json();
        setPlayers(json.data?.players || json.players || []);
      } catch (e) {
        console.error(e);
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  const loadProps = async (player: any) => {
    setSelectedPlayer(player);
    setPropsLoading(true);
    try {
      const token = typeof window !== "undefined" ? localStorage.getItem("sbme_dfs_token") : null;
      const pid = player.player_id || player.id;
      const res = await fetch(`${API_URL}/market-tools/player-props?player_id=${pid}`, {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const json = await res.json();
      const pr = json.data?.props || json.props || json.data || [];
      setProps(Array.isArray(pr) ? pr : []);
    } catch (e) {
      setProps([]);
    } finally {
      setPropsLoading(false);
    }
  };

  const filtered = players.filter((p) => {
    if (!search) return true;
    const q = search.toLowerCase();
    return (p.player_name || p.name || "").toLowerCase().includes(q);
  });

  const getBestOver = (prop: any): string => {
    const books = prop?.bookmakers || prop?.books || prop?.odds || [];
    if (!books.length) return "—";
    let best = books[0];
    for (const b of books) {
      if ((b.over_price || b.price || 0) > (best.over_price || best.price || 0)) best = b;
    }
    return `${best.bookmaker_name || "Book"} ${best.over_price || best.price || "—"}`;
  };

  const getLineRange = (prop: any) => {
    const books = prop?.bookmakers || prop?.books || prop?.odds || [];
    if (!books.length) return "—";
    let min = Infinity, max = -Infinity;
    for (const b of books) {
      const l = b.line || b.points || 0;
      if (l < min) min = l;
      if (l > max) max = l;
    }
    return min === max ? `${min}` : `${min} – ${max}`;
  };

  const fmt = (v: number | null | undefined) => {
    if (v == null) return "—";
    return v > 0 ? `+${v}` : `${v}`;
  };

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
        <UserCheck size={26} color="#c9a84c" />
        <div style={{ flex: 1 }}>
          <h1 style={{ fontSize: 24, fontWeight: 900, color: "#c9a84c", margin: 0 }}>
            Player Props
          </h1>
          <p style={{ fontSize: 13, color: "#94a3b8", margin: "2px 0 0" }}>
            Prop bets across sportsbooks connected to DFS projections
          </p>
        </div>
      </div>

      {/* Search + player chips */}
      <div style={{ marginBottom: 20 }}>
        <div style={{ position: "relative", marginBottom: 12 }}>
          <Search size={14} style={{ position: "absolute", left: 10, top: "50%", transform: "translateY(-50%)", color: "#64748b" }} />
          <input
            type="text"
            placeholder="Search players..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            style={{
              padding: "10px 14px 10px 32px", borderRadius: 10, fontSize: 14,
              background: "#0a0f24", border: "1px solid #1e293b",
              color: "#f0f6fc", outline: "none", width: "100%", maxWidth: 400,
            }}
          />
        </div>
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
          {filtered.slice(0, 30).map((p, i) => {
            const isSelected = (p.player_id || p.id) === (selectedPlayer?.player_id || selectedPlayer?.id);
            return (
              <button
                key={i}
                onClick={() => loadProps(p)}
                style={{
                  padding: "10px 16px", borderRadius: 12, fontSize: 13, fontWeight: 700,
                  border: isSelected ? "1px solid #c9a84c" : "1px solid #1e293b",
                  background: isSelected ? "rgba(201,168,76,0.1)" : "#0a0f24",
                  color: isSelected ? "#c9a84c" : "#f0f6fc",
                  cursor: "pointer",
                }}
              >
                {p.player_name || p.name || `#${p.player_id || p.id}`}
                <span style={{ display: "block", fontSize: 10, color: "#64748b", marginTop: 2 }}>
                  {p.position || ""}{p.dfs_salary ? ` · $${p.dfs_salary}` : ""}
                </span>
              </button>
            );
          })}
        </div>
      </div>

      {/* DFS Projection card */}
      {selectedPlayer && (
        <div
          style={{
            display: "flex", alignItems: "center", gap: 12, marginBottom: 24,
            background: "#0a0f24", borderRadius: 14,
            border: "1px solid rgba(201,168,76,0.25)", padding: "18px 20px",
          }}
        >
          <TrendingUp size={22} color="#c9a84c" />
          <div>
            <div style={{ fontSize: 11, color: "#64748b", fontWeight: 600, textTransform: "uppercase" }}>
              DFS Projection
            </div>
            <div style={{ fontSize: 18, fontWeight: 800, color: "#c9a84c", marginTop: 2 }}>
              {selectedPlayer.base_projection || selectedPlayer.projected_fp || "—"} pts
              {selectedPlayer.fantasy_market_line != null && (
                <span style={{ fontSize: 13, color: "#94a3b8", fontWeight: 400 }}>
                  {" "}· Market: {selectedPlayer.fantasy_market_line}
                  {selectedPlayer.fantasy_market_edge != null && (
                    <span style={{ color: selectedPlayer.fantasy_market_edge > 0 ? "#c9a84c" : "#ef4444", fontWeight: 600 }}>
                      {" "}(Edge: {selectedPlayer.fantasy_market_edge > 0 ? "+" : ""}{selectedPlayer.fantasy_market_edge})
                    </span>
                  )}
                </span>
              )}
            </div>
          </div>
        </div>
      )}

      {propsLoading && (
        <div style={{ textAlign: "center", padding: 40, color: "#94a3b8" }}>
          Loading player props...
        </div>
      )}

      {/* Props grid */}
      {!propsLoading && selectedPlayer && props.length > 0 && (
        <div style={{ display: "grid", gap: 14 }}>
          {props.map((prop, i) => {
            const books = prop?.bookmakers || prop?.books || prop?.odds || [];
            const lineCount: Record<string, number> = {};
            for (const b of books) {
              const l = String(b.line || b.points || "");
              lineCount[l] = (lineCount[l] || 0) + 1;
            }
            let consensus = "—", maxCount = 0;
            for (const [l, c] of Object.entries(lineCount)) {
              if (c > maxCount) { consensus = l; maxCount = c; }
            }

            return (
              <div
                key={i}
                style={{
                  background: "#0a0f24", borderRadius: 14,
                  border: "1px solid #1e293b", padding: "18px 20px",
                }}
              >
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
                  <span style={{ fontSize: 15, fontWeight: 700, color: "#f0f6fc" }}>
                    {prop.market_type || prop.market || prop.name || `Prop ${i + 1}`}
                  </span>
                  {maxCount >= 2 && (
                    <span style={{
                      display: "flex", alignItems: "center", gap: 4,
                      fontSize: 11, color: "#c9a84c", fontWeight: 600,
                    }}>
                      <CheckCircle size={12} /> Consensus: {consensus}
                    </span>
                  )}
                </div>

                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12, marginBottom: 12 }}>
                  <div style={{
                    background: "rgba(201,168,76,0.05)", borderRadius: 8, padding: "8px 12px",
                  }}>
                    <div style={{ fontSize: 10, color: "#64748b", marginBottom: 2 }}>Best Over Price</div>
                    <div style={{ fontSize: 13, fontWeight: 700, color: "#c9a84c" }}>{getBestOver(prop)}</div>
                  </div>
                  <div style={{
                    background: "rgba(201,168,76,0.05)", borderRadius: 8, padding: "8px 12px",
                  }}>
                    <div style={{ fontSize: 10, color: "#64748b", marginBottom: 2 }}>Line Range</div>
                    <div style={{ fontSize: 13, fontWeight: 700, color: "#c9a84c" }}>{getLineRange(prop)}</div>
                  </div>
                </div>

                {books.length > 0 && (
                  <div style={{ borderTop: "1px solid #1e293b", paddingTop: 10 }}>
                    {books.slice(0, 6).map((b: any, bi: number) => (
                      <div
                        key={bi}
                        style={{
                          display: "grid", gridTemplateColumns: "2fr 80px 1fr",
                          padding: "6px 0", alignItems: "center",
                        }}
                      >
                        <span style={{ fontSize: 12, color: "#94a3b8" }}>
                          {b.bookmaker_name || `Book ${bi + 1}`}
                        </span>
                        <span style={{ fontSize: 13, fontWeight: 700, color: "#f0f6fc", textAlign: "center" }}>
                          {b.line || b.points || "—"}
                        </span>
                        <span style={{ fontSize: 12, color: "#c9a84c", textAlign: "right" }}>
                          O {fmt(b.over_price)} / U {fmt(b.under_price)}
                        </span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}

      {!propsLoading && selectedPlayer && props.length === 0 && (
        <div style={{ textAlign: "center", padding: 60, color: "#64748b" }}>
          No player props available from connected sportsbooks.
        </div>
      )}

      {!selectedPlayer && !loading && (
        <div style={{ textAlign: "center", padding: 60, color: "#64748b" }}>
          Select a player to view available prop bets.
        </div>
      )}
    </div>
  );
}