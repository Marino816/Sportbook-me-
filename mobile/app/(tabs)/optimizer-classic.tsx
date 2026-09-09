import { useCallback, useEffect, useMemo, useState } from "react";
import {
  View,
  Text,
  StyleSheet,
  TouchableOpacity,
  ScrollView,
  ActivityIndicator,
  Alert,
  Modal,
} from "react-native";
import { useFocusEffect, useLocalSearchParams } from "expo-router";
import {
  SafeAreaProvider,
  SafeAreaView,
  initialWindowMetrics,
  useSafeAreaInsets,
} from "react-native-safe-area-context";
import {
  getPublishedSlates,
  getSubscriptionStatus,
  runOptimize,
  unwrapUser,
  getMe,
} from "../../lib/api";
import { lineupLimitForPlan } from "../../lib/plan-copy";
import {
  EXPOSURE_OPTIONS,
  MLB_STACK_OPTIONS,
  OPTIMIZER_SPORTS,
  STRATEGIES,
  formatSalary,
  formatProjectionSource,
  formatSourceLabel,
  lineupProjectionIntegrity,
  salaryCapFor,
} from "../../lib/optimizer-config";

function fmtPoints(n: number | null | undefined) {
  return n != null && !Number.isNaN(Number(n)) ? Number(n).toFixed(1) : "—";
}

function clamp(n: number, min: number, max: number) {
  return Math.max(min, Math.min(max, n));
}

