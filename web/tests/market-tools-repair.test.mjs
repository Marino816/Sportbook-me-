import assert from "node:assert/strict";
import test from "node:test";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");

function book(id, extra = {}) {
  return {
    bookmaker: id,
    available: true,
    moneyline: null,
    spread: null,
    over_under: null,
    is_main_line: false,
    last_updated: null,
    opening_odds: null,
    opening_spread: null,
    opening_over_under: null,
    close_odds: null,
    close_spread: null,
    close_over_under: null,
    ...extra,
  };
}

function market(partial) {
  return {
    odd_id: "x",
    market_name: "m",
    bet_type: "moneyline",
    side: "home",
    player_id: "",
    player_name: "",
    stat_entity_id: "",
    stat_id: "",
    period_id: "game",
    is_main_line: false,
    fair_odds: null,
    fair_spread: null,
    fair_over_under: null,
    book_odds: null,
    book_spread: null,
    book_over_under: null,
    books: [],
    ...partial,
  };
}

function event(partial) {
  return {
    id: "e1",
    sport: "BASEBALL",
    league: "MLB",
    start_time: null,
    status: "SCHEDULED",
    status_display: "",
    venue: "",
    home_team: { name: "San Francisco Giants", abbreviation: "SF", team_id: "SF" },
    away_team: { name: "Arizona Diamondbacks", abbreviation: "ARI", team_id: "ARI" },
    home_score: null,
    away_score: null,
    period: null,
    players: [],
    markets: [],
    bookmakers: [],
    ...partial,
  };
}

test("periodGroup treats reg as full game", async () => {
  const mv = await import("../src/lib/market-view.ts");
  assert.equal(mv.periodGroup("game"), "full");
  assert.equal(mv.periodGroup("reg"), "full");
  assert.equal(mv.periodGroup("1h"), "1h");
  assert.equal(mv.periodGroup("1q"), "quarter");
});

test("main-line filter does not hide priced core markets when isMainLine is omitted", async () => {
  const mv = await import("../src/lib/market-view.ts");
  const markets = [
    market({
      bet_type: "moneyline",
      side: "home",
      is_main_line: false,
      books: [book("draftkings", { moneyline: -120 })],
    }),
    market({
      bet_type: "moneyline",
      side: "away",
      is_main_line: false,
      books: [book("fanduel", { moneyline: 110 })],
    }),
  ];
  const filtered = mv.filterMarkets(markets, { lineMode: "main", period: "full" });
  assert.equal(filtered.length, 2);
  const rows = mv.buildBookmakerRows(filtered);
  assert.ok(rows.length >= 1);
  assert.ok(rows.some((r) => r.homeML === -120 || r.awayML === 110));
});

test("true provider-empty vs priced extraction", async () => {
  const mv = await import("../src/lib/market-view.ts");
  const empty = event({ markets: [market({ books: [] })] });
  const priced = event({
    markets: [
      market({
        bet_type: "moneyline",
        side: "home",
        books: [book("draftkings", { moneyline: -110 })],
      }),
    ],
  });
  assert.equal(mv.eventHasActivePrices(empty), false);
  assert.equal(mv.eventHasActivePrices(priced), true);
  const view = mv.marketsForExpandedEvent(empty, { lineMode: "main", period: "full" });
  assert.equal(view.providerEmpty, true);
  assert.equal(mv.buildBookmakerRows(view.markets).length, 0);
});

test("two-page window never exceeds two pages and stays at normal density", async () => {
  const mv = await import("../src/lib/market-view.ts");
  const items = Array.from({ length: 15 }, (_, i) => i);
  const p1 = mv.twoPageWindow(items, 1);
  const p2 = mv.twoPageWindow(items, 2);
  assert.equal(p1.pages, 2);
  assert.equal(p2.pages, 2);
  assert.equal(p1.pageSize, 12);
  assert.deepEqual([...p1.items, ...p2.items], items);
  const board30 = Array.from({ length: 30 }, (_, i) => i);
  const b = mv.twoPageWindow(board30, 1);
  assert.equal(b.pages, 2);
  assert.ok(b.pageSize <= mv.MAX_PAGE_SIZE);
  assert.equal(b.pageSize, 15);
  assert.equal(mv.twoPageWindow(board30, 3).page, 2);
  const catalog = Array.from({ length: 55 }, (_, i) => i);
  const dense = mv.twoPageWindow(catalog, 1, 12, { allowDense: true });
  assert.equal(dense.pages, 2);
  assert.equal(dense.pageSize, 28);
  assert.equal(dense.total, 55);
});

