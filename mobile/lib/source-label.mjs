/**
 * Customer-facing DFS source labels.
 * Stored CSV / BCDFS data is not a live contest-salary feed.
 */

export function formatSourceLabel(raw, slateSource, freshness) {
  const value = String(raw || slateSource || "").trim().toLowerCase();
  const fresh = String(freshness || "").trim();
  const withFresh = (label) => (fresh ? `${label} · ${fresh}` : label);
  if (!value) return { label: withFresh("Source not reported"), isDemo: false };
  if (value === "demo" || value === "sample") {
    return { label: withFresh("Demo slate — not live contest data"), isDemo: true };
  }
  if (value === "native" || value === "bcdfs" || value === "blue_collar") {
    return { label: withFresh("Stored contest salaries"), isDemo: false };
  }
  if (value.includes("draftkings") || value.includes("fanduel")) {
    return { label: withFresh("Stored contest salaries"), isDemo: false };
  }
  return { label: withFresh(String(raw || slateSource)), isDemo: false };
}

const PROJECTION_SOURCE_LABELS = {
  sgo_fantasy_market: "SGO fantasy market",
  prop_based: "Pitcher props",
  bc_proj_fallback: "Blue Collar fallback",
  consensus: "Consensus sources",
  consensus_capped: "Consensus (capped)",
  unavailable: "Projection unavailable",
  my_proj: "My projection",
};

export function formatProjectionSource(raw) {
  const value = String(raw || "").trim().toLowerCase();
  if (!value) return { label: "Source not reported", isFallback: false, isUnavailable: true };
  const label = PROJECTION_SOURCE_LABELS[value] || String(raw);
  return {
    label,
    isFallback: value === "bc_proj_fallback" || value === "prop_based",
    isUnavailable: value === "unavailable",
  };
}

export function roundPoints(n) {
  const v = Number(n);
  if (Number.isNaN(v)) return null;
  return Math.round(v * 10) / 10;
}

export function sumProjectedFp(players) {
  return (players || []).reduce((acc, p) => acc + Number(p?.projected_fp || 0), 0);
}

export function lineupProjectionIntegrity(lineup) {
  const players = lineup?.players || [];
  const sum = roundPoints(sumProjectedFp(players));
  const displayed = roundPoints(lineup?.projected_score);
  const sources = players.map((p) => String(p?.projection_source || "").toUpperCase());
  const fallbackCount = sources.filter((s) => s === "BC_PROJ_FALLBACK" || s === "PROP_BASED").length;
  const unmatchedCount = players.filter(
    (p) => String(p?.mapping_status || "").toUpperCase() === "UNMATCHED",
  ).length;
  const mixed = new Set(sources.filter(Boolean)).size > 1;
  return {
    playerSum: sum,
    displayed,
    totalsMatch: sum != null && displayed != null && sum === displayed,
    fallbackCount,
    unmatchedCount,
    mixed,
    contestReady: false,
  };
}
