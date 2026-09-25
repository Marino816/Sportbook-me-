import assert from "node:assert/strict";
import test from "node:test";
import { existsSync, readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const read = (rel) => readFileSync(join(root, rel), "utf8");

const APP_STORE_URL = "https://apps.apple.com/app/sportbook-me-dfs-ai/id6808706342";
const APP_STORE_ID = "6808706342";
const BRAND = "Sportbook Me DFS AI";
const CTA = "Download Sportbook Me DFS AI for iPhone";

const lib = read("src/lib/app-store.ts");
const badge = read("src/components/AppStoreBadge.tsx");
const home = read("src/app/page.tsx");
const layout = read("src/app/layout.tsx");
const footerLegal = read("src/components/legal/legal-page.tsx");

test("App Store constants use the official listing and brand spelling", () => {
  assert.match(lib, new RegExp(`APP_STORE_ID = "${APP_STORE_ID}"`));
  assert.match(lib, new RegExp(`APP_STORE_URL = "${APP_STORE_URL.replace(/\//g, "\\/")}"`));
  assert.match(lib, new RegExp(`APP_STORE_CTA = "${CTA}"`));
  assert.match(lib, new RegExp(`${BRAND} on the App Store`));
  assert.doesNotMatch(lib, /Sportsbook Me/);
});

test("App Store clicks emit the app_store_click analytics event", () => {
  assert.match(lib, /from "@vercel\/analytics"/);
  assert.match(lib, /track\("app_store_click"/);
  assert.match(badge, /trackAppStoreClick\(placement\)/);
});

test("official App Store badge artwork is hosted locally", () => {
  assert.equal(existsSync(join(root, "public/badges/download-on-the-app-store.svg")), true);
  const svg = read("public/badges/download-on-the-app-store.svg");
  assert.match(svg, /Download_on_the_App_Store_Badge/);
  assert.match(badge, /\/badges\/download-on-the-app-store\.svg/);
  assert.match(badge, /alt=\{APP_STORE_BADGE_ALT\}/);
  assert.match(badge, /target="_blank"/);
  assert.match(badge, /rel="noopener noreferrer"/);
  assert.match(badge, /href=\{APP_STORE_URL\}/);
});

test("homepage hero includes the App Store badge and iPhone CTA", () => {
  assert.match(home, /<AppStoreBadge placement="hero" \/>/);
  assert.match(home, /<AppStoreCtaLink placement="hero-cta" \/>/);
  assert.match(home, /mt-6 flex flex-col sm:flex-row sm:flex-wrap sm:items-center gap-4 w-full max-w-full min-w-0/);
});

test("homepage includes a responsive iOS app section with required features", () => {
  assert.match(home, /id="ios-app"/);
  assert.match(home, /Sportbook Me DFS AI/);
  assert.match(home, /DFS Optimizer/);
  assert.match(home, /Player projections and research/);
  assert.match(home, /Live Odds and Market Tools/);
  assert.match(home, /Parlay Builder/);
  assert.match(home, /SB ME AI assistant/);
  assert.match(home, /grid-cols-1 sm:grid-cols-2 lg:grid-cols-5/);
  assert.match(home, /<AppStoreBadge placement="ios-section" \/>/);
  assert.match(home, /<AppStoreCtaLink placement="ios-section-cta" \/>/);
});

test("website footer includes the App Store badge and official link", () => {
  assert.match(home, /<AppStoreBadge placement="footer" \/>/);
  assert.match(footerLegal, /<AppStoreBadge placement="legal-footer" \/>/);
});

test("root layout publishes the Apple Smart App Banner", () => {
  assert.match(layout, /itunes:\s*\{/);
  assert.match(layout, /appId:\s*"6808706342"/);
});

test("homepage publishes the required public prices and complete disclaimer", () => {
  assert.match(home, /price: "\$49"/);
  assert.match(home, /\.99\/mo/);
  assert.match(home, /or \$399\.99\/year/);
  assert.match(home, /price: "\$89"/);
  assert.match(home, /or \$599\.99\/year/);
  assert.doesNotMatch(home, /price: "\$39"/);
  assert.match(home, /SB ME is sports analytics and DFS intelligence software\. We do not accept wagers, hold betting funds, or place bets\./);
  assert.match(home, /DFS optimizer and Parlay Builder/);
  assert.match(footerLegal, /SB ME is sports analytics and DFS intelligence software\. We do not accept wagers, hold betting funds, or place bets\./);
});
