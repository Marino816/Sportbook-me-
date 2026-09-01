/**
 * Optimizer generate-response helpers. Do not invent lineups or truncate
 * a successful multi-lineup payload to the first row.
 */

export function extractOptimizerLineups(res: unknown): unknown[] {
  if (!res || typeof res !== "object") return [];
  const data = (res as Record<string, unknown>).data;
  if (Array.isArray(data)) return data;
  if (data && typeof data === "object") {
    const inner = (data as Record<string, unknown>).lineups;
    if (Array.isArray(inner)) return inner;
  }
  return [];
}

export function optimizerGenerationNote(res: unknown, renderedCount: number): string | null {
  if (!res || typeof res !== "object") return null;
  const data = (res as Record<string, unknown>).data;
  const fromLineup = (row: unknown): string | null => {
    if (!row || typeof row !== "object") return null;
    const w = (row as Record<string, unknown>).generation_warning;
    return typeof w === "string" && w.trim() ? w : null;
  };
  if (data && typeof data === "object" && !Array.isArray(data)) {
    const rec = data as Record<string, unknown>;
    const requested = Number(rec.requested_lineups);
    const generated = Number(rec.generated_lineups);
    if (Number.isFinite(requested) && Number.isFinite(generated) && generated < requested) {
      return `Only ${generated}/${requested} feasible lineups found`;
    }
    const inner = rec.lineups;
    if (Array.isArray(inner) && inner.length) return fromLineup(inner[0]);
  }
  if (Array.isArray(data) && data.length) return fromLineup(data[0]);
  if (renderedCount > 0) return null;
  return null;
}

export function requestedNumLineups(raw: unknown): number {
  const n = Number(raw);
  if (!Number.isFinite(n) || n < 1) return 1;
  return Math.min(150, Math.floor(n));
}
