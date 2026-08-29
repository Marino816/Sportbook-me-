/**
 * Canonical Expo Router root.
 * package.json main is expo-router/entry — this file is the live application shell.
 * mobile/App.tsx and mobile/src/** are an unused prototype and must not be imported here.
 */

import { useEffect } from "react";
import { ActivityIndicator, StyleSheet, Text, TouchableOpacity, View } from "react-native";
import { Stack, useRootNavigationState, useRouter, useSegments } from "expo-router";
import { StatusBar } from "expo-status-bar";
import { AuthProvider, useAuth } from "../lib/auth";

const BG = "#060b1a";

function BootSplash() {
  return (
    <View style={styles.splash}>
      <ActivityIndicator size="large" color="#c9a84c" />
    </View>
  );
}

function RestoreRetry({ onRetry }: { onRetry: () => void }) {
  return (
    <View style={styles.splash}>
      <Text style={styles.retryTitle}>Couldn't reach your account</Text>
      <Text style={styles.retryBody}>Your session is still saved. Try again.</Text>
      <TouchableOpacity style={styles.retryBtn} onPress={onRetry}>
        <Text style={styles.retryBtnText}>Retry</Text>
      </TouchableOpacity>
    </View>
  );
}

function RootNavigator() {
  const { status, retryRestore } = useAuth();
  const segments = useSegments();
  const router = useRouter();
  const navigationState = useRootNavigationState();

  useEffect(() => {
    // Do not redirect until JWT restore + /auth/me have settled.
    if (status === "loading" || status === "retrying") return;
    if (!navigationState?.key) return;

    const inTabs = segments[0] === "(tabs)";
    const onRegister = segments[0] === "register";

    if (status === "unauthenticated" && inTabs) {
      router.replace("/");
      return;
    }
    if (status === "authenticated" && !inTabs && !onRegister) {
      router.replace("/(tabs)/dashboard");
    }
  }, [status, segments, navigationState?.key, router]);

  return (
    <View style={styles.root}>
      <StatusBar style="light" />
      <Stack
        screenOptions={{
          headerShown: false,
          contentStyle: { backgroundColor: BG },
        }}
      >
        <Stack.Screen name="index" />
        <Stack.Screen name="register" />
        <Stack.Screen name="(tabs)" />
      </Stack>
      {status === "loading" ? <BootSplash /> : null}
      {status === "retrying" ? <RestoreRetry onRetry={() => { void retryRestore(); }} /> : null}
    </View>
  );
}

export default function RootLayout() {
  return (
    <AuthProvider>
      <RootNavigator />
    </AuthProvider>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: BG },
  splash: {
    ...StyleSheet.absoluteFillObject,
    backgroundColor: BG,
    alignItems: "center",
    justifyContent: "center",
    zIndex: 10,
    padding: 32,
  },
  retryTitle: { color: "#f0f6fc", fontSize: 18, fontWeight: "700", textAlign: "center" },
  retryBody: { color: "#94a3b8", fontSize: 14, textAlign: "center", marginTop: 8 },
  retryBtn: {
    marginTop: 20,
    backgroundColor: "#c9a84c",
    borderRadius: 12,
    paddingHorizontal: 24,
    paddingVertical: 12,
  },
  retryBtnText: { color: "#060b1a", fontWeight: "800", fontSize: 16 },
});
