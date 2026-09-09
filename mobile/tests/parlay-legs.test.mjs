/**
 * Parlay duplicate / opposing-outcome helpers.
 * Run: node --test tests/parlay-legs.test.mjs
 */
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { test } from "node:test";
import {
  hasConflictingLeg,
  hasDuplicateLeg,
  uniqueValidLegs,
} from "../lib/parlay-legs.mjs";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");

test("duplicate same-event moneyline is detected", () => {
  const legs = [
    { eventId: "cle-det", market: "moneyline", selection: "Cleveland Guardians", odds: 103 },
  ];
  assert.equal(hasDuplicateLeg(legs, "cle-det", "moneyline", "Cleveland Guardians"), true);
  assert.equal(hasDuplicateLeg(legs, "cle-det", "moneyline", "Detroit Tigers"), false);
});

test("opposing moneylines in the same market conflict", () => {
  const legs = [
    { eventId: "cle-det", market: "moneyline", selection: "Cleveland Guardians", odds: 103 },
  ];
  assert.equal(hasConflictingLeg(legs, "cle-det", "moneyline", "Detroit Tigers"), true);
  assert.equal(hasConflictingLeg(legs, "nyy-bos", "moneyline", "Detroit Tigers"), false);
});

test("payout helpers keep unique valid legs only", () => {
  const legs = [
    { eventId: "cle-det", market: "moneyline", selection: "Cleveland Guardians", odds: 100 },
    { eventId: "cle-det", market: "moneyline", selection: "Cleveland Guardians", odds: 100 },
    { eventId: "cle-det", market: "moneyline", selection: "Detroit Tigers", odds: -118 },
    { eventId: "nyy-bos", market: "moneyline", selection: "New York Yankees", odds: -130 },
  ];
  const unique = uniqueValidLegs(legs);
  assert.equal(unique.length, 2);
  assert.equal(unique[0].selection, "Cleveland Guardians");
  assert.equal(unique[1].selection, "New York Yankees");
});

test("parlay screen wires duplicate and conflict guards", () => {
  const src = readFileSync(join(root, "app/(tabs)/market-tools/parlay.tsx"), "utf8");
  assert.match(src, /hasDuplicateLeg/);
  assert.match(src, /hasConflictingLeg/);
  assert.match(src, /uniqueValidLegs/);
  assert.match(src, /Already added/);
  assert.match(src, /Conflicting pick/);
});
