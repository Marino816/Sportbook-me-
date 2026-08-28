"use client";

import { useMemo, useState } from "react";
import { Building2, Search } from "lucide-react";
import { useEvents } from "@/lib/use-events";
import { formatBookmakerName } from "@/lib/bookmakers";
import {
  classifyPlatforms,
  platformNameForSgoId,
  SBME_55_COUNT,
  SBME_55_PLATFORMS,
} from "@/lib/platforms";
import { filterEventsByStatus, filterMarkets, presentPeriodGroups, type LineMode, type PeriodGroup } from "@/lib/market-view";
import { LeagueChips, LineModeChips, PeriodChips, StatusChips, LastUpdated, FairOddsMark, ConsensusMark } from "@/components/market-controls";
import { gameState, type GameState } from "@/lib/live-scores";
import type { SBEvent, SBMarket } from "@/lib/sbevent";

function fmtOdds(v: number | null | undefined): string {
  if (v == null) return "—";
  return v > 0 ? `+${v}` : `${v}`;
}

function fmtNum(v: number | null | undefined): string {
  if (v == null) return "—";
  return v > 0 ? `+${v}` : `${v}`;
}

type MarketTab = "moneyline" | "spread" | "total" | "player_prop" | "team_prop";

function pickMarket(event: SBEvent, tab: MarketTab, side: string): SBMarket | undefined {
  const types = tab === "total" ? ["total", "over_under"] : [tab];
  return event.markets.find((m) => types.includes(m.bet_type) && (m.side || "") === side);
}

