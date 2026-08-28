import assert from "node:assert/strict";
import test from "node:test";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");

const platforms = JSON.parse(readFileSync(join(root, "src/lib/sbme-55-platforms.json"), "utf8"));
const leagues = readFileSync(join(root, "src/lib/sgo-leagues.ts"), "utf8");
const marketView = readFileSync(join(root, "src/lib/market-view.ts"), "utf8");
const protectedRoute = readFileSync(join(root, "src/components/auth/ProtectedRoute.tsx"), "utf8");
const landing = readFileSync(join(root, "src/app/page.tsx"), "utf8");

test("55-platform catalog is exactly 55 unique rows", () => {
  assert.equal(platforms.length, 55);
  const ids = new Set(platforms.map((p) => p.id));
  assert.equal(ids.size, 55);
  assert.ok(platforms.some((p) => (p.sgo_ids || []).length === 0), "mapping needed rows exist");
  assert.ok(platforms.some((p) => (p.sgo_ids || []).length > 0), "mapped rows exist");
});

test("league selector source lists all 17 Rookie leagues and soccer aliases", () => {
  for (const id of [
    "MLB", "NBA", "NCAAB", "WNBA", "NCAAF", "NFL", "EHF_EURO", "NHL", "UFC",
    "BUNDESLIGA", "EPL", "FR_LIGUE_1", "INTERNATIONAL_SOCCER", "IT_SERIE_A",
    "LA_LIGA", "MLS", "UEFA_CHAMPIONS_LEAGUE",
  ]) {
    assert.match(leagues, new RegExp(`"${id}"`));
  }
  assert.match(leagues, /UCL:\s*"UEFA_CHAMPIONS_LEAGUE"/);
  assert.doesNotMatch(leagues, /GOLF/);
});

test("market-view never invents fair odds or consensus", () => {
  assert.match(marketView, /export function fairOddsForMarket/);
  assert.match(marketView, /export function bookOddsForMarket/);
  assert.match(marketView, /return m\.fair_odds \?\? null/);
  assert.match(marketView, /return m\.book_odds \?\? null/);
  assert.match(marketView, /filterEventsByStatus/);
  assert.match(marketView, /LineMode/);
});

test("protected routes still cover market tools, dashboard, admin, ai", () => {
  for (const path of ["/admin", "/ai", "/dashboard", "/data-hub", "/market-tools", "/optimizer"]) {
    assert.match(protectedRoute, new RegExp(`"${path}"`));
  }
});

test("landing preserves prices and is not a sportsbook", () => {
  assert.match(landing, /\$39/);
  assert.match(landing, /\.99\/mo/);
  assert.match(landing, /\$89/);
  assert.match(landing, /do not accept wagers/i);
  assert.match(landing, /DFS Intelligence/);
  assert.match(landing, /Premier League|EPL/);
});
