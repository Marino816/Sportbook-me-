import { useEffect, useMemo, useState } from "react";
import {
  ActivityIndicator,
  Alert,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  TouchableOpacity,
  View,
} from "react-native";
import { useRouter } from "expo-router";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { MobileStadiumBackground } from "../../../components/MobileStadiumBackground";
import { useOptimizerSession } from "../../../lib/optimizer-session";
import { getLiveOdds } from "../../../lib/api";
import { formatSalaryFull } from "../../../lib/optimizer-config";
import {
  batsDisplay,
  confirmedBattingOrder,
  displayProjection,
  draftTitle,
  eligiblePositionsLabel,
  extractGameCards,
  hasStarterData,
  isConfirmedStarter,
  opponentRank,
  playerGameTime,
  playerMatchesGame,
  playerMatchupLine,
  probablePitcher,
  salaryFooterStats,
  slotEligible,
  slotLabel,
  sortPlayersBySalary,
} from "../../../lib/optimizer-flow.mjs";

function fmtPoints(n: number | null | undefined) {
  return n != null && !Number.isNaN(Number(n)) ? Number(n).toFixed(1) : "—";
}

function projectionLabel(player: any) {
  const value = displayProjection(player);
  return value == null ? "—" : `${fmtPoints(value)} pts`;
}

