(() => {
  const state = {
    data: null,
    tab: new URLSearchParams(location.search).get("tab") || "live",
    sport: new URLSearchParams(location.search).get("sport") || "nfl",
    soccer: "",
    date: "",
    search: "",
    book: "",
    format: "american",
    legs: [],
    slipOpen: false,
    parlay: null,
    parlayError: "",
  };
  const $ = (id) => document.getElementById(id);
  const esc = (v) => String(v ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

  function money(n) {
    if (n == null) return "";
    if (state.format === "decimal") {
      const d = n.decimal != null ? n.decimal : null;
      return d == null ? "" : String(d);
    }
    const a = n.american;
    if (a == null) return "";
    return a > 0 ? `+${a}` : String(a);
  }
  function signed(line) {
    if (line == null || line === "") return "";
    const n = Number(line);
    if (Number.isNaN(n)) return String(line);
    return n > 0 ? `+${n}` : String(n);
  }
  function localTime(iso) {
    if (!iso) return "Time unavailable";
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return iso;
    return d.toLocaleString(undefined, { weekday: "short", month: "short", day: "numeric", hour: "numeric", minute: "2-digit", timeZoneName: "short" });
  }
  function localDate(iso) {
    if (!iso) return "";
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return "";
    const y = d.getFullYear();
    const m = String(d.getMonth() + 1).padStart(2, "0");
    const day = String(d.getDate()).padStart(2, "0");
    return `${y}-${m}-${day}`;
  }
  function selected(id) { return state.legs.some((l) => l.id === id); }

  function conflictWith(leg) {
    return state.legs.find((existing) => {
      if (existing.event_id !== leg.event_id) return false;
      if ((existing.period || "game") !== (leg.period || "game")) return false;
      if (existing.market !== leg.market) return false;
      if (existing.market === "h2h") return existing.selection !== leg.selection;
      if (existing.market === "outrights") return (existing.player || existing.selection) !== (leg.player || leg.selection);
      return String(existing.line ?? "") === String(leg.line ?? "") && existing.selection !== leg.selection;
    });
  }
  function duplicateOf(leg) {
    return state.legs.find((existing) => (
      existing.event_id === leg.event_id
      && existing.market === leg.market
      && existing.selection === leg.selection
      && String(existing.line ?? "") === String(leg.line ?? "")
      && (existing.period || "game") === (leg.period || "game")
      && (existing.player || "") === (leg.player || "")
    ));
  }

  function addLeg(leg) {
    if (!leg || !leg.id || leg.american == null) return;
    if (duplicateOf(leg)) { state.parlayError = "That selection is already on the slip."; renderSlip(); return; }
    if (conflictWith(leg)) { state.parlayError = "That selection conflicts with another pick on the same event and market."; renderSlip(); return; }
    state.legs.push(leg);
    state.parlayError = "";
    state.parlay = null;
    renderAll();
    calcParlay();
  }
  function removeLeg(id) {
    state.legs = state.legs.filter((l) => l.id !== id);
    state.parlay = null;
    state.parlayError = "";
    renderAll();
    calcParlay();
  }
  function clearLegs() {
    state.legs = [];
    state.parlay = null;
    state.parlayError = "";
    renderAll();
  }

  async function calcParlay() {
    if (state.legs.length < 2) { state.parlay = null; renderSlip(); return; }
    const res = await fetch("/api/parlay", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ leg_ids: state.legs.map((l) => l.id) }),
    });
    state.parlay = await res.json();
    renderSlip();
  }

  function oddButton(quote, extra) {
    if (!quote || quote.american == null) {
      return `<button type="button" class="odd" disabled><span>${esc(extra.label)}</span><b>unavailable</b></button>`;
    }
    const on = selected(quote.id) ? " is-on" : "";
    const line = extra.line != null ? ` ${signed(extra.line)}` : "";
    return `<button type="button" class="odd${on}" data-add="${esc(quote.id)}" data-payload="${esc(JSON.stringify({
      id: quote.id,
      event_id: extra.event_id,
      market: extra.market,
      selection: extra.selection,
      player: extra.player || "",
      line: extra.line ?? quote.line,
      bookmaker: quote.bookmaker,
      american: quote.american,
      decimal: quote.decimal,
      period: quote.period || extra.period || "game",
      matchup: extra.matchup,
      market_label: extra.market_label,
    }))}"><span>${esc(extra.label)}${esc(line)}</span><b>${esc(money(quote))}</b></button>`;
  }

  function filteredEvents() {
    const events = state.data.events || [];
    return events.filter((ev) => {
      if (state.sport && ev.selector !== state.sport) return false;
      if (state.sport === "soccer" && state.soccer && ev.sport_key !== state.soccer) return false;
      if (state.date && localDate(ev.commence_time) !== state.date) return false;
      if (state.search) {
        const q = state.search.toLowerCase();
        const blob = `${ev.home_team || ""} ${ev.away_team || ""} ${ev.sport_title || ""}`.toLowerCase();
        const players = (ev.books || []).flatMap((b) => (b.outrights || []).map((o) => o.player || "")).join(" ").toLowerCase();
        if (!blob.includes(q) && !players.includes(q)) return false;
      }
      if (state.book && !(ev.book_names || []).includes(state.book)) return false;
      return true;
    });
  }

  function booksFor(ev) {
    const books = ev.books || [];
    if (!state.book) return books;
    return books.filter((b) => b.bookmaker === state.book);
  }

  function renderFilters() {
    const events = state.data.events || [];
    const dates = [...new Set(events.filter((e) => e.selector === state.sport).map((e) => localDate(e.commence_time)).filter(Boolean))].sort();
    const books = [...new Set(events.flatMap((e) => e.book_names || []))].sort();
    const sports = (state.data.sport_selector || []).map((s) => `<button type="button" class="chip${state.sport === s.id ? " is-on" : ""}" data-sport="${esc(s.id)}">${esc(s.label)}</button>`).join("");
    const soccer = state.sport === "soccer"
      ? `<label>League<select id="soccer-league"><option value="">All soccer</option>${(state.data.soccer_leagues || []).map((l) => `<option value="${esc(l.id)}"${state.soccer === l.id ? " selected" : ""}>${esc(l.label)}</option>`).join("")}</select></label>`
      : "";
    $("filters").innerHTML = `
      <div class="chip-row" style="grid-column:1/-1">${sports}</div>
      ${soccer}
      <label>Date<select id="date-filter"><option value="">Any date</option>${dates.map((d) => `<option value="${d}"${state.date === d ? " selected" : ""}>${d}</option>`).join("")}</select></label>
      <label>Team / player<input type="search" id="team-search" placeholder="Search" value="${esc(state.search)}" /></label>
      <label>Sportsbook<select id="book-filter"><option value="">All books</option>${books.map((b) => `<option value="${esc(b)}"${state.book === b ? " selected" : ""}>${esc(b)}</option>`).join("")}</select></label>
    `;
  }

  function renderMatch(ev) {
    const labels = (state.data.coverage || []).find((c) => c.key === ev.sport_key)?.labels || { h2h: "Moneyline", spreads: "Spread", totals: "Over/Under" };
    const matchup = ev.kind === "outright" ? (ev.sport_title || "Tournament") : `${ev.away_team || "Away"} @ ${ev.home_team || "Home"}`;
    const books = booksFor(ev);
    if (ev.kind === "outright") {
      const body = books.map((book) => {
        const rows = (book.outrights || []).slice(0, 40).map((q) => oddButton(q, {
          label: q.player || q.selection,
          event_id: ev.id,
          market: "outrights",
          selection: q.selection,
          player: q.player,
          matchup,
          market_label: "Tournament Winner",
          period: q.period,
        })).join("");
        return `<div class="book-name">${esc(book.bookmaker)}</div><div class="odds">${rows || '<span class="empty">No winner prices</span>'}</div>`;
      }).join("");
      return `<article class="card">
        <div class="match"><div class="teams">${esc(matchup)}</div><div class="meta">${esc(localTime(ev.commence_time))} · ${esc(ev.period || "game")}</div></div>
        <p class="note">Tournament-winner market only. Not weekly PGA Tour coverage.</p>
        ${body || '<p class="empty">No golf prices in this snapshot.</p>'}
      </article>`;
    }
    const body = books.map((book) => {
      const h2h = book.h2h || {};
      const spreads = book.spreads || {};
      const totals = book.totals || {};
      const soccer = ev.selector === "soccer";
      const mlBtns = soccer
        ? oddButton(h2h.away, { label: ev.away_team || "Away", event_id: ev.id, market: "h2h", selection: ev.away_team, matchup, market_label: labels.h2h })
          + oddButton(h2h.draw, { label: "Draw", event_id: ev.id, market: "h2h", selection: h2h.draw?.selection || "Draw", matchup, market_label: labels.h2h })
          + oddButton(h2h.home, { label: ev.home_team || "Home", event_id: ev.id, market: "h2h", selection: ev.home_team, matchup, market_label: labels.h2h })
        : oddButton(h2h.away, { label: ev.away_team || "Away", event_id: ev.id, market: "h2h", selection: ev.away_team, matchup, market_label: labels.h2h })
          + oddButton(h2h.home, { label: ev.home_team || "Home", event_id: ev.id, market: "h2h", selection: ev.home_team, matchup, market_label: labels.h2h });
      const spBtns = oddButton(spreads.away, { label: ev.away_team || "Away", line: spreads.away?.line, event_id: ev.id, market: "spreads", selection: ev.away_team, matchup, market_label: labels.spreads })
        + oddButton(spreads.home, { label: ev.home_team || "Home", line: spreads.home?.line, event_id: ev.id, market: "spreads", selection: ev.home_team, matchup, market_label: labels.spreads });
      const totBtns = oddButton(totals.over, { label: "Over", line: totals.over?.line, event_id: ev.id, market: "totals", selection: "Over", matchup, market_label: labels.totals })
        + oddButton(totals.under, { label: "Under", line: totals.under?.line, event_id: ev.id, market: "totals", selection: "Under", matchup, market_label: labels.totals });
      const ts = h2h.home?.source_timestamp || spreads.home?.source_timestamp || totals.over?.source_timestamp;
      return `<div class="book-name">${esc(book.bookmaker)}</div>
        <div class="markets">
          <div class="mrow"><div class="mlabel">${esc(labels.h2h)}</div><div class="odds">${mlBtns}</div></div>
          <div class="mrow"><div class="mlabel">${esc(labels.spreads)}</div><div class="odds">${spBtns}</div></div>
          <div class="mrow"><div class="mlabel">${esc(labels.totals)}</div><div class="odds">${totBtns}</div></div>
        </div>
        <p class="meta">Source ${esc(localTime(ts))} · Period ${esc(ev.period || "game")}</p>`;
    }).join("");
    return `<article class="card">
      <div class="match"><div class="teams">${esc(matchup)}</div><div class="meta">${esc(localTime(ev.commence_time))}</div></div>
      ${body || '<p class="empty">No sportsbook prices for this matchup in the snapshot.</p>'}
    </article>`;
  }

  function renderLive() {
    const events = filteredEvents();
    let status = "";
    if (state.sport === "soccer" && !state.soccer) {
      status = `<p class="note">Soccer leagues in this snapshot were sampled in region us. Missing handicap or total prices stay unavailable.</p>`;
    } else {
      const cov = (state.data.coverage || []).find((c) => state.sport === "soccer" ? c.key === state.soccer : c.sport_group && c.sport_group.toLowerCase() === state.sport);
      if (cov) status = `<p class="note">${esc(cov.title)}: ${esc(cov.status)}${cov.empty_does_not_prove_no_coverage ? ". Empty results do not prove coverage is permanently unavailable." : ""}</p>`;
    }
    if (!events.length) {
      $("panel-live").innerHTML = status + `<article class="card"><p class="empty">No saved events for this filter. Documented coverage may still exist outside this snapshot.</p></article>`;
      return;
    }
    $("panel-live").innerHTML = status + events.slice(0, 40).map(renderMatch).join("");
  }

  function renderCompare() {
    const groups = (state.data.compare || []).filter((g) => {
      if (state.sport && g.selector !== state.sport) return false;
      if (state.sport === "soccer" && state.soccer && g.sport_title) {
        const league = (state.data.soccer_leagues || []).find((l) => l.id === state.soccer);
        if (league && g.sport_title !== league.label) return false;
      }
      if (state.search) {
        const q = state.search.toLowerCase();
        const blob = `${g.home_team || ""} ${g.away_team || ""} ${g.player || ""} ${g.selection || ""}`.toLowerCase();
        if (!blob.includes(q)) return false;
      }
      return true;
    }).slice(0, 60);
    const cards = groups.map((g) => {
      const prices = (g.prices || []).map((p) => `<div class="price${p.best_listed ? " best" : ""}">${esc(p.bookmaker)} <b>${esc(money(p))}</b>${p.best_listed ? " · Best listed price" : ""}</div>`).join("");
      const matchup = g.kind === "outright" ? (g.sport_title || "Tournament") : `${g.away_team || ""} @ ${g.home_team || ""}`;
      return `<article class="card">
        <div class="match"><div class="teams">${esc(matchup)}</div><div class="meta">${esc(g.market_label || g.market)} · ${esc(g.player || g.selection)} ${esc(signed(g.line))} · ${esc(g.period)}</div></div>
        <div class="cmp-books">${prices || '<span class="empty">unavailable</span>'}</div>
      </article>`;
    }).join("");
    $("panel-compare").innerHTML = `<p class="note">Compared only when event, market, selection, line, and period match. Different spreads and totals stay separate. Best listed price is the highest American odds in this snapshot, including ties.</p>` + (cards || `<article class="card"><p class="empty">No comparable prices for this filter.</p></article>`);
  }

  function renderProps() {
    const rows = state.data.player_props || [];
    const note = `<p class="note">${esc(state.data.player_props_note || "")} Other player-prop markets are untested.</p>`;
    if (!rows.length) {
      $("panel-props").innerHTML = note + `<article class="card"><p class="empty">No sampled player props in this snapshot.</p></article>`;
      return;
    }
    const byPlayer = new Map();
    for (const row of rows) {
      const key = row.player || "Unknown player";
      byPlayer.set(key, byPlayer.get(key) || []);
      byPlayer.get(key).push(row);
    }
    const cards = [...byPlayer.entries()].map(([player, list]) => {
      const sample = list[0];
      const matchup = `${sample.away_team || ""} @ ${sample.home_team || ""}`;
      const btns = list.map((row) => oddButton(row, {
        label: `${row.selection} · ${row.bookmaker || ""}`.trim(),
        line: row.line,
        event_id: row.event_id,
        market: row.market,
        selection: row.selection,
        player: row.player,
        matchup,
        market_label: row.market_label,
      })).join("");
      return `<article class="card">
        <div class="player">${esc(player)}</div>
        <p class="meta">${esc(matchup)} · ${esc(sample.market_label || "Player market")}</p>
        <div class="odds">${btns}</div>
        <p class="meta">Source ${esc(localTime(sample.source_timestamp))}</p>
      </article>`;
    }).join("");
    $("panel-props").innerHTML = note + cards;
  }

  function renderParlay() {
    $("panel-parlay").innerHTML = `<article class="card">
      <p class="note">Tap odds buttons on Game Odds or Player Props. This preview does not place wagers. Same-game combinations are not given a combined price. Cross-game math is illustrative only.</p>
      <p class="meta">Open the parlay panel at the bottom to review legs, remove picks, or clear all.</p>
    </article>`;
  }

  function renderSlip() {
    const el = $("slip");
    const count = state.legs.length;
    $("slip-count").textContent = String(count);
    el.hidden = count === 0 && !state.slipOpen;
    if (count) el.hidden = false;
    el.classList.toggle("is-open", state.slipOpen || state.tab === "parlay");
    const legs = state.legs.map((leg) => `<div class="leg">
      <div>
        <div><b>${esc(leg.matchup || "")}</b></div>
        <div class="meta">${esc(leg.market_label || leg.market)} · ${esc(leg.player || "")} ${esc(leg.selection || "")} ${esc(signed(leg.line))} · ${esc(leg.bookmaker)} · ${esc(money(leg))}</div>
      </div>
      <button type="button" class="x" data-remove="${esc(leg.id)}" aria-label="Remove">Remove</button>
    </div>`).join("");
    const result = state.parlay;
    let summary = "";
    if (count && count < 2) summary = `<p class="note">Add another leg to calculate illustrative combined odds.</p>`;
    if (result && result.ok) {
      summary = `<p class="ok">${esc(result.label)}</p><p>Combined ${esc(money({ american: result.combined_american, decimal: result.combined_decimal }))}</p>${result.mixed_books ? `<p class="note">${esc(result.mixed_book_note)}</p>` : ""}`;
    } else if (result && !result.ok) {
      summary = `<p class="warn">${esc(result.reason)}</p>`;
    }
    if (state.parlayError) summary = `<p class="warn">${esc(state.parlayError)}</p>` + summary;
    $("slip-body").innerHTML = `
      <p><b>${count} leg${count === 1 ? "" : "s"}</b></p>
      ${legs || "<p class='empty'>No selections.</p>"}
      ${summary}
      <p style="display:flex;gap:8px;flex-wrap:wrap;margin-top:12px">
        <button type="button" class="btn ghost" id="clear-legs">Clear All</button>
      </p>
    `;
  }

  function renderDev() {
    const r = state.data.retrieved || {};
    const cov = (state.data.coverage || []).map((c) => `<article><h3 style="margin:0 0 4px;color:var(--gold2)">${esc(c.title)}</h3><p>${esc(c.status)}${c.event_count != null ? ` · ${c.event_count} events` : ""}</p><p>${esc(JSON.stringify(c.markets))}</p></article>`).join("");
    const est = state.data.monthly_usage_estimate || {};
    $("dev-body").innerHTML = `
      <p>Imported ${esc(r.imported_at || "—")}. Original HTTP ${esc(r.http_requests_used)} / credits ${esc(r.credits_used_from_headers)}. Expansion HTTP ${esc(r.expansion_http)} / credits ${esc(r.expansion_credits)}. Remaining ${esc(r.remaining_credits_header)}.</p>
      <p>${esc(state.data.golf_coverage_note || "")}</p>
      <p>Monthly estimate with reserve: ${esc(est.monthly_with_reserve)} credits. Plan: ${esc(JSON.stringify(est.cheapest_sufficient_under_149))}</p>
      <div class="cov">${cov}</div>
    `;
  }

  function show(tab) {
    state.tab = tab;
    document.querySelectorAll(".tab").forEach((b) => b.classList.toggle("is-on", b.dataset.tab === tab));
    ["live", "compare", "props", "parlay"].forEach((id) => { $(`panel-${id}`).hidden = id !== tab; });
    renderSlip();
  }

  function renderAll() {
    renderFilters();
    renderLive();
    renderCompare();
    renderProps();
    renderParlay();
    renderSlip();
    renderDev();
  }

  document.addEventListener("click", (ev) => {
    const t = ev.target;
    if (!(t instanceof HTMLElement)) return;
    if (t.dataset.tab) show(t.dataset.tab);
    if (t.dataset.sport) { state.sport = t.dataset.sport; state.soccer = ""; state.date = ""; renderAll(); }
    if (t.id === "slip-toggle") { state.slipOpen = !state.slipOpen; renderSlip(); }
    if (t.id === "clear-legs") clearLegs();
    if (t.dataset.remove) removeLeg(t.dataset.remove);
    const btn = t.closest("[data-payload]");
    if (btn instanceof HTMLElement && btn.dataset.payload) {
      try { addLeg(JSON.parse(btn.dataset.payload)); } catch { /* ignore */ }
    }
  });
  document.addEventListener("change", (ev) => {
    const t = ev.target;
    if (!(t instanceof HTMLElement)) return;
    if (t.id === "odds-format") { state.format = t.value; renderAll(); }
    if (t.id === "soccer-league") { state.soccer = t.value; renderAll(); }
    if (t.id === "date-filter") { state.date = t.value; renderAll(); }
    if (t.id === "book-filter") { state.book = t.value; renderAll(); }
  });
  document.addEventListener("input", (ev) => {
    const t = ev.target;
    if (t instanceof HTMLInputElement && t.id === "team-search") { state.search = t.value; renderLive(); renderCompare(); }
  });

  fetch("/api/snapshot").then((r) => r.json()).then((data) => {
    state.data = data;
    renderAll();
    show(state.tab);
  });
})();
