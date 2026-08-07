import { useEffect, useState, useCallback } from "react";
import { View, Text, StyleSheet, ScrollView, TouchableOpacity, ActivityIndicator, RefreshControl } from "react-native";
import { router } from "expo-router";
import { getMe, getSubscriptionStatus } from "../../lib/api";
import { sendAIChat, getSlateSummary, AIPreferences } from "../../lib/ai-api";
import AsyncStorage from "@react-native-async-storage/async-storage";

const QUICK_ACTIONS = [
  { label: "🏗️ Build Best Lineup", prompt: "Build my best GPP lineup tonight." },
  { label: "💰 Cash Lineup", prompt: "Build my optimal cash game lineup." },
  { label: "🎯 GPP Lineup", prompt: "Build my large-field GPP tournament lineup." },
  { label: "📊 Slate Summary", prompt: "Explain today's slate." },
  { label: "⚖️ Compare Players", prompt: "Compare the top two plays tonight." },
  { label: "🧠 Ask SB ME AI", prompt: "" },
];

export default function DashboardScreen() {
  const [greeting, setGreeting] = useState("");
  const [user, setUser] = useState<any>(null);
  const [sub, setSub] = useState<any>(null);
  const [aiTips, setAiTips] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const load = useCallback(async () => {
    try {
      const [u, s] = await Promise.all([
        getMe().catch(() => null),
        getSubscriptionStatus().catch(() => null),
      ]);
      setUser(u?.data);
      setSub(s?.data);

      // AI Greeting
      const hour = new Date().getHours();
      const timeGreeting = hour < 12 ? "Good morning" : hour < 17 ? "Good afternoon" : "Good evening";
      setGreeting(timeGreeting);

      // AI Tips from slate summary
      try {
        const slate = await getSlateSummary();
        if (slate?.data?.tips) setAiTips(slate.data.tips);
      } catch {
        setAiTips(["Build your first lineup to get personalized recommendations."]);
      }
    } catch {} finally { setLoading(false); setRefreshing(false); }
  }, []);

  useEffect(() => { load(); }, [load]);

  async function handleQuickAction(prompt: string) {
    if (prompt) {
      await AsyncStorage.setItem("sbm_ai_pending_prompt", prompt);
    }
    router.push("/(tabs)/ai-chat" as any);
  }

  if (loading) return <View style={s.center}><ActivityIndicator size="large" color="#4ade80" /></View>;

  return (
    <ScrollView style={s.scroll} contentContainerStyle={s.container} refreshControl={<RefreshControl refreshing={refreshing} onRefresh={() => { setRefreshing(true); load(); }} tintColor="#4ade80" />}>
      {/* AI Greeting */}
      <Text style={s.greeting}>{greeting}, {user?.email?.split("@")[0] || "Player"}.</Text>
      <Text style={s.subtitle}>🧠 SB ME Intelligent AI™ is ready.</Text>

      {aiTips.length > 0 && (
        <View style={s.aiCard}>
          <Text style={s.aiTitle}>Today's Insights</Text>
          {aiTips.map((tip, i) => (
            <Text key={i} style={s.aiTip}>• {tip}</Text>
          ))}
        </View>
      )}

      {/* Quick Actions */}
      <Text style={s.section}>Quick Actions</Text>
      <View style={s.quickGrid}>
        {QUICK_ACTIONS.map((a, i) => (
          <TouchableOpacity key={i} style={s.quickBtn} onPress={() => handleQuickAction(a.prompt)}>
            <Text style={s.quickLabel}>{a.label}</Text>
          </TouchableOpacity>
        ))}
      </View>

      {/* Subscription Status */}
      <Text style={s.section}>Subscription</Text>
      <View style={s.card}>
        <View style={s.cardRow}>
          <Text style={s.cardLabel}>Plan</Text>
          <Text style={s.cardValue}>{sub?.plan || "Free"}</Text>
        </View>
        <View style={s.cardRow}>
          <Text style={s.cardLabel}>Status</Text>
          <Text style={[s.cardValue, { color: sub?.has_access ? "#4ade80" : "#ff4444" }]}>{sub?.has_access ? "Active" : "Inactive"}</Text>
        </View>
      </View>

      {/* Account */}
      <Text style={s.section}>Account</Text>
      <View style={s.card}>
        <View style={s.cardRow}><Text style={s.cardLabel}>Email</Text><Text style={s.cardValSm}>{user?.email}</Text></View>
        <View style={s.cardRow}><Text style={s.cardLabel}>Role</Text><Text style={s.cardValSm}>{user?.role || "user"}</Text></View>
      </View>

      <Text style={s.footer}>Powered by 🧠 SB ME Intelligent AI™</Text>
    </ScrollView>
  );
}

const s = StyleSheet.create({
  scroll: { flex: 1, backgroundColor: "#0a0a0a" }, container: { padding: 20, gap: 20, paddingBottom: 40 },
  center: { flex: 1, backgroundColor: "#0a0a0a", justifyContent: "center", alignItems: "center" },
  greeting: { fontSize: 22, fontWeight: "900", color: "#fff", marginTop: 8 }, subtitle: { fontSize: 14, color: "#4ade80", fontStyle: "italic" },
  aiCard: { backgroundColor: "#0d2818", borderRadius: 16, padding: 18, borderWidth: 1, borderColor: "#4ade8030" },
  aiTitle: { fontSize: 12, color: "#4ade80", textTransform: "uppercase", fontWeight: "700", marginBottom: 8, letterSpacing: 1 },
  aiTip: { fontSize: 14, color: "#ccc", lineHeight: 22 },
  section: { fontSize: 12, color: "#666", textTransform: "uppercase", letterSpacing: 1, fontWeight: "700" },
  quickGrid: { flexDirection: "row", flexWrap: "wrap", gap: 10 },
  quickBtn: { flexBasis: "47%", flexGrow: 1, backgroundColor: "#1a1a1a", borderRadius: 14, padding: 16, borderWidth: 1, borderColor: "#333", minWidth: 150 },
  quickLabel: { color: "#fff", fontSize: 13, fontWeight: "600" },
  card: { backgroundColor: "#1a1a1a", borderRadius: 16, padding: 16, borderWidth: 1, borderColor: "#333", gap: 10 },
  cardRow: { flexDirection: "row", justifyContent: "space-between", alignItems: "center" },
  cardLabel: { fontSize: 13, color: "#888" }, cardValue: { fontSize: 16, fontWeight: "700", color: "#fff" },
  cardValSm: { fontSize: 14, color: "#ccc" },
  footer: { textAlign: "center", color: "#4ade8030", fontSize: 11, marginTop: 8 },
});