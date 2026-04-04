import React, { useEffect, useState } from 'react';
import { StyleSheet, View, Text, ScrollView, TouchableOpacity, SafeAreaView, Image, ImageBackground, ActivityIndicator } from 'react-native';
import { Zap, Info, ChevronRight, LayoutGrid, BarChart3, Activity, Users, Wallet, TrendingUp } from 'lucide-react-native';
import { THEME } from '../constants/theme';
import { GlassCard } from '../components/Common';
import { fetchSportsLobby, SportMatchup, ApiResponse } from '../lib/api';
import { ErrorState } from '../components/ErrorState';

export const SportsScreen = () => {
  const [matches, setMatches] = useState<SportMatchup[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetchSportsLobby("NFL");
      setMatches(res.data);
    } catch (e: any) {
      setError(e.message || "Failed to reach sports backend.");
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
        <View style={styles.headerLeft}>
          <View style={styles.avatarPlaceholder} />
          <Text style={styles.logoText}>SportBook Me</Text>
        </View>
        <View style={styles.balanceBadge}>
          <Wallet size={14} color={THEME.colors.primary} />
          <Text style={styles.balanceText}>$1,250.00</Text>
        </View>
      </View>

      <ScrollView showsVerticalScrollIndicator={false} contentContainerStyle={styles.scrollContent}>
        {/* Hero Section */}
        <ImageBackground 
          source={{ uri: 'https://images.unsplash.com/photo-1504450758481-7338eba7524a?auto=format&fit=crop&q=80&w=800' }} 
          style={styles.hero}
          imageStyle={{ borderRadius: 16 }}
        >
          <View style={styles.heroOverlay}>
             <View style={styles.leagueBadge}>
               <View style={styles.dot} />
               <Text style={styles.leagueText}>NFL FOOTBALL</Text>
             </View>
             <Text style={styles.heroTitle}>WEEK 15 LOBBY</Text>
          </View>
        </ImageBackground>

        {/* Category Tabs */}
        <View style={styles.tabs}>
           <TouchableOpacity style={[styles.tab, styles.tabActive]}>
             <Text style={styles.tabTextActive}>Main Bets</Text>
           </TouchableOpacity>
           <TouchableOpacity style={styles.tab}>
             <Text style={styles.tabText}>Player Props</Text>
           </TouchableOpacity>
           <TouchableOpacity style={styles.tab}>
             <Text style={styles.tabText}>Game Props</Text>
           </TouchableOpacity>
        </View>

        {/* Column Headers */}
        <View style={styles.columnHeaders}>
           <Text style={styles.colLabel}>MATCHUP</Text>
           <View style={styles.rightCols}>
             <Text style={styles.colLabelSmall}>SPREAD</Text>
             <Text style={styles.colLabelSmall}>TOTAL</Text>
             <Text style={styles.colLabelSmall}>MONEYLINE</Text>
           </View>
        </View>

        {/* Game Cards */}
        {loading ? (
          <ActivityIndicator color={THEME.colors.primary} style={{ marginVertical: 40 }} />
        ) : (
          matches.map((match, i) => (
            <GameCard 
              key={i}
              time={match.time} 
              team1={match.home_team} 
              team2={match.away_team} 
              isLive={match.is_live}
              isBoosted={match.is_boosted}
              odds={match.odds}
              odds2={match.odds} // Simplified for demo mapping
            />
          ))
        )}
      </ScrollView>

      {/* Floating Bet Slip */}
      <TouchableOpacity style={styles.betSlip}>
         <View style={styles.slipCount}>
           <Text style={styles.slipCountText}>1</Text>
         </View>
         <View style={styles.slipInfo}>
           <Text style={styles.slipTitle}>Bet Slip</Text>
           <Text style={styles.slipDetail}>KC Chiefs Spread -1.5 @ -115</Text>
         </View>
         <View style={styles.payoutContainer}>
            <Text style={styles.payoutLabel}>POSSIBLE{'\n'}PAYOUT</Text>
            <Text style={styles.payoutValue}>$186.94</Text>
         </View>
         <View style={styles.slipAction}>
           <ChevronRight size={24} color="#000" />
         </View>
      </TouchableOpacity>
    </SafeAreaView>
  );
};

