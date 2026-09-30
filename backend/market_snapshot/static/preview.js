(() => {
  const state = { data: null, tab: "live", selected: new Set() };
  const $ = (id) => document.getElementById(id);
  const esc = (v) => String(v ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const moneyline = (n) => (n == null ? '<span class="null">unavailable</span>' : (n > 0 ? `+${n}` : String(n)));

  function rowsHtml(headers, body) {
    return `<table><thead><tr>${headers.map((h) => `<th>${h}</th>`).join("")}</tr></thead><tbody>${body}</tbody></table>`;
  }

  function renderCoverage() {
    const cov = state.data.coverage || {};
    const cards = Object.entries(cov).map(([sport, c]) => {
      const mk = ["h2h", "spreads", "totals"].map((m) => `${m}: ${c[`featured_${m}`] ? "present" : "unavailable"}`).join(" · ");
      return `<article class="cov"><h3>${esc(sport)}</h3><p>${c.event_count || 0} events · ${c.price_rows || 0} prices</p><p>${esc(mk)}</p></article>`;
    }).join("");
    $("coverage").innerHTML = cards;
  }

  function renderLive() {
    const rows = (state.data.live_odds || []).slice(0, 250);
    const body = rows.map((r) => `<tr>
      <td>${esc(r.sport_title)}</td>
      <td>${esc(r.away_team)} @ ${esc(r.home_team)}</td>
      <td>${esc(r.bookmaker)}</td>
      <td>${esc(r.market)}</td>
      <td>${esc(r.selection)}</td>
      <td>${r.line == null ? "—" : esc(r.line)}</td>
      <td>${moneyline(r.american)}</td>
      <td>${r.decimal == null ? "—" : r.decimal}</td>
      <td>${esc(r.source_timestamp)}</td>
    </tr>`).join("") || `<tr><td colspan="9" class="null">No featured prices in this snapshot.</td></tr>`;
    $("panel-live").innerHTML = rowsHtml(["Sport", "Game", "Book", "Market", "Selection", "Line", "American", "Decimal", "Source time"], body);
  }

  function renderCompare() {
    const groups = (state.data.compare || []).slice(0, 120);
    const body = groups.map((g) => {
      const prices = (g.prices || []).map((p) => `${esc(p.bookmaker)} ${p.american > 0 ? "+" : ""}${p.american}`).join(" · ") || "unavailable";
      return `<tr>
        <td>${esc(g.sport_title)}</td>
        <td>${esc(g.away_team)} @ ${esc(g.home_team)}</td>
        <td>${esc(g.market)}</td>
        <td>${esc(g.player || "")} ${esc(g.selection)}</td>
        <td>${g.line == null ? "—" : esc(g.line)}</td>
        <td>${esc(g.period)}</td>
        <td>${g.book_count}</td>
        <td>${prices}</td>
      </tr>`;
    }).join("");
    $("panel-compare").innerHTML = `<p class="note">Grouped by event, market, selection, line, and period. Missing book prices stay unavailable.</p>` +
      rowsHtml(["Sport", "Game", "Market", "Selection", "Line", "Period", "Books", "Prices"], body);
  }

  function renderProps() {
    const rows = state.data.player_props || [];
    const note = esc(state.data.player_props_note || "Player props untested beyond this sample.");
    if (!rows.length) {
      $("panel-props").innerHTML = `<p class="note">${note}</p><p class="note">Requested market: ${esc(state.data.player_props_requested_market || "none")}. Coverage outside this event is unknown.</p>`;
      return;
    }
    const body = rows.map((r) => `<tr>
      <td>${esc(r.player || "—")}</td>
      <td>${esc(r.market)}</td>
      <td>${esc(r.selection)}</td>
      <td>${r.line == null ? "—" : esc(r.line)}</td>
      <td>${esc(r.bookmaker)}</td>
      <td>${moneyline(r.american)}</td>
      <td>${esc(r.source_timestamp)}</td>
    </tr>`).join("");
    $("panel-props").innerHTML = `<p class="note">${note}</p>` +
      rowsHtml(["Player", "Market", "Side", "Line", "Book", "American", "Source time"], body);
  }

  function renderParlay() {
    const pool = (state.data.parlay_pool || []).slice(0, 80);
    const opts = pool.map((p) => `<label><input type="checkbox" data-leg="${esc(p.id)}" /> ${esc(p.label)} (${p.american > 0 ? "+" : ""}${p.american})</label>`).join("");
    $("panel-parlay").innerHTML = `<div class="parlay-box">
      <p class="note">${esc(state.data.parlay_note)}</p>
      <p><button type="button" class="cmd" id="parlay-go">Calculate analytical parlay</button></p>
      <div id="parlay-out"></div>
      ${opts || '<p class="null">No quoted selections in this snapshot.</p>'}
    </div>`;
  }

  function show(tab) {
    state.tab = tab;
    document.querySelectorAll(".tab").forEach((b) => b.classList.toggle("is-on", b.dataset.tab === tab));
    ["live", "compare", "props", "parlay"].forEach((id) => {
      $(`panel-${id}`).hidden = id !== tab;
    });
  }

  async function calcParlay() {
    const ids = [...document.querySelectorAll("input[data-leg]:checked")].map((el) => el.dataset.leg);
    const res = await fetch("/api/parlay", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ leg_ids: ids }),
    });
    const data = await res.json();
    const el = $("parlay-out");
    if (!data.ok) {
      el.innerHTML = `<p class="warn">${esc(data.reason)}</p>`;
      return;
    }
    el.innerHTML = `<p>Analytical combined American: <b>${data.combined_american}</b> · decimal ${data.combined_decimal}</p>
      <p class="note">${esc(data.note)}</p>
      ${data.same_game_warning ? `<p class="warn">${esc(data.same_game_warning)}</p>` : ""}`;
  }

  document.addEventListener("click", (ev) => {
    const t = ev.target;
    if (!(t instanceof HTMLElement)) return;
    if (t.dataset.tab) show(t.dataset.tab);
    if (t.id === "parlay-go") calcParlay();
  });

    const params = new URLSearchParams(location.search);
    const firstTab = params.get("tab") || "live";
    fetch("/api/snapshot").then((r) => r.json()).then((data) => {
    state.data = data;
    const r = data.retrieved || {};
    $("stamp").textContent = `${data.not_live_label}. Imported ${r.imported_at || "—"}. HTTP ${r.http_requests_used ?? "—"} · credits ${r.credits_used_from_headers ?? "—"}.`;
    renderCoverage();
    renderLive();
    renderCompare();
    renderProps();
    renderParlay();
    show(firstTab);
  });
})();
