"use client";

import { useState, useEffect } from "react";
import { SBEvent, normalizeEvents } from "./sbevent";
import { getApiBaseUrl } from "./api-base-url";

const API_BASE = getApiBaseUrl(
  typeof process !== "undefined" ? process.env.NEXT_PUBLIC_API_URL : undefined,
);

function getToken(): string | null {
  if (typeof window === "undefined") return null;
  try {
    return localStorage.getItem("sbme_dfs_token");
  } catch {
    return null;
  }
}

/**
 * Shared hook that loads SGO events for a league through the canonical
 * `/sgo/events` endpoint and normalizes every entry through the SBEvent
 * safe contract so a malformed/missing field can never crash a consumer.
 */
export function useEvents(league: string) {
  const [events, setEvents] = useState<SBEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      setLoading(true);
      setError(null);
      try {
        const token = getToken();
        const res = await fetch(`${API_BASE}/sgo/events?league=${league}`, {
          headers: token ? { Authorization: `Bearer ${token}` } : {},
        });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const json = await res.json();
        if (!cancelled) {
          // /sgo/events has one contract: { status: "success", data: SBEvent[] }.
          // Normalize defensively so any unexpected wrapper or bad field
          // degrades to an empty list instead of throwing during render.
          setEvents(normalizeEvents(json?.data));
        }
      } catch (err: unknown) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Failed to fetch events");
          setEvents([]);
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    load();
    return () => { cancelled = true; };
  }, [league]);

  return { events, loading, error };
}
