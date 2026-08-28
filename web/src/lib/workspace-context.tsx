"use client";

import { createContext, useContext, useMemo, useState, useCallback, ReactNode } from "react";

/**
 * Shared authenticated DFS workspace state.
 *
 * Preserves sport / platform / slate / player selections (locks, excludes,
 * likes, projection overrides) across Data Hub, Optimizer, Sims, and Top
 * Stacks so a user can move between tools without losing state.
 */

export interface WorkspaceState {
  sport: string;
  platform: string; // "draftkings" | "fanduel"
  slateId: number | null;
  lockedIds: string[];
  excludedIds: string[];
  likedIds: string[];
  projOverrides: Record<string, number>; // player name -> custom projection
  pendingLineups: any[]; // lineups sent to Sims
}

interface WorkspaceContextValue extends WorkspaceState {
  setSport: (v: string) => void;
  setPlatform: (v: string) => void;
  setSlateId: (v: number | null) => void;
  toggleLock: (id: string) => void;
  toggleExclude: (id: string) => void;
  toggleLike: (id: string) => void;
  setProjOverride: (name: string, value: number) => void;
  setLockedIds: (ids: string[]) => void;
  setExcludedIds: (ids: string[]) => void;
  setPendingLineups: (lineups: any[]) => void;
  reset: () => void;
}

const DEFAULT_STATE: WorkspaceState = {
  sport: "MLB",
  platform: "draftkings",
  slateId: null,
  lockedIds: [],
  excludedIds: [],
  likedIds: [],
  projOverrides: {},
  pendingLineups: [],
};

const WorkspaceContext = createContext<WorkspaceContextValue | null>(null);

export function WorkspaceProvider({ children }: { children: ReactNode }) {
  const [sport, setSport] = useState<string>("MLB");
  const [platform, setPlatform] = useState<string>("draftkings");
  const [slateId, setSlateId] = useState<number | null>(null);
  const [lockedIds, setLockedIds] = useState<string[]>([]);
  const [excludedIds, setExcludedIds] = useState<string[]>([]);
  const [likedIds, setLikedIds] = useState<string[]>([]);
  const [projOverrides, setProjOverrides] = useState<Record<string, number>>({});
  const [pendingLineups, _setPendingLineups] = useState<any[]>([]);

  const toggleLock = useCallback((id: string) => {
    setLockedIds((prev) => (prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]));
    // Lock removes from excluded
    setExcludedIds((prev) => prev.filter((x) => x !== id));
  }, []);

  const toggleExclude = useCallback((id: string) => {
    setExcludedIds((prev) => (prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]));
    setLockedIds((prev) => prev.filter((x) => x !== id));
  }, []);

  const toggleLike = useCallback((id: string) => {
    setLikedIds((prev) => (prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]));
  }, []);

  const setProjOverride = useCallback((name: string, value: number) => {
    setProjOverrides((prev) => ({ ...prev, [name]: value }));
  }, []);

  const setLockedIdsStable = useCallback((ids: string[]) => {
    setLockedIds(ids);
    setExcludedIds((prev) => prev.filter((x) => !ids.includes(x)));
  }, []);

  const setExcludedIdsStable = useCallback((ids: string[]) => {
    setExcludedIds(ids);
    setLockedIds((prev) => prev.filter((x) => !ids.includes(x)));
  }, []);

  const setPendingLineups = useCallback((lineups: any[]) => {
    _setPendingLineups(lineups);
  }, []);

  const reset = useCallback(() => {
    setSport("MLB");
    setPlatform("draftkings");
    setSlateId(null);
    setLockedIds([]);
    setExcludedIds([]);
    setLikedIds([]);
    setProjOverrides({});
    setPendingLineups([]);
  }, []);

  const value = useMemo<WorkspaceContextValue>(
    () => ({
      sport,
      platform,
      slateId,
      lockedIds,
      excludedIds,
      likedIds,
      projOverrides,
      pendingLineups,
      setSport,
      setPlatform,
      setSlateId,
      toggleLock,
      toggleExclude,
      toggleLike,
      setProjOverride,
      setLockedIds: setLockedIdsStable,
      setExcludedIds: setExcludedIdsStable,
      setPendingLineups,
      reset,
    }),
    [sport, platform, slateId, lockedIds, excludedIds, likedIds, projOverrides, pendingLineups,
     toggleLock, toggleExclude, toggleLike, setProjOverride, setLockedIdsStable, setExcludedIdsStable, setPendingLineups, reset]
  );

  return <WorkspaceContext.Provider value={value}>{children}</WorkspaceContext.Provider>;
}

export function useWorkspace(): WorkspaceContextValue {
  const ctx = useContext(WorkspaceContext);
  if (!ctx) throw new Error("useWorkspace must be used within WorkspaceProvider");
  return ctx;
}
