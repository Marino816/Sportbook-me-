import { useCallback, useEffect, useMemo, useState } from "react";
import {
  View,
  Text,
  StyleSheet,
  TouchableOpacity,
  ScrollView,
  ActivityIndicator,
  Alert,
  Linking,
} from "react-native";
import { useAuth } from "../../lib/auth";
import {
  getSubscriptionStatus,
  getAppleAccountToken,
  verifyAppleTransaction,
  verifyAppleTransactions,
} from "../../lib/api";
import {
  ELITE_LINEUP_COPY,
  ELITE_PRODUCT_IDS,
  PAYWALL_TITLE,
  PRIVACY_POLICY_URL,
  PRO_LINEUP_COPY,
  PRO_PRODUCT_IDS,
  TERMS_OF_USE_URL,
  displayPlanLabel,
  getAppleProduct,
} from "../../lib/apple-products";
import { purchaseCta, canStartPurchase } from "../../lib/subscription-cta.mjs";
import {
  collectRestorableApplePurchases,
  connectAppleIap,
  disconnectAppleIap,
  fetchAppleSubscriptionProducts,
  finishVerifiedApplePurchase,
  isIosAppleIap,
  runRestoreVerify,
  runVerifyAndRefresh,
  startAppleSubscriptionPurchase,
  type StoreKitDisplayProduct,
} from "../../lib/apple-iap";

type BillingStatus = {
  plan?: string;
  status?: string;
  has_access?: boolean;
  provider?: string | null;
  next_billing?: string | null;
};

type UiPhase =
  | "idle"
  | "products"
  | "purchasing"
  | "pending"
  | "verifying"
  | "restoring";

function unwrapBilling(body: unknown): BillingStatus | null {
  if (!body || typeof body !== "object") return null;
  const raw = body as Record<string, unknown>;
  const data = raw.data;
  if (data && typeof data === "object") return data as BillingStatus;
  return raw as BillingStatus;
}

