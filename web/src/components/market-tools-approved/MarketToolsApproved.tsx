"use client";

import { getApiBaseUrl } from "@/lib/api-base-url";
import { getStoredToken } from "@/lib/api";
import { useCallback, useEffect, useMemo, useState } from "react";
import "./market-tools-approved.css";

type Tab = "live" | "compare" | "props" | "parlay";
type OddsFormat = "american" | "decimal";

type Quote = {
  id: string;
  american?: number | null;
  decimal?: number | null;
  line?: number | null;
  bookmaker?: string;
  bookmaker_key?: string;
  period?: string;
  source_timestamp?: string;
  selection?: string;
  player?: string;
};

type Leg = {
  id: string;
  event_id: string;
  market: string;
  selection: string;
  player?: string;
  line?: number | null;
  bookmaker?: string;
  american?: number | null;
  decimal?: number | null;
  period?: string;
  matchup?: string;
  market_label?: string;
  unavailable?: boolean;
  reason?: string;
};

const SLIP_KEY = "sbme_mt_slip_v1";

function money(format: OddsFormat, n?: { american?: number | null; decimal?: number | null } | null) {
  if (!n) return "";
  if (format === "decimal") return n.decimal == null ? "" : String(n.decimal);
  if (n.american == null) return "";
  return n.american > 0 ? `+${n.american}` : String(n.american);
}

function signed(line: unknown) {
  if (line == null || line === "") return "";
  const n = Number(line);
  if (Number.isNaN(n)) return String(line);
  return n > 0 ? `+${n}` : String(n);
}

function threshold(line: unknown) {
  if (line == null || line === "") return "";
  const n = Number(line);
  if (Number.isNaN(n)) return String(line);
  return String(n);
}

function lineLabel(market: string, selection: string, line: unknown) {
  if (line == null || line === "") return "";
  const mk = String(market || "").toLowerCase();
  const sel = String(selection || "").toLowerCase();
  if (mk === "spreads") return signed(line);
  if (mk === "h2h" || mk === "outrights") return "";
  if (mk === "totals" || mk.startsWith("player_") || mk.startsWith("batter_") || mk.startsWith("pitcher_") || sel === "over" || sel === "under") {
    return threshold(line);
  }
  return threshold(line);
}

function localTime(iso?: string | null) {
  if (!iso) return "Time unavailable";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleString(undefined, { weekday: "short", month: "short", day: "numeric", hour: "numeric", minute: "2-digit", timeZoneName: "short" });
}

function utcStamp(iso?: string | null) {
  if (!iso) return "UTC unavailable";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toISOString().replace(".000Z", "Z");
}