test("default Live Odds board is live + today + nearest fill, search finds distant", async () => {
  const mv = await import("../src/lib/market-view.ts");
  const now = Date.parse("2026-08-29T18:00:00");
  const localHours = (h) => {
    const d = new Date(now);
    d.setHours(h, 0, 0, 0);
    return d.toISOString();
  };
  const plusDays = (days) => {
    const d = new Date(now);
    d.setDate(d.getDate() + days);
    d.setHours(19, 0, 0, 0);
    return d.toISOString();
  };
  const live = event({
    id: "live1",
    status: "LIVE",
    start_time: localHours(14),
    home_team: { name: "Boston Red Sox", abbreviation: "BOS", team_id: "BOS" },
    away_team: { name: "Tampa Bay Rays", abbreviation: "TB", team_id: "TB" },
  });
  const today = event({
    id: "today1",
    status: "SCHEDULED",
    start_time: localHours(20),
    home_team: { name: "Cleveland Guardians", abbreviation: "CLE", team_id: "CLE" },
    away_team: { name: "New York Yankees", abbreviation: "NYY", team_id: "NYY" },
  });
  const fillers = Array.from({ length: 30 }, (_, i) =>
    event({
      id: `near-${i}`,
      status: "SCHEDULED",
      start_time: plusDays(1 + i),
      home_team: { name: `Fill Home ${i}`, abbreviation: `FH${i}`, team_id: `FH${i}` },
      away_team: { name: `Fill Away ${i}`, abbreviation: `FA${i}`, team_id: `FA${i}` },
    }),
  );
  const distant = event({
    id: "far1",
    status: "SCHEDULED",
    start_time: plusDays(90),
    home_team: { name: "Los Angeles Dodgers", abbreviation: "LAD", team_id: "LAD" },
    away_team: { name: "San Diego Padres", abbreviation: "SD", team_id: "SD" },
  });
  const finalGame = event({
    id: "final1",
    status: "FINAL",
    start_time: localHours(12),
    home_team: { name: "Atlanta Braves", abbreviation: "ATL", team_id: "ATL" },
    away_team: { name: "Philadelphia Phillies", abbreviation: "PHI", team_id: "PHI" },
  });
  const pool = [live, today, distant, finalGame, ...fillers];
  const board = mv.selectLiveOddsBoard(pool, { now });
  assert.equal(board.items.length, mv.BOARD_FILL_TO);
  assert.ok(board.items.some((e) => e.id === "live1"));
  assert.ok(board.items.some((e) => e.id === "today1"));
  assert.ok(!board.items.some((e) => e.id === "far1" || e.id === "final1"));
  const found = mv.selectLiveOddsBoard(pool, { now, search: "Dodgers" });
  assert.equal(found.items.length, 1);
  assert.equal(found.items[0].id, "far1");
  const nflDump = Array.from({ length: 266 }, (_, i) =>
    event({
      id: `nfl-${i}`,
      league: "NFL",
      status: "SCHEDULED",
      start_time: plusDays(3 + (i % 60)),
      home_team: { name: `Home ${i}`, abbreviation: `H${i}`, team_id: `H${i}` },
      away_team: { name: `Away ${i}`, abbreviation: `A${i}`, team_id: `A${i}` },
    }),
  );
  const nflBoard = mv.selectLiveOddsBoard(nflDump, { now });
  assert.equal(nflBoard.items.length, mv.BOARD_FILL_TO);
  assert.equal(nflBoard.hidden, 266 - mv.BOARD_FILL_TO);
  const paged = mv.twoPageWindow(nflBoard.items, 1);
  assert.equal(paged.pages, 2);
  assert.equal(paged.pageSize, 12);
});

test("bookmaker catalog stays 55 and aliases only collapse proven sgo ids", async () => {
  const catalog = JSON.parse(readFileSync(join(root, "src/lib/sbme-55-platforms.json"), "utf8"));
  assert.equal(catalog.length, 55);
  const plat = await import("../src/lib/platforms.ts");
  assert.equal(plat.SBME_55_COUNT, 55);
  assert.equal(plat.SBME_55_PLATFORMS.length, 55);
  assert.equal(plat.canonicalBookmakerId("bookmaker"), "bookmakereu");
  assert.equal(plat.canonicalBookmakerId("bookmakereu"), "bookmakereu");
  assert.equal(plat.canonicalBookmakerId("betrivers"), "betrivers");
  assert.equal(plat.canonicalBookmakerId("sugarhouse"), "sugarhouse");
  assert.notEqual(plat.canonicalBookmakerId("betrivers"), plat.canonicalBookmakerId("sugarhouse"));
  assert.equal(plat.canonicalBookmakerId("unknown"), "");
  const bet365 = plat.SBME_55_PLATFORMS.find((p) => p.id === "bet365");
  const pinnacle = plat.SBME_55_PLATFORMS.find((p) => p.id === "pinnacle");
  const circa = plat.SBME_55_PLATFORMS.find((p) => p.id === "circa");
  assert.ok(bet365 && pinnacle && circa);
  assert.deepEqual(bet365.sgo_ids, []);
  assert.deepEqual(pinnacle.sgo_ids, []);
  assert.deepEqual(circa.sgo_ids, []);
});

