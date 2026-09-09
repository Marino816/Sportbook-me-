import { View, Text, StyleSheet, TouchableOpacity, ScrollView, Alert } from "react-native";
import { router } from "expo-router";
import { useAuth } from "../../lib/auth";

export default function SettingsScreen() {
  const { signOut } = useAuth();

  async function handleLogout() {
    Alert.alert("Sign Out", "Are you sure?", [
      { text: "Cancel", style: "cancel" },
      { text: "Sign Out", style: "destructive", onPress: async () => { await signOut(); router.replace("/"); } },
    ]);
  }

  return (
    <ScrollView style={s.scroll} contentContainerStyle={s.container}>
      <Text style={s.title}>Settings</Text>

      <View style={s.section}>
        <Text style={s.label}>AI</Text>
        <TouchableOpacity style={s.row} onPress={() => router.push("/(tabs)/ai-preferences")}>
          <Text style={s.rowLabel}>AI Preferences</Text>
          <Text style={s.link}>Open →</Text>
        </TouchableOpacity>
      </View>

      <View style={s.section}>
        <Text style={s.label}>SECURITY</Text>
        <View style={s.row}>
          <View style={{ flex: 1 }}>
            <Text style={s.rowLabel}>Face ID</Text>
            <Text style={s.hint}>Used at Sign In when you choose biometric login. There is no in-app toggle here.</Text>
          </View>
        </View>
      </View>

      <View style={s.section}>
        <Text style={s.label}>ABOUT</Text>
        <View style={s.row}><Text style={s.rowLabel}>Version</Text><Text style={s.value}>1.1.0</Text></View>
        <View style={s.row}><Text style={s.rowLabel}>Powered by</Text><Text style={s.value}>SB ME Intelligent AI</Text></View>
      </View>

      <TouchableOpacity style={s.logout} onPress={handleLogout}><Text style={s.logoutText}>Sign Out</Text></TouchableOpacity>
    </ScrollView>
  );
}

const s = StyleSheet.create({
  scroll: { flex: 1, backgroundColor: "#060b1a" },
  container: { padding: 20, gap: 24 },
  title: { fontSize: 24, fontWeight: "900", color: "#c9a84c", fontStyle: "italic" },
  section: { gap: 4 },
  label: { fontSize: 11, color: "#64748b", letterSpacing: 1, marginBottom: 4 },
  row: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    paddingVertical: 14,
    borderBottomWidth: 1,
    borderColor: "#1e293b",
    gap: 12,
  },
  rowLabel: { fontSize: 15, color: "#f0f6fc" },
  hint: { fontSize: 12, color: "#64748b", marginTop: 4, lineHeight: 18 },
  value: { fontSize: 14, color: "#94a3b8" },
  link: { fontSize: 14, color: "#c9a84c", fontWeight: "700" },
  logout: { marginTop: 16, padding: 16, borderRadius: 12, backgroundColor: "#1e293b", alignItems: "center" },
  logoutText: { color: "#ef4444", fontWeight: "700", fontSize: 16 },
});
