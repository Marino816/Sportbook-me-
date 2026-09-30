"""Provider-independent Market Tools identity. Local only. Zero provider HTTP.

Production callers use SportsGameOdds event IDs, nested SBEvent structures,
SGO Fair Odds, SGO consensus, and SGO oddIDs. This layer does not invent those
fields. Odds API IDs stay namespaced as oddsapi and are never returned as SGO IDs.
"""

from __future__ import annotations

import re

ODDSAPI_NS = "oddsapi"
SGO_NS = "sgo"
_HEX32 = re.compile(r"^[0-9a-f]{32}$", re.I)

# Production routes and modules that consume SGO identifiers or nested SBEvents.
PRODUCTION_SGO_CONSUMERS = (
    {"module": "api.market_tools", "uses": "event_id query/body as SGO event ID for live-odds, compare, player-props, arbitrage scan, parlay legs"},
    {"module": "providers.nested_events", "uses": "canonical nested /v2/events SBEvent cache; find_event_by_id; sbevent_to_game_row / compare / props"},
    {"module": "api.sgo_data", "uses": "load_canonical_sb_events; Redis sgo:v2:sbevents keys"},
    {"module": "market_engine.MarketIdentity", "uses": "odd_id is an SGO oddID; event_id is SGO"},
    {"module": "market_engine.props", "uses": "consensus_line as median SGO line across books; SGO v2 payload only"},
    {"module": "market_engine.arbitrage", "uses": "scan over nested SGO books; soccer 3-way via provided odds_c"},
    {"module": "web/src/app/market-tools", "uses": "SGO event.id from /api/sgo/events and market-tools APIs"},
    {"module": "web/src/lib/platforms.ts", "uses": "sgo_ids for bookmaker canonicalization"},
    {"module": "web/src/lib/arbitrage.ts", "uses": "eventId from SGO events"},
    {"module": "projection.sgo_intelligence", "uses": "SGO player/event join for DFS"},
)

PRODUCTION_UNSUPPORTED = (
    "Lookup by SGO event ID against Odds API snapshots",
    "Nested SBEvent /v2/events shape (home_team/away_team objects, oddID markets)",
    "SGO Fair Odds field on book lines",
    "SGO consensus endpoint or oddID-keyed consensus",
    "SGO player IDs on player props",
    "SGO bookmaker IDs (platforms.sgo_ids) — Odds API uses its own book keys",
    "Period markets stored as SGO period codes (FULL_GAME, 1H, Q1)",
    "Live movement / opening-close SGO fields",
    "Same-game parlay prices from a sportsbook",
    "DFS slate_id as an event identifier",
)


def namespaced_event_id(sport_key: str, source_event_id: str) -> str:
    return f"{ODDSAPI_NS}:{sport_key}:{source_event_id}"


def namespaced_quote_id(parts: list) -> str:
    return "|".join([ODDSAPI_NS, *(str(p) for p in parts)])


def parse_internal_event_id(raw: str | None) -> dict:
    text = (raw or "").strip()
    if not text:
        return {"ok": False, "reason": "missing_event_id", "namespace": None}
    if text.startswith(f"{SGO_NS}:"):
        return {
            "ok": False,
            "namespace": SGO_NS,
            "source_event_id": text.split(":", 1)[1],
            "reason": "SGO event IDs are not Odds API event IDs. Mapping unavailable.",
        }
    if text.startswith(f"{ODDSAPI_NS}:"):
        bits = text.split(":")
        if len(bits) < 3:
            return {"ok": False, "namespace": ODDSAPI_NS, "reason": "malformed_oddsapi_event_id"}
        return {
            "ok": True,
            "namespace": ODDSAPI_NS,
            "sport_key": bits[1],
            "source_event_id": ":".join(bits[2:]),
        }
    if _HEX32.match(text):
        return {
            "ok": True,
            "namespace": ODDSAPI_NS,
            "sport_key": None,
            "source_event_id": text.lower(),
            "bare_source_id": True,
            "note": "Bare 32-character id treated as Odds API source id, not an SGO id.",
        }
    return {
        "ok": False,
        "namespace": None,
        "source_event_id": text,
        "reason": "Unmapped event id. Not treated as SGO or Odds API without a namespace.",
    }


