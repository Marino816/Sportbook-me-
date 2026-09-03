/**
 * PayKings Collect.js helpers and Sportbook Me plan display (frontend).
 *
 * Official Collect.js (PayKings Integration Portal):
 *   script: https://paykings.transactiongateway.com/token/Collect.js
 *   attribute: data-tokenization-key
 *   callback response.token is the single-use payment_token
 *
 * The tokenization key is a public Collect.js key from Settings > Security Keys
 * (public key + Tokenization permission). It is not the Payment API security key.
 */

export const COLLECT_JS_SRC = "https://paykings.transactiongateway.com/token/Collect.js";

export const PAYKINGS_PLAN_IDS = [
  "SBME_PRO_MONTHLY",
  "SBME_PRO_ANNUAL",
  "SBME_ELITE_MONTHLY",
  "SBME_ELITE_ANNUAL",
] as const;

export type PayKingsPlanId = (typeof PAYKINGS_PLAN_IDS)[number];

export type PayKingsPlanDisplay = {
  planId: PayKingsPlanId;
  stripePlan: string;
  name: string;
  priceLabel: string;
  period: string;
  blurb?: string;
};

export const PAYKINGS_PLANS: PayKingsPlanDisplay[] = [
  { planId: "SBME_PRO_MONTHLY", stripePlan: "Pro Arena", name: "Pro Arena", priceLabel: "$49.99", period: "/mo" },
  { planId: "SBME_PRO_ANNUAL", stripePlan: "Pro Arena Annual", name: "Pro Arena Annual", priceLabel: "$399.99", period: "/yr", blurb: "Best value" },
  { planId: "SBME_ELITE_MONTHLY", stripePlan: "Elite Stack", name: "Elite Stack", priceLabel: "$89.99", period: "/mo" },
  { planId: "SBME_ELITE_ANNUAL", stripePlan: "Elite Stack Annual", name: "Elite Stack Annual", priceLabel: "$599.99", period: "/yr" },
];

export function isSupportedPayKingsPlanId(planId: string): planId is PayKingsPlanId {
  return (PAYKINGS_PLAN_IDS as readonly string[]).includes(planId);
}

export function buildPayKingsSubscribeBody(planId: string, paymentToken: string): { plan_id: PayKingsPlanId; payment_token: string } {
  if (!isSupportedPayKingsPlanId(planId)) {
    throw new Error("Unsupported plan");
  }
  if (!paymentToken || !paymentToken.trim()) {
    throw new Error("payment_token is required");
  }
  return { plan_id: planId, payment_token: paymentToken.trim() };
}

export type CollectJsTokenResponse = {
  tokenType?: string;
  token: string;
};

export function getPayKingsTokenizationKey(): string {
  return (process.env.NEXT_PUBLIC_PAYKINGS_TOKENIZATION_KEY || "").trim();
}

declare global {
  interface Window {
    CollectJS?: {
      configure: (opts: {
        paymentType?: string;
        callback?: (response: CollectJsTokenResponse) => void;
      }) => void;
      startPaymentRequest: (event?: Event) => void;
      closePaymentRequest?: () => void;
    };
  }
}

export function loadCollectJs(tokenizationKey: string): Promise<void> {
  return new Promise((resolve, reject) => {
    if (typeof window === "undefined") {
      reject(new Error("Collect.js requires a browser"));
      return;
    }
    if (!tokenizationKey) {
      reject(new Error("PayKings tokenization key is not configured"));
      return;
    }
    if (window.CollectJS) {
      resolve();
      return;
    }
    const existing = document.querySelector(`script[src="${COLLECT_JS_SRC}"]`) as HTMLScriptElement | null;
    if (existing) {
      existing.addEventListener("load", () => resolve(), { once: true });
      existing.addEventListener("error", () => reject(new Error("Collect.js failed to load")), { once: true });
      return;
    }
    const script = document.createElement("script");
    script.src = COLLECT_JS_SRC;
    script.async = true;
    script.setAttribute("data-tokenization-key", tokenizationKey);
    script.onload = () => resolve();
    script.onerror = () => reject(new Error("Collect.js failed to load"));
    document.head.appendChild(script);
  });
}
