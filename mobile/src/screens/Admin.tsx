import React from 'react';
import { StyleSheet, View, Text, ScrollView, TouchableOpacity, SafeAreaView, Dimensions } from 'react-native';
import { Search, Settings, TrendingUp, Users, PieChart, Activity, UserPlus, CreditCard, RefreshCw, ChevronRight, Globe, AlertCircle } from 'lucide-react-native';
import { LineChart, ProgressChart } from 'react-native-chart-kit';
import { THEME } from '../constants/theme';
import { GlassCard } from '../components/Common';

const screenWidth = Dimensions.get('window').width;

export const AdminScreen = () => {
  return (
    <SafeAreaView style={styles.container}>
      <View style={styles.header}>
        <View style={styles.avatar} />
        <Text style={styles.headerTitle}>ELECTRIC ARENA</Text>
        <View style={styles.headerActions}>
           <Search size={22} color={THEME.colors.text} />
           <Settings size={22} color={THEME.colors.primary} />
        </View>
      </View>

      <ScrollView showsVerticalScrollIndicator={false} contentContainerStyle={styles.scrollContent}>
        {/* KPI Grid */}
        <View style={styles.kpiGrid}>
           <KpiCard 
             label="MONTHLY RECURRING REVENUE" 
             value="$142.5K" 
             trend="+12.4% vs last month" 
             icon={<CreditCard size={20} color={THEME.colors.primary} />}
           />
           <KpiCard 
             label="ACTIVE SUBSCRIBERS" 
             value="2.8K" 
             trend="+312 new this cycle" 
             icon={<Users size={20} color="#B983FF" />}
           />
           <KpiCard 
             label="CHURN RATE" 
             value="3.2%" 
             trend="-0.4% retention peak" 
             icon={<TrendingUp size={20} color="#FF6363" />}
             isInverse
           />
           <KpiCard 
             label="TRIAL CONVERSIONS" 
             value="45%" 
             trend="+5% funnel efficiency" 
             icon={<PieChart size={20} color={THEME.colors.primary} />}
           />
        </View>

        {/* Revenue Trends */}
        <View style={styles.sectionHeader}>
           <Text style={styles.sectionTitle}>REVENUE TRENDS</Text>
           <View style={styles.toggleRow}>
              <TouchableOpacity style={styles.toggleBtn}><Text style={styles.toggleText}>7 DAYS</Text></TouchableOpacity>
              <TouchableOpacity style={[styles.toggleBtn, styles.toggleBtnActive]}><Text style={styles.toggleTextActive}>30 DAYS</Text></TouchableOpacity>
           </View>
        </View>

        <View style={styles.chartContainer}>
           <LineChart
             data={{
               labels: ["OCT 01", "OCT 10", "OCT 20", "OCT 30"],
               datasets: [{ data: [45, 52, 48, 58] }]
             }}
             width={screenWidth - 40}
             height={180}
             chartConfig={chartConfig}
             bezier
             style={styles.chart}
             withDots={false}
             withInnerLines={false}
             withOuterLines={false}
             withHorizontalLabels={true}
             formatYLabel={(y) => `${y}K`}
           />
        </View>

        {/* Plan Distribution */}
        <Text style={[styles.sectionTitle, { marginBottom: 20 }]}>PLAN DISTRIBUTION</Text>
        <GlassCard style={styles.donutCard}>
           <View style={styles.donutWrapper}>
             <View style={styles.donutHole}>
               <Text style={styles.donutLabel}>TOTAL</Text>
               <Text style={styles.donutTotal}>2,842</Text>
             </View>
             <ProgressChart
                data={{
                  labels: ["Pro", "Elite", "Starter"],
                  data: [0.55, 0.30, 0.15]
                }}
                width={screenWidth - 80}
                height={160}
                strokeWidth={16}
                radius={32}
                chartConfig={chartConfigDonut}
                hideLegend={true}
              />
           </View>
           <View style={styles.legend}>
              <LegendItem color={THEME.colors.primary} label="Pro Arena" value="55%" />
              <LegendItem color="#B983FF" label="Elite Stack" value="30%" />
              <LegendItem color="#FF9D9D" label="Starter" value="15%" />
           </View>
        </GlassCard>

        {/* Recent Events */}
        <View style={styles.sectionHeader}>
           <Text style={styles.sectionTitle}>RECENT SUBSCRIPTION EVENTS</Text>
           <TouchableOpacity style={styles.viewFullRow}>
             <Text style={styles.viewFullText}>View Full Audit Log</Text>
             <ChevronRight size={14} color={THEME.colors.primary} />
           </TouchableOpacity>
        </View>

        <View style={styles.eventList}>
           <EventRow 
             type="New Signup" 
             user="user_8201@arena.io" 
             meta="Trial: Pro Arena" 
             icon={<UserPlus size={18} color={THEME.colors.primary} />} 
           />
           <EventRow 
             type="Plan Upgrade" 
             user="shark_bettor_99" 
             meta="Starter -> Elite Stack" 
             icon={<TrendingUp size={18} color="#B983FF" />} 
           />
           <EventRow 
             type="Failed Payment" 
             user="dfs_analyst_2024" 
             meta="Pro Arena Monthly" 
             icon={<AlertCircle size={18} color="#FF6363" />} 
           />
           <EventRow 
             type="Renewal" 
             user="vol_trader_pro" 
             meta="Elite Stack Annual" 
             icon={<RefreshCw size={18} color={THEME.colors.primary} />} 
           />
        </View>
      </ScrollView>
    </SafeAreaView>
  );
};

