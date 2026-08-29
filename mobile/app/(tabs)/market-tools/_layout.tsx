import { Stack } from "expo-router";

export default function MarketToolsStack() {
  return (
    <Stack
      screenOptions={{
        headerStyle: { backgroundColor: "#060b1a" },
        headerTintColor: "#c9a84c",
        headerTitleStyle: { fontWeight: "700" },
        contentStyle: { backgroundColor: "#060b1a" },
      }}
    >
      <Stack.Screen name="index" options={{ headerShown: false, title: "Market Tools" }} />
      <Stack.Screen name="live-odds" options={{ title: "Live Odds" }} />
      <Stack.Screen name="compare" options={{ title: "Compare Odds" }} />
      <Stack.Screen name="bookmakers" options={{ title: "Bookmakers" }} />
      <Stack.Screen name="player-props" options={{ title: "Player Props" }} />
      <Stack.Screen name="arbitrage" options={{ title: "Arbitrage" }} />
      <Stack.Screen name="parlay" options={{ title: "Parlay Builder" }} />
    </Stack>
  );
}
