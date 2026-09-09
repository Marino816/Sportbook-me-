/**
 * Paywall purchase-button labels. Does not grant entitlements or change SKUs.
 */

export function purchaseCta(sectionTitle, currentPlan, opts = {}) {
  const section = String(sectionTitle || "");
  const plan = String(currentPlan || "");
  const busy = opts.busy === true;
  const canBuy = opts.canBuy !== false;
  if (plan === "Elite Stack") {
    return {
      disabled: true,
      label: section === "Elite Stack" ? "Current plan" : "Included",
    };
  }
  if (plan === "Pro Arena" && section === "Pro Arena") {
    return { disabled: true, label: "Current plan" };
  }
  return {
    disabled: !canBuy,
    label: busy ? "Please wait" : "Subscribe",
  };
}

export function canStartPurchase(productId, currentPlan) {
  const plan = String(currentPlan || "");
  const id = String(productId || "");
  if (plan === "Elite Stack") return false;
  if (plan === "Pro Arena" && id.includes(".pro.")) return false;
  return true;
}
