import { useState } from "react";
import { View, Text, StyleSheet, TouchableOpacity, TextInput, ScrollView, ActivityIndicator, Alert } from "react-native";
import { buildLineups } from "../../lib/api";

export default function OptimizerScreen() {
  const [platform, setPlatform] = useState<"draftkings" | "fanduel">("draftkings");
  const [strategy, setStrategy] = useState("balanced");
  const [count, setCount] = useState("3");
  const [lineups, setLineups] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);

  async function handleBuild() {
    setLoading(true);
    try {
      const res = await buildLineups({ platform, strategy, count: parseInt(count) || 1 });
      setLineups(res.data?.lineups || []);
    } catch (e: any) {
      Alert.alert("Build Failed", e.message);
    } finally { setLoading(false); }
  }

  return (
    <ScrollView style={s.scroll} contentContainerStyle={s.container}>
      <View style={s.row}>
        <TouchableOpacity style={[s.chip, platform === "draftkings" && s.chipActive]} onPress={() => setPlatform("draftkings")}><Text style={platform === "draftkings" ? s.chipTextActive : s.chipText}>DraftKings</Text></TouchableOpacity>
        <TouchableOpacity style={[s.chip, platform === "fanduel" && s.chipActive]} onPress={() => setPlatform("fanduel")}><Text style={platform === "fanduel" ? s.chipTextActive : s.chipText}>FanDuel</Text></TouchableOpacity>
      </View>

      <View style={s.card}>
        <Text style={s.label}>Strategy</Text>
        <TextInput style={s.input} value={strategy} onChangeText={setStrategy} placeholderTextColor="#666" />
      </View>
      <View style={s.card}>
        <Text style={s.label}>Lineups ({count})</Text>
        <TextInput style={s.input} value={count} onChangeText={setCount} keyboardType="numeric" placeholderTextColor="#666" />
      </View>

      <TouchableOpacity style={s.btn} onPress={handleBuild} disabled={loading}>
        <Text style={s.btnText}>{loading ? "Building..." : "Build Lineups"}</Text>
      </TouchableOpacity>

      {loading && <ActivityIndicator size="large" color="#4ade80" style={{ marginTop: 16 }} />}

      {lineups.map((l, i) => (
        <View key={i} style={s.card}>
          <Text style={s.cardTitle}>Lineup #{i + 1}</Text>
          <Text style={s.cardSub}>
            {l.platform || platform.toUpperCase()} · {l.players?.length || 0} players · ${l.salary_used || "?"}
          </Text>
        </View>
      ))}
    </ScrollView>
  );
}

const s = StyleSheet.create({
  scroll: { flex: 1, backgroundColor: "#0a0a0a" },
  container: { padding: 20, gap: 16 },
  row: { flexDirection: "row", gap: 12 },
  chip: { flex: 1, padding: 12, borderRadius: 12, backgroundColor: "#1a1a1a", borderWidth: 1, borderColor: "#333", alignItems: "center" },
  chipActive: { borderColor: "#4ade80", backgroundColor: "#4ade8020" },
  chipText: { color: "#888", fontWeight: "600" }, chipTextActive: { color: "#4ade80", fontWeight: "700" },
  card: { backgroundColor: "#1a1a1a", borderRadius: 16, padding: 16, borderWidth: 1, borderColor: "#333" },
  cardTitle: { fontSize: 16, fontWeight: "700", color: "#4ade80" },
  cardSub: { fontSize: 13, color: "#888", marginTop: 4 },
  label: { fontSize: 12, color: "#666", textTransform: "uppercase", marginBottom: 6 },
  input: { backgroundColor: "#111", color: "#fff", borderRadius: 10, padding: 12, fontSize: 16, borderWidth: 1, borderColor: "#333" },
  btn: { backgroundColor: "#4ade80", borderRadius: 12, padding: 16, alignItems: "center" },
  btnText: { color: "#000", fontWeight: "700", fontSize: 16 },
});