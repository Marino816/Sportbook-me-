import { useState, useEffect, useCallback } from "react";
import {
  View, Text, StyleSheet, ScrollView, TouchableOpacity,
  ActivityIndicator, RefreshControl, TextInput,
} from "react-native";
import { useRouter, useFocusEffect } from "expo-router";
import { Ionicons } from "@expo/vector-icons";
import { getToken } from "../../../lib/api";

const API_URL = "https://sportbook-me-production.up.railway.app/api";

interface Game {
  game_id: string;
  home_team_name: string;
  away_team_name: string;
  start_time?: string;
  status?: string;
  total_line?: number | null;
  spread_line?: number | null;
  moneyline_home?: number | null;
  moneyline_away?: number | null;
  odds?: any[];
  slate_name?: string;
}

interface LiveOddsData {
  slates?: any[];
  games?: Game[];
  count?: number;
}

const MOVE_COLORS: Record<string, string> = {
  LINE_MOVE: "#fbbf24",
  STEAM_MOVE: "#f97316",
  REVERSAL: "#ef4444",
};

const MOVE_LABELS: Record<string, string> = {
  LINE_MOVE: "Line Move",
  STEAM_MOVE: "Steam",
  REVERSAL: "Reversal",
};

export default function LiveOddsScreen() {
  const router = useRouter();
  const [data, setData] = useState<LiveOddsData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [league, setLeague] = useState("MLB");
  const [search, setSearch] = useState("");

  const load = async () => {
    setLoading(true);
    setError(null);
    try {
      const token = await getToken();
      const res = await fetch(`${API_URL}/market-tools/live-odds?league=${encodeURIComponent(league)}`, {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const json = await res.json();
      setData(json.data || json);
    } catch (e: any) {
      setError(e.message);
      setData(null);
    } finally {
      setLoading(false);
    }
  };

  useFocusEffect(useCallback(() => { load(); }, [league]));

  const games = (data?.games || []).filter((g) => {
    if (!search) return true;
    const q = search.toLowerCase();
    return (
      g.home_team_name?.toLowerCase().includes(q) ||
      g.away_team_name?.toLowerCase().includes(q)
    );
  });

  const getMovementColor = (game: Game): string | null => {
    const odds = game.odds || [];
    for (const o of odds) {
      const moves = o?.movements || o?.alerts || [];
      for (const m of moves) {
        const key = m?.type || m?.alert || "";
        if (MOVE_COLORS[key]) return MOVE_COLORS[key];
      }
    }
    return null;
  };

  const getMovementLabel = (game: Game): string | null => {
    const odds = game.odds || [];
    for (const o of odds) {
      const moves = o?.movements || o?.alerts || [];
      for (const m of moves) {
        const key = m?.type || m?.alert || "";
        if (MOVE_LABELS[key]) return MOVE_LABELS[key];
      }
    }
    return null;
  };

  const formatOdds = (val: number | null | undefined): string => {
    if (val == null) return "—";
    return val > 0 ? `+${val}` : `${val}`;
  };

  const isLive = (game: Game) => game.status === "IN_PLAY" || game.status === "LIVE";

  if (loading) {
    return (
      <View style={s.center}>
        <ActivityIndicator size="large" color="#c9a84c" />
      </View>
    );
  }

  if (error) {
    return (
      <View style={s.center}>
        <Text style={s.errorText}>{error}</Text>
        <TouchableOpacity onPress={load} style={s.retryBtn}>
          <Text style={s.retryText}>Retry</Text>
        </TouchableOpacity>
      </View>
    );
  }

  return (
    <ScrollView
      style={s.container}
      refreshControl={<RefreshControl refreshing={loading} onRefresh={load} tintColor="#c9a84c" />}
    >
      {/* League selector — nested SGO events, not DFS slate IDs */}
      <View style={s.filterRow}>
        {["MLB", "NFL", "NBA", "NHL", "NCAAF", "NCAAB", "WNBA", "UFC", "EPL", "MLS", "LA_LIGA", "BUNDESLIGA", "FR_LIGUE_1", "IT_SERIE_A", "UEFA_CHAMPIONS_LEAGUE", "INTERNATIONAL_SOCCER", "EHF_EURO"].map((lg) => (
          <TouchableOpacity
            key={lg}
            style={[s.slateBtn, league === lg && s.slateBtnActive]}
            onPress={() => setLeague(lg)}
          >
            <Text style={[s.slateBtnText, league === lg && s.slateBtnTextActive]}>{lg}</Text>
          </TouchableOpacity>
        ))}
      </View>

      {/* Search */}
      <TextInput
        style={s.searchInput}
        placeholder="Search teams..."
        placeholderTextColor="#64748b"
        value={search}
        onChangeText={setSearch}
      />

      {/* Game count */}
      <Text style={s.countText}>
        {games.length} game{games.length !== 1 ? "s" : ""}
        {data?.count != null ? ` of ${data.count}` : ""}
      </Text>

      {/* Game cards */}
      {games.map((game, i) => {
        const moveColor = getMovementColor(game);
        const moveLabel = getMovementLabel(game);

        return (
          <View key={game.game_id || i} style={s.gameCard}>
            {/* Header */}
            <View style={s.gameHeader}>
              <View style={{ flex: 1 }}>
                <Text style={s.gameTitle}>
                  {game.away_team_name || "Away"} @ {game.home_team_name || "Home"}
                </Text>
                <View style={s.gameMeta}>
                  {isLive(game) && (
                    <View style={s.liveBadge}>
                      <View style={s.liveDot} />
                      <Text style={s.liveText}>LIVE</Text>
                    </View>
                  )}
                  {game.start_time && (
                    <Text style={s.gameTime}>{game.start_time}</Text>
                  )}
                </View>
              </View>
              {moveColor && moveLabel && (
                <View style={[s.moveBadge, { backgroundColor: moveColor + "22", borderColor: moveColor }]}>
                  <Text style={[s.moveText, { color: moveColor }]}>{moveLabel}</Text>
                </View>
              )}
            </View>

            {/* Odds row */}
            <View style={s.oddsRow}>
              <View style={s.oddsCell}>
                <Text style={s.oddsLabel}>Moneyline</Text>
                <Text style={s.oddsVal}>
                  {formatOdds(game.moneyline_away)} / {formatOdds(game.moneyline_home)}
                </Text>
              </View>
              <View style={[s.oddsCell, s.oddsCellBorder]}>
                <Text style={s.oddsLabel}>Spread</Text>
                <Text style={s.oddsVal}>
                  {game.spread_line != null
                    ? `${game.spread_line > 0 ? "+" : ""}${game.spread_line}`
                    : "—"}
                </Text>
              </View>
              <View style={s.oddsCell}>
                <Text style={s.oddsLabel}>Total</Text>
                <Text style={s.oddsVal}>
                  {game.total_line != null ? `O/U ${game.total_line}` : "—"}
                </Text>
              </View>
            </View>

            {/* Bookmaker odds */}
            {game.odds && game.odds.length > 0 && (
              <View style={s.booksRow}>
                {game.odds.slice(0, 4).map((book: any, bi: number) => (
                  <View key={bi} style={s.bookChip}>
                    <Text style={s.bookName} numberOfLines={1}>
                      {book.bookmaker_name || book.sportsbook || `Book ${bi + 1}`}
                    </Text>
                    <Text style={s.bookOdds}>
                      {formatOdds(book.moneyline_home)} / {formatOdds(book.moneyline_away)}
                    </Text>
                  </View>
                ))}
              </View>
            )}
          </View>
        );
      })}

      {games.length === 0 && (
        <Text style={s.emptyText}>No games available for this league.</Text>
      )}
    </ScrollView>
  );
}

const s = StyleSheet.create({
  container: { flex: 1, backgroundColor: "#060b1a", padding: 16 },
  center: {
    flex: 1, backgroundColor: "#060b1a",
    justifyContent: "center", alignItems: "center",
  },
  filterRow: {
    flexDirection: "row", gap: 8, marginBottom: 12,
  },
  slateBtn: {
    paddingVertical: 8, paddingHorizontal: 16,
    borderRadius: 10, backgroundColor: "#0a0f24",
    borderWidth: 1, borderColor: "#1e293b",
  },
  slateBtnActive: {
    borderColor: "#c9a84c",
    backgroundColor: "rgba(201,168,76,0.1)",
  },
  slateBtnText: { fontSize: 13, fontWeight: "600", color: "#94a3b8" },
  slateBtnTextActive: { color: "#c9a84c" },
  searchInput: {
    backgroundColor: "#0a0f24", borderRadius: 12,
    borderWidth: 1, borderColor: "#1e293b",
    paddingHorizontal: 14, paddingVertical: 10,
    fontSize: 14, color: "#f0f6fc", marginBottom: 10,
  },
  countText: {
    fontSize: 12, color: "#64748b", marginBottom: 10,
  },
  gameCard: {
    backgroundColor: "#0a0f24", borderRadius: 12,
    borderWidth: 1, borderColor: "#1e293b",
    padding: 14, marginBottom: 10,
  },
  gameHeader: { flexDirection: "row", alignItems: "flex-start", marginBottom: 10 },
  gameTitle: { fontSize: 15, fontWeight: "700", color: "#f0f6fc", flex: 1 },
  gameMeta: { flexDirection: "row", alignItems: "center", marginTop: 4, gap: 8 },
  liveBadge: { flexDirection: "row", alignItems: "center", gap: 4 },
  liveDot: {
    width: 6, height: 6, borderRadius: 3,
    backgroundColor: "#ef4444",
  },
  liveText: { fontSize: 10, fontWeight: "700", color: "#ef4444", textTransform: "uppercase" },
  gameTime: { fontSize: 11, color: "#64748b" },
  moveBadge: {
    paddingHorizontal: 8, paddingVertical: 3,
    borderRadius: 6, borderWidth: 1,
  },
  moveText: { fontSize: 10, fontWeight: "700" },
  oddsRow: {
    flexDirection: "row", marginBottom: 10,
    backgroundColor: "rgba(201,168,76,0.05)",
    borderRadius: 8, padding: 8,
  },
  oddsCell: { flex: 1, alignItems: "center" },
  oddsCellBorder: {
    borderLeftWidth: 1, borderRightWidth: 1,
    borderColor: "#1e293b",
  },
  oddsLabel: { fontSize: 10, color: "#64748b", textTransform: "uppercase", marginBottom: 3 },
  oddsVal: { fontSize: 14, fontWeight: "700", color: "#c9a84c" },
  booksRow: {
    flexDirection: "row", flexWrap: "wrap", gap: 6,
  },
  bookChip: {
    backgroundColor: "#1a1f33", borderRadius: 8,
    paddingHorizontal: 10, paddingVertical: 6,
    minWidth: 80, alignItems: "center",
  },
  bookName: { fontSize: 9, fontWeight: "600", color: "#94a3b8", maxWidth: 80 },
  bookOdds: { fontSize: 11, fontWeight: "700", color: "#c9a84c", marginTop: 2 },
  emptyText: {
    color: "#666", textAlign: "center", marginTop: 40, fontSize: 14,
  },
  errorText: { color: "#ef4444", fontSize: 16, textAlign: "center" },
  retryBtn: {
    marginTop: 16, backgroundColor: "#c9a84c22",
    paddingHorizontal: 24, paddingVertical: 10, borderRadius: 8,
  },
  retryText: { color: "#c9a84c", fontWeight: "600" },
});