def resolve_event(raw: str | None, events: list[dict]) -> dict:
    parsed = parse_internal_event_id(raw)
    if not parsed.get("ok"):
        return {
            "found": False,
            "unavailable": True,
            "sgo_event_id": None,
            **parsed,
        }
    source = parsed.get("source_event_id")
    sport_key = parsed.get("sport_key")
    for event in events or []:
        if sport_key and event.get("sport_key") and event.get("sport_key") != sport_key:
            continue
        if event.get("source_event_id") == source or event.get("id") == namespaced_event_id(event.get("sport_key") or "", source or ""):
            return {
                "found": True,
                "unavailable": False,
                "namespace": ODDSAPI_NS,
                "internal_event_id": event.get("internal_event_id") or event.get("id"),
                "source_event_id": event.get("source_event_id"),
                "sgo_event_id": None,
                "sgo_mapping": "unavailable",
                "event": {
                    "id": event.get("id"),
                    "sport_key": event.get("sport_key"),
                    "home_team": event.get("home_team"),
                    "away_team": event.get("away_team"),
                    "commence_time": event.get("commence_time"),
                },
            }
    return {
        "found": False,
        "unavailable": True,
        "namespace": ODDSAPI_NS,
        "source_event_id": source,
        "sgo_event_id": None,
        "reason": "Event is not in this saved snapshot. Selection cannot be mapped reliably.",
    }


def preserve_or_unavailable(leg: dict, events: list[dict]) -> dict:
    """Keep a saved selection when the namespaced event is present; otherwise unavailable."""
    event_id = leg.get("event_id") or leg.get("internal_event_id")
    resolved = resolve_event(event_id, events)
    if resolved.get("found"):
        return {**leg, "mapped": True, "namespace": ODDSAPI_NS, "sgo_event_id": None}
    return {
        "mapped": False,
        "unavailable": True,
        "reason": resolved.get("reason") or "Event cannot be mapped reliably.",
        "sgo_event_id": None,
        "saved_event_id": event_id,
    }


def resolve_selection(leg: dict, quote_index: dict, events: list[dict]) -> dict:
    """Map a saved quote by namespaced id only. Never match on team/player names."""
    quote_id = (leg.get("id") or "").strip()
    event_id = leg.get("event_id") or leg.get("internal_event_id")
    if quote_id in (quote_index or {}):
        quote = quote_index[quote_id]
        return {
            **leg,
            **{k: quote.get(k) for k in ("id", "event_id", "market", "selection", "player", "line", "bookmaker", "bookmaker_key", "american", "period", "source_event_id", "source_timestamp")},
            "mapped": True,
            "unavailable": False,
            "namespace": ODDSAPI_NS,
            "sgo_event_id": None,
        }
    parsed = parse_internal_event_id(str(event_id or quote_id or ""))
    if parsed.get("namespace") == SGO_NS or (not quote_id.startswith(f"{ODDSAPI_NS}|") and str(event_id or "").startswith(f"{SGO_NS}:")):
        return {
            "mapped": False,
            "unavailable": True,
            "reason": "Legacy SGO selection has no verified mapping. Displayed as unavailable.",
            "sgo_event_id": None,
            "saved_id": quote_id or None,
            "saved_event_id": event_id,
        }
    event = resolve_event(event_id, events) if event_id else {"found": False, "reason": "missing_event_id"}
    if not event.get("found"):
        return {
            "mapped": False,
            "unavailable": True,
            "reason": event.get("reason") or "Selection cannot be mapped reliably. Nothing was substituted.",
            "sgo_event_id": None,
            "saved_id": quote_id or None,
            "saved_event_id": event_id,
        }
    if quote_id:
        return {
            "mapped": False,
            "unavailable": True,
            "reason": "Event is present but this selection id is not in the snapshot. Nothing was substituted.",
            "sgo_event_id": None,
            "saved_id": quote_id,
            "saved_event_id": event_id,
        }
    return {
        "mapped": False,
        "unavailable": True,
        "reason": "Saved selection is missing a namespaced quote id. Ambiguous recovery is not allowed.",
        "sgo_event_id": None,
        "saved_event_id": event_id,
    }


def internal_event_record(sport_key: str, source_event_id: str) -> dict:
    return {
        "source_namespace": ODDSAPI_NS,
        "source_event_id": source_event_id,
        "internal_event_id": namespaced_event_id(sport_key, source_event_id),
        "sgo_event_id": None,
        "sgo_mapping": "unavailable",
    }


def production_gaps() -> dict:
    return {
        "provider_independent_contract": True,
        "odds_api_ids_are_not_sgo_ids": True,
        "sgo_fields_fabricated": False,
        "consumers": list(PRODUCTION_SGO_CONSUMERS),
        "unsupported_production_features": list(PRODUCTION_UNSUPPORTED),
        "fair_odds": "Market-derived fair odds from complete same-book outcome sets only. Not SGO Fair Odds.",
        "consensus": "Median vig-inclusive implied probability on equivalent Odds API quotes. Not SGO consensus.",
        "arbitrage": "Historical snapshot discrepancy on compatible Odds API quotes. Not live SGO arb scan.",
    }
