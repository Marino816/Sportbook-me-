import { useMemo, useState } from "react";
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
import { formatSalary } from "../../../lib/optimizer-config";
import {
  averageRemainingPerPlayer,
  displayProjection,
  extractGames,
  playerMatchesGame,
  remainingSalary,
  slotEligible,
  slotLabel,
  sortPlayersBySalary,
} from "../../../lib/optimizer-flow.mjs";

function fmtPoints(n: number | null | undefined) {
  return n != null && !Number.isNaN(Number(n)) ? Number(n).toFixed(1) : "—";
}

export default function OptimizerPlayersScreen() {
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const session = useOptimizerSession();
  const [query, setQuery] = useState("");
  const [game, setGame] = useState("ALL");
  const [salaryDir, setSalaryDir] = useState<"high" | "low">("high");

  const slot = session.roster?.slots[session.selectingSlotIndex] || "";
  const slotName = slotLabel(slot, session.roster);
  const games = useMemo(() => extractGames(session.players), [session.players]);
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

  const visible = useMemo(() => {
    const q = query.trim().toLowerCase();
    const filtered = eligible.filter((player) => {
      if (!playerMatchesGame(player, game)) return false;
      if (!q) return true;
      return `${player.name} ${player.team}`.toLowerCase().includes(q);
    });
    return sortPlayersBySalary(filtered, salaryDir);
  }, [eligible, game, query, salaryDir]);

  const remainingSlots = (session.slots || []).filter((item) => !item).length;
  const avg = averageRemainingPerPlayer(remainingSalary(session.cap, session.slots), remainingSlots);
  const poolPending =
    session.fetchingSlates ||
    session.fetchingPlayers ||
    (session.slateId != null && session.players.length === 0 && !session.playersError);

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
        <TextInput
          value={query}
          onChangeText={setQuery}
          placeholder="Search players"
          placeholderTextColor="#64748b"
          style={styles.search}
        />
        <TouchableOpacity onPress={() => router.back()} style={styles.closeBtn}>
          <Text style={styles.closeX}>X</Text>
        </TouchableOpacity>
      </View>

      <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.games}>
        <TouchableOpacity style={[styles.game, game === "ALL" && styles.gameOn]} onPress={() => setGame("ALL")}>
          <Text style={game === "ALL" ? styles.gameTextOn : styles.gameText}>All Games</Text>
        </TouchableOpacity>
        {games.map((item) => (
          <TouchableOpacity key={item} style={[styles.game, game === item && styles.gameOn]} onPress={() => setGame(item)}>
            <Text style={game === item ? styles.gameTextOn : styles.gameText}>{item}</Text>
          </TouchableOpacity>
        ))}
      </ScrollView>

      <View style={styles.sortRow}>
        <TouchableOpacity onPress={() => setSalaryDir((d) => (d === "high" ? "low" : "high"))}>
          <Text style={styles.sort}>{salaryDir === "high" ? "Salary high → low" : "Salary low → high"}</Text>
        </TouchableOpacity>
      </View>

      <ScrollView style={styles.list} contentContainerStyle={{ paddingBottom: 8 }}>
        {poolPending ? (
          <ActivityIndicator color="#c9a84c" style={{ marginTop: 20 }} />
        ) : null}
        {!poolPending
          ? visible.map((player) => (
              <TouchableOpacity key={`${player.player_id || player.name}`} style={styles.player} onPress={() => pick(player)}>
                <View style={{ flex: 1 }}>
                  <Text style={styles.name}>{player.name}</Text>
                  <Text style={styles.meta}>
                    {player.team || "?"} · {player.position || slotName}
                  </Text>
                </View>
                <View style={{ alignItems: "flex-end" }}>
                  <Text style={styles.sal}>{formatSalary(player.salary)}</Text>
                  <Text style={styles.proj}>{fmtPoints(displayProjection(player))} pts</Text>
                </View>
              </TouchableOpacity>
            ))
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
        <View>
          <Text style={styles.footLabel}>{slotName}</Text>
          <Text style={styles.footVal}>Cap {formatSalary(session.cap)}</Text>
        </View>
        <View style={{ alignItems: "flex-end" }}>
          <Text style={styles.footVal}>{formatSalary(session.remaining)} left</Text>
          <Text style={styles.footLabel}>{formatSalary(avg)} / player</Text>
        </View>
      </View>
    </MobileStadiumBackground>
  );
}

const styles = StyleSheet.create({
  top: { flexDirection: "row", alignItems: "center", gap: 8, paddingHorizontal: 16, paddingBottom: 8 },
  search: {
    flex: 1,
    backgroundColor: "rgba(10,15,36,0.88)",
    borderRadius: 12,
    borderWidth: 1,
    borderColor: "#1e293b",
    color: "#f0f6fc",
    paddingHorizontal: 12,
    paddingVertical: 10,
  },
  closeBtn: { padding: 8 },
  closeX: { color: "#f0f6fc", fontSize: 20, fontWeight: "800" },
  games: { paddingHorizontal: 16, gap: 8, paddingBottom: 8 },
  game: {
    width: 112,
    paddingVertical: 10,
    borderRadius: 12,
    backgroundColor: "rgba(10,15,36,0.82)",
    borderWidth: 1,
    borderColor: "#1e293b",
    alignItems: "center",
    marginRight: 8,
  },
  gameOn: { borderColor: "#c9a84c", backgroundColor: "rgba(201,168,76,0.16)" },
  gameText: { color: "#94a3b8", fontSize: 12, fontWeight: "600" },
  gameTextOn: { color: "#c9a84c", fontSize: 12, fontWeight: "700" },
  sortRow: { paddingHorizontal: 16, paddingBottom: 6 },
  sort: { color: "#c9a84c", fontSize: 12, fontWeight: "700" },
  list: { flex: 1, paddingHorizontal: 16 },
  player: {
    flexDirection: "row",
    alignItems: "center",
    paddingVertical: 10,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: "#1e293b",
  },
  name: { color: "#f0f6fc", fontWeight: "600" },
  meta: { color: "#64748b", fontSize: 12, marginTop: 2 },
  sal: { color: "#c9a84c", fontWeight: "700" },
  proj: { color: "#94a3b8", fontSize: 12, marginTop: 2 },
  empty: { color: "#94a3b8", textAlign: "center", marginTop: 24 },
  footer: {
    flexDirection: "row",
    justifyContent: "space-between",
    paddingHorizontal: 16,
    paddingTop: 8,
    backgroundColor: "rgba(6,11,26,0.88)",
    borderTopWidth: 1,
    borderTopColor: "#1e293b",
  },
  footLabel: { color: "#64748b", fontSize: 11 },
  footVal: { color: "#f0f6fc", fontWeight: "700", fontSize: 13 },
});