export default function SubscriptionScreen() {
  const { user, refreshUser } = useAuth();
  const ios = isIosAppleIap();
  const [billing, setBilling] = useState<BillingStatus | null>(null);
  const [products, setProducts] = useState<StoreKitDisplayProduct[]>([]);
  const [loadingBilling, setLoadingBilling] = useState(true);
  const [loadingProducts, setLoadingProducts] = useState(ios);
  const [productsError, setProductsError] = useState<string | null>(null);
  const [phase, setPhase] = useState<UiPhase>("idle");
  const [message, setMessage] = useState<string | null>(null);
  const [messageKind, setMessageKind] = useState<"info" | "error" | "success">("info");

  const notice = useCallback((text: string, kind: "info" | "error" | "success" = "info") => {
    setMessage(text);
    setMessageKind(kind);
  }, []);

  const refreshEntitlement = useCallback(async () => {
    await refreshUser();
    const status = unwrapBilling(await getSubscriptionStatus());
    if (status) setBilling(status);
    return status;
  }, [refreshUser]);

  const loadBilling = useCallback(async () => {
    try {
      const status = unwrapBilling(await getSubscriptionStatus());
      if (status) setBilling(status);
    } catch {
      notice("Could not load your current subscription.", "error");
    } finally {
      setLoadingBilling(false);
    }
  }, [notice]);

  const loadProducts = useCallback(async () => {
    if (!ios) {
      setLoadingProducts(false);
      return;
    }
    setLoadingProducts(true);
    setProductsError(null);
    try {
      await connectAppleIap();
      setProducts(await fetchAppleSubscriptionProducts());
    } catch (error) {
      setProductsError(
        error instanceof Error ? error.message : "Could not load App Store products.",
      );
    } finally {
      setLoadingProducts(false);
    }
  }, [ios]);

  useEffect(() => {
    loadBilling();
    loadProducts();
    return () => {
      disconnectAppleIap();
    };
  }, [loadBilling, loadProducts]);

  const currentPlan = displayPlanLabel(
    billing?.plan || user?.plan,
    billing?.has_access === true || user?.is_pro === true,
  );
  const hasPaidAccess = currentPlan === "Pro Arena" || currentPlan === "Elite Stack";
  const busy = phase !== "idle";

  const productById = useMemo(() => {
    const map = new Map<string, StoreKitDisplayProduct>();
    for (const product of products) map.set(product.productId, product);
    return map;
  }, [products]);

  async function handlePurchase(productId: string) {
    if (!ios) return;
    if (!canStartPurchase(productId, currentPlan)) return;
    setPhase("purchasing");
    setMessage(null);
    notice("Starting Apple purchase...", "info");
    try {
      const appAccountToken = await getAppleAccountToken();
      const attempt = await startAppleSubscriptionPurchase(productId, appAccountToken);
      if (attempt.kind === "canceled") {
        setPhase("idle");
        notice("Purchase canceled.", "info");
        return;
      }
      if (attempt.kind === "pending") {
        setPhase("pending");
        notice("Purchase pending. Complete the App Store payment to continue.", "info");
        return;
      }
      setPhase("verifying");
      notice("Purchase received. Verifying your subscription...", "info");
      const { account } = await runVerifyAndRefresh({
        signedJws: attempt.signedJws,
        verifyAppleTransaction,
        refreshAccount: refreshEntitlement,
      });
      try {
        await finishVerifiedApplePurchase(attempt.purchase);
      } catch {
        /* verification already succeeded; unfinished transactions can restore */
      }
      const status = (account || {}) as BillingStatus;
      const confirmed = displayPlanLabel(status.plan, status.has_access === true);
      setPhase("idle");
      if (confirmed === "Free") {
        notice("Purchase received. Verifying your subscription...", "info");
        return;
      }
      notice(`${confirmed} is active.`, "success");
    } catch (error) {
      setPhase("idle");
      notice(
        error instanceof Error ? error.message : "Could not verify this purchase.",
        "error",
      );
    }
  }

  async function handleRestore() {
    if (!ios) return;
    setPhase("restoring");
    setMessage(null);
    try {
      const purchases = await collectRestorableApplePurchases();
      const result = await runRestoreVerify({
        purchases,
        verifyAppleTransactions,
        refreshAccount: refreshEntitlement,
      });
      setPhase("idle");
      if (result.kind === "empty") {
        notice("No Apple purchases were found to restore.", "info");
        return;
      }
      const status = (result.account || {}) as BillingStatus;
      const confirmed = displayPlanLabel(status.plan, status.has_access === true);
      notice(
        confirmed === "Free"
          ? "Purchases sent for verification. Refreshing your account..."
          : `${confirmed} restored.`,
        confirmed === "Free" ? "info" : "success",
      );
    } catch (error) {
      setPhase("idle");
      notice(
        error instanceof Error ? error.message : "Could not restore purchases.",
        "error",
      );
    }
  }

  function openLegal(url: string) {
    Linking.openURL(url).catch(() => {
      Alert.alert("Unavailable", "Could not open this link.");
    });
  }

  if (loadingBilling) {
    return (
      <View style={s.center}>
        <ActivityIndicator size="large" color="#c9a84c" />
        <Text style={s.loadingText}>Loading current subscription...</Text>
      </View>
    );
  }

  return (
    <ScrollView style={s.scroll} contentContainerStyle={s.container}>
      <Text style={s.kicker}>SPORTBOOK ME</Text>
      <Text style={s.title}>{PAYWALL_TITLE}</Text>
      <Text style={s.subtitle}>
        AI-powered DFS and Parlay lineup analysis. Subscriptions unlock lineup generation limits.
      </Text>

      <View style={s.currentCard}>
        <Text style={s.cardLabel}>Current plan</Text>
        <Text style={s.currentPlan}>{currentPlan}</Text>
        <Text style={s.currentMeta}>
          {hasPaidAccess
            ? `${billing?.status || "active"}${billing?.provider ? ` · ${billing.provider}` : ""}`
            : "Free access"}
        </Text>
        {hasPaidAccess && currentPlan === "Elite Stack" && (
          <Text style={s.activeNote}>
            Elite Stack is already active on this account. You do not need to buy again to keep access.
          </Text>
        )}
        {hasPaidAccess && currentPlan === "Pro Arena" && (
          <Text style={s.activeNote}>
            Pro Arena is already active. Elite Stack remains available if you want the higher lineup limit.
          </Text>
        )}
      </View>

      {message ? (
        <View style={[s.banner, messageKind === "error" ? s.bannerError : messageKind === "success" ? s.bannerSuccess : s.bannerInfo]}>
          <Text style={s.bannerText}>{message}</Text>
        </View>
      ) : null}

      {phase === "verifying" || phase === "pending" ? (
        <View style={s.verifyRow}>
          <ActivityIndicator color="#c9a84c" />
          <Text style={s.verifyText}>
            {phase === "pending"
              ? "Purchase pending..."
              : "Purchase received. Verifying your subscription..."}
          </Text>
        </View>
      ) : null}

      {ios ? (
        <>
          <PlanSection
            title="Pro Arena"
            lineupCopy={PRO_LINEUP_COPY}
            productIds={PRO_PRODUCT_IDS}
            productById={productById}
            loading={loadingProducts}
            productsError={productsError}
            busy={busy}
            currentPlan={currentPlan}
            onPurchase={handlePurchase}
          />
          <PlanSection
            title="Elite Stack"
            lineupCopy={ELITE_LINEUP_COPY}
            productIds={ELITE_PRODUCT_IDS}
            productById={productById}
            loading={loadingProducts}
            productsError={productsError}
            busy={busy}
            currentPlan={currentPlan}
            onPurchase={handlePurchase}
          />

          <TouchableOpacity
            style={[s.restoreBtn, busy && s.btnDisabled]}
            onPress={handleRestore}
            disabled={busy}
          >
            {phase === "restoring" ? (
              <ActivityIndicator color="#c9a84c" />
            ) : (
              <Text style={s.restoreText}>Restore Purchases</Text>
            )}
          </TouchableOpacity>
        </>
      ) : (
        <View style={s.androidCard}>
          <Text style={s.androidTitle}>Apple In-App Purchases</Text>
          <Text style={s.androidBody}>
            Subscriptions are purchased through the iOS App Store. This screen shows the plan already
            on your account, including web subscriptions.
          </Text>
        </View>
      )}

      <Text style={s.disclosure}>
        Payment will be charged to your Apple ID account at confirmation of purchase. The subscription
        renews automatically unless you cancel at least 24 hours before the end of the current period.
        Your account will be charged for renewal within 24 hours prior to the end of the current period.
        You can manage and cancel subscriptions in your Apple ID account settings.
      </Text>

      <View style={s.legalRow}>
        <TouchableOpacity onPress={() => openLegal(TERMS_OF_USE_URL)}>
          <Text style={s.legalLink}>Terms of Use</Text>
        </TouchableOpacity>
        <Text style={s.legalDot}>·</Text>
        <TouchableOpacity onPress={() => openLegal(PRIVACY_POLICY_URL)}>
          <Text style={s.legalLink}>Privacy Policy</Text>
        </TouchableOpacity>
      </View>
    </ScrollView>
  );
}

