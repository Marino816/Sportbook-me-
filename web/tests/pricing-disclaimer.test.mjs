import assert from "node:assert/strict";
import test from "node:test";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const read = (rel) => readFileSync(join(root, rel), "utf8");

const DISCLAIMER =
  "SB ME is sports analytics and DFS intelligence software. We do not accept wagers, hold betting funds, or place bets.";
const APP_STORE_URL = "https://apps.apple.com/app/sportbook-me-dfs-ai/id6808706342";
const CTA = "Download Sportbook Me DFS AI for iPhone";

const home = read("src/app/page.tsx");
const layout = read("src/app/layout.tsx");
const legal = read("src/components/legal/legal-page.tsx");
const lib = read("src/lib/app-store.ts");
const billing = read("src/app/billing/page.tsx");

test("public homepage lists all four required prices", () => {
  assert.match(home, /WEBSITE_PRICE_DISPLAY\.proMonthlyDollars/);
  assert.match(home, /WEBSITE_PRICE_DISPLAY\.proAnnualLine/);
  assert.match(home, /WEBSITE_PRICE_DISPLAY\.eliteMonthlyDollars/);
  assert.match(home, /WEBSITE_PRICE_DISPLAY\.eliteAnnualLine/);
  assert.doesNotMatch(home, /\$39\.99/);
  assert.doesNotMatch(home, /price: "\$39"/);
  assert.doesNotMatch(home, /\$249\.99/);
  assert.doesNotMatch(home, /\$499\.99/);
});

test("paid plans mention DFS and Parlay functionality", () => {
  const pro = home.slice(home.indexOf("Pro Arena"), home.indexOf("Elite Stack"));
  const elite = home.slice(home.indexOf("Elite Stack"));
  assert.match(pro, /DFS optimizer and Parlay Builder/);
  assert.match(elite, /DFS optimizer and Parlay Builder/);
});

test("homepage and legal footers include the complete wagering disclaimer", () => {
  assert.match(home, new RegExp(DISCLAIMER.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")));
  assert.match(legal, new RegExp(DISCLAIMER.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")));
});

test("App Store URL, iPhone CTA, and Smart App Banner remain", () => {
  assert.match(lib, new RegExp(APP_STORE_URL.replace(/\//g, "\\/")));
  assert.match(lib, new RegExp(`APP_STORE_CTA = "${CTA}"`));
  assert.match(home, /<AppStoreBadge placement="hero" \/>/);
  assert.match(home, /<AppStoreCtaLink placement="hero-cta" \/>/);
  assert.match(home, /id="ios-app"/);
  assert.match(layout, /appId:\s*"6808706342"/);
  assert.match(layout, /itunes:\s*\{/);
});

test("billing checkout uses canonical plan mapping without PayKings", () => {
  assert.match(billing, /handleCheckout\(WEBSITE_CHECKOUT_PLANS\.proMonthly\)/);
  assert.match(billing, /handleCheckout\(WEBSITE_CHECKOUT_PLANS\.proAnnual\)/);
  assert.match(billing, /handleCheckout\(WEBSITE_CHECKOUT_PLANS\.eliteMonthly\)/);
  assert.match(billing, /handleCheckout\(WEBSITE_CHECKOUT_PLANS\.eliteAnnual\)/);
  assert.doesNotMatch(billing, /PayKingsPayButton/);
});
