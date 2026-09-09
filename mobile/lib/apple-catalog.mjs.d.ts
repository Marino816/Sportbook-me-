export const APPLE_BUNDLE_ID: string;
export const APPLE_PRODUCT_IDS: readonly string[];
export const PRO_PRODUCT_IDS: readonly string[];
export const ELITE_PRODUCT_IDS: readonly string[];
export const PRO_LINEUP_COPY: string;
export const ELITE_LINEUP_COPY: string;
export const PRIVACY_POLICY_URL: string;
export const TERMS_OF_USE_URL: string;
export const PAYWALL_TITLE: string;

export type AppleTier = "pro" | "elite";
export type ApplePeriod = "monthly" | "annual";

export type AppleCatalogEntry = {
  productId: string;
  tier: AppleTier;
  period: ApplePeriod;
  section: "Pro Arena" | "Elite Stack";
  maxLineups: number;
  lineupCopy: string;
};

export const APPLE_CATALOG: Record<string, AppleCatalogEntry>;

export function isAppAccountTokenUuid(value: unknown): boolean;
export function getAppleProduct(productId: string): AppleCatalogEntry | null;
export function displayPlanLabel(plan: string | null | undefined, hasAccess?: boolean): string;
export function mapStoreKitDisplay(product: {
  id?: string;
  productId?: string;
  displayPrice?: string;
  subscriptionPeriodUnitIOS?: string | null;
  subscriptionPeriodUnit?: string | null;
}): {
  productId: string;
  displayPrice: string;
  periodLabel: string;
  priceLine: string;
};
export function extractSignedTransactionJws(
  purchase: Record<string, unknown> | null | undefined,
): string | null;
export function isUserCancelledPurchase(error: unknown): boolean;
export function localEntitlementFromPurchase(): null;
export function isStaleNotificationError(error: unknown): boolean;
export function accountHasPaidAccess(account: unknown): boolean;
export function runVerifyAndRefresh(args: {
  signedJws: string;
  verifyAppleTransaction: (jws: string) => Promise<unknown>;
  refreshAccount: () => Promise<unknown>;
}): Promise<{
  verified: unknown;
  account: unknown;
  localEntitlement: null;
  recoveredFromRefresh?: boolean;
}>;
export function runRestoreVerify(args: {
  purchases: unknown[];
  extractJws?: (purchase: unknown) => string | null;
  verifyAppleTransactions: (jwsList: string[]) => Promise<unknown>;
  refreshAccount: () => Promise<unknown>;
}): Promise<{
  kind: "empty" | "verified";
  signedTransactions: string[];
  verified?: unknown;
  account?: unknown;
  localEntitlement: null;
  recoveredFromRefresh?: boolean;
}>;
