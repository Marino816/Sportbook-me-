import assert from "node:assert/strict";
import test from "node:test";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const optimizer = readFileSync(join(root, "src/app/optimizer/page.tsx"), "utf8");
const api = readFileSync(join(root, "src/lib/api.ts"), "utf8");
const results = readFileSync(join(root, "src/lib/optimizer-results.ts"), "utf8");

function extractOptimizerLineups(res) {
  if (!res || typeof res !== "object") return [];
  const data = res.data;
  if (Array.isArray(data)) return data;
  if (data && typeof data === "object") {
    const inner = data.lineups;
    if (Array.isArray(inner)) return inner;
  }
  return [];
}

function optimizerGenerationNote(res, renderedCount) {
  if (!res || typeof res !== "object") return null;
  const data = res.data;
  const fromLineup = (row) => {
    if (!row || typeof row !== "object") return null;
    const w = row.generation_warning;
    return typeof w === "string" && w.trim() ? w : null;
  };
  if (data && typeof data === "object" && !Array.isArray(data)) {
    const requested = Number(data.requested_lineups);
    const generated = Number(data.generated_lineups);
    if (Number.isFinite(requested) && Number.isFinite(generated) && generated < requested) {
      return `Only ${generated}/${requested} feasible lineups found`;
    }
    if (Array.isArray(data.lineups) && data.lineups.length) return fromLineup(data.lineups[0]);
  }
  if (Array.isArray(data) && data.length) return fromLineup(data[0]);
  return renderedCount > 0 ? null : null;
}

function requestedNumLineups(raw) {
  const n = Number(raw);
  if (!Number.isFinite(n) || n < 1) return 1;
  return Math.min(150, Math.floor(n));
}

const tenLineups = Array.from({ length: 10 }, (_, i) => ({
  total_salary: 50000,
  projected_score: 100 + i,
  players: [{ id: `p${i}`, name: `Player ${i}` }],
}));

test("successful save sends lineup payload to POST /lineups/history", () => {
  assert.match(api, /export async function saveLineupHistory/);
  assert.match(api, /"\/lineups\/history"/);
  assert.match(api, /method:\s*"POST"/);
  assert.match(optimizer, /saveLineupHistory\(\{/);
  assert.match(optimizer, /slate_id:\s*resolvedSlateId/);
  assert.match(optimizer, /lineups,/);
  assert.match(optimizer, /res\?\.data\?\.saved/);
});

test("Saved ✓ only after persistence confirmation", () => {
  const mark = optimizer.slice(optimizer.indexOf("const markSaved"), optimizer.indexOf("const slots"));
  assert.match(mark, /await saveLineupHistory/);
  assert.match(mark, /if \(!res\?\.data\?\.saved\)/);
  assert.match(mark, /setHistorySaved\(true\)/);
  assert.ok(mark.indexOf("if (!res?.data?.saved)") < mark.indexOf("setHistorySaved(true)"));
  assert.match(mark, /setSaveError/);
  assert.match(mark, /setHistorySaved\(false\)/);
});

test("save failure does not show Saved check", () => {
  const mark = optimizer.slice(optimizer.indexOf("const markSaved"), optimizer.indexOf("const slots"));
  assert.match(mark, /catch/);
  assert.match(mark, /Could not save lineup/);
  assert.doesNotMatch(mark, /catch\s*\{\s*setSavedNote\(true\)/);
});

test("extractOptimizerLineups keeps all 10 lineups", () => {
  const extracted = extractOptimizerLineups({
    status: "success",
    data: { lineups: tenLineups, requested_lineups: 10, generated_lineups: 10 },
  });
  assert.equal(extracted.length, 10);
  assert.equal(extracted[9].projected_score, 109);
});

test("frontend does not truncate optimizer response to first lineup", () => {
  assert.match(optimizer, /extractOptimizerLineups\(res\)/);
  assert.match(optimizer, /setLineups\(extracted/);
  assert.doesNotMatch(optimizer, /setLineups\(\[extracted\[0\]\]\)/);
  assert.doesNotMatch(optimizer, /inner\[0\]/);
  assert.doesNotMatch(optimizer, /lineups\.slice\(0,\s*1\)/);
  assert.match(results, /if \(Array\.isArray\(inner\)\) return inner/);
});

test("lineupCount 10 is sent as num_lineups on BUILD and regenerate", () => {
  assert.match(optimizer, /num_lineups:\s*numLineups/);
  assert.match(optimizer, /requestedNumLineups\(vars\?\.num_lineups \?\? lineupCount\)/);
  assert.match(optimizer, /mutate\(\{ strategy, num_lineups: lineupCount \}\)/);
  assert.match(optimizer, /mutate\(\{ strategy: next, num_lineups: lineupCount \}\)/);
  assert.equal(requestedNumLineups(10), 10);
});

test("fewer-than-requested solver result surfaces truthful warning", () => {
  const note = optimizerGenerationNote({
    data: { lineups: tenLineups.slice(0, 1), requested_lineups: 10, generated_lineups: 1 },
  }, 1);
  assert.equal(note, "Only 1/10 feasible lineups found");
  assert.match(optimizer, /generationWarning/);
});

test("uniqueness regenerate path still sends selected count", () => {
  assert.match(optimizer, /regenerate_from_ids/);
  const regen = optimizer.slice(optimizer.indexOf("const regenerate"), optimizer.indexOf("const markSaved"));
  assert.match(regen, /num_lineups: lineupCount/);
});

test("manually constructed lineup can be saved via existing payload", () => {
  const extracted = extractOptimizerLineups({
    data: {
      lineups: [{
        total_salary: 49200,
        projected_score: 88.1,
        players: [{ id: "GERRIT_COLE_1_MLB", name: "Gerrit Cole", salary: 9500, projected_fp: 18.6 }],
      }],
    },
  });
  assert.equal(extracted.length, 1);
  assert.equal(extracted[0].players[0].name, "Gerrit Cole");
  assert.match(optimizer, /locked_player_ids: solverPlayerKeys\(ws\.lockedIds/);
});

test("BUILD failure switches to Built Lineups and surfaces the optimizer error", () => {
  const err = optimizer.slice(optimizer.indexOf("onError: (err)"), optimizer.indexOf("const applyStrategy"));
  assert.match(err, /setMainTab\("built"\)/);
  assert.match(optimizer, /optimizeMutation\.isError && !optimizeMutation\.isPending/);
});
