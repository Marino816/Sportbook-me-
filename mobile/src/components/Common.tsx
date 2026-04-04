import React from 'react';
import { StyleSheet, View, ViewStyle, TouchableOpacity, Text, TextStyle, StyleProp } from 'react-native';
import { LinearGradient } from 'expo-linear-gradient';
import { THEME } from '../constants/theme';

interface GlassCardProps {
  children: React.ReactNode;
  style?: StyleProp<ViewStyle>;
}

export const GlassCard = ({ children, style }: GlassCardProps) => (
  <View style={[styles.glassCard, style]}>
    {children}
  </View>
);

interface NeonButtonProps {
  title: string;
  onPress: () => void;
  icon?: React.ReactNode;
  style?: StyleProp<ViewStyle>;
  textStyle?: StyleProp<TextStyle>;
}

export const NeonButton = ({ title, onPress, icon, style, textStyle }: NeonButtonProps) => (
  <TouchableOpacity onPress={onPress} activeOpacity={0.8}>
    <LinearGradient
      colors={[THEME.colors.primary, '#00C97B']}
      start={{ x: 0, y: 0 }}
      end={{ x: 1, y: 0 }}
      style={[styles.neonButton, style]}
    >
      {icon && <View style={styles.buttonIcon}>{icon}</View>}
      <Text style={[styles.buttonText, textStyle]}>{title}</Text>
    </LinearGradient>
  </TouchableOpacity>
);

const styles = StyleSheet.create({
  glassCard: {
    backgroundColor: THEME.colors.card,
    borderRadius: 16,
    padding: THEME.spacing.md,
    borderWidth: 1,
    borderColor: THEME.colors.border,
  },
  neonButton: {
    borderRadius: 12,
    paddingVertical: 14,
    paddingHorizontal: 24,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    shadowColor: THEME.colors.primary,
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.3,
    shadowRadius: 8,
    elevation: 4,
  },
  buttonText: {
    color: '#000',
    fontSize: 16,
    fontWeight: 'bold',
    textTransform: 'uppercase',
    letterSpacing: 1.2,
  },
  buttonIcon: {
    marginRight: 8,
  }
});
