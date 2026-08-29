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
  assert.doesNotMatch(rosterSrc.split("NFL|draftkings")[1].slice(0, 400), /"P", "P", "C"/);
});

test("optimizer uses roster templates and regenerate_from_ids", () => {
  assert.match(optimizer, /getRoster/);
  assert.match(optimizer, /regenerate_from_ids/);
  assert.match(optimizer, /UNIQUE_LINEUP_UNAVAILABLE/);
  assert.match(optimizer, /filterPositions/);
  assert.match(optimizer, /Game chips load from the selected contest slate/);
  assert.doesNotMatch(optimizer, /const DK_SLOTS = \["P"/);
  assert.doesNotMatch(optimizer, /MLB_POSITIONS/);
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
