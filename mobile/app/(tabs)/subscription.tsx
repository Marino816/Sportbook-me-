import { useEffect, useState } from "react";
import { View, Text, StyleSheet, TouchableOpacity, ScrollView, ActivityIndicator, Alert, Linking } from "react-native";
import { getSubscriptionStatus, createCheckout, openBillingPortal } from "../../lib/api";

export default function SubscriptionScreen() {
  const [sub, setSub] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => { load(); }, []);
  async function load() { try { const r = await getSubscriptionStatus(); setSub(r.data); } catch {} finally { setLoading(false); } }

  async function handleCheckout(plan: string) {
    try { const r = await createCheckout(plan); Linking.openURL(r.data.url); } catch (e: any) { Alert.alert("Error", e.message); }
  }
  async function handlePortal() {
    try { const r = await openBillingPortal(); Linking.openURL(r.data.url); } catch (e: any) { Alert.alert("Error", e.message); }
  }

  if (loading) return <View style={s.center}><ActivityIndicator size="large" color="#c9a84c" /></View>;

  return (
    <ScrollView style={s.scroll} contentContainerStyle={s.container}>
      <View style={s.card}>
        <Text style={s.cardTitle}>Current Plan</Text>
        <Text style={s.plan}>{sub?.plan || "Free"}</Text>
        <Text style={s.status}>{sub?.status || "inactive"}</Text>
        {sub?.next_billing && <Text style={s.date}>Next billing: {new Date(sub.next_billing).toLocaleDateString()}</Text>}
      </View>

      <Text style={s.section}>Upgrade Plan</Text>
      <TouchableOpacity style={s.planCard} onPress={() => handleCheckout("Pro Arena")}>
        <View><Text style={s.planName}>Pro Arena</Text><Text style={s.planDesc}>Monthly · Full projections · 20 lineups</Text></View>
        <Text style={s.price}>$39.99/mo</Text>
      </TouchableOpacity>
      <TouchableOpacity style={s.planCard} onPress={() => handleCheckout("Elite Stack")}>
        <View><Text style={s.planName}>Elite Stack</Text><Text style={s.planDesc}>Monthly · Unlimited · 150 lineups</Text></View>
        <Text style={s.price}>$79.99/mo</Text>
      </TouchableOpacity>

      {sub?.status === "active" && (
        <TouchableOpacity style={s.btn} onPress={handlePortal}>
          <Text style={s.btnText}>Manage Subscription</Text>
        </TouchableOpacity>
      )}
    </ScrollView>
  );
}

const s = StyleSheet.create({
  scroll: { flex: 1, backgroundColor: "#060b1a" }, container: { padding: 20, gap: 16 },
  center: { flex: 1, backgroundColor: "#060b1a", justifyContent: "center", alignItems: "center" },
  card: { backgroundColor: "#0a0f24", borderRadius: 16, padding: 20, borderWidth: 1, borderColor: "#333" },
  cardTitle: { fontSize: 12, color: "#666", textTransform: "uppercase" },
  plan: { fontSize: 24, fontWeight: "900", color: "#c9a84c", marginTop: 4, fontStyle: "italic" },
  status: { fontSize: 14, color: "#fff", marginTop: 2 }, date: { fontSize: 12, color: "#888", marginTop: 4 },
  section: { fontSize: 14, fontWeight: "700", color: "#fff", marginTop: 8 },
  planCard: { flexDirection: "row", justifyContent: "space-between", alignItems: "center", backgroundColor: "#0a0f24", borderRadius: 16, padding: 16, borderWidth: 1, borderColor: "#333" },
  planName: { fontSize: 16, fontWeight: "700", color: "#fff" }, planDesc: { fontSize: 13, color: "#888", marginTop: 2 },
  price: { fontSize: 16, fontWeight: "700", color: "#c9a84c" },
  btn: { backgroundColor: "#c9a84c", borderRadius: 12, padding: 16, alignItems: "center", marginTop: 8 },
  btnText: { color: "#000", fontWeight: "700", fontSize: 16 },
});