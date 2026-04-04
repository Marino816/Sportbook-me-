import React, { useEffect, useState } from 'react';
import { StyleSheet, View, Text, ScrollView, TouchableOpacity, SafeAreaView, TextInput, ActivityIndicator } from 'react-native';
import { Search, Filter, ArrowUpDown, ChevronRight, Info } from 'lucide-react-native';
import { THEME } from '../constants/theme';
import { GlassCard } from '../components/Common';
import { fetchProjections, PlayerProjection, ApiResponse } from '../lib/api';
import { ErrorState } from '../components/ErrorState';

export const ProjectionsScreen = () => {
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
      setError(e.message || "Failed to reach projections backend.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  if (error) return <ErrorState message={error} onRetry={load} />;

  return (
    <SafeAreaView style={styles.container}>
      {/* Header */}
      <View style={styles.header}>
        <Text style={styles.headerTitle}>PROJECTIONS</Text>
        <TouchableOpacity style={styles.exportBtn}>
          <Text style={styles.exportText}>EXPORT</Text>
        </TouchableOpacity>
      </View>

      {/* Search & Filters */}
      <View style={styles.filterBar}>
        <View style={styles.searchBox}>
          <Search size={18} color={THEME.colors.textSecondary} />
          <TextInput 
            placeholder="Search players..." 
            placeholderTextColor={THEME.colors.textSecondary}
            style={styles.searchInput}
          />
        </View>
        <TouchableOpacity style={styles.filterBtn}>
          <Filter size={18} color="#FFF" />
        </TouchableOpacity>
      </View>

      {/* Sport Selector */}
      <View style={styles.sportsTabs}>
        {['NBA', 'NFL', 'MLB', 'NHL'].map((sport, i) => (
          <TouchableOpacity key={i} style={[styles.sportTab, i === 0 && styles.sportTabActive]}>
            <Text style={[styles.sportTabText, i === 0 && styles.sportTabTextActive]}>{sport}</Text>
          </TouchableOpacity>
        ))}
      </View>

      {/* Table Headers */}
      <View style={styles.tableHeader}>
        <Text style={[styles.th, { flex: 2 }]}>PLAYER</Text>
        <Text style={styles.th}>SALARY</Text>
        <Text style={[styles.th, { color: THEME.colors.primary }]}>PROJ</Text>
        <Text style={styles.th}>VAL</Text>
      </View>

      <ScrollView showsVerticalScrollIndicator={false}>
        {loading ? (
          <ActivityIndicator color={THEME.colors.primary} style={{ marginTop: 40 }} />
        ) : (
          projections.map((player) => (
            <PlayerRow 
              key={player.id}
              name={player.name} 
              team={player.team} 
              pos={player.roster_position} 
              salary={`$${(player.salary/1000).toFixed(1)}k`}
              proj={player.projected_fp.toFixed(1)}
              value={`${player.value.toFixed(2)}x`}
            />
          ))
        )}
      </ScrollView>
    </SafeAreaView>
  );
};

const PlayerRow = ({ name, team, pos, salary, proj, value }: any) => (
  <View style={styles.row}>
    <View style={[styles.cell, { flex: 2, flexDirection: 'row', alignItems: 'center' }]}>
      <View style={styles.posBadge}><Text style={styles.posText}>{pos}</Text></View>
      <View style={{ marginLeft: 8 }}>
        <Text style={styles.pName}>{name}</Text>
        <Text style={styles.pTeam}>{team}</Text>
      </View>
    </View>
    <Text style={styles.cell}>{salary}</Text>
    <Text style={[styles.cell, { color: THEME.colors.primary, fontWeight: '900' }]}>{proj}</Text>
    <Text style={styles.cell}>{value}</Text>
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
    paddingVertical: 16,
  },
  headerTitle: {
    color: '#FFF',
    fontSize: 20,
    fontWeight: '900',
    fontStyle: 'italic',
    letterSpacing: 1,
  },
  exportBtn: {
    backgroundColor: 'rgba(255,255,255,0.05)',
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 6,
    borderWidth: 1,
    borderColor: 'rgba(255,255,255,0.1)',
  },
  exportText: {
    color: '#FFF',
    fontSize: 10,
    fontWeight: 'bold',
  },
  filterBar: {
    flexDirection: 'row',
    gap: 12,
    paddingHorizontal: 20,
    marginBottom: 16,
  },
  searchBox: {
    flex: 1,
    height: 44,
    backgroundColor: THEME.colors.card,
    borderRadius: 12,
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 16,
    borderWidth: 1,
    borderColor: THEME.colors.border,
  },
  searchInput: {
    flex: 1,
    marginLeft: 10,
    color: '#FFF',
    fontSize: 14,
  },
  filterBtn: {
    width: 44,
    height: 44,
    backgroundColor: THEME.colors.primary,
    borderRadius: 12,
    alignItems: 'center',
    justifyContent: 'center',
  },
  sportsTabs: {
    flexDirection: 'row',
    paddingHorizontal: 20,
    gap: 8,
    marginBottom: 24,
  },
  sportTab: {
    paddingHorizontal: 16,
    paddingVertical: 8,
    borderRadius: 20,
    backgroundColor: 'rgba(255,255,255,0.05)',
  },
  sportTabActive: {
    backgroundColor: 'rgba(0, 255, 157, 0.1)',
    borderWidth: 1,
    borderColor: THEME.colors.primary,
  },
  sportTabText: {
    color: THEME.colors.textSecondary,
    fontSize: 12,
    fontWeight: 'bold',
  },
  sportTabTextActive: {
    color: THEME.colors.primary,
  },
  tableHeader: {
    flexDirection: 'row',
    paddingHorizontal: 25,
    paddingVertical: 12,
    backgroundColor: 'rgba(255,255,255,0.02)',
    borderBottomWidth: 1,
    borderBottomColor: 'rgba(255,255,255,0.05)',
  },
  th: {
    flex: 1,
    color: THEME.colors.textSecondary,
    fontSize: 10,
    fontWeight: 'black',
    letterSpacing: 1,
  },
  row: {
    flexDirection: 'row',
    paddingHorizontal: 25,
    paddingVertical: 16,
    borderBottomWidth: 1,
    borderBottomColor: 'rgba(255,255,255,0.03)',
    alignItems: 'center',
  },
  cell: {
    flex: 1,
    color: '#FFF',
    fontSize: 13,
    fontWeight: '500',
  },
  posBadge: {
    backgroundColor: 'rgba(255,255,255,0.1)',
    paddingHorizontal: 6,
    paddingVertical: 2,
    borderRadius: 4,
    width: 32,
    alignItems: 'center',
  },
  posText: {
    color: THEME.colors.textSecondary,
    fontSize: 9,
    fontWeight: 'bold',
  },
  pName: {
    color: '#FFF',
    fontSize: 14,
    fontWeight: 'bold',
  },
  pTeam: {
    color: THEME.colors.textSecondary,
    fontSize: 10,
    textTransform: 'uppercase',
  }
});
