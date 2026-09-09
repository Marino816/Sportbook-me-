import type { RosterTemplate } from "./dfs-roster.mjs";

export type SlotPlayer = Record<string, any> | null;
export type LineupFillMode = "empty" | "partial" | "full";

export function playerKey(player: any): string;
export function isOpenSlate(slate: any): boolean;
export function filterOpenSlates(slates: any[]): any[];
export function emptySlots(roster: RosterTemplate | null): SlotPlayer[];
export function lineupFillMode(slots: SlotPlayer[]): LineupFillMode;
export function usedSalary(slots: SlotPlayer[]): number;
export function remainingSalary(cap: number, slots: SlotPlayer[]): number;
export function displayProjection(player: any): number | null;
export function validatePlayerSelection(args: {
  player: any;
  slotIndex: number;
  slots: SlotPlayer[];
  roster: RosterTemplate | null;
}): { ok: boolean; reason?: string };
export function validateFullManualLineup(
  slots: SlotPlayer[],
  roster: RosterTemplate | null,
): { ok: boolean; reason?: string; lineup?: any };
export function solverLockKeys(keys: string[], pool: any[]): string[];
export function buildOptimizeSettings(args: {
  platform: string;
  strategy: string;
  numLineups: number;
  sport: string;
  stackSize?: number | null;
  exposure?: number | null;
  lockKeys?: string[];
  pool?: any[];
  regenerateFromIds?: string[];
}): Record<string, unknown>;
export function gameLabel(player: any): string;
export function extractGames(players: any[]): string[];
export function playerMatchesGame(player: any, game: string): boolean;
export function sortPlayersBySalary(players: any[], direction: "high" | "low"): any[];
export function applyLineupToSlots(lineup: any, roster: RosterTemplate): SlotPlayer[];
export function shouldClearResultState(prev: { strategy?: string; count?: number }, next: { strategy?: string; count?: number }): boolean;
export function lockKeysFromSlots(slots: SlotPlayer[]): string[];
export function regenerateIdsFromLineup(lineup: any): string[];
export const OPEN_OPTIMIZER_COPY: string;
export const BUILD_BUTTON_LABEL: string;
export const OPEN_OPTIMIZER_LABEL: string;
export { averageRemainingPerPlayer, getRoster, slotEligible, slotLabel } from "./dfs-roster.mjs";
