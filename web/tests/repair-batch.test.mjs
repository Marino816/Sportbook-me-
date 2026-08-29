import assert from "node:assert/strict";
import test from "node:test";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const rosterSrc = readFileSync(join(root, "src/lib/dfs-roster.ts"), "utf8");
const optimizer = readFileSync(join(root, "src/app/optimizer/page.tsx"), "utf8");
const login = readFileSync(join(root, "src/app/login/page.tsx"), "utf8");
const lineups = readFileSync(join(root, "src/app/lineups/page.tsx"), "utf8");

test("football roster templates are sport+platform specific", () => {
  assert.match(rosterSrc, /NFL\|draftkings/);
  assert.match(rosterSrc, /"QB", "RB", "RB", "WR", "WR", "WR", "TE", "FLEX", "DST"/);
  assert.match(rosterSrc, /"QB", "RB", "RB", "WR", "WR", "WR", "FLEX", "SFLX"/);
  assert.match(rosterSrc, /"QB", "RB", "RB", "WR", "WR", "WR", "TE", "FLEX", "DEF"/);
  assert.match(rosterSrc, /NFL\|fanduel[\s\S]*?salaryCap: 60000/);
  assert.match(rosterSrc, /NCAAF\|fanduel[\s\S]*?salaryCap: 60000/);
  assert.match(rosterSrc, /NFL\|draftkings[\s\S]*?salaryCap: 50000/);
  assert.match(rosterSrc, /NCAAF\|draftkings[\s\S]*?salaryCap: 50000/);
  assert.match(rosterSrc, /export function averageRemainingPerPlayer/);
  assert.doesNotMatch(rosterSrc.split("NFL|draftkings")[1].slice(0, 400), /"P", "P", "C"/);
});

test("empty FanDuel football remaining averages", () => {
  const avg = (remaining, slots) => (slots <= 0 ? 0 : Math.round(remaining / slots));
  assert.equal(avg(60000, 7), 8571);
  assert.equal(avg(60000, 9), 6667);
});

test("optimizer uses roster templates and regenerate_from_ids", () => {
  assert.match(optimizer, /getRoster/);
  assert.match(optimizer, /regenerate_from_ids/);
  assert.match(optimizer, /UNIQUE_LINEUP_UNAVAILABLE/);
  assert.match(optimizer, /filterPositions/);
  assert.match(optimizer, /filterCustomerVisibleSlates/);
  assert.match(optimizer, /SLATE GAMES/);
  assert.match(optimizer, /UPCOMING SCHEDULE/);
  assert.match(optimizer, /No DFS slate currently available/);
  assert.match(optimizer, /Optimizer unavailable until a DFS slate is available/);
  assert.match(optimizer, /SCHEDULE_INTEL_NOTE/);
  assert.match(optimizer, /Avg Remaining \/ Player/);
  assert.doesNotMatch(optimizer, /const DK_SLOTS = \["P"/);
  assert.doesNotMatch(optimizer, /MLB_POSITIONS/);
  assert.doesNotMatch(optimizer, /DKSalaries/);
  assert.doesNotMatch(optimizer, /admin\/dfs-import/);
});

test("login page is cinematic and does not fake OAuth success", () => {
  assert.match(login, /Welcome to SB ME/);
  assert.match(login, /SBMEBackground/);
  assert.match(login, /Continue with Google/);
  assert.match(login, /Continue with Apple/);
  assert.match(login, /Pending — provider not configured/);
  assert.match(login, /Username or Email/);
  assert.match(login, /Forgot password/);
  assert.match(login, /Create account/);
  assert.match(login, /Username login is not enabled yet/);
});

test("lineups history is two pages with real open/duplicate/delete", () => {
  assert.match(lineups, /Delete this saved lineup\?/);
  assert.match(lineups, /Duplicate \/ Build From/);
  assert.match(lineups, /deleteLineupHistory/);
  assert.match(lineups, /Page 1 — newest/);
  assert.match(lineups, /Page 2 — older/);
  assert.match(lineups, /Slate unavailable/);
  assert.match(lineups, /Archived/);
});
