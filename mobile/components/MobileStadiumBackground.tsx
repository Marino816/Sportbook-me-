import type { ReactNode } from "react";
import { ImageBackground, StyleSheet, View } from "react-native";

const STADIUM = require("../assets/stadium-night.jpg");

type Props = {
  children: ReactNode;
};

export function MobileStadiumBackground({ children }: Props) {
  return (
    <View style={styles.root} testID="mobile-stadium-background">
      <ImageBackground source={STADIUM} style={styles.plate} resizeMode="cover" />
      <View style={styles.wash} pointerEvents="none" />
      <View style={styles.content}>{children}</View>
    </View>
  );
}

const styles = StyleSheet.create({
  root: {
    flex: 1,
    backgroundColor: "#060b1a",
    overflow: "hidden",
  },
  plate: {
    ...StyleSheet.absoluteFillObject,
    width: "100%",
    height: "100%",
  },
  wash: {
    ...StyleSheet.absoluteFillObject,
    backgroundColor: "rgba(6, 11, 26, 0.42)",
  },
  content: {
    flex: 1,
  },
});
