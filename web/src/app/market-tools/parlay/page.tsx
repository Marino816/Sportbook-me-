"use client";

import { useState, useMemo, useCallback, useEffect } from "react";
import { Layers, X, SearchIcon, ChevronDown } from "lucide-react";
import { useEvents } from "@/lib/use-events";
import type { SBEvent, SBMarket, SBBookLine } from "@/lib/sbevent";
import { formatBookmakerName, buildBookmakerUniverse } from "@/lib/bookmakers";
import { MARKET_TOOL_LEAGUES, leagueLabel } from "@/lib/sgo-leagues";
import { filterMarkets, type LineMode } from "@/lib/market-view";
import { LineModeChips, FairOddsMark, ConsensusMark, LastUpdated } from "@/components/market-controls";
import { gameState } from "@/lib/live-scores";
import { useRouter } from "next/navigation";

const LEAGUES = MARKET_TOOL_LEAGUES;
type League = typeof LEAGUES[number];
const BET_TYPES = ["moneyline", "spread", "total", "player_prop", "team_prop", "other"] as const;
const INITIAL_VISIBLE_BOOKS = 12;

interface Leg {
  id: string;
  eventName: string;
  market: string;
  selection: string;
  odds: number;
  bookmaker: string;
  fairOdds?: number | null;
  consensus?: number | null;
  period?: string;
  isFinal?: boolean;
}

const EDT = "America/New_York";

function fmtOdds(v: number | null | undefined) {
  if (v == null) return "\u2014";
  return v > 0 ? "+" + v : "" + v;
}
function fmtSpread(v: number | null | undefined) {
  if (v == null) return "\u2014";
  return v > 0 ? "+" + v : "" + v;
}
function americanToDecimal(am: number) {
  return am > 0 ? 1 + am / 100 : 1 + 100 / Math.abs(am);
}

function todayEDT() {
  return new Date().toLocaleDateString("en-US", { timeZone: EDT });
}
function tomorrowEDT() {
  const d = new Date();
  d.setDate(d.getDate() + 1);
  return d.toLocaleDateString("en-US", { timeZone: EDT });
}
function eventDateKey(iso: string | null): string {
  if (!iso) return "9999";
  return new Date(iso).toLocaleDateString("en-US", { timeZone: EDT });
}
function dateLabel(iso: string | null): string {
  const dk = eventDateKey(iso);
  if (!dk || dk === "9999") return "Upcoming";
  const ts = iso || "";
  if (dk === todayEDT()) {
    return "TODAY \u2014 " + new Date(ts).toLocaleDateString("en-US", { timeZone: EDT, weekday: "long", month: "long", day: "numeric" }).toUpperCase();
  }
  if (dk === tomorrowEDT()) {
    return "TOMORROW \u2014 " + new Date(ts).toLocaleDateString("en-US", { timeZone: EDT, weekday: "long", month: "long", day: "numeric" }).toUpperCase();
  }
  return new Date(ts).toLocaleDateString("en-US", { timeZone: EDT, weekday: "long", month: "long", day: "numeric" }).toUpperCase();
}
function shortDate(iso: string | null): string {
  if (!iso) return "?";
  return new Date(iso || "").toLocaleDateString("en-US", { timeZone: EDT, weekday: "short", month: "short", day: "numeric" });
}
function timeEDT(iso: string | null): string {
  if (!iso) return "TBD";
  return new Date(iso).toLocaleTimeString("en-US", { timeZone: EDT, hour: "numeric", minute: "2-digit" }) + " EDT";
}

function buildDateList(events: SBEvent[]): { date: string; label: string; sh: string }[] {
  const seen = new Set<string>();
  const out: { date: string; label: string; sh: string }[] = [];
  for (const ev of events) {
    const dk = eventDateKey(ev.start_time);
    if (!dk || dk === "9999") continue;
    if (seen.has(dk)) continue;
    seen.add(dk);
    out.push({ date: dk, label: dateLabel(ev.start_time), sh: shortDate(ev.start_time) });
  }
  return out.sort((a, b) => new Date(a.date).getTime() - new Date(b.date).getTime());
}

function isLegAdded(legs: Leg[], eventName: string, market: string, selection: string): boolean {
  return legs.some((l) => l.eventName === eventName && l.market === market && l.selection === selection);
}

function getBook(books: SBBookLine[], bookmaker: string): SBBookLine | undefined {
  if (!bookmaker) return undefined;
  return books.find((b) => b.bookmaker === bookmaker);
}

