import { useState, useCallback } from "react";
import { View, Text, StyleSheet, ScrollView, TouchableOpacity, ActivityIndicator, RefreshControl } from "react-native";
import { useFocusEffect } from "expo-router";
import { getIntelligence, getPublishedSlates } from "../../lib/api";

const SPORTS = ["MLB", "NBA", "NFL"];

const SIGNAL_COLORS: Record<string, string> = {
  VERY_BULLISH: "#c9a84c",
  BULLISH: "#c9a84c",
  NEUTRAL: "#888",
  BEARISH: "#ef4444",
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
  const [sport, setSport] = useState("MLB");
  const [slates, setSlates] = useState<any[]>([]);
  const [slateId, setSlateId] = useState<number | null>(null);

  const loadIntel = async (id: number | null) => {
    if (!id) {
      setData({ noSlates: true });
      setLoading(false);
      return;
    }
    setLoading(true);
    try {
      const payload = await getIntelligence(id);
      setData(payload);
    } catch (e: any) {
      setData({ error: e.message });
    } finally {
      setLoading(false);
    }
  };

  const load = async (nextSport = sport) => {
    setLoading(true);
    try {
      const items = await getPublishedSlates({ sport: nextSport });
      setSlates(items);
      const next = items.find((s) => s.is_current) || items[0];
      const nextId = next?.id ?? null;
      setSlateId(nextId);
      await loadIntel(nextId);
    } catch (e: any) {
      setSlates([]);
      setSlateId(null);
      setData({ error: e.message });
      setLoading(false);
    }
  };

  useFocusEffect(useCallback(() => { load(sport); }, [sport]));

  const sportBar = (
    <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={s.sportRow}>
      {SPORTS.map((lg) => (
        <TouchableOpacity key={lg} style={[s.sportChip, sport === lg && s.sportChipOn]} onPress={() => setSport(lg)}>
          <Text style={sport === lg ? s.sportTextOn : s.sportText}>{lg}</Text>
        </TouchableOpacity>
      ))}
    </ScrollView>
  );

  if (loading && !data) return <View style={s.center}><ActivityIndicator size="large" color="#c9a84c" /></View>;

  if (data?.error && !/slate not found/i.test(String(data.error))) {
    return (
      <View style={s.center}>
        {sportBar}
        <Text style={s.errorText}>{data.error}</Text>
        <TouchableOpacity onPress={() => load()} style={s.retryBtn}>
          <Text style={s.retryText}>Retry</Text>
        </TouchableOpacity>
      </View>
    );
  }

  if (data?.noSlates) {
    return (
      <View style={s.center}>
        {sportBar}
        <Text style={s.empty}>No published {sport} slates to score yet.</Text>
      </View>
    );
  }

  const players = data?.players || [];
  const games = data?.games || [];
  const prov = data?.provider || {};
  const perf = data?.performance || {};
  const intelUnavailable =
    data?.empty === true ||
    data?.available === false ||
    /slate not found/i.test(String(data?.error || ""));

  return (
    <ScrollView style={s.container} refreshControl={<RefreshControl refreshing={loading} onRefresh={() => load()} />}>
      {sportBar}
      {slates.length > 0 ? (
        <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={s.sportRow}>
          {slates.map((sl) => (
            <TouchableOpacity
              key={sl.id}
              style={[s.sportChip, slateId === sl.id && s.sportChipOn]}
              onPress={() => { setSlateId(sl.id); loadIntel(sl.id); }}
            >
              <Text style={slateId === sl.id ? s.sportTextOn : s.sportText}>{sl.slate_name || `Slate ${sl.id}`}</Text>
            </TouchableOpacity>
          ))}
        </ScrollView>
      ) : null}
      {/* Provider Status */}
      <View style={s.statusBar}>
        <Text style={s.statusText}>
          DFS: {prov.dfs || "unavailable"} ({prov.dfs_data_mode || "unavailable"}) | Market: {prov.market || "unavailable"} ({prov.market_context_status || "unavailable"})
        </Text>
        <Text style={s.statusSub}>Games: {data?.game_count ?? 0} | Players: {data?.player_intelligence_count ?? 0}{perf.build_ms != null ? ` | ${perf.build_ms}ms` : ""}</Text>
      </View>

      {intelUnavailable ? (
        <Text style={s.empty}>
          {data?.reason === "slate_not_found"
            ? "No intelligence summary for this slate."
            : "No intelligence summary for this slate yet."}
        </Text>
      ) : (
        <>
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
            <Text style={[s.edge, { color: p.fantasy_market_edge > 0 ? "#c9a84c" : p.fantasy_market_edge < 0 ? "#ef4444" : "#888" }]}>
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
        </>
      )}
    </ScrollView>
  );
}

const s = StyleSheet.create({
  container: { flex: 1, backgroundColor: "#060b1a", padding: 16 },
  center: { flex: 1, backgroundColor: "#060b1a", justifyContent: "center", alignItems: "center" },
  statusBar: { backgroundColor: "#0a0f24", borderRadius: 12, padding: 12, marginBottom: 16, borderWidth: 1, borderColor: "#222244" },
  statusText: { color: "#aaa", fontSize: 12 },
  statusSub: { color: "#666", fontSize: 11, marginTop: 4 },
  section: { color: "#c9a84c", fontSize: 16, fontWeight: "700", marginBottom: 10, marginTop: 8 },
  gameCard: { backgroundColor: "#0a0f24", borderRadius: 10, padding: 14, marginBottom: 10 },
  gameTitle: { color: "#fff", fontWeight: "600", fontSize: 15 },
  gameRow: { flexDirection: "row", justifyContent: "space-between", marginTop: 6 },
  gameStat: { color: "#aaa", fontSize: 13 },
  envBadge: { fontWeight: "700", fontSize: 13 },
  movement: { color: "#60a5fa", fontSize: 12, marginTop: 4 },
  playerCard: { backgroundColor: "#0a0f24", borderRadius: 10, padding: 12, marginBottom: 8 },
  playerRow: { flexDirection: "row", justifyContent: "space-between", alignItems: "center" },
  playerName: { color: "#fff", fontWeight: "600", fontSize: 14, flex: 1 },
  signalBadge: { fontWeight: "700", fontSize: 13 },
  playerMeta: { color: "#aaa", fontSize: 12, marginTop: 3 },
  edge: { fontWeight: "600", fontSize: 13, marginTop: 4 },
  missing: { color: "#fbbf24", fontSize: 11, marginTop: 3 },
  reasons: { color: "#888", fontSize: 11, marginTop: 3, fontStyle: "italic" },
  empty: { color: "#64748b", textAlign: "center", marginTop: 40, fontSize: 14, paddingHorizontal: 24 },
  sportRow: { gap: 8, paddingBottom: 12 },
  sportChip: { paddingHorizontal: 12, paddingVertical: 8, borderRadius: 20, backgroundColor: "#0a0f24", borderWidth: 1, borderColor: "#1e293b" },
  sportChipOn: { borderColor: "#c9a84c", backgroundColor: "#c9a84c22" },
  sportText: { color: "#64748b", fontWeight: "700", fontSize: 12 },
  sportTextOn: { color: "#c9a84c", fontWeight: "800", fontSize: 12 },
  errorText: { color: "#ef4444", fontSize: 16, textAlign: "center" },
  retryBtn: { marginTop: 16, backgroundColor: "#c9a84c22", paddingHorizontal: 24, paddingVertical: 10, borderRadius: 8 },
  retryText: { color: "#c9a84c", fontWeight: "600" },
});