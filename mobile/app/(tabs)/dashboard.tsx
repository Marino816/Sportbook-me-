import { useState, useEffect, useCallback } from "react";
import { View, Text, StyleSheet, ScrollView, TouchableOpacity, ActivityIndicator, RefreshControl } from "react-native";
import { useRouter, useFocusEffect } from "expo-router";
import { Ionicons } from "@expo/vector-icons";
import { LogoText } from "../../components/Logo";
import { getMe } from "../../lib/api";

const ACTIONS = [
  { id: "best", icon: "sparkles", label: "Build Best\nLineup", route: "/(tabs)/optimizer" },
  { id: "parlay", icon: "layers", label: "Parlay\nBuilder", route: "/(tabs)/market-tools/parlay" as any },
  { id: "cash", icon: "shield-checkmark", label: "Cash\nLineup", route: "/(tabs)/optimizer" },
  { id: "gpp", icon: "rocket", label: "GPP\nLineup", route: "/(tabs)/optimizer" },
  { id: "slate", icon: "analytics", label: "Slate\nSummary", route: "/(tabs)/optimizer" },
  { id: "ai", icon: "chatbubble-ellipses", label: "Ask\nSB ME AI", route: "/(tabs)/ai-chat" },
];

export default function DashboardScreen() {
  const router = useRouter();
  const [user, setUser] = useState<any>(null);
  const [refreshing, setRefreshing] = useState(false);
  const [greeting, setGreeting] = useState("");

  useEffect(() => {
    const hour = new Date().getHours();
    if (hour < 12) setGreeting("Good morning");
    else if (hour < 17) setGreeting("Good afternoon");
    else setGreeting("Good evening");
  }, []);

  useFocusEffect(useCallback(() => {
    (async () => {
      try {
        const data = await getMe();
        setUser((data as any).data || data);
      } catch {}
    })();
  }, []));

  const onRefresh = async () => {
    setRefreshing(true);
    try {
      const data = await getMe();
      setUser((data as any).data || data);
    } catch {}
    setRefreshing(false);
  };

  return (
    <View style={s.flex}>
      <ScrollView style={s.scroll} contentContainerStyle={s.container}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor="#c9a84c" />}
      >
        {/* Logo Header */}
        <View style={s.header}>
          <LogoText />
          <View style={s.headerIcons}>
            <TouchableOpacity onPress={() => router.push("/(tabs)/market-tools")}>
              <Ionicons name="trending-up" size={20} color="#c9a84c" />
            </TouchableOpacity>
            <TouchableOpacity onPress={() => router.push("/(tabs)/intelligence")}>
              <Ionicons name="pulse" size={20} color="#c9a84c" />
            </TouchableOpacity>
          </View>
        </View>

        {/* Greeting */}
        <Text style={s.greeting}>{greeting}, {user?.name || user?.email?.split("@")[0] || "Player"}.</Text>
        <Text style={s.subtitle}>SB ME Intelligent AI™ is ready.</Text>

        {/* Plan info */}
        <View style={s.planRow}>
          <Ionicons name="ribbon" size={16} color="#c9a84c" />
          <Text style={s.planText}>{user?.plan || "Free"} Plan</Text>
        </View>

        {/* Quick Actions */}
        <Text style={s.sectionTitle}>Quick Actions</Text>
        <View style={s.actionsGrid}>
          {ACTIONS.map((action) => (
            <TouchableOpacity key={action.id} style={s.actionCard} onPress={() => router.push(action.route as any)}>
              <Ionicons name={action.icon as any} size={28} color="#c9a84c" />
              <Text style={s.actionLabel}>{action.label}</Text>
            </TouchableOpacity>
          ))}
        </View>

        {/* Parlay Builder — Prominent Promo */}
        <TouchableOpacity style={s.parlayCard} onPress={() => router.push("/(tabs)/market-tools/parlay" as any)}>
          <View style={s.parlayTop}>
            <View style={s.parlayIconWrap}>
              <Ionicons name="layers" size={16} color="#c9a84c" />
            </View>
            <View style={{ flex: 1 }}><Text style={s.parlayTitle}>BUILD YOUR PARLAY</Text></View>
          </View>
          <Text style={s.parlayBody}>Moneylines · Spreads · Totals · Player Props</Text>
          <Text style={s.parlaySub}>55+ Supported Sportsbooks & Platforms{'\n'}Availability varies by sport and event.</Text>
          <View style={s.parlayCTA}>
            <Text style={s.parlayCTAText}>OPEN PARLAY BUILDER →</Text>
          </View>
        </TouchableOpacity>

        {/* Intelligence Overview */}
        <Text style={s.sectionTitle}>SB ME Intelligence</Text>
        <View style={s.intelCard}>
          <View style={s.intelRow}>
            <Ionicons name="flame" size={16} color="#c9a84c" />
            <Text style={s.intelLabel}>Top Plays</Text>
            <Text style={s.intelVal}>18</Text>
          </View>
          <View style={s.intelRow}>
            <Ionicons name="trending-up" size={16} color="#c9a84c" />
            <Text style={s.intelLabel}>Best Environment</Text>
            <Text style={s.intelVal}>LAD@SD</Text>
          </View>
          <View style={s.intelRow}>
            <Ionicons name="flash" size={16} color="#c9a84c" />
            <Text style={s.intelLabel}>Market Edge</Text>
            <Text style={s.intelVal}>+2.3 pts</Text>
          </View>
        </View>
      </ScrollView>
    </View>
  );
}