export default function BookmakersPage() {
  const [league, setLeague] = useState("MLB");
  const [status, setStatus] = useState<GameState | "ALL">("ALL");
  const [lineMode, setLineMode] = useState<LineMode>("main");
  const [period, setPeriod] = useState<PeriodGroup | "all">("full");
  const [tab, setTab] = useState<MarketTab>("moneyline");
  const [eventId, setEventId] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [catalogOpen, setCatalogOpen] = useState(false);

  const { events, loading, error, lastFetch } = useEvents(league);

  const visibleEvents = useMemo(() => {
    const byStatus = filterEventsByStatus(events, status);
    if (!search) return byStatus;
    const q = search.toLowerCase();
    return byStatus.filter((e) =>
      `${e.away_team.name} ${e.home_team.name} ${e.away_team.abbreviation} ${e.home_team.abbreviation}`
        .toLowerCase()
        .includes(q),
    );
  }, [events, status, search]);

  const selected = useMemo(
    () => visibleEvents.find((e) => e.id === eventId) ?? visibleEvents[0] ?? null,
    [visibleEvents, eventId],
  );

  const periodOptions = useMemo(
    () => presentPeriodGroups(selected?.markets ?? []),
    [selected],
  );

  const filteredEvent = useMemo(() => {
    if (!selected) return null;
    return {
      ...selected,
      markets: filterMarkets(selected.markets, { lineMode, period }),
    };
  }, [selected, lineMode, period]);

  const observed = useMemo(() => {
    const ids = new Set<string>();
    for (const e of events) {
      for (const b of e.bookmakers || []) if (b) ids.add(b);
      for (const m of e.markets || []) for (const b of m.books || []) if (b.bookmaker) ids.add(b.bookmaker);
    }
    return [...ids];
  }, [events]);

  const classified = useMemo(() => classifyPlatforms(observed), [observed]);

  const compareRows = useMemo(() => {
    if (!filteredEvent) return [];
    const home = pickMarket(filteredEvent, tab, tab === "total" ? "over" : "home");
    const away = pickMarket(filteredEvent, tab, tab === "total" ? "under" : "away");
    const extra = filteredEvent.markets.filter((m) => m.bet_type === tab);
    const books = new Set<string>();
    for (const m of [home, away, ...extra]) {
      if (!m) continue;
      for (const b of m.books) books.add(b.bookmaker);
    }
    const rows = [...books].sort().map((bookmaker) => {
      const hb = home?.books.find((b) => b.bookmaker === bookmaker);
      const ab = away?.books.find((b) => b.bookmaker === bookmaker);
      const available = Boolean(hb?.available || ab?.available);
      let homeVal: number | null = null;
      let awayVal: number | null = null;
      if (tab === "moneyline") {
        homeVal = hb?.moneyline ?? null;
        awayVal = ab?.moneyline ?? null;
      } else if (tab === "spread") {
        homeVal = hb?.spread ?? null;
        awayVal = ab?.spread ?? null;
      } else if (tab === "total") {
        homeVal = hb?.over_under ?? null;
        awayVal = ab?.over_under ?? null;
      } else {
        homeVal = hb?.over_under ?? hb?.moneyline ?? null;
        awayVal = ab?.over_under ?? ab?.moneyline ?? null;
      }
      return {
        bookmaker,
        label: platformNameForSgoId(bookmaker) || formatBookmakerName(bookmaker),
        available,
        homeVal,
        awayVal,
        opening: hb?.opening_odds ?? ab?.opening_odds ?? null,
        closing: hb?.close_odds ?? ab?.close_odds ?? null,
      };
    });
    return rows.filter((r) => r.available && (r.homeVal != null || r.awayVal != null));
  }, [filteredEvent, tab]);

  const fair = filteredEvent
    ? pickMarket(filteredEvent, tab, tab === "total" ? "over" : "home")?.fair_odds ?? null
    : null;
  const consensus = filteredEvent
    ? pickMarket(filteredEvent, tab, tab === "total" ? "over" : "home")?.book_odds ?? null
    : null;
  const isFinal = selected ? gameState(selected) === "FINAL" : false;

  return (
    <div style={{ maxWidth: 1200, margin: "0 auto", padding: "32px 16px 56px" }}>
      <div style={{ display: "flex", alignItems: "center", gap: 14, marginBottom: 20, background: "#0a0f24", borderRadius: 14, border: "1px solid #1e293b", padding: "20px 24px", flexWrap: "wrap" }}>
        <Building2 size={26} color="#c9a84c" />
        <div style={{ flex: 1, minWidth: 200 }}>
          <h1 style={{ fontSize: 24, fontWeight: 900, color: "#c9a84c", margin: 0 }}>Bookmakers</h1>
          <p style={{ fontSize: 13, color: "#94a3b8", margin: "2px 0 0" }}>
            Compare available books on live SportsGameOdds markets. The {SBME_55_COUNT}-platform catalog is a separate SB ME product list — not the same as SGO bookmakers.
          </p>
        </div>
        <LastUpdated fetchedAt={lastFetch ?? undefined} />
      </div>

      <div style={{ display: "flex", flexDirection: "column", gap: 12, marginBottom: 16 }}>
        <LeagueChips value={league} onChange={(id) => { setLeague(id); setEventId(null); }} />
        <StatusChips value={status} onChange={setStatus} />
        <LineModeChips value={lineMode} onChange={setLineMode} />
        {periodOptions.length > 0 && (
          <PeriodChips value={period} options={periodOptions} onChange={setPeriod} />
        )}
      </div>

      <div style={{ position: "relative", marginBottom: 16, maxWidth: 320 }}>
        <Search size={14} style={{ position: "absolute", left: 10, top: "50%", transform: "translateY(-50%)", color: "#64748b" }} />
        <input
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Search events..."
          style={{ width: "100%", padding: "8px 14px 8px 32px", borderRadius: 10, fontSize: 13, background: "#0a0f24", border: "1px solid #1e293b", color: "#f0f6fc", outline: "none", boxSizing: "border-box" }}
        />
      </div>

      {loading && <div style={{ textAlign: "center", padding: 40, color: "#94a3b8" }}>Loading markets…</div>}
      {error && <div style={{ textAlign: "center", padding: 40, color: "#ef4444" }}>{error}</div>}

      <div style={{ display: "flex", gap: 8, overflowX: "auto", marginBottom: 16, paddingBottom: 4 }}>
        {visibleEvents.map((e) => {
          const sel = selected?.id === e.id;
          const st = gameState(e);
          return (
            <button
              key={e.id}
              type="button"
              onClick={() => setEventId(e.id)}
              style={{
                flexShrink: 0,
                padding: "10px 14px",
                borderRadius: 12,
                fontSize: 12,
                fontWeight: 700,
                background: sel ? "rgba(201,168,76,0.1)" : "#0a0f24",
                border: sel ? "1px solid #c9a84c" : "1px solid #1e293b",
                color: sel ? "#c9a84c" : "#f0f6fc",
                cursor: "pointer",
              }}
            >
              {e.away_team.abbreviation} @ {e.home_team.abbreviation}
              <span style={{ display: "block", fontSize: 9, fontWeight: 600, color: st === "LIVE" ? "#ef4444" : "#64748b" }}>{st}</span>
            </button>
          );
        })}
        {!loading && visibleEvents.length === 0 && (
          <div style={{ color: "#64748b", fontSize: 13, padding: 12 }}>No events for this filter.</div>
        )}
      </div>

      {filteredEvent && (
        <div style={{ background: "#0a0f24", borderRadius: 14, border: "1px solid #1e293b", padding: 16, marginBottom: 20 }}>
          <div style={{ display: "flex", justifyContent: "space-between", gap: 12, flexWrap: "wrap", marginBottom: 12 }}>
            <div>
              <div style={{ fontSize: 16, fontWeight: 800, color: "#f0f6fc" }}>
                {filteredEvent.away_team.name} @ {filteredEvent.home_team.name}
              </div>
              {(filteredEvent.home_score != null || filteredEvent.away_score != null) && (
                <div style={{ fontSize: 13, color: "#c9a84c", fontWeight: 700, marginTop: 4 }}>
                  {filteredEvent.away_score ?? 0}–{filteredEvent.home_score ?? 0} · {filteredEvent.status_display || filteredEvent.status}
                </div>
              )}
            </div>
            <div style={{ display: "flex", gap: 12, alignItems: "center", flexWrap: "wrap" }}>
              <FairOddsMark value={fair} />
              <ConsensusMark value={consensus} />
            </div>
          </div>
          {isFinal && (
            <div style={{ fontSize: 12, color: "#f59e0b", marginBottom: 12 }}>
              Finalized event — shown for scores and results, not as a current bettable market.
            </div>
          )}
          <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginBottom: 12 }}>
            {(["moneyline", "spread", "total", "player_prop", "team_prop"] as MarketTab[]).map((t) => (
              <button
                key={t}
                type="button"
                onClick={() => setTab(t)}
                style={{
                  padding: "6px 12px",
                  borderRadius: 8,
                  fontSize: 11,
                  fontWeight: 700,
                  background: tab === t ? "rgba(201,168,76,0.12)" : "transparent",
                  border: tab === t ? "1px solid #c9a84c" : "1px solid #1e293b",
                  color: tab === t ? "#c9a84c" : "#94a3b8",
                  cursor: "pointer",
                }}
              >
                {t === "player_prop" ? "Player Props" : t === "team_prop" ? "Team Props" : t === "moneyline" ? "Moneyline" : t === "spread" ? "Spread" : "Total"}
              </button>
            ))}
          </div>

          {compareRows.length === 0 ? (
            <div style={{ textAlign: "center", padding: 28, color: "#64748b", fontSize: 13 }}>
              No bookmaker returned this market for the selected event and filters. Missing books are not filled in.
            </div>
          ) : (
            <div style={{ overflowX: "auto" }}>
              <div style={{ display: "grid", gridTemplateColumns: "minmax(140px,1.4fr) 1fr 1fr 1fr 1fr", gap: 6, minWidth: 560, fontSize: 10, fontWeight: 700, color: "#64748b", textTransform: "uppercase", paddingBottom: 8, borderBottom: "1px solid #1e293b" }}>
                <span>Book</span>
                <span style={{ textAlign: "center" }}>{tab === "total" ? "Over" : filteredEvent.home_team.abbreviation}</span>
                <span style={{ textAlign: "center" }}>{tab === "total" ? "Under" : filteredEvent.away_team.abbreviation}</span>
                <span style={{ textAlign: "center" }}>Open</span>
                <span style={{ textAlign: "center" }}>Close</span>
              </div>
              {compareRows.map((r) => (
                <div key={r.bookmaker} style={{ display: "grid", gridTemplateColumns: "minmax(140px,1.4fr) 1fr 1fr 1fr 1fr", gap: 6, minWidth: 560, padding: "10px 0", borderBottom: "1px solid rgba(30,41,59,0.5)", fontSize: 13, color: "#f0f6fc" }}>
                  <span style={{ fontWeight: 700 }}>{r.label}</span>
                  <span style={{ textAlign: "center", color: "#c9a84c", fontWeight: 700 }}>{tab === "spread" || tab === "total" ? fmtNum(r.homeVal) : fmtOdds(r.homeVal)}</span>
                  <span style={{ textAlign: "center", color: "#c9a84c", fontWeight: 700 }}>{tab === "spread" || tab === "total" ? fmtNum(r.awayVal) : fmtOdds(r.awayVal)}</span>
                  <span style={{ textAlign: "center", color: "#94a3b8" }}>{fmtOdds(r.opening)}</span>
                  <span style={{ textAlign: "center", color: "#94a3b8" }}>{fmtOdds(r.closing)}</span>
                </div>
              ))}
            </div>
          )}
          <p style={{ fontSize: 11, color: "#64748b", marginTop: 12 }}>
            Bookmaker Price is the sportsbook line. Fair Odds and Consensus appear only when SportsGameOdds returned fairOdds / bookOdds. SB ME does not accept or place wagers.
          </p>
        </div>
      )}

      <div style={{ background: "#0a0f24", borderRadius: 14, border: "1px solid #1e293b", padding: 16 }}>
        <button type="button" onClick={() => setCatalogOpen((v) => !v)} style={{ background: "none", border: "none", color: "#c9a84c", fontWeight: 800, fontSize: 14, cursor: "pointer", padding: 0 }}>
          {SBME_55_COUNT} Platforms {catalogOpen ? "▲" : "▼"}
        </button>
        <p style={{ fontSize: 12, color: "#94a3b8", margin: "8px 0 0" }}>
          {classified.counts.mapped_to_sgo} currently mapped to live SGO books · {classified.counts.no_current_data} mapped but no current line · {classified.counts.mapping_needed} mapping needed · {classified.counts.sgo_unlisted} SGO books not in the 55 catalog
        </p>
        {catalogOpen && (
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(160px, 1fr))", gap: 8, marginTop: 14 }}>
            {SBME_55_PLATFORMS.map((p) => {
              const mapped = classified.mapped.some((m) => m.id === p.id);
              const needed = classified.mappingNeeded.some((m) => m.id === p.id);
              return (
                <div key={p.id} style={{ padding: "10px 12px", borderRadius: 10, border: "1px solid #1e293b", background: "rgba(255,255,255,0.02)" }}>
                  <div style={{ fontSize: 12, fontWeight: 700, color: "#f0f6fc" }}>{p.name}</div>
                  <div style={{ fontSize: 10, color: mapped ? "#4ade80" : needed ? "#f59e0b" : "#64748b", marginTop: 4 }}>
                    {mapped ? "Line available" : needed ? "Mapping needed" : "No current market"}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
