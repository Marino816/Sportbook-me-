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
  confirmedBattingOrder,
  displayProjection,
  draftTitle,
  emptySlots,
  extractGameCards,
  filterOpenSlates,
  getRoster,
  lineupFillMode,
  lockKeysFromSlots,
  OPEN_OPTIMIZER_COPY,
  OPEN_OPTIMIZER_LABEL,
  playerMatchesGame,
  remainingSalary,
  salaryFooterStats,
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

test("Page 2 salary and Clear are independently spaced", () => {
  const src = read("app/(tabs)/optimizer/builder.tsx");
  assert.match(src, /styles\.slotSal/);
  assert.match(src, /styles\.clearBtn/);
  assert.match(src, /minHeight: 44/);
  assert.match(src, /marginRight: 12/);
  assert.match(src, /formatSalaryFull/);
  assert.match(src, /accessibilityLabel=\{`Clear/);
  assert.match(src, /numberOfLines=\{1\}/);
  assert.doesNotMatch(src, /slotSal[\s\S]{0,80}styles\.clear/);
});

test("Page 3 uses position-specific draft titles", () => {
  const nfl = getRoster("nfl", "draftkings");
  const mlb = getRoster("mlb", "draftkings");
  assert.equal(draftTitle("QB", nfl), "Draft Quarterback");
  assert.equal(draftTitle("RB", nfl), "Draft Running Back");
  assert.equal(draftTitle("WR", nfl), "Draft Wide Receiver");
  assert.equal(draftTitle("TE", nfl), "Draft Tight End");
  assert.equal(draftTitle("DST", nfl), "Draft DST");
  assert.equal(draftTitle("P", mlb), "Draft Pitcher");
  assert.equal(draftTitle("C", mlb), "Draft Catcher");
  assert.equal(draftTitle("1B", mlb), "Draft First Base");
  assert.equal(draftTitle("2B", mlb), "Draft Second Base");
  assert.equal(draftTitle("3B", mlb), "Draft Third Base");
  assert.equal(draftTitle("SS", mlb), "Draft Shortstop");
  assert.equal(draftTitle("OF", mlb), "Draft Outfield");
  const src = read("app/(tabs)/optimizer/players.tsx");
  assert.match(src, /draftTitle\(/);
  assert.match(src, /Search All Players/);
});

test("compact game cards filter the eligible pool and stay narrow", () => {
  const cards = extractGameCards([
    { name: "A", team: "BUF", opponent: "MIA", game_info: "BUF@MIA 01:00PM ET" },
    { name: "B", team: "MIA", opponent: "BUF", game_info: "BUF@MIA 01:00PM ET" },
    { name: "C", team: "NE", opponent: "SEA", game_info: "NE@SEA 08:20PM ET" },
  ], {
    oddsGames: [{ home_abbr: "MIA", away_abbr: "BUF", moneyline_home: -140, moneyline_away: 120, spread_line: -3.5, total_line: 44.5 }],
  });
  assert.equal(cards.length, 2);
  assert.equal(cards[0].matchup, "BUF@MIA");
  assert.equal(cards[0].time, "01:00PM ET");
  assert.equal(cards[0].moneyline, "+120 / -140");
  assert.equal(cards[0].total, "O/U 44.5");
  assert.equal(cards[0].weather, "");
  assert.equal(playerMatchesGame({ game_info: "BUF@MIA 01:00PM ET" }, "BUF@MIA"), true);
  assert.equal(playerMatchesGame({ game_info: "NE@SEA 08:20PM ET" }, "BUF@MIA"), false);
  const src = read("app/(tabs)/optimizer/players.tsx");
  assert.match(src, /width: 168/);
  assert.match(src, /flexGrow: 0/);
  assert.match(src, /maxHeight: 108/);
  assert.match(src, /All Games/);
});

test("missing projections display as unavailable, not 0.0", () => {
  assert.equal(displayProjection({}), null);
  assert.equal(displayProjection({ fppg: null, bc_beta_proj: null }), null);
  assert.equal(displayProjection({ projected_fp: 0 }), 0);
  assert.equal(displayProjection({ fppg: 12.4 }), 12.4);
  const src = read("app/(tabs)/optimizer/players.tsx");
  assert.match(src, /value == null \? "—" /);
  assert.match(src, /projectionLabel/);
});

test("confirmed batting order shows only when lineup data is confirmed", () => {
  assert.equal(confirmedBattingOrder({ batting_order: 7 }), null);
  assert.equal(confirmedBattingOrder({ batting_order: 7, lineup_confirmed: true }), 7);
  assert.equal(confirmedBattingOrder({ lineup_order: 1, confirmed_lineup: true }), 1);
  assert.equal(confirmedBattingOrder({ batting_order: 6, batting_order_confirmed: "yes" }), 6);
  const src = read("app/(tabs)/optimizer/players.tsx");
  assert.match(src, /confirmedBattingOrder/);
  assert.match(src, /\{order\} ✓/);
  assert.doesNotMatch(src, /fake confirmation|always confirmed/i);
});

test("salary footer tracks filled slots remaining and cap", () => {
  const nfl = getRoster("nfl", "draftkings");
  const slots = emptySlots(nfl);
  const empty = salaryFooterStats({ slots, cap: 50000, roster: nfl });
  assert.equal(empty.filled, 0);
  assert.equal(empty.total, 9);
  assert.equal(empty.remaining, 50000);
  assert.equal(empty.underCap, true);
  slots[0] = { salary: 7000 };
  slots[1] = { salary: 7000 };
  slots[2] = { salary: 6200 };
  const partial = salaryFooterStats({ slots, cap: 50000, roster: nfl });
  assert.equal(partial.filled, 3);
  assert.equal(partial.remaining, 29800);
  assert.equal(partial.avgRemaining, Math.round(29800 / 6));
  const mlb = salaryFooterStats({ slots: emptySlots(roster), cap: 50000, roster });
  assert.equal(mlb.total, 10);
  const src = read("app/(tabs)/optimizer/players.tsx");
  assert.match(src, /Positions Filled/);
  assert.match(src, /Remaining Salary/);
  assert.match(src, /Avg Remaining\/Player/);
});

test("player selection and clear update footer stats and persist via session", () => {
  const nfl = getRoster("nfl", "draftkings");
  const slots = emptySlots(nfl);
  const qb = { player_id: "JOSH_ALLEN_1_NFL", name: "Josh Allen", position: "QB", salary: 7000 };
  assert.equal(validatePlayerSelection({ player: qb, slotIndex: 0, slots, roster: nfl }).ok, true);
  slots[0] = qb;
  const afterPick = salaryFooterStats({ slots, cap: nfl.salaryCap, roster: nfl });
  assert.equal(afterPick.filled, 1);
  assert.equal(afterPick.remaining, 43000);
  slots[0] = null;
  const afterClear = salaryFooterStats({ slots, cap: nfl.salaryCap, roster: nfl });
  assert.equal(afterClear.filled, 0);
  assert.equal(afterClear.remaining, 50000);
  const src = read("app/(tabs)/optimizer/players.tsx");
  assert.match(src, /assignPlayer/);
  assert.match(src, /router\.back\(\)/);
  assert.match(read("app/(tabs)/optimizer/builder.tsx"), /clearSlot/);
  assert.match(read("lib/optimizer-session.tsx"), /assignPlayer/);
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

test("NFL partial BUILD sends DK locks without changing roster rules", () => {
  const nfl = getRoster("nfl", "draftkings");
  assert.equal(nfl.slots.length, 9);
  assert.equal(nfl.salaryCap, 50000);
  const slots = emptySlots(nfl);
  slots[0] = { player_id: "JOSH_ALLEN_1_NFL", name: "Josh Allen", position: "QB", salary: 7000 };
  slots[1] = { player_id: "DEVON_ACHANE_1_NFL", name: "De'Von Achane", position: "RB", salary: 7000 };
  slots[2] = { player_id: "KYREN_WILLIAMS_1_NFL", name: "Kyren Williams", position: "RB", salary: 6200 };
  assert.equal(lineupFillMode(slots), "partial");
  const settings = buildOptimizeSettings({
    platform: "draftkings",
    strategy: "balanced",
    numLineups: 1,
    sport: "nfl",
    lockKeys: lockKeysFromSlots(slots),
    pool: slots.filter(Boolean),
  });
  assert.equal(settings.platform, "draftkings");
  assert.equal(settings.sport, "nfl");
  assert.equal(settings.num_lineups, 1);
  assert.ok(settings.locked_player_ids.includes("JOSH_ALLEN_1_NFL"));
  assert.ok(settings.locked_player_ids.includes("DEVON_ACHANE_1_NFL"));
  assert.ok(settings.locked_player_ids.includes("KYREN_WILLIAMS_1_NFL"));
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