const s = StyleSheet.create({
  flex: { flex: 1, backgroundColor: "#060b1a" },
  scroll: { flex: 1 },
  container: { padding: 20, gap: 16, paddingBottom: 24 },
  header: { flexDirection: "row", justifyContent: "space-between", alignItems: "center" },
  logoContainer: { flexDirection: "row", alignItems: "center", gap: 10 },
  logoBlock: { flexDirection: "row", alignItems: "center" },
  logoText: { fontSize: 22, fontWeight: "900", color: "#c9a84c", letterSpacing: 2, fontStyle: "italic" },
  logoDivider: { width: 1, height: 20, backgroundColor: "#c9a84c40" },
  logoSub: { fontSize: 16, fontWeight: "700", color: "#f0f6fc", letterSpacing: 1 },
  headerIcons: { flexDirection: "row", gap: 16 },
  greeting: { fontSize: 26, fontWeight: "800", color: "#f0f6fc", marginTop: 4 },
  subtitle: { fontSize: 15, color: "#94a3b8", marginTop: -8 },
  planRow: { flexDirection: "row", alignItems: "center", gap: 8, marginTop: -8 },
  planText: { fontSize: 13, color: "#c9a84c", fontWeight: "600" },
  sectionTitle: { fontSize: 14, fontWeight: "700", color: "#64748b", textTransform: "uppercase", letterSpacing: 1 },
  actionsGrid: { flexDirection: "row", flexWrap: "wrap", gap: 10 },
  actionCard: {
    width: "31%", aspectRatio: 1, backgroundColor: "#0a0f24", borderRadius: 16,
    borderWidth: 1, borderColor: "#1e293b", alignItems: "center",
    justifyContent: "center", gap: 6,
  },
  actionLabel: { fontSize: 11, fontWeight: "600", color: "#94a3b8", textAlign: "center", lineHeight: 14 },
  intelCard: { backgroundColor: "#0a0f24", borderRadius: 16, padding: 16, borderWidth: 1, borderColor: "#1e293b", gap: 12 },
  intelRow: { flexDirection: "row", alignItems: "center", gap: 10 },
  intelLabel: { flex: 1, fontSize: 14, color: "#94a3b8" },
  intelVal: { fontSize: 14, fontWeight: "700", color: "#c9a84c" },
  // Parlay promo card
  parlayCard: { backgroundColor: "#0a0f24", borderRadius: 14, borderWidth: 1, borderColor: "rgba(201,168,76,0.15)", padding: 14, gap: 6 },
  parlayTop: { flexDirection: "row", alignItems: "center", gap: 10 },
  parlayIconWrap: { width: 30, height: 30, borderRadius: 7, backgroundColor: "rgba(201,168,76,0.12)", alignItems: "center", justifyContent: "center" },
  parlayTitle: { fontSize: 13, fontWeight: "800", color: "#f0f6fc" },
  parlayBody: { fontSize: 10, color: "#64748b" },
  parlaySub: { fontSize: 9, color: "#475569" },
  parlayCTA: { marginTop: 2, alignSelf: "flex-start", paddingHorizontal: 12, paddingVertical: 5, borderRadius: 6, backgroundColor: "rgba(201,168,76,0.12)", borderWidth: 1, borderColor: "rgba(201,168,76,0.25)" },
  parlayCTAText: { fontSize: 11, fontWeight: "700", color: "#c9a84c" },
});