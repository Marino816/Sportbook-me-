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
export function draftTitle(slot: string, roster: RosterTemplate | null): string;
export function formatAmericanOdds(value: unknown): string;
export function parseGameInfo(gameInfo?: string, fallbackStart?: string | Date | null): { matchup: string; date: string; time: string };
export function matchOddsToGame(label: string, oddsGames?: any[]): any | null;
export function extractGameCards(players: any[], opts?: { slateStart?: string | Date | null; oddsGames?: any[] }): Array<{
  id: string;
  matchup: string;
  date: string;
  time: string;
  weather: string;
  moneyline: string;
  spread: string;
  total: string;
}>;
export function salaryFooterStats(args: { slots: SlotPlayer[]; cap: number; roster: RosterTemplate | null }): {
  filled: number;
  total: number;
  remaining: number;
  underCap: boolean;
  avgRemaining: number;
};
export function confirmedBattingOrder(player: any): number | null;
export function batsDisplay(player: any): string;
export function probablePitcher(player: any): string;
export function opponentRank(player: any): number | null;
export function isConfirmedStarter(player: any): boolean;
export function hasStarterData(players: any[]): boolean;
export function eligiblePositionsLabel(player: any): string;
export function playerMatchupLine(player: any): string;
export function playerGameTime(player: any, slateStart?: string | Date | null): string;
export function sortPlayersBySalary(players: any[], direction: "high" | "low"): any[];
export function applyLineupToSlots(lineup: any, roster: RosterTemplate): SlotPlayer[];
export function shouldClearResultState(prev: { strategy?: string; count?: number }, next: { strategy?: string; count?: number }): boolean;
export function lockKeysFromSlots(slots: SlotPlayer[]): string[];
export function regenerateIdsFromLineup(lineup: any): string[];
export const OPEN_OPTIMIZER_COPY: string;
export const BUILD_BUTTON_LABEL: string;
export const OPEN_OPTIMIZER_LABEL: string;
export { averageRemainingPerPlayer, getRoster, slotEligible, slotLabel } from "./dfs-roster.mjs";
