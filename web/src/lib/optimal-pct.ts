/**
 * Map GET /api/optimal-pct cached simulation results onto Optimizer rows.
 * Values come only from the Optimal% sim payload — never OWN%, leverage, or projections.
 */

export function normalizeOptName(n: string): string {
  return (n || "")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .replace(/[^a-z0-9]/g, "")
    .trim();
}

export type OptimalPctPlayer = {
  player_id?: string | number | null;
  name?: string | null;
  optimal_pct?: number | null;
};

export function mapOptimalPctPlayers(
  players: OptimalPctPlayer[] | null | undefined,
): Record<string, number> {
  const m: Record<string, number> = {};
  for (const p of players || []) {
    if (p == null || p.optimal_pct == null) continue;
    const val = Number(p.optimal_pct);
    if (!Number.isFinite(val)) continue;
    const nm = normalizeOptName(p.name || "");
    if (nm) m[nm] = val;
    if (p.player_id != null && String(p.player_id)) m[String(p.player_id)] = val;
  }
  return m;
}

export function lookupOptimalPct(
  map: Record<string, number>,
  namesOrIds: Array<string | number | null | undefined>,
): number | null {
  for (const key of namesOrIds) {
    if (key == null || key === "") continue;
    const raw = map[String(key)];
    if (raw != null) return raw;
    const byName = map[normalizeOptName(String(key))];
    if (byName != null) return byName;
  }
  return null;
}

export function mapOptimalPctResponse(res: {
  data?: {
    status?: string;
    result?: { players?: OptimalPctPlayer[] | null } | null;
  } | null;
} | null): { status: string; map: Record<string, number> } {
  const status = res?.data?.status ?? "NOT_RUN";
  if (status !== "COMPLETE") return { status, map: {} };
  return { status, map: mapOptimalPctPlayers(res?.data?.result?.players) };
}
