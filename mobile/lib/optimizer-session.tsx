import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { Alert } from "react-native";
import { useFocusEffect, useLocalSearchParams } from "expo-router";
import {
  getLineupHistory,
  getMe,
  getPublishedSlate,
  getPublishedSlates,
  getSubscriptionStatus,
  runOptimize,
  saveLineupHistory,
  unwrapUser,
} from "./api";
import { lineupLimitForPlan } from "./plan-copy";
import { OPTIMIZER_SPORTS, STRATEGIES } from "./optimizer-config";
import {
  applyLineupToSlots,
  buildOptimizeSettings,
  emptySlots,
  getRoster,
  lineupFillMode,
  lockKeysFromSlots,
  regenerateIdsFromLineup,
  remainingSalary,
  shouldClearResultState,
  validateFullManualLineup,
  validatePlayerSelection,
} from "./optimizer-flow.mjs";

function clamp(n: number, min: number, max: number) {
  return Math.max(min, Math.min(max, n));
}

function playersFromSlateDetail(detail: any): any[] {
  if (Array.isArray(detail?.players)) return detail.players;
  if (Array.isArray(detail?.data?.players)) return detail.data.players;
  return [];
}

type Platform = "draftkings" | "fanduel";

type Session = {
  sport: string;
  platform: Platform;
  strategy: string;
  count: number;
  stackSize: number | null;
  exposure: number | null;
  slateId: number | null;
  slates: any[];
  fetchingSlates: boolean;
  slateError: string | null;
  selectedSlate: any | null;
  players: any[];
  fetchingPlayers: boolean;
  playersError: string | null;
  slots: any[];
  lockKeys: string[];
  lineups: any[];
  dataSource: string;
  planLimit: number;
  loading: boolean;
  progress: string;
  buildError: string | null;
  selectingSlotIndex: number;
  savedHistory: any[];
  setSport: (sport: string) => void;
  setPlatform: (platform: Platform) => void;
  setStrategy: (strategy: string) => void;
  setCount: (count: number) => void;
  setStackSize: (size: number | null) => void;
  setExposure: (value: number | null) => void;
  setSlateId: (id: number | null) => void;
  setSelectingSlotIndex: (index: number) => void;
  clearSlot: (index: number) => void;
  assignPlayer: (player: any) => { ok: boolean; reason?: string };
  handleBuild: () => Promise<{ ok: boolean; stayOnPage2?: boolean }>;
  handleRegenerate: () => Promise<{ ok: boolean }>;
  handleSave: () => Promise<{ ok: boolean; id?: number }>;
  loadLineupForEdit: (lineup?: any) => void;
  roster: ReturnType<typeof getRoster>;
  cap: number;
  remaining: number;
};

const OptimizerSessionContext = createContext<Session | null>(null);

