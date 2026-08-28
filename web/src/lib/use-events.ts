"use client";

import { useLiveScores } from "./live-scores";

/**
 * Canonical event hook — shares the live-scores module cache so Market Tools
 * pages do not each independently poll SportsGameOdds.
 */
export function useEvents(league: string) {
  const { events, loading, error, lastFetch, refresh } = useLiveScores(league);
  return { events, loading, error, lastFetch, refresh };
}
