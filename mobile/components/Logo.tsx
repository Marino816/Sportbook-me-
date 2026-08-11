import { Image, View, StyleSheet } from "react-native";

const LOGO_SRC = require("../assets/logo.png");

export function Logo({ size = "md" }: { size?: "sm" | "md" | "lg" }) {
  const dims = { sm: { w: 100, h: 52 }, md: { w: 160, h: 84 }, lg: { w: 220, h: 115 } }[size];
  return (
    <View style={s.container}>
      <Image source={LOGO_SRC} style={{ width: dims.w, height: dims.h }} resizeMode="contain" />
    </View>
  );
}

export function LogoText() {
  return <Logo size="md" />;
}

const s = StyleSheet.create({ container: { alignItems: "center" } });