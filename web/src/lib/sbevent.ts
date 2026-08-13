/**
 * Shared SB Event TypeScript interface — ONE shape consumed by all pages.
 *
 * Matches the canonical backend /api/sgo/events SBEvent JSON output
 * built from the official SportsGameOdds SDK models.
 */
export interface SBTeam {
  name: string;
  abbreviation: string;
  team_id: string;
}

export interface SBPlayer {
  player_id: string;
  name: string;
  team_id: string;
  position: string;
}

export interface SBBookLine {
  bookmaker: string;
  available: boolean;
  moneyline: number | null;
  spread: number | null;
  over_under: number | null;
  is_main_line: boolean;
}

export interface SBMarket {
  odd_id: string;
  market_name: string;
  bet_type: string;
  side: string;
  player_id: string;
  player_name: string;
  stat_entity_id: string;
  stat_id: string;
  fair_odds: number | null;
  fair_spread: number | null;
  fair_over_under: number | null;
  books: SBBookLine[];
}

export interface SBEvent {
  id: string;
  sport: string;
  league: string;
  start_time: string | null;
  status: string;
  status_display: string;
  venue: string;
  home_team: SBTeam;
  away_team: SBTeam;
  home_score: number | null;
  away_score: number | null;
  period: string | null;
  players: SBPlayer[];
  markets: SBMarket[];
  bookmakers: string[];
}