function SelectorBtn({
  label, odds, selected, disabled, onClick,
}: {
  label: string; odds: string; selected?: boolean; disabled?: boolean; onClick: () => void;
}) {
  return (
    <button type="button" onClick={onClick} disabled={disabled} className={`sbme-parlay-sel${selected ? " is-on" : ""}`}>
      <span>{label}</span>
      <b>{odds}</b>
    </button>
  );
}

function MarketLegs({
  betType, markets, event, bookmaker, onAdd, propFilter, legs,
}: {
  betType: string;
  markets: SBMarket[];
  event: SBEvent;
  bookmaker: string;
  onAdd: (market: string, selection: string, odds: number, meta?: { fairOdds?: number | null; consensus?: number | null; period?: string }) => void;
  propFilter: string;
  legs: Leg[];
}) {
  if (!markets.length) return <p className="sbme-parlay-empty">No {betType} markets in this loaded view.</p>;

  if (betType === "moneyline") {
    const home = markets.find((m) => m.side?.toLowerCase() === "home");
    const away = markets.find((m) => m.side?.toLowerCase() === "away");
    const hb = home ? getBook(home.books, bookmaker) : undefined;
    const ab = away ? getBook(away.books, bookmaker) : undefined;
    const awName = event.away_team?.abbreviation || "Away";
    const hmName = event.home_team?.abbreviation || "Home";
    const evName = awName + " @ " + hmName;
    return (
      <div className="sbme-parlay-sels">
        <SelectorBtn
          label={awName}
          odds={fmtOdds(ab?.moneyline)}
          selected={isLegAdded(legs, evName, "Moneyline", awName)}
          disabled={ab?.moneyline == null}
          onClick={() => {
            if (ab?.moneyline == null) return;
            onAdd("Moneyline", awName, ab.moneyline, { fairOdds: away?.fair_odds, consensus: away?.book_odds, period: away?.period_id });
          }}
        />
        <SelectorBtn
          label={hmName}
          odds={fmtOdds(hb?.moneyline)}
          selected={isLegAdded(legs, evName, "Moneyline", hmName)}
          disabled={hb?.moneyline == null}
          onClick={() => {
            if (hb?.moneyline == null) return;
            onAdd("Moneyline", hmName, hb.moneyline, { fairOdds: home?.fair_odds, consensus: home?.book_odds, period: home?.period_id });
          }}
        />
      </div>
    );
  }

  if (betType === "spread") {
    const home = markets.find((m) => m.side?.toLowerCase() === "home");
    const away = markets.find((m) => m.side?.toLowerCase() === "away");
    const hb = home ? getBook(home.books, bookmaker) : undefined;
    const ab = away ? getBook(away.books, bookmaker) : undefined;
    const awName = event.away_team?.abbreviation || "Away";
    const hmName = event.home_team?.abbreviation || "Home";
    const evName = awName + " @ " + hmName;
    const awSel = awName + " " + fmtSpread(ab?.spread);
    const hmSel = hmName + " " + fmtSpread(hb?.spread);
    return (
      <div className="sbme-parlay-sels">
        <SelectorBtn
          label={awSel}
          odds={fmtOdds(ab?.moneyline)}
          selected={isLegAdded(legs, evName, "Spread", awSel)}
          disabled={ab?.moneyline == null || ab?.spread == null}
          onClick={() => {
            if (ab?.moneyline == null || ab?.spread == null) return;
            onAdd("Spread", awSel, ab.moneyline, { fairOdds: away?.fair_odds, consensus: away?.book_odds, period: away?.period_id });
          }}
        />
        <SelectorBtn
          label={hmSel}
          odds={fmtOdds(hb?.moneyline)}
          selected={isLegAdded(legs, evName, "Spread", hmSel)}
          disabled={hb?.moneyline == null || hb?.spread == null}
          onClick={() => {
            if (hb?.moneyline == null || hb?.spread == null) return;
            onAdd("Spread", hmSel, hb.moneyline, { fairOdds: home?.fair_odds, consensus: home?.book_odds, period: home?.period_id });
          }}
        />
      </div>
    );
  }

  if (betType === "total") {
    const over = markets.find((m) => m.side?.toLowerCase() === "over");
    const under = markets.find((m) => m.side?.toLowerCase() === "under");
    const ob = over ? getBook(over.books, bookmaker) : undefined;
    const ub = under ? getBook(under.books, bookmaker) : undefined;
    const line = ob?.over_under ?? ub?.over_under ?? null;
    const awName = event.away_team?.abbreviation || "Away";
    const hmName = event.home_team?.abbreviation || "Home";
    const evName = awName + " @ " + hmName;
    const ovSel = "Over " + (line ?? "\u2014");
    const unSel = "Under " + (line ?? "\u2014");
    return (
      <div className="sbme-parlay-sels">
        <SelectorBtn
          label={ovSel}
          odds={fmtOdds(ob?.moneyline)}
          selected={isLegAdded(legs, evName, "Total", ovSel)}
          disabled={ob?.moneyline == null || line == null}
          onClick={() => {
            if (ob?.moneyline == null || line == null) return;
            onAdd("Total", ovSel, ob.moneyline, { fairOdds: over?.fair_odds, consensus: over?.book_odds, period: over?.period_id });
          }}
        />
        <SelectorBtn
          label={unSel}
          odds={fmtOdds(ub?.moneyline)}
          selected={isLegAdded(legs, evName, "Total", unSel)}
          disabled={ub?.moneyline == null || line == null}
          onClick={() => {
            if (ub?.moneyline == null || line == null) return;
            onAdd("Total", unSel, ub.moneyline, { fairOdds: under?.fair_odds, consensus: under?.book_odds, period: under?.period_id });
          }}
        />
      </div>
    );
  }

  const filtered = propFilter
    ? markets.filter((m) => m.player_name?.toLowerCase().includes(propFilter.toLowerCase()) || m.market_name?.toLowerCase().includes(propFilter.toLowerCase()))
    : markets.slice(0, 30);
  const awName = event.away_team?.abbreviation || "Away";
  const hmName = event.home_team?.abbreviation || "Home";
  const evName = awName + " @ " + hmName;
  const rows = filtered.flatMap((m, i) => {
    const bk = getBook(m.books, bookmaker);
    if (!bk || !bk.available || bk.moneyline == null) return [];
    const label = ((m.player_name || "") + " " + (m.market_name || "").trim() + " " + (bk.over_under ?? "").toString().trim()).trim();
    const sel = label || "\u2014";
    return [{
      key: `${m.odd_id || i}`,
      sel,
      market: m.market_name || betType,
      odds: bk.moneyline,
      added: isLegAdded(legs, evName, m.market_name || betType, sel),
      fairOdds: m.fair_odds,
      consensus: m.book_odds,
      period: m.period_id,
    }];
  });
  return (
    <div className="sbme-parlay-sels sbme-parlay-sels--stack">
      {rows.map((r) => (
        <SelectorBtn
          key={r.key}
          label={r.sel}
          odds={fmtOdds(r.odds)}
          selected={r.added}
          onClick={() => onAdd(r.market, r.sel, r.odds, { fairOdds: r.fairOdds, consensus: r.consensus, period: r.period })}
        />
      ))}
      {rows.length === 0 && <p className="sbme-parlay-empty">No current bookmaker price for these props in this loaded view.</p>}
    </div>
  );
}

