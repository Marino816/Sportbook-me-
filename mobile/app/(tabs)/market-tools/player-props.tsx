import { useState, useEffect, useCallback } from "react";
import {
  View, Text, StyleSheet, ScrollView, TouchableOpacity,
  ActivityIndicator, RefreshControl, TextInput,
} from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { getToken, getApiUrl } from "../../../lib/api";

const API_URL = getApiUrl();

export default function PlayerPropsScreen() {
  const [players, setPlayers] = useState<any[]>([]);
  const [selectedPlayer, setSelectedPlayer] = useState<any>(null);
  const [props, setProps] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [propsLoading, setPropsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState("");

  const loadPlayers = async () => {
    setLoading(true);
    try {
      const token = await getToken();
      const res = await fetch(`${API_URL}/sgo/events?league=MLB`, {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const json = await res.json();
      const events = json.data?.events || json.events || json.data || [];
      const ps: any[] = [];
      for (const evt of Array.isArray(events) ? events : []) {
        for (const p of evt.players || []) {
          ps.push({
            ...p,
            player_id: p.player_id || p.id,
            player_name: p.name || p.player_name,
            event_id: evt.id,
          });
        }
      }
      setPlayers(ps);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  const loadProps = async (player: any) => {
    setSelectedPlayer(player);
    setPropsLoading(true);
    try {
      const token = await getToken();
      const pid = player.player_id || player.id;
      const res = await fetch(`${API_URL}/market-tools/player-props?player_id=${encodeURIComponent(pid)}&sport=MLB`, {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const json = await res.json();
      const pr = json.data?.props || json.props || json.data || [];
      setProps(Array.isArray(pr) ? pr : []);
    } catch (e: any) {
      setProps([]);
    } finally {
      setPropsLoading(false);
    }
  };

  useEffect(() => { loadPlayers(); }, []);

  const filteredPlayers = players.filter((p) => {
    if (!search) return true;
    const q = search.toLowerCase();
    return (p.player_name || p.name || "").toLowerCase().includes(q);
  });

  const getBestOver = (prop: any): string => {
    const books = prop?.bookmakers || prop?.books || prop?.odds || [];
    if (!books.length) return "—";
    let best = books[0];
    for (const b of books) {
      if ((b.over_price || b.price || 0) > (best.over_price || best.price || 0)) best = b;
    }
    return `${best.bookmaker_name || "Book"} ${best.over_price || best.price || "—"}`;
  };

  const getLineRange = (prop: any): string => {
    const books = prop?.bookmakers || prop?.books || prop?.odds || [];
    if (!books.length) return "—";
    let min = Infinity, max = -Infinity;
    for (const b of books) {
      const l = b.line || b.points || 0;
      if (l < min) min = l;
      if (l > max) max = l;
    }
    return min === max ? `${min}` : `${min} – ${max}`;
  };

  const formatOdds = (v: number | null | undefined) => {
    if (v == null) return "—";
    return v > 0 ? `+${v}` : `${v}`;
  };

  return (
    <ScrollView
      style={s.container}
      refreshControl={<RefreshControl refreshing={loading} onRefresh={loadPlayers} tintColor="#c9a84c" />}
    >
      {/* Player search */}
      <Text style={s.sectionLabel}>Find Player</Text>
      <TextInput
        style={s.searchInput}
        placeholder="Search player name..."
        placeholderTextColor="#64748b"
        value={search}
        onChangeText={setSearch}
      />

      <ScrollView horizontal showsHorizontalScrollIndicator={false} style={{ marginBottom: 16 }}>
        <View style={{ flexDirection: "row", gap: 8 }}>
          {filteredPlayers.slice(0, 30).map((p, i) => {
            const isSelected = (p.player_id || p.id) === (selectedPlayer?.player_id || selectedPlayer?.id);
            return (
              <TouchableOpacity
                key={i}
                style={[s.playerChip, isSelected && s.playerChipActive]}
                onPress={() => loadProps(p)}
              >
                <Text style={[s.playerChipText, isSelected && s.playerChipTextActive]}>
                  {p.player_name || p.name || `#${p.player_id || p.id}`}
                </Text>
                <Text style={s.playerChipMeta}>
                  {p.position || ""} · {p.dfs_salary ? `$${p.dfs_salary}` : ""}
                </Text>
              </TouchableOpacity>
            );
          })}
        </View>
      </ScrollView>

      {/* DFS projection info */}
      {selectedPlayer && (
        <View style={s.projectionCard}>
          <Ionicons name="analytics" size={20} color="#c9a84c" />
          <View style={{ marginLeft: 10, flex: 1 }}>
            <Text style={s.projLabel}>DFS Projection</Text>
            <Text style={s.projValue}>
              {selectedPlayer.base_projection || selectedPlayer.projected_fp || "—"} pts
              {selectedPlayer.fantasy_market_line != null && (
                <Text style={s.projEdge}>
                  {" "}· Market: {selectedPlayer.fantasy_market_line}
                  {selectedPlayer.fantasy_market_edge != null && (
                    <Text style={{ color: selectedPlayer.fantasy_market_edge > 0 ? "#c9a84c" : "#ef4444" }}>
                      {" "}(Edge: {selectedPlayer.fantasy_market_edge > 0 ? "+" : ""}{selectedPlayer.fantasy_market_edge})
                    </Text>
                  )}
                </Text>
              )}
            </Text>
          </View>
        </View>
      )}

      {/* Props loading */}
      {propsLoading && (
        <ActivityIndicator size="large" color="#c9a84c" style={{ marginVertical: 30 }} />
      )}

      {/* Props list */}
      {!propsLoading && selectedPlayer && props.length > 0 && (
        <>
          <Text style={s.sectionLabel}>
            Props for {selectedPlayer.player_name || selectedPlayer.name}
            <Text style={{ color: "#64748b", fontSize: 12 }}> ({props.length})</Text>
          </Text>

          {props.map((prop, i) => {
            // Determine consensus line (most common)
            const books = prop?.bookmakers || prop?.books || prop?.odds || [];
            const lineCount: Record<string, number> = {};
            for (const b of books) {
              const l = String(b.line || b.points || "");
              lineCount[l] = (lineCount[l] || 0) + 1;
            }
            let consensusLine = "—";
            let maxCount = 0;
            for (const [l, c] of Object.entries(lineCount)) {
              if (c > maxCount) { consensusLine = l; maxCount = c; }
            }

            return (
              <View key={i} style={s.propCard}>
                <View style={s.propHeader}>
                  <Text style={s.propMarket}>
                    {prop.market_type || prop.market || prop.name || `Prop ${i + 1}`}
                  </Text>
                  {maxCount >= 2 && (
                    <View style={s.consensusBadge}>
                      <Ionicons name="checkmark-circle" size={12} color="#c9a84c" />
                      <Text style={s.consensusText}>Consensus: {consensusLine}</Text>
                    </View>
                  )}
                </View>

                {/* Best over + line range */}
                <View style={s.propStats}>
                  <View style={s.propStat}>
                    <Text style={s.propStatLabel}>Best Over</Text>
                    <Text style={s.propStatVal}>{getBestOver(prop)}</Text>
                  </View>
                  <View style={s.propStat}>
                    <Text style={s.propStatLabel}>Line Range</Text>
                    <Text style={s.propStatVal}>{getLineRange(prop)}</Text>
                  </View>
                </View>

                {/* Book breakdown */}
                {books.length > 0 && (
                  <View style={s.booksBreakdown}>
                    {books.slice(0, 5).map((b: any, bi: number) => (
                      <View key={bi} style={s.bookRow}>
                        <Text style={s.bookRowName}>{b.bookmaker_name || `Book ${bi + 1}`}</Text>
                        <Text style={s.bookRowLine}>{b.line || b.points || "—"}</Text>
                        <Text style={s.bookRowOdds}>
                          O {formatOdds(b.over_price)} / U {formatOdds(b.under_price)}
                        </Text>
                      </View>
                    ))}
                  </View>
                )}
              </View>
            );
          })}
        </>
      )}

      {!propsLoading && selectedPlayer && props.length === 0 && (
        <Text style={s.emptyText}>
          No player props available for this player from connected sportsbooks.
        </Text>
      )}

      {!selectedPlayer && !loading && (
        <Text style={s.emptyText}>Select a player to view available prop bets across sportsbooks.</Text>
      )}

      {error && <Text style={s.errorText}>{error}</Text>}
    </ScrollView>
  );
}

const s = StyleSheet.create({
  container: { flex: 1, backgroundColor: "#060b1a", padding: 16 },
  sectionLabel: {
    fontSize: 13, fontWeight: "700", color: "#c9a84c",
    textTransform: "uppercase", letterSpacing: 1, marginBottom: 8,
  },
  searchInput: {
    backgroundColor: "#0a0f24", borderRadius: 10,
    borderWidth: 1, borderColor: "#1e293b",
    paddingHorizontal: 12, paddingVertical: 8,
    fontSize: 13, color: "#f0f6fc", marginBottom: 10,
  },
  playerChip: {
    paddingVertical: 10, paddingHorizontal: 14,
    borderRadius: 12, backgroundColor: "#0a0f24",
    borderWidth: 1, borderColor: "#1e293b",
    minWidth: 120,
  },
  playerChipActive: {
    borderColor: "#c9a84c",
    backgroundColor: "rgba(201,168,76,0.1)",
  },
  playerChipText: { fontSize: 13, fontWeight: "700", color: "#f0f6fc" },
  playerChipTextActive: { color: "#c9a84c" },
  playerChipMeta: { fontSize: 10, color: "#64748b", marginTop: 2 },
  projectionCard: {
    flexDirection: "row", alignItems: "center",
    backgroundColor: "#0a0f24", borderRadius: 12,
    borderWidth: 1, borderColor: "rgba(201,168,76,0.3)",
    padding: 14, marginBottom: 16,
  },
  projLabel: { fontSize: 11, color: "#64748b", textTransform: "uppercase", fontWeight: "600" },
  projValue: { fontSize: 16, fontWeight: "800", color: "#c9a84c", marginTop: 2 },
  projEdge: { fontSize: 12, color: "#94a3b8" },
  propCard: {
    backgroundColor: "#0a0f24", borderRadius: 12,
    borderWidth: 1, borderColor: "#1e293b",
    padding: 14, marginBottom: 10,
  },
  propHeader: {
    flexDirection: "row", justifyContent: "space-between",
    alignItems: "center", marginBottom: 8,
  },
  propMarket: { fontSize: 14, fontWeight: "700", color: "#f0f6fc" },
  consensusBadge: { flexDirection: "row", alignItems: "center", gap: 4 },
  consensusText: { fontSize: 11, color: "#c9a84c", fontWeight: "600" },
  propStats: { flexDirection: "row", gap: 12, marginBottom: 10 },
  propStat: {
    flex: 1, backgroundColor: "rgba(201,168,76,0.05)",
    borderRadius: 8, padding: 8,
  },
  propStatLabel: { fontSize: 10, color: "#64748b", marginBottom: 2 },
  propStatVal: { fontSize: 12, fontWeight: "700", color: "#c9a84c" },
  booksBreakdown: {
    borderTopWidth: 1, borderTopColor: "#1e293b",
    paddingTop: 8,
  },
  bookRow: {
    flexDirection: "row", alignItems: "center",
    paddingVertical: 6,
  },
  bookRowName: { flex: 1.5, fontSize: 11, color: "#94a3b8" },
  bookRowLine: { width: 50, fontSize: 12, fontWeight: "700", color: "#f0f6fc", textAlign: "center" },
  bookRowOdds: { flex: 1, fontSize: 11, color: "#c9a84c", textAlign: "right" },
  emptyText: { color: "#666", textAlign: "center", marginTop: 40, fontSize: 14 },
  errorText: { color: "#ef4444", textAlign: "center", marginTop: 16, fontSize: 14 },
});