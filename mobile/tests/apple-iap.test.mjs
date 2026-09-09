/**
 * Phase 3 Apple IAP / iOS paywall contracts.
 * Run: node --test tests/apple-iap.test.mjs
 */
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { test } from "node:test";
import {
  APPLE_PRODUCT_IDS,
  APPLE_CATALOG,
  PRIVACY_POLICY_URL,
  TERMS_OF_USE_URL,
  PAYWALL_TITLE,
  PRO_LINEUP_COPY,
  ELITE_LINEUP_COPY,
  displayPlanLabel,
  extractSignedTransactionJws,
  getAppleProduct,
  isAppAccountTokenUuid,
  isUserCancelledPurchase,
  localEntitlementFromPurchase,
  mapStoreKitDisplay,
  accountHasPaidAccess,
  isStaleNotificationError,
  runRestoreVerify,
  runVerifyAndRefresh,
} from "../lib/apple-catalog.mjs";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");

function read(rel) {
  return readFileSync(join(root, rel), "utf8");
}

const EXPECTED_IDS = [
  "com.sportbookme.app.pro.monthly",
  "com.sportbookme.app.pro.annual",
  "com.sportbookme.app.elite.monthly",
  "com.sportbookme.app.elite.annual",
];

test("product ID mapping matches Apple catalog", () => {
  assert.deepEqual([...APPLE_PRODUCT_IDS], EXPECTED_IDS);
  assert.equal(getAppleProduct("com.sportbookme.app.pro.monthly")?.tier, "pro");
  assert.equal(getAppleProduct("com.sportbookme.app.pro.monthly")?.period, "monthly");
  assert.equal(getAppleProduct("com.sportbookme.app.pro.monthly")?.maxLineups, 20);
  assert.equal(getAppleProduct("com.sportbookme.app.pro.annual")?.period, "annual");
  assert.equal(getAppleProduct("com.sportbookme.app.elite.monthly")?.tier, "elite");
  assert.equal(getAppleProduct("com.sportbookme.app.elite.monthly")?.maxLineups, 150);
  assert.equal(getAppleProduct("com.sportbookme.app.elite.annual")?.section, "Elite Stack");
  assert.equal(getAppleProduct("unknown"), null);
  assert.equal(APPLE_CATALOG["com.sportbookme.app.pro.monthly"].lineupCopy, PRO_LINEUP_COPY);
  assert.equal(APPLE_CATALOG["com.sportbookme.app.elite.monthly"].lineupCopy, ELITE_LINEUP_COPY);
});

test("StoreKit product display mapping uses displayPrice, not hardcoded dollars", () => {
  const mapped = mapStoreKitDisplay({
    id: "com.sportbookme.app.pro.monthly",
    displayPrice: "$49.99",
    subscriptionPeriodUnitIOS: "month",
  });
  assert.equal(mapped.displayPrice, "$49.99");
  assert.equal(mapped.periodLabel, "month");
  assert.equal(mapped.priceLine, "$49.99/month");

  const annual = mapStoreKitDisplay({
    productId: "com.sportbookme.app.elite.annual",
    displayPrice: "€599.99",
    subscriptionPeriodUnitIOS: "year",
  });
  assert.equal(annual.priceLine, "€599.99/year");

  const missing = mapStoreKitDisplay({ id: "com.sportbookme.app.pro.monthly" });
  assert.equal(missing.displayPrice, "");
  assert.equal(missing.priceLine, "");
});

