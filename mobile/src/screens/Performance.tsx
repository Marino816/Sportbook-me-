import React, { useEffect, useState } from 'react';
import { StyleSheet, View, Text, ScrollView, SafeAreaView, Image, Dimensions, ActivityIndicator } from 'react-native';
import { Zap, TrendingUp, TrendingDown, Target, Activity, LayoutGrid, Info, ChevronRight, BarChart3, PieChart } from 'lucide-react-native';
import { LineChart, BarChart, ProgressChart } from 'react-native-chart-kit';
import { THEME } from '../constants/theme';
import { GlassCard } from '../components/Common';
import { fetchPerformanceStats, PerformanceStats, ApiResponse } from '../lib/api';
import { ErrorState } from '../components/ErrorState';

const screenWidth = Dimensions.get('window').width;

export const PerformanceScreen = () => {
  const [stats, setStats] = useState<PerformanceStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetchPerformanceStats();
      setStats(res.data);
    } catch (e: any) {
      setError(e.message || "Failed to reach analytics node.");
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
        <View style={styles.logoRow}>
          <Zap size={24} color={THEME.colors.primary} fill={THEME.colors.primary} />
          <Text style={styles.logoText}>SPORTSBOOK ME DFS AI</Text>
        </View>
        <Image 
          source={{ uri: 'https://i.pravatar.cc/100?u=perf' }} 
          style={styles.avatar} 
        />
      </View>

      <ScrollView showsVerticalScrollIndicator={false} contentContainerStyle={styles.scrollContent}>
        {/* ROI Header */}
        <View style={styles.roiSection}>
           <Text style={styles.roiLabel}>TOTAL ROI</Text>
           {loading ? (
             <ActivityIndicator color={THEME.colors.primary} style={{ marginVertical: 20 }} />
           ) : (
             <>
               <View style={styles.roiValueRow}>
                  <Text style={styles.roiValue}>{stats?.total_roi || "+0.0%"}</Text>
                  <TrendingUp size={24} color={THEME.colors.primary} />
               </View>
               <Text style={styles.roiPeriod}>LAST 30 DAYS</Text>
             </>
           )}
        </View>

        {/* Secondary Stats */}
        <View style={styles.statsRow}>
           <View style={styles.statBox}>
              <Text style={styles.statLabel}>MAE (ACCURACY)</Text>
              <View style={styles.statContent}>
                <Text style={styles.statValue}>{stats?.ave_error || "4.12"}</Text>
                <View style={styles.improvementBadge}>
                  <Text style={styles.improvementText}>-0.4% improvement</Text>
                </View>
              </View>
           </View>
           <View style={styles.statBox}>
              <Text style={styles.statLabel}>WIN RATE</Text>
              <Text style={styles.statValue}>{stats?.win_rate || "0.0%"}</Text>
           </View>
        </View>

        {/* Performance Velocity Chart */}
        <Text style={styles.sectionTitle}>PERFORMANCE VELOCITY</Text>
        <View style={styles.chartContainer}>
           <LineChart
             data={{
               labels: ["Day 1", "Day 10", "Day 20", "Day 30"],
               datasets: [{ data: [20, 45, 28, 80, 75, 90] }]
             }}
             width={screenWidth - 40}
             height={180}
             chartConfig={lineChartConfig}
             bezier
             style={styles.chart}
             withDots={true}
             withInnerLines={false}
             withOuterLines={false}
             getDotColor={() => THEME.colors.primary}
           />
        </View>

        {/* Projection Error & Efficiency Grid */}
        <View style={styles.widgetGrid}>
           <GlassCard style={styles.widgetSubCard}>
              <View style={styles.widgetHeader}>
                 <Text style={styles.widgetTitle}>PROJECTION ERROR</Text>
                 <Activity size={16} color="#B983FF" />
              </View>
              <View style={styles.barContainer}>
                 {[40, 70, 30, 60, 45].map((h, i) => (
                   <View 
                     key={i} 
                     style={[styles.miniBar, { height: h, backgroundColor: i % 2 === 0 ? '#B983FF' : '#333' }]} 
                   />
                 ))}
              </View>
              <Text style={styles.widgetSubText}>Avg Var: 1.2 pts</Text>
           </GlassCard>

           <GlassCard style={styles.widgetSubCard}>
              <View style={styles.widgetHeader}>
                 <Text style={styles.widgetTitle}>EFFICIENCY</Text>
                 <Zap size={16} color={THEME.colors.primary} />
              </View>
              <View style={styles.gaugeWrapper}>
                 <ProgressChart
                    data={{ data: [0.82] }}
                    width={100}
                    height={100}
                    strokeWidth={10}
                    radius={32}
                    chartConfig={progressChartConfig}
                    hideLegend={true}
                 />
                 <View style={styles.gaugeLabel}>
                   <Text style={styles.gaugeText}>82%</Text>
                 </View>
              </View>
              <Text style={styles.widgetSubText}>Salary Capture</Text>
           </GlassCard>
        </View>

        {/* Accuracy Trends */}
        <Text style={styles.sectionTitle}>ACCURACY TRENDS</Text>
        <View style={styles.trendsList}>
           <TrendBar label="QB" val={stats?.accuracy?.QB || 92} color="#B983FF" />
           <TrendBar label="WR" val={stats?.accuracy?.WR || 78} color={THEME.colors.primary} />
           <TrendBar label="RB" val={stats?.accuracy?.RB || 64} color="#D1D5DB" />
        </View>
      </ScrollView>
    </SafeAreaView>
  );
};