const GameCard = ({ time, team1, team2, odds, isLive, isBoosted }: any) => (
  <View style={styles.card}>
    <View style={styles.cardHeader}>
       <View style={styles.timeRow}>
          {isLive && <View style={styles.liveBadge}><Text style={styles.liveText}>LIVE</Text></View>}
          <Text style={[styles.timeText, isLive && { color: THEME.colors.primary }]}>
            {isLive && <Activity size={12} color={THEME.colors.primary} style={{ marginRight: 4 }} />}
            {time}
          </Text>
       </View>
       <View style={{ flexDirection: 'row', gap: 12 }}>
         {isBoosted && <View style={styles.boostedBadge}><TrendingUp size={10} color="#B983FF" /> <Text style={styles.boostedText}>BOOSTED</Text></View>}
         <Info size={18} color={THEME.colors.textSecondary} />
       </View>
    </View>

    <View style={styles.gameBody}>
       <View style={styles.teamsCol}>
         <TeamRow name={team1} />
         <TeamRow name={team2} />
       </View>
       <View style={styles.oddsCol}>
         <OddsRow items={odds} />
         <OddsRow items={odds} />
       </View>
    </View>
  </View>
);

const TeamRow = ({ name }: any) => (
  <View style={styles.teamRow}>
    <View style={styles.teamIcon} />
    <Text style={styles.teamName}>{name}</Text>
  </View>
);

