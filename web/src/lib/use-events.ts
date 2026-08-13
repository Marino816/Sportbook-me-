"use client";

import { useState, useEffect } from "react";
import { SBEvent } from "./sbevent";
import { getApiBaseUrl } from "./api-base-url";

const API_BASE = getApiBaseUrl(
  typeof process !== "undefined" ? process.env.NEXT_PUBLIC_API_URL : undefined,
);

function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("sbme_dfs_token");
}

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
          setEvents(Array.isArray(json?.data) ? json.data : []);
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