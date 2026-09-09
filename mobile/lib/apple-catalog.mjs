/**
 * Apple IAP catalog and purchase-verification helpers.
 * Entitlement is never granted locally — only after backend verify + refresh.
 */

export const APPLE_BUNDLE_ID = "com.sportbookme.app";

export const APPLE_PRODUCT_IDS = Object.freeze([
  "com.sportbookme.app.pro.monthly",
  "com.sportbookme.app.pro.annual",
  "com.sportbookme.app.elite.monthly",
  "com.sportbookme.app.elite.annual",
]);

export const PRO_LINEUP_COPY = "20 AI-powered DFS & Parlay lineups per slate";
export const ELITE_LINEUP_COPY = "150 AI-powered DFS & Parlay lineups per slate";

export const PRIVACY_POLICY_URL = "https://sbmedfsai.com/privacy";
export const TERMS_OF_USE_URL = "https://sbmedfsai.com/terms";
export const PAYWALL_TITLE = "Sportbook Me Premium Plans";

export const APPLE_CATALOG = Object.freeze({
  "com.sportbookme.app.pro.monthly": Object.freeze({
    productId: "com.sportbookme.app.pro.monthly",
    tier: "pro",
    period: "monthly",
    section: "Pro Arena",
    maxLineups: 20,
    lineupCopy: PRO_LINEUP_COPY,
  }),
  "com.sportbookme.app.pro.annual": Object.freeze({
    productId: "com.sportbookme.app.pro.annual",
    tier: "pro",
    period: "annual",
    section: "Pro Arena",
    maxLineups: 20,
    lineupCopy: PRO_LINEUP_COPY,
  }),
  "com.sportbookme.app.elite.monthly": Object.freeze({
    productId: "com.sportbookme.app.elite.monthly",
    tier: "elite",
    period: "monthly",
    section: "Elite Stack",
    maxLineups: 150,
    lineupCopy: ELITE_LINEUP_COPY,
  }),
  "com.sportbookme.app.elite.annual": Object.freeze({
    productId: "com.sportbookme.app.elite.annual",
    tier: "elite",
    period: "annual",
    section: "Elite Stack",
    maxLineups: 150,
    lineupCopy: ELITE_LINEUP_COPY,
  }),
});

export const PRO_PRODUCT_IDS = Object.freeze([
  "com.sportbookme.app.pro.monthly",
  "com.sportbookme.app.pro.annual",
]);

export const ELITE_PRODUCT_IDS = Object.freeze([
  "com.sportbookme.app.elite.monthly",
  "com.sportbookme.app.elite.annual",
]);

const UUID_RE =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

export function isAppAccountTokenUuid(value) {
  return typeof value === "string" && UUID_RE.test(value.trim());
}

export function getAppleProduct(productId) {
  if (!productId || typeof productId !== "string") return null;
  return APPLE_CATALOG[productId.trim()] || null;
}

export function displayPlanLabel(plan, hasAccess) {
  const name = String(plan || "").trim();
  const lower = name.toLowerCase();
  if (lower.includes("elite")) return "Elite Stack";
  if (lower.includes("pro")) return "Pro Arena";
  if (hasAccess === true && name && lower !== "starter" && lower !== "free") {
    return name;
  }
  return "Free";
}

export function mapStoreKitDisplay(product) {
  const productId = String(product?.id || product?.productId || "").trim();
  const rawPrice = typeof product?.displayPrice === "string" ? product.displayPrice.trim() : "";
  const unit = String(
    product?.subscriptionPeriodUnitIOS || product?.subscriptionPeriodUnit || "",
  ).toLowerCase();
  let periodLabel = "";
  if (unit.includes("year")) periodLabel = "year";
  else if (unit.includes("month")) periodLabel = "month";
  else if (unit.includes("week")) periodLabel = "week";
  else {
    const entry = getAppleProduct(productId);
    if (entry?.period === "annual") periodLabel = "year";
    else if (entry?.period === "monthly") periodLabel = "month";
  }
  return {
    productId,
    displayPrice: rawPrice,
    periodLabel,
    priceLine: rawPrice ? (periodLabel ? `${rawPrice}/${periodLabel}` : rawPrice) : "",
  };
}

