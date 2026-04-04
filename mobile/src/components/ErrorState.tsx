import React from 'react';
import { StyleSheet, View, Text, TouchableOpacity } from 'react-native';
import { AlertTriangle, RefreshCcw } from 'lucide-react-native';
import { THEME } from '../constants/theme';

export const ErrorState = ({ message, onRetry }: { message: string, onRetry?: () => void }) => (
  <View style={styles.container}>
    <View style={styles.iconContainer}>
      <AlertTriangle size={32} color="#FF6363" />
    </View>
    <Text style={styles.title}>SYSTEM INTERRUPTION</Text>
    <Text style={styles.message}>{message}</Text>
    {onRetry && (
      <TouchableOpacity style={styles.button} onPress={onRetry}>
        <RefreshCcw size={16} color="#000" />
        <Text style={styles.buttonText}>RETRY DIAGNOSTIC</Text>
      </TouchableOpacity>
    )}
  </View>
);

const styles = StyleSheet.create({
  container: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    padding: 40,
    backgroundColor: THEME.colors.background,
  },
  iconContainer: {
    width: 64,
    height: 64,
    borderRadius: 16,
    backgroundColor: 'rgba(255, 99, 99, 0.1)',
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: 24,
  },
  title: {
    color: '#FFF',
    fontSize: 18,
    fontWeight: '900',
    fontStyle: 'italic',
    letterSpacing: 1,
    marginBottom: 8,
  },
  message: {
    color: THEME.colors.textSecondary,
    fontSize: 14,
    textAlign: 'center',
    lineHeight: 20,
    marginBottom: 32,
  },
  button: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    backgroundColor: THEME.colors.primary,
    paddingHorizontal: 24,
    paddingVertical: 12,
    borderRadius: 12,
  },
  buttonText: {
    color: '#000',
    fontSize: 12,
    fontWeight: 'bold',
  }
});
