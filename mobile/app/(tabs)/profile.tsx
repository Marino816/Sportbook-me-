import { useEffect, useState } from "react";
import { View, Text, StyleSheet, TouchableOpacity, ActivityIndicator, Alert, ScrollView } from "react-native";
import { router } from "expo-router";
import { getMe, clearToken } from "../../lib/api";

export default function ProfileScreen() {
  const [user, setUser] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    (async () => {
      try { const r = await getMe(); setUser(r.data || r); } catch {} finally { setLoading(false); }
    })();
  }, []);

  async function handleLogout() {
    Alert.alert("Sign Out", "Are you sure?", [
      { text: "Cancel", style: "cancel" },
      { text: "Sign Out", style: "destructive", onPress: async () => { await clearToken(); router.replace("/"); } },
    ]);
  }

  if (loading) return <View style={s.center}><ActivityIndicator size="large" color="#4ade80" /></View>;

  const plan = user?.plan || (user?.is_pro === true ? "Pro" : "Free");
  const role = user?.role || "user";

  return (
    <ScrollView style={s.container}>
      <View style={s.card}>
        <Text style={s.label}>Email</Text>
        <Text style={s.value}>{user?.email || "N/A"}</Text>
      </View>
      <View style={s.card}>
        <Text style={s.label}>Role</Text>
        <Text style={s.value}>{role}</Text>
      </View>
      <View style={s.card}>
        <Text style={s.label}>Plan</Text>
        <Text style={s.value}>{plan}</Text>
      </View>

      <TouchableOpacity style={s.linkCard} onPress={() => router.push("/(tabs)/subscription")}>
        <Text style={s.linkText}>Billing & Subscription →</Text>
      </TouchableOpacity>
      <TouchableOpacity style={s.linkCard} onPress={() => router.push("/(tabs)/settings")}>
        <Text style={s.linkText}>Settings & AI Preferences →</Text>
      </TouchableOpacity>

      <TouchableOpacity style={s.logout} onPress={handleLogout}>
        <Text style={s.logoutText}>Sign Out</Text>
      </TouchableOpacity>
    </ScrollView>
  );
}

const s = StyleSheet.create({
  container: { flex: 1, backgroundColor: "#0a0a0a", padding: 20 },
  center: { flex: 1, backgroundColor: "#0a0a0a", justifyContent: "center", alignItems: "center" },
  card: { backgroundColor: "#1a1a1a", borderRadius: 16, padding: 16, borderWidth: 1, borderColor: "#333", marginBottom: 12 },
  label: { fontSize: 12, color: "#666", textTransform: "uppercase" },
  value: { fontSize: 16, color: "#fff", marginTop: 4, fontWeight: "600" },
  linkCard: {
    backgroundColor: "#4ade8022", borderRadius: 12, padding: 16, marginBottom: 10,
    borderWidth: 1, borderColor: "#4ade8044",
  },
  linkText: { color: "#4ade80", fontSize: 15, fontWeight: "600" },
  logout: { marginTop: 24, backgroundColor: "#333", borderRadius: 12, padding: 16, alignItems: "center" },
  logoutText: { color: "#ff4444", fontWeight: "700", fontSize: 16 },
});