const KpiCard = ({ label, value, trend, icon, isInverse }: any) => (
  <View style={styles.kpiCard}>
    <View style={styles.kpiSidebar} />
    <View style={styles.kpiContent}>
      <View style={styles.kpiHeader}>
        <Text style={styles.kpiLabel}>{label}</Text>
        {icon}
      </View>
      <Text style={styles.kpiValue}>{value}</Text>
      <View style={[styles.trendBadge, { backgroundColor: isInverse ? 'rgba(255, 99, 99, 0.1)' : 'rgba(0, 255, 157, 0.1)' }]}>
        <Text style={[styles.trendText, { color: isInverse ? '#FF6363' : THEME.colors.primary }]}>{trend}</Text>
      </View>
    </View>
  </View>
);

const LegendItem = ({ color, label, value }: any) => (
  <View style={styles.legendItem}>
    <View style={[styles.legendDot, { backgroundColor: color }]} />
    <Text style={styles.legendLabel}>{label}</Text>
    <Text style={styles.legendValue}>{value}</Text>
  </View>
);

const EventRow = ({ type, user, meta, icon }: any) => (
  <View style={styles.eventRow}>
    <View style={styles.eventIcon}>{icon}</View>
    <View style={styles.eventInfo}>
      <Text style={styles.eventType}>{type}</Text>
      <Text style={styles.eventUser}>{user}</Text>
      <Text style={styles.eventMeta}>{meta}</Text>
    </View>
  </View>
);

const chartConfig = {
  backgroundGradientFrom: THEME.colors.background,
  backgroundGradientTo: THEME.colors.background,
  color: (opacity = 1) => `rgba(0, 255, 157, ${opacity})`,
  labelColor: (opacity = 1) => `rgba(255, 255, 255, ${opacity * 0.5})`,
  strokeWidth: 3,
  propsForBackgroundLines: { strokeDasharray: "" },
};

