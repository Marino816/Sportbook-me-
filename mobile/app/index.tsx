import { useState } from "react";
import { View, Text, TextInput, TouchableOpacity, StyleSheet, Alert, KeyboardAvoidingView, Platform } from "react-native";
import { Link, router } from "expo-router";
import * as LocalAuthentication from "expo-local-authentication";
import { LogoText } from "../components/Logo";
import { login, getToken } from "../lib/api";

export default function LoginScreen() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleLogin() {
    setLoading(true);
    try {
      await login(email, password);
      router.replace("/(tabs)/dashboard");
    } catch (e: any) {
      Alert.alert("Login Failed", e.message);
    } finally { setLoading(false); }
  }

  async function handleBiometric() {
    const hasHW = await LocalAuthentication.hasHardwareAsync();
    if (!hasHW) { Alert.alert("Biometric login not available on this device"); return; }
    const enrolled = await LocalAuthentication.isEnrolledAsync();
    if (!enrolled) { Alert.alert("No biometrics enrolled"); return; }
    const existing = await getToken();
    if (!existing) { Alert.alert("Please log in first to enable biometric login"); return; }
    router.replace("/(tabs)/dashboard");
  }

  return (
    <KeyboardAvoidingView style={s.flex} behavior={Platform.OS === "ios" ? "padding" : undefined}>
      <View style={s.container}>
        {/* Logo */}
        <LogoText />
        <Text style={s.tagline}>AI-Powered DFS Intelligence</Text>
        <Text style={s.motto}>Optimize. Analyze. Win.</Text>

        {/* Fields */}
        <TextInput
          style={s.input} placeholder="Email" placeholderTextColor="#475569"
          value={email} onChangeText={setEmail} keyboardType="email-address"
          autoCapitalize="none" autoCorrect={false}
        />
        <TextInput
          style={s.input} placeholder="Password" placeholderTextColor="#475569"
          value={password} onChangeText={setPassword} secureTextEntry
        />

        <TouchableOpacity style={s.btn} onPress={handleLogin} disabled={loading}>
          <Text style={s.btnText}>{loading ? "Signing In..." : "Sign In"}</Text>
        </TouchableOpacity>

        <View style={s.row}>
          <Link href="/register" style={s.link}><Text style={s.linkText}>Create Account</Text></Link>
          <TouchableOpacity onPress={handleBiometric}>
            <Text style={s.linkText}>Biometric</Text>
          </TouchableOpacity>
        </View>
      </View>
    </KeyboardAvoidingView>
  );
}

const s = StyleSheet.create({
  flex: { flex: 1, backgroundColor: "#060b1a" },
  container: { flex: 1, justifyContent: "center", padding: 32, gap: 16 },
  logoRow: { flexDirection: "row", alignItems: "center", justifyContent: "center", gap: 12, marginBottom: 4 },
  logoText: { fontSize: 34, fontWeight: "900", color: "#c9a84c", letterSpacing: 3, fontStyle: "italic" },
  logoDivider: { width: 1, height: 28, backgroundColor: "#c9a84c40" },
  logoSub: { fontSize: 24, fontWeight: "700", color: "#f0f6fc", letterSpacing: 2 },
  tagline: { fontSize: 16, color: "#94a3b8", textAlign: "center", fontWeight: "600" },
  motto: { fontSize: 13, color: "#64748b", textAlign: "center", marginTop: -8 },
  input: {
    backgroundColor: "#0a0f24", color: "#f0f6fc", borderRadius: 14,
    padding: 16, fontSize: 16, borderWidth: 1, borderColor: "#1e293b",
  },
  btn: { backgroundColor: "#c9a84c", borderRadius: 14, padding: 18, alignItems: "center", marginTop: 8 },
  btnText: { color: "#060b1a", fontWeight: "800", fontSize: 17 },
  row: { flexDirection: "row", justifyContent: "space-between", marginTop: 8 },
  link: {},
  linkText: { color: "#c9a84c", fontWeight: "600", fontSize: 14 },
});