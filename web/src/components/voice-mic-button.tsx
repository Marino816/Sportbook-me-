"use client";

import { Mic, MicOff } from "lucide-react";
import type { VoiceInputStatus } from "@/lib/voice-input";
import { VOICE_DENIED_HINT, VOICE_UNSUPPORTED_HINT } from "@/lib/voice-input";

export function VoiceMicButton({
  listening,
  status,
  supported,
  disabled,
  onToggle,
  onCancel,
}: {
  listening: boolean;
  status: VoiceInputStatus;
  supported: boolean;
  disabled?: boolean;
  onToggle: () => void;
  onCancel: () => void;
}) {
  const unavailable = !supported || status === "unsupported";
  const blocked = status === "denied";
  const title = unavailable
    ? VOICE_UNSUPPORTED_HINT
    : blocked
      ? VOICE_DENIED_HINT
      : listening
        ? "Stop listening"
        : "Start voice input";

  return (
    <button
      type="button"
      className={`sbme-voice-mic${listening ? " sbme-voice-mic--listening" : ""}${blocked ? " sbme-voice-mic--denied" : ""}`}
      aria-label={title}
      aria-pressed={listening}
      title={title}
      disabled={disabled || unavailable}
      onClick={onToggle}
      onKeyDown={(e) => {
        if (e.key === "Escape" && listening) {
          e.preventDefault();
          onCancel();
        }
      }}
    >
      {listening ? <MicOff size={16} aria-hidden /> : <Mic size={16} aria-hidden />}
    </button>
  );
}
