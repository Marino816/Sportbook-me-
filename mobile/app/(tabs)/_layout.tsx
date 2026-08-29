import { Ionicons } from "@expo/vector-icons";
import { Tabs } from "expo-router";
import { useAuth } from "../../lib/auth";

export default function TabLayout() {
  const { status } = useAuth();
  // Root layout owns login/dashboard redirects to avoid a replace loop.
  if (status !== "authenticated") return null;

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
      <Tabs.Screen
        name="dashboard"
        options={{
          title: "SB ME",
          tabBarLabel: "Home",
          tabBarIcon: ({ color, size }) => <Ionicons name="home" size={size} color={color} />,
        }}
      />
      <Tabs.Screen
        name="ai-chat"
        options={{
          title: "SB ME AI",
          tabBarLabel: "AI",
          tabBarIcon: ({ color, size }) => <Ionicons name="chatbubble-ellipses" size={size} color={color} />,
        }}
      />
      <Tabs.Screen
        name="optimizer"
        options={{
          title: "Optimizer",
          tabBarLabel: "Optimizer",
          tabBarIcon: ({ color, size }) => <Ionicons name="flame" size={size} color={color} />,
        }}
      />
      <Tabs.Screen
        name="lineups"
        options={{
          title: "Lineups",
          tabBarLabel: "Lineups",
          tabBarIcon: ({ color, size }) => <Ionicons name="list" size={size} color={color} />,
        }}
      />
      <Tabs.Screen
        name="profile"
        options={{
          title: "Profile",
          tabBarLabel: "Profile",
          tabBarIcon: ({ color, size }) => <Ionicons name="person" size={size} color={color} />,
        }}
      />
      <Tabs.Screen name="subscription" options={{ href: null }} />
      <Tabs.Screen name="settings" options={{ href: null }} />
      <Tabs.Screen name="ai-preferences" options={{ href: null }} />
      <Tabs.Screen name="intelligence" options={{ href: null, title: "Market Intel" }} />
      <Tabs.Screen
        name="market-tools"
        options={{
          href: "/(tabs)/market-tools",
          title: "Market Tools",
          tabBarLabel: "Markets",
          tabBarIcon: ({ color, size }) => <Ionicons name="trending-up" size={size} color={color} />,
        }}
      />
    </Tabs>
  );
}