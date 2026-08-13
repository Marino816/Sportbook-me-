"use client";

import { useState } from "react";
import { Layers, X, ChevronDown, ChevronUp } from "lucide-react";
import { useEvents } from "@/lib/use-events";
import type { SBEvent, SBMarket, SBBookLine } from "@/lib/sbevent";

const LEAGUES = ["MLB", "NFL", "NBA", "NHL", "NCAAF", "NCAAB"] as const;
type League = (typeof LEAGUES)[number];

interface Leg {
  id: string;
  eventName: string;
  market: string;
  selection: string;
  odds: number;
}

function fmtOdds(v: number | null | undefined): string {
  if (v == null) return "—";
  return v > 0 ? `+${v}` : `${v}`;
}

function fmtSpreadVal(v: number | null | undefined): string {
  if (v == null) return "PK";
  return v > 0 ? `+${v}` : `${v}`;
}

/** Best available moneyline odds from the market's books */
function bestMoneyline(books: SBBookLine[]): number | null {
  const odds = books
    .filter((b) => b.available && b.moneyline != null)
    .map((b) => b.moneyline!);
  if (!odds.length) return null;
  return odds.reduce((best, o) => (o > best ? o : best), odds[0]);
}

/** Best available spread odds from the market's books (for the spread side) */
function bestSpreadOdds(books: SBBookLine[]): number | null {
  const odds = books
    .filter((b) => b.available && b.spread != null)
    .map((b) => b.spread!);
  if (!odds.length) return null;
  return odds.reduce((best, o) => (o > best ? o : best), odds[0]);
}

/** Best over/under odds from the market's books */
function bestTotalOdds(books: SBBookLine[]): number | null {
  const odds = books
    .filter((b) => b.available && b.over_under != null)
    .map((b) => b.over_under!);
  if (!odds.length) return null;
  return odds.reduce((best, o) => (o > best ? o : best), odds[0]);
}

function americanToDecimal(am: number): number {
  return am > 0 ? 1 + am / 100 : 1 + 100 / Math.abs(am);
}

