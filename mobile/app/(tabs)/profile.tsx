import { useEffect, useState } from "react";
import { View, Text, StyleSheet, TouchableOpacity, ActivityIndicator, Alert, ScrollView } from "react-native";
import { router } from "expo-router";
import { getMe, getSubscriptionStatus, unwrapUser } from "../../lib/api";
import { useAuth } from "../../lib/auth";
import { displayPlanLabel, lineupCopyForPlan } from "../../lib/plan-copy";

export default function ProfileScreen() {
  const { signOut } = useAuth();
  const [user, setUser] = useState<any>(null);
  const [billing, setBilling] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    (async () => {
      try {
        const [meBody, billBody] = await Promise.all([
          getMe().catch(() => null),
          getSubscriptionStatus().catch(() => null),
        ]);
        setUser(unwrapUser(meBody) || (meBody as any)?.data || meBody);
        setBilling((billBody as any)?.data || billBody);
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  async function handleLogout() {
    Alert.alert("Sign Out", "Are you sure?", [
      { text: "Cancel", style: "cancel" },
      { text: "Sign Out", style: "destructive", onPress: async () => { await signOut(); router.replace("/"); } },
    ]);
  }

  if (loading) return <View style={s.center}><ActivityIndicator size="large" color="#c9a84c" /></View>;

  const hasAccess = billing?.has_access === true || user?.is_pro === true;
  const planLabel = displayPlanLabel(billing?.plan || user?.plan, hasAccess);
  const planCopy = lineupCopyForPlan(billing?.plan || user?.plan, hasAccess);
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
        <Text style={s.value}>{planLabel}</Text>
        <Text style={s.hint}>{planCopy}</Text>
      </View>

      <TouchableOpacity style={s.linkCard} onPress={() => router.push("/(tabs)/subscription")}>
        <Text style={s.linkText}>Billing & Subscription →</Text>
      </TouchableOpacity>
      <TouchableOpacity style={s.linkCard} onPress={() => router.push("/(tabs)/ai-preferences")}>
        <Text style={s.linkText}>AI Preferences →</Text>
      </TouchableOpacity>
      <TouchableOpacity style={s.linkCard} onPress={() => router.push("/(tabs)/settings")}>
        <Text style={s.linkText}>Settings →</Text>
      </TouchableOpacity>

      <TouchableOpacity style={s.logout} onPress={handleLogout}>
        <Text style={s.logoutText}>Sign Out</Text>
      </TouchableOpacity>
    </ScrollView>
  );
}

const s = StyleSheet.create({
  container: { flex: 1, backgroundColor: "#060b1a", padding: 20 },
  center: { flex: 1, backgroundColor: "#060b1a", justifyContent: "center", alignItems: "center" },
  card: { backgroundColor: "#0a0f24", borderRadius: 16, padding: 16, borderWidth: 1, borderColor: "#1e293b", marginBottom: 12 },
  label: { fontSize: 12, color: "#64748b", textTransform: "uppercase" },
  value: { fontSize: 16, color: "#f0f6fc", marginTop: 4, fontWeight: "600" },
  hint: { fontSize: 12, color: "#94a3b8", marginTop: 6, lineHeight: 18 },
  linkCard: {
    backgroundColor: "#c9a84c22", borderRadius: 12, padding: 16, marginBottom: 10,
    borderWidth: 1, borderColor: "#c9a84c44",
  },
  linkText: { color: "#c9a84c", fontSize: 15, fontWeight: "600" },
  logout: { marginTop: 24, backgroundColor: "#1e293b", borderRadius: 12, padding: 16, alignItems: "center" },
  logoutText: { color: "#ef4444", fontWeight: "700", fontSize: 16 },
});
