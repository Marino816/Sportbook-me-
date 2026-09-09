import { useState } from "react";
import {
  ActivityIndicator,
  Modal,
  ScrollView,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from "react-native";
import { useRouter } from "expo-router";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { MobileStadiumBackground } from "../../../components/MobileStadiumBackground";
import { useOptimizerSession } from "../../../lib/optimizer-session";
import {
  EXPOSURE_OPTIONS,
  MLB_STACK_OPTIONS,
  STRATEGIES,
  formatSalary,
} from "../../../lib/optimizer-config";
import { slotLabel } from "../../../lib/optimizer-flow.mjs";

export default function OptimizerBuilderScreen() {
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const session = useOptimizerSession();
  const [strategyOpen, setStrategyOpen] = useState(false);
  const slots = session.roster?.slots || [];

  async function onBuild() {
    const result = await session.handleBuild();
    if (result.ok && !result.stayOnPage2) {
      router.push("/optimizer/result");
    }
  }

  return (
    <MobileStadiumBackground>
      <ScrollView
        style={styles.scroll}
        contentContainerStyle={[styles.content, { paddingBottom: 28 + insets.bottom }]}
      >
        <View style={styles.topRow}>
          <TouchableOpacity onPress={() => router.back()}>
            <Text style={styles.back}>‹ Setup</Text>
          </TouchableOpacity>
          <Text style={styles.meta}>
            {session.platform === "draftkings" ? "DraftKings" : "FanDuel"} · {session.sport.toUpperCase()}
          </Text>
        </View>

        <View style={styles.card}>
          <View style={styles.strategyHead}>
            <View>
              <Text style={styles.label}>Strategy</Text>
              <Text style={styles.strategyVal}>{session.strategy.toUpperCase()} · {session.count} lineups</Text>
            </View>
            <TouchableOpacity style={styles.adjust} onPress={() => setStrategyOpen(true)}>
              <Text style={styles.adjustText}>Adjust Strategy</Text>
            </TouchableOpacity>
          </View>
        </View>

        {slots.map((slot: string, index: number) => {
          const player = session.slots[index];
          return (
            <TouchableOpacity
              key={`${slot}-${index}`}
              style={styles.slot}
              onPress={() => {
                session.setSelectingSlotIndex(index);
                router.push("/optimizer/players");
              }}
            >
              <Text style={styles.slotPos}>{slotLabel(slot, session.roster)}</Text>
              <View style={{ flex: 1 }}>
                <Text style={styles.slotName}>{player?.name || "Tap to select"}</Text>
                <Text style={styles.slotTeam}>{player?.team || "Empty"}</Text>
              </View>
              {player ? (
                <View style={{ alignItems: "flex-end" }}>
                  <Text style={styles.slotSal}>{formatSalary(player.salary)}</Text>
                  <TouchableOpacity onPress={() => session.clearSlot(index)}>
                    <Text style={styles.clear}>Clear</Text>
                  </TouchableOpacity>
                </View>
              ) : (
                <Text style={styles.chevron}>›</Text>
              )}
            </TouchableOpacity>
          );
        })}

        {session.buildError ? <Text style={styles.error}>{session.buildError}</Text> : null}
        {session.loading || session.progress ? (
          <View style={styles.progress}>
            {session.loading ? <ActivityIndicator color="#c9a84c" /> : null}
            <Text style={styles.progressText}>{session.progress}</Text>
          </View>
        ) : null}

        <TouchableOpacity
          style={styles.build}
          onPress={onBuild}
          disabled={session.loading || session.fetchingSlates || !session.slateId}
        >
          <Text style={styles.buildText}>{session.loading ? "Building…" : "BUILD OPTIMAL LINEUP"}</Text>
        </TouchableOpacity>
      </ScrollView>

      <Modal visible={strategyOpen} transparent animationType="fade">
        <View style={styles.overlay}>
          <View style={styles.panel}>
            <View style={styles.panelHead}>
              <Text style={styles.panelTitle}>Strategy</Text>
              <TouchableOpacity onPress={() => setStrategyOpen(false)}>
                <Text style={styles.closeX}>X</Text>
              </TouchableOpacity>
            </View>
            <View style={styles.wrap}>
              {STRATEGIES.map((item) => (
                <TouchableOpacity
                  key={item.id}
                  style={[styles.chip, session.strategy === item.id && styles.chipOn]}
                  onPress={() => session.setStrategy(item.id)}
                >
                  <Text style={session.strategy === item.id ? styles.chipTextOn : styles.chipText}>{item.label}</Text>
                </TouchableOpacity>
              ))}
            </View>
            <Text style={styles.label}>Lineups · {session.planLimit}/slate</Text>
            <View style={styles.stepper}>
              <TouchableOpacity style={styles.stepBtn} onPress={() => session.setCount(session.count - 1)}>
                <Text style={styles.stepText}>−</Text>
              </TouchableOpacity>
              <Text style={styles.count}>{session.count}</Text>
              <TouchableOpacity style={styles.stepBtn} onPress={() => session.setCount(session.count + 1)}>
                <Text style={styles.stepText}>+</Text>
              </TouchableOpacity>
            </View>
            {session.sport === "mlb" ? (
              <>
                <Text style={styles.label}>MLB stack</Text>
                <View style={styles.wrap}>
                  <TouchableOpacity
                    style={[styles.chip, session.stackSize == null && styles.chipOn]}
                    onPress={() => session.setStackSize(null)}
                  >
                    <Text style={session.stackSize == null ? styles.chipTextOn : styles.chipText}>Auto</Text>
                  </TouchableOpacity>
                  {MLB_STACK_OPTIONS.map((item) => (
                    <TouchableOpacity
                      key={item.label}
                      style={[styles.chip, session.stackSize === item.id && styles.chipOn]}
                      onPress={() => session.setStackSize(item.id)}
                    >
                      <Text style={session.stackSize === item.id ? styles.chipTextOn : styles.chipText}>{item.label}</Text>
                    </TouchableOpacity>
                  ))}
                </View>
              </>
            ) : null}
            <Text style={styles.label}>Max exposure</Text>
            <View style={styles.wrap}>
              <TouchableOpacity
                style={[styles.chip, session.exposure == null && styles.chipOn]}
                onPress={() => session.setExposure(null)}
              >
                <Text style={session.exposure == null ? styles.chipTextOn : styles.chipText}>Auto</Text>
              </TouchableOpacity>
              {EXPOSURE_OPTIONS.map((item) => (
                <TouchableOpacity
                  key={item.label}
                  style={[styles.chip, session.exposure === item.id && styles.chipOn]}
                  onPress={() => session.setExposure(item.id)}
                >
                  <Text style={session.exposure === item.id ? styles.chipTextOn : styles.chipText}>{item.label}</Text>
                </TouchableOpacity>
              ))}
            </View>
          </View>
        </View>
      </Modal>
    </MobileStadiumBackground>
  );
}

const styles = StyleSheet.create({
  scroll: { flex: 1 },
  content: { padding: 20, gap: 10 },
  topRow: { flexDirection: "row", justifyContent: "space-between", alignItems: "center" },
  back: { color: "#c9a84c", fontSize: 16, fontWeight: "700" },
  meta: { color: "#94a3b8", fontSize: 12 },
  card: {
    backgroundColor: "rgba(10,15,36,0.82)",
    borderRadius: 16,
    padding: 14,
    borderWidth: 1,
    borderColor: "#1e293b",
  },
  strategyHead: { flexDirection: "row", justifyContent: "space-between", alignItems: "center" },
  label: { color: "#64748b", fontSize: 11, textTransform: "uppercase", letterSpacing: 0.6, marginBottom: 8, marginTop: 8 },
  strategyVal: { color: "#f0f6fc", fontWeight: "700", fontSize: 16 },
  adjust: { borderWidth: 1, borderColor: "#c9a84c", borderRadius: 10, paddingHorizontal: 10, paddingVertical: 8 },
  adjustText: { color: "#c9a84c", fontWeight: "700", fontSize: 12 },
  slot: {
    flexDirection: "row",
    alignItems: "center",
    gap: 12,
    backgroundColor: "rgba(10,15,36,0.82)",
    borderRadius: 14,
    padding: 14,
    borderWidth: 1,
    borderColor: "#1e293b",
  },
  slotPos: { width: 44, color: "#c9a84c", fontWeight: "800" },
  slotName: { color: "#f0f6fc", fontWeight: "600" },
  slotTeam: { color: "#64748b", fontSize: 12, marginTop: 2 },
  slotSal: { color: "#c9a84c", fontWeight: "700" },
  clear: { color: "#94a3b8", fontSize: 11, marginTop: 4 },
  chevron: { color: "#64748b", fontSize: 22 },
  error: { color: "#fca5a5", fontSize: 13, lineHeight: 18 },
  progress: { alignItems: "center", gap: 8 },
  progressText: { color: "#c9a84c", fontWeight: "600" },
  build: { backgroundColor: "#c9a84c", borderRadius: 14, paddingVertical: 18, alignItems: "center", marginTop: 8 },
  buildText: { color: "#060b1a", fontWeight: "900", fontSize: 16, letterSpacing: 0.4 },
  overlay: { flex: 1, backgroundColor: "rgba(0,0,0,0.65)", justifyContent: "center", padding: 20 },
  panel: { backgroundColor: "#0a0f24", borderRadius: 16, padding: 16, borderWidth: 1, borderColor: "#c9a84c40" },
  panelHead: { flexDirection: "row", justifyContent: "space-between", alignItems: "center", marginBottom: 8 },
  panelTitle: { color: "#c9a84c", fontWeight: "800", fontSize: 18 },
  closeX: { color: "#f0f6fc", fontSize: 20, fontWeight: "800", padding: 6 },
  wrap: { flexDirection: "row", flexWrap: "wrap", gap: 8 },
  chip: {
    paddingHorizontal: 12,
    paddingVertical: 8,
    borderRadius: 20,
    backgroundColor: "#111827",
    borderWidth: 1,
    borderColor: "#1e293b",
  },
  chipOn: { borderColor: "#c9a84c", backgroundColor: "#c9a84c20" },
  chipText: { color: "#94a3b8", fontWeight: "600" },
  chipTextOn: { color: "#c9a84c", fontWeight: "700" },
  stepper: { flexDirection: "row", alignItems: "center", gap: 16, marginBottom: 8 },
  stepBtn: {
    width: 40,
    height: 40,
    borderRadius: 10,
    backgroundColor: "#111827",
    borderWidth: 1,
    borderColor: "#1e293b",
    alignItems: "center",
    justifyContent: "center",
  },
  stepText: { color: "#c9a84c", fontSize: 20, fontWeight: "700" },
  count: { color: "#f0f6fc", fontSize: 20, fontWeight: "800", minWidth: 28, textAlign: "center" },
});
