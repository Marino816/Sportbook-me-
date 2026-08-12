"use client";

import { useState, useEffect } from "react";
import { Layers, X, ChevronDown, ChevronUp } from "lucide-react";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "https://sportbook-me-production.up.railway.app/api";

interface Leg {
  id: string;
  eventId?: string;
  eventName?: string;
  market?: string;
  selection?: string;
  odds?: number;
}

export default function ParlayBuilderPage() {
  const [games, setGames] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [legs, setLegs] = useState<Leg[]>([]);
  const [stake, setStake] = useState("10");
  const [pickingFor, setPickingFor] = useState<number | null>(null);
  const [selectedMarket, setSelectedMarket] = useState("moneyline");

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

  const addLeg = (game: any, selection: string, odds: number) => {
    setLegs([
      ...legs,
      {
        id: `${Date.now()}-${Math.random()}`,
        eventId: game.game_id || game.id,
        eventName: `${game.away_team_name || "AWY"} @ ${game.home_team_name || "HOM"}`,
        market: selectedMarket,
        selection,
        odds,
      },
    ]);
    setPickingFor(null);
  };

  const removeLeg = (id: string) => setLegs(legs.filter((l) => l.id !== id));

  const americanToDecimal = (am: number): number =>
    am > 0 ? 1 + am / 100 : 1 + 100 / Math.abs(am);

  const calcParlay = () => {
    if (legs.length === 0) return { odds: 0, payout: 0, profit: 0 };
    let totalDecimal = 1;
    for (const leg of legs) totalDecimal *= americanToDecimal(leg.odds || 0);
    const st = parseFloat(stake) || 0;
    const payout = totalDecimal * st;
    const profit = payout - st;
    const amOdds = totalDecimal >= 2
      ? Math.round((totalDecimal - 1) * 100)
      : Math.round(-100 / (totalDecimal - 1));
    return { odds: amOdds, payout, profit };
  };

  const result = calcParlay();
  const isSGP = legs.length >= 2 && legs.every((l) => l.eventId === legs[0]?.eventId);

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
        <Layers size={26} color="#c9a84c" />
        <div style={{ flex: 1 }}>
          <h1 style={{ fontSize: 24, fontWeight: 900, color: "#c9a84c", margin: 0 }}>
            Parlay Builder
          </h1>
          <p style={{ fontSize: 13, color: "#94a3b8", margin: "2px 0 0" }}>
            Build multi-leg parlays with live pricing & same game parlay detection
          </p>
        </div>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 24 }}>
        {/* Left: Legs */}
        <div>
          <div
            style={{
              background: "#0a0f24", borderRadius: 16,
              border: "1px solid rgba(201,168,76,0.2)", padding: "20px 24px",
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 14 }}>
              <Layers size={18} color="#c9a84c" />
              <span style={{ fontSize: 16, fontWeight: 800, color: "#c9a84c" }}>
                Parlay ({legs.length} legs)
              </span>
              {isSGP && (
                <span style={{
                  fontSize: 9, fontWeight: 800, color: "#f97316",
                  padding: "3px 8px", borderRadius: 4,
                  background: "rgba(249,115,22,0.15)",
                }}>
                  SAME GAME PARLAY
                </span>
              )}
            </div>

            {legs.length === 0 && (
              <p style={{ color: "#64748b", fontSize: 13, textAlign: "center", padding: 20 }}>
                Add legs from the games on the right.
              </p>
            )}

            {legs.map((leg) => (
              <div
                key={leg.id}
                style={{
                  display: "flex", justifyContent: "space-between", alignItems: "center",
                  padding: "10px 0", borderBottom: "1px solid #1e293b30",
                }}
              >
                <div>
                  <div style={{ fontSize: 13, fontWeight: 600, color: "#f0f6fc" }}>
                    {leg.eventName}
                  </div>
                  <div style={{ fontSize: 11, color: "#94a3b8", marginTop: 2 }}>
                    {leg.market} — {leg.selection} @ {fmt(leg.odds)}
                  </div>
                </div>
                <button
                  onClick={() => removeLeg(leg.id)}
                  style={{
                    background: "none", border: "none", cursor: "pointer",
                    padding: 4,
                  }}
                >
                  <X size={18} color="#ef4444" />
                </button>
              </div>
            ))}

            {/* Running odds */}
            {legs.length >= 2 && (
              <div style={{ marginTop: 16, paddingTop: 14, borderTop: "1px solid #1e293b" }}>
                <div style={{ display: "flex", justifyContent: "space-between", padding: "4px 0" }}>
                  <span style={{ fontSize: 13, color: "#94a3b8" }}>Parlay Odds</span>
                  <span style={{ fontSize: 16, fontWeight: 800, color: "#c9a84c" }}>{fmt(result.odds)}</span>
                </div>
                <div style={{ marginTop: 10 }}>
                  <label style={{ fontSize: 11, color: "#64748b", display: "block", marginBottom: 4 }}>
                    Stake ($)
                  </label>
                  <input
                    type="text"
                    value={stake}
                    onChange={(e) => setStake(e.target.value)}
                    style={{
                      width: "100%", padding: "8px 12px", borderRadius: 10,
                      background: "#1a1f33", border: "1px solid #1e293b",
                      color: "#f0f6fc", fontSize: 14, fontWeight: 600,
                      outline: "none", boxSizing: "border-box",
                    }}
                  />
                </div>
                <div style={{ display: "flex", justifyContent: "space-between", padding: "4px 0", marginTop: 8 }}>
                  <span style={{ fontSize: 13, color: "#94a3b8" }}>Payout</span>
                  <span style={{ fontSize: 15, fontWeight: 800, color: "#4ade80" }}>
                    ${result.payout.toFixed(2)}
                  </span>
                </div>
                <div style={{ display: "flex", justifyContent: "space-between", padding: "4px 0" }}>
                  <span style={{ fontSize: 13, color: "#94a3b8" }}>Profit</span>
                  <span style={{ fontSize: 15, fontWeight: 800, color: "#4ade80" }}>
                    ${result.profit.toFixed(2)}
                  </span>
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Right: Game picker */}
        <div>
          <h3
            style={{
              fontSize: 13, fontWeight: 700, color: "#c9a84c",
              textTransform: "uppercase", letterSpacing: 1, marginBottom: 14,
            }}
          >
            Add Legs
          </h3>

          {loading && (
            <div style={{ color: "#94a3b8", padding: 40, textAlign: "center" }}>
              Loading games...
            </div>
          )}

          <div style={{ display: "grid", gap: 10 }}>
            {games.map((game, gi) => {
              const isOpen = pickingFor === gi;
              return (
                <div
                  key={game.game_id || gi}
                  style={{
                    background: "#0a0f24", borderRadius: 14,
                    border: "1px solid #1e293b", overflow: "hidden",
                  }}
                >
                  <button
                    onClick={() => setPickingFor(isOpen ? null : gi)}
                    style={{
                      display: "flex", justifyContent: "space-between", alignItems: "center",
                      width: "100%", padding: "16px 18px",
                      background: "none", border: "none", cursor: "pointer",
                      color: "#f0f6fc", fontSize: 14, fontWeight: 600,
                    }}
                  >
                    <span>
                      {game.away_team_name || "Away"} @ {game.home_team_name || "Home"}
                    </span>
                    {isOpen ? <ChevronUp size={18} color="#94a3b8" /> : <ChevronDown size={18} color="#94a3b8" />}
                  </button>

                  {isOpen && (
                    <div style={{ padding: "0 18px 18px", borderTop: "1px solid #1e293b" }}>
                      {/* Market selector */}
                      <div style={{ display: "flex", gap: 6, margin: "12px 0" }}>
                        {(["moneyline", "spread", "total"] as const).map((m) => (
                          <button
                            key={m}
                            onClick={() => setSelectedMarket(m)}
                            style={{
                              padding: "6px 14px", borderRadius: 8, fontSize: 11, fontWeight: 600,
                              border: selectedMarket === m
                                ? "1px solid #c9a84c"
                                : "1px solid #1e293b",
                              background: selectedMarket === m
                                ? "rgba(201,168,76,0.1)"
                                : "#1a1f33",
                              color: selectedMarket === m ? "#c9a84c" : "#94a3b8",
                              cursor: "pointer",
                            }}
                          >
                            {m === "moneyline" ? "Moneyline" : m === "spread" ? "Spread" : "Total"}
                          </button>
                        ))}
                      </div>

                      {/* Selections */}
                      {selectedMarket === "moneyline" && (
                        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
                          <SelectionBtn
                            label={game.away_team_name || "Away"}
                            odds={fmt(game.moneyline_away)}
                            onClick={() => addLeg(game, game.away_team_name || "Away", game.moneyline_away || -110)}
                          />
                          <SelectionBtn
                            label={game.home_team_name || "Home"}
                            odds={fmt(game.moneyline_home)}
                            onClick={() => addLeg(game, game.home_team_name || "Home", game.moneyline_home || -110)}
                          />
                        </div>
                      )}

                      {selectedMarket === "spread" && (
                        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
                          <SelectionBtn
                            label={game.away_team_name || "Away"}
                            odds={game.spread_line != null
                              ? (game.spread_line > 0 ? "+" : "") + game.spread_line
                              : "PK"}
                            onClick={() =>
                              addLeg(
                                game,
                                `${game.away_team_name || "Away"} ${game.spread_line != null ? (game.spread_line > 0 ? "+" : "") + game.spread_line : "PK"}`,
                                -110,
                              )
                            }
                          />
                          <SelectionBtn
                            label={game.home_team_name || "Home"}
                            odds={game.spread_line != null
                              ? (game.spread_line < 0 ? "" : "-") + Math.abs(game.spread_line)
                              : "PK"}
                            onClick={() =>
                              addLeg(
                                game,
                                `${game.home_team_name || "Home"} ${game.spread_line != null ? (game.spread_line < 0 ? "" : "-") + Math.abs(game.spread_line) : "PK"}`,
                                -110,
                              )
                            }
                          />
                        </div>
                      )}

                      {selectedMarket === "total" && (
                        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
                          <SelectionBtn
                            label="Over"
                            odds={game.total_line || "—"}
                            onClick={() => addLeg(game, `Over ${game.total_line || "—"}`, -110)}
                          />
                          <SelectionBtn
                            label="Under"
                            odds={game.total_line || "—"}
                            onClick={() => addLeg(game, `Under ${game.total_line || "—"}`, -110)}
                          />
                        </div>
                      )}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
}

function SelectionBtn({ label, odds, onClick }: {
  label: string; odds: string; onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      style={{
        padding: "14px", borderRadius: 10,
        background: "#1a1f33", border: "1px solid #1e293b",
        cursor: "pointer", textAlign: "center",
        transition: "all 0.15s",
      }}
      onMouseEnter={(e) => {
        (e.currentTarget as HTMLElement).style.borderColor = "#c9a84c";
      }}
      onMouseLeave={(e) => {
        (e.currentTarget as HTMLElement).style.borderColor = "#1e293b";
      }}
    >
      <div style={{ fontSize: 13, fontWeight: 700, color: "#f0f6fc" }}>{label}</div>
      <div style={{ fontSize: 12, fontWeight: 600, color: "#c9a84c", marginTop: 4 }}>{odds}</div>
    </button>
  );
}