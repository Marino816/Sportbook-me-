import Svg, { Path, G, Defs, LinearGradient, Stop } from "react-native-svg";
import { View, Text, StyleSheet } from "react-native";

export function Logo({ size = "md" }: { size?: "sm" | "md" | "lg" }) {
  const dims = { sm: { w: 90, h: 50, fs1: 20, fs2: 12 },
                 md: { w: 130, h: 70, fs1: 28, fs2: 16 },
                 lg: { w: 180, h: 100, fs1: 38, fs2: 22 } }[size];

  return (
    <View style={s.container}>
      <Svg width={dims.w} height={dims.h} viewBox="0 0 180 100">
        <Defs>
          <LinearGradient id="gold" x1="0" y1="0" x2="1" y2="1">
            <Stop offset="0" stopColor="#d4af37" />
            <Stop offset="1" stopColor="#c9a84c" />
          </LinearGradient>
        </Defs>
        {/* SB text */}
        <G transform="translate(10, 65)">
          <Path
            d="M8 -2 L32 -2 L24 -20 L26 -20 L36 2 L32 2 L36 10 L32 10 L26 -4 L22 -4 L26 10 L22 10 Z"
            fill="url(#gold)" transform="scale(1.6, 1.6) translate(0, -5)"
          />
        </G>
        {/* Upward arrow through SB mark */}
        <G transform="translate(10, 65)">
          <Path
            d="M55 -15 L65 -30 L75 -15 L70 -15 L70 10 L60 10 L60 -15 Z"
            fill="url(#gold)" transform="scale(1.6, 1.6) translate(-5, -5)"
          />
        </G>
        {/* ME text */}
        <G transform="translate(10, 65)">
          <Path
            d="M80 -2 L105 -2 L105 2 L85 2 L85 5 L100 5 L100 8 L85 8 L85 10 L105 10 L105 14 L80 14 Z M108 -2 L113 -2 L113 14 L108 14 Z M118 -2 L125 -2 L135 14 L130 14 L128 9 L120 9 L118 14 L113 14 Z M121 6 L126 6 L124 2 Z"
            fill="url(#gold)" transform="scale(1.6, 1.6) translate(-5, -5)"
          />
        </G>
        {/* DFS.AI text below */}
        <Text style={{ fontSize: dims.fs2, fontWeight: "700", fill: "#f0f6fc", letterSpacing: 2 }} x="28" y="85">
          DFS.AI
        </Text>
      </Svg>
    </View>
  );
}

export function LogoText() {
  return (
    <View style={s.logoRow}>
      <Text style={s.logoSB}>SB ME</Text>
      <View style={s.divider} />
      <Text style={s.logoSub}>DFS.AI</Text>
    </View>
  );
}

const s = StyleSheet.create({
  container: { alignItems: "center" },
  logoRow: { flexDirection: "row", alignItems: "center", gap: 10 },
  logoSB: { fontSize: 24, fontWeight: "900", color: "#c9a84c", letterSpacing: 3, fontStyle: "italic" },
  divider: { width: 1, height: 22, backgroundColor: "#c9a84c40" },
  logoSub: { fontSize: 18, fontWeight: "700", color: "#f0f6fc", letterSpacing: 2 },
});