/**
 * Shared SportsGameOdds bookmaker display formatting.
 *
 * The ACTIVE bookmaker universe is always derived dynamically from the live
 * SGO response (SBEvent.bookmakers / SBBookLine.bookmaker). This file only
 * maps raw SGO bookmaker IDs to customer-facing display names — it never
 * hard-codes which books are "active" or "available".
 */

const DISPLAY_NAMES: Record<string, string> = {
  draftkings: "DraftKings",
  fanduel: "FanDuel",
  betmgm: "BetMGM",
  caesars: "Caesars",
  espnbet: "ESPN BET",
  bovada: "Bovada",
  unibet: "Unibet",
  pointsbet: "PointsBet",
  williamhill: "William Hill",
  "1xbet": "1xBet",
  "888sport": "888 Sport",
  ballybet: "Bally Bet",
  barstool: "Barstool",
  betvictor: "Bet Victor",
  betanysports: "BetAnySports",
  betclic: "BetClic",
  betonline: "BetOnline",
  betparx: "BetPARX",
  betrivers: "BetRivers",
  betus: "BetUS",
  betfairexchange: "Betfair Exchange",
  betfairsportsbook: "Betfair Sportsbook",
  betfred: "Betfred",
  betrsportsbook: "Betr Sportsbook",
  betsafe: "Betsafe",
  betsson: "Betsson",
  betway: "Betway",
  bluebet: "BlueBet",
  bodog: "Bodog",
  bookmakereu: "Bookmaker.eu",
  bookmaker: "Bookmaker.eu",
  boomBet: "BoomBet",
  boylesports: "BoyleSports",
  casumo: "Casumo",
  coolbet: "Coolbet",
  coral: "Coral",
  everygame: "Everygame",
  foxbet: "FOX Bet",
  fliff: "Fliff",
  fourwinds: "FourWinds",
  gtbets: "GTbets",
  grosvenor: "Grosvenor",
  hardrockbet: "Hard Rock Bet",
  hotstreak: "HotStreak",
  kalshi: "Kalshi",
  ladbrokes: "Ladbrokes",
  leovegas: "LeoVegas",
  livescorebet: "LiveScore Bet",
  lowvig: "LowVig",
  marathonbet: "Marathon Bet",
  matchbook: "Matchbook",
  mrgreen: "Mr Green",
  mybookie: "MyBookie",
  neds: "Neds",
  nordicbet: "NordicBet",
  northstarbets: "NorthStar Bets",
  novig: "Novig",
  paddypower: "Paddy Power",
  parlayplay: "ParlayPlay",
  polymarket: "Polymarket",
  playup: "PlayUp",
  primesports: "Prime Sports",
  prophetexchange: "Prophet Exchange",
  sisportsbook: "SI Sportsbook",
  skybet: "Sky Bet",
  sleeper: "Sleeper",
  sportsbet: "SportsBet",
  sportsbettingag: "SportsBetting.ag",
  sporttrade: "Sporttrade",
  stake: "Stake",
  sugarhouse: "SugarHouse",
  superbook: "Superbook",
  suprabets: "Suprabets",
  tab: "TAB",
  tabtouch: "TABtouch",
  tipico: "Tipico",
  topsport: "TopSport",
  underdog: "Underdog",
  virginbet: "Virgin Bet",
  windcreek: "Wind Creek",
  wynnbet: "WynnBet",
  thescorebet: "theScore Bet",
  unknown: "Unknown",
};

/** Title-case a raw id as a fallback when no mapping exists. */
function titleCase(s: string): string {
  return s
    .replace(/([a-z0-9])([A-Z])/g, "$1 $2")
    .replace(/[_-]+/g, " ")
    .trim()
    .split(/\s+/)
    .map((w) => (w ? w.charAt(0).toUpperCase() + w.slice(1) : w))
    .join(" ");
}

/** Format a raw SGO bookmaker id for display. */
export function formatBookmakerName(id: string | null | undefined): string {
  if (!id) return "Unknown";
  const key = id.toLowerCase();
  return DISPLAY_NAMES[key] ?? titleCase(id);
}

/**
 * Build the dynamic bookmaker universe from live SGO events.
 * Dedupes and sorts, and drops the "unknown" placeholder book so customers
 * only see real books that SportsGameOdds actually returned.
 */
export function buildBookmakerUniverse(bookmakerLists: string[][]): string[] {
  const seen = new Set<string>();
  for (const list of bookmakerLists) {
    for (const raw of list ?? []) {
      const id = String(raw ?? "").trim();
      if (!id || id.toLowerCase() === "unknown") continue;
      seen.add(id);
    }
  }
  return Array.from(seen).sort((a, b) =>
    formatBookmakerName(a).localeCompare(formatBookmakerName(b)),
  );
}
