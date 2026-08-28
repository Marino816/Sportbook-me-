import { View, Text, StyleSheet, ScrollView, TouchableOpacity, Dimensions } from "react-native";
import { useRouter } from "expo-router";
import { Ionicons } from "@expo/vector-icons";

const SCREEN_WIDTH = Dimensions.get("window").width;
const CARD_GAP = 10;
const CARD_PADDING = 20;
const CARD_WIDTH = (SCREEN_WIDTH - CARD_PADDING * 2 - CARD_GAP) / 2;

const TOOLS = [
  {
    id: "live-odds",
    title: "Live Odds",
    subtitle: "Real-time odds & line movements",
    icon: "pulse" as const,
    route: "/(tabs)/market-tools/live-odds",
  },
  {
    id: "compare",
    title: "Compare Odds",
    subtitle: "Best price across all books",
    icon: "git-compare" as const,
    route: "/(tabs)/market-tools/compare",
  },
  {
    id: "bookmakers",
    title: "Bookmakers",
    subtitle: "Live books + 55-platform catalog",
    icon: "business" as const,
    route: "/(tabs)/market-tools/bookmakers",
  },
  {
    id: "player-props",
    title: "Player Props",
    subtitle: "Prop bets & DFS projections",
    icon: "person" as const,
    route: "/(tabs)/market-tools/player-props",
  },
  {
    id: "arbitrage",
    title: "Arbitrage",
    subtitle: "Find & calculate arb bets",
    icon: "calculator" as const,
    route: "/(tabs)/market-tools/arbitrage",
  },
  {
    id: "parlay",
    title: "Parlay Builder",
    subtitle: "Build & price your parlays",
    icon: "layers" as const,
    route: "/(tabs)/market-tools/parlay",
  },
];

export default function MarketToolsHub() {
  const router = useRouter();

  return (
    <View style={s.flex}>
      <ScrollView style={s.scroll} contentContainerStyle={s.container}>
        {/* Header */}
        <View style={s.headerRow}>
          <Ionicons name="trending-up" size={24} color="#c9a84c" />
          <View style={{ flex: 1, marginLeft: 10 }}>
            <Text style={s.title}>Market Tools</Text>
            <Text style={s.subtitle}>
              Live odds, arbitrage, parlays & more — powered by SportsGameOdds
            </Text>
          </View>
        </View>

        {/* Tool Grid */}
        <View style={s.grid}>
          {TOOLS.map((tool) => (
            <TouchableOpacity
              key={tool.id}
              style={s.card}
              activeOpacity={0.7}
              onPress={() => router.push(tool.route as any)}
            >
              <View style={s.cardIconWrap}>
                <Ionicons name={tool.icon} size={32} color="#c9a84c" />
              </View>
              <Text style={s.cardTitle}>{tool.title}</Text>
              <Text style={s.cardSub}>{tool.subtitle}</Text>
            </TouchableOpacity>
          ))}
        </View>

        {/* Full-width CTA */}
        <TouchableOpacity
          style={s.ctaCard}
          activeOpacity={0.8}
          onPress={() => router.push("/(tabs)/intelligence")}
        >
          <Ionicons name="flash" size={24} color="#c9a84c" />
          <View style={{ marginLeft: 12, flex: 1 }}>
            <Text style={s.ctaTitle}>SB ME Intelligence™</Text>
            <Text style={s.ctaText}>
              AI-powered market signals with fantasy-market edge detection
            </Text>
          </View>
          <Ionicons name="chevron-forward" size={20} color="#c9a84c" />
        </TouchableOpacity>
      </ScrollView>
    </View>
  );
}

const s = StyleSheet.create({
  flex: { flex: 1, backgroundColor: "#060b1a" },
  scroll: { flex: 1 },
  container: { padding: 20, paddingBottom: 32 },
  headerRow: {
    flexDirection: "row",
    alignItems: "center",
    marginBottom: 20,
    backgroundColor: "#0a0f24",
    borderRadius: 14,
    padding: 14,
    borderWidth: 1,
    borderColor: "#1e293b",
  },
  title: { fontSize: 20, fontWeight: "800", color: "#c9a84c" },
  subtitle: { fontSize: 12, color: "#94a3b8", marginTop: 2 },
  grid: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: CARD_GAP,
  },
  card: {
    width: CARD_WIDTH,
    backgroundColor: "#0a0f24",
    borderRadius: 16,
    borderWidth: 1,
    borderColor: "#1e293b",
    padding: 16,
    alignItems: "center",
    minHeight: 150,
  },
  cardIconWrap: {
    width: 56,
    height: 56,
    borderRadius: 16,
    backgroundColor: "rgba(201,168,76,0.1)",
    alignItems: "center",
    justifyContent: "center",
    marginBottom: 10,
    borderWidth: 1,
    borderColor: "rgba(201,168,76,0.2)",
  },
  cardTitle: {
    fontSize: 15,
    fontWeight: "700",
    color: "#f0f6fc",
    textAlign: "center",
    marginBottom: 4,
  },
  cardSub: {
    fontSize: 11,
    color: "#94a3b8",
    textAlign: "center",
    lineHeight: 15,
  },
  ctaCard: {
    flexDirection: "row",
    alignItems: "center",
    marginTop: 20,
    backgroundColor: "#0a0f24",
    borderRadius: 14,
    borderWidth: 1,
    borderColor: "rgba(201,168,76,0.25)",
    padding: 16,
  },
  ctaTitle: { fontSize: 15, fontWeight: "700", color: "#c9a84c" },
  ctaText: { fontSize: 12, color: "#94a3b8", marginTop: 2 },
});