function PlanSection({
  title,
  lineupCopy,
  productIds,
  productById,
  loading,
  productsError,
  busy,
  currentPlan,
  onPurchase,
}: {
  title: string;
  lineupCopy: string;
  productIds: readonly string[];
  productById: Map<string, StoreKitDisplayProduct>;
  loading: boolean;
  productsError: string | null;
  busy: boolean;
  currentPlan: string;
  onPurchase: (productId: string) => void;
}) {
  return (
    <View style={s.sectionCard}>
      <Text style={s.sectionTitle}>{title}</Text>
      <Text style={s.lineupCopy}>{lineupCopy}</Text>
      {productIds.map((productId) => {
            const catalog = getAppleProduct(productId);
        const store = productById.get(productId);
        const period = catalog?.period === "annual" ? "Annual" : "Monthly";
        const priceLine = store?.priceLine || (loading ? "Loading price..." : productsError ? "Price unavailable" : "Price unavailable");
        const cta = purchaseCta(title, currentPlan, {
          busy,
          canBuy: !!store?.displayPrice && !busy && !loading,
        });
        return (
          <View key={productId} style={s.offerRow}>
            <View style={s.offerCopy}>
              <Text style={s.offerPeriod}>{period}</Text>
              <Text style={s.offerPrice}>{priceLine}</Text>
            </View>
            <TouchableOpacity
              style={[s.buyBtn, cta.disabled && s.btnDisabled]}
              onPress={() => onPurchase(productId)}
              disabled={cta.disabled}
            >
              <Text style={s.buyText}>{cta.label}</Text>
            </TouchableOpacity>
          </View>
        );
      })}
    </View>
  );
}