test("arbitrage canonical key dedupes reversed book permutations and keeps best", async () => {
  const arb = await import("../src/lib/arbitrage.ts");
  const evt = event({
    markets: [
      market({
        odd_id: "points-home-game-ml-home",
        bet_type: "moneyline",
        side: "home",
        period_id: "game",
        books: [
          book("fanduel", { moneyline: 150 }),
          book("nordicbet", { moneyline: 140 }),
        ],
      }),
      market({
        odd_id: "points-away-game-ml-away",
        bet_type: "moneyline",
        side: "away",
        period_id: "game",
        books: [
          book("betrivers", { moneyline: 150 }),
          book("sugarhouse", { moneyline: 130 }),
        ],
      }),
    ],
  });
  const opps = arb.scanArbitrage([evt]);
  const mls = opps.filter((o) => o.market === "moneyline");
  assert.equal(mls.length, 1);
  assert.equal(mls[0].home_book, "fanduel");
  assert.equal(mls[0].away_book, "betrivers");
  const math = arb.twoWayArb(150, 150);
  assert.ok(math);
  assert.equal(mls[0].arb_pct, math.arb_pct);
  assert.equal(mls[0].payout, math.payout);
});

test("arbitrage keeps distinct markets periods and lines", async () => {
  const arb = await import("../src/lib/arbitrage.ts");
  const evt = event({
    markets: [
      market({
        bet_type: "moneyline",
        side: "home",
        period_id: "game",
        books: [book("fanduel", { moneyline: 150 })],
      }),
      market({
        bet_type: "moneyline",
        side: "away",
        period_id: "game",
        books: [book("draftkings", { moneyline: 150 })],
      }),
      market({
        bet_type: "moneyline",
        side: "home",
        period_id: "1h",
        books: [book("fanduel", { moneyline: 160 })],
      }),
      market({
        bet_type: "moneyline",
        side: "away",
        period_id: "1h",
        books: [book("draftkings", { moneyline: 160 })],
      }),
      market({
        bet_type: "total",
        side: "over",
        period_id: "game",
        books: [book("fanduel", { moneyline: 150, over_under: 8.5 })],
      }),
      market({
        bet_type: "total",
        side: "under",
        period_id: "game",
        books: [book("draftkings", { moneyline: 150, over_under: 8.5 })],
      }),
      market({
        bet_type: "total",
        side: "over",
        period_id: "game",
        books: [book("fanduel", { moneyline: 150, over_under: 9.5 })],
      }),
      market({
        bet_type: "total",
        side: "under",
        period_id: "game",
        books: [book("draftkings", { moneyline: 150, over_under: 9.5 })],
      }),
    ],
  });
  const opps = arb.scanArbitrage([evt]);
  const keys = opps.map((o) => o.key).sort();
  assert.equal(keys.length, 4);
  assert.ok(keys.some((k) => k.includes("moneyline") && k.includes("game")));
  assert.ok(keys.some((k) => k.includes("moneyline") && k.includes("1h")));
  assert.ok(keys.some((k) => k.includes("|total|") && k.includes("8.50")));
  assert.ok(keys.some((k) => k.includes("|total|") && k.includes("9.50")));
});

test("invalid arbitrage (juice) is rejected", async () => {
  const arb = await import("../src/lib/arbitrage.ts");
  assert.equal(arb.twoWayArb(-110, -110), null);
  const evt = event({
    markets: [
      market({ bet_type: "moneyline", side: "home", books: [book("fanduel", { moneyline: -110 })] }),
      market({ bet_type: "moneyline", side: "away", books: [book("draftkings", { moneyline: -110 })] }),
    ],
  });
  assert.equal(arb.scanArbitrage([evt]).length, 0);
});

