import React from 'react';
import { StyleSheet, View, Text, ScrollView, TouchableOpacity, SafeAreaView } from 'react-native';
import { Zap, CreditCard, ChevronRight, CheckCircle2, History, ExternalLink, Settings, ShieldCheck } from 'lucide-react-native';
import { THEME } from '../constants/theme';
import { GlassCard, NeonButton } from '../components/Common';

export const BillingScreen = () => {
  return (
    <SafeAreaView style={styles.container}>
      <ScrollView showsVerticalScrollIndicator={false} contentContainerStyle={styles.scrollContent}>
        <View style={styles.header}>
           <Text style={styles.headerTitle}>Billing Settings</Text>
           <Text style={styles.headerSub}>Manage your subscription engine, view transaction history, and optimize your data throughput.</Text>
           <TouchableOpacity style={styles.portalBtn}>
              <ExternalLink size={16} color="#FFF" />
              <Text style={styles.portalText}>Manage via Stripe Portal</Text>
           </TouchableOpacity>
        </View>

        {/* Current Subscription Card */}
        <GlassCard style={styles.mainCard}>
           <View style={styles.cardHeader}>
             <Text style={styles.cardLabel}>CURRENT SUBSCRIPTION</Text>
             <View style={styles.activeBadge}>
                <View style={styles.dot} />
                <Text style={styles.activeText}>ACTIVE NOW</Text>
             </View>
           </View>
           <Text style={styles.planTitle}>Pro Tier</Text>
           
           <View style={styles.detailGrid}>
              <View style={styles.detailBox}>
                <Text style={styles.detailLabel}>RENEWAL DATE</Text>
                <Text style={styles.detailValue}>Oct 12, 2024</Text>
              </View>
              <View style={styles.detailBox}>
                 <Text style={styles.detailLabel}>NEXT PAYMENT</Text>
                 <Text style={styles.detailValue}>$49.00 <Text style={styles.detailSub}>/mo</Text></Text>
              </View>
           </View>

           <View style={styles.paymentMethod}>
              <Text style={styles.detailLabel}>PAYMENT METHOD</Text>
              <View style={styles.cardRow}>
                 <CreditCard size={20} color={THEME.colors.secondary} />
                 <Text style={styles.cardNumber}>•••• 8821</Text>
              </View>
           </View>

           <NeonButton 
             title="UPGRADE TO ELITE" 
             onPress={() => {}} 
             style={styles.upgradeBtn}
           />
           <TouchableOpacity style={styles.cancelBtn}>
              <Text style={styles.cancelText}>CANCEL SUBSCRIPTION</Text>
           </TouchableOpacity>
        </GlassCard>

        {/* Upsell Card */}
        <View style={styles.upsellSection}>
           <View style={styles.upsellHeader}>
              <Zap size={18} color="#FFF" fill="#FFF" />
              <Text style={styles.upsellTitle}>UNLOCK ELITE CAPACITY</Text>
           </View>
           <Text style={styles.upsellHeading}>Advanced Projections & Global API</Text>
           
           <View style={styles.checklist}>
              <CheckItem text="Unlimited lineup exports" />
              <CheckItem text="Real-time ownership pings" />
              <CheckItem text="High-priority cloud compute" />
           </View>

           <View style={styles.offerCard}>
              <Text style={styles.offerLabel}>SPECIAL OFFER</Text>
              <Text style={styles.offerText}>Upgrade now and save 20% on your first 3 months.</Text>
           </View>
        </View>

        {/* Invoice History */}
        <View style={styles.sectionHeader}>
           <View style={styles.sectionTitleRow}>
              <History size={20} color="#FFF" />
              <Text style={styles.sectionTitle}>Invoice History</Text>
           </View>
           <Text style={styles.periodText}>SHOWING LAST 12 MONTHS</Text>
        </View>

        <View style={styles.tableHeader}>
           <Text style={styles.colLabel}>STATUS</Text>
           <Text style={styles.colLabel}>INVOICE DATE</Text>
           <Text style={[styles.colLabel, { flex: 1, textAlign: 'right' }]}>BILLING PERIOD</Text>
        </View>

        <InvoiceRow status="Paid" date="Sep 12, 2024" period="Aug 12 — Sep 11, 2024" />
        <InvoiceRow status="Paid" date="Aug 12, 2024" period="Jul 12 — Aug 11, 2024" />
        <InvoiceRow status="Paid" date="Jul 12, 2024" period="Jun 12 — Jul 11, 2024" />

        {/* Manage Payment Methods Bottom Card */}
        <GlassCard style={styles.bottomCard}>
           <Text style={styles.bottomTitle}>Manage Payment Methods</Text>
           <Text style={styles.bottomSub}>Add a backup card or update your billing address via our secure Stripe integration.</Text>
           <View style={styles.bottomActions}>
              <View style={styles.iconRow}>
                 <CreditCard size={18} color={THEME.colors.textSecondary} />
                 <ChevronRight size={18} color={THEME.colors.textSecondary} />
              </View>
              <TouchableOpacity style={styles.launchBtn}>
                 <Text style={styles.launchText}>Launch Portal</Text>
              </TouchableOpacity>
           </View>
        </GlassCard>
      </ScrollView>
    </SafeAreaView>
  );
};

