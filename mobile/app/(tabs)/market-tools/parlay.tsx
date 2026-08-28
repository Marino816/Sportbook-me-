import { useState, useEffect } from "react";
import {
  View, Text, StyleSheet, ScrollView, TouchableOpacity,
  ActivityIndicator, TextInput,
} from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { getToken, getApiUrl } from "../../../lib/api";

const API_URL = getApiUrl();

interface Leg {
  id: string;
  eventId?: string;
  eventName?: string;
  market?: string;
  selection?: string;
  odds?: number;
  book?: string;
}

export default function ParlayBuilderScreen() {
  const [games, setGames] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [legs, setLegs] = useState<Leg[]>([]);
  const [stake, setStake] = useState("10");
  const [pickingFor, setPickingFor] = useState<number | null>(null); // game index
  const [selectedMarket, setSelectedMarket] = useState<string>("moneyline");

  const loadGames = async () => {
    setLoading(true);
    try {
      const token = await getToken();
      const res = await fetch(`${API_URL}/market-tools/live-odds?league=MLB`, {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const json = await res.json();
      const gs = json.data?.games || json.games || [];
      setGames(gs);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { loadGames(); }, []);

  const addLeg = (game: any, selection: string, odds: number) => {
    const isSGP = legs.length > 0 && game.game_id === legs[0].eventId;
    const newLeg: Leg = {
      id: `${Date.now()}-${Math.random()}`,
      eventId: game.game_id || game.id,
      eventName: `${game.away_team_name || "AWY"} @ ${game.home_team_name || "HOM"}`,
      market: selectedMarket,
      selection,
      odds,
      book: "Select Book",
    };
    setLegs([...legs, newLeg]);
    setPickingFor(null);
  };

  const removeLeg = (id: string) => {
    setLegs(legs.filter((l) => l.id !== id));
  };

  const americanToDecimal = (am: number): number => {
    if (am > 0) return 1 + am / 100;
    return 1 + 100 / Math.abs(am);
  };

  const calculateParlay = () => {
    if (legs.length === 0) return { odds: 0, payout: 0, profit: 0 };
    let totalDecimal = 1;
    for (const leg of legs) {
      totalDecimal *= americanToDecimal(leg.odds || 0);
    }
    const st = parseFloat(stake) || 0;
    const payout = totalDecimal * st;
    const profit = payout - st;
    // Convert back to American
    let amOdds: number;
    if (totalDecimal >= 2) amOdds = Math.round((totalDecimal - 1) * 100);
    else amOdds = Math.round(-100 / (totalDecimal - 1));
    return { odds: amOdds, payout, profit };
  };

  const result = calculateParlay();
  const isSGP = legs.length >= 2 && legs.every((l) => l.eventId === legs[0]?.eventId);

  const formatOdds = (v: number | null | undefined) => {
    if (v == null) return "—";
    return v > 0 ? `+${v}` : `${v}`;
  };

  return (
    <ScrollView style={s.container}>
      {loading && (
        <ActivityIndicator size="large" color="#c9a84c" style={{ marginVertical: 40 }} />
      )}

      {/* Legs summary */}
      <View style={s.legsSection}>
        <View style={s.legsHeader}>
          <Ionicons name="layers" size={18} color="#c9a84c" />
          <Text style={s.legsTitle}>Parlay ({legs.length} legs)</Text>
          {isSGP && <Text style={s.sgpBadge}>SAME GAME PARLAY</Text>}
        </View>

        {legs.map((leg, i) => (
          <View key={leg.id} style={s.legRow}>
            <View style={{ flex: 1 }}>
              <Text style={s.legEvent} numberOfLines={1}>{leg.eventName}</Text>
              <Text style={s.legDetail}>
                {leg.market} — {leg.selection} @ {formatOdds(leg.odds)}
              </Text>
            </View>
            <TouchableOpacity onPress={() => removeLeg(leg.id)}>
              <Ionicons name="close-circle" size={22} color="#ef4444" />
            </TouchableOpacity>
          </View>
        ))}

        {legs.length === 0 && (
          <Text style={s.emptyLegs}>Add legs from the games below.</Text>
        )}

        {/* Running odds */}
        {legs.length >= 2 && (
          <View style={s.runningOdds}>
            <View style={s.roRow}>
              <Text style={s.roLabel}>Parlay Odds</Text>
              <Text style={s.roVal}>{formatOdds(result.odds)}</Text>
            </View>
            <Text style={s.inputLabel}>Stake ($)</Text>
            <TextInput
              style={s.calcInput}
              placeholder="10"
              placeholderTextColor="#64748b"
              value={stake}
              onChangeText={setStake}
              keyboardType="numeric"
            />
            <View style={s.roRow}>
              <Text style={s.roLabel}>Payout</Text>
              <Text style={[s.roVal, { color: "#4ade80" }]}>
                ${result.payout.toFixed(2)}
              </Text>
            </View>
            <View style={s.roRow}>
              <Text style={s.roLabel}>Profit</Text>
              <Text style={[s.roVal, { color: "#4ade80" }]}>
                ${result.profit.toFixed(2)}
              </Text>
            </View>
          </View>
        )}
      </View>

      {/* Add legs from games */}
      <Text style={s.sectionLabel}>Add Legs</Text>

      {games.map((game, gi) => {
        const isOpen = pickingFor === gi;
        return (
          <View key={game.game_id || gi} style={s.gameCard}>
            <TouchableOpacity
              style={s.gameRow}
              onPress={() => setPickingFor(isOpen ? null : gi)}
            >
              <View style={{ flex: 1 }}>
                <Text style={s.gameName}>
                  {game.away_team_name || "Away"} @ {game.home_team_name || "Home"}
                </Text>
              </View>
              <Ionicons
                name={isOpen ? "chevron-up" : "chevron-down"}
                size={18} color="#94a3b8"
              />
            </TouchableOpacity>

            {isOpen && (
              <View style={s.pickerSheet}>
                {/* Market selector */}
                <ScrollView horizontal style={{ marginBottom: 10 }}>
                  <View style={{ flexDirection: "row", gap: 6 }}>
                    {["moneyline", "spread", "total"].map((m) => (
                      <TouchableOpacity
                        key={m}
                        style={[s.marketChip, selectedMarket === m && s.marketChipActive]}
                        onPress={() => setSelectedMarket(m)}
                      >
                        <Text style={[s.marketChipText, selectedMarket === m && s.marketChipTextActive]}>
                          {m === "moneyline" ? "Moneyline" : m === "spread" ? "Spread" : "Total"}
                        </Text>
                      </TouchableOpacity>
                    ))}
                  </View>
                </ScrollView>

                {/* Selections */}
                <View style={s.selectionsRow}>
                  {selectedMarket === "moneyline" ? (
                    <>
                      <TouchableOpacity
                        style={s.selectionBtn}
                        onPress={() => addLeg(game, game.away_team_name || "Away", game.moneyline_away || -110)}
                      >
                        <Text style={s.selectionName}>{game.away_team_name || "Away"}</Text>
                        <Text style={s.selectionOdds}>{formatOdds(game.moneyline_away)}</Text>
                      </TouchableOpacity>
                      <TouchableOpacity
                        style={s.selectionBtn}
                        onPress={() => addLeg(game, game.home_team_name || "Home", game.moneyline_home || -110)}
                      >
                        <Text style={s.selectionName}>{game.home_team_name || "Home"}</Text>
                        <Text style={s.selectionOdds}>{formatOdds(game.moneyline_home)}</Text>
                      </TouchableOpacity>
                    </>
                  ) : selectedMarket === "spread" ? (
                    <>
                      <TouchableOpacity
                        style={s.selectionBtn}
                        onPress={() => addLeg(
                          game,
                          `${game.away_team_name || "Away"} ${game.spread_line != null ? (game.spread_line > 0 ? "+" : "") + game.spread_line : "PK"}`,
                          -110,
                        )}
                      >
                        <Text style={s.selectionName}>{game.away_team_name || "Away"}</Text>
                        <Text style={s.selectionOdds}>{game.spread_line != null ? (game.spread_line > 0 ? "+" : "") + game.spread_line : "PK"}</Text>
                      </TouchableOpacity>
                      <TouchableOpacity
                        style={s.selectionBtn}
                        onPress={() => addLeg(
                          game,
                          `${game.home_team_name || "Home"} ${game.spread_line != null ? (game.spread_line < 0 ? "" : "-") + Math.abs(game.spread_line) : "PK"}`,
                          -110,
                        )}
                      >
                        <Text style={s.selectionName}>{game.home_team_name || "Home"}</Text>
                        <Text style={s.selectionOdds}>{game.spread_line != null ? (game.spread_line < 0 ? "" : "-") + Math.abs(game.spread_line) : "PK"}</Text>
                      </TouchableOpacity>
                    </>
                  ) : (
                    <>
                      <TouchableOpacity
                        style={s.selectionBtn}
                        onPress={() => addLeg(
                          game,
                          `Over ${game.total_line || "—"}`,
                          -110,
                        )}
                      >
                        <Text style={s.selectionName}>Over</Text>
                        <Text style={s.selectionOdds}>{game.total_line || "—"}</Text>
                      </TouchableOpacity>
                      <TouchableOpacity
                        style={s.selectionBtn}
                        onPress={() => addLeg(
                          game,
                          `Under ${game.total_line || "—"}`,
                          -110,
                        )}
                      >
                        <Text style={s.selectionName}>Under</Text>
                        <Text style={s.selectionOdds}>{game.total_line || "—"}</Text>
                      </TouchableOpacity>
                    </>
                  )}
                </View>
              </View>
            )}
          </View>
        );
      })}

      {error && <Text style={s.errorText}>{error}</Text>}
      <View style={{ height: 60 }} />
    </ScrollView>
  );
}

const s = StyleSheet.create({
  container: { flex: 1, backgroundColor: "#060b1a", padding: 16 },
  sectionLabel: {
    fontSize: 13, fontWeight: "700", color: "#c9a84c",
    textTransform: "uppercase", letterSpacing: 1, marginBottom: 10, marginTop: 16,
  },

  // Legs
  legsSection: {
    backgroundColor: "#0a0f24", borderRadius: 16,
    borderWidth: 1, borderColor: "rgba(201,168,76,0.25)",
    padding: 16,
  },
  legsHeader: { flexDirection: "row", alignItems: "center", gap: 8, marginBottom: 12 },
  legsTitle: { fontSize: 16, fontWeight: "800", color: "#c9a84c", flex: 1 },
  sgpBadge: {
    fontSize: 9, fontWeight: "800", color: "#f97316",
    backgroundColor: "rgba(249,115,22,0.15)",
    paddingHorizontal: 8, paddingVertical: 3, borderRadius: 4,
    overflow: "hidden",
  },
  legRow: {
    flexDirection: "row", alignItems: "center",
    paddingVertical: 10, borderBottomWidth: 1, borderBottomColor: "#1e293b30",
  },
  legEvent: { fontSize: 13, fontWeight: "600", color: "#f0f6fc" },
  legDetail: { fontSize: 11, color: "#94a3b8", marginTop: 2 },
  emptyLegs: { color: "#64748b", fontSize: 13, textAlign: "center", paddingVertical: 12 },
  runningOdds: {
    marginTop: 12, paddingTop: 12,
    borderTopWidth: 1, borderTopColor: "#1e293b",
  },
  roRow: {
    flexDirection: "row", justifyContent: "space-between",
    alignItems: "center", paddingVertical: 4,
  },
  roLabel: { fontSize: 13, color: "#94a3b8" },
  roVal: { fontSize: 15, fontWeight: "800", color: "#c9a84c" },
  inputLabel: { fontSize: 11, color: "#64748b", marginTop: 8, marginBottom: 4 },
  calcInput: {
    backgroundColor: "#1a1f33", borderRadius: 10,
    borderWidth: 1, borderColor: "#1e293b",
    paddingHorizontal: 14, paddingVertical: 8,
    fontSize: 14, fontWeight: "600", color: "#f0f6fc",
  },

  // Game picker
  gameCard: {
    backgroundColor: "#0a0f24", borderRadius: 12,
    borderWidth: 1, borderColor: "#1e293b",
    marginBottom: 8, overflow: "hidden",
  },
  gameRow: {
    flexDirection: "row", alignItems: "center",
    padding: 14,
  },
  gameName: { fontSize: 14, fontWeight: "600", color: "#f0f6fc" },
  pickerSheet: {
    padding: 14, paddingTop: 0,
    borderTopWidth: 1, borderTopColor: "#1e293b",
  },
  marketChip: {
    paddingVertical: 6, paddingHorizontal: 14,
    borderRadius: 8, backgroundColor: "#1a1f33",
    borderWidth: 1, borderColor: "#1e293b",
  },
  marketChipActive: {
    borderColor: "#c9a84c", backgroundColor: "rgba(201,168,76,0.1)",
  },
  marketChipText: { fontSize: 11, fontWeight: "600", color: "#94a3b8" },
  marketChipTextActive: { color: "#c9a84c" },
  selectionsRow: { flexDirection: "row", gap: 10 },
  selectionBtn: {
    flex: 1, alignItems: "center", paddingVertical: 12,
    backgroundColor: "#1a1f33", borderRadius: 10,
    borderWidth: 1, borderColor: "#1e293b",
  },
  selectionName: { fontSize: 13, fontWeight: "700", color: "#f0f6fc" },
  selectionOdds: { fontSize: 12, fontWeight: "600", color: "#c9a84c", marginTop: 4 },

  errorText: { color: "#ef4444", textAlign: "center", marginTop: 16, fontSize: 14 },
});