test("same catalog alias does not create a fake two-book arb", async () => {
  const arb = await import("../src/lib/arbitrage.ts");
  const evt = event({
    markets: [
      market({ bet_type: "moneyline", side: "home", books: [book("bookmaker", { moneyline: 150 })] }),
      market({ bet_type: "moneyline", side: "away", books: [book("bookmakereu", { moneyline: 150 })] }),
    ],
  });
  assert.equal(arb.scanArbitrage([evt]).length, 0);
});

test("arbitrage search and sport filter operate on the full deduped set", async () => {
  const arb = await import("../src/lib/arbitrage.ts");
  const mv = await import("../src/lib/market-view.ts");
  const mlb = event({
    id: "mlb1",
    league: "MLB",
    sport: "BASEBALL",
    home_team: { name: "Cleveland Guardians", abbreviation: "CLE", team_id: "CLE" },
    away_team: { name: "New York Yankees", abbreviation: "NYY", team_id: "NYY" },
    markets: [
      market({ bet_type: "moneyline", side: "home", books: [book("fanduel", { moneyline: 150 })] }),
      market({ bet_type: "moneyline", side: "away", books: [book("draftkings", { moneyline: 150 })] }),
    ],
  });
  const nfl = event({
    id: "nfl1",
    league: "NFL",
    sport: "FOOTBALL",
    home_team: { name: "San Francisco 49ers", abbreviation: "SF", team_id: "SF" },
    away_team: { name: "Arizona Cardinals", abbreviation: "ARI", team_id: "ARI" },
    markets: [
      market({ bet_type: "moneyline", side: "home", books: [book("fanduel", { moneyline: 160 })] }),
      market({ bet_type: "moneyline", side: "away", books: [book("draftkings", { moneyline: 160 })] }),
    ],
  });
  const all = arb.scanArbitrage([mlb, nfl]);
  assert.equal(all.length, 2);
  assert.equal(arb.filterOpportunities(all, { sport: "NFL" }).length, 1);
  assert.equal(arb.filterOpportunities(all, { search: "ARI" }).length, 1);
  const paged = mv.twoPageWindow(all, 1);
  assert.ok(paged.pages <= 2);
});

test("arbitrage board keeps strongest unique opps and reports remainder", async () => {
  const arb = await import("../src/lib/arbitrage.ts");
  const mv = await import("../src/lib/market-view.ts");
  const events = Array.from({ length: 40 }, (_, i) => {
    const home = 150 + i;
    const away = 150 + i;
    return event({
      id: `e${i}`,
      league: "NFL",
      home_team: { name: `Home ${i}`, abbreviation: `H${i}`, team_id: `H${i}` },
      away_team: { name: `Away ${i}`, abbreviation: `A${i}`, team_id: `A${i}` },
      markets: [
        market({ bet_type: "moneyline", side: "home", books: [book("fanduel", { moneyline: home })] }),
        market({ bet_type: "moneyline", side: "away", books: [book("draftkings", { moneyline: away })] }),
      ],
    });
  });
  const opps = arb.scanArbitrage(events);
  assert.equal(opps.length, 40);
  assert.ok(opps[0].arb_pct >= opps[opps.length - 1].arb_pct);
  const capped = mv.capCustomerList(opps);
  assert.equal(capped.items.length, mv.MAX_BOARD_ITEMS);
  assert.equal(capped.hidden, 10);
  assert.equal(capped.items[0].event_id, opps[0].event_id);
  const paged = mv.twoPageWindow(capped.items, 1);
  assert.equal(paged.pages, 2);
  assert.ok(paged.pageSize <= mv.MAX_PAGE_SIZE);
});

test("pages do not hard-code the old empty copy or cartesian scanner", () => {
  const live = readFileSync(join(root, "src/app/market-tools/live-odds/page.tsx"), "utf8");
  const books = readFileSync(join(root, "src/app/market-tools/bookmakers/page.tsx"), "utf8");
  const arb = readFileSync(join(root, "src/app/market-tools/arbitrage/page.tsx"), "utf8");
  assert.match(live, /twoPageWindow/);
  assert.match(live, /selectLiveOddsBoard/);
  assert.match(live, /SportsGameOdds currently has no active bookmaker prices/);
  assert.doesNotMatch(live, /No bookmaker data available for this event/);
  assert.match(books, /twoPageWindow/);
  assert.match(books, /allowDense: true/);
  assert.match(books, /Open Live Odds/);
  assert.match(books, /marketsOpen/);
  assert.match(arb, /scanArbitrage/);
  assert.match(arb, /capCustomerList/);
  assert.doesNotMatch(arb, /found\.slice\(0, 30\)/);
});
