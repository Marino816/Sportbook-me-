import type { SBEvent } from "@/lib/sbevent";

export const SCHEDULE_INTEL_NOTE =
  "Schedule intelligence — DFS contest availability is tracked separately.";

function isFinalEventStatus(status: string | undefined | null): boolean {
  return /final|complete|closed|cancel|postpon/i.test(status || "");
}

function teamLabel(team: { abbreviation?: string; name?: string } | null | undefined): string {
  return (team?.abbreviation || team?.name || "").trim();
}

/** Informational SGO schedule only — never a DFS contest slate. */
export function upcomingScheduleEvents(events: SBEvent[]): SBEvent[] {
  const now = Date.now();
  return events
    .filter((e) => {
      if (!e.start_time || !teamLabel(e.away_team) || !teamLabel(e.home_team)) return false;
      if (isFinalEventStatus(e.status) || isFinalEventStatus(e.status_display)) return false;
      const ts = Date.parse(e.start_time);
      if (!Number.isFinite(ts)) return false;
      return ts >= now - 4 * 60 * 60 * 1000;
    })
    .sort((a, b) => Date.parse(a.start_time || "") - Date.parse(b.start_time || ""));
}

export function formatKickoffEt(startTime: string | null | undefined): string {
  if (!startTime) return "";
  const d = new Date(startTime);
  if (Number.isNaN(d.getTime())) return "";
  const datePart = d.toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    timeZone: "America/New_York",
  }).toUpperCase();
  const timePart = d.toLocaleTimeString("en-US", {
    hour: "numeric",
    minute: "2-digit",
    timeZone: "America/New_York",
  });
  return `${datePart} · ${timePart} ET`;
}

export function scheduleMatchupLabel(event: SBEvent): string {
  return `${teamLabel(event.away_team)} @ ${teamLabel(event.home_team)}`;
}

export function eventsWithMarketContext(events: SBEvent[]): SBEvent[] {
  return events.filter((e) => (e.markets?.length || 0) > 0 || (e.bookmakers?.length || 0) > 0);
}
