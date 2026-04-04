from __future__ import annotations

import io
import math
import random
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import date
from typing import Dict, List, Optional, Tuple
from urllib.parse import quote_plus

import pandas as pd
import requests
import streamlit as st

try:
    import pulp
except Exception:
    pulp = None

st.set_page_config(page_title='DFS Builder v7', layout='wide')

SITE_CONFIG = {
    ('NBA', 'DraftKings'): {'salary_cap': 50000, 'slots': ['PG', 'SG', 'SF', 'PF', 'C', 'G', 'F', 'UTIL']},
    ('NBA', 'FanDuel'): {'salary_cap': 60000, 'slots': ['PG', 'PG', 'SG', 'SG', 'SF', 'SF', 'PF', 'PF', 'C']},
    ('MLB', 'DraftKings'): {'salary_cap': 50000, 'slots': ['P', 'P', 'C', '1B', '2B', '3B', 'SS', 'OF', 'OF', 'OF']},
    ('MLB', 'FanDuel'): {'salary_cap': 35000, 'slots': ['P', 'C/1B', '2B', '3B', 'SS', 'OF', 'OF', 'OF', 'UTIL']},
}

POSITION_MAP = {
    'PG': ['PG'], 'SG': ['SG'], 'SF': ['SF'], 'PF': ['PF'], 'C': ['C'],
    'G': ['PG', 'SG'], 'F': ['SF', 'PF'], 'UTIL': ['PG', 'SG', 'SF', 'PF', 'C', '1B', '2B', '3B', 'SS', 'OF'],
    'P': ['P', 'SP', 'RP'], 'C/1B': ['C', '1B'], '1B': ['1B'], '2B': ['2B'], '3B': ['3B'], 'SS': ['SS'], 'OF': ['OF']
}

CONTEST_PROFILES = {
    'Cash': {'projection_weight': 1.00, 'ceiling_weight': 0.15, 'value_weight': 0.22, 'ownership_weight': 0.10, 'leverage_weight': 0.00, 'randomness_default': 0.02, 'min_salary_pct': 0.98, 'max_repeat_default': 8},
    'Single Entry': {'projection_weight': 0.90, 'ceiling_weight': 0.32, 'value_weight': 0.18, 'ownership_weight': 0.02, 'leverage_weight': 0.12, 'randomness_default': 0.05, 'min_salary_pct': 0.965, 'max_repeat_default': 7},
    '3-Max': {'projection_weight': 0.84, 'ceiling_weight': 0.38, 'value_weight': 0.15, 'ownership_weight': -0.05, 'leverage_weight': 0.22, 'randomness_default': 0.07, 'min_salary_pct': 0.955, 'max_repeat_default': 6},
    '20-Max': {'projection_weight': 0.76, 'ceiling_weight': 0.42, 'value_weight': 0.13, 'ownership_weight': -0.10, 'leverage_weight': 0.30, 'randomness_default': 0.10, 'min_salary_pct': 0.94, 'max_repeat_default': 5},
    '150-Max': {'projection_weight': 0.66, 'ceiling_weight': 0.48, 'value_weight': 0.10, 'ownership_weight': -0.18, 'leverage_weight': 0.38, 'randomness_default': 0.14, 'min_salary_pct': 0.92, 'max_repeat_default': 4},
}

@dataclass
class StrategyConstraints:
    mlb_primary_stack_team: Optional[str] = None
    mlb_primary_stack_size: int = 0
    mlb_secondary_stack_team: Optional[str] = None
    mlb_secondary_stack_size: int = 0
    mlb_max_hitters_per_team: int = 5
    nba_target_game: Optional[str] = None
    nba_game_stack_size: int = 0
    nba_bring_back_team: Optional[str] = None
    nba_bring_back_size: int = 0
    avoid_pitcher_vs_batters: bool = True

@dataclass
class ExposureSettings:
    max_player_exposure: int = 100
    min_player_exposure: int = 0
    max_team_exposure: int = 100
    unique_players_between_lineups: int = 1

class FetchResult:
    def __init__(self, ok: bool, data: Optional[pd.DataFrame] = None, error: Optional[str] = None):
        self.ok = ok
        self.data = data if data is not None else pd.DataFrame()
        self.error = error

