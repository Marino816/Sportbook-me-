"use client";

import { useState, useEffect, useCallback } from "react";
import { Layers, X, ChevronDown, ChevronUp } from "lucide-react";
import { getApiBaseUrl } from "@/lib/api-base-url";

const API_BASE = getApiBaseUrl(process.env.NEXT_PUBLIC_API_URL);

const LEAGUES = ["MLB", "NFL", "NBA", "NHL", "NCAAF", "NCAAB"] as const;
type League = (typeof LEAGUES)[number];

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

interface Leg {
  id: string;
  eventId?: string;
  eventName?: string;
  market?: string;
  selection?: string;
  odds?: number;
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

function formatSpread(v: number | null | undefined): string {
  if (v == null) return "PK";
  return v > 0 ? `+${v}` : `${v}`;
}

export default function ParlayBuilderPage() {
  const [activeLeague, setActiveLeague] = useState<League>("MLB");
  const [events, setEvents] = useState<SgoEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [legs, setLegs] = useState<Leg[]>([]);
  const [stake, setStake] = useState("10");
  const [pickingFor, setPickingFor] = useState<number | null>(null);
  const [selectedMarket, setSelectedMarket] = useState("moneyline");

  // Store loaded odds per event so we have real odds
  const [eventOdds, setEventOdds] = useState<Record<string, SgoBook[]>>({});

  const loadEvents = useCallback(async () => {
    setLoading(true);
    const data = await sgoFetch<{ events: SgoEvent[]; league: string; count: number }>(
      `/events?league=${activeLeague}`
    );
    setEvents(data?.events ?? []);
    setEventOdds({});
    setPickingFor(null);
    setLoading(false);
  }, [activeLeague]);

  useEffect(() => { loadEvents(); }, [loadEvents]);

  const togglePick = async (idx: number) => {
    if (pickingFor === idx) {
      setPickingFor(null);
      return;
    }
    setPickingFor(idx);

    // Load odds for this event if not already loaded
    const evt = events[idx];
    if (!evt || eventOdds[evt.event_id]) return;

    const data = await sgoFetch<{ event_id: string; books: SgoBook[] }>(
      `/events/${evt.event_id}/odds`
    );
    if (data) {
      setEventOdds((prev) => ({ ...prev, [evt.event_id]: data.books }));
    }
  };

  const addLeg = (game: SgoEvent, selection: string, odds: number) => {
    setLegs([...legs, {
      id: `${Date.now()}-${Math.random()}`,
      eventId: game.event_id,
      eventName: `${game.away_team.abbreviation || "AWY"} @ ${game.home_team.abbreviation || "HOM"}`,
      market: selectedMarket,
      selection,
      odds,
    }]);
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

  // Get best consensus odds for an event
  const getEventOdds = (evt: SgoEvent): SgoBook | null => {
    const books = eventOdds[evt.event_id];
    if (!books?.length) return null;
    return books[0]; // Use first (highest-ranked) book
  };

  return (
    <div style={{ maxWidth: 1200, margin: "0 auto", padding: "32px 24px" }}>
      {/* Header */}
      <div style={{
        display: "flex", alignItems: "center", gap: 14, marginBottom: 28,
        background: "#0a0f24", borderRadius: 14, border: "1px solid #1e293b", padding: "20px 24px",
      }}>
        <Layers size={26} color="#c9a84c" />
        <div style={{ flex: 1 }}>
          <h1 style={{ fontSize: 24, fontWeight: 900, color: "#c9a84c", margin: 0 }}>Parlay Builder</h1>
          <p style={{ fontSize: 13, color: "#94a3b8", margin: "2px 0 0" }}>
            Build multi-leg parlays with live pricing — SportsGameOdds
          </p>
        </div>
      </div>

      {/* League tabs */}
      <div style={{ display: "flex", gap: 8, marginBottom: 20, flexWrap: "wrap" }}>
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

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 24 }}>
        {/* Left: Built legs */}
        <div>
          <div style={{
            background: "#0a0f24", borderRadius: 16, border: "1px solid rgba(201,168,76,0.2)",
            padding: "20px 24px",
          }}>
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
                }}>SAME GAME PARLAY</span>
              )}
            </div>

            {legs.length === 0 && (
              <p style={{ color: "#64748b", fontSize: 13, textAlign: "center", padding: 20 }}>
                Add legs from the games on the right.
              </p>
            )}

            {legs.map((leg) => (
              <div key={leg.id} style={{
                display: "flex", justifyContent: "space-between", alignItems: "center",
                padding: "10px 0", borderBottom: "1px solid #1e293b30",
              }}>
                <div>
                  <div style={{ fontSize: 13, fontWeight: 600, color: "#f0f6fc" }}>{leg.eventName}</div>
                  <div style={{ fontSize: 11, color: "#94a3b8", marginTop: 2 }}>
                    {leg.market} — {leg.selection} @ {fmtOdds(leg.odds)}
                  </div>
                </div>
                <button onClick={() => removeLeg(leg.id)} style={{
                  background: "none", border: "none", cursor: "pointer", padding: 4,
                }}>
                  <X size={18} color="#ef4444" />
                </button>
              </div>
            ))}

            {legs.length >= 2 && (
              <div style={{ marginTop: 16, paddingTop: 14, borderTop: "1px solid #1e293b" }}>
                <div style={{ display: "flex", justifyContent: "space-between", padding: "4px 0" }}>
                  <span style={{ fontSize: 13, color: "#94a3b8" }}>Parlay Odds</span>
                  <span style={{ fontSize: 16, fontWeight: 800, color: "#c9a84c" }}>{fmtOdds(result.odds)}</span>
                </div>
                <div style={{ marginTop: 10 }}>
                  <label style={{ fontSize: 11, color: "#64748b", display: "block", marginBottom: 4 }}>Stake ($)</label>
                  <input type="text" value={stake} onChange={(e) => setStake(e.target.value)}
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
                  <span style={{ fontSize: 15, fontWeight: 800, color: "#c9a84c" }}>${result.payout.toFixed(2)}</span>
                </div>
                <div style={{ display: "flex", justifyContent: "space-between", padding: "4px 0" }}>
                  <span style={{ fontSize: 13, color: "#94a3b8" }}>Profit</span>
                  <span style={{ fontSize: 15, fontWeight: 800, color: "#c9a84c" }}>${result.profit.toFixed(2)}</span>
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Right: Event picker */}
        <div>
          <h3 style={{
            fontSize: 13, fontWeight: 700, color: "#c9a84c",
            textTransform: "uppercase", letterSpacing: 1, marginBottom: 14,
          }}>Add Legs</h3>

          {loading && (
            <div style={{ color: "#94a3b8", padding: 40, textAlign: "center" }}>Loading events...</div>
          )}

          <div style={{ display: "grid", gap: 10 }}>
            {events.map((game, gi) => {
              const isOpen = pickingFor === gi;
              const odds = getEventOdds(game);

              return (
                <div key={game.event_id || gi} style={{
                  background: "#0a0f24", borderRadius: 14, border: "1px solid #1e293b", overflow: "hidden",
                }}>
                  <button onClick={() => togglePick(gi)} style={{
                    display: "flex", justifyContent: "space-between", alignItems: "center",
                    width: "100%", padding: "16px 18px",
                    background: "none", border: "none", cursor: "pointer",
                    color: "#f0f6fc", fontSize: 14, fontWeight: 600,
                  }}>
                    <span>
                      {game.away_team.abbreviation || "Away"} @ {game.home_team.abbreviation || "Home"}
                    </span>
                    {isOpen ? <ChevronUp size={18} color="#94a3b8" /> : <ChevronDown size={18} color="#94a3b8" />}
                  </button>

                  {isOpen && (
                    <div style={{ padding: "0 18px 18px", borderTop: "1px solid #1e293b" }}>
                      <div style={{ display: "flex", gap: 6, margin: "12px 0" }}>
                        {(["moneyline", "spread", "total"] as const).map((m) => (
                          <button key={m} onClick={() => setSelectedMarket(m)} style={{
                            padding: "6px 14px", borderRadius: 8, fontSize: 11, fontWeight: 600,
                            border: selectedMarket === m ? "1px solid #c9a84c" : "1px solid #1e293b",
                            background: selectedMarket === m ? "rgba(201,168,76,0.1)" : "#1a1f33",
                            color: selectedMarket === m ? "#c9a84c" : "#94a3b8",
                            cursor: "pointer",
                          }}>
                            {m === "moneyline" ? "Moneyline" : m === "spread" ? "Spread" : "Total"}
                          </button>
                        ))}
                      </div>

                      {selectedMarket === "moneyline" && (
                        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
                          <SelectionBtn
                            label={game.away_team.abbreviation || game.away_team.name || "Away"}
                            odds={fmtOdds(odds?.moneyline_away)}
                            onClick={() => addLeg(game, game.away_team.abbreviation || game.away_team.name || "Away", odds?.moneyline_away ?? -110)}
                          />
                          <SelectionBtn
                            label={game.home_team.abbreviation || game.home_team.name || "Home"}
                            odds={fmtOdds(odds?.moneyline_home)}
                            onClick={() => addLeg(game, game.home_team.abbreviation || game.home_team.name || "Home", odds?.moneyline_home ?? -110)}
                          />
                        </div>
                      )}

                      {selectedMarket === "spread" && (
                        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
                          <SelectionBtn
                            label={game.away_team.abbreviation || game.away_team.name || "Away"}
                            odds={formatSpread(odds?.spread_away)}
                            onClick={() => addLeg(game,
                              `${game.away_team.abbreviation || "Away"} ${formatSpread(odds?.spread_away)}`, -110)}
                          />
                          <SelectionBtn
                            label={game.home_team.abbreviation || game.home_team.name || "Home"}
                            odds={formatSpread(odds?.spread_home)}
                            onClick={() => addLeg(game,
                              `${game.home_team.abbreviation || "Home"} ${formatSpread(odds?.spread_home)}`, -110)}
                          />
                        </div>
                      )}

                      {selectedMarket === "total" && (
                        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
                          <SelectionBtn
                            label={`Over ${odds?.total_over ?? "—"}`}
                            odds={fmtOdds(odds?.total_over)}
                            onClick={() => addLeg(game, `Over ${odds?.total_over ?? "—"}`, odds?.total_over ?? -110)}
                          />
                          <SelectionBtn
                            label={`Under ${odds?.total_under ?? "—"}`}
                            odds={fmtOdds(odds?.total_under)}
                            onClick={() => addLeg(game, `Under ${odds?.total_under ?? "—"}`, odds?.total_under ?? -110)}
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
    <button onClick={onClick} style={{
      padding: "14px", borderRadius: 10,
      background: "#1a1f33", border: "1px solid #1e293b",
      cursor: "pointer", textAlign: "center",
      transition: "all 0.15s",
    }}
      onMouseEnter={(e) => { (e.currentTarget as HTMLElement).style.borderColor = "#c9a84c"; }}
      onMouseLeave={(e) => { (e.currentTarget as HTMLElement).style.borderColor = "#1e293b"; }}
    >
      <div style={{ fontSize: 13, fontWeight: 700, color: "#f0f6fc" }}>{label}</div>
      <div style={{ fontSize: 12, fontWeight: 600, color: "#c9a84c", marginTop: 4 }}>{odds}</div>
    </button>
  );
}