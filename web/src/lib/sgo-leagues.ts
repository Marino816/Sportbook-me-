/** Confirmed SportsGameOdds Rookie leagues (live GET /v2/leagues/, 2026-08-28). */

export const ROOKIE_LEAGUES = [
  { leagueID: "MLB", label: "MLB", sportID: "BASEBALL" },
  { leagueID: "NBA", label: "NBA", sportID: "BASKETBALL" },
  { leagueID: "NCAAB", label: "NCAAB", sportID: "BASKETBALL" },
  { leagueID: "WNBA", label: "WNBA", sportID: "BASKETBALL" },
  { leagueID: "NCAAF", label: "NCAAF", sportID: "FOOTBALL" },
  { leagueID: "NFL", label: "NFL", sportID: "FOOTBALL" },
  { leagueID: "EHF_EURO", label: "EHF", sportID: "HANDBALL" },
  { leagueID: "NHL", label: "NHL", sportID: "HOCKEY" },
  { leagueID: "UFC", label: "UFC", sportID: "MMA" },
  { leagueID: "BUNDESLIGA", label: "Bundesliga", sportID: "SOCCER" },
  { leagueID: "EPL", label: "EPL", sportID: "SOCCER" },
  { leagueID: "FR_LIGUE_1", label: "Ligue 1", sportID: "SOCCER" },
  { leagueID: "INTERNATIONAL_SOCCER", label: "Intl Soccer", sportID: "SOCCER" },
  { leagueID: "IT_SERIE_A", label: "Serie A", sportID: "SOCCER" },
  { leagueID: "LA_LIGA", label: "La Liga", sportID: "SOCCER" },
  { leagueID: "MLS", label: "MLS", sportID: "SOCCER" },
  { leagueID: "UEFA_CHAMPIONS_LEAGUE", label: "UCL", sportID: "SOCCER" },
] as const;

export const ROOKIE_LEAGUE_IDS = ROOKIE_LEAGUES.map((row) => row.leagueID);

export const SOCCER_LEAGUE_IDS = ROOKIE_LEAGUES.filter((row) => row.sportID === "SOCCER").map(
  (row) => row.leagueID,
);

const ALIASES: Record<string, string> = {
  UCL: "UEFA_CHAMPIONS_LEAGUE",
  CHAMPIONS_LEAGUE: "UEFA_CHAMPIONS_LEAGUE",
  LIGUE_1: "FR_LIGUE_1",
  LIGUE1: "FR_LIGUE_1",
  SERIE_A: "IT_SERIE_A",
  SERIEA: "IT_SERIE_A",
  LALIGA: "LA_LIGA",
  PREMIER_LEAGUE: "EPL",
  PREMIER: "EPL",
  INTL_SOCCER: "INTERNATIONAL_SOCCER",
};

export function normalizeLeagueId(league: string | null | undefined): string {
  const raw = (league || "MLB").trim().toUpperCase().replace(/[\s-]+/g, "_");
  return ALIASES[raw] || raw;
}

export const MARKET_TOOL_LEAGUES = ROOKIE_LEAGUE_IDS;

export function leagueLabel(leagueId: string): string {
  const row = ROOKIE_LEAGUES.find((r) => r.leagueID === leagueId);
  return row?.label || leagueId;
}
