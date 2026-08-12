import { useState, useEffect } from "react";
import {
  View, Text, StyleSheet, ScrollView, TouchableOpacity,
  ActivityIndicator, RefreshControl, TextInput,
} from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { getToken } from "../../../lib/api";

const API_URL = "https://sportbook-me-production.up.railway.app/api";

type TabKey = "moneyline" | "spread" | "total" | "props";

const TABS: { key: TabKey; label: string }[] = [
  { key: "moneyline", label: "Moneyline" },
  { key: "spread", label: "Spread" },
  { key: "total", label: "Total" },
  { key: "props", label: "Player Props" },
];

export default function CompareOddsScreen() {
  const [games, setGames] = useState<any[]>([]);
  const [selectedGameId, setSelectedGameId] = useState<string | null>(null);
  const [compareData, setCompareData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [comparing, setComparing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<TabKey>("moneyline");
  const [search, setSearch] = useState("");

  const loadGames = async () => {
    setLoading(true);
    try {
      const token = await getToken();
      const res = await fetch(`${API_URL}/market-tools/live-odds?slate_id=1`, {
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

  const loadCompare = async (gameId: string) => {
    setSelectedGameId(gameId);
    setComparing(true);
    try {
      const token = await getToken();
      const res = await fetch(`${API_URL}/market-tools/compare?event_id=${gameId}`, {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const json = await res.json();
      setCompareData(json.data || json);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setComparing(false);
    }
  };

  useEffect(() => { loadGames(); }, []);

  const filteredGames = games.filter((g) => {
    if (!search) return true;
    const q = search.toLowerCase();
    return (
      (g.home_team_name || "").toLowerCase().includes(q) ||
      (g.away_team_name || "").toLowerCase().includes(q)
    );
  });

  const getBestPrice = (prices: any[]): any => {
    if (!prices || prices.length === 0) return null;
    return prices.reduce((best, p) => {
      const val = p.price || p.odds || 0;
      const bestVal = best.price || best.odds || 0;
      return val > (bestVal > 0 ? bestVal : -9999) ? p : best;
    }, prices[0]);
  };

  const formatOdds = (n: number | null | undefined) => {
    if (n == null) return "—";
    return n > 0 ? `+${n}` : `${n}`;
  };

  return (
    <ScrollView
      style={s.container}
      refreshControl={<RefreshControl refreshing={loading} onRefresh={loadGames} tintColor="#c9a84c" />}
    >
      {/* Event selector */}
      <Text style={s.sectionLabel}>Select Event</Text>
      <TextInput
        style={s.searchInput}
        placeholder="Search teams..."
        placeholderTextColor="#64748b"
        value={search}
        onChangeText={setSearch}
      />

      <ScrollView horizontal showsHorizontalScrollIndicator={false} style={{ marginBottom: 16 }}>
        <View style={{ flexDirection: "row", gap: 8 }}>
          {filteredGames.map((g, i) => {
            const isSelected = g.game_id === selectedGameId;
            return (
              <TouchableOpacity
                key={g.game_id || i}
                style={[s.eventChip, isSelected && s.eventChipActive]}
                onPress={() => loadCompare(g.game_id || g.id)}
              >
                <Text style={[s.eventChipText, isSelected && s.eventChipTextActive]}>
                  {(g.away_team_name || "AWY")?.substring(0, 3)} @ {(g.home_team_name || "HOM")?.substring(0, 3)}
                </Text>
              </TouchableOpacity>
            );
          })}
        </View>
      </ScrollView>

      {comparing && (
        <ActivityIndicator size="large" color="#c9a84c" style={{ marginVertical: 40 }} />
      )}

      {compareData && !comparing && (
        <>
          {/* Market type tabs */}
          <View style={s.tabRow}>
            {TABS.map((t) => (
              <TouchableOpacity
                key={t.key}
                style={[s.tabBtn, activeTab === t.key && s.tabBtnActive]}
                onPress={() => setActiveTab(t.key)}
              >
                <Text style={[s.tabText, activeTab === t.key && s.tabTextActive]}>
                  {t.label}
                </Text>
              </TouchableOpacity>
            ))}
          </View>

          {/* Compare table */}
          {activeTab !== "props" && (
            <View style={s.table}>
              {/* Header */}
              <View style={s.tableHeader}>
                <Text style={[s.th, { flex: 1.5 }]}>Bookmaker</Text>
                <Text style={s.th}>{compareData?.home_team || "Home"}</Text>
                <Text style={s.th}>{compareData?.away_team || "Away"}</Text>
                <Text style={s.th}>Best?</Text>
              </View>

              {/* Compare data */}
              {(compareData?.bookmakers || compareData?.books || []).map((book: any, i: number) => {
                const h = activeTab === "spread"
                  ? book?.spread_home
                  : activeTab === "total"
                    ? book?.total
                    : book?.moneyline_home;
                const a = activeTab === "spread"
                  ? book?.spread_away
                  : activeTab === "total"
                    ? book?.total
                    : book?.moneyline_away;

                const homeBest = getBestPrice(
                  (compareData?.bookmakers || compareData?.books || [])
                    .map((b: any) => ({
                      price: activeTab === "spread" ? b?.spread_home
                            : activeTab === "total" ? b?.total
                            : b?.moneyline_home,
                    }))
                );
                const awayBest = getBestPrice(
                  (compareData?.bookmakers || compareData?.books || [])
                    .map((b: any) => ({
                      price: activeTab === "spread" ? b?.spread_away
                            : activeTab === "total" ? b?.total
                            : b?.moneyline_away,
                    }))
                );

                const hStr = formatOdds(h);
                const awayStr = formatOdds(a);

                return (
                  <View key={i} style={s.tableRow}>
                    <Text style={[s.td, { flex: 1.5, color: "#94a3b8" }]}>
                      {book.bookmaker_name || book.sportsbook || book.name || `Book ${i + 1}`}
                    </Text>
                    <Text style={[
                      s.td,
                      homeBest?.price === h && h != null && { color: "#c9a84c", fontWeight: "800" },
                    ]}>
                      {hStr}
                    </Text>
                    <Text style={[
                      s.td,
                      awayBest?.price === a && a != null && { color: "#c9a84c", fontWeight: "800" },
                    ]}>
                      {awayStr}
                    </Text>
                    <Text style={s.td}>
                      {homeBest?.price === h || awayBest?.price === a ? (
                        <Ionicons name="trophy" size={14} color="#c9a84c" />
                      ) : "—"}
                    </Text>
                  </View>
                );
              })}
            </View>
          )}

          {/* Props tab */}
          {activeTab === "props" && (
            <View style={s.table}>
              <Text style={s.tableHeaderLabel}>
                Player Props — Select a player on the Player Props screen for full comparison
              </Text>
              {(compareData?.player_props || []).slice(0, 5).map((prop: any, i: number) => (
                <View key={i} style={s.tableRow}>
                  <Text style={[s.td, { flex: 1.5 }]}>{prop.player_name || `Prop ${i + 1}`}</Text>
                  <Text style={s.td}>{prop.market || "—"}</Text>
                  <Text style={[s.td, { color: "#c9a84c" }]}>{prop.line || "—"}</Text>
                </View>
              ))}
            </View>
          )}
        </>
      )}

      {!compareData && !comparing && !loading && (
        <Text style={s.emptyText}>Select an event to compare odds across bookmakers.</Text>
      )}

      {error && (
        <Text style={s.errorText}>{error}</Text>
      )}
    </ScrollView>
  );
}

const s = StyleSheet.create({
  container: { flex: 1, backgroundColor: "#060b1a", padding: 16 },
  center: {
    flex: 1, backgroundColor: "#060b1a",
    justifyContent: "center", alignItems: "center",
  },
  sectionLabel: {
    fontSize: 13, fontWeight: "700", color: "#c9a84c",
    textTransform: "uppercase", letterSpacing: 1, marginBottom: 8,
  },
  searchInput: {
    backgroundColor: "#0a0f24", borderRadius: 10,
    borderWidth: 1, borderColor: "#1e293b",
    paddingHorizontal: 12, paddingVertical: 8,
    fontSize: 13, color: "#f0f6fc", marginBottom: 10,
  },
  eventChip: {
    paddingVertical: 8, paddingHorizontal: 14,
    borderRadius: 10, backgroundColor: "#0a0f24",
    borderWidth: 1, borderColor: "#1e293b",
  },
  eventChipActive: {
    borderColor: "#c9a84c",
    backgroundColor: "rgba(201,168,76,0.1)",
  },
  eventChipText: { fontSize: 12, fontWeight: "600", color: "#94a3b8" },
  eventChipTextActive: { color: "#c9a84c" },
  tabRow: { flexDirection: "row", gap: 6, marginBottom: 16 },
  tabBtn: {
    paddingVertical: 8, paddingHorizontal: 14,
    borderRadius: 10, backgroundColor: "#0a0f24",
    borderWidth: 1, borderColor: "#1e293b",
  },
  tabBtnActive: {
    borderColor: "#c9a84c",
    backgroundColor: "rgba(201,168,76,0.12)",
  },
  tabText: { fontSize: 12, fontWeight: "600", color: "#94a3b8" },
  tabTextActive: { color: "#c9a84c" },
  table: {
    backgroundColor: "#0a0f24", borderRadius: 12,
    borderWidth: 1, borderColor: "#1e293b",
    overflow: "hidden",
  },
  tableHeader: {
    flexDirection: "row", paddingVertical: 10, paddingHorizontal: 12,
    backgroundColor: "rgba(201,168,76,0.08)",
    borderBottomWidth: 1, borderBottomColor: "#1e293b",
  },
  tableHeaderLabel: {
    fontSize: 12, color: "#94a3b8", padding: 16, textAlign: "center",
  },
  th: { flex: 1, fontSize: 11, fontWeight: "700", color: "#c9a84c", textAlign: "center" },
  tableRow: {
    flexDirection: "row", paddingVertical: 12, paddingHorizontal: 12,
    borderBottomWidth: 1, borderBottomColor: "#1e293b20",
  },
  td: { flex: 1, fontSize: 13, color: "#f0f6fc", textAlign: "center", fontWeight: "500" },
  emptyText: { color: "#666", textAlign: "center", marginTop: 40, fontSize: 14 },
  errorText: { color: "#ef4444", textAlign: "center", marginTop: 16, fontSize: 14 },
});