export type RosterTemplate = {
  sport: string;
  platform: string;
  slots: string[];
  salaryCap: number | null;
  minSalary: number;
  filterPositions: string[];
  flexEligible: string[];
  sflxEligible: string[];
  slotLabels: Record<string, string>;
  salaryCapSource: string;
  minUniqueDefault: number;
};

export function rosterKey(sport: string, platform: string): string;
export function getRoster(sport: string, platform: string): RosterTemplate | null;
export function slotLabel(slot: string, roster?: RosterTemplate | null): string;
export function normalizePlayerPos(raw?: string | null): string[];
export function slotEligible(pos: string | undefined | null, slot: string, roster: RosterTemplate): boolean;
export function averageRemainingPerPlayer(remainingSalary: number, remainingSlots: number): number;
export const UNIQUE_LINEUP_UNAVAILABLE: string;
