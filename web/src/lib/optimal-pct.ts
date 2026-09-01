/**
 * Map GET /api/optimal-pct cached simulation results onto Optimizer rows.
 * Values come only from the Optimal% sim payload — never OWN%, leverage, or projections.
 */

const JOB_STATUSES = new Set([
  "NOT_RUN",
  "QUEUED",
  "RUNNING",
  "COMPLETE",
  "FAILED",
  "LOCKED",
  "UNKNOWN",
]);

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

type OptPctEnvelope = {
  status?: string;
  data?: {
    status?: string;
    result?: { players?: OptimalPctPlayer[] | null } | null;
    data?: {
      status?: string;
      result?: { players?: OptimalPctPlayer[] | null } | null;
    } | null;
  } | null;
} | null;

function readJobStatus(res: OptPctEnvelope): string {
  const candidates = [res?.data?.status, res?.data?.data?.status];
  for (const raw of candidates) {
    if (typeof raw !== "string") continue;
    const up = raw.trim().toUpperCase();
    if (JOB_STATUSES.has(up)) return up;
  }
  return "NOT_RUN";
}

function readPlayers(res: OptPctEnvelope): OptimalPctPlayer[] | null {
  const a = res?.data?.result?.players;
  const b = res?.data?.data?.result?.players;
  if (Array.isArray(a)) return a;
  if (Array.isArray(b)) return b;
  return null;
}

export function mapOptimalPctResponse(
  res: OptPctEnvelope,
): { status: string; map: Record<string, number> } {
  const players = readPlayers(res);
  let status = readJobStatus(res);
  // A payload that already includes sim players is COMPLETE. Never leave the
  // table on Calculating… just because the status field was nested or stale.
  if (status !== "LOCKED" && Array.isArray(players) && players.length > 0) {
    status = "COMPLETE";
  }
  if (status !== "COMPLETE") return { status, map: {} };
  return { status, map: mapOptimalPctPlayers(players) };
}

/** OPT% cell copy. Calculating… only while the current slate job is queued/running. */
export function formatOptPctCell(
  optPct: number | null | undefined,
  status: string,
): string {
  if (optPct != null && Number.isFinite(Number(optPct))) {
    return `${Number(optPct).toFixed(1)}%`;
  }
  const s = (status || "").trim().toUpperCase();
  if (s === "QUEUED" || s === "RUNNING") return "Calculating…";
  return "—";
}
