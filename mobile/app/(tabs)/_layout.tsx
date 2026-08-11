import { Tabs } from "expo-router";

export default function TabLayout() {
  return (
    <Tabs screenOptions={{
      headerStyle: { backgroundColor: "#0a0a0a" },
      headerTintColor: "#4ade80",
      headerTitleStyle: { fontWeight: "900", fontStyle: "italic" },
      tabBarStyle: { backgroundColor: "#111", borderTopColor: "#222" },
      tabBarActiveTintColor: "#4ade80",
      tabBarInactiveTintColor: "#666",
      tabBarLabelStyle: { fontSize: 11 },
    }}>
      <Tabs.Screen name="dashboard" options={{ title: "SB ME", tabBarLabel: "Home" }} />
      <Tabs.Screen name="ai-chat" options={{ title: "SB ME AI", tabBarLabel: "AI" }} />
      <Tabs.Screen name="optimizer" options={{ title: "Optimizer", tabBarLabel: "Optimizer" }} />
      <Tabs.Screen name="lineups" options={{ title: "Lineups", tabBarLabel: "Lineups" }} />
      <Tabs.Screen name="profile" options={{ title: "Profile", tabBarLabel: "Profile" }} />
      {/* Hidden from tab bar — accessible via Profile links */}
      <Tabs.Screen name="subscription" options={{ href: null }} />
      <Tabs.Screen name="settings" options={{ href: null }} />
      <Tabs.Screen name="ai-preferences" options={{ href: null }} />
      <Tabs.Screen name="intelligence" options={{ href: null, title: "Market Intelligence" }} />
    </Tabs>
  );
}