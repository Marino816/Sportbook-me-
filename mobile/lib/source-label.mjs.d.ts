export function formatSourceLabel(
  raw?: unknown,
  slateSource?: unknown,
  freshness?: unknown,
): { label: string; isDemo: boolean };

export function formatProjectionSource(
  raw?: unknown,
): { label: string; isFallback: boolean; isUnavailable: boolean };

export function lineupProjectionIntegrity(lineup?: {
  players?: Array<{
    projected_fp?: number;
    projection_source?: string;
    mapping_status?: string;
  }>;
  projected_score?: number;
}): {
  playerSum: number | null;
  displayed: number | null;
  totalsMatch: boolean;
  fallbackCount: number;
  unmatchedCount: number;
  mixed: boolean;
  contestReady: boolean;
};
