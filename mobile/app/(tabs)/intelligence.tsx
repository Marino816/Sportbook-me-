import { useState, useEffect, useCallback } from "react";
import { View, Text, StyleSheet, ScrollView, TouchableOpacity, ActivityIndicator, RefreshControl } from "react-native";
import { useFocusEffect } from "expo-router";
import { getToken } from "../../lib/api";

const API_URL = "https://sportbook-me-production.up.railway.app/api";

const SIGNAL_COLORS: Record<string, string> = {
  VERY_BULLISH: "#22c55e",
  BULLISH: "#4ade80",
  NEUTRAL: "#888",
  BEARISH: "#f87171",
  VERY_BEARISH: "#ef4444",
  UNAVAILABLE: "#666",
};

const ENV_COLORS: Record<string, string> = {
  HIGH: "#f97316",
  ABOVE_AVERAGE: "#fbbf24",
  NEUTRAL: "#888",
  BELOW_AVERAGE: "#60a5fa",
  LOW: "#3b82f6",
};

export default function IntelligenceScreen() {
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [slateId, setSlateId] = useState(1);

  const load = async () => {
    setLoading(true);
    try {
      const token = await getToken();
      const res = await fetch(`${API_URL}/intelligence/slate/${slateId}`, {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const json = await res.json();
      setData(json.data || json);
    } catch (e: any) {
      setData({ error: e.message });
    } finally {
      setLoading(false);
    }
  };

  useFocusEffect(useCallback(() => { load(); }, [slateId]));

  if (loading) return <View style={s.center}><ActivityIndicator size="large" color="#4ade80" /></View>;

  if (data?.error) {
    return (
      <View style={s.center}>
        <Text style={s.errorText}>{data.error}</Text>
        <TouchableOpacity onPress={load} style={s.retryBtn}>
          <Text style={s.retryText}>Retry</Text>
        </TouchableOpacity>
      </View>
    );
  }

  const players = data?.players || [];
  const games = data?.games || [];
  const prov = data?.provider || {};
  const perf = data?.performance || {};

  return (
    <ScrollView style={s.container} refreshControl={<RefreshControl refreshing={loading} onRefresh={load} />}>
      {/* Provider Status */}
      <View style={s.statusBar}>
        <Text style={s.statusText}>
          DFS: {prov.dfs} ({prov.dfs_data_mode}) | Market: {prov.market} ({prov.market_context_status})
        </Text>
        <Text style={s.statusSub}>Games: {data?.game_count} | Players: {data?.player_intelligence_count} | {perf.build_ms}ms</Text>
      </View>

      {/* Games */}
      <Text style={s.section}>Game Environments</Text>
      {games.map((g: any, i: number) => (
        <View key={i} style={s.gameCard}>
          <Text style={s.gameTitle}>{g.home_team_name} vs {g.away_team_name}</Text>
          <View style={s.gameRow}>
            <Text style={s.gameStat}>Total: {g.total_line ?? "N/A"}</Text>
            <Text style={[s.envBadge, { color: ENV_COLORS[g.game_environment] || "#888" }]}>
              {g.game_environment || "NEUTRAL"}
            </Text>
          </View>
          {g.spread_line != null && <Text style={s.gameStat}>Spread: {g.spread_line}</Text>}
          {g.total_movement != null && (
            <Text style={s.movement}>Movement: {g.total_movement > 0 ? "+" : ""}{g.total_movement}</Text>
          )}
        </View>
      ))}

      {/* Players */}
      <Text style={s.section}>Player Intelligence ({players.length})</Text>
      {players.map((p: any, i: number) => (
        <View key={i} style={s.playerCard}>
          <View style={s.playerRow}>
            <Text style={s.playerName}>{p.player_name || `#${p.player_id}`}</Text>
            <Text style={[s.signalBadge, { color: SIGNAL_COLORS[p.player_signal] || "#888" }]}>
              {p.player_signal || "NEUTRAL"}
            </Text>
          </View>
          <Text style={s.playerMeta}>
            {p.position || "?"} · ${p.dfs_salary?.toLocaleString()} · Proj {p.base_projection}
            {p.fantasy_market_line != null && ` · Market ${p.fantasy_market_line}`}
          </Text>
          {p.fantasy_market_edge != null && (
            <Text style={[s.edge, { color: p.fantasy_market_edge > 0 ? "#4ade80" : p.fantasy_market_edge < 0 ? "#f87171" : "#888" }]}>
              Edge: {p.fantasy_market_edge > 0 ? "+" : ""}{p.fantasy_market_edge}
            </Text>
          )}
          {p.missing_signals?.length > 0 && (
            <Text style={s.missing}>Missing: {p.missing_signals.join(", ")}</Text>
          )}
          {p.reasons?.length > 0 && (
            <Text style={s.reasons}>{p.reasons[0]}</Text>
          )}
        </View>
      ))}

      {players.length === 0 && <Text style={s.empty}>No intelligence data available for this slate.</Text>}
    </ScrollView>
  );
}

const s = StyleSheet.create({
  container: { flex: 1, backgroundColor: "#0a0a1a", padding: 16 },
  center: { flex: 1, backgroundColor: "#0a0a1a", justifyContent: "center", alignItems: "center" },
  statusBar: { backgroundColor: "#111133", borderRadius: 12, padding: 12, marginBottom: 16, borderWidth: 1, borderColor: "#222244" },
  statusText: { color: "#aaa", fontSize: 12 },
  statusSub: { color: "#666", fontSize: 11, marginTop: 4 },
  section: { color: "#4ade80", fontSize: 16, fontWeight: "700", marginBottom: 10, marginTop: 8 },
  gameCard: { backgroundColor: "#14142b", borderRadius: 10, padding: 14, marginBottom: 10 },
  gameTitle: { color: "#fff", fontWeight: "600", fontSize: 15 },
  gameRow: { flexDirection: "row", justifyContent: "space-between", marginTop: 6 },
  gameStat: { color: "#aaa", fontSize: 13 },
  envBadge: { fontWeight: "700", fontSize: 13 },
  movement: { color: "#60a5fa", fontSize: 12, marginTop: 4 },
  playerCard: { backgroundColor: "#14142b", borderRadius: 10, padding: 12, marginBottom: 8 },
  playerRow: { flexDirection: "row", justifyContent: "space-between", alignItems: "center" },
  playerName: { color: "#fff", fontWeight: "600", fontSize: 14, flex: 1 },
  signalBadge: { fontWeight: "700", fontSize: 13 },
  playerMeta: { color: "#aaa", fontSize: 12, marginTop: 3 },
  edge: { fontWeight: "600", fontSize: 13, marginTop: 4 },
  missing: { color: "#fbbf24", fontSize: 11, marginTop: 3 },
  reasons: { color: "#888", fontSize: 11, marginTop: 3, fontStyle: "italic" },
  empty: { color: "#666", textAlign: "center", marginTop: 40, fontSize: 14 },
  errorText: { color: "#f87171", fontSize: 16, textAlign: "center" },
  retryBtn: { marginTop: 16, backgroundColor: "#4ade8022", paddingHorizontal: 24, paddingVertical: 10, borderRadius: 8 },
  retryText: { color: "#4ade80", fontWeight: "600" },
});