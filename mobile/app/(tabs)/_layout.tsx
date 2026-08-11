import { Tabs } from "expo-router";

export default function TabLayout() {
  return (
    <Tabs screenOptions={{
      headerStyle: { backgroundColor: "#060b1a" },
      headerTintColor: "#c9a84c",
      headerTitleStyle: { fontWeight: "900", fontSize: 18 },
      tabBarStyle: { backgroundColor: "#0a0f24", borderTopColor: "#1e293b" },
      tabBarActiveTintColor: "#c9a84c",
      tabBarInactiveTintColor: "#475569",
      tabBarLabelStyle: { fontSize: 11, fontWeight: "600" },
    }}>
      <Tabs.Screen name="dashboard" options={{ title: "SB ME", tabBarLabel: "Home" }} />
      <Tabs.Screen name="ai-chat" options={{ title: "SB ME AI", tabBarLabel: "AI" }} />
      <Tabs.Screen name="optimizer" options={{ title: "Optimizer", tabBarLabel: "Optimizer" }} />
      <Tabs.Screen name="lineups" options={{ title: "Lineups", tabBarLabel: "Lineups" }} />
      <Tabs.Screen name="profile" options={{ title: "Profile", tabBarLabel: "Profile" }} />
      <Tabs.Screen name="subscription" options={{ href: null }} />
      <Tabs.Screen name="settings" options={{ href: null }} />
      <Tabs.Screen name="ai-preferences" options={{ href: null }} />
      <Tabs.Screen name="intelligence" options={{ href: null, title: "Market Intelligence" }} />
    </Tabs>
  );
}