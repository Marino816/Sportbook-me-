/**
 * Controlled-release QA fix regressions.
 * Run: node --test tests/qa-fix-pass.test.mjs
 */
import assert from "node:assert/strict";
import { existsSync, readFileSync, statSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { test } from "node:test";
import { formatSourceLabel, formatProjectionSource, lineupProjectionIntegrity } from "../lib/source-label.mjs";
import { canStartPurchase, purchaseCta } from "../lib/subscription-cta.mjs";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");

function read(rel) {
  return readFileSync(join(root, rel), "utf8");
}

test("native/stored DFS data is not labeled live contest salaries", () => {
  assert.equal(formatSourceLabel("native").label, "Stored contest salaries");
  assert.equal(formatSourceLabel("bcdfs").isDemo, false);
  assert.match(formatSourceLabel("native", "native", "FRESH").label, /Stored contest salaries · FRESH/);
  assert.match(formatSourceLabel("demo").label, /Demo slate/);
  assert.equal(formatSourceLabel("demo").isDemo, true);
  assert.doesNotMatch(formatSourceLabel("native").label, /Live contest salaries/);
  assert.doesNotMatch(read("lib/optimizer-config.ts"), /Live contest salaries/);
  assert.doesNotMatch(read("lib/source-label.mjs"), /Live contest salaries/);
  assert.match(read("app/(tabs)/optimizer/index.tsx"), /selectedSlate\?\.freshness/);
});

test("lineup details modal uses a Modal-local SafeAreaProvider", () => {
  const src = read("app/(tabs)/optimizer/result.tsx");
  assert.match(src, /react-native-safe-area-context/);
  assert.match(src, /SafeAreaProvider/);
  assert.match(src, /initialWindowMetrics/);
  assert.match(src, /useSafeAreaInsets/);
  assert.match(src, /presentationStyle="fullScreen"/);
  assert.match(src, /edges=\{\["top", "bottom"\]\}/);
  assert.match(src, /Lineup details/);
  assert.match(src, /setSelected\(null\)/);
  const modalIdx = src.indexOf("<Modal");
  const providerIdx = src.indexOf("<SafeAreaProvider", modalIdx);
  const safeIdx = src.indexOf("<SafeAreaView", providerIdx);
  assert.equal(modalIdx >= 0 && providerIdx > modalIdx && safeIdx > providerIdx, true);
});

test("lineup history uses the Optimizer source-label helper, not raw native", () => {
  const src = read("app/(tabs)/lineups.tsx");
  assert.match(src, /formatSourceLabel/);
  assert.match(src, /selected\.data_mode/);
  assert.match(src, /source\.label/);
  assert.doesNotMatch(src, /\{selected\.data_mode\}/);
  assert.equal(formatSourceLabel("native").label, "Stored contest salaries");
  assert.equal(formatSourceLabel("blue_collar").label, "Stored contest salaries");
});

test("projection integrity helper matches displayed total and refuses contest-ready", () => {
  const integrity = lineupProjectionIntegrity({
    projected_score: 122.1,
    players: [
      { projected_fp: 30.5, projection_source: "SGO_FANTASY_MARKET", mapping_status: "MATCHED" },
      { projected_fp: 29.5, projection_source: "SGO_FANTASY_MARKET", mapping_status: "MATCHED" },
      { projected_fp: 8.0, projection_source: "BC_PROJ_FALLBACK", mapping_status: "UNMATCHED" },
      { projected_fp: 8.2, projection_source: "BC_PROJ_FALLBACK", mapping_status: "UNMATCHED" },
      { projected_fp: 7.0, projection_source: "BC_PROJ_FALLBACK", mapping_status: "UNMATCHED" },
      { projected_fp: 6.5, projection_source: "SGO_FANTASY_MARKET", mapping_status: "MATCHED" },
      { projected_fp: 7.9, projection_source: "BC_PROJ_FALLBACK", mapping_status: "MATCHED" },
      { projected_fp: 8.3, projection_source: "BC_PROJ_FALLBACK", mapping_status: "UNMATCHED" },
      { projected_fp: 8.4, projection_source: "BC_PROJ_FALLBACK", mapping_status: "UNMATCHED" },
      { projected_fp: 7.8, projection_source: "BC_PROJ_FALLBACK", mapping_status: "MATCHED" },
    ],
  });
  assert.equal(integrity.playerSum, 122.1);
  assert.equal(integrity.displayed, 122.1);
  assert.equal(integrity.totalsMatch, true);
  assert.equal(integrity.fallbackCount, 7);
  assert.equal(integrity.unmatchedCount, 5);
  assert.equal(integrity.contestReady, false);
  assert.equal(formatProjectionSource("SGO_FANTASY_MARKET").label, "SGO fantasy market");
  assert.equal(formatProjectionSource("BC_PROJ_FALLBACK").isFallback, true);
});

test("Pro subscriber sees Current plan on Pro and Subscribe on Elite", () => {
  const proMonthly = purchaseCta("Pro Arena", "Pro Arena", { canBuy: true });
  const eliteUpgrade = purchaseCta("Elite Stack", "Pro Arena", { canBuy: true });
  assert.equal(proMonthly.label, "Current plan");
  assert.equal(proMonthly.disabled, true);
  assert.equal(eliteUpgrade.label, "Subscribe");
  assert.equal(eliteUpgrade.disabled, false);
  assert.equal(canStartPurchase("com.sportbookme.app.pro.monthly", "Pro Arena"), false);
  assert.equal(canStartPurchase("com.sportbookme.app.elite.monthly", "Pro Arena"), true);
});

test("Elite subscriber disables current-tier and lower-tier purchase", () => {
  const elite = purchaseCta("Elite Stack", "Elite Stack", { canBuy: true });
  const included = purchaseCta("Pro Arena", "Elite Stack", { canBuy: true });
  assert.equal(elite.label, "Current plan");
  assert.equal(elite.disabled, true);
  assert.equal(included.label, "Included");
  assert.equal(included.disabled, true);
  assert.equal(canStartPurchase("com.sportbookme.app.elite.annual", "Elite Stack"), false);
  assert.equal(canStartPurchase("com.sportbookme.app.pro.annual", "Elite Stack"), false);
});

test("paywall still uses StoreKit verify and restore without local grants", () => {
  const src = read("app/(tabs)/subscription.tsx");
  assert.match(src, /purchaseCta/);
  assert.match(src, /canStartPurchase/);
  assert.match(src, /Restore Purchases/);
  assert.match(src, /verifyAppleTransaction/);
  assert.match(src, /startAppleSubscriptionPurchase/);
  assert.doesNotMatch(src, /createCheckout/);
  assert.doesNotMatch(src, /is_pro\s*=\s*true/);
});

test("Home Screen display name is Sportbook ME; store listing name stays out of the binary", () => {
  const app = JSON.parse(read("app.json"));
  assert.equal(app.expo.name, "Sportbook ME");
  assert.equal(app.expo.ios.bundleIdentifier, "com.sportbookme.app");
  assert.equal(app.expo.ios.infoPlist.CFBundleDisplayName, "Sportbook ME");
  assert.equal(app.expo.ios.infoPlist.CFBundleName, "Sportbook ME");
  assert.equal(app.expo.version, "1.1.0");
  assert.doesNotMatch(JSON.stringify(app), /Sportbook Me DFS AI/);
});

test("production EAS profile still points at Railway production /api", () => {
  const eas = JSON.parse(read("eas.json"));
  assert.equal(eas.build.production.env.EXPO_PUBLIC_API_URL, "https://sportbook-me-production.up.railway.app/api");
  assert.equal(eas.build.production.autoIncrement, true);
  assert.equal(eas.submit.production.ios.ascAppId, "6808706342");
});

test("app icon is generated from the owner-approved logo.png, not the Expo grid template", () => {
  const logo = join(root, "assets/logo.png");
  const icon = join(root, "assets/icon.png");
  assert.equal(existsSync(logo), true);
  assert.equal(existsSync(icon), true);
  assert.ok(statSync(logo).size > 300_000);
  assert.ok(statSync(icon).size > 80_000);
  const header = readFileSync(icon).subarray(0, 24);
  assert.equal(header[0], 0x89);
  assert.equal(header[1], 0x50);
  const width = header.readUInt32BE(16);
  const height = header.readUInt32BE(20);
  assert.equal(width, 1024);
  assert.equal(height, 1024);
  for (const name of ["icon-1024.png", "icon-180.png", "icon-120.png", "icon-87.png", "icon-80.png", "icon-60.png"]) {
    const p = join(root, "assets/ios-icons", name);
    assert.equal(existsSync(p), true, name);
    assert.ok(statSync(p).size > 1000, name);
  }
});

test("Home and Intelligence treat empty intelligence as unavailable, not 404 copy", () => {
  const home = read("app/(tabs)/dashboard.tsx");
  assert.match(home, /intelReady/);
  assert.match(home, /intel\?\.empty !== true/);
  assert.doesNotMatch(home, /\|\| "live"/);
  const intel = read("app/(tabs)/intelligence.tsx");
  assert.match(intel, /noSlates/);
  assert.match(intel, /intelUnavailable/);
  assert.match(intel, /No intelligence summary for this slate yet/);
});