export default function OptimizerPlayersScreen() {
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const session = useOptimizerSession();
  const [query, setQuery] = useState("");
  const [game, setGame] = useState("ALL");
  const [salaryDir, setSalaryDir] = useState<"high" | "low">("high");
  const [startersOnly, setStartersOnly] = useState(false);
  const [oddsGames, setOddsGames] = useState<any[]>([]);

  const slot = session.roster?.slots[session.selectingSlotIndex] || "";
  const slotName = slotLabel(slot, session.roster);
  const title = draftTitle(slot, session.roster);
  const sport = String(session.sport || "").toLowerCase();
  const slateStart = session.selectedSlate?.start_time || session.selectedSlate?.slate_date || null;
  const footer = salaryFooterStats({ slots: session.slots, cap: session.cap, roster: session.roster });

  const eligible = useMemo(() => {
    if (!session.roster) return [];
    return session.players.filter((player) =>
      slotEligible(
        Array.isArray(player.eligible_positions)
          ? player.eligible_positions.join("/")
          : player.eligible_positions || player.position,
        slot,
        session.roster!,
      ),
    );
  }, [session.players, session.roster, slot]);

  const starterFilterAvailable = useMemo(() => sport === "mlb" && hasStarterData(eligible), [eligible, sport]);

  const games = useMemo(
    () => extractGameCards(eligible, { slateStart, oddsGames }),
    [eligible, slateStart, oddsGames],
  );

  const visible = useMemo(() => {
    const q = query.trim().toLowerCase();
    const filtered = eligible.filter((player) => {
      if (!playerMatchesGame(player, game)) return false;
      if (startersOnly && starterFilterAvailable && !isConfirmedStarter(player)) return false;
      if (!q) return true;
      return `${player.name} ${player.team} ${player.opponent || ""}`.toLowerCase().includes(q);
    });
    return sortPlayersBySalary(filtered, salaryDir);
  }, [eligible, game, query, salaryDir, starterFilterAvailable, startersOnly]);

  const poolPending =
    session.fetchingSlates ||
    session.fetchingPlayers ||
    (session.slateId != null && session.players.length === 0 && !session.playersError);

  useEffect(() => {
    let cancelled = false;
    getLiveOdds(String(session.sport || "MLB").toUpperCase())
      .then((payload) => {
        if (cancelled) return;
        const list = Array.isArray(payload?.games) ? payload.games : [];
        setOddsGames(list);
      })
      .catch(() => {
        if (!cancelled) setOddsGames([]);
      });
    return () => {
      cancelled = true;
    };
  }, [session.sport]);

  function pick(player: any) {
    const result = session.assignPlayer(player);
    if (!result.ok) {
      Alert.alert("Can't add player", result.reason || "Choose a lower-salary replacement.");
      return;
    }
    router.back();
  }

  return (
    <MobileStadiumBackground>
      <View style={[styles.top, { paddingTop: 8 }]}>
        <View style={{ flex: 1, minWidth: 0 }}>
          <Text style={styles.title}>{title}</Text>
          <TextInput
            value={query}
            onChangeText={setQuery}
            placeholder="Search All Players"
            placeholderTextColor="#64748b"
            style={styles.search}
          />
        </View>
        <TouchableOpacity onPress={() => router.back()} style={styles.closeBtn} accessibilityLabel="Close">
          <Text style={styles.closeX}>X</Text>
        </TouchableOpacity>
      </View>

      <ScrollView
        horizontal
        showsHorizontalScrollIndicator={false}
        style={styles.gamesStrip}
        contentContainerStyle={styles.games}
      >
        <TouchableOpacity style={[styles.game, game === "ALL" && styles.gameOn]} onPress={() => setGame("ALL")}>
          <Text style={game === "ALL" ? styles.gameTextOn : styles.gameText}>All Games</Text>
        </TouchableOpacity>
        {games.map((item) => (
          <TouchableOpacity
            key={item.id}
            style={[styles.game, game === item.id && styles.gameOn]}
            onPress={() => setGame(item.id)}
          >
            <Text style={game === item.id ? styles.gameTextOn : styles.gameText} numberOfLines={1}>
              {item.matchup}
            </Text>
            {item.date || item.time ? (
              <Text style={styles.gameMeta} numberOfLines={1}>
                {[item.date, item.time].filter(Boolean).join(" · ")}
              </Text>
            ) : null}
            {item.weather ? (
              <Text style={styles.gameMeta} numberOfLines={1}>{item.weather}</Text>
            ) : null}
            {item.moneyline || item.spread || item.total ? (
              <Text style={styles.gameOdds} numberOfLines={2}>
                {[item.moneyline, item.spread, item.total].filter(Boolean).join(" · ")}
              </Text>
            ) : null}
          </TouchableOpacity>
        ))}
      </ScrollView>

      <View style={styles.sortRow}>
        <TouchableOpacity onPress={() => setSalaryDir((d) => (d === "high" ? "low" : "high"))}>
          <Text style={styles.sort}>{salaryDir === "high" ? "Salary High → Low" : "Salary Low → High"}</Text>
        </TouchableOpacity>
        {starterFilterAvailable ? (
          <TouchableOpacity onPress={() => setStartersOnly((v) => !v)}>
            <Text style={[styles.sort, startersOnly && styles.sortOn]}>Confirmed Starters Only</Text>
          </TouchableOpacity>
        ) : null}
      </View>

      <ScrollView style={styles.list} contentContainerStyle={{ paddingBottom: 8 }}>
        {poolPending ? (
          <ActivityIndicator color="#c9a84c" style={{ marginTop: 20 }} />
        ) : null}
        {!poolPending
          ? visible.map((player) => {
              const order = sport === "mlb" ? confirmedBattingOrder(player) : null;
              const bats = sport === "mlb" ? batsDisplay(player) : "";
              const pitcher = sport === "mlb" ? probablePitcher(player) : "";
              const rank = sport === "nfl" ? opponentRank(player) : null;
              const matchup = playerMatchupLine(player);
              const time = playerGameTime(player, slateStart);
              return (
                <TouchableOpacity
                  key={`${player.player_id || player.name}`}
                  style={styles.player}
                  onPress={() => pick(player)}
                >
                  <View style={{ flex: 1, minWidth: 0 }}>
                    <View style={styles.playerTop}>
                      <Text style={styles.pos}>{eligiblePositionsLabel(player) || slotName}</Text>
                      <Text style={styles.name} numberOfLines={1}>{player.name}</Text>
                      {order != null ? <Text style={styles.order}>{order} ✓</Text> : null}
                    </View>
                    <Text style={styles.meta} numberOfLines={2}>
                      {sport === "mlb"
                        ? [
                            player.team && player.opponent ? `${player.team}/${player.opponent}` : player.team,
                            time,
                            pitcher ? `vs ${pitcher}` : "",
                            bats ? `Bats ${bats}` : "",
                          ].filter(Boolean).join(" · ")
                        : [
                            player.team || "?",
                            matchup,
                            time,
                            rank != null ? `Opp #${rank}` : "",
                          ].filter(Boolean).join(" · ")}
                    </Text>
                  </View>
                  <View style={styles.playerRight}>
                    <Text style={styles.sal}>{formatSalaryFull(player.salary)}</Text>
                    <Text style={styles.proj}>{projectionLabel(player)}</Text>
                  </View>
                  <TouchableOpacity
                    style={styles.addBtn}
                    onPress={() => pick(player)}
                    accessibilityRole="button"
                    accessibilityLabel={`Add ${player.name}`}
                    hitSlop={{ top: 6, bottom: 6, left: 6, right: 6 }}
                  >
                    <Text style={styles.add}>+</Text>
                  </TouchableOpacity>
                </TouchableOpacity>
              );
            })
          : null}
        {poolPending ? null : session.playersError ? (
          <Text style={styles.empty}>{session.playersError}</Text>
        ) : !session.slateId ? (
          <Text style={styles.empty}>No slate selected. Go back and choose a live slate.</Text>
        ) : visible.length === 0 ? (
          <Text style={styles.empty}>No eligible players for this slot on the current slate.</Text>
        ) : null}
      </ScrollView>

      <View style={[styles.footer, { paddingBottom: Math.max(8, insets.bottom) }]}>
        <View style={styles.footCol}>
          <Text style={styles.footLabel}>Positions Filled {footer.filled}/{footer.total}</Text>
          <Text style={styles.footVal}>Remaining Salary {formatSalaryFull(footer.remaining)}</Text>
        </View>
        <View style={[styles.footCol, { alignItems: "flex-end" }]}>
          <Text style={footer.underCap ? styles.footOk : styles.footWarn}>
            {footer.underCap ? "Under Salary Cap" : "Over Salary Cap"}
          </Text>
          <Text style={styles.footLabel}>Avg Remaining/Player {formatSalaryFull(footer.avgRemaining)}</Text>
        </View>
      </View>
    </MobileStadiumBackground>
  );
}