const OddsRow = ({ items }: any) => (
  <View style={styles.oddsButtons}>
    {items?.map((item: any, i: number) => (
      <TouchableOpacity key={i} style={styles.oddsBtn}>
        {item.val && <Text style={styles.oddsVal}>{item.val}</Text>}
        <Text style={[styles.oddsPrice, { color: item.price?.startsWith('+') ? THEME.colors.primary : '#FF6363' }]}>
          {item.price || item.val}
        </Text>
      </TouchableOpacity>
    ))}
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
    paddingVertical: 12,
  },
  headerLeft: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
  },
  avatarPlaceholder: {
    width: 32,
    height: 32,
    borderRadius: 8,
    backgroundColor: '#333',
  },
  logoText: {
    color: THEME.colors.primary,
    fontSize: 18,
    fontWeight: 'bold',
    fontStyle: 'italic',
  },
  balanceBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    backgroundColor: 'rgba(0, 255, 157, 0.1)',
    paddingHorizontal: 10,
    paddingVertical: 6,
    borderRadius: 8,
  },
  balanceText: {
    color: THEME.colors.primary,
    fontSize: 14,
    fontWeight: 'bold',
  },
  scrollContent: {
    padding: 20,
    paddingBottom: 100,
  },
  hero: {
    height: 180,
    justifyContent: 'flex-end',
    marginBottom: 24,
  },
  heroOverlay: {
    backgroundColor: 'rgba(0,0,0,0.4)',
    padding: 20,
    borderBottomLeftRadius: 16,
    borderBottomRightRadius: 16,
  },
  leagueBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    marginBottom: 8,
  },
  dot: {
    width: 6,
    height: 6,
    borderRadius: 3,
    backgroundColor: THEME.colors.primary,
  },
  leagueText: {
    color: '#00FFAD',
    fontSize: 10,
    fontWeight: 'bold',
    letterSpacing: 1,
  },
  heroTitle: {
    color: '#FFF',
    fontSize: 28,
    fontWeight: '900',
    letterSpacing: 0.5,
  },
  tabs: {
    flexDirection: 'row',
    gap: 12,
    marginBottom: 32,
  },
  tab: {
    flex: 1,
    backgroundColor: 'rgba(255,255,255,0.05)',
    paddingVertical: 12,
    borderRadius: 8,
    alignItems: 'center',
  },
  tabActive: {
    backgroundColor: THEME.colors.primary,
  },
  tabText: {
    color: THEME.colors.textSecondary,
    fontSize: 14,
    fontWeight: 'bold',
  },
  tabTextActive: {
    color: '#000',
    fontSize: 14,
    fontWeight: 'bold',
  },
  columnHeaders: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    paddingHorizontal: 12,
    marginBottom: 16,
  },
  colLabel: {
    color: THEME.colors.textSecondary,
    fontSize: 10,
    fontWeight: 'bold',
    letterSpacing: 1,
  },
  rightCols: {
    flexDirection: 'row',
    gap: 24,
  },
  colLabelSmall: {
    color: THEME.colors.textSecondary,
    fontSize: 8,
    fontWeight: 'black',
    letterSpacing: 0.5,
    width: 60,
    textAlign: 'center',
  },
  card: {
    backgroundColor: THEME.colors.card,
    borderRadius: 16,
    padding: 16,
    marginBottom: 16,
    borderWidth: 1,
    borderColor: THEME.colors.border,
  },
  cardHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 16,
  },
  timeRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  liveBadge: {
    backgroundColor: THEME.colors.primary,
    paddingHorizontal: 8,
    paddingVertical: 2,
    borderRadius: 12,
  },
  liveText: {
    color: '#000',
    fontSize: 10,
    fontWeight: 'black',
  },
  timeText: {
    color: THEME.colors.textSecondary,
    fontSize: 12,
    fontWeight: 'bold',
  },
  boostedBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    backgroundColor: 'rgba(185, 131, 255, 0.1)',
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderRadius: 6,
  },
  boostedText: {
    color: '#B983FF',
    fontSize: 10,
    fontWeight: 'black',
  },
  gameBody: {
    flexDirection: 'row',
    justifyContent: 'space-between',
  },
  teamsCol: {
    gap: 20,
    flex: 1,
  },
  teamRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
  },
  teamIcon: {
    width: 32,
    height: 32,
    borderRadius: 8,
    backgroundColor: 'rgba(255,255,255,0.05)',
  },
  teamName: {
    color: '#FFF',
    fontSize: 16,
    fontWeight: 'bold',
  },
  oddsCol: {
    gap: 12,
  },
  oddsButtons: {
    flexDirection: 'row',
    gap: 8,
  },
  oddsBtn: {
    width: 64,
    height: 64,
    backgroundColor: THEME.colors.background,
    borderRadius: 8,
    alignItems: 'center',
    justifyContent: 'center',
    borderWidth: 1,
    borderColor: THEME.colors.border,
  },
  oddsVal: {
    color: THEME.colors.textSecondary,
    fontSize: 10,
    fontWeight: 'bold',
  },
  oddsPrice: {
    fontSize: 14,
    fontWeight: 'bold',
    marginTop: 2,
  },
  betSlip: {
    position: 'absolute',
    bottom: 20,
    left: 20,
    right: 20,
    backgroundColor: THEME.colors.card,
    borderRadius: 16,
    padding: 16,
    flexDirection: 'row',
    alignItems: 'center',
    borderWidth: 1,
    borderColor: THEME.colors.primary + '30',
    shadowColor: THEME.colors.primary,
    shadowOffset: { width: 0, height: 10 },
    shadowOpacity: 0.2,
    shadowRadius: 20,
    elevation: 10,
  },
  slipCount: {
    width: 36,
    height: 36,
    borderRadius: 8,
    backgroundColor: THEME.colors.primary + '20',
    alignItems: 'center',
    justifyContent: 'center',
    marginRight: 16,
  },
  slipCountText: {
    color: THEME.colors.primary,
    fontSize: 18,
    fontWeight: 'black',
  },
  slipInfo: {
    flex: 1,
  },
  slipTitle: {
    color: '#FFF',
    fontSize: 16,
    fontWeight: 'bold',
  },
  slipDetail: {
    color: THEME.colors.textSecondary,
    fontSize: 12,
    marginTop: 2,
  },
  payoutContainer: {
    alignItems: 'flex-end',
    marginRight: 16,
  },
  payoutLabel: {
    color: THEME.colors.textSecondary,
    fontSize: 8,
    fontWeight: 'black',
    textAlign: 'right',
  },
  payoutValue: {
    color: THEME.colors.primary,
    fontSize: 18,
    fontWeight: 'black',
    marginTop: 2,
  },
  slipAction: {
    width: 44,
    height: 44,
    borderRadius: 8,
    backgroundColor: THEME.colors.primary,
    alignItems: 'center',
    justifyContent: 'center',
  }
});