export function extractSignedTransactionJws(purchase) {
  if (!purchase || typeof purchase !== "object") return null;
  const candidates = [
    purchase.purchaseToken,
    purchase.jwsRepresentationIOS,
    purchase.jwsRepresentation,
    purchase.verificationResultIOS,
    purchase.signedTransaction,
  ];
  for (const value of candidates) {
    if (typeof value !== "string") continue;
    const trimmed = value.trim();
    if (trimmed.split(".").length === 3 && trimmed.length > 40) return trimmed;
  }
  return null;
}

export function isUserCancelledPurchase(error) {
  if (!error || typeof error !== "object") return false;
  const code = String(error.code || "").toLowerCase();
  if (
    code === "user-cancelled" ||
    code === "e_user_cancelled" ||
    code.includes("user-cancelled") ||
    code.includes("user_cancelled")
  ) {
    return true;
  }
  const message = String(error.message || "").toLowerCase();
  return (
    message.includes("user cancelled") ||
    message.includes("user canceled") ||
    message.includes("cancelled by user") ||
    message.includes("canceled by user")
  );
}

/** StoreKit success must never become a local entitlement. */
export function localEntitlementFromPurchase() {
  return null;
}

export function isStaleNotificationError(error) {
  if (!error) return false;
  const detail = typeof error.detail === "string" ? error.detail : "";
  if (detail === "stale_notification") return true;
  const message = String(error.message || error);
  return message === "stale_notification" || message.includes("stale_notification");
}

export function accountHasPaidAccess(account) {
  if (!account || typeof account !== "object") return false;
  const hasAccess = account.has_access === true || account.is_pro === true;
  if (!hasAccess) return false;
  const label = displayPlanLabel(account.plan, true);
  return label === "Pro Arena" || label === "Elite Stack";
}

function recoverFromAlreadyCurrent(verifiedError, account) {
  return isStaleNotificationError(verifiedError) && accountHasPaidAccess(account);
}

export async function runVerifyAndRefresh({
  signedJws,
  verifyAppleTransaction,
  refreshAccount,
}) {
  if (!signedJws || typeof signedJws !== "string") {
    throw new Error("missing_signed_transaction");
  }
  let verified = null;
  let verifyError = null;
  try {
    verified = await verifyAppleTransaction(signedJws);
  } catch (error) {
    verifyError = error;
  }
  const account = await refreshAccount();
  if (verifyError) {
    if (recoverFromAlreadyCurrent(verifyError, account)) {
      return {
        verified: { alreadyCurrent: true, decision: "already_current" },
        account,
        localEntitlement: localEntitlementFromPurchase(),
        recoveredFromRefresh: true,
      };
    }
    throw verifyError;
  }
  return {
    verified,
    account,
    localEntitlement: localEntitlementFromPurchase(),
  };
}

export async function runRestoreVerify({
  purchases,
  extractJws = extractSignedTransactionJws,
  verifyAppleTransactions,
  refreshAccount,
}) {
  const signedTransactions = [];
  for (const purchase of purchases || []) {
    const jws = extractJws(purchase);
    if (jws) signedTransactions.push(jws);
  }
  if (signedTransactions.length === 0) {
    return {
      kind: "empty",
      signedTransactions: [],
      localEntitlement: localEntitlementFromPurchase(),
    };
  }
  let verified = null;
  let verifyError = null;
  try {
    verified = await verifyAppleTransactions(signedTransactions);
  } catch (error) {
    verifyError = error;
  }
  const account = await refreshAccount();
  if (verifyError) {
    if (recoverFromAlreadyCurrent(verifyError, account)) {
      return {
        kind: "verified",
        signedTransactions,
        verified: { alreadyCurrent: true, decision: "already_current" },
        account,
        localEntitlement: localEntitlementFromPurchase(),
        recoveredFromRefresh: true,
      };
    }
    throw verifyError;
  }
  return {
    kind: "verified",
    signedTransactions,
    verified,
    account,
    localEntitlement: localEntitlementFromPurchase(),
  };
}
