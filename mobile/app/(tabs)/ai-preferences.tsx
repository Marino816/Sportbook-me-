import { useState, useEffect } from "react";
import { View, Text, StyleSheet, TouchableOpacity, ScrollView, Alert } from "react-native";
import AsyncStorage from "@react-native-async-storage/async-storage";
import { AIPreferences } from "../../lib/ai-api";

const PREFS_KEY = "sbm_ai_preferences";

const defaultPrefs: AIPreferences = {
  preferred_sport: "nba",
  preferred_contest: "gpp",
  risk_tolerance: "medium",
  salary_utilization: "balanced",
};

export default function AIPreferencesScreen() {
  const [prefs, setPrefs] = useState<AIPreferences>(defaultPrefs);

  useEffect(() => { (async () => {
    try { const stored = await AsyncStorage.getItem(PREFS_KEY); if (stored) setPrefs({ ...defaultPrefs, ...JSON.parse(stored) }); } catch {}
  })(); }, []);

  async function save(newPrefs: AIPreferences) {
    setPrefs(newPrefs);
    await AsyncStorage.setItem(PREFS_KEY, JSON.stringify(newPrefs));
  }

  function select<T extends Record<string, any>>(key: keyof AIPreferences, value: any) {
    save({ ...prefs, [key]: value });
  }

  const opts = {
    preferred_sport: ["nba", "nfl", "mlb", "mma"],
    preferred_contest: ["cash", "gpp", "single_entry", "tournament"],
    risk_tolerance: ["low", "medium", "high"],
    salary_utilization: ["conservative", "balanced", "aggressive"],
  };

  return (
    <ScrollView style={s.scroll} contentContainerStyle={s.container}>
      <Text style={s.title}>AI Personalization</Text>
      <Text style={s.subtitle}>Your preferences help the AI personalize recommendations. You can change or reset these at any time.</Text>

      {(Object.keys(opts) as (keyof typeof opts)[]).map(category => (
        <View key={category} style={s.section}>
          <Text style={s.label}>{category.replace(/_/g, " ").toUpperCase()}</Text>
          <View style={s.row}>
            {opts[category].map((v: string) => (
              <TouchableOpacity key={v} style={[s.chip, prefs[category] === v && s.chipActive]} onPress={() => select(category, v)}>
                <Text style={[s.chipText, prefs[category] === v && s.chipTextActive]}>{v}</Text>
              </TouchableOpacity>
            ))}
          </View>
        </View>
      ))}

      <TouchableOpacity style={s.reset} onPress={() => { save(defaultPrefs); Alert.alert("Reset", "Preferences reset to defaults."); }}>
        <Text style={s.resetText}>Reset to Defaults</Text>
      </TouchableOpacity>
    </ScrollView>
  );
}

const s = StyleSheet.create({
  scroll: { flex: 1, backgroundColor: "#060b1a" }, container: { padding: 20, gap: 24 },
  title: { fontSize: 24, fontWeight: "900", color: "#c9a84c", fontStyle: "italic" },
  subtitle: { fontSize: 14, color: "#888", lineHeight: 20 },
  section: { gap: 8 },
  label: { fontSize: 12, color: "#666", textTransform: "uppercase", letterSpacing: 1 },
  row: { flexDirection: "row", flexWrap: "wrap", gap: 8 },
  chip: { paddingHorizontal: 16, paddingVertical: 10, borderRadius: 20, backgroundColor: "#0a0f24", borderWidth: 1, borderColor: "#333" },
  chipActive: { borderColor: "#c9a84c", backgroundColor: "#c9a84c20" },
  chipText: { color: "#888", fontSize: 13, fontWeight: "600" },
  chipTextActive: { color: "#c9a84c" },
  reset: { marginTop: 8, padding: 16, borderRadius: 12, backgroundColor: "#333", alignItems: "center" },
  resetText: { color: "#ff4444", fontWeight: "600" },
});