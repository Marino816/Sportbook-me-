import { useState, useCallback } from "react";
import {
  View, Text, StyleSheet, ScrollView, TouchableOpacity, ActivityIndicator,
} from "react-native";
import { useFocusEffect } from "expo-router";
import { getToken, getApiUrl } from "../../../lib/api";

const API_URL = getApiUrl();
const LEAGUES = [
  "MLB", "NBA", "NCAAB", "WNBA", "NCAAF", "NFL", "EHF_EURO", "NHL", "UFC",
  "BUNDESLIGA", "EPL", "FR_LIGUE_1", "INTERNATIONAL_SOCCER", "IT_SERIE_A",
  "LA_LIGA", "MLS", "UEFA_CHAMPIONS_LEAGUE",
];

export default function BookmakersScreen() {
  const [league, setLeague] = useState("MLB");
  const [payload, setPayload] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = async () => {
    setLoading(true);
    setError(null);
    try {
      const token = await getToken();
      const res = await fetch(`${API_URL}/sgo/platforms?league=${encodeURIComponent(league)}`, {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const json = await res.json();
      setPayload(json.data || json);
    } catch (e: any) {
      setError(e.message);
      setPayload(null);
    } finally {
      setLoading(false);
    }
  };

  useFocusEffect(useCallback(() => { load(); }, [league]));

  const counts = payload?.counts || {};
  const mapped = payload?.mapped_to_sgo || [];
  const needed = payload?.mapping_needed || [];
  const noData = payload?.no_current_data || [];

  return (
    <View style={s.flex}>
      <ScrollView contentContainerStyle={s.pad}>
        <Text style={s.title}>Bookmakers</Text>
        <Text style={s.sub}>Live SportsGameOdds books vs the SB ME 55-platform catalog. Missing lines are not filled in.</Text>
        <ScrollView horizontal showsHorizontalScrollIndicator={false} style={{ marginVertical: 12 }}>
          {LEAGUES.map((lg) => (
            <TouchableOpacity key={lg} onPress={() => setLeague(lg)} style={[s.chip, league === lg && s.chipOn]}>
              <Text style={[s.chipText, league === lg && s.chipTextOn]}>{lg}</Text>
            </TouchableOpacity>
          ))}
        </ScrollView>
        {loading && <ActivityIndicator color="#c9a84c" />}
        {error && <Text style={s.err}>{error}</Text>}
        {payload && (
          <>
            <Text style={s.meta}>
              {counts.total_existing ?? 55} platforms · {counts.mapped_to_sgo ?? 0} with current SGO data · {counts.mapping_needed ?? 0} mapping needed · {counts.no_current_data ?? 0} no current line
            </Text>
            <Text style={s.h}>Line available</Text>
            {mapped.length === 0 ? <Text style={s.empty}>No mapped books returned a current market.</Text> : mapped.map((p: any) => (
              <View key={p.id} style={s.row}><Text style={s.name}>{p.name}</Text><Text style={s.ok}>Available</Text></View>
            ))}
            <Text style={s.h}>No current market</Text>
            {noData.slice(0, 20).map((p: any) => (
              <View key={p.id} style={s.row}><Text style={s.name}>{p.name}</Text><Text style={s.muted}>No line</Text></View>
            ))}
            <Text style={s.h}>Mapping needed</Text>
            {needed.map((p: any) => (
              <View key={p.id} style={s.row}><Text style={s.name}>{p.name}</Text><Text style={s.warn}>Mapping needed</Text></View>
            ))}
          </>
        )}
      </ScrollView>
    </View>
  );
}

const s = StyleSheet.create({
  flex: { flex: 1, backgroundColor: "#060b1a" },
  pad: { padding: 16, paddingBottom: 40 },
  title: { fontSize: 22, fontWeight: "900", color: "#c9a84c" },
  sub: { fontSize: 12, color: "#94a3b8", marginTop: 6 },
  chip: { paddingHorizontal: 10, paddingVertical: 6, borderRadius: 8, borderWidth: 1, borderColor: "#1e293b", marginRight: 6, backgroundColor: "#0a0f24" },
  chipOn: { borderColor: "#c9a84c", backgroundColor: "rgba(201,168,76,0.12)" },
  chipText: { color: "#94a3b8", fontSize: 11, fontWeight: "700" },
  chipTextOn: { color: "#c9a84c" },
  err: { color: "#ef4444", marginTop: 12 },
  meta: { color: "#94a3b8", fontSize: 12, marginBottom: 12 },
  h: { color: "#c9a84c", fontSize: 12, fontWeight: "800", marginTop: 16, marginBottom: 8, textTransform: "uppercase" },
  row: { flexDirection: "row", justifyContent: "space-between", paddingVertical: 8, borderBottomWidth: 1, borderBottomColor: "#1e293b" },
  name: { color: "#f0f6fc", fontSize: 13, fontWeight: "600" },
  ok: { color: "#4ade80", fontSize: 11 },
  muted: { color: "#64748b", fontSize: 11 },
  warn: { color: "#f59e0b", fontSize: 11 },
  empty: { color: "#64748b", fontSize: 12 },
});
