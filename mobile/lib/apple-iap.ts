/**
 * StoreKit 2 wrapper via expo-iap.
 * Purchase success is not an entitlement. Backend verify + /auth/me refresh are.
 */

import { Platform } from "react-native";
import {
  ErrorCode,
  endConnection,
  fetchProducts,
  finishTransaction,
  getAvailablePurchases,
  initConnection,
  purchaseErrorListener,
  purchaseUpdatedListener,
  requestPurchase,
  restorePurchases as restoreStoreKitPurchases,
  type ProductSubscription,
  type Purchase,
} from "expo-iap";
import {
  APPLE_PRODUCT_IDS,
  extractSignedTransactionJws,
  isAppAccountTokenUuid,
  isUserCancelledPurchase,
  mapStoreKitDisplay,
  runRestoreVerify,
  runVerifyAndRefresh,
} from "./apple-catalog.mjs";

export type StoreKitDisplayProduct = {
  productId: string;
  displayPrice: string;
  periodLabel: string;
  priceLine: string;
  title: string;
};

export type PurchaseAttemptResult =
  | { kind: "purchased"; purchase: Purchase; signedJws: string }
  | { kind: "pending" }
  | { kind: "canceled" };

const PURCHASE_TIMEOUT_MS = 120_000;

export function isIosAppleIap(): boolean {
  return Platform.OS === "ios";
}

export async function connectAppleIap(): Promise<void> {
  if (!isIosAppleIap()) return;
  await initConnection();
}

export async function disconnectAppleIap(): Promise<void> {
  if (!isIosAppleIap()) return;
  try {
    await endConnection();
  } catch {
    /* ignore */
  }
}

export async function fetchAppleSubscriptionProducts(): Promise<StoreKitDisplayProduct[]> {
  if (!isIosAppleIap()) return [];
  const products = (await fetchProducts({
    skus: [...APPLE_PRODUCT_IDS],
    type: "subs",
  })) as ProductSubscription[] | null;
  const mapped: StoreKitDisplayProduct[] = [];
  for (const product of products || []) {
    const display = mapStoreKitDisplay(product);
    if (!display.productId) continue;
    mapped.push({
      ...display,
      title: String(product.title || product.displayName || display.productId),
    });
  }
  return mapped;
}

function asPurchase(value: unknown): Purchase | null {
  if (!value || typeof value !== "object") return null;
  if (Array.isArray(value)) {
    for (const item of value) {
      const purchase = asPurchase(item);
      if (purchase) return purchase;
    }
    return null;
  }
  const record = value as Purchase;
  if (record.productId || record.purchaseToken || record.id) return record;
  return null;
}

export async function startAppleSubscriptionPurchase(
  productId: string,
  appAccountToken: string,
): Promise<PurchaseAttemptResult> {
  if (!isIosAppleIap()) {
    throw new Error("Apple In-App Purchase is only available on iOS");
  }
  if (!isAppAccountTokenUuid(appAccountToken)) {
    throw new Error("Invalid Apple account token");
  }

  return new Promise<PurchaseAttemptResult>((resolve, reject) => {
    let settled = false;
    const finish = (fn: () => void) => {
      if (settled) return;
      settled = true;
      clearTimeout(timer);
      updated.remove();
      errored.remove();
      fn();
    };

    const updated = purchaseUpdatedListener((purchase) => {
      if (purchase.purchaseState === "pending") {
        finish(() => resolve({ kind: "pending" }));
        return;
      }
      const signedJws = extractSignedTransactionJws(purchase as unknown as Record<string, unknown>);
      if (!signedJws) {
        finish(() => reject(new Error("missing_signed_transaction")));
        return;
      }
      finish(() => resolve({ kind: "purchased", purchase, signedJws }));
    });

    const errored = purchaseErrorListener((error) => {
      if (error.code === ErrorCode.UserCancelled || isUserCancelledPurchase(error)) {
        finish(() => resolve({ kind: "canceled" }));
        return;
      }
      finish(() => reject(error));
    });

    const timer = setTimeout(() => {
      finish(() => reject(new Error("Purchase timed out")));
    }, PURCHASE_TIMEOUT_MS);

    requestPurchase({
      type: "subs",
      request: {
        apple: {
          sku: productId,
          appAccountToken,
          andDangerouslyFinishTransactionAutomatically: false,
        },
      },
    })
      .then((result) => {
        const purchase = asPurchase(result);
        if (!purchase || settled) return;
        if (purchase.purchaseState === "pending") {
          finish(() => resolve({ kind: "pending" }));
          return;
        }
        const signedJws = extractSignedTransactionJws(purchase as unknown as Record<string, unknown>);
        if (signedJws) {
          finish(() => resolve({ kind: "purchased", purchase, signedJws }));
        }
      })
      .catch((error) => {
        if (isUserCancelledPurchase(error)) {
          finish(() => resolve({ kind: "canceled" }));
          return;
        }
        finish(() => reject(error));
      });
  });
}

export async function finishVerifiedApplePurchase(purchase: Purchase): Promise<void> {
  await finishTransaction({ purchase, isConsumable: false });
}

export async function collectRestorableApplePurchases(): Promise<Purchase[]> {
  if (!isIosAppleIap()) return [];
  try {
    await restoreStoreKitPurchases();
  } catch {
    /* getAvailablePurchases is the source of signed transactions */
  }
  let purchases = await getAvailablePurchases({ onlyIncludeActiveItemsIOS: true });
  if (!Array.isArray(purchases) || purchases.length === 0) {
    purchases = await getAvailablePurchases();
  }
  return Array.isArray(purchases) ? purchases : [];
}

export {
  extractSignedTransactionJws,
  isUserCancelledPurchase,
  runRestoreVerify,
  runVerifyAndRefresh,
};
