/**
 * Canonical Expo Router root.
 * package.json main is expo-router/entry — this file is the live application shell.
 * mobile/App.tsx and mobile/src/** are an unused prototype and must not be imported here.
 */

import { useEffect } from "react";
import { ActivityIndicator, StyleSheet, View } from "react-native";
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

function RootNavigator() {
  const { status } = useAuth();
  const segments = useSegments();
  const router = useRouter();
  const navigationState = useRootNavigationState();

  useEffect(() => {
    if (status === "loading") return;
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
  },
});
