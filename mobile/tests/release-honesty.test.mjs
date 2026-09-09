/**
 * Release honesty contracts for the customer-facing Expo app.
 * Run: node --test tests/release-honesty.test.mjs
 */
import assert from "node:assert/strict";
import { readFileSync, readdirSync, statSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { test } from "node:test";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");

function walk(dir, acc = []) {
  for (const name of readdirSync(dir)) {
    if (name === "node_modules" || name === ".expo" || name === "dist") continue;
    const p = join(dir, name);
    if (statSync(p).isDirectory()) walk(p, acc);
    else if (/\.(ts|tsx|js|jsx)$/.test(name)) acc.push(p);
  }
  return acc;
}

function read(rel) {
  return readFileSync(join(root, rel), "utf8");
}

test("Home has no hardcoded LAD@SD / +2.3 pts intel", () => {
  const src = read("app/(tabs)/dashboard.tsx");
  assert.doesNotMatch(src, /LAD@SD/);
  assert.doesNotMatch(src, /\+2\.3 pts/);
  assert.match(src, /getLiveOdds/);
  assert.match(src, /getPublishedSlates/);
  assert.match(src, /getIntelligence/);
  assert.match(src, /lineupCopyForPlan/);
});

test("Home header uses wordmark, stadium hero, and optimizer setup CTA", () => {
  const src = read("app/(tabs)/dashboard.tsx");
  const mark = read("components/HomeWordmark.tsx");
  assert.match(src, /HomeWordmark/);
  assert.doesNotMatch(src, /LogoText/);
  assert.match(mark, /Sportbook/);
  assert.match(mark, /DFS AI/);
  assert.doesNotMatch(mark, /logo\.png/);
  assert.match(src, /stadium-night\.jpg/);
  assert.match(src, /SPORTBOOK ME DFS AI · SB ME/);
  assert.match(src, /DFS Intelligence/);
  assert.match(src, /Live Markets/);
  assert.match(src, /One AI Platform/);
  assert.match(src, /not a sportsbook/);
  assert.match(src, /OPEN OPTIMIZER/);
  assert.match(src, /SEE HOW IT WORKS/);
  assert.match(src, /push\("\/optimizer"\)/);
  assert.match(src, /\/\(tabs\)\/intelligence/);
  assert.doesNotMatch(src, /Build optimal lineups/);
  assert.doesNotMatch(src, /Smarter Plays/);
  assert.match(src, /\/\(tabs\)\/profile/);
  assert.doesNotMatch(src, /Log In/);
  assert.match(src, /NCAAF/);
  assert.match(src, /UEFA_CHAMPIONS_LEAGUE/);
  assert.match(src, /person-circle/);
});

test("Optimizer empty state is not demo data", () => {
  const src = read("app/(tabs)/optimizer/index.tsx");
  const flow = read("lib/optimizer-flow.mjs");
  assert.doesNotMatch(src, /using demo data/i);
  assert.match(src, /No live slates for this sport and platform/);
  assert.match(src, /formatSourceLabel/);
  assert.match(flow, /stack_size/);
  assert.match(flow, /max_exposure_pct/);
  assert.match(flow, /num_lineups/);
});

test("Lineups history maps native metadata through formatSourceLabel", () => {
  const src = read("app/(tabs)/lineups.tsx");
  assert.match(src, /formatSourceLabel\(selected\.data_mode/);
  assert.match(src, /source\.label/);
  assert.doesNotMatch(src, / · \{selected\.data_mode\}/);
});

test("Optimizer source labels never claim live contest salaries for native data", () => {
  const cfg = read("lib/optimizer-config.ts");
  const labels = read("lib/source-label.mjs");
  assert.match(cfg, /formatSourceLabel/);
  assert.doesNotMatch(cfg, /Live contest salaries/);
  assert.doesNotMatch(labels, /Live contest salaries/);
  assert.match(labels, /Stored contest salaries/);
  assert.match(labels, /Demo slate — not live contest data/);
});

test("Settings has no local-only Switch controls", () => {
  const src = read("app/(tabs)/settings.tsx");
  assert.doesNotMatch(src, /\bSwitch\b/);
  assert.match(src, /ai-preferences/);
  assert.match(src, /signOut\(\)/);
});

test("AI Preferences is reachable from Profile, Settings, and AI chat", () => {
  assert.match(read("app/(tabs)/profile.tsx"), /\/\(tabs\)\/ai-preferences/);
  assert.match(read("app/(tabs)/settings.tsx"), /\/\(tabs\)\/ai-preferences/);
  assert.match(read("app/(tabs)/ai-chat.tsx"), /\/\(tabs\)\/ai-preferences/);
  assert.match(read("app/(tabs)/ai-preferences.tsx"), /loadAIPreferences/);
});

test("Profile plan copy uses production 20 / 150 labels", () => {
  const src = read("app/(tabs)/profile.tsx");
  assert.match(src, /displayPlanLabel/);
  assert.match(src, /lineupCopyForPlan/);
  assert.doesNotMatch(src, /10 daily/i);
  assert.doesNotMatch(src, /unlimited/i);
});

test("Customer-facing app routes do not claim 10 daily or unlimited", () => {
  const files = walk(join(root, "app"));
  for (const file of files) {
    const src = readFileSync(file, "utf8");
    assert.doesNotMatch(src, /10 daily/i, file);
    assert.doesNotMatch(src, /unlimited lineups/i, file);
  }
});

test("Lineups uses gold brand color instead of prototype purple", () => {
  const src = read("app/(tabs)/lineups.tsx");
  assert.doesNotMatch(src, /#7c5cfc/);
  assert.match(src, /#c9a84c/);
});

test("Intelligence does not hardcode slate 1", () => {
  const src = read("app/(tabs)/intelligence.tsx");
  assert.doesNotMatch(src, /useState\(1\)/);
  assert.match(src, /getPublishedSlates/);
});

test("Plan copy helper matches Pro 20 and Elite 150", () => {
  const src = read("lib/plan-copy.ts");
  assert.match(src, /if \(label === "Elite Stack"\) return 150;/);
  assert.match(src, /if \(label === "Pro Arena"\) return 20;/);
  assert.match(src, /PRO_LINEUP_COPY/);
  assert.match(src, /ELITE_LINEUP_COPY/);
});
