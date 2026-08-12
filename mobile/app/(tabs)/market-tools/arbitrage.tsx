import { useState, useEffect, useCallback } from "react";
import {
  View, Text, StyleSheet, ScrollView, TouchableOpacity,
  ActivityIndicator, RefreshControl, TextInput,
} from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { getToken } from "../../../lib/api";

const API_URL = "https://sportbook-me-production.up.railway.app/api";

export default function ArbitrageScreen() {
  const [tab, setTab] = useState<"calculator" | "scanner">("scanner");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Scanner state
  const [opportunities, setOpportunities] = useState<any[]>([]);

  // Calculator state
  const [oddsA, setOddsA] = useState("");
  const [oddsB, setOddsB] = useState("");
  const [oddsC, setOddsC] = useState("");
  const [bankroll, setBankroll] = useState("100");
  const [isThreeWay, setIsThreeWay] = useState(false);

  // Results
  const [calcResult, setCalcResult] = useState<any>(null);

  const loadOpportunities = async () => {
    setLoading(true);
    setError(null);
    try {
      const token = await getToken();
      const res = await fetch(`${API_URL}/market-tools/arbitrage/scan`, {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const json = await res.json();
      const opps = json.data?.opportunities || json.opportunities || json.data || [];
      setOpportunities(Array.isArray(opps) ? opps : []);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (tab === "scanner") loadOpportunities();
  }, [tab]);

  const americanToDecimal = (american: number): number => {
    if (american > 0) return 1 + american / 100;
    return 1 + 100 / Math.abs(american);
  };

  const calculate = () => {
    const a = parseFloat(oddsA);
    const b = parseFloat(oddsB);
    const c = parseFloat(oddsC);
    const br = parseFloat(bankroll) || 100;

    if (isNaN(a) || isNaN(b)) {
      setCalcResult({ error: "Enter American odds for both sides" });
      return;
    }
    if (isThreeWay && isNaN(c)) {
      setCalcResult({ error: "Enter odds for all three outcomes" });
      return;
    }

    const decA = americanToDecimal(a);
    const decB = americanToDecimal(b);

    if (isThreeWay) {
      const decC = americanToDecimal(c);
      const impliedTotal = (1 / decA + 1 / decB + 1 / decC) * 100;
      const arbPct = impliedTotal < 100 ? 100 - impliedTotal : null;

      if (arbPct == null || arbPct < 0) {
        setCalcResult({
          twoWay: false,
          impliedTotal: impliedTotal.toFixed(2),
          arbPct: null,
          message: "No arbitrage opportunity — implied total exceeds 100%",
        });
        return;
      }

      const stakeA = (br * (1 / decA)) / (impliedTotal / 100);
      const stakeB = (br * (1 / decB)) / (impliedTotal / 100);
      const stakeC = (br * (1 / decC)) / (impliedTotal / 100);
      const payout = Math.min(stakeA * decA, stakeB * decB, stakeC * decC);
      const profit = payout - br;

      setCalcResult({
        twoWay: false,
        impliedTotal: impliedTotal.toFixed(2),
        arbPct: arbPct.toFixed(2),
        stakes: { A: stakeA.toFixed(2), B: stakeB.toFixed(2), C: stakeC.toFixed(2) },
        payout: payout.toFixed(2),
        profit: profit.toFixed(2),
      });
    } else {
      const impliedTotal = (1 / decA + 1 / decB) * 100;
      const arbPct = impliedTotal < 100 ? 100 - impliedTotal : null;

      if (arbPct == null || arbPct < 0) {
        setCalcResult({
          twoWay: true,
          impliedTotal: impliedTotal.toFixed(2),
          arbPct: null,
          message: "No arb — implied total ≥ 100%",
        });
        return;
      }

      const stakeA = (br * (1 / decA)) / (impliedTotal / 100);
      const stakeB = (br * (1 / decB)) / (impliedTotal / 100);
      const payout = Math.min(stakeA * decA, stakeB * decB);
      const profit = payout - br;

      setCalcResult({
        twoWay: true,
        impliedTotal: impliedTotal.toFixed(2),
        arbPct: arbPct.toFixed(2),
        stakes: { A: stakeA.toFixed(2), B: stakeB.toFixed(2) },
        payout: payout.toFixed(2),
        profit: profit.toFixed(2),
      });
    }
  };

  const formatOdds = (v: number | null | undefined) => {
    if (v == null) return "—";
    return v > 0 ? `+${v}` : `${v}`;
  };

  return (
    <ScrollView
      style={s.container}
      refreshControl={tab === "scanner" ? (
        <RefreshControl refreshing={loading} onRefresh={loadOpportunities} tintColor="#c9a84c" />
      ) : undefined}
    >
      {/* Tab toggle */}
      <View style={s.tabRow}>
        <TouchableOpacity
          style={[s.tabBtn, tab === "scanner" && s.tabBtnActive]}
          onPress={() => setTab("scanner")}
        >
          <Ionicons name="scan" size={16} color={tab === "scanner" ? "#c9a84c" : "#94a3b8"} />
          <Text style={[s.tabText, tab === "scanner" && s.tabTextActive]}>Auto Scanner</Text>
        </TouchableOpacity>
        <TouchableOpacity
          style={[s.tabBtn, tab === "calculator" && s.tabBtnActive]}
          onPress={() => setTab("calculator")}
        >
          <Ionicons name="calculator" size={16} color={tab === "calculator" ? "#c9a84c" : "#94a3b8"} />
          <Text style={[s.tabText, tab === "calculator" && s.tabTextActive]}>Manual Calculator</Text>
        </TouchableOpacity>
      </View>

      {/* Scanner Tab */}
      {tab === "scanner" && (
        <>
          {loading && !opportunities.length && (
            <ActivityIndicator size="large" color="#c9a84c" style={{ marginVertical: 40 }} />
          )}
          {error && <Text style={s.errorText}>{error}</Text>}

          {!loading && opportunities.length === 0 && (
            <Text style={s.emptyText}>
              No arbitrage opportunities found. Check back later — arbitrage is rare.
            </Text>
          )}

          {opportunities.map((opp, i) => (
            <View key={i} style={s.oppCard}>
              <View style={s.oppHeader}>
                <Text style={s.oppEvent}>{opp.event_name || opp.matchup || "Arb Opportunity"}</Text>
                <View style={s.oppPctBadge}>
                  <Text style={s.oppPctText}>
                    {opp.arb_percentage != null ? `${opp.arb_percentage}%` : "—"}
                  </Text>
                </View>
              </View>
              <View style={s.oppDetails}>
                <View style={s.oppSide}>
                  <Text style={s.oppLabel}>{opp.side_a_book || "Book A"}</Text>
                  <Text style={s.oppOdds}>{formatOdds(opp.side_a_odds)}</Text>
                </View>
                <Ionicons name="arrow-forward" size={16} color="#64748b" />
                <View style={s.oppSide}>
                  <Text style={s.oppLabel}>{opp.side_b_book || "Book B"}</Text>
                  <Text style={s.oppOdds}>{formatOdds(opp.side_b_odds)}</Text>
                </View>
                {opp.side_c_odds != null && (
                  <>
                    <Ionicons name="arrow-forward" size={16} color="#64748b" />
                    <View style={s.oppSide}>
                      <Text style={s.oppLabel}>{opp.side_c_book || "Book C"}</Text>
                      <Text style={s.oppOdds}>{formatOdds(opp.side_c_odds)}</Text>
                    </View>
                  </>
                )}
              </View>
              {opp.payout != null && (
                <Text style={s.oppPayout}>
                  Payout: ${opp.payout} on ${opp.bankroll || 100} · Profit: ${opp.profit || "—"}
                </Text>
              )}
            </View>
          ))}
        </>
      )}

      {/* Calculator Tab */}
      {tab === "calculator" && (
        <>
          <View style={s.calcCard}>
            <Text style={s.calcTitle}>Arbitrage Calculator</Text>

            <View style={s.calcRow}>
              <TouchableOpacity
                style={[s.typeBtn, !isThreeWay && s.typeBtnActive]}
                onPress={() => setIsThreeWay(false)}
              >
                <Text style={[s.typeText, !isThreeWay && s.typeTextActive]}>2-Way</Text>
              </TouchableOpacity>
              <TouchableOpacity
                style={[s.typeBtn, isThreeWay && s.typeBtnActive]}
                onPress={() => setIsThreeWay(true)}
              >
                <Text style={[s.typeText, isThreeWay && s.typeTextActive]}>3-Way</Text>
              </TouchableOpacity>
            </View>

            <Text style={s.inputLabel}>Odds A (American)</Text>
            <TextInput
              style={s.calcInput}
              placeholder="e.g. +150"
              placeholderTextColor="#64748b"
              value={oddsA}
              onChangeText={setOddsA}
              keyboardType="numeric"
            />

            <Text style={s.inputLabel}>Odds B (American)</Text>
            <TextInput
              style={s.calcInput}
              placeholder="e.g. +200"
              placeholderTextColor="#64748b"
              value={oddsB}
              onChangeText={setOddsB}
              keyboardType="numeric"
            />

            {isThreeWay && (
              <>
                <Text style={s.inputLabel}>Odds C (American)</Text>
                <TextInput
                  style={s.calcInput}
                  placeholder="e.g. +250"
                  placeholderTextColor="#64748b"
                  value={oddsC}
                  onChangeText={setOddsC}
                  keyboardType="numeric"
                />
              </>
            )}

            <Text style={s.inputLabel}>Bankroll ($)</Text>
            <TextInput
              style={s.calcInput}
              placeholder="100"
              placeholderTextColor="#64748b"
              value={bankroll}
              onChangeText={setBankroll}
              keyboardType="numeric"
            />

            <TouchableOpacity style={s.calcBtn} onPress={calculate}>
              <Ionicons name="calculator" size={18} color="#060b1a" />
              <Text style={s.calcBtnText}>Calculate</Text>
            </TouchableOpacity>
          </View>

          {/* Results */}
          {calcResult && (
            <View style={s.resultCard}>
              {calcResult.error ? (
                <Text style={s.errorText}>{calcResult.error}</Text>
              ) : (
                <>
                  <View style={s.resultRow}>
                    <Text style={s.resultLabel}>Implied Total</Text>
                    <Text style={s.resultVal}>{calcResult.impliedTotal}%</Text>
                  </View>
                  <View style={s.resultRow}>
                    <Text style={s.resultLabel}>Arb %</Text>
                    <Text style={[s.resultVal, { color: "#c9a84c" }]}>
                      {calcResult.arbPct != null ? `${calcResult.arbPct}%` : "None"}
                    </Text>
                  </View>
                  {calcResult.stakes && (
                    <>
                      <View style={s.resultRow}>
                        <Text style={s.resultLabel}>Stake A</Text>
                        <Text style={s.resultVal}>${calcResult.stakes.A}</Text>
                      </View>
                      <View style={s.resultRow}>
                        <Text style={s.resultLabel}>Stake B</Text>
                        <Text style={s.resultVal}>${calcResult.stakes.B}</Text>
                      </View>
                      {calcResult.stakes.C && (
                        <View style={s.resultRow}>
                          <Text style={s.resultLabel}>Stake C</Text>
                          <Text style={s.resultVal}>${calcResult.stakes.C}</Text>
                        </View>
                      )}
                    </>
                  )}
                  <View style={[s.resultRow, { borderTopWidth: 1, borderTopColor: "#1e293b", marginTop: 8, paddingTop: 8 }]}>
                    <Text style={[s.resultLabel, { fontWeight: "700" }]}>Guaranteed Payout</Text>
                    <Text style={[s.resultVal, { color: "#4ade80", fontWeight: "800" }]}>${calcResult.payout}</Text>
                  </View>
                  <View style={s.resultRow}>
                    <Text style={s.resultLabel}>Profit</Text>
                    <Text style={[s.resultVal, { color: "#4ade80", fontWeight: "800" }]}>
                      ${calcResult.profit}
                    </Text>
                  </View>

                  {calcResult.message && (
                    <Text style={s.resultMsg}>{calcResult.message}</Text>
                  )}
                </>
              )}
            </View>
          )}

          {/* Disclaimer */}
          <View style={s.disclaimer}>
            <Ionicons name="information-circle" size={14} color="#64748b" />
            <Text style={s.disclaimerText}>
              This is a mathematical comparison, not guaranteed profit. Odds change rapidly.
              Always verify across live sportsbook screens before placing real-money wagers.
            </Text>
          </View>
        </>
      )}
    </ScrollView>
  );
}

const s = StyleSheet.create({
  container: { flex: 1, backgroundColor: "#060b1a", padding: 16 },
  tabRow: { flexDirection: "row", marginBottom: 16, gap: 8 },
  tabBtn: {
    flex: 1, flexDirection: "row", alignItems: "center", justifyContent: "center",
    gap: 6, paddingVertical: 12, borderRadius: 12,
    backgroundColor: "#0a0f24", borderWidth: 1, borderColor: "#1e293b",
  },
  tabBtnActive: { borderColor: "#c9a84c", backgroundColor: "rgba(201,168,76,0.1)" },
  tabText: { fontSize: 13, fontWeight: "600", color: "#94a3b8" },
  tabTextActive: { color: "#c9a84c" },

  // Scanner
  oppCard: {
    backgroundColor: "#0a0f24", borderRadius: 12,
    borderWidth: 1, borderColor: "#1e293b",
    padding: 14, marginBottom: 10,
  },
  oppHeader: {
    flexDirection: "row", justifyContent: "space-between",
    alignItems: "center", marginBottom: 10,
  },
  oppEvent: { fontSize: 14, fontWeight: "700", color: "#f0f6fc", flex: 1 },
  oppPctBadge: {
    backgroundColor: "rgba(74,222,128,0.15)",
    borderRadius: 6, paddingHorizontal: 10, paddingVertical: 4,
  },
  oppPctText: { fontSize: 13, fontWeight: "800", color: "#4ade80" },
  oppDetails: {
    flexDirection: "row", alignItems: "center", gap: 8,
    flexWrap: "wrap",
  },
  oppSide: { alignItems: "center", minWidth: 60 },
  oppLabel: { fontSize: 10, color: "#64748b" },
  oppOdds: { fontSize: 14, fontWeight: "700", color: "#c9a84c", marginTop: 2 },
  oppPayout: { fontSize: 12, color: "#94a3b8", marginTop: 8 },

  // Calculator
  calcCard: {
    backgroundColor: "#0a0f24", borderRadius: 16,
    borderWidth: 1, borderColor: "#1e293b",
    padding: 18,
  },
  calcTitle: { fontSize: 16, fontWeight: "800", color: "#c9a84c", marginBottom: 14 },
  calcRow: { flexDirection: "row", gap: 8, marginBottom: 14 },
  typeBtn: {
    flex: 1, alignItems: "center", paddingVertical: 8,
    borderRadius: 10, backgroundColor: "#1a1f33", borderWidth: 1, borderColor: "#1e293b",
  },
  typeBtnActive: { borderColor: "#c9a84c", backgroundColor: "rgba(201,168,76,0.1)" },
  typeText: { fontSize: 13, fontWeight: "600", color: "#94a3b8" },
  typeTextActive: { color: "#c9a84c" },
  inputLabel: { fontSize: 11, color: "#64748b", marginBottom: 4, marginTop: 8 },
  calcInput: {
    backgroundColor: "#1a1f33", borderRadius: 10,
    borderWidth: 1, borderColor: "#1e293b",
    paddingHorizontal: 14, paddingVertical: 10,
    fontSize: 15, fontWeight: "600", color: "#f0f6fc",
  },
  calcBtn: {
    flexDirection: "row", alignItems: "center", justifyContent: "center",
    gap: 8, marginTop: 16,
    backgroundColor: "#c9a84c", borderRadius: 12,
    paddingVertical: 14,
  },
  calcBtnText: { fontSize: 15, fontWeight: "800", color: "#060b1a" },
  resultCard: {
    backgroundColor: "#0a0f24", borderRadius: 16,
    borderWidth: 1, borderColor: "rgba(201,168,76,0.3)",
    padding: 18, marginTop: 16,
  },
  resultRow: {
    flexDirection: "row", justifyContent: "space-between",
    alignItems: "center", paddingVertical: 6,
  },
  resultLabel: { fontSize: 13, color: "#94a3b8" },
  resultVal: { fontSize: 14, fontWeight: "700", color: "#f0f6fc" },
  resultMsg: { fontSize: 12, color: "#fbbf24", marginTop: 8 },

  // Shared
  disclaimer: {
    flexDirection: "row", alignItems: "flex-start", gap: 8,
    marginTop: 20, backgroundColor: "rgba(100,116,139,0.08)",
    borderRadius: 10, padding: 12,
  },
  disclaimerText: { flex: 1, fontSize: 11, color: "#64748b", lineHeight: 16 },
  emptyText: { color: "#666", textAlign: "center", marginTop: 40, fontSize: 14 },
  errorText: { color: "#ef4444", textAlign: "center", marginTop: 16, fontSize: 14 },
});