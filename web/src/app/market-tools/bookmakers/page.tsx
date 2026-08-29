"use client";

import { useMemo, useState, useEffect } from "react";
import Link from "next/link";
import { Building2, Search, ChevronDown } from "lucide-react";
import { useEvents } from "@/lib/use-events";
import { formatBookmakerName } from "@/lib/bookmakers";
import {
  catalogHasSgoMapping,
  catalogMappingCounts,
  classifyPlatforms,
  directoryLane,
  platformNameForSgoId,
  SBME_55_COUNT,
  SBME_55_PLATFORMS,
  type DirectoryLane,
} from "@/lib/platforms";
import { filterEventsByStatus, filterMarkets, presentPeriodGroups, twoPageWindow, type LineMode, type PeriodGroup } from "@/lib/market-view";
import { LeagueChips, LineModeChips, PeriodChips, StatusChips, LastUpdated, FairOddsMark, ConsensusMark, TwoPagePager } from "@/components/market-controls";
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
type CatalogFilter = "all" | DirectoryLane;

function pickMarket(event: SBEvent, tab: MarketTab, side: string): SBMarket | undefined {
  const types = tab === "total" ? ["total", "over_under"] : [tab];
  return event.markets.find((m) => types.includes(m.bet_type) && (m.side || "") === side);
}

type CardLane = DirectoryLane | "pending";

function laneLabel(lane: CardLane): string {
  if (lane === "mapping_needed") return "Mapping Needed";
  if (lane === "no_current_data") return "No Current Data";
  if (lane === "pending") return "Awaiting Markets";
  return "Mapped";
}

