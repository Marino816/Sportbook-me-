"""SB ME 55-platform catalog vs SportsGameOdds bookmaker IDs.

The 55-platform product list is NOT the SGO bookmaker universe.
This module classifies mappings without fabricating odds.
"""

from __future__ import annotations

import json
from pathlib import Path

_JSON = Path(__file__).resolve().parents[2] / "web" / "src" / "lib" / "sbme-55-platforms.json"


def load_platform_catalog() -> list[dict]:
    return json.loads(_JSON.read_text())


def catalog_count() -> int:
    return len(load_platform_catalog())


def classify_observed_books(observed_sgo_ids: list[str] | set[str]) -> dict:
    """Classify 55 platforms against bookmaker IDs seen in nested events.

    Categories:
      mapped_to_sgo — catalog row has SGO ids and at least one is currently present
      mapping_needed — catalog row has no SGO ids (SB ME-only / unmatched brand)
      no_current_data — catalog row maps to SGO but none of those ids are in *observed*
      sgo_unlisted — observed SGO book not in the 55 catalog
    """
    catalog = load_platform_catalog()
    observed = {str(x).strip().lower() for x in observed_sgo_ids if x}
    catalog_sgo: set[str] = set()
    mapped, needed, no_data = [], [], []
    for row in catalog:
        sgo_ids = [str(i).lower() for i in (row.get("sgo_ids") or [])]
        catalog_sgo.update(sgo_ids)
        if not sgo_ids:
            needed.append(row)
        elif any(i in observed for i in sgo_ids):
            mapped.append(row)
        else:
            no_data.append(row)
    unlisted = sorted(observed - catalog_sgo)
    return {
        "total_existing": len(catalog),
        "mapped_to_sgo": mapped,
        "mapping_needed": needed,
        "no_current_data": no_data,
        "sgo_unlisted": unlisted,
        "counts": {
            "total_existing": len(catalog),
            "mapped_to_sgo": len(mapped),
            "mapping_needed": len(needed),
            "no_current_data": len(no_data),
            "sgo_unlisted": len(unlisted),
        },
        "note": (
            "The 55-platform catalog is a SB ME product list. "
            "SportsGameOdds bookmakers are a separate, event-dependent universe. "
            "No odds are invented for unmapped or empty rows."
        ),
    }