export default function OptimizerScreen() {
  const insets = useSafeAreaInsets();
  const modalMetrics = initialWindowMetrics ?? {
    frame: { x: 0, y: 0, width: 0, height: 0 },
    insets: {
      top: insets.top,
      left: insets.left,
      right: insets.right,
      bottom: insets.bottom,
    },
  };
  const params = useLocalSearchParams<{ strategy?: string; sport?: string; platform?: string }>();
  const [sport, setSport] = useState("mlb");
  const [platform, setPlatform] = useState<"draftkings" | "fanduel">("draftkings");
  const [strategy, setStrategy] = useState("balanced");
  const [count, setCount] = useState(3);
  const [stackSize, setStackSize] = useState<number | null>(null);
  const [exposure, setExposure] = useState<number | null>(null);
  const [slateId, setSlateId] = useState<number | null>(null);
  const [slates, setSlates] = useState<any[]>([]);
  const [lineups, setLineups] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [progress, setProgress] = useState("");
  const [fetchingSlates, setFetchingSlates] = useState(false);
  const [slateError, setSlateError] = useState<string | null>(null);
  const [selected, setSelected] = useState<any>(null);
  const [dataSource, setDataSource] = useState<string>("");
  const [planLimit, setPlanLimit] = useState(1);

  useEffect(() => {
    const nextSport = String(params.sport || "").toLowerCase();
    if (OPTIMIZER_SPORTS.includes(nextSport as (typeof OPTIMIZER_SPORTS)[number])) setSport(nextSport);
    const nextPlatform = String(params.platform || "").toLowerCase();
    if (nextPlatform === "draftkings" || nextPlatform === "fanduel") setPlatform(nextPlatform);
    const nextStrategy = String(params.strategy || "").toLowerCase();
    if (STRATEGIES.some((item) => item.id === nextStrategy)) setStrategy(nextStrategy);
  }, [params.sport, params.platform, params.strategy]);

  useFocusEffect(
    useCallback(() => {
      let active = true;
      Promise.all([getSubscriptionStatus().catch(() => null), getMe().catch(() => null)]).then(
        ([billingBody, meBody]) => {
          if (!active) return;
          const billing = (billingBody as any)?.data || billingBody;
          const user = unwrapUser(meBody) || (meBody as any)?.data || meBody;
          const hasAccess = billing?.has_access === true || user?.is_pro === true;
          setPlanLimit(lineupLimitForPlan(billing?.plan || user?.plan, hasAccess));
        },
      );
      return () => {
        active = false;
      };
    }, []),
  );

  useEffect(() => {
    setCount((prev) => clamp(prev, 1, Math.max(1, planLimit)));
  }, [planLimit]);

  useEffect(() => {
    setSlates([]);
    setSlateId(null);
    setLineups([]);
    setDataSource("");
    let cancelled = false;
    (async () => {
      setFetchingSlates(true);
      try {
        const items = await getPublishedSlates({ sport, platform });
        if (cancelled) return;
        setSlateError(null);
        setSlates(items);
        const current = items.find((s) => s.is_current) || items[0];
        setSlateId(current?.id ?? null);
      } catch (e) {
        if (cancelled) return;
        setSlates([]);
        setSlateId(null);
        setSlateError(e instanceof Error ? e.message : "Could not load slates");
      } finally {
        if (!cancelled) setFetchingSlates(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [sport, platform]);

  const selectedSlate = useMemo(
    () => slates.find((s) => s.id === slateId) || null,
    [slates, slateId],
  );
  const cap = salaryCapFor(sport, platform);
  const source = formatSourceLabel(
    dataSource || selectedSlate?.data_source,
    selectedSlate?.data_source,
    selectedSlate?.freshness,
  );

  async function handleBuild() {
    if (!slateId || slateId <= 0) {
      Alert.alert("Select a slate", "No live slate is selected for this sport and platform.");
      return;
    }
    const numLineups = clamp(count, 1, planLimit);
    setLoading(true);
    setLineups([]);
    setProgress(`Generating ${numLineups} ${strategy} lineup${numLineups === 1 ? "" : "s"}…`);
    try {
      const settings: Record<string, unknown> = {
        platform,
        strategy,
        num_lineups: numLineups,
        sport,
      };
      if (sport === "mlb" && stackSize != null) settings.stack_size = stackSize;
      if (exposure != null) settings.max_exposure_pct = exposure;
      const result = await runOptimize(slateId, settings);
      const built = Array.isArray(result?.lineups) ? result.lineups : [];
      setLineups(built);
      setDataSource(result?.dfs_source || result?.source || selectedSlate?.data_source || "");
      setProgress(built.length ? `Built ${built.length} lineup${built.length === 1 ? "" : "s"}.` : "No lineups returned.");
    } catch (e: any) {
      setProgress("");
      Alert.alert("Build failed", e.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <View style={s.flex}>
      <ScrollView style={s.scroll} contentContainerStyle={s.container}>
        <View style={s.row}>
          {OPTIMIZER_SPORTS.map((sp) => (
            <TouchableOpacity key={sp} style={[s.chip, sport === sp && s.chipActive]} onPress={() => setSport(sp)}>
              <Text style={sport === sp ? s.chipTextActive : s.chipText}>{sp.toUpperCase()}</Text>
            </TouchableOpacity>
          ))}
        </View>

        <View style={s.row}>
          <TouchableOpacity
            style={[s.chip, platform === "draftkings" && s.chipActive]}
            onPress={() => setPlatform("draftkings")}
          >
            <Text style={platform === "draftkings" ? s.chipTextActive : s.chipText}>DraftKings</Text>
          </TouchableOpacity>
          <TouchableOpacity
            style={[s.chip, platform === "fanduel" && s.chipActive]}
            onPress={() => setPlatform("fanduel")}
          >
            <Text style={platform === "fanduel" ? s.chipTextActive : s.chipText}>FanDuel</Text>
          </TouchableOpacity>
        </View>

        <View style={s.card}>
          <Text style={s.label}>Slate</Text>
          {fetchingSlates ? (
            <ActivityIndicator color="#c9a84c" style={{ marginTop: 8 }} />
          ) : slates.length > 0 ? (
            <ScrollView horizontal showsHorizontalScrollIndicator={false} style={{ marginTop: 4 }}>
              {slates.map((sl: any) => (
                <TouchableOpacity
                  key={sl.id}
                  style={[s.slateChip, slateId === sl.id && s.slateChipActive]}
                  onPress={() => setSlateId(sl.id)}
                >
                  <Text style={slateId === sl.id ? s.slateChipTextActive : s.slateChipText}>
                    {sl.slate_name || `Slate ${sl.id}`}
                  </Text>
                </TouchableOpacity>
              ))}
            </ScrollView>
          ) : (
            <Text style={s.empty}>
              {slateError || `No live slates for this sport and platform.`}
            </Text>
          )}
          {selectedSlate ? (
            <View style={s.context}>
              <Text style={s.contextLine}>
                {selectedSlate.player_count || 0} players · {selectedSlate.game_count || 0} games
                {selectedSlate.freshness ? ` · ${selectedSlate.freshness}` : ""}
              </Text>
              <Text style={s.contextLine}>
                Cap {formatSalary(cap)} · {source.label}
              </Text>
            </View>
          ) : null}
        </View>

        <View style={s.card}>
          <Text style={s.label}>Strategy</Text>
          <View style={s.wrap}>
            {STRATEGIES.map((item) => (
              <TouchableOpacity
                key={item.id}
                style={[s.miniChip, strategy === item.id && s.chipActive]}
                onPress={() => setStrategy(item.id)}
              >
                <Text style={strategy === item.id ? s.chipTextActive : s.chipText}>{item.label}</Text>
              </TouchableOpacity>
            ))}
          </View>
        </View>

        <View style={s.card}>
          <Text style={s.label}>Lineups · {planLimit}/slate on your plan</Text>
          <View style={s.stepper}>
            <TouchableOpacity style={s.stepBtn} onPress={() => setCount((n) => clamp(n - 1, 1, planLimit))}>
              <Text style={s.stepText}>−</Text>
            </TouchableOpacity>
            <Text style={s.countVal}>{clamp(count, 1, planLimit)}</Text>
            <TouchableOpacity style={s.stepBtn} onPress={() => setCount((n) => clamp(n + 1, 1, planLimit))}>
              <Text style={s.stepText}>+</Text>
            </TouchableOpacity>
          </View>
        </View>

        {sport === "mlb" ? (
          <View style={s.card}>
            <Text style={s.label}>MLB stack</Text>
            <View style={s.wrap}>
              <TouchableOpacity
                style={[s.miniChip, stackSize == null && s.chipActive]}
                onPress={() => setStackSize(null)}
              >
                <Text style={stackSize == null ? s.chipTextActive : s.chipText}>Auto</Text>
              </TouchableOpacity>
              {MLB_STACK_OPTIONS.map((item) => (
                <TouchableOpacity
                  key={item.label}
                  style={[s.miniChip, stackSize === item.id && s.chipActive]}
                  onPress={() => setStackSize(item.id)}
                >
                  <Text style={stackSize === item.id ? s.chipTextActive : s.chipText}>{item.label}</Text>
                </TouchableOpacity>
              ))}
            </View>
          </View>
        ) : null}

        <View style={s.card}>
          <Text style={s.label}>Max exposure</Text>
          <View style={s.wrap}>
            <TouchableOpacity
              style={[s.miniChip, exposure == null && s.chipActive]}
              onPress={() => setExposure(null)}
            >
              <Text style={exposure == null ? s.chipTextActive : s.chipText}>Auto</Text>
            </TouchableOpacity>
            {EXPOSURE_OPTIONS.map((item) => (
              <TouchableOpacity
                key={item.label}
                style={[s.miniChip, exposure === item.id && s.chipActive]}
                onPress={() => setExposure(item.id)}
              >
                <Text style={exposure === item.id ? s.chipTextActive : s.chipText}>{item.label}</Text>
              </TouchableOpacity>
            ))}
          </View>
        </View>

        <View style={[s.sourceBadge, source.isDemo && s.demoBadge]}>
          <Text style={[s.sourceText, source.isDemo && s.demoText]}>{source.label}</Text>
        </View>

        <TouchableOpacity style={s.btn} onPress={handleBuild} disabled={loading || fetchingSlates || !slateId}>
          <Text style={s.btnText}>{loading ? "Building…" : "Build lineups"}</Text>
        </TouchableOpacity>

        {loading || progress ? (
          <View style={s.progressCard}>
            {loading ? <ActivityIndicator color="#c9a84c" /> : null}
            <Text style={s.progressText}>{progress}</Text>
          </View>
        ) : null}

        {lineups.map((l, i) => {
          const remaining = cap - Number(l.total_salary || 0);
          return (
            <TouchableOpacity key={i} style={s.lineupCard} onPress={() => setSelected(l)} activeOpacity={0.7}>
              <View style={s.lineupHeader}>
                <Text style={s.lineupNum}>Lineup #{i + 1}</Text>
                <Text style={s.arrow}>›</Text>
              </View>
              <View style={s.lineupStats}>
                <Text style={s.stat}>
                  Proj <Text style={s.statBold}>{fmtPoints(l.projected_score)}</Text>
                </Text>
                <Text style={s.stat}>
                  Sal <Text style={s.statBold}>{formatSalary(l.total_salary)}</Text>
                </Text>
                <Text style={s.stat}>
                  Left <Text style={s.statBold}>{formatSalary(remaining)}</Text>
                </Text>
              </View>
            </TouchableOpacity>
          );
        })}
      </ScrollView>

      <Modal visible={!!selected} animationType="slide" presentationStyle="fullScreen">
        {selected && (
          <SafeAreaProvider initialMetrics={modalMetrics}>
          <SafeAreaView style={s.modal} edges={["top", "bottom"]}>
          <ScrollView style={s.modalScroll} contentContainerStyle={s.modalContent}>
            <View style={s.modalHeader}>
              <Text style={s.modalTitle}>Lineup details</Text>
              <TouchableOpacity onPress={() => setSelected(null)}>
                <Text style={s.closeBtn}>✕ Back</Text>
              </TouchableOpacity>
            </View>
            <View style={s.detailCard}>
              <View style={s.detailRow}>
                <Text style={s.detailLabel}>Sport</Text>
                <Text style={s.detailVal}>{sport.toUpperCase()}</Text>
              </View>
              <View style={s.detailRow}>
                <Text style={s.detailLabel}>Platform</Text>
                <Text style={s.detailVal}>{platform === "draftkings" ? "DraftKings" : "FanDuel"}</Text>
              </View>
              <View style={s.detailRow}>
                <Text style={s.detailLabel}>Strategy</Text>
                <Text style={s.detailVal}>{strategy}</Text>
              </View>
              <View style={s.detailRow}>
                <Text style={s.detailLabel}>Total salary</Text>
                <Text style={s.detailVal}>{formatSalary(selected.total_salary)}</Text>
              </View>
              <View style={s.detailRow}>
                <Text style={s.detailLabel}>Remaining</Text>
                <Text style={s.detailVal}>{formatSalary(cap - Number(selected.total_salary || 0))}</Text>
              </View>
              <View style={s.detailRow}>
                <Text style={s.detailLabel}>Projected</Text>
                <Text style={[s.detailVal, { color: "#c9a84c" }]}>{fmtPoints(selected.projected_score)} pts</Text>
              </View>
              <View style={s.detailRow}>
                <Text style={s.detailLabel}>Players</Text>
                <Text style={s.detailVal}>{selected.players?.length || 0}</Text>
              </View>
              <View style={s.detailRow}>
                <Text style={s.detailLabel}>Data source</Text>
                <Text style={[s.detailVal, { color: source.isDemo ? "#fbbf24" : "#c9a84c", flex: 1, textAlign: "right" }]}>
                  {source.label}
                </Text>
              </View>
            </View>
            {(() => {
              const integrity = lineupProjectionIntegrity(selected);
              const notes = [];
              if (!integrity.totalsMatch) {
                notes.push(
                  `Displayed ${fmtPoints(integrity.displayed)} pts does not match the player sum ${fmtPoints(integrity.playerSum)}.`,
                );
              }
              if (integrity.fallbackCount > 0) {
                notes.push(
                  `${integrity.fallbackCount} player${integrity.fallbackCount === 1 ? "" : "s"} use fallback projections (Blue Collar FPPG or pitcher props), not a live contest feed.`,
                );
              }
              if (integrity.unmatchedCount > 0) {
                notes.push(
                  `${integrity.unmatchedCount} player${integrity.unmatchedCount === 1 ? "" : "s"} are UNMATCHED — slate team/identity is not verified.`,
                );
              }
              notes.push("Unused salary is leftover after maximizing the strategy objective, not a fill target.");
              notes.push("Not contest-ready as a live DraftKings salary or projection feed.");
              return (
                <View style={s.honestyCard}>
                  {notes.map((note) => (
                    <Text key={note} style={s.honestyText}>{note}</Text>
                  ))}
                </View>
              );
            })()}
            {selected.players?.map((p: any, j: number) => (
              <View key={j} style={s.playerCard}>
                <View style={s.playerTop}>
                  <Text style={s.playerPos}>{p.roster_slot || p.assigned_slot || p.roster_position || "?"}</Text>
                  <View style={{ flex: 1 }}>
                    <Text style={s.playerName}>{p.name || `Player ${p.id}`}</Text>
                    <Text style={s.playerTeam}>
                      {p.team || "?"}
                      {String(p.mapping_status || "").toUpperCase() === "UNMATCHED" ? " · UNMATCHED" : ""}
                    </Text>
                  </View>
                  <Text style={s.playerSal}>{formatSalary(p.salary)}</Text>
                </View>
                <View style={s.playerStats}>
                  <Text style={s.pStat}>
                    Proj: <Text style={s.pStatBold}>{fmtPoints(p.projected_fp)}</Text>
                    {" · "}
                    {formatProjectionSource(p.projection_source).label}
                  </Text>
                  {p.fppg != null && Number(p.fppg) > 0 && Number(p.fppg) !== Number(p.projected_fp) ? (
                    <Text style={s.pStat}>
                      BC FPPG: <Text style={s.pStatBold}>{fmtPoints(p.fppg)}</Text>
                    </Text>
                  ) : null}
                  {p.value != null && p.value > 0 ? (
                    <Text style={s.pStat}>
                      Value: <Text style={s.pStatBold}>{Number(p.value).toFixed(1)}</Text>
                    </Text>
                  ) : null}
                  {p.ownership != null && p.ownership > 0 ? (
                    <Text style={s.pStat}>
                      Own: <Text style={s.pStatBold}>{Number(p.ownership).toFixed(1)}%</Text>
                    </Text>
                  ) : (
                    <Text style={s.pStat}>
                      Own: <Text style={s.pStatBold}>N/A</Text>
                    </Text>
                  )}
                </View>
              </View>
            ))}
            {selected.explanation ? (
              <View style={s.explainCard}>
                <Text style={s.explainTitle}>AI explanation</Text>
                <Text style={s.explainText}>{selected.explanation}</Text>
              </View>
            ) : null}
          </ScrollView>
          </SafeAreaView>
          </SafeAreaProvider>
        )}
      </Modal>
    </View>
  );
}

const s = StyleSheet.create({
  flex: { flex: 1, backgroundColor: "#060b1a" },
  scroll: { flex: 1 },
  container: { padding: 20, gap: 16, paddingBottom: 36 },
  row: { flexDirection: "row", gap: 12 },
  wrap: { flexDirection: "row", flexWrap: "wrap", gap: 8 },
  chip: {
    flex: 1,
    padding: 12,
    borderRadius: 12,
    backgroundColor: "#0a0f24",
    borderWidth: 1,
    borderColor: "#1e293b",
    alignItems: "center",
  },
  miniChip: {
    paddingHorizontal: 12,
    paddingVertical: 8,
    borderRadius: 20,
    backgroundColor: "#0a0f24",
    borderWidth: 1,
    borderColor: "#1e293b",
  },
  chipActive: { borderColor: "#c9a84c", backgroundColor: "#c9a84c20" },
  chipText: { color: "#64748b", fontWeight: "600" },
  chipTextActive: { color: "#c9a84c", fontWeight: "700" },
  card: { backgroundColor: "#0a0f24", borderRadius: 16, padding: 16, borderWidth: 1, borderColor: "#1e293b" },
  label: { fontSize: 12, color: "#64748b", textTransform: "uppercase", marginBottom: 8, letterSpacing: 0.6 },
  empty: { color: "#94a3b8", fontSize: 13, marginTop: 4, lineHeight: 18 },
  context: { marginTop: 10, gap: 4 },
  contextLine: { color: "#94a3b8", fontSize: 12 },
  stepper: { flexDirection: "row", alignItems: "center", gap: 16 },
  stepBtn: {
    width: 44,
    height: 44,
    borderRadius: 12,
    backgroundColor: "#111827",
    borderWidth: 1,
    borderColor: "#1e293b",
    alignItems: "center",
    justifyContent: "center",
  },
  stepText: { color: "#c9a84c", fontSize: 22, fontWeight: "700" },
  countVal: { color: "#f0f6fc", fontSize: 22, fontWeight: "800", minWidth: 36, textAlign: "center" },
  btn: { backgroundColor: "#c9a84c", borderRadius: 12, padding: 16, alignItems: "center" },
  btnText: { color: "#060b1a", fontWeight: "700", fontSize: 16 },
  slateChip: {
    paddingHorizontal: 14,
    paddingVertical: 10,
    borderRadius: 20,
    backgroundColor: "#0a0f24",
    borderWidth: 1,
    borderColor: "#1e293b",
    marginRight: 8,
  },
  slateChipActive: { borderColor: "#c9a84c", backgroundColor: "#c9a84c20" },
  slateChipText: { color: "#64748b", fontSize: 12, fontWeight: "600" },
  slateChipTextActive: { color: "#c9a84c" },
  sourceBadge: {
    backgroundColor: "#0a0f24",
    borderRadius: 10,
    padding: 10,
    borderWidth: 1,
    borderColor: "#1e293b",
  },
  sourceText: { color: "#94a3b8", fontSize: 12, textAlign: "center" },
  demoBadge: { backgroundColor: "#332200", borderColor: "#ffaa0040" },
  demoText: { color: "#fbbf24" },
  progressCard: {
    backgroundColor: "#0a0f24",
    borderRadius: 12,
    padding: 12,
    borderWidth: 1,
    borderColor: "#1e293b",
    alignItems: "center",
    gap: 8,
  },
  progressText: { color: "#c9a84c", fontSize: 13, fontWeight: "600" },
  lineupCard: { backgroundColor: "#0a0f24", borderRadius: 16, padding: 16, borderWidth: 1, borderColor: "#1e293b" },
  lineupHeader: { flexDirection: "row", justifyContent: "space-between", alignItems: "center", marginBottom: 10 },
  lineupNum: { fontSize: 16, fontWeight: "700", color: "#c9a84c" },
  arrow: { fontSize: 20, color: "#64748b" },
  lineupStats: { flexDirection: "row", gap: 16 },
  stat: { fontSize: 13, color: "#64748b" },
  statBold: { color: "#f0f6fc", fontWeight: "600" },
  modal: { flex: 1, backgroundColor: "#060b1a" },
  modalScroll: { flex: 1 },
  modalContent: { padding: 20, gap: 16, paddingBottom: 60 },
  modalHeader: { flexDirection: "row", justifyContent: "space-between", alignItems: "center" },
  modalTitle: { fontSize: 22, fontWeight: "900", color: "#c9a84c", fontStyle: "italic" },
  closeBtn: { fontSize: 16, color: "#94a3b8", padding: 8 },
  detailCard: { backgroundColor: "#0a0f24", borderRadius: 16, padding: 16, borderWidth: 1, borderColor: "#1e293b", gap: 8 },
  detailRow: { flexDirection: "row", justifyContent: "space-between", gap: 12 },
  detailLabel: { fontSize: 13, color: "#64748b" },
  detailVal: { fontSize: 14, fontWeight: "600", color: "#f0f6fc" },
  playerCard: { backgroundColor: "#0a0f24", borderRadius: 12, padding: 14, borderWidth: 1, borderColor: "#1e293b" },
  playerTop: { flexDirection: "row", alignItems: "center", gap: 12 },
  playerPos: { fontSize: 13, fontWeight: "700", color: "#c9a84c", width: 28 },
  playerName: { fontSize: 15, fontWeight: "600", color: "#f0f6fc" },
  playerTeam: { fontSize: 12, color: "#64748b", marginTop: 2 },
  playerSal: { fontSize: 14, fontWeight: "600", color: "#c9a84c" },
  playerStats: { flexDirection: "row", flexWrap: "wrap", gap: 12, marginTop: 10, paddingTop: 10, borderTopWidth: 1, borderColor: "#1e293b" },
  pStat: { fontSize: 12, color: "#64748b" },
  pStatBold: { color: "#cbd5e1", fontWeight: "600" },
  honestyCard: { backgroundColor: "#14110a", borderRadius: 12, padding: 12, borderWidth: 1, borderColor: "#c9a84c30", gap: 6 },
  honestyText: { fontSize: 12, color: "#cbd5e1", lineHeight: 18 },
  explainCard: { backgroundColor: "#14110a", borderRadius: 16, padding: 16, borderWidth: 1, borderColor: "#c9a84c30" },
  explainTitle: { fontSize: 12, fontWeight: "700", color: "#c9a84c", textTransform: "uppercase", marginBottom: 8 },
  explainText: { fontSize: 14, color: "#cbd5e1", lineHeight: 22 },
});
