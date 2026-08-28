/**
 * Browser voice input helpers for SB ME Intelligence.
 *
 * Implementation: Web Speech API (SpeechRecognition / webkitSpeechRecognition).
 * No paid transcription provider.
 *
 * Support (as of 2026):
 * - Chromium desktop: Chrome, Edge, Opera — supported (SpeechRecognition)
 * - Safari 14.1+ (macOS/iOS) — supported via webkitSpeechRecognition
 * - Firefox — not supported; typing remains available
 * - In-app browsers / missing API — treated as unsupported
 *
 * Permission is requested only when the user starts listening (recognition.start()).
 * Secure context required (https or localhost).
 */

export type VoiceInputStatus =
  | "idle"
  | "listening"
  | "unsupported"
  | "denied"
  | "error";

export type SpeechRecognitionLike = {
  lang: string;
  continuous: boolean;
  interimResults: boolean;
  start: () => void;
  stop: () => void;
  abort: () => void;
  onresult: ((event: SpeechRecognitionResultEventLike) => void) | null;
  onerror: ((event: { error?: string }) => void) | null;
  onend: (() => void) | null;
};

export type SpeechRecognitionResultEventLike = {
  resultIndex: number;
  results: ArrayLike<{
    isFinal: boolean;
    0: { transcript: string };
    length: number;
  }>;
};

type RecognitionCtor = new () => SpeechRecognitionLike;

type WindowWithSpeech = {
  SpeechRecognition?: RecognitionCtor;
  webkitSpeechRecognition?: RecognitionCtor;
};

export function getSpeechRecognitionCtor(
  globalObj: WindowWithSpeech | undefined | null = typeof globalThis !== "undefined"
    ? (globalThis as WindowWithSpeech)
    : undefined,
): RecognitionCtor | null {
  if (!globalObj) return null;
  return globalObj.SpeechRecognition || globalObj.webkitSpeechRecognition || null;
}

export function isSpeechRecognitionSupported(
  globalObj?: WindowWithSpeech | null,
): boolean {
  return getSpeechRecognitionCtor(globalObj) != null;
}

/** Merge a spoken fragment onto composer text already in the box. */
export function appendVoiceTranscript(baseline: string, spoken: string): string {
  const base = (baseline || "").trimEnd();
  const next = (spoken || "").replace(/\s+/g, " ").trim();
  if (!next) return baseline || "";
  if (!base) return next;
  return `${base} ${next}`;
}

export function collectSpokenTranscript(event: SpeechRecognitionResultEventLike): string {
  const parts: string[] = [];
  const results = event.results;
  for (let i = 0; i < results.length; i += 1) {
    const alt = results[i]?.[0]?.transcript;
    if (alt) parts.push(alt);
  }
  return parts.join(" ").replace(/\s+/g, " ").trim();
}

export const VOICE_UNSUPPORTED_HINT =
  "Voice input isn’t supported in this browser. Type your question instead.";
export const VOICE_DENIED_HINT =
  "Microphone access was blocked. You can still type.";
export const VOICE_LISTENING_HINT = "Listening…";