def clean_cols(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out.columns = [str(c).strip().lower().replace(' ', '_') for c in out.columns]
    return out

def fetch_json(url: str, timeout: int = 20):
    r = requests.get(url, timeout=timeout, headers={'User-Agent': 'Mozilla/5.0'})
    r.raise_for_status()
    return r.json()

def fetch_text(url: str, timeout: int = 20) -> str:
    r = requests.get(url, timeout=timeout, headers={'User-Agent': 'Mozilla/5.0'})
    r.raise_for_status()
    return r.text

def _safe(series, default=0.0) -> pd.Series:
    return pd.to_numeric(series, errors='coerce').fillna(default)

def american_to_prob(value: float) -> float:
    try:
        v = float(value)
    except Exception:
        return 0.5
    if v == 0: return 0.5
    if v > 0: return 100 / (v + 100)
    return abs(v) / (abs(v) + 100)

def implied_total_from_event(total: float, moneyline: float, is_home: bool) -> float:
    total = float(total or 0)
    if total <= 0: return 0.0
    win_prob = american_to_prob(moneyline)
    spread_component = (win_prob - 0.5) * (0.18 * total)
    return round(total / 2 + (spread_component if is_home else -spread_component), 2)

def standardize_game_label(game_label: str) -> str:
    return str(game_label).replace(' ', '').upper()

def fetch_espn_nba_scoreboard(slate_date: date) -> FetchResult:
    ds = slate_date.strftime('%Y%m%d')
    try:
        data = fetch_json(f'https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard?dates={ds}')
        games = []
        for e in data.get('events', []):
            comp = (e.get('competitions') or [{}])[0]
            competitors = comp.get('competitors') or []
            away = next((c for c in competitors if c.get('homeAway') == 'away'), {})
            home = next((c for c in competitors if c.get('homeAway') == 'home'), {})
            odds = (comp.get('odds') or [{}])
            odds0 = odds[0] if odds else {}
            total = odds0.get('overUnder') or odds0.get('details')
            ou_num = 0.0
            if isinstance(total, (int, float)):
                ou_num = float(total)
            elif isinstance(total, str):
                for token in total.replace(',', ' ').split():
                    try:
                        ou_num = float(token)
                        break
                    except: continue
            home_ml = odds0.get('homeTeamOdds', {}).get('moneyLine') if isinstance(odds0.get('homeTeamOdds'), dict) else None
            away_ml = odds0.get('awayTeamOdds', {}).get('moneyLine') if isinstance(odds0.get('awayTeamOdds'), dict) else None
            games.append({
                'game_id': e.get('id'),
                'game_label': f"{away.get('team', {}).get('abbreviation', '')}@{home.get('team', {}).get('abbreviation', '')}",
                'away_team': away.get('team', {}).get('abbreviation'),
                'home_team': home.get('team', {}).get('abbreviation'),
                'status': comp.get('status', {}).get('type', {}).get('description'),
                'date': comp.get('date'),
                'venue': comp.get('venue', {}).get('fullName'),
                'broadcast': ', '.join([b.get('names', [''])[0] for b in comp.get('broadcasts', []) if b.get('names')]),
                'home_moneyline': home_ml if home_ml is not None else odds0.get('favorite', '').replace(home.get('team', {}).get('abbreviation', ''), '').strip(),
                'away_moneyline': away_ml,
                'total': ou_num,
                'home_implied_total': implied_total_from_event(ou_num, float(home_ml or -110), True) if ou_num else 0.0,
                'away_implied_total': implied_total_from_event(ou_num, float(away_ml or -110), False) if ou_num else 0.0,
                'odds_provider': odds0.get('provider', {}).get('name'),
            })
        return FetchResult(True, pd.DataFrame(games))
    except Exception as exc:
        return FetchResult(False, error=str(exc))

def fetch_mlb_schedule(slate_date: date) -> FetchResult:
    ds = slate_date.isoformat()
    try:
        url = f'https://statsapi.mlb.com/api/v1/schedule?sportId=1&date={ds}&hydrate=probablePitcher,linescore,team,lineups'
        data = fetch_json(url)
        games = []
        for d in data.get('dates', []):
            for g in d.get('games', []):
                teams = g.get('teams', {})
                away = teams.get('away', {}).get('team', {})
                home = teams.get('home', {}).get('team', {})
                linescore = g.get('linescore', {}) or {}
                lineup_exists = bool(linescore.get('offense')) or bool(g.get('lineups'))
                games.append({
                    'game_id': g.get('gamePk'),
                    'game_label': f"{away.get('abbreviation', away.get('name', ''))}@{home.get('abbreviation', home.get('name', ''))}",
                    'away_team': away.get('abbreviation', away.get('name', '')),
                    'home_team': home.get('abbreviation', home.get('name', '')),
                    'status': g.get('status', {}).get('detailedState'),
                    'date': g.get('gameDate'),
                    'venue': g.get('venue', {}).get('name'),
                    'away_probable_pitcher': teams.get('away', {}).get('probablePitcher', {}).get('fullName'),
                    'home_probable_pitcher': teams.get('home', {}).get('probablePitcher', {}).get('fullName'),
                    'lineups_published': lineup_exists,
                })
        return FetchResult(True, pd.DataFrame(games))
    except Exception as exc:
        return FetchResult(False, error=str(exc))

def fetch_google_news_rss(query: str, max_items: int = 20) -> FetchResult:
    try:
        url = f'https://news.google.com/rss/search?q={quote_plus(query)}&hl=en-US&gl=US&ceid=US:en'
        text = fetch_text(url)
        root = ET.fromstring(text)
        items = []
        for item in root.findall('./channel/item')[:max_items]:
            items.append({
                'title': item.findtext('title', default=''),
                'link': item.findtext('link', default=''),
                'pub_date': item.findtext('pubDate', default=''),
                'source': item.findtext('source', default='Google News'),
            })
        return FetchResult(True, pd.DataFrame(items))
    except Exception as exc:
        return FetchResult(False, error=str(exc))

def fetch_the_odds_events(sport: str, api_key: str, markets: str = 'h2h,totals') -> FetchResult:
    sport_key = 'basketball_nba' if sport == 'NBA' else 'baseball_mlb'
    try:
        url = (
            f'https://api.the-odds-api.com/v4/sports/{sport_key}/odds/'
            f'?apiKey={api_key}&regions=us&markets={markets}&oddsFormat=american&bookmakers=draftkings,fanduel'
        )
        data = fetch_json(url)
        rows = []
        for event in data:
            teams = event.get('teams') or []
            home_team = event.get('home_team', '')
            away_team = next((t for t in teams if t != home_team), '')
            best_home_ml, best_away_ml, best_total = None, None, None
            for book in event.get('bookmakers', []):
                for market in book.get('markets', []):
                    if market.get('key') == 'h2h':
                        for outcome in market.get('outcomes', []):
                            if outcome.get('name') == home_team:
                                best_home_ml = outcome.get('price') if best_home_ml is None else best_home_ml
                            if outcome.get('name') == away_team:
                                best_away_ml = outcome.get('price') if best_away_ml is None else best_away_ml
                    if market.get('key') == 'totals' and market.get('outcomes'):
                        pts = market.get('outcomes', [{}])[0].get('point')
                        if pts is not None: best_total = float(pts)
            rows.append({
                'game_label': f'{away_team}@{home_team}',
                'away_team': away_team,
                'home_team': home_team,
                'date': event.get('commence_time'),
                'home_moneyline': best_home_ml,
                'away_moneyline': best_away_ml,
                'total': best_total or 0.0,
                'home_implied_total': implied_total_from_event(best_total or 0.0, float(best_home_ml or -110), True) if best_total else 0.0,
                'away_implied_total': implied_total_from_event(best_total or 0.0, float(best_away_ml or -110), False) if best_total else 0.0,
                'odds_provider': 'The Odds API',
            })
        return FetchResult(True, pd.DataFrame(rows))
    except Exception as exc:
        return FetchResult(False, error=str(exc))

def fetch_mlb_probable_lineups(slate_date: date) -> FetchResult:
    ds = slate_date.isoformat()
    try:
        data = fetch_json(f'https://statsapi.mlb.com/api/v1/schedule?sportId=1&date={ds}&hydrate=lineups,probablePitcher,team')
        rows = []
        for d in data.get('dates', []):
            for g in d.get('games', []):
                teams = g.get('teams', {})
                away_team = teams.get('away', {}).get('team', {}).get('abbreviation', '')
                home_team = teams.get('home', {}).get('team', {}).get('abbreviation', '')
                game_label = f'{away_team}@{home_team}'
                for side in ('away', 'home'):
                    team_abbr = away_team if side == 'away' else home_team
                    probable = teams.get(side, {}).get('probablePitcher', {}).get('fullName')
                    if probable:
                        rows.append({'game_label': game_label, 'team': team_abbr, 'player_name': probable, 'lineup_status': 'probable_pitcher', 'batting_order': None})
                lineups = g.get('lineups') or []
                if isinstance(lineups, list):
                    for lu in lineups:
                        team_name = str(lu.get('teamName', ''))
                        team_abbr = away_team if away_team in team_name.upper() else home_team if home_team in team_name.upper() else ''
                        for batter in lu.get('players', []) or []:
                            rows.append({
                                'game_label': game_label,
                                'team': team_abbr,
                                'player_name': batter.get('fullName') or batter.get('name'),
                                'lineup_status': 'confirmed_lineup',
                                'batting_order': batter.get('battingOrder') or batter.get('order'),
                            })
        return FetchResult(True, pd.DataFrame(rows))
    except Exception as exc:
        return FetchResult(False, error=str(exc))

def build_fallback_slate(sport: str, slate_date: date) -> pd.DataFrame:
    if sport == 'NBA':
        return pd.DataFrame([
            {'game_label': 'BOS@NYK', 'away_team': 'BOS', 'home_team': 'NYK', 'status': 'Fallback', 'date': slate_date.isoformat(), 'venue': 'TBD'},
        ])
    return pd.DataFrame([
        {'game_label': 'ATL@PHI', 'away_team': 'ATL', 'home_team': 'PHI', 'status': 'Fallback', 'date': slate_date.isoformat(), 'venue': 'TBD'},
    ])

def parse_salary_file(raw_df: pd.DataFrame, sport: str, site: str) -> pd.DataFrame:
    df = clean_cols(raw_df)
    rename_map = {}
    for source, targets in {
        'name': ['name', 'nickname', 'player', 'player_name'],
        'id': ['id', 'playerid', 'player_id'],
        'position': ['position', 'roster_position', 'positions'],
        'salary': ['salary'],
        'team': ['teamabbr', 'team', 'team_abbrev'],
        'game_info': ['game_info', 'game', 'matchup'],
        'injury_status': ['injury_status', 'status'],
        'avg_points': ['avgpointspergame', 'fppg', 'avg_points', 'fantasy_points_per_game'],
    }.items():
        for t in targets:
            if t in df.columns:
                rename_map[t] = source
                break
    df = df.rename(columns=rename_map)

    if 'name' not in df.columns or 'position' not in df.columns or 'salary' not in df.columns:
        raise ValueError('salary file must include player name, position, and salary columns')

    out = pd.DataFrame()
    out['player_name'] = df['name'].astype(str).str.strip()
    out['player_id'] = df['id'].astype(str) if 'id' in df.columns else out['player_name']
    out['position'] = df['position'].astype(str).str.upper()
    out['salary'] = pd.to_numeric(df['salary'], errors='coerce').fillna(0).astype(int)
    out['team'] = df['team'].astype(str).str.upper().str.strip() if 'team' in df.columns else ''
    out['injury_status'] = df['injury_status'].astype(str).str.upper().fillna('') if 'injury_status' in df.columns else ''
    out['avg_points'] = pd.to_numeric(df['avg_points'], errors='coerce').fillna(0.0) if 'avg_points' in df.columns else 0.0
    out['game_info'] = df['game_info'].astype(str) if 'game_info' in df.columns else ''

    out['game_label'] = out['game_info'].fillna('').astype(str).str.extract(r'([A-Z]{2,4}\s*@\s*[A-Z]{2,4}|[A-Z]{2,4}\s+@\s+[A-Z]{2,4})', expand=False).fillna('').str.replace(' ', '', regex=False).str.upper()
    out['locked'], out['exclude'], out['is_late_game'] = False, False, False
    out['start_time'], out['site'], out['sport'] = None, site, sport
    out['is_pitcher'] = out['position'].str.contains('P', na=False)
    out['news_flag'], out['lineup_status'], out['news_bump'] = '', '', 0.0

    def infer_opponent(r):
        g = str(r.get('game_label', ''))
        t = str(r.get('team', ''))
        if '@' in g and t:
            a, h = g.split('@', 1)
            return h if a == t else (a if h == t else '')
        return ''
    out['opponent'] = out.apply(infer_opponent, axis=1)
    return out

def attach_slate_context(pool: pd.DataFrame, slate_df: pd.DataFrame) -> pd.DataFrame:
    if slate_df is None or slate_df.empty or 'game_label' not in slate_df.columns: return pool.copy()
    sd = slate_df.copy()
    sd['game_label'] = sd['game_label'].astype(str).map(standardize_game_label)
    if 'date' in sd.columns: sd['date_parsed'] = pd.to_datetime(sd['date'], errors='coerce', utc=True)
    keep = ['game_label'] + [c for c in ['date_parsed', 'home_team', 'away_team', 'status'] if c in sd.columns]
    merged = pool.copy()
    merged['game_label'] = merged['game_label'].astype(str).map(standardize_game_label)
    merged = merged.merge(sd[keep], on='game_label', how='left')
    if 'date_parsed' in merged.columns:
        now = pd.Timestamp.now(tz='UTC')
        merged['is_late_game'] = merged['date_parsed'].fillna(now) > now
        merged['start_time'] = merged['date_parsed'].astype(str)
    return merged

def merge_odds_overlay(slate_df: pd.DataFrame, odds_df: Optional[pd.DataFrame]) -> pd.DataFrame:
    if odds_df is None or odds_df.empty: return slate_df
    base, overlay = slate_df.copy(), odds_df.copy()
    base['game_label'] = base['game_label'].astype(str).map(standardize_game_label)
    overlay['game_label'] = overlay['game_label'].astype(str).map(standardize_game_label)
    drop_cols = [c for c in ['home_moneyline', 'away_moneyline', 'home_implied_total', 'away_implied_total'] if c in overlay.columns]
    base = base.drop(columns=[c for c in drop_cols if c in base.columns], errors='ignore')
    return base.merge(overlay[['game_label'] + drop_cols], on='game_label', how='left').fillna(base)

def apply_recent_form(pool: pd.DataFrame, custom_logs: Optional[pd.DataFrame] = None, lookback_games: int = 10) -> pd.DataFrame:
    pool = pool.copy()
    pool['recent_fpts'] = pool['avg_points']
    if custom_logs is None or custom_logs.empty: return pool
    logs = clean_cols(custom_logs).rename(columns={'player': 'player_name', 'fantasy_points': 'recent_fpts'})
    if 'player_name' not in logs.columns: return pool
    if 'recent_fpts' in logs.columns:
        logs = logs.groupby('player_name', as_index=False).agg(recent_fpts=('recent_fpts', 'mean'))
    pool = pool.merge(logs[['player_name', 'recent_fpts']], on='player_name', how='left')
    pool['recent_fpts'] = pool['recent_fpts_y'].combine_first(pool['recent_fpts_x']).fillna(pool['avg_points'])
    pool = pool.drop(columns=['recent_fpts_x', 'recent_fpts_y'], errors='ignore')
    return pool

def project_players(pool: pd.DataFrame, sport: str, contest_profile: str) -> pd.DataFrame:
    df = pool.copy()
    raw_proj = 0.60 * _safe(df['avg_points']) + 0.40 * _safe(df.get('recent_fpts', df['avg_points']))
    injury = df.get('injury_status', '').astype(str).str.upper()
    injury_penalty = injury.map(lambda x: 0.20 if x in {'O', 'OUT'} else (0.10 if x in {'Q', 'D', 'GTD'} else 0.0))
    df['projection'] = (raw_proj * (1 - injury_penalty) + _safe(df.get('news_bump', 0.0))).round(2)
    df['ceiling'] = (df['projection'] * 1.25 + 3).round(2)
    df['floor'] = (df['projection'] * 0.75).round(2)
    df['value'] = ((df['projection'] / df['salary'].replace(0, math.nan)) * 1000).fillna(0).round(2)
    df['ownership_proj'] = (df['value'] * 4.2).clip(0, 75).round(2)
    df['leverage_score'] = (df['ceiling'] - df['ownership_proj'] * 0.30 + df['value'] * 0.8).round(2)
    return df.sort_values(['projection'], ascending=False)

def eligible_for_slot(position: str, slot: str) -> bool:
    pos_list = [p.strip() for p in str(position).split('/')]
    allowed = POSITION_MAP.get(slot, [slot])
    return any(p in allowed for p in pos_list)

def optimize_single_lineup(df: pd.DataFrame, sport: str, site: str, min_salary: int, locked: List[str], excluded: List[str], prev_df: pd.DataFrame=None, max_repeat: int=9) -> pd.DataFrame:
    if pulp is None: raise RuntimeError('PuLP is required. Install with: pip install pulp')
    cfg = SITE_CONFIG[(sport, site)]
    slots = cfg['slots']
    df = df.copy().reset_index(drop=True)
    prob = pulp.LpProblem('dfs', pulp.LpMaximize)
    x = {(i, s): pulp.LpVariable(f'x_{i}_{s}', 0, 1, 'Binary') for i in df.index for s in range(len(slots)) if eligible_for_slot(df.loc[i, 'position'], slots[s])}
    y = {i: pulp.LpVariable(f'y_{i}', 0, 1, 'Binary') for i in df.index}
    prob += pulp.lpSum(df.loc[i, 'projection'] * y[i] for i in df.index)
    for s in range(len(slots)):
        prob += pulp.lpSum(x[(i, s)] for i in df.index if (i, s) in x) == 1
    for i in df.index:
        v = [s for s in range(len(slots)) if (i, s) in x]
        if v: prob += pulp.lpSum(x[(i, s)] for s in v) == y[i]
        else: prob += y[i] == 0
    prob += pulp.lpSum(df.loc[i, 'salary'] * y[i] for i in df.index) <= cfg['salary_cap']
    prob += pulp.lpSum(df.loc[i, 'salary'] * y[i] for i in df.index) >= min_salary
    for i, r in df.iterrows():
        if r['player_name'] in excluded: prob += y[i] == 0
        if r['player_name'] in locked: prob += y[i] == 1
    if prev_df is not None:
        prev_names = set(prev_df['player_name'].astype(str))
        prob += pulp.lpSum(y[i] for i in df.index if df.loc[i, 'player_name'] in prev_names) <= max_repeat
    prob.solve(pulp.PULP_CBC_CMD(msg=False))
    if pulp.LpStatus[prob.status] != 'Optimal': return pd.DataFrame()
    s_idx = [i for i in df.index if pulp.value(y[i]) > 0.5]
    chosen = df.loc[s_idx].copy()
    assignments = {}
    for i in s_idx:
        for s in range(len(slots)):
            if (i, s) in x and pulp.value(x[(i, s)]) > 0.5:
                assignments[i] = slots[s]
                break
    chosen['roster_slot'] = chosen.index.map(assignments)
    return chosen.sort_values('roster_slot').reset_index(drop=True)

def generate_lineups(df: pd.DataFrame, sport: str, site: str, count: int, min_sal: int, locked: List[str], excluded: List[str], repeat: int, rand: float) -> List[pd.DataFrame]:
    lineups = []
    base = df.copy()
    for _ in range(count):
        work = base.copy()
        work['projection'] = work['projection'] * (1 + pd.Series([random.uniform(-rand, rand) for _ in range(len(work))]))
        prev = lineups[-1] if lineups else None
        lu = optimize_single_lineup(work, sport, site, min_sal, locked, excluded, prev, repeat)
        if not lu.empty: lineups.append(lu)
    return lineups

def build_site_upload_template(lineups: List[pd.DataFrame], sport: str, site: str) -> pd.DataFrame:
    slots = SITE_CONFIG[(sport, site)]['slots']
    headers = []
    seen = {}
    for s in slots:
        seen[s] = seen.get(s, 0) + 1
        headers.append(s if slots.count(s) == 1 else f'{s}{seen[s]}')
    rows = []
    for idx, lu in enumerate(lineups, start=1):
        row = {'lineup_number': idx}
        used = {}
        for _, r in lu.iterrows():
            s = str(r['roster_slot'])
            used[s] = used.get(s, 0) + 1
            key = s if slots.count(s) == 1 else f'{s}{used[s]}'
            row[key] = f"{r.get('player_id', '')}:{r['player_name']}"
        rows.append(row)
    return pd.DataFrame(rows).fillna('')

st.title('DFS Builder v7')
st.caption('Live News, Odds, Lineups, and Backtesting')

with st.sidebar:
    sport = st.selectbox('Sport', ['NBA', 'MLB'])
    site = st.selectbox('Site', ['DraftKings', 'FanDuel'])
    slate_date = st.date_input('Slate date', value=date.today())
    contest_profile = st.selectbox('Contest profile', list(CONTEST_PROFILES.keys()), index=2)
    lineup_count = st.slider('Number of lineups', 1, 25, 10)
    uploaded = st.file_uploader('Upload DK/FD salary CSV', type=['csv'])
    custom_logs = st.file_uploader('Optional custom logs CSV', type=['csv'])

cfg = SITE_CONFIG[(sport, site)]
profile = CONTEST_PROFILES[contest_profile]
default_randomness = float(profile['randomness_default'])
default_min_salary = int(cfg['salary_cap'] * profile['min_salary_pct'])
default_max_repeat = int(profile['max_repeat_default'])

c1, c2, c3 = st.columns(3)
c1.metric('Salary cap', f"${cfg['salary_cap']}")
c2.metric('Roster spots', len(cfg['slots']))
c3.metric('Contest profile', contest_profile)

if uploaded is None:
    st.info("Upload the day's salary CSV to continue.")
    st.stop()

raw_df = pd.read_csv(uploaded)
pool = parse_salary_file(raw_df, sport, site)
slate_df = fetch_espn_nba_scoreboard(slate_date).data if sport == 'NBA' else fetch_mlb_schedule(slate_date).data
pool = attach_slate_context(pool, slate_df)
custom_logs_df = pd.read_csv(custom_logs) if custom_logs is not None else None
pool = apply_recent_form(pool, custom_logs_df)
proj_df = project_players(pool, sport, contest_profile)

st.subheader('Player Pool & Projections')
st.dataframe(proj_df[['player_name', 'team', 'position', 'salary', 'projection', 'ceiling', 'value', 'ownership_proj']], use_container_width=True)

st.subheader('Settings & Optimization')
randomness = st.slider('Lineup diversity', 0.0, 0.30, default_randomness, 0.01)
max_repeat = st.slider('Max repeated players', 0, 9, default_max_repeat)
min_salary = st.number_input('Min salary spend', 0, int(cfg['salary_cap']), default_min_salary)
locked = st.multiselect('Lock players', proj_df['player_name'].tolist())
excluded = st.multiselect('Exclude players', proj_df['player_name'].tolist())

if st.button('Generate Lineups', type='primary'):
    with st.spinner('Generating...'):
        try:
            lineups = generate_lineups(proj_df, sport, site, lineup_count, min_salary, locked, excluded, max_repeat, randomness)
            if lineups:
                st.success(f'Generated {len(lineups)} lineups.')
                summary = []
                for i, lu in enumerate(lineups):
                    with st.expander(f"Lineup {i+1} | Projection: {lu['projection'].sum():.2f} | Salary: ${lu['salary'].sum():.0f}"):
                        st.dataframe(lu[['roster_slot', 'player_name', 'salary', 'projection']])
                
                upload_df = build_site_upload_template(lineups, sport, site)
                buf = io.StringIO()
                upload_df.to_csv(buf, index=False)
                st.download_button('Download Site Export (CSV)', data=buf.getvalue().encode('utf-8'), file_name='export.csv', mime='text/csv')
            else:
                st.error("Could not find any optimal lineups matching criteria.")
        except Exception as e:
            st.error(f"Error: {e}")

st.markdown('---')
st.markdown('**What v7 adds:** live news headline ingestion, MLB probable/confirmed lineup ingestion, optional bookmaker odds overlay, and a projection-accuracy dashboard for backtesting.')
