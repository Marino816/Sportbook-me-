/**
 * Sport + platform DFS roster templates (mirrors backend/dfs/roster.py).
 *
 * FanDuel NFL / NCAAF salary caps are 60000 from the verified FanDuel
 * contest reference (empty-lineup remaining + roster slot counts).
 */

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

const DK_NFL_FLEX = ["RB", "WR", "TE"];
const DK_NCAAF_FLEX = ["RB", "WR"];
const SFLX = ["QB", "RB", "WR", "TE"];
const FD_NFL_FLEX = ["RB", "WR", "TE"];
const FD_NCAAF_SFLX = ["QB", "RB", "WR"];

const TEMPLATES: Record<string, RosterTemplate> = {
  "MLB|draftkings": {
    sport: "MLB", platform: "draftkings",
    slots: ["P", "P", "C", "1B", "2B", "3B", "SS", "OF", "OF", "OF"],
    salaryCap: 50000, minSalary: 0,
    filterPositions: ["P", "C", "1B", "2B", "3B", "SS", "OF"],
    flexEligible: [], sflxEligible: [], slotLabels: {},
    salaryCapSource: "mlb_optimizer.PLATFORM_CONFIG", minUniqueDefault: 2,
  },
  "MLB|fanduel": {
    sport: "MLB", platform: "fanduel",
    slots: ["P", "C1B", "2B", "3B", "SS", "OF", "OF", "OF", "UTIL"],
    salaryCap: 35000, minSalary: 28000,
    filterPositions: ["P", "C", "1B", "2B", "3B", "SS", "OF"],
    flexEligible: [], sflxEligible: [], slotLabels: { C1B: "C/1B" },
    salaryCapSource: "mlb_optimizer.PLATFORM_CONFIG", minUniqueDefault: 2,
  },
  "NFL|draftkings": {
    sport: "NFL", platform: "draftkings",
    slots: ["QB", "RB", "RB", "WR", "WR", "WR", "TE", "FLEX", "DST"],
    salaryCap: 50000, minSalary: 0,
    filterPositions: ["QB", "RB", "WR", "TE", "DST"],
    flexEligible: DK_NFL_FLEX, sflxEligible: [], slotLabels: {},
    salaryCapSource: "production review + dfs.parsers DK default", minUniqueDefault: 2,
  },
  "NFL|fanduel": {
    sport: "NFL", platform: "fanduel",
    slots: ["QB", "RB", "RB", "WR", "WR", "WR", "TE", "FLEX", "DEF"],
    salaryCap: 60000, minSalary: 0,
    filterPositions: ["QB", "RB", "WR", "TE", "DEF"],
    flexEligible: FD_NFL_FLEX, sflxEligible: [], slotLabels: {},
    salaryCapSource: "FanDuel NFL contest reference (60k / 9 slots)", minUniqueDefault: 2,
  },
  "NCAAF|draftkings": {
    sport: "NCAAF", platform: "draftkings",
    slots: ["QB", "RB", "RB", "WR", "WR", "WR", "FLEX", "SFLX"],
    salaryCap: 50000, minSalary: 0,
    filterPositions: ["QB", "RB", "WR", "TE", "DST"],
    flexEligible: DK_NCAAF_FLEX, sflxEligible: SFLX, slotLabels: { SFLX: "SUPER FLEX" },
    salaryCapSource: "production review + dfs.parsers DK default", minUniqueDefault: 2,
  },
  "NCAAF|fanduel": {
    sport: "NCAAF", platform: "fanduel",
    slots: ["QB", "RB", "RB", "WR", "WR", "WR", "SFLX"],
    salaryCap: 60000, minSalary: 0,
    filterPositions: ["QB", "RB", "WR", "TE"],
    flexEligible: [], sflxEligible: FD_NCAAF_SFLX, slotLabels: { SFLX: "SUPER FLEX" },
    salaryCapSource: "FanDuel NCAAF contest reference (60k / 7 slots)", minUniqueDefault: 2,
  },
  "NBA|draftkings": {
    sport: "NBA", platform: "draftkings",
    slots: ["PG", "SG", "SF", "PF", "C", "G", "F", "UTIL"],
    salaryCap: 50000, minSalary: 0,
    filterPositions: ["PG", "SG", "SF", "PF", "C"],
    flexEligible: [], sflxEligible: [], slotLabels: {},
    salaryCapSource: "builder.engine.DK_CAP", minUniqueDefault: 2,
  },
  "NBA|fanduel": {
    sport: "NBA", platform: "fanduel",
    slots: ["PG", "PG", "SG", "SG", "SF", "SF", "PF", "PF", "C"],
    salaryCap: 60000, minSalary: 0,
    filterPositions: ["PG", "SG", "SF", "PF", "C"],
    flexEligible: [], sflxEligible: [], slotLabels: {},
    salaryCapSource: "builder.engine.FD_CAP", minUniqueDefault: 2,
  },
};

export function rosterKey(sport: string, platform: string): string {
  return `${(sport || "").toUpperCase()}|${(platform || "draftkings").toLowerCase()}`;
}

export function getRoster(sport: string, platform: string): RosterTemplate | null {
  return TEMPLATES[rosterKey(sport, platform)] || null;
}

export function slotLabel(slot: string, roster?: RosterTemplate | null): string {
  if (roster?.slotLabels?.[slot]) return roster.slotLabels[slot];
  if (slot === "SFLX") return "SUPER FLEX";
  if (slot === "C1B") return "C/1B";
  return slot;
}

export function normalizePlayerPos(raw: string | undefined | null): string[] {
  const text = (raw || "")
    .toUpperCase()
    .replace("SUPER FLEX", "SFLX")
    .replace("SUPERFLEX", "SFLX")
    .replace("D/ST", "DST")
    .replace("D-ST", "DST");
  const parts = text.split(/[/,]/).map((s) => s.trim()).filter(Boolean);
  return parts.map((p) => {
    if (p === "SP" || p === "RP") return "P";
    if (p === "LF" || p === "RF" || p === "CF" || p === "DH") return "OF";
    return p;
  });
}

export function slotEligible(
  pos: string | undefined | null,
  slot: string,
  roster: RosterTemplate,
): boolean {
  const positions = new Set(normalizePlayerPos(pos));
  let slotN = (slot || "").toUpperCase();
  if (slotN === "SUPER FLEX" || slotN === "SUPERFLEX") slotN = "SFLX";
  if (slotN === "UTIL") return [...positions].some((p) => p !== "P");
  if (slotN === "C1B") return positions.has("C") || positions.has("1B") || positions.has("C1B");
  if (slotN === "FLEX") return roster.flexEligible.some((p) => positions.has(p));
  if (slotN === "SFLX") return roster.sflxEligible.some((p) => positions.has(p));
  if (slotN === "DST" || slotN === "DEF") return positions.has("DST") || positions.has("DEF");
  if (roster.sport === "NBA" && slotN === "G") return positions.has("PG") || positions.has("SG") || positions.has("G");
  if (roster.sport === "NBA" && slotN === "F") return positions.has("SF") || positions.has("PF") || positions.has("F");
  return positions.has(slotN);
}

export function averageRemainingPerPlayer(remainingSalary: number, remainingSlots: number): number {
  if (remainingSlots <= 0) return 0;
  return Math.round(remainingSalary / remainingSlots);
}

export const UNIQUE_LINEUP_UNAVAILABLE =
  "No additional unique lineup is available under the current locks/exclusions.";