test("live paywall has no hardcoded $39.99/$79.99 and no Stripe checkout", () => {
  const paywall = read("app/(tabs)/subscription.tsx");
  assert.doesNotMatch(paywall, /\$39\.99/);
  assert.doesNotMatch(paywall, /\$79\.99/);
  assert.doesNotMatch(paywall, /\$49\.99/);
  assert.doesNotMatch(paywall, /\$89\.99/);
  assert.doesNotMatch(paywall, /createCheckout/);
  assert.doesNotMatch(paywall, /openBillingPortal/);
  assert.doesNotMatch(paywall, /billing\/checkout/);
  assert.doesNotMatch(paywall, /Linking\.openURL\(r\.data\.url\)/);
  assert.match(paywall, /getAppleAccountToken/);
  assert.match(paywall, /verifyAppleTransaction/);
  assert.match(paywall, /Restore Purchases/);
  assert.match(paywall, /PAYWALL_TITLE/);
  assert.match(paywall, /Pro Arena/);
  assert.match(paywall, /Elite Stack/);
  assert.match(paywall, /PRO_LINEUP_COPY/);
  assert.match(paywall, /ELITE_LINEUP_COPY/);
  assert.match(paywall, /Purchase received\. Verifying your subscription/);
  assert.doesNotMatch(paywall, /Family Sharing/);
  assert.doesNotMatch(paywall, /is_pro\s*=\s*true/);
  assert.doesNotMatch(paywall, /setUser\(\{[\s\S]*is_pro:\s*true/);
});

test("account-token fetch uses authenticated helper and no client userId", () => {
  const api = read("lib/api.ts");
  assert.match(api, /export async function getAppleAccountToken/);
  assert.match(api, /\/billing\/apple\/account-token/);
  const tokenFn = api.match(/export async function getAppleAccountToken[\s\S]*?^export async function verifyAppleTransaction/m)?.[0] || "";
  assert.match(tokenFn, /apiFetch\("\/billing\/apple\/account-token"\)/);
  assert.doesNotMatch(tokenFn, /userId/);
  assert.doesNotMatch(tokenFn, /user_id/);
  assert.match(tokenFn, /appAccountToken/);
});

test("verify API call sends signed JWS only", () => {
  const api = read("lib/api.ts");
  assert.match(api, /export async function verifyAppleTransaction/);
  assert.match(api, /\/billing\/apple\/verify/);
  const verifyFn = api.match(/export async function verifyAppleTransaction[\s\S]*?^export async function verifyAppleTransactions/m)?.[0] || "";
  assert.match(verifyFn, /signedTransaction/);
  assert.doesNotMatch(verifyFn, /userId/);
  assert.doesNotMatch(verifyFn, /is_pro/);
  assert.doesNotMatch(verifyFn, /sandbox:\s*true/);
});

test("purchase success does not locally grant entitlement", async () => {
  assert.equal(localEntitlementFromPurchase(), null);
  const account = { plan: "Starter", has_access: false };
  const verified = await runVerifyAndRefresh({
    signedJws: "aaa.bbb.ccc-this-is-long-enough-to-look-like-jws-payload",
    verifyAppleTransaction: async (jws) => {
      assert.match(jws, /aaa\.bbb\.ccc/);
      return { data: { granted: true, tier: "pro" } };
    },
    refreshAccount: async () => account,
  });
  assert.equal(verified.localEntitlement, null);
  assert.equal(verified.account, account);
  assert.equal(displayPlanLabel(account.plan, account.has_access), "Free");
});

test("restore sends signed transactions to backend verify", async () => {
  const jws = "header.payload.signature-restore-jws-value-is-long-enough";
  let sent = null;
  const result = await runRestoreVerify({
    purchases: [{ purchaseToken: jws, productId: "com.sportbookme.app.pro.monthly" }],
    verifyAppleTransactions: async (list) => {
      sent = list;
      return { data: { granted: true } };
    },
    refreshAccount: async () => ({ plan: "Pro Arena", has_access: true }),
  });
  assert.deepEqual(sent, [jws]);
  assert.equal(result.kind, "verified");
  assert.equal(result.localEntitlement, null);
});

test("restore found nothing does not grant locally", async () => {
  const result = await runRestoreVerify({
    purchases: [{ productId: "com.sportbookme.app.pro.monthly" }],
    verifyAppleTransactions: async () => {
      throw new Error("verify should not run");
    },
    refreshAccount: async () => {
      throw new Error("refresh should not run");
    },
  });
  assert.equal(result.kind, "empty");
  assert.equal(result.localEntitlement, null);
});

test("backend-confirmed entitlement refresh drives plan display", async () => {
  const refreshed = await runVerifyAndRefresh({
    signedJws: "header.payload.signature-verify-jws-value-is-long-enough",
    verifyAppleTransaction: async () => ({ data: { granted: true, tier: "elite" } }),
    refreshAccount: async () => ({ plan: "Elite Stack", has_access: true, provider: "apple" }),
  });
  assert.equal(displayPlanLabel(refreshed.account.plan, refreshed.account.has_access), "Elite Stack");
  assert.equal(refreshed.localEntitlement, null);
});

test("web subscriber displays current server tier", () => {
  assert.equal(displayPlanLabel("Starter", false), "Free");
  assert.equal(displayPlanLabel("Free", false), "Free");
  assert.equal(displayPlanLabel("Pro Arena", true), "Pro Arena");
  assert.equal(displayPlanLabel("Pro Arena Annual", true), "Pro Arena");
  assert.equal(displayPlanLabel("Elite Stack", true), "Elite Stack");
  assert.equal(displayPlanLabel("Elite Stack Annual", true), "Elite Stack");
  assert.equal(displayPlanLabel("Starter", true), "Free");
});

test("purchase canceled path is detected without granting access", () => {
  assert.equal(isUserCancelledPurchase({ code: "user-cancelled" }), true);
  assert.equal(isUserCancelledPurchase({ message: "User cancelled the purchase" }), true);
  assert.equal(isUserCancelledPurchase({ code: "network-error" }), false);
  assert.equal(localEntitlementFromPurchase(), null);
  const paywall = read("app/(tabs)/subscription.tsx");
  assert.match(paywall, /Purchase canceled/);
  assert.match(paywall, /kind === "canceled"/);
});

test("verification failure path does not grant locally", async () => {
  let refreshed = false;
  await assert.rejects(
    () => runVerifyAndRefresh({
      signedJws: "header.payload.signature-failed-jws-value-is-long-enough",
      verifyAppleTransaction: async () => {
        throw new Error("invalid_signature");
      },
      refreshAccount: async () => {
        refreshed = true;
        return { plan: "Pro Arena", has_access: true };
      },
    }),
    /invalid_signature/,
  );
  assert.equal(refreshed, true);
  assert.equal(localEntitlementFromPurchase(), null);
});

test("stale_notification refreshes and shows current paid plan", async () => {
  let refreshed = false;
  const result = await runVerifyAndRefresh({
    signedJws: "header.payload.signature-stale-jws-value-is-long-enough",
    verifyAppleTransaction: async () => {
      throw new Error("stale_notification");
    },
    refreshAccount: async () => {
      refreshed = true;
      return { plan: "Pro Arena", has_access: true, provider: "apple" };
    },
  });
  assert.equal(refreshed, true);
  assert.equal(result.recoveredFromRefresh, true);
  assert.equal(result.localEntitlement, null);
  assert.equal(displayPlanLabel(result.account.plan, result.account.has_access), "Pro Arena");
  assert.equal(accountHasPaidAccess(result.account), true);
  assert.equal(isStaleNotificationError(new Error("stale_notification")), true);
});

test("stale_notification without paid access still fails", async () => {
  let refreshed = false;
  await assert.rejects(
    () => runVerifyAndRefresh({
      signedJws: "header.payload.signature-stale-free-jws-value-is-long-enough",
      verifyAppleTransaction: async () => {
        throw new Error("stale_notification");
      },
      refreshAccount: async () => {
        refreshed = true;
        return { plan: "Starter", has_access: false };
      },
    }),
    /stale_notification/,
  );
  assert.equal(refreshed, true);
  assert.equal(localEntitlementFromPurchase(), null);
});

test("restore succeeds from already-current entitlement", async () => {
  const jws = "header.payload.signature-restore-stale-jws-value-is-long-enough";
  let refreshed = false;
  const result = await runRestoreVerify({
    purchases: [{ purchaseToken: jws, productId: "com.sportbookme.app.pro.monthly" }],
    verifyAppleTransactions: async () => {
      throw new Error("stale_notification");
    },
    refreshAccount: async () => {
      refreshed = true;
      return { plan: "Pro Arena", has_access: true, provider: "apple" };
    },
  });
  assert.equal(refreshed, true);
  assert.equal(result.kind, "verified");
  assert.equal(result.recoveredFromRefresh, true);
  assert.equal(result.localEntitlement, null);
  assert.equal(displayPlanLabel(result.account.plan, result.account.has_access), "Pro Arena");
});

test("restore does not swallow unrelated verify errors", async () => {
  let refreshed = false;
  await assert.rejects(
    () => runRestoreVerify({
      purchases: [{
        purchaseToken: "header.payload.signature-restore-bad-jws-value-is-long-enough",
      }],
      verifyAppleTransactions: async () => {
        throw new Error("invalid_signature");
      },
      refreshAccount: async () => {
        refreshed = true;
        return { plan: "Pro Arena", has_access: true };
      },
    }),
    /invalid_signature/,
  );
  assert.equal(refreshed, true);
  assert.equal(localEntitlementFromPurchase(), null);
});

test("JWS extraction and appAccountToken UUID checks", () => {
  assert.equal(
    extractSignedTransactionJws({
      purchaseToken: "aaa.bbb.ccc-signed-apple-jws-token-value-here",
    }),
    "aaa.bbb.ccc-signed-apple-jws-token-value-here",
  );
  assert.equal(extractSignedTransactionJws({ purchaseToken: "not-jws" }), null);
  assert.equal(isAppAccountTokenUuid("2f1d0c3a-1111-4111-8111-aaaaaaaaaaaa"), true);
  assert.equal(isAppAccountTokenUuid("42"), false);
  const iap = read("lib/apple-iap.ts");
  assert.match(iap, /appAccountToken/);
  assert.match(iap, /andDangerouslyFinishTransactionAutomatically:\s*false/);
});

test("active subscriber CTAs do not change SKUs or StoreKit verify", () => {
  const paywall = read("app/(tabs)/subscription.tsx");
  assert.match(paywall, /purchaseCta/);
  assert.match(paywall, /canStartPurchase/);
  assert.match(paywall, /Restore Purchases/);
  assert.match(paywall, /verifyAppleTransaction/);
  assert.match(paywall, /getAppleAccountToken/);
  assert.doesNotMatch(paywall, /createCheckout/);
  const catalog = read("lib/apple-catalog.mjs");
  assert.match(catalog, /com\.sportbookme\.app\.pro\.monthly/);
  assert.match(catalog, /com\.sportbookme\.app\.elite\.monthly/);
});

test("legal URLs are the existing public pages", () => {
  assert.equal(PRIVACY_POLICY_URL, "https://sbmedfsai.com/privacy");
  assert.equal(TERMS_OF_USE_URL, "https://sbmedfsai.com/terms");
  assert.equal(PAYWALL_TITLE, "Sportbook Me Premium Plans");
  const paywall = read("app/(tabs)/subscription.tsx");
  assert.match(paywall, /TERMS_OF_USE_URL/);
  assert.match(paywall, /PRIVACY_POLICY_URL/);
});

test("expo-iap is configured without a committed ios/ directory", () => {
  const pkg = JSON.parse(read("package.json"));
  assert.equal(pkg.dependencies["expo-iap"], "^5.5.1");
  const app = read("app.json");
  assert.match(app, /"expo-iap"/);
  assert.match(app, /"bundleIdentifier": "com\.sportbookme\.app"/);
});
