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

test("catalog mapping-needed rows are empty sgo_ids from JSON, not hardcoded counts", () => {
  const needed = platforms.filter((p) => !(p.sgo_ids || []).length);
  const mapped = platforms.filter((p) => (p.sgo_ids || []).length > 0);
  assert.equal(needed.length + mapped.length, platforms.length);
  assert.equal(platforms.length, 55);
  const neededIds = needed.map((p) => p.id).sort();
  assert.deepEqual(neededIds, ["bet365", "circa", "pinnacle"]);
});

test("bookmakers directory is a catalog page, not a live-odds claim", () => {
  const bookmakers = readFileSync(join(root, "src/app/market-tools/bookmakers/page.tsx"), "utf8");
  const platformsLib = readFileSync(join(root, "src/lib/platforms.ts"), "utf8");
  assert.match(platformsLib, /export function catalogMappingCounts/);
  assert.match(platformsLib, /export function directoryLane/);
  assert.match(bookmakers, /classified\.counts\.mapped_to_sgo/);
  assert.match(bookmakers, /classified\.counts\.mapping_needed/);
  assert.match(bookmakers, /classified\.counts\.no_current_data/);
  assert.match(bookmakers, /catalogMappingCounts/);
  assert.match(bookmakers, /Search platforms/);
  assert.match(bookmakers, /Mapping Needed/);
  assert.match(bookmakers, /No Current Data/);
  assert.match(bookmakers, /does not accept or place wagers/);
  assert.doesNotMatch(bookmakers, /Line available/);
  assert.doesNotMatch(bookmakers, /currently mapped to live/);
  assert.match(bookmakers, /SBME_55_PLATFORMS\.filter/);
});

test("parlay is an analytical workspace without wager execution", () => {
  const parlay = readFileSync(join(root, "src/app/market-tools/parlay/page.tsx"), "utf8");
  assert.match(parlay, /Parlay Intelligence/);
  assert.match(parlay, /does not accept or place wagers/);
  assert.doesNotMatch(parlay, /Place Bet/);
  assert.match(parlay, /sbme_ai_draft/);
  assert.match(parlay, /router\.push\("\/ai"\)/);
  assert.match(parlay, /FairOddsMark/);
  assert.match(parlay, /ConsensusMark/);
  assert.match(parlay, /removeLeg/);
  assert.match(parlay, /setLegs\(\[\]\)/);
  assert.doesNotMatch(parlay, /\?\?-110/);
  assert.doesNotMatch(parlay, /\?\?-100/);
  assert.match(parlay, /Select markets to analyze together/);
});

test("landing preserves prices and is not a sportsbook", () => {
  assert.match(landing, /\$39/);
  assert.match(landing, /\.99\/mo/);
  assert.match(landing, /\$89/);
  assert.match(landing, /do not accept wagers/i);
  assert.match(landing, /DFS Intelligence/);
  assert.match(landing, /Premier League|EPL/);
});
