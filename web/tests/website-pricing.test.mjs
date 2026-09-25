import assert from "node:assert/strict";
import test from "node:test";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const read = (rel) => readFileSync(join(root, rel), "utf8");

const pricing = read("src/lib/website-pricing.ts");
const home = read("src/app/page.tsx");
const billing = read("src/app/billing/page.tsx");
const terms = read("src/app/terms/page.tsx");
const refund = read("src/app/refund-policy/page.tsx");
const legal = read("src/components/legal/legal-page.tsx");
const layout = read("src/app/layout.tsx");
const appStore = read("src/lib/app-store.ts");
const api = read("src/lib/api.ts");

const DISCLAIMER =
  "SB ME is sports analytics and DFS intelligence software. We do not accept wagers, hold betting funds, or place bets.";
const APP_STORE_URL = "https://apps.apple.com/app/sportbook-me-dfs-ai/id6808706342";
const CTA = "Download Sportbook Me DFS AI for iPhone";

const ACTIVE_PAGES = [
  ["homepage", home],
  ["billing", billing],
  ["terms", terms],
  ["refund", refund],
  ["legal footer", legal],
  ["website pricing", pricing],
];

test("canonical source lists the four approved prices", () => {
  assert.match(pricing, /proMonthly:\s*49\.99/);
  assert.match(pricing, /proAnnual:\s*399\.99/);
  assert.match(pricing, /eliteMonthly:\s*89\.99/);
  assert.match(pricing, /eliteAnnual:\s*599\.99/);
  assert.match(pricing, /proMonthly:\s*"Pro Arena"/);
  assert.match(pricing, /proAnnual:\s*"Pro Arena Annual"/);
  assert.match(pricing, /eliteMonthly:\s*"Elite Stack"/);
  assert.match(pricing, /eliteAnnual:\s*"Elite Stack Annual"/);
});

test("old prices do not appear in active website pages or checkout configuration", () => {
  for (const [label, source] of ACTIVE_PAGES) {
    assert.doesNotMatch(source, /\$39\.99/, `${label} still contains $39.99`);
    assert.doesNotMatch(source, /\$249\.99/, `${label} still contains $249.99`);
    assert.doesNotMatch(source, /\$499\.99/, `${label} still contains $499.99`);
    assert.doesNotMatch(source, /proMonthly:\s*39\.99/);
    assert.doesNotMatch(source, /proAnnual:\s*249\.99/);
    assert.doesNotMatch(source, /eliteAnnual:\s*499\.99/);
  }
  assert.doesNotMatch(billing, /\$39</);
  assert.doesNotMatch(billing, /\$249</);
  assert.doesNotMatch(billing, /\$499</);
});

test("homepage, billing, terms, and refund use the canonical pricing source", () => {
  assert.match(home, /from "@\/lib\/website-pricing"/);
  assert.match(home, /WEBSITE_PRICE_DISPLAY\.proMonthlyDollars/);
  assert.match(home, /WEBSITE_PRICE_DISPLAY\.proAnnualLine/);
  assert.match(home, /WEBSITE_PRICE_DISPLAY\.eliteMonthlyDollars/);
  assert.match(home, /WEBSITE_PRICE_DISPLAY\.eliteAnnualLine/);
  assert.match(billing, /from "@\/lib\/website-pricing"/);
  assert.match(terms, /from "@\/lib\/website-pricing"/);
  assert.match(refund, /from "@\/lib\/website-pricing"/);
  assert.match(terms, /WEBSITE_PRICE_DISPLAY\.proMonthlyLegal/);
  assert.match(terms, /WEBSITE_PRICE_DISPLAY\.proAnnualLegal/);
  assert.match(terms, /WEBSITE_PRICE_DISPLAY\.eliteMonthlyLegal/);
  assert.match(terms, /WEBSITE_PRICE_DISPLAY\.eliteAnnualLegal/);
  assert.match(refund, /WEBSITE_PRICE_DISPLAY\.proMonthlyLegal/);
  assert.match(refund, /WEBSITE_PRICE_DISPLAY\.proAnnualLegal/);
  assert.match(refund, /WEBSITE_PRICE_DISPLAY\.eliteMonthlyLegal/);
  assert.match(refund, /WEBSITE_PRICE_DISPLAY\.eliteAnnualLegal/);
});

test("monthly and annual selections submit the canonical plan names only", () => {
  assert.match(billing, /handleCheckout\(WEBSITE_CHECKOUT_PLANS\.proMonthly\)/);
  assert.match(billing, /handleCheckout\(WEBSITE_CHECKOUT_PLANS\.proAnnual\)/);
  assert.match(billing, /handleCheckout\(WEBSITE_CHECKOUT_PLANS\.eliteMonthly\)/);
  assert.match(billing, /handleCheckout\(WEBSITE_CHECKOUT_PLANS\.eliteAnnual\)/);
  assert.match(api, /export async function createCheckout\(plan: string\)/);
  assert.match(api, /body: JSON\.stringify\(\{ plan \}\)/);
  assert.doesNotMatch(api, /JSON\.stringify\(\{[^}]*amount/);
  assert.doesNotMatch(billing, /PayKingsPayButton/);
  assert.doesNotMatch(billing, /Collect\.js/);
});

test("terms and refund policy match the approved website prices", () => {
  assert.match(terms, /WEBSITE_PRICE_DISPLAY\.proMonthlyLegal/);
  assert.match(terms, /WEBSITE_PRICE_DISPLAY\.eliteAnnualLegal/);
  assert.match(refund, /WEBSITE_PRICE_DISPLAY\.proAnnualLegal/);
  assert.match(refund, /WEBSITE_PRICE_DISPLAY\.eliteMonthlyLegal/);
});

test("App Store promotion and complete disclaimer remain intact", () => {
  const escaped = DISCLAIMER.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  assert.match(home, new RegExp(escaped));
  assert.match(legal, new RegExp(escaped));
  assert.match(appStore, new RegExp(APP_STORE_URL.replace(/\//g, "\\/")));
  assert.match(appStore, new RegExp(`APP_STORE_CTA = "${CTA}"`));
  assert.match(home, /<AppStoreBadge placement="hero" \/>/);
  assert.match(home, /<AppStoreCtaLink placement="hero-cta" \/>/);
  assert.match(home, /id="ios-app"/);
  assert.match(layout, /appId:\s*"6808706342"/);
  assert.match(home, /DFS optimizer and Parlay Builder/);
});
