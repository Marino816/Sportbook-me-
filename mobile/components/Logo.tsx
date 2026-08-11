import Svg, { Path, G, Defs, LinearGradient, Stop, Text as SvgText } from "react-native-svg";
import { View, StyleSheet } from "react-native";

export function Logo({ size = "md" }: { size?: "sm" | "md" | "lg" }) {
  const dims = { sm: { w: 110, h: 60 },
                 md: { w: 160, h: 85 },
                 lg: { w: 220, h: 120 } }[size];

  return (
    <View style={s.container}>
      <Svg width={dims.w} height={dims.h} viewBox="0 0 240 120">
        <Defs>
          <LinearGradient id="goldGrad" x1="0" y1="0" x2="1" y2="1">
            <Stop offset="0" stopColor="#f0d060" />
            <Stop offset="0.4" stopColor="#c9a84c" />
            <Stop offset="0.7" stopColor="#b8922e" />
            <Stop offset="1" stopColor="#c9a84c" />
          </LinearGradient>
          <LinearGradient id="goldShine" x1="0" y1="0" x2="0" y2="1">
            <Stop offset="0" stopColor="#f5e6a0" />
            <Stop offset="0.5" stopColor="#c9a84c" />
            <Stop offset="1" stopColor="#8a6b20" />
          </LinearGradient>
        </Defs>

        {/* "SB" bold lettering with integrated upward arrow */}
        <G transform="translate(10, 20)">
          {/* S — curved gold */}
          <Path
            d="M5 28 L5 20 Q5 4 25 4 Q40 4 40 16 Q40 26 22 26 L5 26 Q5 32 20 32 Q35 32 40 36 Q40 42 20 42 Q5 42 5 30"
            fill="none" stroke="url(#goldGrad)" strokeWidth="4.5" strokeLinecap="round" strokeLinejoin="round"
            transform="scale(1.3)"
          />
          {/* B — bold gold */}
          <Path
            d="M52 4 L52 38 M52 4 L70 4 Q82 4 82 16 Q82 26 70 26 L52 26 M52 26 L74 26 Q85 26 85 38 L85 42 L52 42"
            fill="none" stroke="url(#goldGrad)" strokeWidth="4.5" strokeLinecap="round" strokeLinejoin="round"
            transform="scale(1.3)"
          />
        </G>

        {/* Upward market arrow — integrated through the SB mark */}
        <G transform="translate(100, 15)">
          <Path
            d="M28 50 L38 24 L48 50 L44 50 L44 58 L32 58 L32 50 Z"
            fill="url(#goldShine)"
          />
          {/* Arrow head accent lines */}
          <Path
            d="M28 50 L38 30 L48 50"
            fill="none" stroke="url(#goldGrad)" strokeWidth="2"
          />
        </G>

        {/* "ME" bold gold */}
        <G transform="translate(160, 20)">
          <Path
            d="M2 4 L18 4 L2 22 L18 22 L2 38 L20 38"
            fill="none" stroke="url(#goldGrad)" strokeWidth="4.5" strokeLinecap="round" strokeLinejoin="round"
            transform="scale(1.3)"
          />
          <Path
            d="M28 4 L28 38 L44 38"
            fill="none" stroke="url(#goldGrad)" strokeWidth="4.5" strokeLinecap="round" strokeLinejoin="round"
            transform="scale(1.3)"
          />
        </G>

        {/* "DFS.AI" white-gold text below */}
        <SvgText
          x="20" y="102"
          fill="#d4af37"
          fontWeight="700"
          letterSpacing={3}
          fontSize={16}
        >
          DFS.AI
        </SvgText>
      </Svg>
    </View>
  );
}

export function LogoText() {
  return <Logo size="md" />;
}

const s = StyleSheet.create({
  container: { alignItems: "center", justifyContent: "center" },
});