const chartConfigDonut = {
  backgroundGradientFrom: '#1E2028',
  backgroundGradientTo: '#1E2028',
  color: (opacity = 1, index = 0) => {
    const colors = [THEME.colors.primary, "#B983FF", "#FF9D9D"];
    return colors[index % 3];
  },
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
    borderBottomColor: THEME.colors.border,
  },
  avatar: {
    width: 32,
    height: 32,
    borderRadius: 8,
    backgroundColor: '#333',
  },
  headerTitle: {
    color: '#FFF',
    fontSize: 16,
    fontWeight: 'bold',
    letterSpacing: 2,
  },
  headerActions: {
    flexDirection: 'row',
    gap: 16,
  },
  scrollContent: {
    padding: 20,
    paddingBottom: 40,
  },
  kpiGrid: {
    gap: 16,
    marginBottom: 32,
  },
  kpiCard: {
    backgroundColor: THEME.colors.card,
    borderRadius: 12,
    flexDirection: 'row',
    height: 120,
    overflow: 'hidden',
  },
  kpiSidebar: {
    width: 4,
    backgroundColor: THEME.colors.primary,
    height: '100%',
  },
  kpiContent: {
    flex: 1,
    padding: 16,
  },
  kpiHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 8,
  },
  kpiLabel: {
    color: THEME.colors.textSecondary,
    fontSize: 10,
    fontWeight: 'bold',
  },
  kpiValue: {
    color: '#FFF',
    fontSize: 32,
    fontWeight: 'bold',
    marginBottom: 6,
  },
  trendBadge: {
    alignSelf: 'flex-start',
    paddingHorizontal: 6,
    paddingVertical: 2,
    borderRadius: 4,
  },
  trendText: {
    fontSize: 10,
    fontWeight: 'bold',
  },
  sectionHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 24,
    marginTop: 8,
  },
  sectionTitle: {
    color: '#FFF',
    fontSize: 14,
    fontWeight: 'bold',
    letterSpacing: 1,
  },
  toggleRow: {
    flexDirection: 'row',
    backgroundColor: THEME.colors.card,
    borderRadius: 6,
    padding: 4,
  },
  toggleBtn: {
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 4,
  },
  toggleBtnActive: {
    backgroundColor: THEME.colors.primary,
  },
  toggleText: {
    color: THEME.colors.textSecondary,
    fontSize: 10,
    fontWeight: 'bold',
  },
  toggleTextActive: {
    color: '#000',
    fontSize: 10,
    fontWeight: 'bold',
  },
  chartContainer: {
    marginBottom: 32,
  },
  chart: {
    borderRadius: 16,
    paddingRight: 40,
  },
  donutCard: {
    padding: 24,
    marginBottom: 32,
  },
  donutWrapper: {
    alignItems: 'center',
    justifyContent: 'center',
    position: 'relative',
    height: 180,
  },
  donutHole: {
    position: 'absolute',
    alignItems: 'center',
    justifyContent: 'center',
    zIndex: 1,
    backgroundColor: '#111',
    width: 100,
    height: 100,
    borderRadius: 50,
  },
  donutLabel: {
    color: THEME.colors.textSecondary,
    fontSize: 10,
    fontWeight: 'bold',
  },
  donutTotal: {
    color: '#FFF',
    fontSize: 24,
    fontWeight: 'bold',
  },
  legend: {
    marginTop: 20,
    gap: 12,
  },
  legendItem: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  legendDot: {
    width: 8,
    height: 8,
    borderRadius: 4,
    marginRight: 12,
  },
  legendLabel: {
    color: THEME.colors.textSecondary,
    fontSize: 12,
    flex: 1,
  },
  legendValue: {
    color: '#FFF',
    fontSize: 12,
    fontWeight: 'bold',
  },
  viewFullRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
  },
  viewFullText: {
    color: THEME.colors.primary,
    fontSize: 12,
    fontWeight: 'bold',
  },
  eventList: {
    gap: 20,
  },
  eventRow: {
    flexDirection: 'row',
    gap: 16,
  },
  eventIcon: {
    width: 44,
    height: 44,
    borderRadius: 8,
    backgroundColor: THEME.colors.card,
    alignItems: 'center',
    justifyContent: 'center',
  },
  eventInfo: {
    flex: 1,
    borderBottomWidth: 1,
    borderBottomColor: 'rgba(255,255,255,0.05)',
    paddingBottom: 16,
  },
  eventType: {
    color: THEME.colors.textSecondary,
    fontSize: 10,
    fontWeight: 'bold',
    marginBottom: 4,
  },
  eventUser: {
    color: '#FFF',
    fontSize: 16,
    fontWeight: 'bold',
  },
  eventMeta: {
    color: THEME.colors.textSecondary,
    fontSize: 12,
    marginTop: 2,
  }
});
