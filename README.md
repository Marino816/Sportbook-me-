# DFS Builder v7

NBA + MLB daily fantasy optimizer with:

- live slate import
- auto-generated lineups
- optional live odds overlay
- live news headline ingestion
- MLB probable / confirmed lineup ingestion when the feed publishes it
- DK / FD upload-template export
- late swap tools
- backtesting and projection accuracy dashboard

## Run

```bash
cd /mnt/data/dfs_dual_sport_app_v7
pip install -r requirements.txt
streamlit run app.py
```

## Inputs

### Required
- DraftKings or FanDuel salary CSV

### Optional
- game-log / custom model CSV
- starter / lineup / news override CSV
- backtest CSV with `player_name`, `projection`, and `actual_fpts`
- The Odds API key for bookmaker odds and totals overlay

## Notes

### Live news
The app pulls recent headlines and applies a light projection bump when a player's name appears in relevant slate news.

### MLB probable lineups
The app attempts to read MLB probable pitchers and any published lineup info. If the live feed has not posted lineup data yet, upload a manual starter override CSV.

### NBA lineup status
Because stable no-key public starter feeds for NBA are inconsistent, this version relies on salary data, live slate context, news headlines, and optional uploaded starter overrides.

### Backtesting
Upload a historical results file to see:
- overall MAE / RMSE / bias
- by-date accuracy
- salary-bucket accuracy
- biggest misses

## Override CSV examples

### starter / lineup / news override CSV
Columns you can use:
- `player_name`
- `team`
- `lineup_status`
- `batting_order`
- `news_flag`
- `news_bump`

### backtest CSV
Columns you can use:
- `slate_date`
- `player_name`
- `team`
- `position`
- `salary`
- `projection`
- `actual_fpts`
