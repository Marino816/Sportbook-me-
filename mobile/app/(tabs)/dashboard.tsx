import { useEffect, useState } from "react";
import { View, Text, StyleSheet, ScrollView, ActivityIndicator } from "react-native";
import { getMe, getSubscriptionStatus, getMissionControl } from "../../lib/api";

export default function DashboardScreen() {
  const [user, setUser] = useState<any>(null);
  const [sub, setSub] = useState<any>(null);
  const [mc, setMc] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => { (async () => {
    try {
      const [u, s, m] = await Promise.all([getMe().catch(() => null), getSubscriptionStatus().catch(() => null), getMissionControl().catch(() => null)]);
      setUser(u?.data); setSub(s?.data); setMc(m?.data);
    } catch {} finally { setLoading(false); }
  })(); }, []);

  if (loading) return <View style={s.center}><ActivityIndicator size="large" color="#4ade80" /></View>;

  return (
    <ScrollView style={s.scroll} contentContainerStyle={s.container}>
      <Text style={s.greeting}>Welcome, {user?.email || "User"}</Text>
      <View style={s.card}>
        <Text style={s.cardTitle}>Subscription</Text>
        <Text style={s.cardValue}>{sub?.plan || "Free"}</Text>
        <Text style={s.cardSub}>{sub?.status === "active" ? "Active" : "Inactive"}</Text>
      </View>
      <View style={s.card}>
        <Text style={s.cardTitle}>Account</Text>
        <Text style={s.cardSub}>{user?.role === "admin" ? "Admin" : "User"} · {user?.is_pro ? "Pro" : "Free"}</Text>
      </View>
      {mc && (
        <View style={s.card}>
          <Text style={s.cardTitle}>Mission Control</Text>
          <Text style={s.cardValue}>{mc.widget_count || 0} Widgets</Text>
          <Text style={s.cardSub}>Tier: {mc.tier}</Text>
        </View>
      )}
    </ScrollView>
  );
}

const s = StyleSheet.create({
  scroll: { flex: 1, backgroundColor: "#0a0a0a" },
  container: { padding: 20, gap: 16 },
  center: { flex: 1, backgroundColor: "#0a0a0a", justifyContent: "center", alignItems: "center" },
  greeting: { fontSize: 22, fontWeight: "900", color: "#4ade80", marginBottom: 8, fontStyle: "italic" },
  card: { backgroundColor: "#1a1a1a", borderRadius: 16, padding: 20, borderWidth: 1, borderColor: "#333" },
  cardTitle: { fontSize: 12, color: "#666", textTransform: "uppercase", marginBottom: 4 },
  cardValue: { fontSize: 20, fontWeight: "700", color: "#fff" },
  cardSub: { fontSize: 14, color: "#888", marginTop: 2 },
});