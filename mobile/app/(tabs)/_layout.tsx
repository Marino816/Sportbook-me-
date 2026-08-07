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
    }}>
      <Tabs.Screen name="dashboard" options={{ title: "Dashboard", tabBarLabel: "Home" }} />
      <Tabs.Screen name="ai-chat" options={{ title: "SB ME AI", tabBarLabel: "AI" }} />
      <Tabs.Screen name="optimizer" options={{ title: "Optimizer", tabBarLabel: "Optimizer" }} />
      <Tabs.Screen name="subscription" options={{ title: "Billing", tabBarLabel: "Billing" }} />
      <Tabs.Screen name="profile" options={{ title: "Profile", tabBarLabel: "Profile" }} />
      <Tabs.Screen name="settings" options={{ title: "Settings", tabBarLabel: "Settings" }} />
    </Tabs>
  );
}