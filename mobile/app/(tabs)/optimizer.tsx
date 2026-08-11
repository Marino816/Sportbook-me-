import { useState, useEffect } from "react";
import { View, Text, StyleSheet, TouchableOpacity, TextInput, ScrollView, ActivityIndicator, Alert, Modal } from "react-native";
import { getToken } from "../../lib/api";

const API_URL = "https://sportbook-me-production.up.railway.app/api";

export default function OptimizerScreen() {
  const [sport, setSport] = useState("mlb");
  const [platform, setPlatform] = useState<"draftkings" | "fanduel">("draftkings");
  const [strategy, setStrategy] = useState("balanced");
  const [count, setCount] = useState("3");
  const [slateId, setSlateId] = useState<number | null>(null);
  const [slates, setSlates] = useState<any[]>([]);
  const [lineups, setLineups] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [fetchingSlates, setFetchingSlates] = useState(false);
  const [selected, setSelected] = useState<any>(null);
  const [dataSource, setDataSource] = useState<string>("");

  // Fetch available slates — filter by sport AND platform, reset stale state
  useEffect(() => {
    setSlates([]);
    setSlateId(null);
    setLineups([]);
    (async () => {
      setFetchingSlates(true);
      try {
        const token = await getToken();
        const res = await fetch(`${API_URL}/sports/slates?sport=${sport.toUpperCase()}`, {
          headers: token ? { Authorization: `Bearer ${token}` } : {},
        });
        const data = await res.json();
        const items: any[] = (data.data || data) || [];
        // Filter to current platform
        const siteKey = platform === "draftkings" ? "DraftKings" : "FanDuel";
        const filtered = items.filter((s: any) =>
          (s.site || "").toLowerCase() === siteKey.toLowerCase() ||
          (s.platform || "").toLowerCase() === platform
        );
        if (filtered.length > 0) {
          setSlates(filtered);
          // Auto-select first match
          setSlateId(filtered[0].slate_id || filtered[0].id || null);
        } else {
          setSlates([]);
          setSlateId(null);
        }
      } catch {
        setSlates([]);
        setSlateId(null);
      } finally { setFetchingSlates(false); }
    })();
  }, [sport, platform]);

  async function handleBuild() {
    if (!slateId || slateId <= 0) {
      Alert.alert("Select a Slate", "No slate selected. Please choose a slate above.");
      return;
    }
    setLoading(true);
    setLineups([]);
    try {
      const token = await getToken();
      const res = await fetch(`${API_URL}/optimize`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({
          slate_id: slateId,
          settings: {
            platform: platform,
            strategy: strategy,
            num_lineups: parseInt(count) || 1,
          },
        }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || `HTTP ${res.status}`);
      }
      const data = await res.json();
      const result = data.data || data;
      setLineups(result.lineups || []);
      setDataSource(result.source || "demo");
    } catch (e: any) {
      Alert.alert("Build Failed", e.message);
    } finally { setLoading(false); }
  }

  function fmtSalary(n: number) { return n ? `$${(n / 1000).toFixed(1)}K` : "..."; }
  function fmtPoints(n: number) { return n != null ? n.toFixed(1) : "..."; }

  return (
    <View style={s.flex}>
      <ScrollView style={s.scroll} contentContainerStyle={s.container}>
        {/* Sport Selector */}
        <View style={s.row}>
          {["mlb", "nba", "nfl"].map((sp) => (
            <TouchableOpacity key={sp} style={[s.chip, sport === sp && s.chipActive]} onPress={() => setSport(sp)}>
              <Text style={sport === sp ? s.chipTextActive : s.chipText}>{sp.toUpperCase()}</Text>
            </TouchableOpacity>
          ))}
        </View>

        {/* Platform */}
        <View style={s.row}>
          <TouchableOpacity style={[s.chip, platform === "draftkings" && s.chipActive]} onPress={() => setPlatform("draftkings")}>
            <Text style={platform === "draftkings" ? s.chipTextActive : s.chipText}>DraftKings</Text>
          </TouchableOpacity>
          <TouchableOpacity style={[s.chip, platform === "fanduel" && s.chipActive]} onPress={() => setPlatform("fanduel")}>
            <Text style={platform === "fanduel" ? s.chipTextActive : s.chipText}>FanDuel</Text>
          </TouchableOpacity>
        </View>

        {/* Slate Selection */}
        <View style={s.card}>
          <Text style={s.label}>SLATE</Text>
          {fetchingSlates ? (
            <ActivityIndicator color="#c9a84c" style={{ marginTop: 8 }} />
          ) : slates.length > 0 ? (
            <ScrollView horizontal showsHorizontalScrollIndicator={false} style={{ marginTop: 4 }}>
              {slates.map((sl: any, i: number) => (
                <TouchableOpacity key={i} style={[s.slateChip, slateId === (sl.slate_id || sl.id) && s.slateChipActive]}
                                    onPress={() => setSlateId(sl.slate_id || sl.id)}>
                                  <Text style={slateId === (sl.slate_id || sl.id) ? s.slateChipTextActive : s.slateChipText}>
                                    {sl.label || sl.site || sl.platform || ("Slate #" + (i + 1))}
                                  </Text>
                </TouchableOpacity>
              ))}
            </ScrollView>
          ) : (
            <Text style={s.noSlate}>No live slates available — using demo data</Text>
          )}
        </View>

        {/* Strategy + Count */}
        <View style={s.card}>
          <Text style={s.label}>Strategy</Text>
          <TextInput style={s.input} value={strategy} onChangeText={setStrategy} placeholderTextColor="#666" />
        </View>
        <View style={s.card}>
          <Text style={s.label}>Lineups ({count})</Text>
          <TextInput style={s.input} value={count} onChangeText={setCount} keyboardType="numeric" placeholderTextColor="#666" />
        </View>

        {/* Data Source Label */}
        <View style={s.demoBadge}>
            <Text style={s.demoText}>SportsDataIO Trial — Scrambled Integration Data</Text>
          </View>

        <TouchableOpacity style={s.btn} onPress={handleBuild} disabled={loading || fetchingSlates}>
          <Text style={s.btnText}>{loading ? "Building..." : "Build Lineups"}</Text>
        </TouchableOpacity>

        {loading && <ActivityIndicator size="large" color="#c9a84c" style={{ marginTop: 16 }} />}

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

      {/* Lineup Detail Modal — unchanged from fix K */}
      <Modal visible={!!selected} animationType="slide">
        {selected && (
          <ScrollView style={s.modal} contentContainerStyle={s.modalContent}>
            <View style={s.modalHeader}>
              <Text style={s.modalTitle}>Lineup Details</Text>
              <TouchableOpacity onPress={() => setSelected(null)}>
                <Text style={s.closeBtn}>✕ Back</Text>
              </TouchableOpacity>
            </View>
            <View style={s.detailCard}>
              <View style={s.detailRow}><Text style={s.detailLabel}>Sport</Text><Text style={s.detailVal}>{sport.toUpperCase()}</Text></View>
              <View style={s.detailRow}><Text style={s.detailLabel}>Platform</Text><Text style={s.detailVal}>{platform.toUpperCase()}</Text></View>
              <View style={s.detailRow}><Text style={s.detailLabel}>Strategy</Text><Text style={s.detailVal}>{strategy}</Text></View>
              <View style={s.detailRow}><Text style={s.detailLabel}>Total Salary</Text><Text style={s.detailVal}>${(selected.total_salary || 0).toLocaleString()}</Text></View>
              <View style={s.detailRow}><Text style={s.detailLabel}>Projected</Text><Text style={[s.detailVal, { color: "#c9a84c" }]}>{fmtPoints(selected.projected_score)} pts</Text></View>
              <View style={s.detailRow}><Text style={s.detailLabel}>Players</Text><Text style={s.detailVal}>{selected.players?.length || 0}</Text></View>
              <View style={s.detailRow}><Text style={s.detailLabel}>Data Source</Text><Text style={[s.detailVal, { color: dataSource === "live" ? "#c9a84c" : "#ffaa00" }]}>{dataSource || "demo"}</Text></View>
            </View>
            {selected.players?.map((p: any, j: number) => (
              <View key={j} style={s.playerCard}>
                <View style={s.playerTop}>
                  <Text style={s.playerPos}>{p.roster_slot || p.assigned_slot || p.roster_position || "?"}</Text>
                  <View style={{ flex: 1 }}>
                    <Text style={s.playerName}>{p.name || `Player ${p.id}`}</Text>
                    <Text style={s.playerTeam}>{p.team || "?"}</Text>
                  </View>
                  <Text style={s.playerSal}>${(p.salary || 0).toLocaleString()}</Text>
                </View>
                <View style={s.playerStats}>
                  <Text style={s.pStat}>Proj: <Text style={s.pStatBold}>{fmtPoints(p.projected_fp)}</Text></Text>
                  {p.value != null && p.value > 0 && <Text style={s.pStat}>Value: <Text style={s.pStatBold}>{p.value.toFixed(1)}</Text></Text>}
                  {p.ownership != null && p.ownership > 0 ? <Text style={s.pStat}>Own: <Text style={s.pStatBold}>{p.ownership.toFixed(1)}%</Text></Text> : <Text style={s.pStat}>Own: <Text style={s.pStatBold}>N/A</Text></Text>}
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
  flex: { flex: 1, backgroundColor: "#060b1a" },
  scroll: { flex: 1 }, container: { padding: 20, gap: 16 },
  row: { flexDirection: "row", gap: 12 },
  chip: { flex: 1, padding: 12, borderRadius: 12, backgroundColor: "#0a0f24", borderWidth: 1, borderColor: "#333", alignItems: "center" },
  chipActive: { borderColor: "#c9a84c", backgroundColor: "#c9a84c20" },
  chipText: { color: "#888", fontWeight: "600" }, chipTextActive: { color: "#c9a84c", fontWeight: "700" },
  card: { backgroundColor: "#0a0f24", borderRadius: 16, padding: 16, borderWidth: 1, borderColor: "#333" },
  label: { fontSize: 12, color: "#666", textTransform: "uppercase", marginBottom: 6 },
  input: { backgroundColor: "#111", color: "#fff", borderRadius: 10, padding: 12, fontSize: 16, borderWidth: 1, borderColor: "#333" },
  btn: { backgroundColor: "#c9a84c", borderRadius: 12, padding: 16, alignItems: "center" },
  btnText: { color: "#000", fontWeight: "700", fontSize: 16 },
  noSlate: { color: "#ffaa00", fontSize: 13, marginTop: 4 },
  slateChip: { paddingHorizontal: 14, paddingVertical: 10, borderRadius: 20, backgroundColor: "#0a0f24", borderWidth: 1, borderColor: "#333", marginRight: 8 },
  slateChipActive: { borderColor: "#c9a84c", backgroundColor: "#c9a84c20" },
  slateChipText: { color: "#888", fontSize: 12, fontWeight: "600" },
  slateChipTextActive: { color: "#c9a84c" },
  demoBadge: { backgroundColor: "#332200", borderRadius: 10, padding: 10, borderWidth: 1, borderColor: "#ffaa0040" },
  demoText: { color: "#ffaa00", fontSize: 12, textAlign: "center" },
  lineupCard: { backgroundColor: "#0a0f24", borderRadius: 16, padding: 16, borderWidth: 1, borderColor: "#333" },
  lineupHeader: { flexDirection: "row", justifyContent: "space-between", alignItems: "center", marginBottom: 10 },
  lineupNum: { fontSize: 16, fontWeight: "700", color: "#c9a84c" },
  arrow: { fontSize: 20, color: "#666" },
  lineupStats: { flexDirection: "row", gap: 16 },
  stat: { fontSize: 13, color: "#888" }, statBold: { color: "#fff", fontWeight: "600" },
  modal: { flex: 1, backgroundColor: "#060b1a" },
  modalContent: { padding: 20, gap: 16, paddingBottom: 60 },
  modalHeader: { flexDirection: "row", justifyContent: "space-between", alignItems: "center" },
  modalTitle: { fontSize: 22, fontWeight: "900", color: "#c9a84c", fontStyle: "italic" },
  closeBtn: { fontSize: 16, color: "#888", padding: 8 },
  detailCard: { backgroundColor: "#0a0f24", borderRadius: 16, padding: 16, borderWidth: 1, borderColor: "#333", gap: 8 },
  detailRow: { flexDirection: "row", justifyContent: "space-between" },
  detailLabel: { fontSize: 13, color: "#888" }, detailVal: { fontSize: 14, fontWeight: "600", color: "#fff" },
  playerCard: { backgroundColor: "#0a0f24", borderRadius: 12, padding: 14, borderWidth: 1, borderColor: "#333" },
  playerTop: { flexDirection: "row", alignItems: "center", gap: 12 },
  playerPos: { fontSize: 13, fontWeight: "700", color: "#c9a84c", width: 28 },
  playerName: { fontSize: 15, fontWeight: "600", color: "#fff" },
  playerTeam: { fontSize: 12, color: "#888", marginTop: 2 },
  playerSal: { fontSize: 14, fontWeight: "600", color: "#c9a84c" },
  playerStats: { flexDirection: "row", gap: 20, marginTop: 10, paddingTop: 10, borderTopWidth: 1, borderColor: "#333" },
  pStat: { fontSize: 12, color: "#888" }, pStatBold: { color: "#ccc", fontWeight: "600" },
  explainCard: { backgroundColor: "#0d2818", borderRadius: 16, padding: 16, borderWidth: 1, borderColor: "#c9a84c30" },
  explainTitle: { fontSize: 12, fontWeight: "700", color: "#c9a84c", textTransform: "uppercase", marginBottom: 8 },
  explainText: { fontSize: 14, color: "#ccc", lineHeight: 22 },
});