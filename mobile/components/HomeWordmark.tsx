import { StyleSheet, Text, View } from "react-native";

/** Horizontal Sportbook ME DFS AI wordmark. Typographic stand-in for the owner-approved header (IMG_3229). */
export function HomeWordmark() {
  return (
    <View accessible accessibilityRole="header" accessibilityLabel="Sportbook ME DFS AI" style={styles.wrap}>
      <View style={styles.row}>
        <Text style={styles.sportbook}>Sportbook</Text>
        <View style={styles.meCol}>
          <View style={styles.meBadge}>
            <Text style={styles.meLetter}>ME</Text>
          </View>
          <Text style={styles.dfs}>DFS AI</Text>
        </View>
      </View>
    </View>
  );
}

const GOLD = "#c9a84c";

const styles = StyleSheet.create({
  wrap: { flexShrink: 1 },
  row: { flexDirection: "row", alignItems: "flex-end", gap: 8 },
  sportbook: {
    color: GOLD,
    fontSize: 26,
    fontWeight: "800",
    fontStyle: "italic",
    letterSpacing: 0.4,
    paddingBottom: 14,
  },
  meCol: { alignItems: "center", gap: 3 },
  meBadge: {
    backgroundColor: GOLD,
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: 4,
    minWidth: 44,
    alignItems: "center",
    justifyContent: "center",
  },
  meLetter: {
    color: "#000000",
    fontSize: 16,
    fontWeight: "900",
    letterSpacing: 1,
  },
  dfs: {
    color: GOLD,
    fontSize: 11,
    fontWeight: "800",
    letterSpacing: 2,
  },
});
