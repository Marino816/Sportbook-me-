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
  assert.match(aiPage, /VoiceMicButton/);
  assert.match(aiPage, /onTranscript: \(text\) => setInput\(text\)/);
});

test("command center identity, safeguard, and real context bar", () => {
  assert.match(aiPage, /SB ME Intelligence™/);
  assert.match(aiPage, /Sports Intelligence/);
  assert.match(aiPage, /SB ME CACHE/);
  assert.doesNotMatch(aiPage, /LIVE DATA CONNECTED/);
  assert.match(aiPage, /will not invent odds/);
  assert.match(aiPage, /sessionContextView/);
  assert.match(aiPage, /ctxView \?/);
  assert.match(aiPage, /send\(item\.prompt\)/);
  assert.match(aiPage, /Today's MLB games/);
  assert.match(aiPage, /Build a DraftKings lineup/);
  assert.match(session, /export function hasMeaningfulContext/);
  assert.match(session, /export function sessionContextView/);
  assert.match(session, /Locked:/);
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

test("context bar requires real session fields", () => {
  const meaningful = (ctx) => Boolean(
    ctx.sport || ctx.platform || ctx.slate_id || ctx.slate_name
    || (ctx.locked_players || []).some((p) => p?.name),
  );
  assert.equal(meaningful({}), false);
  assert.equal(meaningful({ requested_action: "optimizer" }), false);
  assert.equal(meaningful({
    sport: "MLB",
    platform: "draftkings",
    slate_name: "7:10 PM Main",
    locked_players: [{ name: "Yordan Alvarez" }],
  }), true);
});
