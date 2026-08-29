import { useState } from "react";
import { View, Text, TextInput, TouchableOpacity, StyleSheet, Alert, KeyboardAvoidingView, Platform } from "react-native";
import { Link, router } from "expo-router";
import { register } from "../lib/api";

export default function RegisterScreen() {
  const [username, setUsername] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleRegister() {
    setLoading(true);
    try {
      await register(username, email, password);
      Alert.alert("Account Created", "Please sign in.");
      router.replace("/");
    } catch (e: any) {
      Alert.alert("Registration Failed", e.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <KeyboardAvoidingView behavior={Platform.OS === "ios" ? "padding" : "height"} style={s.container}>
      <Text style={s.title}>Create Account</Text>
      <TextInput style={s.input} placeholder="Username" placeholderTextColor="#475569" autoCapitalize="none" value={username} onChangeText={setUsername} />
      <TextInput style={s.input} placeholder="Email" placeholderTextColor="#475569" autoCapitalize="none" keyboardType="email-address" value={email} onChangeText={setEmail} />
      <TextInput style={s.input} placeholder="Password (8+ characters)" placeholderTextColor="#475569" secureTextEntry value={password} onChangeText={setPassword} />
      <TouchableOpacity style={s.btn} onPress={handleRegister} disabled={loading}>
        <Text style={s.btnText}>{loading ? "Creating..." : "Sign Up"}</Text>
      </TouchableOpacity>
      <Link href="/" style={s.link}><Text style={s.linkText}>Already have an account? Sign In</Text></Link>
    </KeyboardAvoidingView>
  );
}

const s = StyleSheet.create({
  container: { flex: 1, backgroundColor: "#060b1a", justifyContent: "center", padding: 24 },
  title: { fontSize: 24, fontWeight: "900", color: "#c9a84c", textAlign: "center", marginBottom: 32, fontStyle: "italic" },
  input: {
    backgroundColor: "#0a0f24", color: "#f0f6fc", borderRadius: 14,
    padding: 14, marginBottom: 12, fontSize: 16, borderWidth: 1, borderColor: "#1e293b",
  },
  btn: { backgroundColor: "#c9a84c", borderRadius: 14, padding: 16, alignItems: "center", marginBottom: 16 },
  btnText: { color: "#060b1a", fontWeight: "700", fontSize: 16 },
  link: { alignSelf: "center" },
  linkText: { color: "#c9a84c", textAlign: "center", fontSize: 14, fontWeight: "600" },
});
