import assert from "node:assert/strict";
import test from "node:test";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const optimizer = readFileSync(join(root, "src/app/optimizer/page.tsx"), "utf8");
const css = readFileSync(join(root, "src/app/globals.css"), "utf8");

test("optimizer v2 command center preserves engine contracts", () => {
  assert.match(optimizer, /AppShell/);
  assert.match(optimizer, /sbme-opt/);
  assert.match(optimizer, /BUILD OPTIMAL LINEUP/);
  assert.match(optimizer, /runOptimizer/);
  assert.match(optimizer, /canGenerate/);
  assert.match(optimizer, /getRoster/);
  assert.match(optimizer, /regenerate_from_ids/);
  assert.match(optimizer, /SPORTS = \["MLB", "NFL", "NBA", "NHL", "NCAAF", "NCAAB"\]/);
  assert.doesNotMatch(optimizer, /WNBA|UFC|GOLF/);
  assert.doesNotMatch(optimizer, /Elite stack|High upside|Best leverage/);
  assert.doesNotMatch(optimizer, /new Date\(\)\.toLocaleTimeString\(\)/);
});

test("optimizer v2 surfaces real fields only and keeps no-slate copy", () => {
  assert.match(optimizer, /No DFS slate currently available/);
  assert.match(optimizer, /Optimizer unavailable until a DFS slate is available/);
  assert.match(optimizer, /SCHEDULE_INTEL_NOTE/);
  assert.match(optimizer, /SLATE GAMES/);
  assert.match(optimizer, /UPCOMING SCHEDULE/);
  assert.match(optimizer, /Avg Remaining \/ Player/);
  assert.match(optimizer, /sbme_ownership_pct/);
  assert.match(optimizer, /LastFive/);
  assert.match(optimizer, /PROJECTIONS UNAVAILABLE/);
  assert.match(optimizer, /NO PLAYERS AVAILABLE/);
  assert.match(optimizer, /NO LINEUP GENERATED/);
  assert.match(optimizer, /NO ACTIVE DFS SLATE/);
  assert.match(css, /sbme-opt-workspace/);
  assert.match(css, /sbme-opt-intel/);
  assert.match(css, /prefers-reduced-motion/);
  assert.match(optimizer, /sbme-opt-banner/);
});

test("optimizer v2 places schedule intelligence above the workspace", () => {
  const scheduleIdx = optimizer.indexOf("sbme-opt-schedule");
  const slateGamesIdx = optimizer.indexOf("SLATE GAMES");
  const upcomingIdx = optimizer.indexOf("UPCOMING SCHEDULE");
  const workspaceIdx = optimizer.indexOf("sbme-opt-workspace");
  const lowerIdx = optimizer.indexOf("sbme-opt-lower");
  assert.ok(scheduleIdx > 0, "schedule region exists");
  assert.ok(scheduleIdx < workspaceIdx, "schedule is above workspace");
  assert.ok(slateGamesIdx > scheduleIdx && slateGamesIdx < workspaceIdx, "slate games stay in schedule region");
  assert.ok(upcomingIdx > scheduleIdx && upcomingIdx < workspaceIdx, "upcoming schedule is above workspace");
  assert.ok(workspaceIdx < lowerIdx, "workspace stays above lower intelligence");
  assert.match(css, /\.sbme-opt-schedule/);
  assert.match(css, /\.sbme-opt-schedule \{ order: 0; \}/);
  assert.match(css, /\.sbme-opt-workspace \{ grid-template-columns: 1fr; order: 1; \}/);
  assert.match(css, /\.sbme-opt-builder \{ position: static; order: -1; \}/);
  assert.match(css, /\.sbme-opt-pool \{ order: 0; \}/);
  assert.match(css, /\.sbme-opt-lower \{ grid-template-columns: 1fr; order: 2; \}/);
});
