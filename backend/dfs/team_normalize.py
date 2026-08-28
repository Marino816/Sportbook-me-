"""Shared DFS/SGO team-abbreviation normalization.

Providers disagree on a few MLB codes (Athletics ATH/OAK, White Sox CHW/CWS).
Canonical forms used across BC ingest, reconciliation, and optimizer quarantine:
  Athletics → OAK
  White Sox → CWS
"""

from __future__ import annotations

# Map any known alias to the canonical abbreviation.
TEAM_ABBR_ALIASES: dict[str, str] = {
    "ATH": "OAK",
    "OAK": "OAK",
    "CHW": "CWS",
    "CWS": "CWS",
    "AZ": "ARI",
    "ARI": "ARI",
    "WSH": "WSH",
    "WAS": "WSH",
}


def normalize_team_abbr(abbr: str | None) -> str:
    """Return the canonical uppercase team abbreviation."""
    raw = (abbr or "").upper().strip()
    if not raw:
        return ""
    return TEAM_ABBR_ALIASES.get(raw, raw)


def teams_equivalent(a: str | None, b: str | None) -> bool:
    """True when two abbreviations refer to the same club (including aliases)."""
    na, nb = normalize_team_abbr(a), normalize_team_abbr(b)
    if not na or not nb:
        return False
    return na == nb