function GameContext({ ev }: { ev: any }) {
  const ctx = ev.context || {};
  const schedule = ctx.schedule || {};
  const score = ctx.score || {};
  const weather = ctx.weather || {};
  const injuries = ctx.injuries || [];
  const periodBits = [score.period, score.inning, score.clock].filter((v: unknown) => v != null && v !== "");
  const scoreLine = (score.away_score != null || score.home_score != null)
    ? `${score.away_score ?? "—"}–${score.home_score ?? "—"}`
    : null;
  const weatherLine = weather.kind === "indoor"
    ? (weather.label || "Indoor")
    : weather.label === "Forecast not yet available."
      ? "Forecast not yet available."
      : weather.kind === "forecast" && weather.temperature != null
        ? `${weather.temperature}°${weather.temperature_unit || "F"}`
        : weather.label || "Weather unavailable";
  return (
    <div className="game-context" data-game-context data-fixture-label={ev.fixture_label || ""} data-status={score.status || ""}>
      <p className="context-line">
        <span data-local-time>{localTime(schedule.commence_time_utc || ev.commence_time)}</span>
        {score.status_display ? <span> · {score.status_display}</span> : null}
        {scoreLine ? <span data-score> · {scoreLine}</span> : null}
        {weatherLine ? <span data-weather-summary> · {weatherLine}</span> : null}
        {injuries.length ? <span> · {injuries.length} availability note{injuries.length === 1 ? "" : "s"}</span> : null}
        {score.freshness === "stale" ? <span className="warn"> · Stale</span> : null}
      </p>
      <details className="game-details">
        <summary>Game details</summary>
        <p className="meta">UTC {utcStamp(schedule.commence_time_utc || ev.commence_time)} · shown in your timezone{schedule.timezone_abbreviation ? ` (${schedule.timezone_abbreviation} on the server preview)` : ""}.</p>
        {score.note ? <p className="note">{score.note}</p> : null}
        {periodBits.length ? <p className="meta">Period/clock {periodBits.join(" · ")}</p> : <p className="note">Period, inning, and clock were not supplied.</p>}
        {score.source ? <p className="meta">Scores source {score.source}{score.source_updated_at ? ` · updated ${localTime(score.source_updated_at)}` : ""}{score.retrieved_at ? ` · retrieved ${localTime(score.retrieved_at)}` : ""} · {score.freshness || "unknown"}</p> : null}
        {weather.kind === "indoor" ? <p className="meta">{weather.label || "Indoor"}{weather.venue_name ? ` · ${weather.venue_name}` : ""} · {weather.note || ""}</p> : null}
        {weather.kind === "forecast" && weather.label === "Forecast not yet available." ? <p className="note">Forecast not yet available.</p> : null}
        {weather.kind === "forecast" && weather.temperature != null ? (
          <p className="meta">
            Forecast (not an observation) · {weather.venue_name} · {weather.temperature}°{weather.temperature_unit || "F"}
            {weather.wind ? ` · Wind ${weather.wind}` : ""}
            {weather.precipitation_probability != null ? ` · Precip ${weather.precipitation_probability}%` : ""}
            {weather.forecast_time ? ` · valid ${localTime(weather.forecast_time)}` : ""} · {weather.source}
            {weather.roof_note ? ` · ${weather.roof_note}` : ""}
          </p>
        ) : null}
        {weather.kind === "unavailable" ? <p className="note">{weather.reason || "Weather unavailable"}</p> : null}
        {injuries.length === 0 ? <p className="note">{ctx.injuries_note || "No report does not mean healthy or available."}</p> : injuries.map((row: any, i: number) => (
          <p className="meta" key={i} data-injury>
            {row.player} ({row.team}) · {row.source_wording || row.reported_status} · {row.certainty_label}
            {row.source_url ? <> · <a href={row.source_url} target="_blank" rel="noreferrer">Source</a></> : null}
            {row.published_at ? ` · ${localTime(row.published_at)}` : ""}
            {row.projection_adjustment === "not_applied" ? " · projections unchanged" : ""}
          </p>
        ))}
      </details>
    </div>
  );
}

