"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import {
  appendVoiceTranscript,
  collectSpokenTranscript,
  getSpeechRecognitionCtor,
  isSpeechRecognitionSupported,
  type SpeechRecognitionLike,
  type VoiceInputStatus,
} from "@/lib/voice-input";

/**
 * Browser-only voice capture. Does not send messages.
 * Permission is requested only when start() runs.
 */
export function useVoiceInput(options: {
  lang?: string;
  getBaseline: () => string;
  onTranscript: (composerText: string) => void;
}) {
  const { lang = "en-US", getBaseline, onTranscript } = options;
  const [status, setStatus] = useState<VoiceInputStatus>("idle");
  const [supported, setSupported] = useState<boolean | null>(null);
  const recRef = useRef<SpeechRecognitionLike | null>(null);
  const baselineRef = useRef("");
  const ignoreEndRef = useRef(false);
  const onTranscriptRef = useRef(onTranscript);
  const getBaselineRef = useRef(getBaseline);
  onTranscriptRef.current = onTranscript;
  getBaselineRef.current = getBaseline;

  useEffect(() => {
    setSupported(isSpeechRecognitionSupported());
  }, []);

  const teardown = useCallback(() => {
    const rec = recRef.current;
    recRef.current = null;
    if (!rec) return;
    rec.onresult = null;
    rec.onerror = null;
    rec.onend = null;
    try {
      rec.abort();
    } catch {
      /* ignore */
    }
  }, []);

  useEffect(() => () => teardown(), [teardown]);

  const start = useCallback(() => {
    if (!isSpeechRecognitionSupported()) {
      setStatus("unsupported");
      return;
    }
    teardown();
    const Ctor = getSpeechRecognitionCtor();
    if (!Ctor) {
      setStatus("unsupported");
      return;
    }
    baselineRef.current = getBaselineRef.current() || "";
    ignoreEndRef.current = false;
    const rec = new Ctor();
    rec.lang = lang;
    rec.continuous = true;
    rec.interimResults = true;
    rec.onresult = (event) => {
      const spoken = collectSpokenTranscript(event);
      onTranscriptRef.current(appendVoiceTranscript(baselineRef.current, spoken));
    };
    rec.onerror = (event) => {
      const err = String(event?.error || "");
      if (err === "not-allowed" || err === "service-not-allowed") {
        setStatus("denied");
        return;
      }
      if (err === "aborted" || err === "no-speech") {
        setStatus("idle");
        return;
      }
      setStatus("error");
    };
    rec.onend = () => {
      recRef.current = null;
      if (ignoreEndRef.current) return;
      setStatus((prev) => (prev === "denied" || prev === "unsupported" ? prev : "idle"));
    };
    recRef.current = rec;
    try {
      rec.start();
      setStatus("listening");
    } catch {
      recRef.current = null;
      setStatus("error");
    }
  }, [lang, teardown]);

  const stop = useCallback(() => {
    ignoreEndRef.current = false;
    const rec = recRef.current;
    if (!rec) {
      setStatus("idle");
      return;
    }
    try {
      rec.stop();
    } catch {
      teardown();
    }
    setStatus("idle");
  }, [teardown]);

  const cancel = useCallback(() => {
    ignoreEndRef.current = true;
    const baseline = baselineRef.current;
    teardown();
    onTranscriptRef.current(baseline);
    setStatus("idle");
  }, [teardown]);

  const toggle = useCallback(() => {
    if (status === "listening") stop();
    else start();
  }, [status, start, stop]);

  return {
    status,
    supported,
    listening: status === "listening",
    start,
    stop,
    cancel,
    toggle,
  };
}