const TrendBar = ({ label, val, color }: any) => (
  <View style={styles.trendRow}>
    <Text style={styles.trendLabel}>{label}</Text>
    <View style={styles.trendBarWrapper}>
       <View style={[styles.trendBar, { width: `${val}%`, backgroundColor: color }]} />
    </View>
    <Text style={styles.trendVal}>{val}%</Text>
  </View>
);

const lineChartConfig = {
  backgroundGradientFrom: THEME.colors.background,
  backgroundGradientTo: THEME.colors.background,
  color: (opacity = 1) => `rgba(0, 255, 157, ${opacity})`,
  labelColor: (opacity = 1) => `rgba(255, 255, 255, ${opacity * 0.4})`,
  strokeWidth: 3,
  propsForBackgroundLines: { strokeDasharray: "" },
};

const progressChartConfig = {
  backgroundGradientFrom: THEME.colors.card,
  backgroundGradientTo: THEME.colors.card,
  color: (opacity = 1) => `rgba(0, 255, 157, ${opacity})`,
};

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
    paddingVertical: 12,
    borderBottomWidth: 1,
    borderBottomColor: 'rgba(255,255,255,0.05)',
  },
  logoRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  logoText: {
    color: THEME.colors.primary,
    fontSize: 20,
    fontWeight: '900',
    fontStyle: 'italic',
  },
  avatar: {
    width: 36,
    height: 36,
    borderRadius: 18,
    borderWidth: 1,
    borderColor: 'rgba(255,255,255,0.2)',
  },
  scrollContent: {
    padding: 20,
    paddingBottom: 40,
  },
  roiSection: {
    alignItems: 'flex-start',
    marginBottom: 32,
    marginTop: 12,
  },
  roiLabel: {
    color: THEME.colors.textSecondary,
    fontSize: 10,
    fontWeight: 'bold',
    letterSpacing: 1,
  },
  roiValueRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
    marginVertical: 4,
  },
  roiValue: {
    color: THEME.colors.primary,
    fontSize: 48,
    fontWeight: '900',
  },
  roiPeriod: {
    color: THEME.colors.textSecondary,
    fontSize: 12,
    fontWeight: 'black',
    letterSpacing: 1,
  },
  statsRow: {
    flexDirection: 'row',
    gap: 16,
    marginBottom: 32,
  },
  statBox: {
    flex: 1,
  },
  statLabel: {
    color: THEME.colors.textSecondary,
    fontSize: 8,
    fontWeight: 'bold',
    letterSpacing: 0.5,
    marginBottom: 8,
  },
  statContent: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  statValue: {
    color: '#FFF',
    fontSize: 24,
    fontWeight: 'bold',
  },
  improvementBadge: {
    backgroundColor: '#00FF9D20',
    paddingHorizontal: 6,
    paddingVertical: 2,
    borderRadius: 4,
  },
  improvementText: {
    color: THEME.colors.primary,
    fontSize: 9,
    fontWeight: 'bold',
  },
  sectionTitle: {
    color: '#FFF',
    fontSize: 12,
    fontWeight: 'black',
    letterSpacing: 2,
    marginBottom: 20,
    marginTop: 8,
  },
  chartContainer: {
    marginBottom: 32,
    marginTop: -10,
  },
  chart: {
    borderRadius: 16,
    paddingRight: 40,
  },
  widgetGrid: {
    flexDirection: 'row',
    gap: 12,
    marginBottom: 32,
  },
  widgetSubCard: {
    flex: 1,
    padding: 16,
  },
  widgetHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 16,
  },
  widgetTitle: {
    color: THEME.colors.textSecondary,
    fontSize: 9,
    fontWeight: 'black',
    letterSpacing: 0.5,
  },
  barContainer: {
    flexDirection: 'row',
    alignItems: 'flex-end',
    justifyContent: 'space-between',
    height: 70,
    marginBottom: 12,
  },
  miniBar: {
    width: 6,
    borderRadius: 2,
  },
  gaugeWrapper: {
    alignItems: 'center',
    justifyContent: 'center',
    height: 70,
    marginBottom: 12,
  },
  gaugeLabel: {
    position: 'absolute',
    alignItems: 'center',
    justifyContent: 'center',
  },
  gaugeText: {
    color: '#FFF',
    fontSize: 16,
    fontWeight: 'bold',
  },
  widgetSubText: {
    color: THEME.colors.textSecondary,
    fontSize: 10,
    fontWeight: 'bold',
  },
  trendsList: {
    gap: 20,
  },
  trendRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 16,
  },
  trendLabel: {
    width: 40,
    color: '#FFF',
    fontSize: 14,
    fontWeight: '900',
  },
  trendBarWrapper: {
    flex: 1,
    height: 8,
    backgroundColor: 'rgba(255,255,255,0.05)',
    borderRadius: 4,
    overflow: 'hidden',
  },
  trendBar: {
    height: '100%',
    borderRadius: 4,
  },
  trendVal: {
    width: 40,
    color: THEME.colors.textSecondary,
    fontSize: 12,
    fontWeight: 'bold',
    textAlign: 'right',
  },
});
