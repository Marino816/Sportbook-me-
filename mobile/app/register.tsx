import { useState } from "react";
import { View, Text, TextInput, TouchableOpacity, StyleSheet, Alert, KeyboardAvoidingView, Platform } from "react-native";
import { Link, router } from "expo-router";
import { register } from "../lib/api";

export default function RegisterScreen() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleRegister() {
    setLoading(true);
    try {
      await register(email, password);
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
      <TextInput style={s.input} placeholder="Email" placeholderTextColor="#666" autoCapitalize="none" keyboardType="email-address" value={email} onChangeText={setEmail} />
      <TextInput style={s.input} placeholder="Password (8+ characters)" placeholderTextColor="#666" secureTextEntry value={password} onChangeText={setPassword} />
      <TouchableOpacity style={s.btn} onPress={handleRegister} disabled={loading}>
        <Text style={s.btnText}>{loading ? "Creating..." : "Sign Up"}</Text>
      </TouchableOpacity>
      <Link href="/" style={s.link}>Already have an account? Sign In</Link>
    </KeyboardAvoidingView>
  );
}

const s = StyleSheet.create({
  container: { flex: 1, backgroundColor: "#0a0a0a", justifyContent: "center", padding: 24 },
  title: { fontSize: 24, fontWeight: "900", color: "#4ade80", textAlign: "center", marginBottom: 32, fontStyle: "italic" },
  input: { backgroundColor: "#1a1a1a", color: "#fff", borderRadius: 12, padding: 14, marginBottom: 12, fontSize: 16, borderWidth: 1, borderColor: "#333" },
  btn: { backgroundColor: "#4ade80", borderRadius: 12, padding: 16, alignItems: "center", marginBottom: 16 },
  btnText: { color: "#000", fontWeight: "700", fontSize: 16 },
  link: { color: "#888", textAlign: "center", fontSize: 14 },
});