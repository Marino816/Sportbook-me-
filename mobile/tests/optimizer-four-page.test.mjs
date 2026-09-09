/**
 * Four-page mobile optimizer contracts.
 * Run: node --test tests/optimizer-four-page.test.mjs
 */
import assert from "node:assert/strict";
import { existsSync, readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { test } from "node:test";
import {
  applyLineupToSlots,
  BUILD_BUTTON_LABEL,
  buildOptimizeSettings,
  emptySlots,
  filterOpenSlates,
  getRoster,
  lineupFillMode,
  lockKeysFromSlots,
  OPEN_OPTIMIZER_COPY,
  OPEN_OPTIMIZER_LABEL,
  remainingSalary,
  shouldClearResultState,
  slotEligible,
  validateFullManualLineup,
  validatePlayerSelection,
} from "../lib/optimizer-flow.mjs";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");

function read(rel) {
  return readFileSync(join(root, rel), "utf8");
}

const roster = getRoster("mlb", "draftkings");

function player(overrides) {
  return {
    player_id: "p1",
    name: "Player One",
    position: "OF",
    salary: 4000,
    projected_fp: 8.2,
    ...overrides,
  };
}

test("Page 1 OPEN OPTIMIZER navigates to Page 2", () => {
  const src = read("app/(tabs)/optimizer/index.tsx");
  assert.match(src, new RegExp(OPEN_OPTIMIZER_LABEL));
  assert.match(src, new RegExp(OPEN_OPTIMIZER_COPY.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")));
  assert.match(src, /optimizer\/builder/);
  assert.match(src, />PLATFORM</);
  assert.doesNotMatch(src, /Select Pitcher/);
  assert.equal(existsSync(join(root, "app/(tabs)/optimizer/builder.tsx")), true);
});

test("Page 2 slot opens Page 3", () => {
  const src = read("app/(tabs)/optimizer/builder.tsx");
  assert.match(src, /setSelectingSlotIndex/);
  assert.match(src, /push\("\/optimizer\/players"\)/);
  assert.doesNotMatch(src, /\/\(tabs\)\/optimizer\/players/);
  assert.match(src, new RegExp(BUILD_BUTTON_LABEL));
  assert.match(src, /handleBuild/);
});

test("Page 3 player selection returns to Page 2 and rejects over-cap", () => {
  const src = read("app/(tabs)/optimizer/players.tsx");
  assert.match(src, /assignPlayer/);
  assert.match(src, /router\.back\(\)/);
  assert.match(src, /Choose a lower-salary replacement/);
  assert.match(src, /All Games/);
  assert.match(src, /poolPending/);
  assert.match(src, /playersError/);
  assert.match(src, /getPublishedSlate|current slate/);

  const slots = emptySlots(roster);
  const cheap = player({ player_id: "of1", position: "OF", salary: 4000 });
  const ok = validatePlayerSelection({ player: cheap, slotIndex: 7, slots, roster });
  assert.equal(ok.ok, true);

  const expensive = player({ player_id: "of2", position: "OF", salary: 60000 });
  const bad = validatePlayerSelection({ player: expensive, slotIndex: 7, slots, roster });
  assert.equal(bad.ok, false);
  assert.match(bad.reason, /salary cap/);
});

test("empty BUILD uses optimizer settings without locks", () => {
  const settings = buildOptimizeSettings({
    platform: "draftkings",
    strategy: "balanced",
    numLineups: 3,
    sport: "mlb",
    stackSize: 4,
    exposure: 30,
    lockKeys: [],
    pool: [],
  });
  assert.equal(settings.num_lineups, 3);
  assert.equal(settings.stack_size, 4);
  assert.equal(settings.max_exposure_pct, 30);
  assert.deepEqual(settings.locked_player_ids, []);
  assert.equal(lineupFillMode(emptySlots(roster)), "empty");
});

test("partial BUILD sends manual locks", () => {
  const slots = emptySlots(roster);
  slots[0] = player({ player_id: "pitch1", name: "Ace", position: "P", salary: 9000 });
  assert.equal(lineupFillMode(slots), "partial");
  const settings = buildOptimizeSettings({
    platform: "draftkings",
    strategy: "gpp",
    numLineups: 2,
    sport: "mlb",
    lockKeys: lockKeysFromSlots(slots),
    pool: slots.filter(Boolean),
  });
  assert.ok(settings.locked_player_ids.includes("pitch1"));
  assert.ok(settings.locked_player_ids.includes("Ace"));
});

test("valid full manual lineup goes to Page 4 without optimizer generation", () => {
  const slots = [
    player({ player_id: "p1", name: "P1", position: "P", salary: 8000 }),
    player({ player_id: "p2", name: "P2", position: "P", salary: 8000 }),
    player({ player_id: "c1", name: "C1", position: "C", salary: 4000 }),
    player({ player_id: "b1", name: "B1", position: "1B", salary: 4000 }),
    player({ player_id: "b2", name: "B2", position: "2B", salary: 4000 }),
    player({ player_id: "b3", name: "B3", position: "3B", salary: 4000 }),
    player({ player_id: "ss", name: "SS1", position: "SS", salary: 4000 }),
    player({ player_id: "of1", name: "OF1", position: "OF", salary: 4000 }),
    player({ player_id: "of2", name: "OF2", position: "OF", salary: 4000 }),
    player({ player_id: "of3", name: "OF3", position: "OF", salary: 4000 }),
  ];
  assert.equal(lineupFillMode(slots), "full");
  const result = validateFullManualLineup(slots, roster);
  assert.equal(result.ok, true);
  assert.equal(result.lineup.players.length, 10);
  assert.ok(result.lineup.total_salary <= roster.salaryCap);
});

test("Page 4 Edit returns to Page 2 and Save uses history API", () => {
  const src = read("app/(tabs)/optimizer/result.tsx");
  assert.match(src, /loadLineupForEdit/);
  assert.match(src, /optimizer\/builder/);
  assert.match(src, /handleSave/);
  assert.match(src, /handleRegenerate/);
  assert.match(src, /\/\(tabs\)\/lineups/);
  assert.match(src, /regenerate_from_ids|handleRegenerate/);
});

test("strategy change clears incompatible result state", () => {
  assert.equal(shouldClearResultState({ strategy: "balanced", count: 3 }, { strategy: "gpp", count: 3 }), true);
  assert.equal(shouldClearResultState({ strategy: "balanced", count: 3 }, { strategy: "balanced", count: 5 }), true);
  assert.equal(shouldClearResultState({ strategy: "balanced", count: 3 }, { strategy: "balanced", count: 3 }), false);
});

test("stadium background is shared across Pages 1-4", () => {
  for (const file of [
    "app/(tabs)/optimizer/index.tsx",
    "app/(tabs)/optimizer/builder.tsx",
    "app/(tabs)/optimizer/players.tsx",
    "app/(tabs)/optimizer/result.tsx",
  ]) {
    assert.match(read(file), /MobileStadiumBackground/);
  }
  assert.match(read("components/MobileStadiumBackground.tsx"), /stadium-night\.jpg/);
  assert.doesNotMatch(read("components/MobileStadiumBackground.tsx"), /borderRadius: 999/);
  assert.equal(existsSync(join(root, "assets/stadium-night.jpg")), true);
  assert.equal(existsSync(join(root, "app/(tabs)/optimizer-classic.tsx")), true);
});

test("canonical MLB DraftKings roster is 10 slots", () => {
  assert.deepEqual(roster.slots, ["P", "P", "C", "1B", "2B", "3B", "SS", "OF", "OF", "OF"]);
  assert.equal(slotEligible("SP", "P", roster), true);
  assert.equal(slotEligible('["SP"]', "P", roster), true);
  assert.equal(slotEligible(["C"], "C", roster), true);
  assert.equal(slotEligible("OF", "SS", roster), false);
  const lineup = {
    players: [
      { name: "A", roster_slot: "P", position: "P" },
      { name: "B", roster_slot: "P", position: "P" },
    ],
  };
  const slots = applyLineupToSlots(lineup, roster);
  assert.equal(slots[0].name, "A");
  assert.equal(remainingSalary(50000, [player({ salary: 5000 }), null]), 45000);
});

test("session reuses runOptimize and saveLineupHistory", () => {
  const src = read("lib/optimizer-session.tsx");
  assert.match(src, /runOptimize/);
  assert.match(src, /saveLineupHistory/);
  assert.match(src, /locked_player_ids|lockKeysFromSlots/);
  assert.match(src, /regenerate_from_ids|regenerateIdsFromLineup/);
  assert.match(src, /getPublishedSlate/);
  assert.match(src, /playersFromSlateDetail/);
});
