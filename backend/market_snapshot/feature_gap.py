"""SGO losses versus net-new gaps. Unavailable handling is not a replacement."""

from __future__ import annotations

SGO_FEATURES_THAT_WOULD_BE_LOST = (
    {
        "feature": "Nested live scores with period, inning, and clock",
        "sgo_surface": "SGO nested /v2/events game status",
        "odds_api_today": "Scores endpoint attaches home/away scores and status on unique event id + identical commence_time. Period, inning, and clock are not in the documented scores schema and are not invented.",
        "customer_impact": "A customer who currently sees inning/clock on a live SGO card would see score + status only, or a completed score-only card labeled Saved result. That is a loss of live game state, not a substitute.",
    },
    {
        "feature": "SGO oddIDs and leftover SGO selection identity",
        "sgo_surface": "market_engine odd_id / sgo_odd_id",
        "odds_api_today": "Namespaced oddsapi quote ids. leftover SGO oddIDs return structured unavailable.",
        "customer_impact": "Saved SGO parlays, deep links, and assistant event ids that still use sgo:… cannot resolve. Unavailable is a refusal, not a mapped replacement.",
    },
    {
        "feature": "Nested SGO team props",
        "sgo_surface": "SGO team prop markets on nested events",
        "odds_api_today": "Not in the featured h2h/spreads/totals snapshot. Field stays unavailable.",
        "customer_impact": "Team-prop tickets and assistant team-prop answers go empty. No Odds API team-prop slate is being collected.",
    },
    {
        "feature": "SB ME game environment derived from nested SGO markets",
        "sgo_surface": "providers/intelligence environment",
        "odds_api_today": "Not derived from Odds API featured markets.",
        "customer_impact": "Environment context on DFS/game cards disappears when SGO is blocked.",
    },
    {
        "feature": "DFS SGO player-prop intelligence",
        "sgo_surface": "projection.sgo_intelligence.build_sgo_intelligence",
        "odds_api_today": (
            "While Odds API serving blocks SGO, listed player Over lines map onto existing DFS prop keys "
            "(hits, HR, RBI, pitcher K/ER/H/BB/outs, NFL pass/rush/rec, NBA points/rebounds/assists). "
            "No Odds API fantasy-points market exists; fantasyScore stays None and is not invented."
        ),
        "customer_impact": (
            "Optimizer/projection can use cached Odds API Over lines for those mapped keys. "
            "SGO fantasyScore is gone. Hitters without a mapped market stay on Blue Collar fallback. "
            "The current saved snapshot only sampled NFL player_pass_tds, so MLB slates stay unenriched until those markets are collected."
        ),
    },
    {
        "feature": "Assistant SGO event/odds/prop/status tools",
        "sgo_surface": "assistant.tools get_sgo_current_events, get_sgo_current_odds, related SGO tools",
        "odds_api_today": (
            "While Odds API serving is on, SGO event IDs return structured unavailable. "
            "Some tools read Odds API cache rows for events/odds/props when a snapshot exists. "
            "Nested SGO markets, steam, opening lines, SGP quotes, team props, and environment stay unavailable."
        ),
        "customer_impact": (
            "The assistant can recite saved Odds API featured/prop rows when the cache is populated. "
            "It cannot answer from live nested SGO, cannot use a customer’s sgo: event id, and cannot "
            "fill team props or clock. A structured unavailable payload is an honest miss, not a replacement tool."
        ),
    },
    {
        "feature": "Line movement, steam, and opening lines",
        "sgo_surface": "SGO historical/opening series",
        "odds_api_today": "movement labeled unavailable. No opening-vs-current series is stored.",
        "customer_impact": "Compare/steam views show unavailable. Unchanged current prices after a refresh are not movement.",
    },
    {
        "feature": "Same-game parlay combined quotes",
        "sgo_surface": "SGO SGP pricing",
        "odds_api_today": "Same-game combinations are not given a combined price. Cross-game math is illustrative only.",
        "customer_impact": "Parlay Builder still lists legs; it does not sell or display an SGP number.",
    },
)

