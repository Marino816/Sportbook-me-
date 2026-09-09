import { useState } from "react";
import {
  ActivityIndicator,
  Alert,
  Modal,
  ScrollView,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from "react-native";
import { useRouter } from "expo-router";
import {
  SafeAreaProvider,
  SafeAreaView,
  initialWindowMetrics,
  useSafeAreaInsets,
} from "react-native-safe-area-context";
import { MobileStadiumBackground } from "../../../components/MobileStadiumBackground";
import { useOptimizerSession } from "../../../lib/optimizer-session";
import {
  formatProjectionSource,
  formatSalary,
  formatSourceLabel,
  lineupProjectionIntegrity,
} from "../../../lib/optimizer-config";

function fmtPoints(n: number | null | undefined) {
  return n != null && !Number.isNaN(Number(n)) ? Number(n).toFixed(1) : "—";
}

export default function OptimizerResultScreen() {
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const session = useOptimizerSession();
  const [selected, setSelected] = useState<any>(null);
  const [saving, setSaving] = useState(false);
  const source = formatSourceLabel(
    session.dataSource || session.selectedSlate?.data_source,
    session.selectedSlate?.data_source,
    session.selectedSlate?.freshness,
  );
  const modalMetrics = initialWindowMetrics ?? {
    frame: { x: 0, y: 0, width: 0, height: 0 },
    insets: {
      top: insets.top,
      left: insets.left,
      right: insets.right,
      bottom: insets.bottom,
    },
  };

  async function onSave() {
    setSaving(true);
    const result = await session.handleSave();
    setSaving(false);
    if (result.ok) {
      Alert.alert("Saved", "Lineup saved to History / Saved Lineups.", [
        { text: "History", onPress: () => router.push("/(tabs)/lineups") },
        { text: "OK" },
      ]);
    }
  }

  async function onRegenerate() {
    await session.handleRegenerate();
  }

  function onEdit() {
    session.loadLineupForEdit(selected || session.lineups[0]);
    router.replace("/optimizer/builder");
  }

  return (
    <MobileStadiumBackground>
      <ScrollView
        style={styles.scroll}
        contentContainerStyle={[styles.content, { paddingBottom: 28 + insets.bottom }]}
      >
        <View style={styles.actions}>
          <TouchableOpacity style={styles.action} onPress={onSave} disabled={saving}>
            <Text style={styles.actionText}>{saving ? "Saving…" : "SAVE"}</Text>
          </TouchableOpacity>
          <TouchableOpacity style={styles.action} onPress={onRegenerate} disabled={session.loading}>
            <Text style={styles.actionText}>REGENERATE</Text>
          </TouchableOpacity>
          <TouchableOpacity style={styles.action} onPress={onEdit}>
            <Text style={styles.actionText}>EDIT</Text>
          </TouchableOpacity>
          <TouchableOpacity style={styles.action} onPress={() => router.push("/(tabs)/lineups")}>
            <Text style={styles.actionText}>HISTORY</Text>
          </TouchableOpacity>
        </View>

        {session.loading ? <ActivityIndicator color="#c9a84c" /> : null}

        {session.lineups.map((lineup, i) => {
          const remaining = session.cap - Number(lineup.total_salary || 0);
          return (
            <TouchableOpacity key={i} style={styles.lineupCard} onPress={() => setSelected(lineup)}>
              <Text style={styles.lineupNum}>Lineup #{i + 1}</Text>
              <Text style={styles.stat}>
                Proj {fmtPoints(lineup.projected_score)} · Sal {formatSalary(lineup.total_salary)} · Left {formatSalary(remaining)}
              </Text>
              {(lineup.players || []).slice(0, 4).map((player: any, j: number) => (
                <Text key={j} style={styles.preview}>
                  {player.roster_slot || "?"} {player.name}
                </Text>
              ))}
              {(lineup.players || []).length > 4 ? (
                <Text style={styles.preview}>+{(lineup.players || []).length - 4} more</Text>
              ) : null}
            </TouchableOpacity>
          );
        })}
        {!session.lineups.length ? <Text style={styles.empty}>No lineups to show.</Text> : null}
      </ScrollView>

      <Modal visible={!!selected} animationType="slide" presentationStyle="fullScreen">
        {selected && (
          <SafeAreaProvider initialMetrics={modalMetrics}>
            <SafeAreaView style={styles.modal} edges={["top", "bottom"]}>
              <ScrollView style={styles.modalScroll} contentContainerStyle={styles.modalContent}>
                <View style={styles.modalHeader}>
                  <Text style={styles.modalTitle}>Lineup details</Text>
                  <TouchableOpacity onPress={() => setSelected(null)}>
                    <Text style={styles.closeBtn}>✕ Back</Text>
                  </TouchableOpacity>
                </View>
                <View style={styles.detailCard}>
                  <Text style={styles.detailVal}>{session.sport.toUpperCase()} · {session.platform}</Text>
                  <Text style={styles.detailVal}>{formatSalary(selected.total_salary)} · {fmtPoints(selected.projected_score)} pts</Text>
                  <Text style={[styles.detailVal, { color: source.isDemo ? "#fbbf24" : "#c9a84c" }]}>{source.label}</Text>
                </View>
                {(() => {
                  const integrity = lineupProjectionIntegrity(selected);
                  const notes = [];
                  if (!integrity.totalsMatch) {
                    notes.push(`Displayed ${fmtPoints(integrity.displayed)} pts does not match the player sum ${fmtPoints(integrity.playerSum)}.`);
                  }
                  if (integrity.fallbackCount > 0) {
                    notes.push(`${integrity.fallbackCount} player${integrity.fallbackCount === 1 ? "" : "s"} use fallback projections.`);
                  }
                  notes.push("Not contest-ready as a live DraftKings salary or projection feed.");
                  return (
                    <View style={styles.honesty}>
                      {notes.map((note) => <Text key={note} style={styles.honestyText}>{note}</Text>)}
                    </View>
                  );
                })()}
                {(selected.players || []).map((player: any, j: number) => (
                  <View key={j} style={styles.playerCard}>
                    <Text style={styles.playerPos}>{player.roster_slot || "?"}</Text>
                    <View style={{ flex: 1 }}>
                      <Text style={styles.playerName}>{player.name}</Text>
                      <Text style={styles.playerTeam}>{player.team || "?"}</Text>
                    </View>
                    <Text style={styles.playerSal}>{formatSalary(player.salary)}</Text>
                    <Text style={styles.pStat}>{fmtPoints(player.projected_fp)} · {formatProjectionSource(player.projection_source).label}</Text>
                  </View>
                ))}
              </ScrollView>
            </SafeAreaView>
          </SafeAreaProvider>
        )}
      </Modal>
    </MobileStadiumBackground>
  );
}

const styles = StyleSheet.create({
  scroll: { flex: 1 },
  content: { padding: 20, gap: 12 },
  actions: { flexDirection: "row", flexWrap: "wrap", gap: 8 },
  action: {
    flexGrow: 1,
    minWidth: "45%",
    backgroundColor: "#c9a84c",
    borderRadius: 12,
    paddingVertical: 12,
    alignItems: "center",
  },
  actionText: { color: "#060b1a", fontWeight: "800" },
  lineupCard: {
    backgroundColor: "rgba(10,15,36,0.82)",
    borderRadius: 16,
    padding: 16,
    borderWidth: 1,
    borderColor: "#1e293b",
    gap: 4,
  },
  lineupNum: { color: "#c9a84c", fontWeight: "800", fontSize: 16 },
  stat: { color: "#94a3b8", fontSize: 13 },
  preview: { color: "#e2e8f0", fontSize: 13 },
  empty: { color: "#94a3b8", textAlign: "center", marginTop: 24 },
  modal: { flex: 1, backgroundColor: "#060b1a" },
  modalScroll: { flex: 1 },
  modalContent: { padding: 20, gap: 12, paddingBottom: 60 },
  modalHeader: { flexDirection: "row", justifyContent: "space-between", alignItems: "center" },
  modalTitle: { fontSize: 22, fontWeight: "900", color: "#c9a84c", fontStyle: "italic" },
  closeBtn: { fontSize: 16, color: "#94a3b8", padding: 8 },
  detailCard: { backgroundColor: "#0a0f24", borderRadius: 16, padding: 16, borderWidth: 1, borderColor: "#1e293b", gap: 6 },
  detailVal: { color: "#f0f6fc", fontWeight: "600" },
  honesty: { backgroundColor: "#14110a", borderRadius: 12, padding: 12, borderWidth: 1, borderColor: "#c9a84c30", gap: 6 },
  honestyText: { fontSize: 12, color: "#cbd5e1", lineHeight: 18 },
  playerCard: { backgroundColor: "#0a0f24", borderRadius: 12, padding: 12, borderWidth: 1, borderColor: "#1e293b", flexDirection: "row", flexWrap: "wrap", alignItems: "center", gap: 8 },
  playerPos: { color: "#c9a84c", fontWeight: "800", width: 36 },
  playerName: { color: "#f0f6fc", fontWeight: "600" },
  playerTeam: { color: "#64748b", fontSize: 12 },
  playerSal: { color: "#c9a84c", fontWeight: "600" },
  pStat: { color: "#94a3b8", fontSize: 12, width: "100%" },
});
