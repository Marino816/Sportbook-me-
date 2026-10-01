"""Bounded final Odds API → shared cache → API → browser test. Default: do not execute."""

from __future__ import annotations

# Last reported remaining credits after the scores/weather collect (2026-09-30T16:38:30Z).
LEDGER_REMAINING_REPORTED = 418
LEDGER_USED_REPORTED = 82

HOST = "https://api.the-odds-api.com"
REGION = "us"
FEATURED = "h2h,spreads,totals"
NFL_PROP_MARKETS = "player_pass_tds,player_pass_yds,player_rush_yds"

REQUESTS = (
    {
        "order": 1,
        "at": "T+0s",
        "method": "GET",
        "path": "/v4/sports/americanfootball_nfl/odds",
        "query": {"regions": REGION, "markets": FEATURED, "oddsFormat": "american"},
        "credits_max": 3,
        "why": "Replace shared cache featured NFL odds.",
    },
    {
        "order": 2,
        "at": "T+2s",
        "method": "GET",
        "path": "/v4/sports/baseball_mlb/odds",
        "query": {"regions": REGION, "markets": FEATURED, "oddsFormat": "american"},
        "credits_max": 3,
        "why": "Replace shared cache featured MLB odds.",
    },
    {
        "order": 3,
        "at": "T+4s",
        "method": "GET",
        "path": "/v4/sports/americanfootball_nfl/scores",
        "query": {"daysFrom": "1"},
        "credits_max": 2,
        "why": "NFL live/upcoming/recent completed scores. Match by source id + commence_time.",
    },
    {
        "order": 4,
        "at": "T+6s",
        "method": "GET",
        "path": "/v4/sports/baseball_mlb/scores",
        "query": {"daysFrom": "1"},
        "credits_max": 2,
        "why": "MLB scores including completed games for Odds unavailable cards.",
    },
    {
        "order": 5,
        "at": "T+8s",
        "method": "GET",
        "path": "/v4/sports/americanfootball_nfl/events/{event_id}/odds",
        "query": {"regions": REGION, "markets": NFL_PROP_MARKETS, "oddsFormat": "american"},
        "credits_max": 3,
        "event_id_source": "id of the first NFL event from request 1 body. No extra /events list.",
        "why": "One full-listed-markets NFL prop event into the same cache generation.",
    },
)

SUCCESS = (
    "Each response 200; x-requests-last matches credits_max or less; empty body allowed at 0.",
    "replace_from_payloads writes Redis (cache_backend=redis). Memory-only is not production-path proof.",
    "GET /api/market-tools/internal/snapshot returns generation matching the collect; browsing_triggers_upstream false; odds_api_http 0 after collect.",
    "Browser desktop+phone: NFL featured odds from this capture’s retrieved_at; MLB completed unmatched game labeled Saved result—not a live refresh and Odds unavailable if it has no matching odds event.",
    "A same-team future MLB matchup must not inherit that completed score.",
    "Prop card for the sampled NFL event shows the requested markets or structured unavailable if the event body is empty.",
    "Production flags stay off except this isolated local collect process. Scheduled fetching stays off afterward.",
)


def final_refresh_plan(*, execute: bool = False) -> dict:
    """Return the authorization package. execute=True is refused here; no provider HTTP."""
    credits_max = sum(int(row["credits_max"]) for row in REQUESTS)
    return {
        "execute": False,
        "executed": False,
        "refused_execute": bool(execute),
        "authorization_required": True,
        "production_flags_remain_off": True,
        "scheduled_fetch_remains_off": True,
        "host": HOST,
        "region": REGION,
        "http_requests": len(REQUESTS),
        "credits_max": credits_max,
        "credits_min_if_all_empty": 0,
        "ledger_remaining_reported": LEDGER_REMAINING_REPORTED,
        "ledger_used_reported": LEDGER_USED_REPORTED,
        "remaining_after_max": LEDGER_REMAINING_REPORTED - credits_max,
        "requests": [dict(row) for row in REQUESTS],
        "timing": {
            "collect_window_seconds": 12,
            "cache_replace": "T+10s immediately after last HTTP, same process, no browse-triggered fetch",
            "api_read": "T+11s GET /api/market-tools/internal/snapshot with Pro Arena/Elite entitlement",
            "browser": "T+15s to T+60s Chrome desktop 1280 and phone 390 against http://127.0.0.1:3000/market-tools",
            "restore": "If labeled fixtures were used first, POST /internal/restore-saved-preview then re-run this collect",
        },
        "requires": {
            "mario_authorization": True,
            "docker_redis": True,
            "isolated_local_process_only": True,
            "env_for_collect_process_only": {
                "MARKET_TOOLS_ODDSAPI_ENABLED": "true",
                "MARKET_TOOLS_ODDSAPI_COLLECT": "true",
                "MARKET_TOOLS_PROVIDER": "sgo",
                "NODE_ENV": "development",
            },
            "env_after_test": {
                "MARKET_TOOLS_ODDSAPI_ENABLED": "false",
                "MARKET_TOOLS_ODDSAPI_COLLECT": "false",
            },
        },
        "blockers_that_prevent_running_now": [
            "Docker Desktop is not installed; shared Redis cache replacement cannot be proven.",
            "Mario has not authorized this bounded spend.",
        ],
        "success_criteria": list(SUCCESS),
        "nws": "Not in this final Odds API test. Reuse saved forecast only when an event venue is verified.",
        "injuries": "No injury HTTP.",
        "note": (
            "Do not run this plan until Docker Redis is up and Mario authorizes "
            f"{credits_max} credits / {len(REQUESTS)} HTTP. Browsing must not call the provider."
        ),
    }
