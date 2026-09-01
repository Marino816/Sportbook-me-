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

test("desktop Live Lineup Builder is capped so Player Pool can show all columns", () => {
  const desktop = css.match(/\.sbme-opt-workspace \{\n  display: grid;\n[\s\S]*?grid-template-columns: ([^;]+);/);
  assert.ok(desktop, "desktop workspace grid exists");
  assert.equal(desktop[1].trim(), "minmax(0, 1fr) minmax(260px, 280px)");
  assert.match(css, /minmax\(260px, 280px\)/);
  assert.doesNotMatch(css, /minmax\(280px, 0\.9fr\)/);
  for (const col of ["Team", "Opp", "Start", "Pos", "Player", "Salary", "BC Proj", "SB Proj", "My Proj", "Value", "SB OWN%", "LEV", "OPT%", "CEIL", "FLOOR", "PROPS", "Action"]) {
    assert.match(optimizer, new RegExp(col.replace("%", "\\%")));
  }
});

test("strategy change applies immediately and refreshes strategy-dependent results", () => {
  assert.match(optimizer, /STRATEGIES = \["balanced", "cash", "gpp", "aggressive"\]/);
  assert.match(optimizer, /onChange=\{applyStrategy\}/);
  assert.match(optimizer, /optimizeMutation\.mutate\(\{ strategy: next \}\)/);
  assert.match(optimizer, /strategy: appliedStrategy/);
  assert.match(optimizer, /setLineups\(\[\]\)/);
  assert.doesNotMatch(optimizer, /onChange=\{setStrategy\}/);
  assert.match(optimizer, /ws\.setSport|sport/);
  assert.match(optimizer, /lockedIds/);
  assert.match(optimizer, /likedIds/);
  assert.match(optimizer, /excludedIds/);
  assert.doesNotMatch(optimizer, /window\.location\.reload/);
});

test("OPT% uses /api/optimal-pct and polls until COMPLETE", () => {
  assert.match(optimizer, /fetchOptimalPct/);
  assert.match(optimizer, /mapOptimalPctResponse/);
  assert.match(optimizer, /lookupOptimalPct/);
  assert.match(optimizer, /formatOptPctCell/);
  assert.match(optimizer, /QUEUED/);
  assert.match(optimizer, /RUNNING/);
  assert.match(optimizer, /setInterval\(load, POLL_MS\)/);
  assert.doesNotMatch(optimizer, /optPctMap\[normName\(p\.name\)\] \?\? .*ownership/);
});
