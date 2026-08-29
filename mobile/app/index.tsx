import { useState } from "react";
import { View, Text, TextInput, TouchableOpacity, StyleSheet, Alert, KeyboardAvoidingView, Platform } from "react-native";
import { Link, router } from "expo-router";
import { LogoText } from "../components/Logo";
import { useAuth } from "../lib/auth";

export default function LoginScreen() {
  const { signIn, signInWithBiometrics } = useAuth();
  const [identifier, setIdentifier] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleLogin() {
    setLoading(true);
    try {
      await signIn(identifier, password);
      router.replace("/(tabs)/dashboard");
    } catch (e: any) {
      Alert.alert("Login Failed", e.message);
    } finally {
      setLoading(false);
    }
  }

  async function handleBiometric() {
    try {
      await signInWithBiometrics();
      router.replace("/(tabs)/dashboard");
    } catch (e: any) {
      Alert.alert("Biometric Login", e.message);
    }
  }

  return (
    <KeyboardAvoidingView style={s.flex} behavior={Platform.OS === "ios" ? "padding" : undefined}>
      <View style={s.container}>
        <LogoText />
        <Text style={s.tagline}>AI-Powered DFS Intelligence</Text>
        <Text style={s.motto}>Optimize. Analyze. Win.</Text>

        <Text style={s.fieldLabel}>Username or email</Text>
        <TextInput
          style={s.input}
          placeholder="Username or email"
          placeholderTextColor="#475569"
          value={identifier}
          onChangeText={setIdentifier}
          autoCapitalize="none"
          autoCorrect={false}
          autoComplete="off"
          textContentType="none"
          keyboardType="default"
        />
        <TextInput
          style={s.input}
          placeholder="Password"
          placeholderTextColor="#475569"
          value={password}
          onChangeText={setPassword}
          secureTextEntry
          autoComplete="password"
          textContentType="password"
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
  tagline: { fontSize: 16, color: "#94a3b8", textAlign: "center", fontWeight: "600" },
  motto: { fontSize: 13, color: "#64748b", textAlign: "center", marginTop: -8 },
  fieldLabel: { fontSize: 13, color: "#c9a84c", fontWeight: "700" },
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
