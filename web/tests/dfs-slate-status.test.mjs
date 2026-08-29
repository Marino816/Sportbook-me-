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
  assert.match(dataHub, /filterCustomerVisibleSlates/);
  assert.match(dataHub, /Slate Directory/);
  assert.match(dataHub, /NO DFS SLATE CURRENTLY AVAILABLE/);
  assert.match(dataHub, /Optimizer unavailable until a DFS slate is available/);
  assert.match(dataHub, /UPCOMING SCHEDULE/);
  assert.match(dataHub, /WAITING FOR DFS SLATE|Waiting for DFS Slate/);
  assert.doesNotMatch(dataHub, /Upload a contest salary CSV/);
  assert.doesNotMatch(dataHub, /No slates available/);
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

test("customer-visible slates match optimizer and data hub rules", async () => {
  const mod = await import("../src/lib/dfs-slate-status.ts");
  const base = {
    id: 1,
    platform: "draftkings",
    sport: "NFL",
    slate_name: "Main",
    start_time: new Date(Date.now() + 3600_000).toISOString(),
    slate_date: null,
    is_current: false,
    game_count: 10,
    player_count: 200,
    status: "DRAFT",
    data_source: "native",
  };
  assert.equal(mod.isCustomerVisibleSlate({ ...base, freshness: "STALE" }, "NFL"), false);
  assert.equal(mod.isCustomerVisibleSlate({ ...base, freshness: "UPCOMING", is_live_eligible: true }, "NFL"), true);
  assert.equal(mod.isCustomerVisibleSlate({ ...base, freshness: "UPCOMING" }, "MLB"), false);
  assert.equal(mod.isCustomerVisibleSlate({ ...base, freshness: "CURRENT", is_current: true }, "MLB"), true);
  assert.equal(mod.filterCustomerVisibleSlates([
    { ...base, id: 1, freshness: "STALE" },
    { ...base, id: 2, freshness: "CURRENT", is_current: true, sport: "MLB" },
  ], "MLB").map((s) => s.id).join(","), "2");
});
