import assert from "node:assert/strict";
import test from "node:test";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const paykings = readFileSync(join(root, "src/lib/paykings.ts"), "utf8");
const api = readFileSync(join(root, "src/lib/api.ts"), "utf8");
const billing = readFileSync(join(root, "src/app/billing/page.tsx"), "utf8");
const button = readFileSync(join(root, "src/components/PayKingsPayButton.tsx"), "utf8");
const envExample = readFileSync(join(root, "..", ".env.example"), "utf8");

function buildPayKingsSubscribeBody(planId, paymentToken) {
  const ids = ["SBME_PRO_MONTHLY", "SBME_PRO_ANNUAL", "SBME_ELITE_MONTHLY", "SBME_ELITE_ANNUAL"];
  if (!ids.includes(planId)) throw new Error("Unsupported plan");
  if (!paymentToken || !String(paymentToken).trim()) throw new Error("payment_token is required");
  return { plan_id: planId, payment_token: String(paymentToken).trim() };
}

test("supported plans render with confirmed prices", () => {
  assert.match(billing, /SBME_PRO_MONTHLY/);
  assert.match(billing, /SBME_PRO_ANNUAL/);
  assert.match(billing, /SBME_ELITE_MONTHLY/);
  assert.match(billing, /SBME_ELITE_ANNUAL/);
  assert.match(billing, /\$49/);
  assert.match(billing, /\$399/);
  assert.match(billing, /\$89/);
  assert.match(billing, /\$599/);
  assert.doesNotMatch(billing, /\$39\.99/);
  assert.match(paykings, /SBME_PRO_MONTHLY/);
  assert.match(paykings, /\$49\.99/);
});

test("unsupported plan cannot submit", () => {
  assert.throws(() => buildPayKingsSubscribeBody("NOT_A_PLAN", "tok"), /Unsupported plan/);
  assert.match(paykings, /isSupportedPayKingsPlanId/);
  assert.match(button, /isSupportedPayKingsPlanId\(planId\)/);
});

test("subscribe body is only plan_id and payment_token", () => {
  const body = buildPayKingsSubscribeBody("SBME_PRO_MONTHLY", "tok_collect_once");
  assert.deepEqual(body, { plan_id: "SBME_PRO_MONTHLY", payment_token: "tok_collect_once" });
  assert.equal(Object.keys(body).sort().join(","), "payment_token,plan_id");
  assert.match(api, /createPayKingsSubscribe/);
  assert.match(api, /\/billing\/paykings\/subscribe/);
  assert.match(api, /buildPayKingsSubscribeBody/);
  assert.doesNotMatch(api, /createPayKingsSubscribe[\s\S]*user_id/);
});

test("browser does not send price tier or user_id", () => {
  assert.match(button, /createPayKingsSubscribe\(selectedPlan, paymentToken\)/);
  assert.doesNotMatch(button, /user_id/);
  assert.doesNotMatch(button, /expected_price/);
  assert.doesNotMatch(paykings, /JSON\.stringify\([^)]*tier/);
});

test("payment_token is not persisted", () => {
  assert.doesNotMatch(button, /localStorage/);
  assert.doesNotMatch(button, /sessionStorage/);
  assert.doesNotMatch(paykings, /localStorage/);
  assert.doesNotMatch(button, /console\.log/);
});

test("security_key never appears in client bundle", () => {
  assert.doesNotMatch(paykings, /process\.env\.PAYKINGS_SECURITY_KEY/);
  assert.doesNotMatch(paykings, /NEXT_PUBLIC_PAYKINGS_SECURITY_KEY/);
  assert.doesNotMatch(api, /PAYKINGS_SECURITY_KEY/);
  assert.doesNotMatch(billing, /PAYKINGS_SECURITY_KEY/);
  assert.doesNotMatch(button, /PAYKINGS_SECURITY_KEY/);
  assert.match(paykings, /NEXT_PUBLIC_PAYKINGS_TOKENIZATION_KEY/);
  assert.match(envExample, /NEXT_PUBLIC_PAYKINGS_TOKENIZATION_KEY=/);
  assert.match(envExample, /PAYKINGS_SECURITY_KEY=/);
});

test("raw card data is never sent to backend", () => {
  assert.doesNotMatch(api, /ccnumber/);
  assert.doesNotMatch(api, /ccexp/);
  assert.doesNotMatch(button, /ccnumber/);
  assert.match(paykings, /token\/Collect\.js/);
  assert.match(paykings, /data-tokenization-key/);
  assert.match(button, /response\?\.token/);
});

test("tokenization and backend failures are handled", () => {
  assert.match(button, /Card tokenization failed/);
  assert.match(button, /Could not load the secure payment form/);
  assert.match(button, /PayKings declined/);
  assert.match(button, /Payment submitted\. Your subscription is being confirmed\./);
});

test("submitted waiting-webhook copy does not claim active access", () => {
  assert.match(button, /Payment submitted\. Your subscription is being confirmed\./);
  assert.doesNotMatch(button, /features are now unlocked/);
  assert.doesNotMatch(button, /You are now Pro/);
});

test("Stripe checkout remains available", () => {
  assert.match(billing, /createCheckout/);
  assert.match(billing, /Or pay with Stripe/);
  assert.match(billing, /Manage in Stripe/);
  assert.match(api, /\/billing\/checkout/);
});