export function OptimizerSessionProvider({ children }: { children: React.ReactNode }) {
  const params = useLocalSearchParams<{ strategy?: string; sport?: string; platform?: string }>();
  const [sport, setSportState] = useState("mlb");
  const [platform, setPlatformState] = useState<Platform>("draftkings");
  const [strategy, setStrategyState] = useState("balanced");
  const [count, setCountState] = useState(3);
  const [stackSize, setStackSize] = useState<number | null>(null);
  const [exposure, setExposure] = useState<number | null>(null);
  const [slateId, setSlateIdState] = useState<number | null>(null);
  const [slates, setSlates] = useState<any[]>([]);
  const [fetchingSlates, setFetchingSlates] = useState(true);
  const [slateError, setSlateError] = useState<string | null>(null);
  const [players, setPlayers] = useState<any[]>([]);
  const [fetchingPlayers, setFetchingPlayers] = useState(false);
  const [playersError, setPlayersError] = useState<string | null>(null);
  const [slots, setSlots] = useState<any[]>([]);
  const [lockKeys, setLockKeys] = useState<string[]>([]);
  const [lineups, setLineups] = useState<any[]>([]);
  const [dataSource, setDataSource] = useState("");
  const [planLimit, setPlanLimit] = useState(1);
  const [loading, setLoading] = useState(false);
  const [progress, setProgress] = useState("");
  const [buildError, setBuildError] = useState<string | null>(null);
  const [selectingSlotIndex, setSelectingSlotIndex] = useState(0);
  const [savedHistory, setSavedHistory] = useState<any[]>([]);

  const roster = useMemo(() => getRoster(sport, platform), [sport, platform]);
  const cap = roster?.salaryCap ?? 50000;
  const remaining = remainingSalary(cap, slots);

  const resetLineupState = useCallback((nextRoster = roster) => {
    setSlots(emptySlots(nextRoster));
    setLockKeys([]);
    setLineups([]);
    setBuildError(null);
    setProgress("");
    setDataSource("");
  }, [roster]);

  useEffect(() => {
    const nextSport = String(params.sport || "").toLowerCase();
    if (OPTIMIZER_SPORTS.includes(nextSport as (typeof OPTIMIZER_SPORTS)[number])) setSportState(nextSport);
    const nextPlatform = String(params.platform || "").toLowerCase();
    if (nextPlatform === "draftkings" || nextPlatform === "fanduel") setPlatformState(nextPlatform);
    const nextStrategy = String(params.strategy || "").toLowerCase();
    if (STRATEGIES.some((item) => item.id === nextStrategy)) setStrategyState(nextStrategy);
  }, [params.sport, params.platform, params.strategy]);

  useFocusEffect(
    useCallback(() => {
      let active = true;
      Promise.all([
        getSubscriptionStatus().catch(() => null),
        getMe().catch(() => null),
        getLineupHistory().catch(() => []),
      ]).then(([billingBody, meBody, history]) => {
        if (!active) return;
        const billing = (billingBody as any)?.data || billingBody;
        const user = unwrapUser(meBody) || (meBody as any)?.data || meBody;
        const hasAccess = billing?.has_access === true || user?.is_pro === true;
        setPlanLimit(lineupLimitForPlan(billing?.plan || user?.plan, hasAccess));
        setSavedHistory(Array.isArray(history) ? history : []);
      });
      return () => {
        active = false;
      };
    }, []),
  );

  useEffect(() => {
    setCountState((prev) => clamp(prev, 1, Math.max(1, planLimit)));
  }, [planLimit]);

  useEffect(() => {
    setFetchingSlates(true);
    setSlates([]);
    setSlateIdState(null);
    setPlayers([]);
    setPlayersError(null);
    resetLineupState(getRoster(sport, platform));
    let cancelled = false;
    (async () => {
      try {
        const items = await getPublishedSlates({ sport, platform });
        if (cancelled) return;
        setSlateError(null);
        setSlates(items);
        const current = items.find((s: any) => s.is_current) || items.find((s: any) => String(s.freshness || "").toUpperCase() === "CURRENT") || items[0];
        const nextId = current?.id == null ? null : Number(current.id);
        if (nextId) setFetchingPlayers(true);
        setSlateIdState(nextId);
      } catch (e) {
        if (cancelled) return;
        setSlates([]);
        setSlateIdState(null);
        setSlateError(e instanceof Error ? e.message : "Could not load slates");
      } finally {
        if (!cancelled) setFetchingSlates(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [sport, platform, resetLineupState]);

  useEffect(() => {
    setSlots(emptySlots(roster));
    setLockKeys([]);
  }, [roster]);

  useEffect(() => {
    if (!slateId) {
      setPlayers([]);
      setPlayersError(null);
      setFetchingPlayers(false);
      return;
    }
    const id = Number(slateId);
    if (!Number.isFinite(id) || id <= 0) {
      setPlayers([]);
      setPlayersError("No live slate is selected.");
      setFetchingPlayers(false);
      return;
    }
    let cancelled = false;
    (async () => {
      setFetchingPlayers(true);
      setPlayersError(null);
      try {
        const detail = await getPublishedSlate(id);
        if (cancelled) return;
        const pool = playersFromSlateDetail(detail);
        setPlayers(pool);
        if (detail?.data_source) setDataSource(String(detail.data_source));
        if (!pool.length) setPlayersError("This slate returned no players.");
      } catch (e) {
        if (cancelled) return;
        setPlayers([]);
        setPlayersError(e instanceof Error ? e.message : "Could not load this slate's players.");
      } finally {
        if (!cancelled) setFetchingPlayers(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [slateId]);

  const selectedSlate = useMemo(
    () => slates.find((s) => Number(s.id) === Number(slateId)) || null,
    [slates, slateId],
  );

  const setSport = (next: string) => {
    setSportState(next);
  };
  const setPlatform = (next: Platform) => {
    setPlatformState(next);
  };
  const setSlateId = (id: number | null) => {
    const next = id == null ? NaN : Number(id);
    if (Number.isFinite(next) && next > 0) {
      setSlateIdState(next);
      setFetchingPlayers(true);
    } else {
      setSlateIdState(null);
      setPlayers([]);
      setPlayersError(null);
      setFetchingPlayers(false);
    }
    resetLineupState();
  };
  const setStrategy = (next: string) => {
    if (shouldClearResultState({ strategy, count }, { strategy: next, count })) {
      setLineups([]);
      setBuildError(null);
      setProgress("");
    }
    setStrategyState(next);
  };
  const setCount = (next: number) => {
    const clamped = clamp(next, 1, planLimit);
    if (shouldClearResultState({ strategy, count }, { strategy, count: clamped })) {
      setLineups([]);
      setBuildError(null);
      setProgress("");
    }
    setCountState(clamped);
  };

  const clearSlot = (index: number) => {
    const current = slots[index];
    setSlots((prev) => prev.map((item, i) => (i === index ? null : item)));
    if (current) {
      const key = String(current.player_id || current.name || "");
      setLockKeys((prev) => prev.filter((item) => item !== key && item !== current.name));
    }
    setLineups([]);
  };

  const assignPlayer = (player: any) => {
    const result = validatePlayerSelection({ player, slotIndex: selectingSlotIndex, slots, roster });
    if (!result.ok) return result;
    setSlots((prev) => prev.map((item, i) => (i === selectingSlotIndex ? player : item)));
    const key = String(player.player_id || player.name);
    setLockKeys((prev) => Array.from(new Set([...prev, key, player.name].filter(Boolean))));
    setLineups([]);
    return { ok: true };
  };

  const handleBuild = async () => {
    if (!slateId || slateId <= 0) {
      Alert.alert("Select a slate", "No live slate is selected for this sport and platform.");
      return { ok: false, stayOnPage2: true };
    }
    const mode = lineupFillMode(slots);
    if (mode === "full") {
      const validated = validateFullManualLineup(slots, roster);
      if (!validated.ok) {
        setBuildError(validated.reason || "Lineup is not valid.");
        Alert.alert("Lineup invalid", validated.reason || "Lineup is not valid.");
        return { ok: false, stayOnPage2: true };
      }
      setLineups([validated.lineup]);
      setDataSource(selectedSlate?.data_source || dataSource || "");
      setBuildError(null);
      setProgress("Manual lineup ready.");
      return { ok: true };
    }

    const numLineups = clamp(count, 1, planLimit);
    setLoading(true);
    setBuildError(null);
    setProgress(`Generating ${numLineups} ${strategy} lineup${numLineups === 1 ? "" : "s"}…`);
    try {
      const settings = buildOptimizeSettings({
        platform,
        strategy,
        numLineups,
        sport,
        stackSize,
        exposure,
        lockKeys: mode === "empty" ? ([] as string[]) : lockKeysFromSlots(slots),
        pool: players,
        regenerateFromIds: [] as string[],
      });
      const result = await runOptimize(slateId, settings);
      const built = Array.isArray(result?.lineups) ? result.lineups : [];
      setLineups(built);
      setDataSource(result?.dfs_source || result?.source || selectedSlate?.data_source || "");
      setProgress(built.length ? `Built ${built.length} lineup${built.length === 1 ? "" : "s"}.` : "No lineups returned.");
      return { ok: true };
    } catch (e: any) {
      const message = e?.message || "Build failed";
      setProgress("");
      setBuildError(message);
      Alert.alert("Build failed", message);
      return { ok: false, stayOnPage2: true };
    } finally {
      setLoading(false);
    }
  };

  const handleRegenerate = async () => {
    if (!slateId || slateId <= 0) return { ok: false };
    const current = lineups[0];
    setLoading(true);
    try {
      const settings = buildOptimizeSettings({
        platform,
        strategy,
        numLineups: clamp(count, 1, planLimit),
        sport,
        stackSize,
        exposure,
        lockKeys,
        pool: players,
        regenerateFromIds: regenerateIdsFromLineup(current),
      });
      const result = await runOptimize(slateId, settings);
      const built = Array.isArray(result?.lineups) ? result.lineups : [];
      setLineups(built);
      setDataSource(result?.dfs_source || result?.source || selectedSlate?.data_source || "");
      return { ok: true };
    } catch (e: any) {
      Alert.alert("Regenerate failed", e?.message || "Could not regenerate.");
      return { ok: false };
    } finally {
      setLoading(false);
    }
  };

  const handleSave = async () => {
    if (!lineups.length) {
      Alert.alert("Nothing to save", "Build a lineup first.");
      return { ok: false };
    }
    try {
      const saved = await saveLineupHistory({
        sport: sport.toUpperCase(),
        platform,
        slate_id: slateId,
        strategy,
        lineups,
      });
      const history = await getLineupHistory().catch(() => []);
      setSavedHistory(Array.isArray(history) ? history : []);
      return { ok: true, id: saved?.id };
    } catch (e: any) {
      Alert.alert("Save failed", e?.message || "Could not save lineup.");
      return { ok: false };
    }
  };

  const loadLineupForEdit = (lineup?: any) => {
    if (!roster) return;
    const source = lineup || lineups[0];
    if (!source) return;
    setSlots(applyLineupToSlots(source, roster));
  };

  const value: Session = {
    sport,
    platform,
    strategy,
    count,
    stackSize,
    exposure,
    slateId,
    slates,
    fetchingSlates,
    slateError,
    selectedSlate,
    players,
    fetchingPlayers,
    playersError,
    slots,
    lockKeys,
    lineups,
    dataSource,
    planLimit,
    loading,
    progress,
    buildError,
    selectingSlotIndex,
    savedHistory,
    setSport,
    setPlatform,
    setStrategy,
    setCount,
    setStackSize,
    setExposure,
    setSlateId,
    setSelectingSlotIndex,
    clearSlot,
    assignPlayer,
    handleBuild,
    handleRegenerate,
    handleSave,
    loadLineupForEdit,
    roster,
    cap,
    remaining,
  };

  return <OptimizerSessionContext.Provider value={value}>{children}</OptimizerSessionContext.Provider>;
}

export function useOptimizerSession() {
  const ctx = useContext(OptimizerSessionContext);
  if (!ctx) throw new Error("useOptimizerSession must be used inside OptimizerSessionProvider");
  return ctx;
}
