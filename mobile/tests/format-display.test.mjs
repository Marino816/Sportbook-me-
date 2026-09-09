/**
 * Live-odds display helpers.
 * Run: node --test tests/format-display.test.mjs
 */
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { test } from "node:test";
import { displayBookmakerName, formatEventTime } from "../lib/format-display.mjs";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");

test("formatEventTime turns ISO timestamps into local readable time", () => {
  const formatted = formatEventTime("2026-09-08T23:40:00Z");
  assert.match(formatted, /Sep/);
  assert.match(formatted, /8/);
  assert.match(formatted, /\d/);
  assert.doesNotMatch(formatted, /2026-09-08T23:40:00Z/);
  assert.equal(formatEventTime(""), "");
  assert.equal(formatEventTime(null), "");
});

test("unknown bookmaker placeholders are not displayed", () => {
  assert.equal(displayBookmakerName("unknown"), "");
  assert.equal(displayBookmakerName("Unknown"), "");
  assert.equal(displayBookmakerName(""), "");
  assert.equal(displayBookmakerName("DraftKings"), "DraftKings");
});

test("live odds screen does not invent Book N names", () => {
  const src = readFileSync(join(root, "app/(tabs)/market-tools/live-odds.tsx"), "utf8");
  assert.match(src, /formatEventTime/);
  assert.match(src, /displayBookmakerName/);
  assert.doesNotMatch(src, /Book \$\{bi/);
});
