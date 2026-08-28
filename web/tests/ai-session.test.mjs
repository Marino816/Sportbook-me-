import assert from "node:assert/strict";
import test from "node:test";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const aiPage = readFileSync(join(root, "src/app/ai/page.tsx"), "utf8");
const optimizer = readFileSync(join(root, "src/app/optimizer/page.tsx"), "utf8");
const session = readFileSync(join(root, "src/lib/ai-session.ts"), "utf8");
const mobileApi = readFileSync(join(root, "../mobile/lib/ai-api.ts"), "utf8");

test("AI chat sends history, conversation_id, and structured context", () => {
  assert.match(aiPage, /history/);
  assert.match(aiPage, /conversation_id/);
  assert.match(aiPage, /context:/);
  assert.match(aiPage, /suggested_actions/);
  assert.match(aiPage, /onAction/);
});

test("optimizer applies AI handoff query params including locked players", () => {
  assert.match(optimizer, /parseOptimizerHandoff/);
  assert.match(optimizer, /setLockedIds/);
  assert.match(optimizer, /get\("slate"\)/);
});

test("handoff URL builder encodes sport platform slate and lock", () => {
  assert.match(session, /export function buildOptimizerHandoffUrl/);
  assert.match(session, /export function parseOptimizerHandoff/);
  assert.match(session, /params\.set\("lock"/);
  assert.match(session, /params\.set\("slate"/);
});

test("mobile AI client forwards history and context", () => {
  assert.match(mobileApi, /history: history/);
  assert.match(mobileApi, /context: context/);
  assert.match(mobileApi, /conversation_id/);
});
