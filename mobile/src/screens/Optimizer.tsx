import React, { useState, useEffect } from 'react';
import { StyleSheet, View, Text, ScrollView, TouchableOpacity, SafeAreaView, Image, ActivityIndicator, Alert } from 'react-native';
import { Zap, LayoutGrid, Lock, Ban, X, ListFilter, Search, Info, CheckCircle2 } from 'lucide-react-native';
import { THEME } from '../constants/theme';
import { GlassCard, NeonButton } from '../components/Common';
import { fetchProjections, runOptimizer, PlayerProjection, LineupResponse, ApiResponse } from '../lib/api';
import { ErrorState } from '../components/ErrorState';

export const OptimizerScreen = () => {
  const [exposure, setExposure] = useState(65);
  const [projections, setProjections] = useState<PlayerProjection[]>([]);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [lineups, setLineups] = useState<LineupResponse[]>([]);
  const [lockedIds, setLockedIds] = useState<number[]>([]);
  const [excludedIds, setExcludedIds] = useState<number[]>([]);
  const [error, setError] = useState<string | null>(null);

  const load = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetchProjections(1);
      setProjections(res.data);
    } catch (e: any) {
      setError(e.message || "Failed to reach optimization node.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  if (error) return <ErrorState message={error} onRetry={load} />;

  const handleGenerate = async () => {
    setGenerating(true);
    try {
      const results = await runOptimizer(1, {
        max_exposure: exposure / 100,
        locked: lockedIds,
        excluded: excludedIds
      });
      setLineups(results.data);
      Alert.alert("Success", `Generated ${results.data.length} optimal lineups!`);
    } catch (error: any) {
      Alert.alert("Optimization Error", error.message || "Could not generate lineups.");
    } finally {
      setGenerating(false);
    }
  };

  const toggleLock = (id: number) => {
    if (lockedIds.includes(id)) {
      setLockedIds(lockedIds.filter(i => i !== id));
    } else {
      setLockedIds([...lockedIds, id]);
      setExcludedIds(excludedIds.filter(i => i !== id));
    }
  };

  const toggleExclude = (id: number) => {
    if (excludedIds.includes(id)) {
      setExcludedIds(excludedIds.filter(i => i !== id));
    } else {
      setExcludedIds([...excludedIds, id]);
      setLockedIds(lockedIds.filter(i => i !== id));
    }
  };

  return (
    <SafeAreaView style={styles.container}>
      <View style={styles.header}>
        <View style={styles.logoRow}>
          <Zap size={24} color={THEME.colors.primary} fill={THEME.colors.primary} />
          <Text style={styles.logoText}>SPORTSBOOK ME DFS AI</Text>
        </View>
        <Image 
          source={{ uri: 'https://i.pravatar.cc/100?u=user1' }} 
          style={styles.avatar} 
        />
      </View>

      <ScrollView showsVerticalScrollIndicator={false} contentContainerStyle={styles.scrollContent}>
        <View style={styles.sectionHeader}>
          <Text style={styles.sectionTitle}>CONTEST STRATEGY</Text>
          <Text style={styles.versionText}>ALGORITHM V4.2</Text>
        </View>

        {/* Strategy Selector */}
        <View style={styles.strategyRow}>
          <View style={styles.strategyOption}>
            <Text style={styles.strategyName}>CASH</Text>
            <Text style={styles.strategySub}>SAFE/FLOOR</Text>
          </View>
          <View style={[styles.strategyOption, styles.strategyOptionActive]}>
            <Text style={[styles.strategyName, { color: '#000' }]}>GPP</Text>
            <Text style={[styles.strategySub, { color: 'rgba(0,0,0,0.6)' }]}>UPSIDE</Text>
          </View>
          <View style={styles.strategyOption}>
            <Text style={styles.strategyName}>150-MAX</Text>
            <Text style={styles.strategySub}>MME</Text>
          </View>
        </View>

        {/* Exposure Slider */}
        <View style={styles.sliderContainer}>
          <View style={styles.sliderLabelRow}>
            <Text style={styles.sliderLabel}>Global Max Exposure</Text>
            <Text style={styles.sliderValue}>{exposure}%</Text>
          </View>
          <View style={styles.track}>
            <View style={[styles.progress, { width: `${exposure}%` }]} />
            <View style={[styles.thumb, { left: `${exposure}%` }]} />
          </View>
          <View style={styles.tickRow}>
            <Text style={styles.tick}>10%</Text>
            <Text style={styles.tick}>100%</Text>
          </View>
        </View>

        {/* Advanced Constraints */}
        <View style={styles.constraintsCard}>
          <View style={styles.constraintsHeader}>
            <LayoutGrid size={18} color={THEME.colors.textSecondary} />
            <Text style={styles.constraintsTitle}>Advanced Constraints</Text>
          </View>
          <ScrollView horizontal showsHorizontalScrollIndicator={false} style={styles.constraintsRow}>
            <ConstraintBox label="QB-WR Stacking" value="At least 1 WR" />
            <ConstraintBox label="Run Back" value="Enabled" />
            <ConstraintBox label="Late Swap" value="Auto-Active" />
          </ScrollView>
        </View>

        {/* Player Pool */}
        <View style={styles.poolHeader}>
          <Text style={styles.poolTitle}>PLAYER POOL</Text>
          <View style={styles.poolActions}>
            <ListFilter size={20} color={THEME.colors.text} />
            <Search size={20} color={THEME.colors.text} />
          </View>
        </View>

        {loading ? (
          <ActivityIndicator color={THEME.colors.primary} style={{ marginTop: 40 }} />
        ) : (
          projections.map((player) => (
            <PoolRow 
               key={player.id}
               name={player.name} 
               team={player.team} 
               salary={`$${player.salary.toLocaleString()}`} 
               proj={player.projected_fp.toFixed(1)} 
               exposure={lineups.length > 0 ? "100%" : ""} 
               isLocked={lockedIds.includes(player.id)} 
               isExcluded={excludedIds.includes(player.id)}
               isOptimal={player.value > 5.5}
               onLock={() => toggleLock(player.id)}
               onExclude={() => toggleExclude(player.id)}
            />
          ))
        )}

        <View style={styles.engineStatus}>
          <View style={[styles.statusDot, { backgroundColor: generating ? '#FFB800' : THEME.colors.primary }]} />
          <Text style={styles.statusLabel}>{generating ? 'OPTIMIZING...' : lineups.length > 0 ? 'LINEUPS READY' : 'ENGINE IDLE'}</Text>
          <Text style={styles.statusDetail}>
            {generating ? 'RUNNING PuLP SOLVER...' : lineups.length > 0 ? `${lineups.length} LINEUPS GENERATED` : 'READY FOR 150-MAX SIMULATION'}
          </Text>
        </View>
      </ScrollView>

      {/* Generate Button Container */}
      <View style={styles.bottomActions}>
          <NeonButton 
            title={generating ? "GENERATING..." : lineups.length > 0 ? "RE-GENERATE LINEUPS" : "GENERATE 150 LINEUPS"} 
            onPress={handleGenerate} 
            icon={generating ? <ActivityIndicator size="small" color="#000" /> : <Zap size={20} color="#000" fill="#000" />}
            style={styles.generateButton}
          />
      </View>
    </SafeAreaView>
  );
};

const ConstraintBox = ({ label, value }: any) => (
  <View style={styles.constraintBox}>
    <View style={styles.constraintBar} />
    <View>
      <Text style={styles.constraintLabel}>{label}</Text>
      <Text style={styles.constraintValue}>{value}</Text>
    </View>
  </View>
);

const PoolRow = ({ name, team, salary, proj, exposure, isLocked, isExcluded, isOptimal, onLock, onExclude }: any) => (
  <View style={[styles.poolRow, isOptimal && styles.poolRowOptimal, isExcluded && { opacity: 0.5 }]}>
    <View style={styles.playerInfo}>
       <View style={[styles.avatarPlaceholder, isExcluded && { opacity: 0.2 }]}>
         {isLocked && <View style={styles.lockOverlay}><Lock size={12} color="#000" fill="#000" /></View>}
       </View>
       <View>
         <View style={styles.nameRow}>
           {isOptimal && <View style={styles.valueBadge}><Text style={styles.valueBadgeText}>VALUE</Text></View>}
           <Text style={[styles.playerName, isExcluded && { textDecorationLine: 'line-through' }]}>{name}</Text>
           <Text style={styles.playerTeam}>{team}</Text>
         </View>
         <View style={styles.playerStats}>
           <View style={styles.salaryBadge}><Text style={styles.salaryText}>{salary}</Text></View>
           <Text style={styles.playerProj}>Proj: {proj}</Text>
         </View>
       </View>
    </View>

    <View style={styles.poolRight}>
       {isExcluded ? (
         <TouchableOpacity onPress={onExclude} style={styles.removeCircle}>
           <X size={16} color="#FF6363" />
         </TouchableOpacity>
       ) : (
         <View style={styles.actionRow}>
            <TouchableOpacity 
              onPress={onLock} 
              style={[styles.actionCircle, isLocked && { backgroundColor: THEME.colors.primary, borderColor: THEME.colors.primary }]}
            >
              <Lock size={16} color={isLocked ? "#000" : "#FFF"} />
            </TouchableOpacity>
            <TouchableOpacity 
              onPress={onExclude} 
              style={styles.actionCircle}
            >
              <Ban size={16} color="#FFF" />
            </TouchableOpacity>
         </View>
       )}
    </View>
  </View>
);

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: THEME.colors.background,
  },
  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingHorizontal: 20,
    paddingVertical: 10,
  },
  logoRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  logoText: {
    color: THEME.colors.text,
    fontSize: 20,
    fontWeight: '900',
    fontStyle: 'italic',
  },
  avatar: {
    width: 40,
    height: 40,
    borderRadius: 20,
    borderWidth: 1,
    borderColor: '#FFF',
  },
  scrollContent: {
    padding: THEME.spacing.md,
    paddingBottom: 120,
  },
  sectionHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginTop: 20,
    marginBottom: 20,
  },
  sectionTitle: {
    color: '#FFF',
    fontSize: 20,
    fontWeight: 'bold',
  },
  versionText: {
    color: THEME.colors.textSecondary,
    fontSize: 10,
    fontWeight: 'bold',
    letterSpacing: 1,
  },
  strategyRow: {
    flexDirection: 'row',
    gap: 12,
    marginBottom: 32,
  },
  strategyOption: {
    flex: 1,
    backgroundColor: THEME.colors.card,
    borderRadius: 8,
    padding: 12,
    borderWidth: 1,
    borderColor: THEME.colors.border,
    alignItems: 'center',
  },
  strategyOptionActive: {
    backgroundColor: THEME.colors.primary,
    borderColor: THEME.colors.primary,
    shadowColor: THEME.colors.primary,
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.3,
    shadowRadius: 10,
  },
  strategyName: {
    color: '#FFF',
    fontSize: 14,
    fontWeight: 'bold',
  },
  strategySub: {
    color: THEME.colors.textSecondary,
    fontSize: 8,
    fontWeight: 'bold',
    marginTop: 4,
  },
  sliderContainer: {
    backgroundColor: THEME.colors.card,
    borderRadius: 16,
    padding: 20,
    marginBottom: 32,
  },
  sliderLabelRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 16,
  },
  sliderLabel: {
    color: '#FFF',
    fontSize: 16,
    fontWeight: '500',
  },
  sliderValue: {
    color: THEME.colors.primary,
    fontSize: 18,
    fontWeight: '900',
  },
  track: {
    height: 6,
    backgroundColor: '#333',
    borderRadius: 3,
    position: 'relative',
  },
  progress: {
    height: 6,
    backgroundColor: THEME.colors.primary,
    borderRadius: 3,
  },
  thumb: {
    width: 20,
    height: 20,
    backgroundColor: THEME.colors.primary,
    borderRadius: 10,
    position: 'absolute',
    top: -7,
    marginLeft: -10,
    borderWidth: 3,
    borderColor: '#000',
  },
  tickRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    marginTop: 12,
  },
  tick: {
    color: THEME.colors.textSecondary,
    fontSize: 12,
  },
  constraintsCard: {
    backgroundColor: THEME.colors.card,
    borderRadius: 16,
    paddingVertical: 20,
    paddingLeft: 20,
    marginBottom: 32,
  },
  constraintsHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    marginBottom: 20,
  },
  constraintsTitle: {
    color: '#FFF',
    fontSize: 18,
    fontWeight: 'bold',
  },
  constraintsRow: {
    flexDirection: 'row',
  },
  constraintBox: {
    width: 140,
    height: 64,
    backgroundColor: THEME.colors.background,
    borderRadius: 8,
    marginRight: 12,
    flexDirection: 'row',
    alignItems: 'center',
    padding: 12,
  },
  constraintBar: {
    width: 3,
    height: '100%',
    backgroundColor: THEME.colors.primary,
    borderRadius: 2,
    marginRight: 12,
  },
  constraintLabel: {
    color: THEME.colors.textSecondary,
    fontSize: 10,
    fontWeight: 'bold',
  },
  constraintValue: {
    color: '#FFF',
    fontSize: 12,
    fontWeight: 'bold',
    marginTop: 4,
  },
  poolHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 24,
  },
  poolTitle: {
    color: '#FFF',
    fontSize: 20,
    fontWeight: 'bold',
  },
  poolActions: {
    flexDirection: 'row',
    gap: 16,
  },
  poolRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingVertical: 16,
    borderBottomWidth: 1,
    borderBottomColor: 'rgba(255,255,255,0.05)',
  },
  poolRowOptimal: {
    borderWidth: 1,
    borderColor: 'rgba(0, 255, 157, 0.2)',
    borderRadius: 12,
    marginTop: 8,
    paddingHorizontal: 12,
    backgroundColor: 'rgba(0, 255, 157, 0.05)',
  },
  playerInfo: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 16,
  },
  avatarPlaceholder: {
    width: 48,
    height: 48,
    borderRadius: 8,
    backgroundColor: THEME.colors.card,
    position: 'relative',
  },
  lockOverlay: {
    position: 'absolute',
    bottom: -4,
    right: -4,
    width: 22,
    height: 22,
    borderRadius: 11,
    backgroundColor: THEME.colors.primary,
    alignItems: 'center',
    justifyContent: 'center',
    borderWidth: 2,
    borderColor: '#000',
  },
  nameRow: {
    gap: 2,
  },
  playerName: {
    color: '#FFF',
    fontSize: 16,
    fontWeight: 'bold',
  },
  playerTeam: {
    color: THEME.colors.textSecondary,
    fontSize: 10,
  },
  playerStats: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    marginTop: 6,
  },
  salaryBadge: {
    backgroundColor: THEME.colors.card,
    paddingHorizontal: 6,
    paddingVertical: 2,
    borderRadius: 4,
  },
  salaryText: {
    color: THEME.colors.primary,
    fontSize: 12,
    fontWeight: 'bold',
  },
  playerProj: {
    color: THEME.colors.textSecondary,
    fontSize: 12,
  },
  poolRight: {
    alignItems: 'flex-end',
  },
  exposureCol: {
    alignItems: 'flex-end',
    gap: 4,
  },
  exposureLabel: {
    color: THEME.colors.textSecondary,
    fontSize: 10,
    fontWeight: 'bold',
  },
  exposureVal: {
    fontSize: 16,
    fontWeight: 'bold',
  },
  actionRow: {
    flexDirection: 'row',
    gap: 12,
  },
  actionCircle: {
    width: 36,
    height: 36,
    borderRadius: 18,
    backgroundColor: THEME.colors.card,
    alignItems: 'center',
    justifyContent: 'center',
    borderWidth: 1,
    borderColor: THEME.colors.border,
  },
  removeCircle: {
     width: 36,
     height: 36,
     borderRadius: 18,
     backgroundColor: 'rgba(255, 99, 99, 0.1)',
     alignItems: 'center',
     justifyContent: 'center',
  },
  valueBadge: {
    backgroundColor: '#5C3BFF',
    paddingHorizontal: 6,
    paddingVertical: 2,
    borderRadius: 4,
    alignSelf: 'flex-start',
    marginBottom: 2,
  },
  valueBadgeText: {
    color: '#FFF',
    fontSize: 8,
    fontWeight: 'bold',
  },
  exposureBar: {
    width: 48,
    height: 4,
    backgroundColor: '#333',
    borderRadius: 2,
    marginTop: 4,
    overflow: 'hidden',
  },
  exposureProgress: {
    height: '100%',
    backgroundColor: '#5844FF',
  },
  engineStatus: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
    marginTop: 32,
  },
  statusDot: {
    width: 8,
    height: 8,
    borderRadius: 4,
    backgroundColor: THEME.colors.primary,
  },
  statusLabel: {
    color: '#FFF',
    fontSize: 14,
    fontWeight: 'bold',
  },
  statusDetail: {
    color: THEME.colors.textSecondary,
    fontSize: 10,
    fontWeight: 'bold',
    flex: 1,
    textAlign: 'right',
  },
  bottomActions: {
    position: 'absolute',
    bottom: 0,
    left: 0,
    right: 0,
    backgroundColor: THEME.colors.background,
    padding: 20,
    borderTopWidth: 1,
    borderTopColor: THEME.colors.border,
  },
  generateButton: {
    shadowColor: THEME.colors.primary,
    shadowOffset: { width: 0, height: 10 },
    shadowOpacity: 0.5,
    shadowRadius: 20,
  }
});
