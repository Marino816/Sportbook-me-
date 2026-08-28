import assert from "node:assert/strict";
import test from "node:test";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const helpers = readFileSync(join(root, "src/lib/voice-input.ts"), "utf8");
const hook = readFileSync(join(root, "src/hooks/use-voice-input.ts"), "utf8");
const mic = readFileSync(join(root, "src/components/voice-mic-button.tsx"), "utf8");
const aiPage = readFileSync(join(root, "src/app/ai/page.tsx"), "utf8");

function appendVoiceTranscript(baseline, spoken) {
  const base = (baseline || "").trimEnd();
  const next = (spoken || "").replace(/\s+/g, " ").trim();
  if (!next) return baseline || "";
  if (!base) return next;
  return `${base} ${next}`;
}

function getSpeechRecognitionCtor(globalObj) {
  if (!globalObj) return null;
  return globalObj.SpeechRecognition || globalObj.webkitSpeechRecognition || null;
}

test("appendVoiceTranscript fills composer without sending", () => {
  assert.equal(appendVoiceTranscript("", "Build it"), "Build it");
  assert.equal(appendVoiceTranscript("Lock Yordan", "Build it"), "Lock Yordan Build it");
  assert.equal(appendVoiceTranscript("hello  ", "world"), "hello world");
  assert.match(helpers, /export function appendVoiceTranscript/);
});

test("SpeechRecognition detection supports webkit and empty fallback", () => {
  assert.equal(getSpeechRecognitionCtor(null), null);
  assert.equal(getSpeechRecognitionCtor({}), null);
  assert.equal(typeof getSpeechRecognitionCtor({ webkitSpeechRecognition: function Webkit() {} }), "function");
  assert.match(helpers, /webkitSpeechRecognition/);
  assert.match(helpers, /Firefox/);
});

test("voice hook never auto-sends or fetches chat", () => {
  assert.match(hook, /rec\.start\(\)/);
  assert.match(hook, /onTranscriptRef\.current/);
  assert.match(hook, /const cancel = useCallback/);
  assert.match(hook, /const stop = useCallback/);
  assert.doesNotMatch(hook, /fetch\(/);
  assert.doesNotMatch(hook, /\/ai\/chat/);
  assert.doesNotMatch(hook, /\bsend\s*\(/);
});

test("AI composer wires mic into input only and keeps session payload", () => {
  assert.match(aiPage, /VoiceMicButton/);
  assert.match(aiPage, /onTranscript: \(text\) => setInput\(text\)/);
  assert.match(aiPage, /Ask SB ME Intelligence/);
  assert.match(aiPage, /conversation_id: convRef\.current/);
  assert.match(aiPage, /history,/);
  assert.match(aiPage, /context: current/);
  assert.match(aiPage, /voice\.cancel/);
  assert.doesNotMatch(aiPage, /onTranscript:[\s\S]{0,120}send\(/);
  assert.doesNotMatch(aiPage, /onTranscript:[\s\S]{0,120}setContext\(/);
  assert.doesNotMatch(aiPage, /onTranscript:[\s\S]{0,120}setConvId\(/);
  assert.doesNotMatch(aiPage, /onTranscript:[\s\S]{0,120}setMessages\(/);
});

test("mic control is keyboard accessible and has listening/cancel affordances", () => {
  assert.match(mic, /aria-label/);
  assert.match(mic, /aria-pressed/);
  assert.match(mic, /Escape/);
  assert.match(aiPage, /VOICE_LISTENING_HINT/);
  assert.match(aiPage, /sbme-voice-cancel/);
  assert.match(aiPage, /Cancel/);
});
