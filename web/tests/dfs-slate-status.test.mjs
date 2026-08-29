import assert from "node:assert/strict";
import test from "node:test";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");

test("dfs slate status distinguishes locked vs unlocked", async () => {
  const mod = await import("../src/lib/dfs-slate-status.ts");
  const future = new Date(Date.now() + 3600_000).toISOString();
  const past = new Date(Date.now() - 3600_000).toISOString();
  assert.equal(mod.isSlateLocked(past), true);
  assert.equal(mod.isSlateLocked(future), false);
  assert.equal(mod.isSlateLocked(null), true);
  const unlocked = mod.getSlateDisplayStatus({
    id: 1,
    platform: "draftkings",
    sport: "MLB",
    slate_name: "Main",
    start_time: future,
    slate_date: null,
    is_current: true,
    game_count: 10,
    player_count: 200,
    status: "PUBLISHED",
    data_source: "native",
  });
  assert.equal(unlocked, "UNLOCKED");
});

test("data hub uses real DFS sports and canonical handoffs", () => {
  const dataHub = readFileSync(join(root, "src/app/data-hub/page.tsx"), "utf8");
  const importSvc = readFileSync(join(root, "../backend/dfs/import_service.py"), "utf8");
  assert.match(dataHub, /sbme-dhub/);
  assert.match(dataHub, /buildOptimizerHandoffUrl/);
  assert.match(dataHub, /fetchOptimalPct/);
  assert.match(dataHub, /getSlateDisplayStatus/);
  assert.match(dataHub, /Slate Directory/);
  assert.doesNotMatch(dataHub, /runSims/);
  assert.doesNotMatch(dataHub, /POSITIONS = \["ALL", "P"/);
  for (const sport of ["MLB", "NFL", "NBA", "NHL", "NCAAF", "NCAAB"]) {
    assert.match(dataHub, new RegExp(`"${sport}"`));
    assert.match(importSvc, new RegExp(`"${sport}"`));
  }
  assert.doesNotMatch(dataHub, /soccer/i);
  assert.match(dataHub, /projection_source === "UNAVAILABLE"/);
  assert.match(dataHub, /href="\/ai"/);
});