export default function BookmakersPage() {
  const [league, setLeague] = useState("MLB");
  const [status, setStatus] = useState<GameState | "ALL">("ALL");
  const [lineMode, setLineMode] = useState<LineMode>("main");
  const [period, setPeriod] = useState<PeriodGroup | "all">("full");
  const [tab, setTab] = useState<MarketTab>("moneyline");
  const [eventId, setEventId] = useState<string | null>(null);
  const [eventQuery, setEventQuery] = useState("");
  const [catalogQuery, setCatalogQuery] = useState("");
  const [catalogFilter, setCatalogFilter] = useState<CatalogFilter>("all");
  const [catalogPage, setCatalogPage] = useState(1);
  const [marketsOpen, setMarketsOpen] = useState(false);

  const { events, loading, error, lastFetch } = useEvents(league);
  const mappingCounts = catalogMappingCounts();

  const visibleEvents = useMemo(() => {
    const byStatus = filterEventsByStatus(events, status);
    if (!eventQuery) return byStatus;
    const q = eventQuery.toLowerCase();
    return byStatus.filter((e) =>
      `${e.away_team.name} ${e.home_team.name} ${e.away_team.abbreviation} ${e.home_team.abbreviation}`
        .toLowerCase()
        .includes(q),
    );
  }, [events, status, eventQuery]);

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
  const dataReady = !loading && !error;

  const directory = useMemo(() => {
    const q = catalogQuery.trim().toLowerCase();
    return SBME_55_PLATFORMS.filter((p) => {
      if (catalogFilter === "mapping_needed" && catalogHasSgoMapping(p)) return false;
      if (catalogFilter === "mapped") {
        if (!dataReady || directoryLane(p, classified) !== "mapped") return false;
      }
      if (catalogFilter === "no_current_data") {
        if (!dataReady || directoryLane(p, classified) !== "no_current_data") return false;
      }
      if (!q) return true;
      const ids = (p.sgo_ids || []).join(" ").toLowerCase();
      return p.name.toLowerCase().includes(q) || p.id.toLowerCase().includes(q) || ids.includes(q);
    });
  }, [catalogFilter, catalogQuery, classified, dataReady]);

  useEffect(() => {
    setCatalogPage(1);
  }, [catalogQuery, catalogFilter]);

  const catalogWindow = useMemo(
    () => twoPageWindow(directory, catalogPage, 12, { allowDense: true }),
    [directory, catalogPage],
  );

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

  const FILTERS: { id: CatalogFilter; label: string }[] = [
    { id: "all", label: "All" },
    { id: "mapped", label: "Mapped" },
    { id: "mapping_needed", label: "Mapping Needed" },
    { id: "no_current_data", label: "No Current Data" },
  ];

  return (
    <div className="sbme-books">
      <header className="sbme-books-head">
        <span className="sbme-books-icon" aria-hidden>
          <Building2 size={20} />
        </span>
        <div>
          <p className="sbme-books-kicker">{mappingCounts.total} PLATFORM CATALOG</p>
          <h1>Bookmakers</h1>
          <p>
            SB ME supported platform catalog and available SportsGameOdds market-data mappings.
            Catalog membership is not live-odds coverage. SB ME does not accept or place wagers.
          </p>
        </div>
      </header>

      <section className="sbme-books-stats" aria-label="Catalog summary">
        <div className="sbme-books-stat">
          <span className="sbme-books-stat-n">{mappingCounts.total}</span>
          <span className="sbme-books-stat-l">Platform Catalog</span>
        </div>
        <div className="sbme-books-stat">
          <span className="sbme-books-stat-n">{dataReady ? classified.counts.mapped_to_sgo : "—"}</span>
          <span className="sbme-books-stat-l">Mapped</span>
        </div>
        <div className="sbme-books-stat">
          <span className="sbme-books-stat-n">{classified.counts.mapping_needed}</span>
          <span className="sbme-books-stat-l">Mapping Needed</span>
        </div>
        <div className="sbme-books-stat">
          <span className="sbme-books-stat-n">{dataReady ? classified.counts.no_current_data : "—"}</span>
          <span className="sbme-books-stat-l">No Current Data</span>
        </div>
      </section>
      <p className="sbme-books-note">
        Mapped is a catalog row whose SGO id appears in this league's loaded events — not a live-odds guarantee.
        Mapping Needed is a catalog row with no SGO id. No Current Data is a catalog row with an SGO mapping
        whose ids are not in this loaded view.
        {classified.counts.sgo_unlisted > 0
          ? ` ${classified.counts.sgo_unlisted} observed SGO book${classified.counts.sgo_unlisted === 1 ? "" : "s"} ${classified.counts.sgo_unlisted === 1 ? "is" : "are"} not in the ${SBME_55_COUNT}-platform catalog.`
          : ""}
      </p>

      <section className="sbme-books-directory" aria-label="Platform directory">
        <div className="sbme-books-toolbar">
          <div className="sbme-books-filters" aria-label="Catalog status">
            {FILTERS.map((f) => (
              <button
                key={f.id}
                type="button"
                aria-pressed={catalogFilter === f.id}
                className={`sbme-books-filter${catalogFilter === f.id ? " is-on" : ""}`}
                onClick={() => setCatalogFilter(f.id)}
              >
                {f.label}
              </button>
            ))}
          </div>
          <label className="sbme-books-search">
            <Search size={14} aria-hidden />
            <input
              value={catalogQuery}
              onChange={(e) => setCatalogQuery(e.target.value)}
              placeholder="Search platforms…"
              aria-label="Search platforms"
            />
          </label>
        </div>
        <p className="sbme-books-shown">
          Showing {catalogWindow.total} of {mappingCounts.total}
        </p>
        {directory.length === 0 ? (
          <div className="sbme-books-empty">
            {!dataReady && (catalogFilter === "mapped" || catalogFilter === "no_current_data")
              ? "Current-data filters apply after this league's markets load."
              : "No platforms in the loaded catalog match this filter or search."}
          </div>
        ) : (
          <>
          <div className="sbme-books-grid">
            {catalogWindow.items.map((p) => {
              const ids = (p.sgo_ids || []).filter(Boolean);
              const lane: CardLane = !catalogHasSgoMapping(p)
                ? "mapping_needed"
                : dataReady
                  ? directoryLane(p, classified)
                  : "pending";
              return (
                <article key={p.id} className={`sbme-books-card sbme-books-card--${lane.replace(/_/g, "-")}`}>
                  <div className="sbme-books-card-top">
                    <h2>{p.name}</h2>
                    <span className={`sbme-books-pill sbme-books-pill--${lane.replace(/_/g, "-")}`}>
                      {laneLabel(lane)}
                    </span>
                  </div>
                  <p className="sbme-books-ids">
                    {ids.length ? `SGO id${ids.length === 1 ? "" : "s"}: ${ids.join(", ")}` : "No SGO id mapped"}
                  </p>
                  {lane === "mapping_needed" && (
                    <p className="sbme-books-card-note">
                      In the SB ME catalog. Current canonical market data is not available — no SportsGameOdds id is mapped.
                    </p>
                  )}
                  {lane === "pending" && (
                    <p className="sbme-books-card-note">
                      In the SB ME catalog with an SGO mapping. Current-data state appears when this league's markets load.
                    </p>
                  )}
                  {lane === "no_current_data" && (
                    <p className="sbme-books-card-note">
                      In the SB ME catalog with an SGO mapping. Current canonical market data is not available in this loaded view.
                    </p>
                  )}
                  {lane === "mapped" && (
                    <p className="sbme-books-card-note">
                      Catalog mapping present. This platform's SGO id appears in this league's loaded events — not a live-odds claim.
                    </p>
                  )}
                </article>
              );
            })}
          </div>
          <TwoPagePager
            page={catalogWindow.page}
            pages={catalogWindow.pages}
            total={catalogWindow.total}
            pageSize={catalogWindow.pageSize}
            onChange={setCatalogPage}
          />
          </>
        )}
      </section>

      <section className="sbme-books-markets sbme-books-markets--compact">
        <div className="sbme-books-markets-head">
          <div>
            <p className="sbme-books-kicker">LOADED MARKETS</p>
            <h2>Live Odds workspace</h2>
            <p>
              {dataReady
                ? `${events.length} ${league} event${events.length === 1 ? "" : "s"} loaded · ${classified.counts.mapped_to_sgo} catalog books observed in this view.`
                : "Market coverage for this league loads with Live Odds."}
              {" "}Book comparison lives on Live Odds so this page stays a platform directory.
            </p>
          </div>
          <LastUpdated fetchedAt={lastFetch ?? undefined} />
        </div>
        <div className="sbme-books-cta-row">
          <Link href="/market-tools/live-odds" className="sbme-books-cta">
            Open Live Odds
          </Link>
          <button
            type="button"
            className="sbme-books-toggle"
            aria-expanded={marketsOpen}
            onClick={() => setMarketsOpen((v) => !v)}
          >
            <ChevronDown size={14} style={{ transform: marketsOpen ? "rotate(180deg)" : undefined }} />
            {marketsOpen ? "Hide compact comparison" : "Compare one loaded event"}
          </button>
        </div>
        {marketsOpen && (
          <div className="sbme-books-compact-compare">

        <div className="sbme-books-controls">
          <LeagueChips value={league} onChange={(id) => { setLeague(id); setEventId(null); }} />
          <StatusChips value={status} onChange={setStatus} />
          <LineModeChips value={lineMode} onChange={setLineMode} />
          {periodOptions.length > 0 && (
            <PeriodChips value={period} options={periodOptions} onChange={setPeriod} />
          )}
        </div>

        <label className="sbme-books-search sbme-books-search--events">
          <Search size={14} aria-hidden />
          <input
            value={eventQuery}
            onChange={(e) => setEventQuery(e.target.value)}
            placeholder="Search events…"
            aria-label="Search events"
          />
        </label>

        {loading && <div className="sbme-books-empty">Loading markets…</div>}
        {error && <div className="sbme-books-empty sbme-books-empty--err">{error}</div>}

        <div className="sbme-books-events">
          {visibleEvents.map((e) => {
            const sel = selected?.id === e.id;
            const st = gameState(e);
            return (
              <button
                key={e.id}
                type="button"
                onClick={() => setEventId(e.id)}
                className={`sbme-books-event${sel ? " is-on" : ""}`}
              >
                {e.away_team.abbreviation} @ {e.home_team.abbreviation}
                <span className={st === "LIVE" ? "is-live" : undefined}>{st}</span>
              </button>
            );
          })}
          {!loading && visibleEvents.length === 0 && (
            <div className="sbme-books-empty">No events for this filter.</div>
          )}
        </div>

        {filteredEvent && (
          <div className="sbme-books-board">
            <div className="sbme-books-board-top">
              <div>
                <div className="sbme-books-matchup">
                  {filteredEvent.away_team.name} @ {filteredEvent.home_team.name}
                </div>
                {(filteredEvent.home_score != null || filteredEvent.away_score != null) && (
                  <div className="sbme-books-score">
                    {filteredEvent.away_score ?? 0}–{filteredEvent.home_score ?? 0}
                    {(filteredEvent.status_display || filteredEvent.status)
                      ? ` · ${filteredEvent.status_display || filteredEvent.status}`
                      : ""}
                  </div>
                )}
              </div>
              <div className="sbme-books-marks">
                <FairOddsMark value={fair} />
                <ConsensusMark value={consensus} />
              </div>
            </div>
            {isFinal && (
              <div className="sbme-books-final">
                Finalized event — shown for scores and results, not as a current bettable market.
              </div>
            )}
            <div className="sbme-books-tabs">
              {(["moneyline", "spread", "total", "player_prop", "team_prop"] as MarketTab[]).map((t) => (
                <button
                  key={t}
                  type="button"
                  onClick={() => setTab(t)}
                  className={`sbme-chip${tab === t ? " is-on" : ""}`}
                >
                  {t === "player_prop" ? "Player Props" : t === "team_prop" ? "Team Props" : t === "moneyline" ? "Moneyline" : t === "spread" ? "Spread" : "Total"}
                </button>
              ))}
            </div>

            {compareRows.length === 0 ? (
              <div className="sbme-books-empty">
                No bookmaker returned this market for the selected event and filters. Missing books are not filled in.
              </div>
            ) : (
              <div className="sbme-books-table-wrap">
                <div className="sbme-books-table sbme-books-table--head">
                  <span>Book</span>
                  <span>{tab === "total" ? "Over" : filteredEvent.home_team.abbreviation}</span>
                  <span>{tab === "total" ? "Under" : filteredEvent.away_team.abbreviation}</span>
                  <span>Open</span>
                  <span>Close</span>
                </div>
                {compareRows.map((r) => (
                  <div key={r.bookmaker} className="sbme-books-table">
                    <span className="sbme-books-book">{r.label}</span>
                    <span>{tab === "spread" || tab === "total" ? fmtNum(r.homeVal) : fmtOdds(r.homeVal)}</span>
                    <span>{tab === "spread" || tab === "total" ? fmtNum(r.awayVal) : fmtOdds(r.awayVal)}</span>
                    <span className="is-muted">{fmtOdds(r.opening)}</span>
                    <span className="is-muted">{fmtOdds(r.closing)}</span>
                  </div>
                ))}
              </div>
            )}
            <p className="sbme-books-board-note">
              Bookmaker Price is the sportsbook line. Fair Odds and Consensus appear only when SportsGameOdds returned fairOdds / bookOdds. SB ME does not accept or place wagers.
            </p>
          </div>
        )}
          </div>
        )}
      </section>
    </div>
  );
}
