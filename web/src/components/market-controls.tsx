"use client";

import { ROOKIE_LEAGUES, leagueLabel } from "@/lib/sgo-leagues";
import type { LineMode, PeriodGroup } from "@/lib/market-view";
import { formatFreshness, periodLabelForId } from "@/lib/market-view";
import type { GameState } from "@/lib/live-scores";

const gold = "#c9a84c";
const border = "#1e293b";
const muted = "#94a3b8";
const card = "#0a0f24";

const chip = (active: boolean): React.CSSProperties => ({
  padding: "6px 12px",
  borderRadius: 8,
  fontSize: 11,
  fontWeight: 700,
  cursor: "pointer",
  background: active ? "rgba(201,168,76,0.12)" : card,
  border: active ? `1px solid ${gold}` : `1px solid ${border}`,
  color: active ? gold : muted,
  whiteSpace: "nowrap" as const,
});

export function LeagueChips({
  value,
  onChange,
}: {
  value: string;
  onChange: (id: string) => void;
}) {
  return (
    <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
      {ROOKIE_LEAGUES.map((lg) => (
        <button key={lg.leagueID} type="button" onClick={() => onChange(lg.leagueID)} style={chip(value === lg.leagueID)}>
          {lg.label}
        </button>
      ))}
    </div>
  );
}

export function StatusChips({
  value,
  onChange,
}: {
  value: GameState | "ALL";
  onChange: (v: GameState | "ALL") => void;
}) {
  const opts: Array<GameState | "ALL"> = ["ALL", "LIVE", "UPCOMING", "FINAL"];
  const labels: Record<string, string> = { ALL: "All", LIVE: "Live", UPCOMING: "Upcoming", FINAL: "Final" };
  return (
    <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
      {opts.map((s) => (
        <button key={s} type="button" onClick={() => onChange(s)} style={chip(value === s)}>
          {labels[s]}
        </button>
      ))}
    </div>
  );
}

export function LineModeChips({
  value,
  onChange,
}: {
  value: LineMode;
  onChange: (v: LineMode) => void;
}) {
  const opts: Array<{ id: LineMode; label: string }> = [
    { id: "main", label: "Main Lines" },
    { id: "alt", label: "Alternate Lines" },
    { id: "all", label: "All Lines" },
  ];
  return (
    <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
      {opts.map((o) => (
        <button key={o.id} type="button" onClick={() => onChange(o.id)} style={chip(value === o.id)}>
          {o.label}
        </button>
      ))}
    </div>
  );
}

export function PeriodChips({
  value,
  options,
  onChange,
}: {
  value: PeriodGroup | "all";
  options: PeriodGroup[];
  onChange: (v: PeriodGroup | "all") => void;
}) {
  const shown: Array<PeriodGroup | "all"> = ["all", ...options];
  return (
    <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
      {shown.map((p) => (
        <button key={p} type="button" onClick={() => onChange(p)} style={chip(value === p)}>
          {p === "all" ? "All Periods" : periodLabelForId(p === "full" ? "game" : p)}
        </button>
      ))}
    </div>
  );
}

export function LastUpdated({ iso, fetchedAt }: { iso?: string | null; fetchedAt?: number }) {
  const label = formatFreshness(iso, fetchedAt);
  if (!label) return null;
  return (
    <span style={{ fontSize: 11, color: muted }}>
      Last updated: {label}
    </span>
  );
}

export function FairOddsMark({ value }: { value: number | null | undefined }) {
  if (value == null) return <span style={{ color: "#64748b", fontSize: 11 }}>Fair unavailable</span>;
  const txt = value > 0 ? `+${value}` : `${value}`;
  return (
    <span style={{ fontSize: 11, color: gold, fontWeight: 700 }} title="SportsGameOdds Fair Odds">
      Fair {txt}
    </span>
  );
}

export function ConsensusMark({ value }: { value: number | null | undefined }) {
  if (value == null) return <span style={{ color: "#64748b", fontSize: 11 }}>Consensus unavailable</span>;
  const txt = value > 0 ? `+${value}` : `${value}`;
  return (
    <span style={{ fontSize: 11, color: "#93c5fd", fontWeight: 700 }} title="SportsGameOdds bookOdds consensus">
      Consensus {txt}
    </span>
  );
}

export { leagueLabel };
