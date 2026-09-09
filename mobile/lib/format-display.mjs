/**
 * Customer-facing time and bookmaker labels.
 * Never invent a sportsbook name for the SGO "unknown" placeholder.
 */

export function formatEventTime(raw) {
  if (raw == null || raw === "") return "";
  const d = new Date(raw);
  if (Number.isNaN(d.getTime())) return String(raw);
  return d.toLocaleString("en-US", {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

export function displayBookmakerName(raw) {
  const name = String(raw || "").trim();
  if (!name || name.toLowerCase() === "unknown") return "";
  return name;
}