export default function ParlayBuilderPage() {
  const router = useRouter();
  const [activeLeague, setActiveLeague] = useState<League>("MLB");
  const [legs, setLegs] = useState<Leg[]>([]);
  const [stake, setStake] = useState("10");
  const [stakeFocused, setStakeFocused] = useState(false);
  const [selectedGameId, setSelectedGameId] = useState<string | null>(null);
  const [selectedBetType, setSelectedBetType] = useState<string>("moneyline");
  const [selectedBook, setSelectedBook] = useState<string>("");
  const [propFilter, setPropFilter] = useState("");
  const [selectedDateIdx, setSelectedDateIdx] = useState(0);
  const [showAllBooks, setShowAllBooks] = useState(false);
  const [pendingBook, setPendingBook] = useState<string | null>(null);
  const [lineMode, setLineMode] = useState<LineMode>("main");
  const [notice, setNotice] = useState<string | null>(null);

  const { events: rawEvents, loading, lastFetch } = useEvents(activeLeague);
  const events = useMemo(() => {
    const seen = new Set<string>();
    return rawEvents.filter((e) => {
      if (seen.has(e.id)) return false;
      seen.add(e.id);
      return true;
    });
  }, [rawEvents]);

  const availableBooks = useMemo(() => buildBookmakerUniverse(events.map((e) => e.bookmakers)), [events]);
  useEffect(() => {
    if (selectedBook && !availableBooks.includes(selectedBook)) setSelectedBook("");
  }, [availableBooks, selectedBook]);

  const dateNav = useMemo(() => buildDateList(events), [events]);
  const selectedDate = useMemo(() => dateNav[selectedDateIdx] || null, [dateNav, selectedDateIdx]);
  const selectedDateGames = useMemo(() => {
    if (!selectedDate) return [];
    return events
      .filter((e) => eventDateKey(e.start_time) === selectedDate.date)
      .sort((a, b) => new Date(a.start_time || 0).getTime() - new Date(b.start_time || 0).getTime());
  }, [events, selectedDate]);

  const goLeague = useCallback((lg: League) => {
    setActiveLeague(lg);
    setSelectedGameId(null);
    setSelectedBook("");
    setLegs([]);
    setNotice(null);
  }, []);

  useEffect(() => {
    if (loading || dateNav.length === 0) return;
    const td = todayEDT();
    const idx = dateNav.findIndex((d) => d.date === td);
    setSelectedDateIdx(idx >= 0 ? idx : 0);
  }, [loading, dateNav]);

  const selectedGame = useMemo(() => events.find((e) => e.id === selectedGameId) || null, [events, selectedGameId]);
  const expandedMarkets = useMemo(() => {
    if (!selectedGame) return {};
    const groups: Record<string, SBMarket[]> = {};
    for (const m of filterMarkets(selectedGame.markets || [], { lineMode, period: "all" })) {
      const k = m.bet_type;
      if (!groups[k]) groups[k] = [];
      groups[k].push(m);
    }
    return groups;
  }, [selectedGame, lineMode]);

  const addLeg = useCallback((
    event: SBEvent,
    market: string,
    selection: string,
    odds: number,
    meta?: { fairOdds?: number | null; consensus?: number | null; period?: string },
  ) => {
    const evName = event.away_team?.abbreviation + " @ " + event.home_team?.abbreviation;
    if (gameState(event) === "FINAL") {
      setNotice("Finalized event — selections cannot be added.");
      return;
    }
    if (odds == null || Number.isNaN(odds)) {
      setNotice("No current bookmaker price for this selection.");
      return;
    }
    const dup = legs.find((l) => l.eventName === evName && l.market === market && l.selection === selection);
    if (dup) return;
    const conf = legs.find((l) => l.eventName === evName && l.market === market && l.selection !== selection);
    if (conf && (market === "Moneyline" || market.includes("Spread") || market.includes("Total"))) {
      setNotice("Potential conflict — the opposite side of this market is already in the combination.");
      return;
    }
    setNotice(null);
    setLegs((prev) => [...prev, {
      id: Date.now() + "-" + Math.random().toString(36).slice(2, 6),
      eventName: evName,
      market,
      selection,
      odds,
      bookmaker: selectedBook,
      fairOdds: meta?.fairOdds ?? null,
      consensus: meta?.consensus ?? null,
      period: meta?.period,
      isFinal: false,
    }]);
  }, [selectedBook, legs]);

  const removeLeg = useCallback((id: string) => setLegs((prev) => prev.filter((l) => l.id !== id)), []);

  const result = useMemo(() => {
    if (legs.length === 0) return { odds: 0, payout: 0, profit: 0 };
    let dec = 1;
    for (const l of legs) dec *= americanToDecimal(l.odds);
    const st = parseFloat(stake) || 0;
    const payout = dec * st;
    const profit = payout - st;
    const am = dec >= 2 ? Math.round((dec - 1) * 100) : Math.round(-100 / (dec - 1));
    return { odds: am, payout, profit };
  }, [legs, stake]);

  const allSameEvent = legs.length >= 2 && legs.every((l) => l.eventName === legs[0]?.eventName);

  const sortedBooks = useMemo(() => {
    const popular = ["draftkings", "fanduel", "betmgm", "caesars", "espnbet", "bovada", "pinnacle", "bet365", "pointsbet", "barstool"];
    const seen = new Set<string>();
    const out: string[] = [];
    for (const b of popular) {
      if (availableBooks.includes(b) && !seen.has(b)) {
        out.push(b);
        seen.add(b);
      }
    }
    for (const b of [...availableBooks].sort()) {
      if (!seen.has(b)) out.push(b);
    }
    return out;
  }, [availableBooks]);

  const visibleBooks = showAllBooks ? sortedBooks : sortedBooks.slice(0, INITIAL_VISIBLE_BOOKS);
  const hiddenCount = sortedBooks.length - INITIAL_VISIBLE_BOOKS;

  const requestBookChange = useCallback((book: string) => {
    if (legs.length === 0) {
      setSelectedBook(book);
      setLegs([]);
    } else {
      setPendingBook(book);
    }
  }, [legs]);
  const confirmBookChange = useCallback(() => {
    if (pendingBook != null) {
      setSelectedBook(pendingBook);
      setLegs([]);
      setPendingBook(null);
      setNotice(null);
    }
  }, [pendingBook]);
  const cancelBookChange = useCallback(() => setPendingBook(null), []);

  const askIntelligence = () => {
    const draft = [
      "Analyze this analytical parlay using only cached SportsGameOdds data.",
      "Do not invent bookmaker prices, lines, market availability, or sportsbook-specific parlay eligibility.",
      "If a field is missing, say it is unavailable.",
      "Bookmaker: " + (selectedBook || "unspecified"),
      ...legs.map((l, i) => `Leg ${i + 1}: ${l.eventName} | ${l.market} | ${l.selection} | Book price ${fmtOdds(l.odds)} | Fair ${l.fairOdds ?? "unavailable"} | Consensus ${l.consensus ?? "unavailable"}`),
    ].join("\n");
    try { sessionStorage.setItem("sbme_ai_draft", draft); } catch { /* ignore */ }
    router.push("/ai");
  };

  return (
    <div className="sbme-parlay">
      {pendingBook !== null && (
        <div className="sbme-parlay-modal-scrim" onClick={cancelBookChange} role="presentation">
          <div className="sbme-parlay-modal" onClick={(e) => e.stopPropagation()} role="dialog" aria-labelledby="parlay-book-dialog">
            <h3 id="parlay-book-dialog">Change sportsbook?</h3>
            <p>
              Changing sportsbooks will clear the current combination because prices and market availability may differ between books.
            </p>
            <div className="sbme-parlay-modal-actions">
              <button type="button" className="is-ghost" onClick={cancelBookChange}>Cancel</button>
              <button type="button" className="is-gold" onClick={confirmBookChange}>Change sportsbook</button>
            </div>
          </div>
        </div>
      )}

      <header className="sbme-parlay-head">
        <span className="sbme-parlay-icon" aria-hidden>
          <Layers size={20} />
        </span>
        <div>
          <p className="sbme-parlay-kicker">MARKET COMBINATION</p>
          <h1>Parlay Intelligence</h1>
          <p>
            Analytical market-combination intelligence using available canonical SportsGameOdds data.
            SB ME does not accept or place wagers.
          </p>
        </div>
        <div className="sbme-parlay-head-meta">
          <LastUpdated fetchedAt={lastFetch ?? undefined} />
        </div>
      </header>

      <div className="sbme-parlay-work">
        <section className="sbme-parlay-panel sbme-parlay-select" aria-label="Market selection">
          {!selectedBook ? (
            <>
              <p className="sbme-parlay-books-label">
                {loading ? "Loading books in this league's events…" : "Books in this league's loaded events"}
              </p>
              {visibleBooks.length === 0 && !loading && (
                <p className="sbme-parlay-empty">No bookmakers returned in this league's loaded events.</p>
              )}
              <div className="sbme-parlay-books">
                {visibleBooks.map((b) => (
                  <button
                    key={b}
                    type="button"
                    className={`sbme-parlay-book${selectedBook === b ? " is-on" : ""}`}
                    onClick={() => requestBookChange(b)}
                  >
                    {formatBookmakerName(b)}
                  </button>
                ))}
              </div>
              {hiddenCount > 0 && (
                <button type="button" className="sbme-parlay-more" onClick={() => setShowAllBooks(!showAllBooks)}>
                  {showAllBooks ? "Show less" : `Show more (${hiddenCount} more)`}
                  <ChevronDown size={12} style={{ transform: showAllBooks ? "rotate(180deg)" : "none" }} />
                </button>
              )}
            </>
          ) : (
            <div className="sbme-parlay-bookbar">
              <span>Book</span>
              <strong>{formatBookmakerName(selectedBook)}</strong>
              <button type="button" className="sbme-parlay-change sbme-parlay-change--end" onClick={() => requestBookChange("")}>
                Change
              </button>
            </div>
          )}

          <div className="sbme-parlay-controls">
            <LineModeChips value={lineMode} onChange={setLineMode} />
            <div className="sbme-parlay-leagues">
              {LEAGUES.map((lg) => (
                <button
                  key={lg}
                  type="button"
                  className={`sbme-chip${activeLeague === lg ? " is-on" : ""}`}
                  onClick={() => goLeague(lg)}
                >
                  {leagueLabel(lg)}
                </button>
              ))}
            </div>
          </div>

          <div className="sbme-parlay-select-body">
            <div className="sbme-parlay-sub">
              <div className="sbme-parlay-panel-h">
                <h2>{activeLeague} events</h2>
              </div>
              {dateNav.length > 0 && (
                <div className="sbme-parlay-dates">
                  <button type="button" className="sbme-parlay-date-nav" onClick={() => setSelectedDateIdx((i) => Math.max(0, i - 1))} disabled={selectedDateIdx === 0}>‹</button>
                  {dateNav.map((d, i) => (
                    <button
                      key={d.date}
                      type="button"
                      className={`sbme-parlay-date${i === selectedDateIdx ? " is-on" : ""}`}
                      onClick={() => setSelectedDateIdx(i)}
                      style={{ opacity: Math.abs(i - selectedDateIdx) > 3 ? 0.4 : 1 }}
                    >
                      {d.sh.toUpperCase()}
                    </button>
                  ))}
                  <button type="button" className="sbme-parlay-date-nav" onClick={() => setSelectedDateIdx((i) => Math.min(dateNav.length - 1, i + 1))} disabled={selectedDateIdx >= dateNav.length - 1}>›</button>
                </div>
              )}
              {selectedDate && <div className="sbme-parlay-date-label">{selectedDate.label}</div>}
              <div className="sbme-parlay-list">
                {loading && <p className="sbme-parlay-empty">Loading events…</p>}
                {!loading && selectedDateGames.length === 0 && (
                  <p className="sbme-parlay-empty">No {activeLeague} games on this date.</p>
                )}
                {selectedDateGames.map((ev) => {
                  const sel = selectedGameId === ev.id;
                  const final = gameState(ev) === "FINAL";
                  const live = gameState(ev) === "LIVE";
                  return (
                    <button
                      key={ev.id}
                      type="button"
                      className={`sbme-parlay-game${sel ? " is-on" : ""}`}
                      onClick={() => setSelectedGameId(ev.id)}
                    >
                      <span>{ev.away_team?.abbreviation || "AWY"} @ {ev.home_team?.abbreviation || "HOM"}</span>
                      <em className={live ? "is-live" : undefined}>{final ? "FINAL" : live ? "LIVE" : timeEDT(ev.start_time)}</em>
                    </button>
                  );
                })}
              </div>
            </div>

            <div className="sbme-parlay-sub">
              {!selectedGame ? (
                <p className="sbme-parlay-empty">Select an event to view available markets.</p>
              ) : !selectedBook ? (
                <p className="sbme-parlay-empty">Select a book from this league's loaded events to price selections.</p>
              ) : (
                <>
                  <div className="sbme-parlay-panel-h">
                    <h2>{selectedGame.away_team?.abbreviation || "AWY"} @ {selectedGame.home_team?.abbreviation || "HOM"}</h2>
                  </div>
                  {gameState(selectedGame) === "FINAL" && (
                    <div className="sbme-parlay-final">Finalized event — not a current bettable market. Selections cannot be added.</div>
                  )}
                  <div className="sbme-parlay-tabs">
                    {BET_TYPES.map((bt) => {
                      const count = (expandedMarkets[bt] || []).length;
                      return (
                        <button
                          key={bt}
                          type="button"
                          className={`sbme-chip${selectedBetType === bt ? " is-on" : ""}`}
                          onClick={() => setSelectedBetType(bt)}
                        >
                          {bt === "moneyline" ? "ML" : bt === "spread" ? "Spread" : bt === "total" ? "Total" : bt === "player_prop" ? "Player Props" : bt === "team_prop" ? "Team Props" : "Other"}
                          {count > 0 ? ` ${count}` : ""}
                        </button>
                      );
                    })}
                  </div>
                  {(selectedBetType === "player_prop" || selectedBetType === "team_prop" || selectedBetType === "other") && (
                    <div className="sbme-parlay-search">
                      <SearchIcon size={12} />
                      <input
                        type="text"
                        value={propFilter}
                        onChange={(e) => setPropFilter(e.target.value)}
                        placeholder="Filter by player or market…"
                        aria-label="Filter props"
                      />
                      {propFilter && (
                        <button type="button" className="sbme-parlay-clear" onClick={() => setPropFilter("")}>Clear</button>
                      )}
                    </div>
                  )}
                  <MarketLegs
                    betType={selectedBetType}
                    markets={expandedMarkets[selectedBetType] || []}
                    event={selectedGame}
                    bookmaker={selectedBook}
                    onAdd={(market, selection, odds, meta) => addLeg(selectedGame, market, selection, odds, meta)}
                    propFilter={propFilter}
                    legs={legs}
                  />
                </>
              )}
            </div>
          </div>
        </section>

        <aside className="sbme-parlay-panel sbme-parlay-analysis" aria-label="Combination analysis">
          <div className="sbme-parlay-panel-h">
            <h2>Combination ({legs.length})</h2>
            {legs.length > 0 && (
              <button type="button" className="sbme-parlay-clear" onClick={() => { setLegs([]); setNotice(null); }}>
                Clear all
              </button>
            )}
          </div>
          {selectedBook && (
            <p className="sbme-parlay-note" style={{ marginTop: 0, marginBottom: 8 }}>
              Book prices from {formatBookmakerName(selectedBook)}. Analysis reflects currently available market data.
            </p>
          )}
          {notice && <div className="sbme-parlay-notice">{notice}</div>}
          {allSameEvent && (
            <div className="sbme-parlay-flag sbme-parlay-flag--sgp">
              Potential conflict — same-game combination. Combined price is a multiplicative product of listed book prices, not sportsbook same-game parlay pricing.
            </div>
          )}

          {legs.length === 0 ? (
            <div className="sbme-parlay-empty">
              <strong>Select markets to analyze together</strong>
              SB ME will evaluate the combination using available market intelligence. No example prices are shown until you add a real selection.
            </div>
          ) : (
            <div>
              {legs.map((l) => (
                <div key={l.id} className="sbme-parlay-leg">
                  <div>
                    <h3>{l.eventName}</h3>
                    <p>{l.market} · {l.selection}</p>
                    <p>
                      {formatBookmakerName(l.bookmaker)} · Book {fmtOdds(l.odds)}
                      {l.period ? ` · ${l.period}` : ""}
                    </p>
                    <div className="sbme-parlay-leg-meta">
                      <FairOddsMark value={l.fairOdds ?? null} />
                      <ConsensusMark value={l.consensus ?? null} />
                    </div>
                  </div>
                  <button type="button" className="sbme-parlay-x" onClick={() => removeLeg(l.id)} aria-label="Remove leg">
                    <X size={14} />
                  </button>
                </div>
              ))}
            </div>
          )}

          {legs.length >= 2 && (
            <div className="sbme-parlay-metrics">
              <div className="sbme-parlay-row">
                <span>Combined book price</span>
                <strong>{fmtOdds(result.odds)}</strong>
              </div>
              <label className="sbme-parlay-note" style={{ margin: 0 }} htmlFor="parlay-stake">Reference stake (analytical)</label>
              <input
                id="parlay-stake"
                className="sbme-parlay-stake"
                type="text"
                inputMode="decimal"
                value={stakeFocused ? stake : stake || "10"}
                onFocus={() => setStakeFocused(true)}
                onBlur={() => setStakeFocused(false)}
                onChange={(e) => {
                  const v = e.target.value;
                  if (v === "" || /^\d*\.?\d{0,2}$/.test(v)) setStake(v);
                }}
                placeholder="Reference stake"
              />
              <div className="sbme-parlay-row">
                <span>Hypothetical payout</span>
                <strong>${result.payout.toFixed(2)}</strong>
              </div>
              <div className="sbme-parlay-row">
                <span>Hypothetical profit</span>
                <strong>${result.profit.toFixed(2)}</strong>
              </div>
              <p className="sbme-parlay-note">
                Combined price multiplies listed book prices. This is not a sportsbook ticket and is not Fair Odds.
                Fair Odds and Consensus appear per leg only when SportsGameOdds returned them.
              </p>
              <button type="button" className="sbme-parlay-ai" onClick={askIntelligence}>
                Ask SB ME Intelligence
              </button>
            </div>
          )}
        </aside>
      </div>
    </div>
  );
}
