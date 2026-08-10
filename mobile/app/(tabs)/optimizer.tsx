import { useState } from "react";
import { View, Text, StyleSheet, TouchableOpacity, TextInput, ScrollView, ActivityIndicator, Alert, Modal } from "react-native";
import { buildLineups } from "../../lib/api";

export default function OptimizerScreen() {
  const [platform, setPlatform] = useState<"draftkings" | "fanduel">("draftkings");
  const [strategy, setStrategy] = useState("balanced");
  const [count, setCount] = useState("3");
  const [lineups, setLineups] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [selected, setSelected] = useState<any>(null);

  async function handleBuild() {
    setLoading(true);
    setLineups([]);
    try {
      const res = await buildLineups({ platform, strategy, count: parseInt(count) || 1 });
      setLineups(res.data?.lineups || []);
    } catch (e: any) {
      Alert.alert("Build Failed", e.message);
    } finally { setLoading(false); }
  }

  function fmtSalary(n: number) { return n ? `$${(n / 1000).toFixed(1)}K` : "..."; }
  function fmtPoints(n: number) { return n != null ? n.toFixed(1) : "..."; }

  return (
    <View style={s.flex}>
      <ScrollView style={s.scroll} contentContainerStyle={s.container}>
        <View style={s.row}>
          <TouchableOpacity style={[s.chip, platform === "draftkings" && s.chipActive]} onPress={() => setPlatform("draftkings")}>
            <Text style={platform === "draftkings" ? s.chipTextActive : s.chipText}>DraftKings</Text>
          </TouchableOpacity>
          <TouchableOpacity style={[s.chip, platform === "fanduel" && s.chipActive]} onPress={() => setPlatform("fanduel")}>
            <Text style={platform === "fanduel" ? s.chipTextActive : s.chipText}>FanDuel</Text>
          </TouchableOpacity>
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
          <TouchableOpacity key={i} style={s.lineupCard} onPress={() => setSelected(l)} activeOpacity={0.7}>
            <View style={s.lineupHeader}>
              <Text style={s.lineupNum}>Lineup #{i + 1}</Text>
              <Text style={s.arrow}>›</Text>
            </View>
            <View style={s.lineupStats}>
              <Text style={s.stat}>Projected: <Text style={s.statBold}>{fmtPoints(l.projected_score)}</Text></Text>
              <Text style={s.stat}>Salary: <Text style={s.statBold}>{fmtSalary(l.total_salary)}</Text></Text>
              <Text style={s.stat}>Players: <Text style={s.statBold}>{l.players?.length || 0}</Text></Text>
            </View>
          </TouchableOpacity>
        ))}
      </ScrollView>

      {/* Lineup Detail Modal */}
      <Modal visible={!!selected} animationType="slide" presentationStyle="pageSheet">
        {selected && (
          <ScrollView style={s.modal} contentContainerStyle={s.modalContent}>
            <View style={s.modalHeader}>
              <Text style={s.modalTitle}>Lineup Details</Text>
              <TouchableOpacity onPress={() => setSelected(null)}>
                <Text style={s.closeBtn}>✕</Text>
              </TouchableOpacity>
            </View>

            <View style={s.detailCard}>
              <View style={s.detailRow}><Text style={s.detailLabel}>Platform</Text><Text style={s.detailVal}>{selected.platform?.toUpperCase() || platform.toUpperCase()}</Text></View>
              <View style={s.detailRow}><Text style={s.detailLabel}>Strategy</Text><Text style={s.detailVal}>{strategy}</Text></View>
              <View style={s.detailRow}><Text style={s.detailLabel}>Total Salary</Text><Text style={s.detailVal}>${(selected.total_salary || 0).toLocaleString()}</Text></View>
              <View style={s.detailRow}><Text style={s.detailLabel}>Projected</Text><Text style={[s.detailVal, { color: "#4ade80" }]}>{fmtPoints(selected.projected_score)} pts</Text></View>
              <View style={s.detailRow}><Text style={s.detailLabel}>Players</Text><Text style={s.detailVal}>{selected.players?.length || 0}</Text></View>
            </View>

            {selected.players?.map((p: any, j: number) => (
              <View key={j} style={s.playerCard}>
                <View style={s.playerTop}>
                  <Text style={s.playerPos}>{p.roster_position || "?"}</Text>
                  <View style={{ flex: 1 }}>
                    <Text style={s.playerName}>{p.player?.first_name} {p.player?.last_name}</Text>
                    <Text style={s.playerTeam}>{p.player?.team} vs {p.player?.opponent}</Text>
                  </View>
                  <Text style={s.playerSal}>${(p.salary || 0).toLocaleString()}</Text>
                </View>
                <View style={s.playerStats}>
                  <Text style={s.pStat}>Proj: <Text style={s.pStatBold}>{fmtPoints(p.projected_fp)}</Text></Text>
                  <Text style={s.pStat}>Value: <Text style={s.pStatBold}>{p.value != null ? p.value.toFixed(1) : "..."}</Text></Text>
                  <Text style={s.pStat}>Own: <Text style={s.pStatBold}>{p.ownership != null ? p.ownership.toFixed(1) + "%" : "..."}</Text></Text>
                </View>
              </View>
            ))}

            {selected.explanation && (
              <View style={s.explainCard}>
                <Text style={s.explainTitle}>AI Explanation</Text>
                <Text style={s.explainText}>{selected.explanation}</Text>
              </View>
            )}
          </ScrollView>
        )}
      </Modal>
    </View>
  );
}