export default function ParlayBuilderPage() {
  const [activeLeague, setActiveLeague] = useState<League>("MLB");
  const [legs, setLegs] = useState<Leg[]>([]);
  const [stake, setStake] = useState("10");
  const [expandedEventId, setExpandedEventId] = useState<string | null>(null);
  const [selectedBetType, setSelectedBetType] = useState<string>("moneyline");

  const { events, loading } = useEvents(activeLeague);

  const toggleExpand = (id: string) => {
    setExpandedEventId((prev) => (prev === id ? null : id));
  };

  const addLeg = (
    event: SBEvent,
    market: string,
    selection: string,
    odds: number,
  ) => {
    const evName = `${event.away_team.abbreviation || "AWY"} @ ${event.home_team.abbreviation || "HOM"}`;
    setLegs([
      ...legs,
      {
        id: `${Date.now()}-${Math.random()}`,
        eventName: evName,
        market,
        selection,
        odds,
      },
    ]);
  };

  const removeLeg = (id: string) => setLegs(legs.filter((l) => l.id !== id));

  const calcParlay = () => {
    if (legs.length === 0) return { odds: 0, payout: 0, profit: 0 };
    let totalDec = 1;
    for (const leg of legs) totalDec *= americanToDecimal(leg.odds || 0);
    const st = parseFloat(stake) || 0;
    const payout = totalDec * st;
    const profit = payout - st;
    const amOdds =
      totalDec >= 2
        ? Math.round((totalDec - 1) * 100)
        : Math.round(-100 / (totalDec - 1));
    return { odds: amOdds, payout, profit };
  };

  const result = calcParlay();
  const allSameEvent = legs.length >= 2 && legs.every((l) => l.eventName === legs[0]?.eventName);

  // ── Group markets by bet_type for a given event ──────────────
  function getMarketGroups(evt: SBEvent) {
    const groups: Record<string, SBMarket[]> = {};
    for (const m of evt.markets || []) {
      const key = m.bet_type;
      if (!groups[key]) groups[key] = [];
      groups[key].push(m);
    }
    return groups;
  }

  // ── Render ──────────────────────────────────────────────────
  return (
    <div style={{ maxWidth: 1200, margin: "0 auto", padding: "32px 24px" }}>
      {/* Header */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 14,
          marginBottom: 28,
          background: "#0a0f24",
          borderRadius: 14,
          border: "1px solid #1e293b",
          padding: "20px 24px",
        }}
      >
        <Layers size={26} color="#c9a84c" />
        <div style={{ flex: 1 }}>
          <h1 style={{ fontSize: 24, fontWeight: 900, color: "#c9a84c", margin: 0 }}>
            Parlay Builder
          </h1>
          <p style={{ fontSize: 13, color: "#94a3b8", margin: "2px 0 0" }}>
            Build multi-leg parlays with live pricing — SportsGameOdds
          </p>
        </div>
      </div>

      {/* League tabs */}
      <div style={{ display: "flex", gap: 8, marginBottom: 20, flexWrap: "wrap" }}>
        {LEAGUES.map((lg) => (
          <button
            key={lg}
            onClick={() => {
              setActiveLeague(lg);
              setExpandedEventId(null);
            }}
            style={{
              padding: "8px 14px",
              borderRadius: 10,
              fontSize: 12,
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

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 24 }}>
        {/* Left: Built parlay */}
        <div>
          <div
            style={{
              background: "#0a0f24",
              borderRadius: 16,
              border: "1px solid rgba(201,168,76,0.2)",
              padding: "20px 24px",
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 14 }}>
              <Layers size={18} color="#c9a84c" />
              <span style={{ fontSize: 16, fontWeight: 800, color: "#c9a84c" }}>
                Parlay ({legs.length} legs)
              </span>
              {allSameEvent && (
                <span
                  style={{
                    fontSize: 9,
                    fontWeight: 800,
                    color: "#f97316",
                    padding: "3px 8px",
                    borderRadius: 4,
                    background: "rgba(249,115,22,0.15)",
                  }}
                >
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
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                  padding: "10px 0",
                  borderBottom: "1px solid #1e293b30",
                }}
              >
                <div>
                  <div style={{ fontSize: 13, fontWeight: 600, color: "#f0f6fc" }}>
                    {leg.eventName}
                  </div>
                  <div style={{ fontSize: 11, color: "#94a3b8", marginTop: 2 }}>
                    {leg.market} — {leg.selection} @ {fmtOdds(leg.odds)}
                  </div>
                </div>
                <button
                  onClick={() => removeLeg(leg.id)}
                  style={{ background: "none", border: "none", cursor: "pointer", padding: 4 }}
                >
                  <X size={18} color="#ef4444" />
                </button>
              </div>
            ))}

            {legs.length >= 2 && (
              <div style={{ marginTop: 16, paddingTop: 14, borderTop: "1px solid #1e293b" }}>
                <div style={{ display: "flex", justifyContent: "space-between", padding: "4px 0" }}>
                  <span style={{ fontSize: 13, color: "#94a3b8" }}>Parlay Odds</span>
                  <span style={{ fontSize: 16, fontWeight: 800, color: "#c9a84c" }}>
                    {fmtOdds(result.odds)}
                  </span>
                </div>
                <div style={{ marginTop: 10 }}>
                  <label
                    style={{
                      fontSize: 11,
                      color: "#64748b",
                      display: "block",
                      marginBottom: 4,
                    }}
                  >
                    Stake ($)
                  </label>
                  <input
                    type="text"
                    value={stake}
                    onChange={(e) => setStake(e.target.value)}
                    style={{
                      width: "100%",
                      padding: "8px 12px",
                      borderRadius: 10,
                      background: "#1a1f33",
                      border: "1px solid #1e293b",
                      color: "#f0f6fc",
                      fontSize: 14,
                      fontWeight: 600,
                      outline: "none",
                      boxSizing: "border-box",
                    }}
                  />
                </div>
                <div
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    padding: "4px 0",
                    marginTop: 8,
                  }}
                >
                  <span style={{ fontSize: 13, color: "#94a3b8" }}>Payout</span>
                  <span style={{ fontSize: 15, fontWeight: 800, color: "#c9a84c" }}>
                    ${result.payout.toFixed(2)}
                  </span>
                </div>
                <div style={{ display: "flex", justifyContent: "space-between", padding: "4px 0" }}>
                  <span style={{ fontSize: 13, color: "#94a3b8" }}>Profit</span>
                  <span style={{ fontSize: 15, fontWeight: 800, color: "#c9a84c" }}>
                    ${result.profit.toFixed(2)}
                  </span>
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Right: Event picker */}
        <div>
          <h3
            style={{
              fontSize: 13,
              fontWeight: 700,
              color: "#c9a84c",
              textTransform: "uppercase",
              letterSpacing: 1,
              marginBottom: 14,
            }}
          >
            Add Legs
          </h3>

          {loading && (
            <div style={{ color: "#94a3b8", padding: 40, textAlign: "center" }}>
              Loading events...
            </div>
          )}

          {!loading && events.length === 0 && (
            <div style={{ color: "#64748b", padding: 40, textAlign: "center" }}>
              No events found for {activeLeague}.
            </div>
          )}

          <div style={{ display: "grid", gap: 10 }}>
            {events.map((game) => {
              const isOpen = expandedEventId === game.id;
              const groups = getMarketGroups(game);
              const betTypes = Object.keys(groups);

              return (
                <div
                  key={game.id}
                  style={{
                    background: "#0a0f24",
                    borderRadius: 14,
                    border: "1px solid #1e293b",
                    overflow: "hidden",
                  }}
                >
                  <button
                    onClick={() => toggleExpand(game.id)}
                    style={{
                      display: "flex",
                      justifyContent: "space-between",
                      alignItems: "center",
                      width: "100%",
                      padding: "16px 18px",
                      background: "none",
                      border: "none",
                      cursor: "pointer",
                      color: "#f0f6fc",
                      fontSize: 14,
                      fontWeight: 600,
                    }}
                  >
                    <span>
                      {game.away_team.abbreviation || game.away_team.name} @{" "}
                      {game.home_team.abbreviation || game.home_team.name}
                    </span>
                    {isOpen ? (
                      <ChevronUp size={18} color="#94a3b8" />
                    ) : (
                      <ChevronDown size={18} color="#94a3b8" />
                    )}
                  </button>

                  {isOpen && betTypes.length > 0 && (
                    <div style={{ padding: "0 18px 18px", borderTop: "1px solid #1e293b" }}>
                      {/* Bet type tabs */}
                      <div style={{ display: "flex", gap: 6, margin: "12px 0", flexWrap: "wrap" }}>
                        {betTypes.map((bt) => (
                          <button
                            key={bt}
                            onClick={() => setSelectedBetType(bt)}
                            style={{
                              padding: "6px 14px",
                              borderRadius: 8,
                              fontSize: 11,
                              fontWeight: 600,
                              border:
                                selectedBetType === bt
                                  ? "1px solid #c9a84c"
                                  : "1px solid #1e293b",
                              background:
                                selectedBetType === bt
                                  ? "rgba(201,168,76,0.1)"
                                  : "#1a1f33",
                              color:
                                selectedBetType === bt ? "#c9a84c" : "#94a3b8",
                              cursor: "pointer",
                            }}
                          >
                            {bt === "moneyline"
                              ? "Moneyline"
                              : bt === "spread"
                                ? "Spread"
                                : bt === "total"
                                  ? "Total"
                                  : bt}
                          </button>
                        ))}
                      </div>

                      {/* Market legs for selected bet type */}
                      <MarketLegs
                        betType={selectedBetType}
                        markets={groups[selectedBetType] || []}
                        event={game}
                        onAdd={(market: string, selection: string, odds: number) =>
                          addLeg(game, market, selection, odds)
                        }
                      />
                    </div>
                  )}

                  {isOpen && betTypes.length === 0 && (
                    <div style={{ padding: "0 18px 18px", borderTop: "1px solid #1e293b" }}>
                      <p style={{ color: "#64748b", fontSize: 12, textAlign: "center", padding: 16 }}>
                        No markets available for this event.
                      </p>
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

// ── Market legs sub-component ───────────────────────────────

function MarketLegs({
  betType,
  markets,
  event,
  onAdd,
}: {
  betType: string;
  markets: SBMarket[];
  event: SBEvent;
  onAdd: (market: string, selection: string, odds: number) => void;
}) {
  if (!markets.length) {
    return (
      <p style={{ color: "#64748b", fontSize: 12, textAlign: "center", padding: 10 }}>
        No {betType} markets available.
      </p>
    );
  }

  if (betType === "moneyline") {
    const home = markets.find((m) => m.side?.toLowerCase() === "home");
    const away = markets.find((m) => m.side?.toLowerCase() === "away");
    return (
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
        {away && (
          <SelectionBtn
            label={event.away_team.abbreviation || event.away_team.name || "Away"}
            odds={fmtOdds(bestMoneyline(away.books))}
            onClick={() => {
              const o = bestMoneyline(away.books) ?? -110;
              onAdd("Moneyline", event.away_team.abbreviation || "Away", o);
            }}
          />
        )}
        {home && (
          <SelectionBtn
            label={event.home_team.abbreviation || event.home_team.name || "Home"}
            odds={fmtOdds(bestMoneyline(home.books))}
            onClick={() => {
              const o = bestMoneyline(home.books) ?? -110;
              onAdd("Moneyline", event.home_team.abbreviation || "Home", o);
            }}
          />
        )}
        {!home && !away && (
          <p style={{ color: "#64748b", fontSize: 12, gridColumn: "1 / -1", textAlign: "center" }}>
            No moneyline lines available.
          </p>
        )}
      </div>
    );
  }

  if (betType === "spread") {
    const home = markets.find((m) => m.side?.toLowerCase() === "home");
    const away = markets.find((m) => m.side?.toLowerCase() === "away");
    return (
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
        {away && (
          <SelectionBtn
            label={`${event.away_team.abbreviation || "Away"} ${fmtSpreadVal(away.fair_spread)}`}
            odds={fmtOdds(bestSpreadOdds(away.books))}
            onClick={() => {
              const o = bestSpreadOdds(away.books) ?? -110;
              onAdd("Spread", `${event.away_team.abbreviation || "Away"} ${fmtSpreadVal(away.fair_spread)}`, o);
            }}
          />
        )}
        {home && (
          <SelectionBtn
            label={`${event.home_team.abbreviation || "Home"} ${fmtSpreadVal(home.fair_spread)}`}
            odds={fmtOdds(bestSpreadOdds(home.books))}
            onClick={() => {
              const o = bestSpreadOdds(home.books) ?? -110;
              onAdd("Spread", `${event.home_team.abbreviation || "Home"} ${fmtSpreadVal(home.fair_spread)}`, o);
            }}
          />
        )}
        {!home && !away && (
          <p style={{ color: "#64748b", fontSize: 12, gridColumn: "1 / -1", textAlign: "center" }}>
            No spread lines available.
          </p>
        )}
      </div>
    );
  }

  if (betType === "total") {
    const over = markets.find((m) => m.side?.toLowerCase() === "over");
    const under = markets.find((m) => m.side?.toLowerCase() === "under");
    const line = over?.fair_over_under ?? under?.fair_over_under ?? null;
    return (
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
        <SelectionBtn
          label={`Over ${line ?? "—"}`}
          odds={fmtOdds(over ? bestTotalOdds(over.books) : null)}
          onClick={() => {
            const o = over ? (bestTotalOdds(over.books) ?? -110) : -110;
            onAdd("Total", `Over ${line ?? "—"}`, o);
          }}
        />
        <SelectionBtn
          label={`Under ${line ?? "—"}`}
          odds={fmtOdds(under ? bestTotalOdds(under.books) : null)}
          onClick={() => {
            const o = under ? (bestTotalOdds(under.books) ?? -110) : -110;
            onAdd("Total", `Under ${line ?? "—"}`, o);
          }}
        />
      </div>
    );
  }

  // Generic / player props / other bet types
  return (
    <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
      {markets.map((m) => {
        const label = m.player_name
          ? `${m.player_name} ${m.market_name || m.stat_id || ""}`
          : m.market_name || m.side || m.odd_id;
        const bestOdds = bestMoneyline(m.books);
        return (
          <SelectionBtn
            key={m.odd_id}
            label={label}
            odds={fmtOdds(bestOdds)}
            onClick={() => onAdd(m.bet_type, label, bestOdds ?? -110)}
          />
        );
      })}
    </div>
  );
}

// ── Selection button ─────────────────────────────────────────

function SelectionBtn({
  label,
  odds,
  onClick,
}: {
  label: string;
  odds: string;
  onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      style={{
        padding: "14px",
        borderRadius: 10,
        background: "#1a1f33",
        border: "1px solid #1e293b",
        cursor: "pointer",
        textAlign: "center",
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
      <div style={{ fontSize: 12, fontWeight: 600, color: "#c9a84c", marginTop: 4 }}>
        {odds}
      </div>
    </button>
  );
}