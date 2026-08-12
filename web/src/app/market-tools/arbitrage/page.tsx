"use client";

import { useState, useEffect, useCallback } from "react";
import { Calculator, Scan, AlertTriangle, Info } from "lucide-react";
import { getApiBaseUrl } from "@/lib/api-base-url";

const API_BASE = getApiBaseUrl(process.env.NEXT_PUBLIC_API_URL);

const LEAGUES = ["MLB", "NFL", "NBA", "NHL", "NCAAF", "NCAAB"] as const;
type League = (typeof LEAGUES)[number];

interface SgoEvent {
  event_id: string;
  home_team: { name: string; abbreviation: string };
  away_team: { name: string; abbreviation: string };
}

interface SgoBook {
  bookmaker: string;
  moneyline_home: number | null;
  moneyline_away: number | null;
}

interface ArbOpp {
  event: string;
  event_id: string;
  home_book: string;
  home_odds: number;
  away_book: string;
  away_odds: number;
  arb_pct: number;
  payout: number;
  profit: number;
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

function americanToDecimal(am: number): number {
  return am > 0 ? 1 + am / 100 : 1 + 100 / Math.abs(am);
}

function fmtOdds(v: number | null | undefined): string {
  if (v == null) return "—";
  return v > 0 ? `+${v}` : `${v}`;
}

export default function ArbitragePage() {
  const [tab, setTab] = useState<"scanner" | "calculator">("scanner");
  const [activeLeague, setActiveLeague] = useState<League>("MLB");

  // Scanner
  const [opportunities, setOpportunities] = useState<ArbOpp[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Calculator
  const [oddsA, setOddsA] = useState("");
  const [oddsB, setOddsB] = useState("");
  const [oddsC, setOddsC] = useState("");
  const [bankroll, setBankroll] = useState("100");
  const [isThreeWay, setIsThreeWay] = useState(false);
  const [calcResult, setCalcResult] = useState<any>(null);

  const scanArbitrage = useCallback(async () => {
    setLoading(true);
    setError(null);

    try {
      // Fetch events for league
      const eventsData = await sgoFetch<{ events: SgoEvent[] }>(`/events?league=${activeLeague}`);
      const events = eventsData?.events ?? [];
      if (!events.length) {
        setOpportunities([]);
        setLoading(false);
        return;
      }

      const found: ArbOpp[] = [];
      // Scan up to 6 events
      for (const evt of events.slice(0, 6)) {
        try {
          const oddsData = await sgoFetch<{ event_id: string; books: SgoBook[] }>(
            `/events/${evt.event_id}/odds`
          );
          const books = oddsData?.books ?? [];
          if (books.length < 2) continue;

          const matchName = `${evt.away_team.abbreviation || "AWY"} @ ${evt.home_team.abbreviation || "HOM"}`;

          // Check all pairs of books for moneyline arb
          for (let i = 0; i < books.length; i++) {
            for (let j = i + 1; j < books.length; j++) {
              const bh = books[i].moneyline_home;
              const ba = books[j].moneyline_away;
              if (bh == null || ba == null) continue;

              const decH = americanToDecimal(bh);
              const decA = americanToDecimal(ba);
              const implied = (1 / decH + 1 / decA) * 100;

              if (implied < 100) {
                const arb = 100 - implied;
                const stake1 = (100 * (1 / decH)) / (implied / 100);
                const stake2 = (100 * (1 / decA)) / (implied / 100);
                const payout = Math.min(stake1 * decH, stake2 * decA);

                found.push({
                  event: matchName,
                  event_id: evt.event_id,
                  home_book: books[i].bookmaker,
                  home_odds: bh,
                  away_book: books[j].bookmaker,
                  away_odds: ba,
                  arb_pct: Math.round(arb * 100) / 100,
                  payout: Math.round(payout * 100) / 100,
                  profit: Math.round((payout - 100) * 100) / 100,
                });
              }

              // Also check reverse pairing
              const bh2 = books[j].moneyline_home;
              const ba2 = books[i].moneyline_away;
              if (bh2 == null || ba2 == null) continue;

              const decH2 = americanToDecimal(bh2);
              const decA2 = americanToDecimal(ba2);
              const implied2 = (1 / decH2 + 1 / decA2) * 100;

              if (implied2 < 100) {
                const arb2 = 100 - implied2;
                const stake1b = (100 * (1 / decH2)) / (implied2 / 100);
                const stake2b = (100 * (1 / decA2)) / (implied2 / 100);
                const payout2 = Math.min(stake1b * decH2, stake2b * decA2);

                found.push({
                  event: matchName,
                  event_id: evt.event_id,
                  home_book: books[j].bookmaker,
                  home_odds: bh2,
                  away_book: books[i].bookmaker,
                  away_odds: ba2,
                  arb_pct: Math.round(arb2 * 100) / 100,
                  payout: Math.round(payout2 * 100) / 100,
                  profit: Math.round((payout2 - 100) * 100) / 100,
                });
              }
            }
          }
        } catch {
          continue;
        }
      }

      // Sort by arb_pct descending
      found.sort((a, b) => b.arb_pct - a.arb_pct);
      setOpportunities(found.slice(0, 20));
    } catch (e: any) {
      setError(e.message || "Scan failed");
    } finally {
      setLoading(false);
    }
  }, [activeLeague]);

  useEffect(() => {
    if (tab === "scanner") scanArbitrage();
  }, [tab, scanArbitrage]);

  const calculate = () => {
    const a = parseFloat(oddsA);
    const b = parseFloat(oddsB);
    const c = parseFloat(oddsC);
    const br = parseFloat(bankroll) || 100;

    if (isNaN(a) || isNaN(b)) {
      setCalcResult({ error: "Enter American odds for both sides" });
      return;
    }

    const decA = americanToDecimal(a);
    const decB = americanToDecimal(b);

    if (isThreeWay) {
      if (isNaN(c)) { setCalcResult({ error: "Enter odds for all three outcomes" }); return; }
      const decC = americanToDecimal(c);
      const it = (1 / decA + 1 / decB + 1 / decC) * 100;
      const arb = it < 100 ? 100 - it : null;
      if (!arb || arb < 0) {
        setCalcResult({ impliedTotal: it.toFixed(2), arbPct: null, message: "No arbitrage opportunity" });
        return;
      }
      const stakeA = (br * (1 / decA)) / (it / 100);
      const stakeB = (br * (1 / decB)) / (it / 100);
      const stakeC = (br * (1 / decC)) / (it / 100);
      const payout = Math.min(stakeA * decA, stakeB * decB, stakeC * decC);
      setCalcResult({
        impliedTotal: it.toFixed(2), arbPct: arb.toFixed(2),
        stakes: { A: stakeA.toFixed(2), B: stakeB.toFixed(2), C: stakeC.toFixed(2) },
        payout: payout.toFixed(2), profit: (payout - br).toFixed(2),
      });
    } else {
      const it = (1 / decA + 1 / decB) * 100;
      const arb = it < 100 ? 100 - it : null;
      if (!arb || arb < 0) {
        setCalcResult({ impliedTotal: it.toFixed(2), arbPct: null, message: "No arbitrage — implied total ≥ 100%" });
        return;
      }
      const stakeA = (br * (1 / decA)) / (it / 100);
      const stakeB = (br * (1 / decB)) / (it / 100);
      const payout = Math.min(stakeA * decA, stakeB * decB);
      setCalcResult({
        impliedTotal: it.toFixed(2), arbPct: arb.toFixed(2),
        stakes: { A: stakeA.toFixed(2), B: stakeB.toFixed(2) },
        payout: payout.toFixed(2), profit: (payout - br).toFixed(2),
      });
    }
  };

  return (
    <div style={{ maxWidth: 1200, margin: "0 auto", padding: "32px 24px" }}>
      {/* Header */}
      <div style={{
        display: "flex", alignItems: "center", gap: 14, marginBottom: 28,
        background: "#0a0f24", borderRadius: 14, border: "1px solid #1e293b", padding: "20px 24px",
      }}>
        <Calculator size={26} color="#c9a84c" />
        <div style={{ flex: 1 }}>
          <h1 style={{ fontSize: 24, fontWeight: 900, color: "#c9a84c", margin: 0 }}>Arbitrage</h1>
          <p style={{ fontSize: 13, color: "#94a3b8", margin: "2px 0 0" }}>
            Auto scanner & manual calculator — SportsGameOdds
          </p>
        </div>
      </div>

      {/* Tab toggle */}
      <div style={{ display: "flex", gap: 10, marginBottom: 24 }}>
        <button onClick={() => setTab("scanner")} style={{
          display: "flex", alignItems: "center", gap: 6,
          padding: "10px 20px", borderRadius: 12, fontSize: 13, fontWeight: 600,
          border: tab === "scanner" ? "1px solid #c9a84c" : "1px solid #1e293b",
          background: tab === "scanner" ? "rgba(201,168,76,0.1)" : "#0a0f24",
          color: tab === "scanner" ? "#c9a84c" : "#94a3b8",
          cursor: "pointer",
        }}>
          <Scan size={16} /> Auto Scanner
        </button>
        <button onClick={() => setTab("calculator")} style={{
          display: "flex", alignItems: "center", gap: 6,
          padding: "10px 20px", borderRadius: 12, fontSize: 13, fontWeight: 600,
          border: tab === "calculator" ? "1px solid #c9a84c" : "1px solid #1e293b",
          background: tab === "calculator" ? "rgba(201,168,76,0.1)" : "#0a0f24",
          color: tab === "calculator" ? "#c9a84c" : "#94a3b8",
          cursor: "pointer",
        }}>
          <Calculator size={16} /> Manual Calculator
        </button>
      </div>

      {/* Scanner */}
      {tab === "scanner" && (
        <>
          {/* League selector */}
          <div style={{ display: "flex", gap: 8, marginBottom: 16, flexWrap: "wrap" }}>
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

          {loading && (
            <div style={{ textAlign: "center", padding: 40, color: "#94a3b8" }}>
              Scanning {activeLeague} events for arbitrage opportunities...
            </div>
          )}
          {error && (
            <div style={{ padding: 20, color: "#ef4444", textAlign: "center" }}>{error}</div>
          )}
          {!loading && opportunities.length === 0 && (
            <div style={{ textAlign: "center", padding: 60, color: "#64748b" }}>
              <AlertTriangle size={32} style={{ marginBottom: 12 }} />
              <p>No arbitrage opportunities found for {activeLeague}. Try another league.</p>
            </div>
          )}
          <div style={{ display: "grid", gap: 14 }}>
            {opportunities.map((opp, i) => (
              <div key={i} style={{
                background: "#0a0f24", borderRadius: 14, border: "1px solid #1e293b", padding: "18px 20px",
              }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
                  <span style={{ fontSize: 15, fontWeight: 700, color: "#f0f6fc" }}>{opp.event}</span>
                  <span style={{
                    padding: "4px 12px", borderRadius: 6, fontSize: 13, fontWeight: 800,
                    background: "rgba(201,168,76,0.15)", color: "#c9a84c",
                  }}>
                    {opp.arb_pct}%
                  </span>
                </div>
                <div style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
                  <div style={{ textAlign: "center", minWidth: 60 }}>
                    <div style={{ fontSize: 10, color: "#64748b" }}>{opp.home_book}</div>
                    <div style={{ fontSize: 15, fontWeight: 700, color: "#c9a84c" }}>{fmtOdds(opp.home_odds)}</div>
                  </div>
                  <span style={{ color: "#64748b" }}>→</span>
                  <div style={{ textAlign: "center", minWidth: 60 }}>
                    <div style={{ fontSize: 10, color: "#64748b" }}>{opp.away_book}</div>
                    <div style={{ fontSize: 15, fontWeight: 700, color: "#c9a84c" }}>{fmtOdds(opp.away_odds)}</div>
                  </div>
                </div>
                <div style={{ fontSize: 12, color: "#94a3b8", marginTop: 10 }}>
                  Payout: ${opp.payout} on $100 · Profit: ${opp.profit}
                </div>
              </div>
            ))}
          </div>
        </>
      )}

      {/* Calculator */}
      {tab === "calculator" && (
        <>
          <div style={{
            background: "#0a0f24", borderRadius: 16, border: "1px solid #1e293b",
            padding: "24px 28px", maxWidth: 500,
          }}>
            <h3 style={{ fontSize: 18, fontWeight: 800, color: "#c9a84c", margin: "0 0 20px" }}>
              Arbitrage Calculator
            </h3>

            <div style={{ display: "flex", gap: 8, marginBottom: 18 }}>
              <button onClick={() => setIsThreeWay(false)} style={{
                flex: 1, padding: "8px", borderRadius: 10, fontSize: 13, fontWeight: 600,
                border: !isThreeWay ? "1px solid #c9a84c" : "1px solid #1e293b",
                background: !isThreeWay ? "rgba(201,168,76,0.1)" : "#1a1f33",
                color: !isThreeWay ? "#c9a84c" : "#94a3b8",
                cursor: "pointer",
              }}>2-Way</button>
              <button onClick={() => setIsThreeWay(true)} style={{
                flex: 1, padding: "8px", borderRadius: 10, fontSize: 13, fontWeight: 600,
                border: isThreeWay ? "1px solid #c9a84c" : "1px solid #1e293b",
                background: isThreeWay ? "rgba(201,168,76,0.1)" : "#1a1f33",
                color: isThreeWay ? "#c9a84c" : "#94a3b8",
                cursor: "pointer",
              }}>3-Way</button>
            </div>

            <InputGroup label="Odds A (American)" value={oddsA} onChange={setOddsA} placeholder="e.g. +150" />
            <InputGroup label="Odds B (American)" value={oddsB} onChange={setOddsB} placeholder="e.g. +200" />
            {isThreeWay && <InputGroup label="Odds C (American)" value={oddsC} onChange={setOddsC} placeholder="e.g. +250" />}
            <InputGroup label="Bankroll ($)" value={bankroll} onChange={setBankroll} placeholder="100" />

            <button onClick={calculate} style={{
              width: "100%", padding: "14px", borderRadius: 12, border: "none",
              background: "#c9a84c", color: "#060b1a", fontWeight: 800, fontSize: 15,
              cursor: "pointer", marginTop: 8,
            }}>Calculate</button>
          </div>

          {calcResult && (
            <div style={{
              background: "#0a0f24", borderRadius: 16, border: "1px solid rgba(201,168,76,0.25)",
              padding: "20px 24px", maxWidth: 500, marginTop: 20,
            }}>
              {calcResult.error ? (
                <p style={{ color: "#ef4444", fontSize: 14, margin: 0 }}>{calcResult.error}</p>
              ) : (
                <>
                  <ResultRow label="Implied Total" value={`${calcResult.impliedTotal}%`} />
                  <ResultRow
                    label="Arb %"
                    value={calcResult.arbPct ? `${calcResult.arbPct}%` : "None"}
                    highlight
                  />
                  {calcResult.stakes && (
                    <>
                      <ResultRow label="Stake A" value={`$${calcResult.stakes.A}`} />
                      <ResultRow label="Stake B" value={`$${calcResult.stakes.B}`} />
                      {calcResult.stakes.C && <ResultRow label="Stake C" value={`$${calcResult.stakes.C}`} />}
                    </>
                  )}
                  <div style={{ borderTop: "1px solid #1e293b", marginTop: 10, paddingTop: 10 }}>
                    <ResultRow label="Guaranteed Payout" value={`$${calcResult.payout}`} gold bold />
                    <ResultRow label="Profit" value={`$${calcResult.profit}`} gold bold />
                  </div>
                  {calcResult.message && (
                    <p style={{ color: "#fbbf24", fontSize: 12, marginTop: 8 }}>{calcResult.message}</p>
                  )}
                </>
              )}
            </div>
          )}

          <div style={{
            display: "flex", alignItems: "flex-start", gap: 10,
            background: "rgba(100,116,139,0.08)", borderRadius: 10,
            padding: "14px 16px", maxWidth: 500, marginTop: 20,
          }}>
            <Info size={16} color="#64748b" style={{ flexShrink: 0, marginTop: 1 }} />
            <p style={{ fontSize: 11, color: "#64748b", margin: 0, lineHeight: 1.6 }}>
              This is a mathematical comparison, not guaranteed profit. Odds change rapidly.
              Always verify across live sportsbook screens before placing real-money wagers.
            </p>
          </div>
        </>
      )}
    </div>
  );
}

function InputGroup({ label, value, onChange, placeholder }: {
  label: string; value: string; onChange: (v: string) => void; placeholder: string;
}) {
  return (
    <div style={{ marginBottom: 12 }}>
      <label style={{ display: "block", fontSize: 11, color: "#64748b", marginBottom: 4 }}>{label}</label>
      <input type="text" value={value} onChange={(e) => onChange(e.target.value)} placeholder={placeholder}
        style={{
          width: "100%", padding: "10px 14px", borderRadius: 10,
          background: "#1a1f33", border: "1px solid #1e293b",
          color: "#f0f6fc", fontSize: 15, fontWeight: 600,
          outline: "none", boxSizing: "border-box",
        }}
      />
    </div>
  );
}

function ResultRow({ label, value, highlight, gold, bold }: {
  label: string; value: string; highlight?: boolean; gold?: boolean; bold?: boolean;
}) {
  return (
    <div style={{ display: "flex", justifyContent: "space-between", padding: "5px 0" }}>
      <span style={{ fontSize: 13, color: "#94a3b8", fontWeight: bold ? 700 : 400 }}>{label}</span>
      <span style={{
        fontSize: 14, fontWeight: bold ? 800 : 600,
        color: gold ? "#c9a84c" : highlight ? "#c9a84c" : "#f0f6fc",
      }}>{value}</span>
    </div>
  );
}