const s = StyleSheet.create({
  flex: { flex: 1, backgroundColor: "#0a0a0a" },
  scroll: { flex: 1 },
  container: { padding: 20, gap: 16 },
  row: { flexDirection: "row", gap: 12 },
  chip: { flex: 1, padding: 12, borderRadius: 12, backgroundColor: "#1a1a1a", borderWidth: 1, borderColor: "#333", alignItems: "center" },
  chipActive: { borderColor: "#4ade80", backgroundColor: "#4ade8020" },
  chipText: { color: "#888", fontWeight: "600" }, chipTextActive: { color: "#4ade80", fontWeight: "700" },
  card: { backgroundColor: "#1a1a1a", borderRadius: 16, padding: 16, borderWidth: 1, borderColor: "#333" },
  label: { fontSize: 12, color: "#666", textTransform: "uppercase", marginBottom: 6 },
  input: { backgroundColor: "#111", color: "#fff", borderRadius: 10, padding: 12, fontSize: 16, borderWidth: 1, borderColor: "#333" },
  btn: { backgroundColor: "#4ade80", borderRadius: 12, padding: 16, alignItems: "center" },
  btnText: { color: "#000", fontWeight: "700", fontSize: 16 },

  lineupCard: { backgroundColor: "#1a1a1a", borderRadius: 16, padding: 16, borderWidth: 1, borderColor: "#333" },
  lineupHeader: { flexDirection: "row", justifyContent: "space-between", alignItems: "center", marginBottom: 10 },
  lineupNum: { fontSize: 16, fontWeight: "700", color: "#4ade80" },
  arrow: { fontSize: 20, color: "#666" },
  lineupStats: { flexDirection: "row", gap: 16 },
  stat: { fontSize: 13, color: "#888" }, statBold: { color: "#fff", fontWeight: "600" },

  modal: { flex: 1, backgroundColor: "#0a0a0a" },
  modalContent: { padding: 20, gap: 16, paddingBottom: 60 },
  modalHeader: { flexDirection: "row", justifyContent: "space-between", alignItems: "center" },
  modalTitle: { fontSize: 22, fontWeight: "900", color: "#4ade80", fontStyle: "italic" },
  closeBtn: { fontSize: 24, color: "#888", padding: 8 },

  detailCard: { backgroundColor: "#1a1a1a", borderRadius: 16, padding: 16, borderWidth: 1, borderColor: "#333", gap: 8 },
  detailRow: { flexDirection: "row", justifyContent: "space-between" },
  detailLabel: { fontSize: 13, color: "#888" },
  detailVal: { fontSize: 14, fontWeight: "600", color: "#fff" },

  playerCard: { backgroundColor: "#1a1a1a", borderRadius: 12, padding: 14, borderWidth: 1, borderColor: "#333" },
  playerTop: { flexDirection: "row", alignItems: "center", gap: 12 },
  playerPos: { fontSize: 13, fontWeight: "700", color: "#4ade80", width: 28 },
  playerName: { fontSize: 15, fontWeight: "600", color: "#fff" },
  playerTeam: { fontSize: 12, color: "#888", marginTop: 2 },
  playerSal: { fontSize: 14, fontWeight: "600", color: "#4ade80" },
  playerStats: { flexDirection: "row", gap: 20, marginTop: 10, paddingTop: 10, borderTopWidth: 1, borderColor: "#333" },
  pStat: { fontSize: 12, color: "#888" }, pStatBold: { color: "#ccc", fontWeight: "600" },

  explainCard: { backgroundColor: "#0d2818", borderRadius: 16, padding: 16, borderWidth: 1, borderColor: "#4ade8030" },
  explainTitle: { fontSize: 12, fontWeight: "700", color: "#4ade80", textTransform: "uppercase", marginBottom: 8 },
  explainText: { fontSize: 14, color: "#ccc", lineHeight: 22 },
});