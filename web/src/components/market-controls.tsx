"use client";

import { ROOKIE_LEAGUES, leagueLabel } from "@/lib/sgo-leagues";
import type { LineMode, PeriodGroup } from "@/lib/market-view";
import { formatFreshness, periodLabelForId } from "@/lib/market-view";
import type { GameState } from "@/lib/live-scores";

const muted = "#94a3b8";
const card = "#0a0f24";
const gold = "#c9a84c";
const border = "#1e293b";

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
  grouped = false,
}: {
  value: string;
  onChange: (id: string) => void;
  grouped?: boolean;
}) {
  const soccer = ROOKIE_LEAGUES.filter((lg) => lg.sportID === "SOCCER");
  const rest = ROOKIE_LEAGUES.filter((lg) => lg.sportID !== "SOCCER");

  const render = (list: typeof ROOKIE_LEAGUES[number][]) =>
    list.map((lg) => (
      <button
        key={lg.leagueID}
        type="button"
        onClick={() => onChange(lg.leagueID)}
        className={`sbme-chip${value === lg.leagueID ? " is-on" : ""}`}
      >
        {lg.label}
      </button>
    ));

  if (!grouped) {
    return <div className="sbme-chips">{render([...ROOKIE_LEAGUES])}</div>;
  }

  return (
    <div>
      <div className="sbme-chips">{render(rest)}</div>
      <div className="sbme-chips sbme-chips--soccer">
        <span className="sbme-chips-label">Soccer</span>
        {render(soccer)}
      </div>
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
    <div className="sbme-seg">
      {opts.map((s) => (
        <button
          key={s}
          type="button"
          onClick={() => onChange(s)}
          className={`sbme-seg-btn${value === s ? " is-on" : ""}${s === "LIVE" ? " is-live" : ""}`}
        >
          {s === "LIVE" && <span className="sbme-live-dot" />}
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
    <div className="sbme-chips">
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
    <div className="sbme-chips">
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
  if (value == null) return <span className="sbme-stat is-off">Fair unavailable</span>;
  const txt = value > 0 ? `+${value}` : `${value}`;
  return (
    <span className="sbme-stat is-gold" title="SportsGameOdds Fair Odds">
      Fair <strong>{txt}</strong>
    </span>
  );
}

export function ConsensusMark({ value }: { value: number | null | undefined }) {
  if (value == null) return <span className="sbme-stat is-off">Consensus unavailable</span>;
  const txt = value > 0 ? `+${value}` : `${value}`;
  return (
    <span className="sbme-stat is-blue" title="SportsGameOdds bookOdds consensus">
      Consensus <strong>{txt}</strong>
    </span>
  );
}

export function TwoPagePager({
  page,
  pages,
  total,
  pageSize,
  onChange,
}: {
  page: number;
  pages: number;
  total: number;
  pageSize: number;
  onChange: (page: number) => void;
}) {
  if (total === 0) return null;
  return (
    <div className="sbme-pager" role="navigation" aria-label="Results pages">
      <span className="sbme-pager-meta">
        {total} result{total === 1 ? "" : "s"} · {pageSize}/page
      </span>
      <div className="sbme-pager-btns">
        <button type="button" className="sbme-pager-btn" disabled={page <= 1} onClick={() => onChange(1)}>
          Page 1
        </button>
        {pages > 1 && (
          <button type="button" className="sbme-pager-btn" disabled={page >= 2} onClick={() => onChange(2)}>
            Page 2
          </button>
        )}
      </div>
      <span className="sbme-pager-page">Showing page {page} of {pages}</span>
    </div>
  );
}

export { leagueLabel };