const styles = StyleSheet.create({
  top: { flexDirection: "row", alignItems: "flex-start", gap: 8, paddingHorizontal: 16, paddingBottom: 8 },
  title: { color: "#c9a84c", fontWeight: "800", fontSize: 20, marginBottom: 8 },
  search: {
    backgroundColor: "rgba(10,15,36,0.88)",
    borderRadius: 12,
    borderWidth: 1,
    borderColor: "#1e293b",
    color: "#f0f6fc",
    paddingHorizontal: 12,
    paddingVertical: 10,
  },
  closeBtn: { padding: 8, marginTop: 4 },
  closeX: { color: "#f0f6fc", fontSize: 20, fontWeight: "800" },
  gamesStrip: { flexGrow: 0, flexShrink: 0, maxHeight: 108 },
  games: { paddingHorizontal: 16, gap: 8, paddingBottom: 8, alignItems: "stretch" },
  game: {
    width: 168,
    minHeight: 72,
    paddingVertical: 8,
    paddingHorizontal: 10,
    borderRadius: 12,
    backgroundColor: "rgba(10,15,36,0.82)",
    borderWidth: 1,
    borderColor: "#1e293b",
    marginRight: 8,
    justifyContent: "center",
  },
  gameOn: { borderColor: "#c9a84c", backgroundColor: "rgba(201,168,76,0.16)" },
  gameText: { color: "#94a3b8", fontSize: 13, fontWeight: "700" },
  gameTextOn: { color: "#c9a84c", fontSize: 13, fontWeight: "800" },
  gameMeta: { color: "#64748b", fontSize: 11, marginTop: 3 },
  gameOdds: { color: "#94a3b8", fontSize: 10, marginTop: 4, lineHeight: 13 },
  sortRow: {
    paddingHorizontal: 16,
    paddingBottom: 6,
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
  },
  sort: { color: "#c9a84c", fontSize: 12, fontWeight: "700" },
  sortOn: { textDecorationLine: "underline" },
  list: { flex: 1, paddingHorizontal: 16 },
  player: {
    flexDirection: "row",
    alignItems: "center",
    paddingVertical: 10,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: "#1e293b",
    gap: 8,
  },
  playerTop: { flexDirection: "row", alignItems: "center", gap: 6, minWidth: 0 },
  pos: { color: "#c9a84c", fontSize: 11, fontWeight: "800", minWidth: 28 },
  name: { color: "#f0f6fc", fontWeight: "600", flex: 1, minWidth: 0 },
  order: { color: "#86efac", fontSize: 12, fontWeight: "800" },
  meta: { color: "#64748b", fontSize: 12, marginTop: 2 },
  playerRight: { alignItems: "flex-end", flexShrink: 0 },
  sal: { color: "#c9a84c", fontWeight: "700" },
  proj: { color: "#94a3b8", fontSize: 12, marginTop: 2 },
  addBtn: {
    width: 36,
    height: 36,
    borderRadius: 18,
    borderWidth: 1,
    borderColor: "#c9a84c",
    alignItems: "center",
    justifyContent: "center",
    flexShrink: 0,
  },
  add: { color: "#c9a84c", fontSize: 22, fontWeight: "700", marginTop: -1 },
  empty: { color: "#94a3b8", textAlign: "center", marginTop: 24 },
  footer: {
    flexDirection: "row",
    justifyContent: "space-between",
    paddingHorizontal: 16,
    paddingTop: 8,
    backgroundColor: "rgba(6,11,26,0.88)",
    borderTopWidth: 1,
    borderTopColor: "#1e293b",
    gap: 12,
  },
  footCol: { flex: 1, minWidth: 0 },
  footLabel: { color: "#64748b", fontSize: 11 },
  footVal: { color: "#f0f6fc", fontWeight: "700", fontSize: 13, marginTop: 2 },
  footOk: { color: "#86efac", fontWeight: "700", fontSize: 12 },
  footWarn: { color: "#fca5a5", fontWeight: "700", fontSize: 12 },
});
