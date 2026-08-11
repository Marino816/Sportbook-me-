import { useState, useEffect, useCallback } from "react";
import { View, Text, StyleSheet, ScrollView, TouchableOpacity, ActivityIndicator, Alert, RefreshControl } from "react-native";
import { useFocusEffect } from "expo-router";
import { getToken } from "../../lib/api";

const API_URL = "https://sportbook-me-production.up.railway.app/api";

export default function LineupsScreen() {
  const [history, setHistory] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState<any>(null);

  const fetchHistory = async () => {
    setLoading(true);
    try {
      const token = await getToken();
      const res = await fetch(`${API_URL}/lineups/history`, {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
      const data = await res.json();
      setHistory(data.data || []);
    } catch (e) {
      // silent — shown as empty state
    } finally {
      setLoading(false);
    }
  };

  useFocusEffect(useCallback(() => { fetchHistory(); }, []));

  const handleDelete = async (id: number) => {
    Alert.alert("Delete", "Remove this lineup history?", [
      { text: "Cancel", style: "cancel" },
      {
        text: "Delete",
        style: "destructive",
        onPress: async () => {
          try {
            const token = await getToken();
            await fetch(`${API_URL}/lineups/history/${id}`, {
              method: "DELETE",
              headers: token ? { Authorization: `Bearer ${token}` } : {},
            });
            setHistory((prev) => prev.filter((h) => h.id !== id));
            if (selected?.id === id) setSelected(null);
          } catch (e) {
            Alert.alert("Error", "Could not delete.");
          }
        },
      },
    ]);
  };

  if (selected) {
    const lus = selected.lineups || [];
    return (
      <ScrollView style={styles.container}>
        <TouchableOpacity onPress={() => setSelected(null)} style={styles.backBtn}>
          <Text style={styles.backText}>← Back</Text>
        </TouchableOpacity>
        <Text style={styles.title}>
          {selected.sport} · {selected.platform}
        </Text>
        <Text style={styles.meta}>
          {selected.strategy} · {selected.created_at?.slice(0, 10)} · {selected.data_mode}
        </Text>
        {lus.map((lu: any, i: number) => (
          <View key={i} style={styles.card}>
            <Text style={styles.cardTitle}>Lineup #{i + 1}</Text>
            <Text style={styles.cardSal}>${lu.total_salary?.toLocaleString() || 0} · {lu.projected_score?.toFixed(1)} pts</Text>
            {(lu.players || []).map((p: any, j: number) => (
              <View key={j} style={styles.pRow}>
                <Text style={styles.pSlot}>{p.roster_slot || "?"}</Text>
                <Text style={styles.pName}>{p.name || `Player ${p.player_id}`}</Text>
                <Text style={styles.pSal}>${p.salary?.toLocaleString() || 0}</Text>
              </View>
            ))}
          </View>
        ))}
      </ScrollView>
    );
  }

  return (
    <ScrollView
      style={styles.container}
      refreshControl={<RefreshControl refreshing={loading} onRefresh={fetchHistory} />}
    >
      <Text style={styles.header}>Lineup History</Text>
      {loading && <ActivityIndicator style={{ marginTop: 20 }} />}
      {!loading && history.length === 0 && (
        <Text style={styles.empty}>No lineups generated yet.{'\n'}Build one in the Optimizer tab.</Text>
      )}
      {history.map((h: any) => (
        <TouchableOpacity key={h.id} style={styles.histCard} onPress={() => setSelected(h)}>
          <View style={styles.histRow}>
            <Text style={styles.histSport}>{h.sport} · {h.platform}</Text>
            <TouchableOpacity onPress={() => handleDelete(h.id)}>
              <Text style={styles.delBtn}>🗑</Text>
            </TouchableOpacity>
          </View>
          <Text style={styles.histMeta}>
            {h.strategy} · {h.lineup_count} lineups · ${h.total_salary?.toLocaleString()} · {h.projected_score?.toFixed(1)} pts
          </Text>
          <Text style={styles.histDate}>{h.created_at?.slice(0, 16) || ""}</Text>
        </TouchableOpacity>
      ))}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: "#060b1a", padding: 16 },
  header: { fontSize: 22, fontWeight: "700", color: "#fff", marginBottom: 12 },
  empty: { color: "#888", textAlign: "center", marginTop: 40, fontSize: 15 },
  histCard: { backgroundColor: "#0a0f24", borderRadius: 10, padding: 14, marginBottom: 10 },
  histRow: { flexDirection: "row", justifyContent: "space-between" },
  histSport: { color: "#fff", fontWeight: "600", fontSize: 15 },
  delBtn: { fontSize: 16 },
  histMeta: { color: "#aaa", fontSize: 13, marginTop: 4 },
  histDate: { color: "#666", fontSize: 11, marginTop: 4 },
  title: { fontSize: 20, fontWeight: "700", color: "#fff" },
  meta: { color: "#888", fontSize: 13, marginBottom: 16 },
  backBtn: { marginBottom: 12 },
  backText: { color: "#7c5cfc", fontSize: 15 },
  card: { backgroundColor: "#0a0f24", borderRadius: 10, padding: 14, marginBottom: 12 },
  cardTitle: { color: "#fff", fontWeight: "600", fontSize: 15 },
  cardSal: { color: "#aaa", fontSize: 13, marginBottom: 8 },
  pRow: { flexDirection: "row", paddingVertical: 3, borderBottomWidth: 0.5, borderBottomColor: "#222" },
  pSlot: { color: "#7c5cfc", width: 40, fontSize: 12, fontWeight: "600" },
  pName: { color: "#ddd", flex: 1, fontSize: 13 },
  pSal: { color: "#aaa", fontSize: 12 },
});