import { useMemo } from "react";
import { ActivityIndicator, ScrollView, StyleSheet, Text, TouchableOpacity, View } from "react-native";
import { useRouter } from "expo-router";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { MobileStadiumBackground } from "../../../components/MobileStadiumBackground";
import { useOptimizerSession } from "../../../lib/optimizer-session";
import { OPTIMIZER_SPORTS, formatSalary, formatSourceLabel } from "../../../lib/optimizer-config";
import { filterOpenSlates } from "../../../lib/optimizer-flow.mjs";

export default function OptimizerLandingScreen() {
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const session = useOptimizerSession();
  const openSlates = useMemo(() => filterOpenSlates(session.slates), [session.slates]);
  const source = formatSourceLabel(
    session.dataSource || session.selectedSlate?.data_source,
    session.selectedSlate?.data_source,
    session.selectedSlate?.freshness,
  );

  return (
    <MobileStadiumBackground>
      <ScrollView
        style={styles.scroll}
        contentContainerStyle={[styles.content, { paddingBottom: 28 + insets.bottom }]}
      >
        <Text style={styles.section}>PLATFORM</Text>
        <View style={styles.platformRow}>
          {([
            ["draftkings", "DraftKings"],
            ["fanduel", "FanDuel"],
          ] as const).map(([id, label]) => (
            <TouchableOpacity
              key={id}
              style={[styles.platformCard, session.platform === id && styles.platformCardOn]}
              onPress={() => session.setPlatform(id)}
            >
              <Text style={session.platform === id ? styles.platformTextOn : styles.platformText}>{label}</Text>
            </TouchableOpacity>
          ))}
        </View>

        <Text style={styles.section}>SPORT</Text>
        <View style={styles.wrap}>
          {OPTIMIZER_SPORTS.map((sport) => (
            <TouchableOpacity
              key={sport}
              style={[styles.chip, session.sport === sport && styles.chipOn]}
              onPress={() => session.setSport(sport)}
            >
              <Text style={session.sport === sport ? styles.chipTextOn : styles.chipText}>{sport.toUpperCase()}</Text>
            </TouchableOpacity>
          ))}
        </View>

        <Text style={styles.section}>DFS SALARY SLATE</Text>
        <View style={styles.card}>
          {session.fetchingSlates ? (
            <ActivityIndicator color="#c9a84c" />
          ) : openSlates.length > 0 ? (
            openSlates.map((slate: any) => (
              <TouchableOpacity
                key={slate.id}
                style={[styles.slateRow, session.slateId === slate.id && styles.slateRowOn]}
                onPress={() => session.setSlateId(slate.id)}
              >
                <Text style={session.slateId === slate.id ? styles.slateNameOn : styles.slateName}>
                  {slate.slate_name || `Slate ${slate.id}`}
                </Text>
                <Text style={styles.slateMeta}>
                  {slate.player_count || 0} players · {slate.game_count || 0} games
                  {slate.freshness ? ` · ${slate.freshness}` : ""}
                </Text>
              </TouchableOpacity>
            ))
          ) : (
            <Text style={styles.empty}>
              {session.slateError || "No live slates for this sport and platform."}
            </Text>
          )}
          {session.selectedSlate ? (
            <Text style={styles.context}>
              Cap {formatSalary(session.cap)} · {source.label}
            </Text>
          ) : null}
        </View>

        <Text style={styles.section}>PARLAY / SPORTSBOOKS</Text>
        <View style={styles.row}>
          <TouchableOpacity style={styles.halfCard} onPress={() => router.push("/(tabs)/market-tools/parlay" as any)}>
            <Text style={styles.halfTitle}>Parlay Builder</Text>
            <Text style={styles.halfBody}>Moneylines, spreads, totals</Text>
          </TouchableOpacity>
          <TouchableOpacity style={styles.halfCard} onPress={() => router.push("/(tabs)/market-tools/bookmakers" as any)}>
            <Text style={styles.halfTitle}>Sportsbooks</Text>
            <Text style={styles.halfBody}>Live books + catalog</Text>
          </TouchableOpacity>
        </View>

        <Text style={styles.section}>SAVED LINEUPS</Text>
        <TouchableOpacity style={styles.card} onPress={() => router.push("/(tabs)/lineups")}>
          <Text style={styles.savedTitle}>
            {session.savedHistory.length} saved lineup{session.savedHistory.length === 1 ? "" : "s"}
          </Text>
          <Text style={styles.halfBody}>Open History / Saved Lineups</Text>
        </TouchableOpacity>

        <Text style={styles.next}>Open Optimizer to review roster, strategy, players and build.</Text>
        <TouchableOpacity
          style={styles.openBtn}
          onPress={() => router.push("/optimizer/builder")}
        >
          <Text style={styles.openBtnText}>OPEN OPTIMIZER</Text>
        </TouchableOpacity>
      </ScrollView>
    </MobileStadiumBackground>
  );
}

