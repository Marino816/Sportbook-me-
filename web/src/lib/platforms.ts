/**
 * SB ME 55-platform catalog vs SportsGameOdds bookmaker IDs.
 *
 * These are NOT the same universe. Odds are never invented for a platform
 * that did not return a market.
 */

import catalog from "./sbme-55-platforms.json";

export type PlatformRow = {
  id: string;
  name: string;
  sgo_ids: string[];
};

export const SBME_55_PLATFORMS: PlatformRow[] = catalog as PlatformRow[];

export const SBME_55_COUNT = SBME_55_PLATFORMS.length;

export type PlatformStatus = "mapped_to_sgo" | "mapping_needed" | "no_current_data" | "sgo_unlisted";

export function classifyPlatforms(observedSgoIds: string[]): {
  mapped: PlatformRow[];
  mappingNeeded: PlatformRow[];
  noCurrentData: PlatformRow[];
  sgoUnlisted: string[];
  counts: Record<string, number>;
} {
  const observed = new Set(observedSgoIds.map((id) => id.trim().toLowerCase()).filter(Boolean));
  const catalogSgo = new Set<string>();
  const mapped: PlatformRow[] = [];
  const mappingNeeded: PlatformRow[] = [];
  const noCurrentData: PlatformRow[] = [];
  for (const row of SBME_55_PLATFORMS) {
    const ids = (row.sgo_ids || []).map((i) => i.toLowerCase());
    ids.forEach((i) => catalogSgo.add(i));
    if (!ids.length) mappingNeeded.push(row);
    else if (ids.some((i) => observed.has(i))) mapped.push(row);
    else noCurrentData.push(row);
  }
  const sgoUnlisted = [...observed].filter((id) => !catalogSgo.has(id)).sort();
  return {
    mapped,
    mappingNeeded,
    noCurrentData,
    sgoUnlisted,
    counts: {
      total_existing: SBME_55_PLATFORMS.length,
      mapped_to_sgo: mapped.length,
      mapping_needed: mappingNeeded.length,
      no_current_data: noCurrentData.length,
      sgo_unlisted: sgoUnlisted.length,
    },
  };
}

export function catalogHasSgoMapping(row: PlatformRow): boolean {
  return (row.sgo_ids || []).length > 0;
}

export function catalogMappingCounts(): { total: number; mapped: number; mapping_needed: number } {
  let mapped = 0;
  let mapping_needed = 0;
  for (const row of SBME_55_PLATFORMS) {
    if (catalogHasSgoMapping(row)) mapped += 1;
    else mapping_needed += 1;
  }
  return { total: SBME_55_PLATFORMS.length, mapped, mapping_needed };
}

export type DirectoryLane = "mapped" | "mapping_needed" | "no_current_data";

/** Three-way directory status from catalog mapping + currently observed SGO ids. */
export function directoryLane(
  row: PlatformRow,
  classified: ReturnType<typeof classifyPlatforms>,
): DirectoryLane {
  if (!catalogHasSgoMapping(row)) return "mapping_needed";
  if (classified.noCurrentData.some((p) => p.id === row.id)) return "no_current_data";
  return "mapped";
}

export function platformNameForSgoId(sgoId: string): string | null {
  const key = (sgoId || "").toLowerCase();
  const row = SBME_55_PLATFORMS.find((p) => p.sgo_ids.map((i) => i.toLowerCase()).includes(key));
  return row?.name ?? null;
}
