import { Stack } from "expo-router";
import { OptimizerSessionProvider } from "../../../lib/optimizer-session";

export default function OptimizerStackLayout() {
  return (
    <OptimizerSessionProvider>
      <Stack
        screenOptions={{
          headerShown: false,
          contentStyle: { backgroundColor: "#060b1a" },
          animation: "slide_from_right",
        }}
      >
        <Stack.Screen name="index" />
        <Stack.Screen name="builder" />
        <Stack.Screen name="players" />
        <Stack.Screen name="result" />
      </Stack>
    </OptimizerSessionProvider>
  );
}