const styles = StyleSheet.create({
  scroll: { flex: 1 },
  content: { padding: 20, gap: 14 },
  section: { color: "#c9a84c", fontSize: 12, fontWeight: "800", letterSpacing: 1.2 },
  platformRow: { flexDirection: "row", gap: 12 },
  platformCard: {
    flex: 1,
    minHeight: 88,
    borderRadius: 16,
    backgroundColor: "rgba(10,15,36,0.82)",
    borderWidth: 1,
    borderColor: "#1e293b",
    alignItems: "center",
    justifyContent: "center",
    padding: 16,
  },
  platformCardOn: { borderColor: "#c9a84c", backgroundColor: "rgba(201,168,76,0.16)" },
  platformText: { color: "#94a3b8", fontWeight: "700", fontSize: 16 },
  platformTextOn: { color: "#c9a84c", fontWeight: "800", fontSize: 16 },
  wrap: { flexDirection: "row", flexWrap: "wrap", gap: 8 },
  chip: {
    paddingHorizontal: 14,
    paddingVertical: 10,
    borderRadius: 20,
    backgroundColor: "rgba(10,15,36,0.82)",
    borderWidth: 1,
    borderColor: "#1e293b",
  },
  chipOn: { borderColor: "#c9a84c", backgroundColor: "rgba(201,168,76,0.16)" },
  chipText: { color: "#94a3b8", fontWeight: "600" },
  chipTextOn: { color: "#c9a84c", fontWeight: "700" },
  card: {
    backgroundColor: "rgba(10,15,36,0.82)",
    borderRadius: 16,
    padding: 14,
    borderWidth: 1,
    borderColor: "#1e293b",
    gap: 10,
  },
  slateRow: { paddingVertical: 8, borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: "#1e293b" },
  slateRowOn: { backgroundColor: "rgba(201,168,76,0.08)", borderRadius: 8, paddingHorizontal: 8 },
  slateName: { color: "#e2e8f0", fontWeight: "600" },
  slateNameOn: { color: "#c9a84c", fontWeight: "700" },
  slateMeta: { color: "#94a3b8", fontSize: 12, marginTop: 2 },
  empty: { color: "#94a3b8", fontSize: 13, lineHeight: 18 },
  context: { color: "#94a3b8", fontSize: 12 },
  row: { flexDirection: "row", gap: 12 },
  halfCard: {
    flex: 1,
    backgroundColor: "rgba(10,15,36,0.82)",
    borderRadius: 16,
    padding: 14,
    borderWidth: 1,
    borderColor: "#1e293b",
  },
  halfTitle: { color: "#f0f6fc", fontWeight: "700" },
  halfBody: { color: "#94a3b8", fontSize: 12, marginTop: 4 },
  savedTitle: { color: "#f0f6fc", fontWeight: "700", fontSize: 16 },
  next: { color: "#e2e8f0", fontSize: 15, lineHeight: 22, textAlign: "center", marginTop: 8 },
  openBtn: {
    backgroundColor: "#c9a84c",
    borderRadius: 14,
    paddingVertical: 18,
    alignItems: "center",
  },
  openBtnText: { color: "#060b1a", fontWeight: "900", fontSize: 18, letterSpacing: 0.6 },
});
