import { useState, useEffect } from "react";
import { View, Text, StyleSheet, TouchableOpacity, ScrollView, Alert } from "react-native";
import { AIPreferences } from "../../lib/ai-api";
import { defaultAIPreferences, loadAIPreferences, saveAIPreferences } from "../../lib/ai-api";

export default function AIPreferencesScreen() {
  const [prefs, setPrefs] = useState<AIPreferences>(defaultAIPreferences);

  useEffect(() => {
    loadAIPreferences().then(setPrefs);
  }, []);

  async function save(newPrefs: AIPreferences) {
    setPrefs(newPrefs);
    await saveAIPreferences(newPrefs);
  }

  function select(key: keyof AIPreferences, value: string) {
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
      <Text style={s.subtitle}>
        These preferences stay on this device and help SB ME AI personalize recommendations. Models and prompts are unchanged.
      </Text>

      {(Object.keys(opts) as (keyof typeof opts)[]).map((category) => (
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

      <TouchableOpacity style={s.reset} onPress={() => { save(defaultAIPreferences); Alert.alert("Reset", "Preferences reset to defaults."); }}>
        <Text style={s.resetText}>Reset to Defaults</Text>
      </TouchableOpacity>
    </ScrollView>
  );
}

const s = StyleSheet.create({
  scroll: { flex: 1, backgroundColor: "#060b1a" },
  container: { padding: 20, gap: 24 },
  title: { fontSize: 24, fontWeight: "900", color: "#c9a84c", fontStyle: "italic" },
  subtitle: { fontSize: 14, color: "#94a3b8", lineHeight: 20 },
  section: { gap: 8 },
  label: { fontSize: 12, color: "#64748b", textTransform: "uppercase", letterSpacing: 1 },
  row: { flexDirection: "row", flexWrap: "wrap", gap: 8 },
  chip: { paddingHorizontal: 16, paddingVertical: 10, borderRadius: 20, backgroundColor: "#0a0f24", borderWidth: 1, borderColor: "#1e293b" },
  chipActive: { borderColor: "#c9a84c", backgroundColor: "#c9a84c20" },
  chipText: { color: "#64748b", fontSize: 13, fontWeight: "600" },
  chipTextActive: { color: "#c9a84c" },
  reset: { marginTop: 8, padding: 16, borderRadius: 12, backgroundColor: "#1e293b", alignItems: "center" },
  resetText: { color: "#ef4444", fontWeight: "600" },
});
