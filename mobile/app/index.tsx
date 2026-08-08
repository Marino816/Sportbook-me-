import { useState } from "react";
import { View, Text, TextInput, TouchableOpacity, StyleSheet, Alert, KeyboardAvoidingView, Platform } from "react-native";
import { Link, router } from "expo-router";
import * as LocalAuthentication from "expo-local-authentication";
import { login, getToken } from "../../lib/api";

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
    } finally {
      setLoading(false);
    }
  }

  async function handleBiometric() {
    const hasHW = await LocalAuthentication.hasHardwareAsync();
    if (!hasHW) { Alert.alert("Biometric login not available on this device"); return; }
    const enrolled = await LocalAuthentication.isEnrolledAsync();
    if (!enrolled) { Alert.alert("No biometrics enrolled"); return; }
    const existing = await getToken();
    if (!existing) { Alert.alert("Please log in first to enable biometric login"); return; }
    const result = await LocalAuthentication.authenticateAsync({ promptMessage: "Sign in to SB-Me DFS AI" });
    if (result.success) router.replace("/(tabs)/dashboard");
    else Alert.alert("Authentication failed");
  }

  return (
    <KeyboardAvoidingView behavior={Platform.OS === "ios" ? "padding" : "height"} style={s.container}>
      <Text style={s.logo}>SB-Me</Text>
      <Text style={s.subtitle}>Sportsbook Me DFS AI</Text>
      <TextInput style={s.input} placeholder="Email" placeholderTextColor="#666" autoCapitalize="none" keyboardType="email-address" value={email} onChangeText={setEmail} />
      <TextInput style={s.input} placeholder="Password" placeholderTextColor="#666" secureTextEntry value={password} onChangeText={setPassword} />
      <TouchableOpacity style={s.btn} onPress={handleLogin} disabled={loading}>
        <Text style={s.btnText}>{loading ? "Signing In..." : "Sign In"}</Text>
      </TouchableOpacity>
      <TouchableOpacity onPress={handleBiometric}><Text style={s.bio}>🔐 Sign in with Biometrics</Text></TouchableOpacity>
      <Link href="/register" style={s.link}>Create Account</Link>
    </KeyboardAvoidingView>
  );
}

const s = StyleSheet.create({
  container: { flex: 1, backgroundColor: "#0a0a0a", justifyContent: "center", padding: 24 },
  logo: { fontSize: 32, fontWeight: "900", color: "#4ade80", textAlign: "center", fontStyle: "italic" },
  subtitle: { fontSize: 14, color: "#888", textAlign: "center", marginBottom: 32 },
  input: { backgroundColor: "#1a1a1a", color: "#fff", borderRadius: 12, padding: 14, marginBottom: 12, fontSize: 16, borderWidth: 1, borderColor: "#333" },
  btn: { backgroundColor: "#4ade80", borderRadius: 12, padding: 16, alignItems: "center", marginBottom: 16 },
  btnText: { color: "#000", fontWeight: "700", fontSize: 16 },
  bio: { color: "#4ade80", textAlign: "center", fontSize: 14, marginBottom: 16 },
  link: { color: "#888", textAlign: "center", fontSize: 14 },
});