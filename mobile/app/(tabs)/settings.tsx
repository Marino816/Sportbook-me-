import { useState } from "react";
import { View, Text, StyleSheet, TouchableOpacity, ScrollView, Switch, Alert } from "react-native";
import { router } from "expo-router";
import { useAuth } from "../../lib/auth";

export default function SettingsScreen() {
  const { signOut } = useAuth();
  const [notifications, setNotifications] = useState(true);
  const [biometric, setBiometric] = useState(true);
  const [darkMode, setDarkMode] = useState(true);

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
        <Text style={s.label}>NOTIFICATIONS</Text>
        <View style={s.row}><Text style={s.rowLabel}>Push Notifications</Text><Switch value={notifications} onValueChange={setNotifications} trackColor={{ false: "#333", true: "#c9a84c" }} /></View>
        <View style={s.row}><Text style={s.rowLabel}>Slate Reminders</Text><Switch value={notifications} onValueChange={setNotifications} trackColor={{ false: "#333", true: "#c9a84c" }} /></View>
        <View style={s.row}><Text style={s.rowLabel}>Injury Alerts</Text><Switch value={notifications} onValueChange={setNotifications} trackColor={{ false: "#333", true: "#c9a84c" }} /></View>
      </View>

      <View style={s.section}>
        <Text style={s.label}>SECURITY</Text>
        <View style={s.row}><Text style={s.rowLabel}>Biometric Login</Text><Switch value={biometric} onValueChange={setBiometric} trackColor={{ false: "#333", true: "#c9a84c" }} /></View>
      </View>

      <View style={s.section}>
        <Text style={s.label}>APPEARANCE</Text>
        <View style={s.row}><Text style={s.rowLabel}>Dark Mode</Text><Switch value={darkMode} onValueChange={setDarkMode} trackColor={{ false: "#333", true: "#c9a84c" }} /></View>
      </View>

      <View style={s.section}>
        <Text style={s.label}>ABOUT</Text>
        <View style={s.row}><Text style={s.rowLabel}>Version</Text><Text style={s.value}>1.1.0</Text></View>
        <View style={s.row}><Text style={s.rowLabel}>Powered by</Text><Text style={s.value}>🧠 SB ME Intelligent AI</Text></View>
      </View>

      <TouchableOpacity style={s.logout} onPress={handleLogout}><Text style={s.logoutText}>Sign Out</Text></TouchableOpacity>
    </ScrollView>
  );
}

const s = StyleSheet.create({
  scroll: { flex: 1, backgroundColor: "#060b1a" }, container: { padding: 20, gap: 24 },
  title: { fontSize: 24, fontWeight: "900", color: "#c9a84c", fontStyle: "italic" },
  section: { gap: 4 },
  label: { fontSize: 11, color: "#666", letterSpacing: 1, marginBottom: 4 },
  row: { flexDirection: "row", justifyContent: "space-between", alignItems: "center", paddingVertical: 14, borderBottomWidth: 1, borderColor: "#222" },
  rowLabel: { fontSize: 15, color: "#fff" }, value: { fontSize: 14, color: "#888" },
  logout: { marginTop: 16, padding: 16, borderRadius: 12, backgroundColor: "#333", alignItems: "center" },
  logoutText: { color: "#ff4444", fontWeight: "700", fontSize: 16 },
});