const CheckItem = ({ text }: any) => (
  <View style={styles.checkItem}>
    <CheckCircle2 size={18} color={THEME.colors.text} />
    <Text style={styles.checkText}>{text}</Text>
  </View>
);

const InvoiceRow = ({ status, date, period }: any) => (
  <View style={styles.invoiceRow}>
    <View style={styles.statusCol}>
       <View style={styles.statusDot} />
       <Text style={styles.statusText}>{status}</Text>
    </View>
    <Text style={styles.dateText}>{date}</Text>
    <Text style={styles.periodVal}>{period}</Text>
  </View>
);

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: THEME.colors.background,
  },
  scrollContent: {
    padding: 20,
    paddingBottom: 40,
  },
  header: {
    marginBottom: 32,
    marginTop: 20,
  },
  headerTitle: {
    color: '#FFF',
    fontSize: 32,
    fontWeight: 'bold',
    marginBottom: 12,
  },
  headerSub: {
    color: THEME.colors.textSecondary,
    fontSize: 14,
    lineHeight: 20,
    marginBottom: 24,
  },
  portalBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    backgroundColor: '#272A35',
    paddingHorizontal: 16,
    paddingVertical: 12,
    borderRadius: 8,
    alignSelf: 'flex-start',
  },
  portalText: {
    color: '#FFF',
    fontSize: 14,
    fontWeight: 'bold',
  },
  mainCard: {
    padding: 24,
    marginBottom: 32,
  },
  cardHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 16,
  },
  cardLabel: {
    color: THEME.colors.textSecondary,
    fontSize: 12,
    fontWeight: 'bold',
  },
  activeBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    backgroundColor: THEME.colors.primary + '20',
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: 12,
  },
  dot: {
    width: 6,
    height: 6,
    borderRadius: 3,
    backgroundColor: THEME.colors.primary,
  },
  activeText: {
    color: THEME.colors.primary,
    fontSize: 10,
    fontWeight: 'bold',
  },
  planTitle: {
    color: '#FFF',
    fontSize: 48,
    fontWeight: 'bold',
    marginBottom: 32,
  },
  detailGrid: {
    flexDirection: 'row',
    gap: 20,
    marginBottom: 24,
  },
  detailBox: {
    flex: 1,
  },
  detailLabel: {
    color: THEME.colors.textSecondary,
    fontSize: 12,
    fontWeight: 'bold',
    marginBottom: 8,
  },
  detailValue: {
    color: '#FFF',
    fontSize: 18,
    fontWeight: 'bold',
  },
  detailSub: {
    color: THEME.colors.textSecondary,
    fontSize: 12,
  },
  paymentMethod: {
    marginBottom: 32,
    paddingBottom: 24,
    borderBottomWidth: 1,
    borderBottomColor: 'rgba(255,255,255,0.05)',
  },
  cardRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
    marginTop: 4,
  },
  cardNumber: {
    color: '#FFF',
    fontSize: 16,
    fontWeight: 'bold',
  },
  upgradeBtn: {
    paddingVertical: 16,
    marginBottom: 12,
  },
  cancelBtn: {
    borderWidth: 1,
    borderColor: '#272A35',
    paddingVertical: 14,
    borderRadius: 8,
    alignItems: 'center',
  },
  cancelText: {
    color: THEME.colors.textSecondary,
    fontSize: 12,
    fontWeight: '900',
    letterSpacing: 1,
  },
  upsellSection: {
    backgroundColor: 'rgba(15, 17, 21, 0.5)',
    borderRadius: 16,
    borderWidth: 1,
    borderColor: 'rgba(255,255,255,0.05)',
    padding: 24,
    marginBottom: 32,
  },
  upsellHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
    marginBottom: 20,
  },
  upsellTitle: {
    color: '#FFF',
    fontSize: 12,
    fontWeight: 'bold',
    letterSpacing: 1,
  },
  upsellHeading: {
    color: '#FFF',
    fontSize: 22,
    fontWeight: 'bold',
    marginBottom: 24,
  },
  checklist: {
    gap: 16,
    marginBottom: 32,
  },
  checkItem: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
  },
  checkText: {
    color: THEME.colors.textSecondary,
    fontSize: 14,
  },
  offerCard: {
    backgroundColor: '#272A3550',
    borderRadius: 8,
    padding: 16,
    borderLeftWidth: 3,
    borderLeftColor: THEME.colors.primary,
  },
  offerLabel: {
    color: THEME.colors.textSecondary,
    fontSize: 10,
    fontWeight: 'bold',
    marginBottom: 4,
  },
  offerText: {
    color: '#FFF',
    fontSize: 13,
    lineHeight: 18,
  },
  sectionHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 24,
  },
  sectionTitleRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
  },
  sectionTitle: {
    color: '#FFF',
    fontSize: 18,
    fontWeight: 'bold',
  },
  periodText: {
    color: THEME.colors.textSecondary,
    fontSize: 10,
    fontWeight: 'bold',
  },
  tableHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    paddingHorizontal: 8,
    marginBottom: 20,
  },
  colLabel: {
    color: THEME.colors.textSecondary,
    fontSize: 10,
    fontWeight: 'bold',
  },
  invoiceRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
    paddingVertical: 20,
    borderTopWidth: 1,
    borderTopColor: 'rgba(255,255,255,0.05)',
  },
  statusCol: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    width: 80,
  },
  statusDot: {
    width: 6,
    height: 6,
    borderRadius: 3,
    backgroundColor: THEME.colors.primary,
  },
  statusText: {
    color: '#FFF',
    fontSize: 13,
    fontWeight: 'bold',
  },
  dateText: {
    color: '#FFF',
    fontSize: 14,
    width: 100,
    lineHeight: 20,
  },
  periodVal: {
    color: THEME.colors.textSecondary,
    fontSize: 12,
    flex: 1,
    textAlign: 'right',
    lineHeight: 18,
  },
  bottomCard: {
    marginTop: 32,
    padding: 24,
  },
  bottomTitle: {
    color: '#FFF',
    fontSize: 18,
    fontWeight: 'bold',
    marginBottom: 8,
  },
  bottomSub: {
    color: THEME.colors.textSecondary,
    fontSize: 13,
    lineHeight: 18,
    marginBottom: 24,
  },
  bottomActions: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  iconRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
    backgroundColor: '#272A35',
    padding: 10,
    borderRadius: 8,
  },
  launchBtn: {
    backgroundColor: '#E2E8F0',
    paddingHorizontal: 16,
    paddingVertical: 10,
    borderRadius: 6,
  },
  launchText: {
    color: '#0F172A',
    fontSize: 14,
    fontWeight: 'bold',
  }
});
