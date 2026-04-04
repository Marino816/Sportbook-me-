import React, { useEffect, useState } from 'react';
import { StyleSheet, View, Text, TouchableOpacity } from 'react-native';
import { Info } from 'lucide-react-native';
import { THEME } from '../constants/theme';
import { fetchSystemStatus, type SystemStatus } from '../lib/api';

export const DataSourceBadge = () => {
  const [status, setStatus] = useState<SystemStatus | null>(null);

  useEffect(() => {
    async function load() {
      try {
        const res = await fetchSystemStatus();
        if (res.data && res.data.length > 0) {
          setStatus(res.data[0]);
        }
      } catch (e) {
        console.error("Mobile health check failed", e);
      }
    }
    load();
    const interval = setInterval(load, 60000);
    return () => clearInterval(interval);
  }, []);

  if (!status) return null;

  const mode = status.data_source_mode || 'live';
  const color = mode === 'live' ? THEME.colors.primary : mode === 'cached' ? '#FFB800' : '#FF6363';

  return (
    <View style={styles.container}>
      <View style={[styles.badge, { borderColor: color + '40', backgroundColor: color + '10' }]}>
        <View style={[styles.dot, { backgroundColor: color }]} />
        <Text style={[styles.text, { color }]}>
          {mode === 'live' ? 'LIVE DATA' : mode === 'cached' ? 'CACHED' : 'DEMO MODE'}
        </Text>
      </View>
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    position: 'absolute',
    top: 60,
    right: 20,
    zIndex: 100,
  },
  badge: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 10,
    paddingVertical: 5,
    borderRadius: 12,
    borderWidth: 1,
    gap: 6,
  },
  dot: {
    width: 6,
    height: 6,
    borderRadius: 3,
  },
  text: {
    fontSize: 9,
    fontWeight: '900',
    letterSpacing: 1,
    fontStyle: 'italic',
  }
});