REQUESTED_NEW_FEATURES_NEITHER_SUPPLIES = (
    {
        "feature": "Commercial NFL/NBA injury ingest and display",
        "why_neither": "NFL.com and NBA.com terms do not permit automated collection and commercial display without consent. SGO did not supply a licensed injury feed used here. Odds API has no injury product in this integration.",
        "current_handling": "Official report links only plus “Live injury feed not connected.” Zero injury HTTP. Labeled fixtures are not live coverage.",
        "not_a_replacement": True,
    },
    {
        "feature": "Event-specific official venue GIS for every game",
        "why_neither": "Home-team stadium catalogs are not event-specific. Odds API event payloads do not include verified coordinates. SGO nested events were not treated as verified GIS.",
        "current_handling": "Weather renders only when event_venue.verified is true. Forecasts are not observations.",
        "not_a_replacement": True,
    },
    {
        "feature": "Odds API period / alternate / player-period markets as a full slate",
        "why_neither": "This integration collects featured h2h/spreads/totals and a listed player-prop set. Period markets are not in the snapshot. SGO nested period markets are a different product and are blocked when Odds API serving is on.",
        "current_handling": "Unavailable. Not invented.",
        "not_a_replacement": True,
    },
    {
        "feature": "A currently released mobile binary pointed at an isolated backend",
        "why_neither": "The App Store / TestFlight client bakes EXPO_PUBLIC_API_URL at EAS production to Railway. getApiUrl() has no runtime override. Neither SGO nor Odds API changes that client.",
        "current_handling": "Source can project live-odds onto the mobile contract. That is not an installed-app test.",
        "not_a_replacement": True,
    },
)


def empty_dfs_intelligence_impact() -> dict:
    return {
        "when": "MARKET_TOOLS_ODDSAPI_ENABLED is on (or snapshot serving blocks SGO)",
        "code": "build_sgo_intelligence maps Odds API Over lines onto market_lines as thresholds; props stay empty; fantasyScore stays empty",
        "mapped_from_odds_api": [
            "MLB pitcher K/ER/H/BB/outs when those Odds API markets are in the cache (PROP_BASED)",
            "Listed NFL/NBA/MLB player O/U lines stored on the player intelligence dict",
        ],
        "not_a_replacement": True,
        "customer_impact": (
            "SGO fantasyScore is gone. Hitter native projections still require Blue Collar fallback. "
            "Pitcher PROP_BASED can run when Odds API pitcher markets are cached. "
            "The current saved snapshot only has an NFL player_pass_tds sample, so MLB DFS slates stay unenriched until those markets are collected. "
            "Empty fantasyScore is not an Odds API fantasy-points market."
        ),
        "unavailable_handling_is_not_feature_replacement": True,
    }


def unavailable_assistant_tools_impact() -> dict:
    return {
        "when": "Odds API Market Tools serving is on",
        "sgo_event_ids": "Structured unavailable. No invented mapping.",
        "odds_api_cache_rows": "Assistant recites saved events, de-vigged fair odds, book consensus, scores, and player-prop rows when present.",
        "still_unavailable": [
            "nested live clock/period",
            "SGO team props",
            "SB ME environment",
            "steam / opening lines",
            "SGP quotes",
            "sgo: event IDs",
        ],
        "not_a_replacement": True,
        "customer_impact": (
            "Assistant answers that depended on nested SGO become “unavailable” or Odds API snapshot recitation. "
            "That keeps the assistant from inventing data; it does not restore the SGO tools. "
            "If the shared cache is empty or Redis is down, even the snapshot recitation is unavailable."
        ),
        "unavailable_handling_is_not_feature_replacement": True,
    }


