import { useState } from "react";
import { View, Text, StyleSheet, TouchableOpacity, ScrollView, Switch, Alert } from "react-native";
import { router } from "expo-router";
import { clearToken, deleteAccount } from "../../lib/api";

export default function SettingsScreen() {
  const [notifications, setNotifications] = useState(true);
  const [biometric, setBiometric] = useState(true);
  const [darkMode, setDarkMode] = useState(true);

  async function handleLogout() {
    Alert.alert("Sign Out", "Are you sure?", [
      { text: "Cancel", style: "cancel" },
      { text: "Sign Out", style: "destructive", onPress: async () => { await clearToken(); router.replace("/"); } },
    ]);
  }

  async function handleDeleteAccount() {
    Alert.alert(
      "Delete account permanently?",
      "This permanently deletes your Sportbook Me DFS AI account and saved app data. Cancel Apple, Google Play, Stripe, or PayKings billing first — deletion does not stop those charges. It cannot be undone.",
      [
        { text: "Cancel", style: "cancel" },
        {
          text: "Delete Account",
          style: "destructive",
          onPress: async () => {
            try {
              await deleteAccount();
              await clearToken();
              Alert.alert("Account deleted", "Your Sportbook Me account was deleted.", [
                { text: "OK", onPress: () => router.replace("/") },
              ]);
            } catch (error) {
              Alert.alert(
                "Could not delete account",
                error instanceof Error ? error.message : "Please try again.",
              );
            }
          },
        },
      ],
    );
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
        <View style={s.row}><Text style={s.rowLabel}>Version</Text><Text style={s.value}>1.1.1</Text></View>
        <View style={s.row}><Text style={s.rowLabel}>Powered by</Text><Text style={s.value}>🧠 SB ME Intelligent AI</Text></View>
      </View>

      <View style={s.section}>
        <Text style={s.label}>ACCOUNT</Text>
        <TouchableOpacity style={s.row} onPress={handleDeleteAccount}>
          <Text style={[s.rowLabel, { color: "#ef4444" }]}>Delete Account</Text>
          <Text style={{ color: "#ef4444", fontWeight: "700" }}>Request →</Text>
        </TouchableOpacity>
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