function localDate(iso?: string | null) {
  if (!iso) return "";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

function conflictWith(legs: Leg[], leg: Leg) {
  return legs.find((existing) => {
    if (existing.event_id !== leg.event_id) return false;
    if ((existing.period || "game") !== (leg.period || "game")) return false;
    if (existing.market !== leg.market) return false;
    if (existing.market === "h2h") return existing.selection !== leg.selection;
    if (existing.market === "outrights") return (existing.player || existing.selection) !== (leg.player || leg.selection);
    return String(existing.line ?? "") === String(leg.line ?? "") && existing.selection !== leg.selection;
  });
}

function duplicateOf(legs: Leg[], leg: Leg) {
  return legs.find((existing) => (
    existing.event_id === leg.event_id
    && existing.market === leg.market
    && existing.selection === leg.selection
    && String(existing.line ?? "") === String(leg.line ?? "")
    && (existing.period || "game") === (leg.period || "game")
    && (existing.player || "") === (leg.player || "")
  ));
}

async function api(path: string, init?: RequestInit) {
  const token = getStoredToken();
  const base = getApiBaseUrl(process.env.NEXT_PUBLIC_API_URL);
  const res = await fetch(`${base}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(init?.headers || {}),
    },
  });
  if (!res.ok) throw new Error(`API ${res.status}`);
  return res.json();
}

function OddButton({
  quote, extra, format, selected, onAdd,
}: {
  quote?: Quote | null;
  extra: Partial<Leg> & { label: string; lineInLabel?: boolean };
  format: OddsFormat;
  selected: boolean;
  onAdd: (leg: Leg) => void;
}) {
  if (!quote || quote.american == null) {
    return (
      <button type="button" className="odd" disabled data-market={extra.market || ""} data-event-id={extra.event_id || ""} data-selection={extra.selection || extra.label || ""}>
        <span>{extra.label}</span>
        <b>unavailable</b>
      </button>
    );
  }
  const shown = extra.lineInLabel || extra.line == null || extra.line === "" ? "" : ` ${lineLabel(extra.market || "", extra.selection || "", extra.line)}`;
  const leg: Leg = {
    id: quote.id,
    event_id: extra.event_id || "",
    market: extra.market || "",
    selection: extra.selection || "",
    player: extra.player || "",
    line: (extra.line ?? quote.line) as number | null,
    bookmaker: quote.bookmaker,
    american: quote.american,
    decimal: quote.decimal,
    period: quote.period || extra.period || "game",
    matchup: extra.matchup,
    market_label: extra.market_label,
  };
  return (
    <button type="button" className={`odd${selected ? " is-on" : ""}`} data-market={leg.market} data-event-id={leg.event_id} data-selection={leg.selection || ""} data-american={quote.american ?? ""} onClick={() => onAdd(leg)}>
      <span>{extra.label}{shown}</span>
      <b>{money(format, quote)}</b>
    </button>
  );
}

export function MarketToolsApproved({ initialTab = "live" }: { initialTab?: Tab }) {
  const [data, setData] = useState<any>(null);
  const [tab, setTab] = useState<Tab>(initialTab);
  const [sport, setSport] = useState("nfl");
  const [soccer, setSoccer] = useState("");
  const [date, setDate] = useState("");
  const [search, setSearch] = useState("");
  const [book, setBook] = useState("");
  const [format, setFormat] = useState<OddsFormat>("american");
  const [legs, setLegs] = useState<Leg[]>([]);
  const [slipOpen, setSlipOpen] = useState(false);
  const [parlay, setParlay] = useState<any>(null);
  const [parlayError, setParlayError] = useState("");
  const [desktop, setDesktop] = useState(false);
  const [loadError, setLoadError] = useState("");

  useEffect(() => { setTab(initialTab); }, [initialTab]);

  useEffect(() => {
    const mq = window.matchMedia("(min-width: 801px)");
    const apply = () => setDesktop(mq.matches);
    apply();
    mq.addEventListener("change", apply);
    return () => mq.removeEventListener("change", apply);
  }, []);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const token = getStoredToken();
        const base = getApiBaseUrl(process.env.NEXT_PUBLIC_API_URL);
        const res = await fetch(`${base}/market-tools/internal/snapshot`, {
          headers: {
            "Content-Type": "application/json",
            ...(token ? { Authorization: `Bearer ${token}` } : {}),
          },
        });
        if (res.status === 401) {
          if (!cancelled) setLoadError("Sign in is required for Market Tools.");
          return;
        }
        if (res.status === 403) {
          if (!cancelled) setLoadError("Market Tools requires an active Pro Arena or Elite Stack plan. Sign-in alone is not enough.");
          return;
        }
        if (!res.ok) throw new Error(`API ${res.status}`);
        const json = await res.json();
        if (json?.data?.unavailable) {
          if (!cancelled) setLoadError(json.data.reason || "Shared odds cache is unavailable.");
          return;
        }
        if (!cancelled) setData(json.data);
      } catch {
        if (!cancelled) setLoadError("Saved snapshot is unavailable. Existing SGO Market Tools stay on the default provider.");
      }
    })();
    return () => { cancelled = true; };
  }, []);

  useEffect(() => {
    try {
      const raw = localStorage.getItem(SLIP_KEY);
      if (!raw) return;
      const saved = JSON.parse(raw);
      if (Array.isArray(saved?.legs)) setLegs(saved.legs);
    } catch { /* ignore */ }
  }, []);

  useEffect(() => {
    try {
      localStorage.setItem(SLIP_KEY, JSON.stringify({ legs }));
    } catch { /* ignore */ }
  }, [legs]);

  useEffect(() => {
    if (!data || !legs.length) return;
    let cancelled = false;
    (async () => {
      try {
        const json = await api("/market-tools/internal/resolve", {
          method: "POST",
          body: JSON.stringify({ legs }),
        });
        const mapped = (json.data?.legs || []) as any[];
        if (cancelled) return;
        setLegs((current) => current.map((leg, i) => {
          const row = mapped[i];
          if (row?.unavailable) return { ...leg, unavailable: true, reason: row.reason };
          return { ...leg, unavailable: false, reason: undefined };
        }));
      } catch { /* keep saved legs */ }
    })();
    return () => { cancelled = true; };
  }, [data]); // eslint-disable-line react-hooks/exhaustive-deps -- resolve once after snapshot loads

  const calcParlay = useCallback(async (nextLegs: Leg[]) => {
    const playable = nextLegs.filter((l) => !l.unavailable);
    if (playable.length < 2) {
      setParlay(null);
      return;
    }
    const json = await api("/market-tools/internal/parlay", {
      method: "POST",
      body: JSON.stringify({ leg_ids: playable.map((l) => l.id) }),
    });
    setParlay(json.data);
  }, []);

  const addLeg = (leg: Leg) => {
    if (!leg?.id || leg.american == null) return;
    if (duplicateOf(legs, leg)) {
      setParlayError("That selection is already on the slip.");
      return;
    }
    if (conflictWith(legs, leg)) {
      setParlayError("That selection conflicts with another pick on the same event and market.");
      return;
    }
    const next = [...legs, leg];
    setLegs(next);
    setParlayError("");
    setParlay(null);
    void calcParlay(next);
  };

  const removeLeg = (id: string) => {
    const next = legs.filter((l) => l.id !== id);
    setLegs(next);
    setParlay(null);
    setParlayError("");
    void calcParlay(next);
  };

  const clearLegs = () => {
    setLegs([]);
    setParlay(null);
    setParlayError("");
  };

  const events = data?.events || [];
  const filteredEvents = useMemo(() => events.filter((ev: any) => {
    if (sport && ev.selector !== sport) return false;
    if (sport === "soccer" && soccer && ev.sport_key !== soccer) return false;
    if (date && localDate(ev.commence_time) !== date) return false;
    if (search) {
      const q = search.toLowerCase();
      const blob = `${ev.home_team || ""} ${ev.away_team || ""} ${ev.sport_title || ""}`.toLowerCase();
      const players = (ev.books || []).flatMap((b: any) => (b.outrights || []).map((o: any) => o.player || "")).join(" ").toLowerCase();
      if (!blob.includes(q) && !players.includes(q)) return false;
    }
    if (book && !(ev.book_names || []).includes(book)) return false;
    return true;
  }), [events, sport, soccer, date, search, book]);

  const dates = [...new Set(events.filter((e: any) => e.selector === sport).map((e: any) => localDate(e.commence_time)).filter(Boolean))].sort();
  const books = [...new Set(events.flatMap((e: any) => e.book_names || []))].sort();

  if (loadError) {
    return <div className="sbme-mt-approved"><article className="card"><p className="warn">{loadError}</p></article></div>;
  }
  if (!data) {
    return <div className="sbme-mt-approved"><article className="card"><p className="note">Loading saved odds…</p></article></div>;
  }

  const selected = (id: string) => legs.some((l) => l.id === id);
  const count = legs.length;
  const slipVisible = count > 0 || slipOpen;
  const slipIsOpen = slipOpen || tab === "parlay" || (desktop && count > 0);

  function booksFor(ev: any) {
    const list = ev.books || [];
    if (!book) return list;
    return list.filter((b: any) => b.bookmaker === book);
  }

  function renderMatch(ev: any) {
    const labels = (data.coverage || []).find((c: any) => c.key === ev.sport_key)?.labels || { h2h: "Moneyline", spreads: "Spread", totals: "Over/Under" };
    const matchup = ev.kind === "outright" ? (ev.sport_title || "Tournament") : `${ev.away_team || "Away"} @ ${ev.home_team || "Home"}`;
    const listed = booksFor(ev);
    if (ev.kind === "outright") {
      return (
        <article className="card" key={ev.id}>
          <div className="match"><div className="teams">{matchup}</div><div className="meta">{localTime(ev.commence_time)} · {ev.period || "game"}</div></div>
          <GameContext ev={ev} />
          <p className="note">Tournament-winner market only. Not weekly PGA Tour coverage.</p>
          {listed.map((bookRow: any) => (
            <div key={bookRow.bookmaker}>
              <div className="book-name">{bookRow.bookmaker}</div>
              <div className="odds">
                {(bookRow.outrights || []).slice(0, 40).map((q: Quote) => (
                  <OddButton key={q.id} quote={q} format={format} selected={selected(q.id)} onAdd={addLeg} extra={{
                    label: q.player || q.selection || "",
                    event_id: ev.id, market: "outrights", selection: q.selection || "", player: q.player, matchup, market_label: "Tournament Winner", period: q.period,
                  }} />
                ))}
              </div>
            </div>
          ))}
        </article>
      );
    }
    return (
      <article className="card" key={ev.id}>
        <div className="match"><div className="teams">{matchup}</div><div className="meta">{localTime(ev.commence_time)}</div></div>
        <GameContext ev={ev} />
        {ev.stale ? <p className="warn">Saved odds—not live</p> : null}
        {listed.map((bookRow: any) => {
          const h2h = bookRow.h2h || {};
          const spreads = bookRow.spreads || {};
          const totals = bookRow.totals || {};
          const soccerMatch = ev.selector === "soccer";
          const ts = h2h.home?.source_timestamp || spreads.home?.source_timestamp || totals.over?.source_timestamp;
          return (
            <div key={bookRow.bookmaker}>
              <div className="book-name">{bookRow.bookmaker}</div>
              <div className="markets">
                <div className="mrow"><div className="mlabel">{labels.h2h}</div><div className="odds">
                  <OddButton quote={h2h.away} format={format} selected={selected(h2h.away?.id)} onAdd={addLeg} extra={{ label: ev.away_team || "Away", event_id: ev.id, market: "h2h", selection: ev.away_team, matchup, market_label: labels.h2h }} />
                  {soccerMatch ? <OddButton quote={h2h.draw} format={format} selected={selected(h2h.draw?.id)} onAdd={addLeg} extra={{ label: "Draw", event_id: ev.id, market: "h2h", selection: h2h.draw?.selection || "Draw", matchup, market_label: labels.h2h }} /> : null}
                  <OddButton quote={h2h.home} format={format} selected={selected(h2h.home?.id)} onAdd={addLeg} extra={{ label: ev.home_team || "Home", event_id: ev.id, market: "h2h", selection: ev.home_team, matchup, market_label: labels.h2h }} />
                </div></div>
                <div className="mrow"><div className="mlabel">{labels.spreads}</div><div className="odds">
                  <OddButton quote={spreads.away} format={format} selected={selected(spreads.away?.id)} onAdd={addLeg} extra={{ label: ev.away_team || "Away", line: spreads.away?.line, event_id: ev.id, market: "spreads", selection: ev.away_team, matchup, market_label: labels.spreads }} />
                  <OddButton quote={spreads.home} format={format} selected={selected(spreads.home?.id)} onAdd={addLeg} extra={{ label: ev.home_team || "Home", line: spreads.home?.line, event_id: ev.id, market: "spreads", selection: ev.home_team, matchup, market_label: labels.spreads }} />
                </div></div>
                <div className="mrow"><div className="mlabel">{labels.totals}</div><div className="odds">
                  <OddButton quote={totals.over} format={format} selected={selected(totals.over?.id)} onAdd={addLeg} extra={{ label: "Over", line: totals.over?.line, event_id: ev.id, market: "totals", selection: "Over", matchup, market_label: labels.totals }} />
                  <OddButton quote={totals.under} format={format} selected={selected(totals.under?.id)} onAdd={addLeg} extra={{ label: "Under", line: totals.under?.line, event_id: ev.id, market: "totals", selection: "Under", matchup, market_label: labels.totals }} />
                </div></div>
              </div>
              {bookRow.fair_h2h?.sides ? (
                <p className="note">Market-derived fair odds · Away {money(format, bookRow.fair_h2h.sides.away || {})}{bookRow.fair_h2h.sides.draw ? ` · Draw ${money(format, bookRow.fair_h2h.sides.draw)}` : ""} · Home {money(format, bookRow.fair_h2h.sides.home || {})}</p>
              ) : bookRow.fair_h2h_unavailable ? <p className="note">Market-derived fair odds unavailable.</p> : null}
              <p className="meta">Source {localTime(ts)} · Period {ev.period || "game"}</p>
            </div>
          );
        })}
      </article>
    );
  }

  const compareGroups = (data.compare || []).filter((g: any) => {
    if (sport && g.selector !== sport) return false;
    if (sport === "soccer" && soccer) {
      const league = (data.soccer_leagues || []).find((l: any) => l.id === soccer);
      if (league && g.sport_title !== league.label) return false;
    }
    if (search) {
      const q = search.toLowerCase();
      const blob = `${g.home_team || ""} ${g.away_team || ""} ${g.player || ""} ${g.selection || ""}`.toLowerCase();
      if (!blob.includes(q)) return false;
    }
    return true;
  }).slice(0, 60);

  const arbs = (data.arbitrage || []).filter((a: any) => {
    const ev = events.find((e: any) => e.id === a.event_id);
    return ev && ev.selector === sport;
  }).slice(0, 8);

  const propRows = (data.player_props || []).filter((row: any) => {
    if (sport && row.selector !== sport) return false;
    if (search) {
      const q = search.toLowerCase();
      const blob = `${row.player || ""} ${row.home_team || ""} ${row.away_team || ""} ${row.market_label || ""}`.toLowerCase();
      if (!blob.includes(q)) return false;
    }
    if (book && row.bookmaker !== book) return false;
    return true;
  });

  const byPlayer = new Map<string, any[]>();
  for (const row of propRows) {
    const key = `${row.player || "Unknown player"}|${row.event_id}|${row.market}`;
    byPlayer.set(key, [...(byPlayer.get(key) || []), row]);
  }

  let liveStatus = null;
  if (sport === "soccer" && !soccer) {
    liveStatus = <p className="note">Soccer in this snapshot is region us. Missing prices stay unavailable.</p>;
  } else {
    const cov = (data.coverage || []).find((c: any) => sport === "soccer" ? c.key === soccer : c.sport_group && c.sport_group.toLowerCase() === sport);
    if (cov?.empty_does_not_prove_no_coverage) liveStatus = <p className="note">{cov.title}: no events in this snapshot. That does not prove the sport is uncovered.</p>;
  }

  const refresh = data.refresh || {};

  return (
    <div className={`sbme-mt-approved${desktop ? " desktop-open" : ""}`} data-generation={data.generation || ""} data-fixture={data.fixture_label || ""}>
      <header className="top">
        <div>
          <p className="kicker">SPORTBOOK ME <span>DFS.AI</span></p>
          <h1>Market Tools</h1>
        </div>
        <p className="notice">Saved odds—not live</p>
        <label className="fmt">
          <span>Odds</span>
          <select value={format} onChange={(e) => setFormat(e.target.value as OddsFormat)}>
            <option value="american">American</option>
            <option value="decimal">Decimal</option>
          </select>
        </label>
      </header>

      <nav className="tabs">
        {([["live", "Game Odds"], ["compare", "Compare"], ["props", "Player Props"], ["parlay", "Parlay Builder"]] as const).map(([id, label]) => (
          <button key={id} type="button" className={`tab${tab === id ? " is-on" : ""}`} onClick={() => setTab(id)}>{label}</button>
        ))}
      </nav>

      <section className="filters">
        <div className="chip-row" style={{ gridColumn: "1 / -1" }}>
          {(data.sport_selector || []).map((s: any) => (
            <button key={s.id} type="button" className={`chip${sport === s.id ? " is-on" : ""}`} onClick={() => { setSport(s.id); setSoccer(""); setDate(""); }}>{s.label}</button>
          ))}
        </div>
        {sport === "soccer" ? (
          <label>League
            <select value={soccer} onChange={(e) => setSoccer(e.target.value)}>
              <option value="">All soccer</option>
              {(data.soccer_leagues || []).map((l: any) => <option key={l.id} value={l.id}>{l.label}</option>)}
            </select>
          </label>
        ) : null}
        <label>Date
          <select value={date} onChange={(e) => setDate(e.target.value)}>
            <option value="">Any date</option>
            {dates.map((d) => <option key={d} value={d}>{d}</option>)}
          </select>
        </label>
        <label>Team / player
          <input type="search" placeholder="Search" value={search} onChange={(e) => setSearch(e.target.value)} />
        </label>
        <label>Sportsbook
          <select value={book} onChange={(e) => setBook(e.target.value)}>
            <option value="">All books</option>
            {books.map((b) => <option key={b} value={b}>{b}</option>)}
          </select>
        </label>
      </section>

      {tab === "live" ? (
        <section>
          {liveStatus}
          {filteredEvents.length ? filteredEvents.slice(0, 40).map(renderMatch) : (
            <article className="card"><p className="empty">No saved events for this filter. Documented coverage may still exist outside this snapshot.</p></article>
          )}
        </section>
      ) : null}

      {tab === "compare" ? (
        <section>
          <p className="note">Same event, market, selection, line, and period only. Historical prices—not live. Movement, period markets, and SGP quotes remain unavailable.</p>
          {arbs.some((a: any) => a.ok && Number(a.discrepancy_pct) > 0) || arbs.some((a: any) => a.unavailable) ? (
            <article className="card">
              <p className="warn">{data.arbitrage_label || "Historical price discrepancy—not verified live."}</p>
              {arbs.filter((a: any) => a.ok && Number(a.discrepancy_pct) > 0).map((a: any, i: number) => (
                <p className="meta" key={i}><b>{a.matchup || ""}</b> · {a.market} {lineLabel(a.market, "", a.line)} · {a.discrepancy_pct}% · {(a.legs || []).map((leg: any) => `${leg.selection || ""} ${lineLabel(a.market, leg.selection, leg.line)} ${leg.bookmaker || ""} ${money(format, leg)}`).join(" · ")}</p>
              ))}
              {arbs.filter((a: any) => a.unavailable).map((a: any, i: number) => <p className="meta" key={`u${i}`}>Unavailable · {a.reason || ""}</p>)}
            </article>
          ) : null}
          {compareGroups.map((g: any, i: number) => {
            const matchup = g.kind === "outright" ? (g.sport_title || "Tournament") : `${g.away_team || ""} @ ${g.home_team || ""}`;
            return (
              <article className="card" key={`${g.event_id}-${g.market}-${g.selection}-${i}`}>
                <div className="match"><div className="teams">{matchup}</div><div className="meta">{g.market_label || g.market} · {g.player || g.selection} {lineLabel(g.market, g.selection, g.line)}</div></div>
                <div className="cmp-books">
                  {(g.prices || []).map((p: any, pi: number) => (
                    <div className={`price${p.best_listed ? " best" : ""}`} key={pi}>{p.bookmaker} <b>{money(format, p)}</b>{p.best_listed ? " · Best listed" : ""}</div>
                  ))}
                </div>
                {g.consensus ? (
                  <p className="note">Sportsbook consensus {money(format, { american: g.consensus.american, decimal: g.consensus.decimal })} · {g.consensus.book_count} books · {localTime(g.consensus.timestamp_range?.latest)}</p>
                ) : <p className="note">Sportsbook consensus unavailable.</p>}
              </article>
            );
          })}
        </section>
      ) : null}

      {tab === "props" ? (
        <section>
          <p className="note">Sampled player props from saved odds. One event is not league coverage.</p>
          {sport === "ncaab" ? (
            <article className="card"><p className="empty">NCAAB player props are documented with NBA/WNBA markets, but this snapshot has no NCAAB events. Not tested.</p></article>
          ) : byPlayer.size === 0 ? (
            <article className="card"><p className="empty">No sampled player props for this sport in this snapshot. One event is not league coverage.</p></article>
          ) : [...byPlayer.entries()].slice(0, 48).map(([key, list]) => {
            const sample = list[0];
            const matchup = `${sample.away_team || ""} @ ${sample.home_team || ""}`;
            const over = list.find((r: any) => String(r.selection || "").toLowerCase() === "over");
            const under = list.find((r: any) => String(r.selection || "").toLowerCase() === "under");
            const rest = list.filter((r: any) => r !== over && r !== under);
            const booksOnCard = [...new Set(list.map((r: any) => r.bookmaker).filter(Boolean))];
            return (
              <article className="card" key={key}>
                <div className="player">{sample.player || "Unknown player"}</div>
                {sample.season_label === "possible_preseason_not_confirmed_regular_season" ? <p className="warn">Possible preseason — not confirmed regular-season coverage.</p> : null}
                <p className="meta">{matchup} · {sample.market_label || "Player market"}</p>
                {sample.availability ? (
                  <p className="note" data-injury>
                    {sample.availability.source_wording || sample.availability.reported_status} · {sample.availability.certainty_label}
                    {sample.availability.source_url ? <> · <a href={sample.availability.source_url} target="_blank" rel="noreferrer">Source</a></> : null}
                    {" · projections unchanged"}
                  </p>
                ) : (
                  <details className="game-details">
                    <summary>Availability</summary>
                    <p className="note">No availability report on file. That does not mean healthy or available. Projections were not changed.</p>
                  </details>
                )}
                <div className="odds">
                  {[over, under, ...rest].filter(Boolean).map((row: any) => (
                    <OddButton key={row.id} quote={row} format={format} selected={selected(row.id)} onAdd={addLeg} extra={{
                      label: `${row.selection} ${threshold(row.line)} · ${row.bookmaker || "Sportsbook unavailable"}`.trim(),
                      event_id: row.event_id, market: row.market, selection: row.selection, player: row.player, matchup, market_label: row.market_label, period: row.period, line: row.line, lineInLabel: true,
                    }} />
                  ))}
                </div>
                <p className="meta">{booksOnCard.length > 1 ? `${booksOnCard.length} sportsbooks` : booksOnCard[0] || "Sportsbook unavailable"} · {localTime(sample.source_timestamp)}</p>
              </article>
            );
          })}
        </section>
      ) : null}

      {tab === "parlay" ? (
        <section>
          <article className="card">
            <p className="note">Tap odds buttons on Game Odds or Player Props. This preview does not place wagers. Same-game combinations are not given a combined price. Cross-game math is illustrative only. SGP quotes remain unavailable.</p>
            <p className="meta">Open the parlay panel at the bottom to review legs, remove picks, or clear all. Selections persist across these tabs.</p>
          </article>
        </section>
      ) : null}

      <details className="dev">
        <summary>How it works</summary>
        <p><b>Saved odds—not live.</b> Game start times are stored in UTC and shown in your timezone. Scores come from The Odds API scores endpoint when a unique match exists. Period and clock stay hidden unless supplied.</p>
        <p>Venue weather is an NWS forecast for outdoor US catalogs, or Indoor when the venue is documented as indoor. Injury notes are sourced reports only; missing notes are not a healthy listing.</p>
        <p><b>Market-derived fair odds</b> remove that sportsbook’s margin from a complete set of outcomes for the same market, line, and period. They are not SB ME win probabilities.</p>
        <p><b>Sportsbook consensus</b> is the typical listed price across unique books for the same selection. It still includes each book’s margin.</p>
        <p>Price discrepancies are historical and not a live or guaranteed profit. Incomplete markets, mismatched lines, integer lines that can push, and stale mixed timestamps stay unavailable.</p>
        <p>Player props in this preview are sampled events, not every game. Combined parlay prices are illustrative except when same-game legs suppress a combined price.</p>
      </details>
      <details className="dev">
        <summary>Development details</summary>
        <p>Continuous fetch: {String(refresh.continuous_fetch_enabled)}. {refresh.recommendation_note || ""}</p>
        <p>{refresh.five_event_prop_limit || ""}</p>
        <p>{data.golf_coverage_note || ""}</p>
        <p>Cache hits {data.cache?.cache_hits ?? 0}. Provider HTTP this process {data.cache?.provider_http_this_process ?? 0}.</p>
      </details>

      {slipVisible ? (
        <aside className={`slip${slipIsOpen ? " is-open" : ""}${count ? " has-legs" : ""}`} hidden={false}>
          <button type="button" className="slip-toggle" onClick={() => setSlipOpen((v) => !v)}>Parlay <span>{count}</span></button>
          <div className="slip-body">
            <p><b>{count} leg{count === 1 ? "" : "s"}</b></p>
            {legs.length ? legs.map((leg) => (
              <div className="leg" key={leg.id}>
                <div>
                  <div><b>{leg.matchup || ""}</b></div>
                  <div className="meta">{leg.market_label || leg.market} · {leg.player || ""} {leg.selection} {lineLabel(leg.market, leg.selection, leg.line)} · {leg.bookmaker || "Sportsbook unavailable"} · {money(format, leg)}</div>
                  {leg.unavailable ? <p className="warn">{leg.reason || "Unavailable"}</p> : null}
                </div>
                <button type="button" className="x" onClick={() => removeLeg(leg.id)} aria-label="Remove">Remove</button>
              </div>
            )) : <p className="empty">No selections.</p>}
            {count > 0 && count < 2 ? <p className="note">Add another leg to calculate illustrative combined odds.</p> : null}
            {parlay?.ok ? (
              <>
                <p className="ok">{parlay.label}</p>
                <p>Combined {money(format, { american: parlay.combined_american, decimal: parlay.combined_decimal })}</p>
                {parlay.mixed_books ? <p className="note">{parlay.mixed_book_note}</p> : null}
              </>
            ) : parlay && !parlay.ok ? <p className={`warn${parlay.same_game ? " sgp-unavailable" : ""}`}>{parlay.reason}</p> : null}
            {parlayError ? <p className="warn">{parlayError}</p> : null}
            <p style={{ display: "flex", gap: 8, flexWrap: "wrap", marginTop: 12 }}>
              <button type="button" className="btn ghost" onClick={clearLegs}>Clear All</button>
            </p>
          </div>
        </aside>
      ) : null}
    </div>
  );
}