const s = StyleSheet.create({
  scroll: { flex: 1, backgroundColor: "#060b1a" },
  container: { padding: 20, paddingBottom: 48, gap: 16 },
  center: { flex: 1, backgroundColor: "#060b1a", justifyContent: "center", alignItems: "center", gap: 12 },
  loadingText: { color: "#94a3b8", fontSize: 14 },
  kicker: { color: "#c9a84c", fontSize: 11, fontWeight: "800", letterSpacing: 1.4 },
  title: { color: "#fff", fontSize: 28, fontWeight: "900", lineHeight: 34 },
  subtitle: { color: "#94a3b8", fontSize: 14, lineHeight: 20, marginTop: -4 },
  currentCard: {
    backgroundColor: "#0a0f24",
    borderRadius: 16,
    padding: 18,
    borderWidth: 1,
    borderColor: "#c9a84c55",
    gap: 4,
  },
  cardLabel: { color: "#888", fontSize: 11, fontWeight: "700", textTransform: "uppercase" },
  currentPlan: { color: "#c9a84c", fontSize: 26, fontWeight: "900" },
  currentMeta: { color: "#cbd5e1", fontSize: 13 },
  activeNote: { color: "#94a3b8", fontSize: 13, lineHeight: 18, marginTop: 8 },
  banner: { borderRadius: 12, padding: 12 },
  bannerInfo: { backgroundColor: "#1e293b" },
  bannerError: { backgroundColor: "#3f1d1d" },
  bannerSuccess: { backgroundColor: "#14532d" },
  bannerText: { color: "#fff", fontSize: 14, lineHeight: 20 },
  verifyRow: { flexDirection: "row", alignItems: "center", gap: 10 },
  verifyText: { color: "#c9a84c", fontSize: 14, flex: 1 },
  sectionCard: {
    backgroundColor: "#0a0f24",
    borderRadius: 16,
    padding: 18,
    borderWidth: 1,
    borderColor: "#1e293b",
    gap: 12,
  },
  sectionTitle: { color: "#fff", fontSize: 22, fontWeight: "900" },
  lineupCopy: { color: "#cbd5e1", fontSize: 14, lineHeight: 20, marginTop: -4 },
  offerRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    gap: 12,
    backgroundColor: "#060b1a",
    borderRadius: 12,
    padding: 14,
    borderWidth: 1,
    borderColor: "#1e293b",
  },
  offerCopy: { flex: 1 },
  offerPeriod: { color: "#fff", fontSize: 16, fontWeight: "700" },
  offerPrice: { color: "#c9a84c", fontSize: 15, fontWeight: "700", marginTop: 2 },
  buyBtn: { backgroundColor: "#c9a84c", borderRadius: 10, paddingVertical: 10, paddingHorizontal: 14 },
  buyText: { color: "#000", fontWeight: "800", fontSize: 13 },
  restoreBtn: {
    borderWidth: 1,
    borderColor: "#c9a84c",
    borderRadius: 12,
    padding: 16,
    alignItems: "center",
  },
  restoreText: { color: "#c9a84c", fontWeight: "800", fontSize: 16 },
  btnDisabled: { opacity: 0.45 },
  androidCard: {
    backgroundColor: "#0a0f24",
    borderRadius: 16,
    padding: 18,
    borderWidth: 1,
    borderColor: "#1e293b",
    gap: 8,
  },
  androidTitle: { color: "#fff", fontSize: 18, fontWeight: "800" },
  androidBody: { color: "#94a3b8", fontSize: 14, lineHeight: 20 },
  disclosure: { color: "#64748b", fontSize: 12, lineHeight: 18 },
  legalRow: { flexDirection: "row", justifyContent: "center", alignItems: "center", gap: 10, paddingBottom: 8 },
  legalLink: { color: "#c9a84c", fontSize: 14, fontWeight: "700" },
  legalDot: { color: "#64748b", fontSize: 14 },
});
