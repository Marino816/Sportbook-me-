/**
 * Apple IAP product mapping for the mobile paywall.
 * Prices come from StoreKit displayPrice — never from hardcoded dollar strings.
 */

export {
  APPLE_BUNDLE_ID,
  APPLE_PRODUCT_IDS,
  APPLE_CATALOG,
  PRO_PRODUCT_IDS,
  ELITE_PRODUCT_IDS,
  PRO_LINEUP_COPY,
  ELITE_LINEUP_COPY,
  PRIVACY_POLICY_URL,
  TERMS_OF_USE_URL,
  PAYWALL_TITLE,
  isAppAccountTokenUuid,
  getAppleProduct,
  displayPlanLabel,
  mapStoreKitDisplay,
} from "./apple-catalog.mjs";
