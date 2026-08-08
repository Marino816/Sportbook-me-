import { useEffect, useState } from "react";
import { View, Text, StyleSheet, TouchableOpacity, ActivityIndicator, Alert } from "react-native";
import { router } from "expo-router";
import { getMe, clearToken } from "../../lib/api";

export default function ProfileScreen() {
  const [user, setUser] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => { (async () => { try { const r = await getMe(); setUser(r.data); } catch {} finally { setLoading(false); } })(); }, []);

  async function handleLogout() {
    Alert.alert("Sign Out", "Are you sure?", [
      { text: "Cancel", style: "cancel" },
      { text: "Sign Out", style: "destructive", onPress: async () => { await clearToken(); router.replace("/"); } },
    ]);
  }

  if (loading) return <View style={s.center}><ActivityIndicator size="large" color="#4ade80" /></View>;

  return (
    <View style={s.container}>
      <View style={s.card}>
        <Text style={s.label}>Email</Text><Text style={s.value}>{user?.email}</Text>
      </View>
      <View style={s.card}>
        <Text style={s.label}>Role</Text><Text style={s.value}>{user?.role || "user"}</Text>
      </View>
      <View style={s.card}>
        <Text style={s.label}>Plan</Text><Text style={s.value}>{user?.is_pro ? "Pro" : "Free"}</Text>
      </View>
      <TouchableOpacity style={s.logout} onPress={handleLogout}>
        <Text style={s.logoutText}>Sign Out</Text>
      </TouchableOpacity>
    </View>
  );
}

const s = StyleSheet.create({
  container: { flex: 1, backgroundColor: "#0a0a0a", padding: 20, gap: 16 },
  center: { flex: 1, backgroundColor: "#0a0a0a", justifyContent: "center", alignItems: "center" },
  card: { backgroundColor: "#1a1a1a", borderRadius: 16, padding: 16, borderWidth: 1, borderColor: "#333" },
  label: { fontSize: 12, color: "#666", textTransform: "uppercase" }, value: { fontSize: 16, color: "#fff", marginTop: 4, fontWeight: "600" },
  logout: { marginTop: 32, backgroundColor: "#333", borderRadius: 12, padding: 16, alignItems: "center" },
  logoutText: { color: "#ff4444", fontWeight: "700", fontSize: 16 },
});