def remaining_losses_for_mario() -> tuple[dict, ...]:
    return (
        {
            "id": "sgo_fantasy_score",
            "kind": "unsupported_provider_capability",
            "technical_identifier": False,
            "customer_function": "DFS native fantasy-point projection from a fantasyScore market",
            "customer_surface": "DFS optimizer / projections",
            "was": "SGO nested fantasyScore market used as native projection",
            "now": "No Odds API fantasy-points market. Sportsbook prop lines are thresholds, not fantasy points. Hitters stay on Blue Collar fallback or UNAVAILABLE.",
            "decision": "accept_loss_or_keep_sgo_for_dfs",
        },
        {
            "id": "live_clock_period",
            "kind": "unsupported_provider_capability",
            "technical_identifier": False,
            "customer_function": "Live inning/clock/period on Game Odds cards and assistant status",
            "customer_surface": "Game Odds cards and assistant game status",
            "was": "Nested SGO period/inning/clock",
            "now": "Scores + status when unique Odds API match exists. Clock is not in the scores schema.",
            "decision": "accept_loss_or_keep_sgo_live_state",
        },
        {
            "id": "sgo_event_and_odd_ids",
            "kind": "technical_identifier",
            "technical_identifier": True,
            "customer_function": "Open a saved parlay, deep link, or assistant event by its stored id",
            "customer_surface": "Saved parlays, deep links, assistant event_id",
            "was": "sgo:… and SGO oddIDs",
            "now": (
                "Saved SGO legs are kept and shown as unavailable. They are not discarded and not "
                "fuzzy-mapped by team/player name. Safe migration only when a namespaced oddsapi "
                "quote id is present in the current snapshot quote_index."
            ),
            "decision": "keep_saved_legs_unavailable_or_authorize_verified_remap_later",
        },
        {
            "id": "team_props",
            "kind": "not_yet_collected",
            "technical_identifier": False,
            "customer_function": "Team-total tickets distinct from game totals",
            "customer_surface": "Assistant get_sgo_team_props and nested team markets",
            "was": "SGO team totals distinct from game totals",
            "now": "Not in the featured h2h/spreads/totals snapshot. Not invented. This is collection scope, not a claim that Odds API has no team markets.",
            "decision": "accept_or_authorize_documented_odds_api_team_market_collect",
        },
        {
            "id": "sbme_environment",
            "kind": "unsupported_provider_capability",
            "technical_identifier": False,
            "customer_function": "DFS canonical environment fields on game/player cards",
            "customer_surface": "DFS canonical environment fields",
            "was": "Derived from nested SGO markets",
            "now": "Not derived from Odds API featured markets.",
            "decision": "accept_null_environment",
        },
        {
            "id": "steam_opening_sgp",
            "kind": "history_not_yet_stored_and_unsupported_sgp",
            "technical_identifier": False,
            "customer_function": "Line movement / steam on Compare; combined same-game parlay price on Parlay Builder",
            "customer_surface": "Compare movement, Parlay Builder combined price",
            "was": "SGO opening/steam series and SGP quotes",
            "now": (
                "Current featured prices exist in the snapshot; an opening-vs-current series is not stored "
                "(history not yet stored, not a missing current market). Combined SGP price is unsupported "
                "and not fabricated."
            ),
            "decision": "accept_loss",
        },
        {
            "id": "mlb_prop_coverage_in_current_snapshot",
            "kind": "not_yet_collected",
            "technical_identifier": False,
            "customer_function": "MLB DFS player-prop threshold display (not fantasy points)",
            "customer_surface": "DFS MLB enrichment",
            "was": "SGO MLB player markets including fantasyScore",
            "now": "Threshold mapping is implemented; the saved Odds API snapshot only sampled NFL player_pass_tds. MLB slates stay unenriched until a later authorized collect.",
            "decision": "authorize_mlb_prop_collect_or_accept_empty_mlb_intel",
        },
    )


def feature_gap_report() -> dict:
    return {
        "sgo_features_that_would_be_lost": list(SGO_FEATURES_THAT_WOULD_BE_LOST),
        "requested_new_features_neither_supplies": list(REQUESTED_NEW_FEATURES_NEITHER_SUPPLIES),
        "empty_dfs_intelligence": empty_dfs_intelligence_impact(),
        "unavailable_assistant_tools": unavailable_assistant_tools_impact(),
        "remaining_losses_for_mario": list(remaining_losses_for_mario()),
        "rule": "Structured unavailable is a refusal. It is not a working replacement for the missing capability.",
    }
