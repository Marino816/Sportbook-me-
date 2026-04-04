import React, { useEffect, useState } from 'react';
import { StyleSheet, View, Text, ScrollView, TouchableOpacity, SafeAreaView, Image, ActivityIndicator } from 'react-native';
import { Zap, AlertTriangle, ChevronRight, LayoutGrid, BarChart3, Activity as ActivityIcon, Users } from 'lucide-react-native';
import { THEME } from '../constants/theme';
import { GlassCard, NeonButton } from '../components/Common';
import { fetchProjections, PlayerProjection, ApiResponse } from '../lib/api';
import { ErrorState } from '../components/ErrorState';

export const HomeScreen = ({ navigation }: any) => {
  const [projections, setProjections] = useState<PlayerProjection[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetchProjections(1);
      setProjections(res.data);
    } catch (e: any) {
      setError(e.message || "Failed to reach system node.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  if (error) return <ErrorState message={error} onRetry={load} />;

  const valuePicks = projections.filter(p => p.value > 5.5).slice(0, 3);

  return (
    <SafeAreaView style={styles.container}>
      <ScrollView showsVerticalScrollIndicator={false} contentContainerStyle={styles.scrollContent}>
        {/* Top Branding */}
        <View style={styles.branding}>
          <Zap size={24} color={THEME.colors.primary} fill={THEME.colors.primary} />
          <Text style={styles.brandingText}>SPORTSBOOK ME DFS AI</Text>
        </View>

        {/* Critical Alert Banner */}
        <View style={styles.alertBanner}>
          <AlertTriangle size={18} color="#FF7A00" />
          <Text style={styles.alertText}>CRITICAL: G. Antetokounmpo (MIL) OUT</Text>
        </View>

        {/* Home Header */}
        <View style={styles.header}>
          <Text style={styles.headerSub}>GOOD MORNING, SHARK</Text>
          <Text style={styles.headerTitle}>OPTIMIZE YOUR {'\n'}SUNDAY SLATE</Text>
        </View>

        {/* Active Slates */}
        <View style={styles.sectionHeader}>
          <Text style={styles.sectionTitle}>ACTIVE SLATES</Text>
          <TouchableOpacity><Text style={styles.viewAll}>VIEW ALL</Text></TouchableOpacity>
        </View>

        <ScrollView horizontal showsHorizontalScrollIndicator={false} style={styles.slatesRow}>
          <SlateCard sport="NBA" site="DraftKings" games={8} time="7:00 PM" isActive />
          <SlateCard sport="NFL" site="FanDuel" games={12} time="1:00 PM" />
          <SlateCard sport="MLB" site="DraftKings" games={15} time="10:05 PM" />
        </ScrollView>

        {/* Top Value Picks */}
        <Text style={styles.sectionTitle}>AI VALUE PICKS</Text>
        {loading ? (
          <ActivityIndicator color={THEME.colors.primary} style={{ marginVertical: 20 }} />
        ) : (
          valuePicks.map((player, index) => (
            <ValuePickCard 
              key={player.id}
              name={player.name} 
              team={player.team} 
              proj={player.projected_fp.toFixed(1)} 
              value={`${player.value.toFixed(2)}x`} 
              isTop={index === 0}
            />
          ))
        )}

        <NeonButton 
          title="LAUNCH LINEUP OPTIMIZER" 
          onPress={() => navigation.navigate('Optimizer')} 
          style={styles.mainAction}
          icon={<Zap size={20} color="#000" fill="#000" />}
        />
      </ScrollView>
    </SafeAreaView>
  );
};

const SlateCard = ({ sport, site, games, time, isActive }: any) => (
  <GlassCard style={[styles.slateCard, isActive ? styles.slateCardActive : undefined]}>
    <View style={styles.slateHeader}>
      <Text style={styles.slateSport}>{sport}</Text>
      <View style={[styles.siteBadge, { backgroundColor: isActive ? THEME.colors.primary : '#272A35' }]}>
        <Text style={[styles.siteText, { color: isActive ? '#000' : '#FFF' }]}>{site}</Text>
      </View>
    </View>
    <Text style={styles.slateGames}>{games} Games</Text>
    <Text style={styles.slateTime}>Lock: {time}</Text>
  </GlassCard>
);

const ValuePickCard = ({ name, team, proj, value, isTop }: any) => (
  <View style={styles.pickCard}>
    <View style={styles.pickLeft}>
      <View style={styles.playerAvatar} />
      <View>
        <Text style={styles.playerName}>{name}</Text>
        <Text style={styles.playerMeta}>{team} • {isTop ? 'TOP VALUE' : 'HIGH VALUE'}</Text>
      </View>
    </View>
    <View style={styles.pickRight}>
      <View style={styles.pickStat}>
         <Text style={styles.statLabel}>PROJ</Text>
         <Text style={styles.statValue}>{proj}</Text>
      </View>
      <View style={styles.pickStat}>
         <Text style={styles.statLabel}>VAL</Text>
         <Text style={[styles.statValue, { color: THEME.colors.primary }]}>{value}</Text>
      </View>
      <ChevronRight size={20} color={THEME.colors.textSecondary} />
    </View>
  </View>
);

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: THEME.colors.background,
  },
  scrollContent: {
    padding: THEME.spacing.md,
    paddingBottom: 40,
  },
  branding: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    marginTop: 10,
    marginBottom: 20,
  },
  brandingText: {
    color: '#FFF',
    fontSize: 16,
    fontWeight: '900',
    fontStyle: 'italic',
  },
  alertBanner: {
    backgroundColor: '#FF7A0020',
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
    padding: 12,
    borderRadius: 8,
    borderWidth: 1,
    borderColor: '#FF7A0040',
    marginBottom: 32,
  },
  alertText: {
    color: '#FF7A00',
    fontSize: 12,
    fontWeight: 'bold',
  },
  header: {
    marginBottom: 32,
  },
  headerSub: {
    color: THEME.colors.textSecondary,
    fontSize: 12,
    fontWeight: 'bold',
    letterSpacing: 2,
  },
  headerTitle: {
    color: '#FFF',
    fontSize: 32,
    fontWeight: '900',
    lineHeight: 32,
    marginTop: 8,
  },
  sectionHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 16,
  },
  sectionTitle: {
    color: THEME.colors.textSecondary,
    fontSize: 12,
    fontWeight: 'bold',
    letterSpacing: 1,
  },
  viewAll: {
    color: THEME.colors.primary,
    fontSize: 10,
    fontWeight: 'bold',
  },
  slatesRow: {
    marginBottom: 32,
  },
  slateCard: {
    width: 140,
    padding: 16,
    marginRight: 12,
  },
  slateCardActive: {
    borderColor: THEME.colors.primary,
  },
  slateHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 12,
  },
  slateSport: {
    color: '#FFF',
    fontSize: 18,
    fontWeight: 'bold',
  },
  siteBadge: {
    paddingHorizontal: 6,
    paddingVertical: 2,
    borderRadius: 4,
  },
  siteText: {
    fontSize: 8,
    fontWeight: 'bold',
  },
  slateGames: {
    color: '#FFF',
    fontSize: 14,
    fontWeight: '500',
  },
  slateTime: {
    color: THEME.colors.textSecondary,
    fontSize: 10,
    marginTop: 4,
  },
  pickCard: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingVertical: 16,
    borderBottomWidth: 1,
    borderBottomColor: 'rgba(255,255,255,0.05)',
  },
  pickLeft: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
  },
  playerAvatar: {
    width: 44,
    height: 44,
    borderRadius: 22,
    backgroundColor: '#272A35',
  },
  playerName: {
    color: '#FFF',
    fontSize: 16,
    fontWeight: 'bold',
  },
  playerMeta: {
    color: THEME.colors.textSecondary,
    fontSize: 10,
  },
  pickRight: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 16,
  },
  pickStat: {
    alignItems: 'center',
  },
  statLabel: {
    color: THEME.colors.textSecondary,
    fontSize: 8,
    fontWeight: 'bold',
  },
  statValue: {
    color: '#FFF',
    fontSize: 14,
    fontWeight: 'bold',
  },
  mainAction: {
    marginTop: 32,
    paddingVertical: 18,
  }
});
