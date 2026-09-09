/**
 * Client-side parlay identity — duplicates and opposing same-market outcomes.
 */

export function legIdentity(eventId, market, selection) {
  return `${String(eventId || "").trim()}::${String(market || "").trim().toLowerCase()}::${String(selection || "").trim().toLowerCase()}`;
}

export function hasDuplicateLeg(legs, eventId, market, selection) {
  const key = legIdentity(eventId, market, selection);
  return (legs || []).some((leg) => legIdentity(leg.eventId, leg.market, leg.selection) === key);
}

export function hasConflictingLeg(legs, eventId, market, selection) {
  const event = String(eventId || "").trim();
  const mkt = String(market || "").trim().toLowerCase();
  const sel = String(selection || "").trim().toLowerCase();
  if (!event || !sel) return false;
  return (legs || []).some((leg) => {
    if (String(leg.eventId || "").trim() !== event) return false;
    if (String(leg.market || "").trim().toLowerCase() !== mkt) return false;
    return String(leg.selection || "").trim().toLowerCase() !== sel;
  });
}

export function uniqueValidLegs(legs) {
  const seen = new Set();
  const marketPick = new Map();
  const out = [];
  for (const leg of legs || []) {
    const event = String(leg.eventId || "").trim();
    const market = String(leg.market || "").trim().toLowerCase();
    const selection = String(leg.selection || "").trim().toLowerCase();
    const key = legIdentity(event, market, selection);
    if (!event || !selection || seen.has(key)) continue;
    const mk = `${event}::${market}`;
    if (marketPick.has(mk) && marketPick.get(mk) !== selection) continue;
    seen.add(key);
    marketPick.set(mk, selection);
    out.push(leg);
  }
  return out;
}
