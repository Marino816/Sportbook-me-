"""Canonical DFS game identity — unordered team matchups."""

from __future__ import annotations

from typing import Any, Iterable, Optional


def canonical_matchup_key(
    game_info: Optional[str] = None,
    team: Optional[str] = None,
    opponent: Optional[str] = None,
) -> Optional[str]:
    """Return a stable key for one contest game.

    ``LAD@SD …`` and ``SD@LAD …`` collapse to the same key. Identical CSV
    ``Game Info`` strings (both sides of a game share ``DET@CLE …``) also
    collapse to one game.
    """
    tokens: list[str] = []
    gi = (game_info or "").strip()
    if gi:
        first = gi.split()[0]
        if "@" in first:
            left, right = first.split("@", 1)
            left, right = left.strip().upper(), right.strip().upper()
            if left:
                tokens.append(left)
            if right:
                tokens.append(right)
    if len({t for t in tokens if t and t != "OPP"}) < 2:
        t = (team or "").strip().upper()
        o = (opponent or "").strip().upper()
        if t:
            tokens.append(t)
        if o:
            tokens.append(o)
    uniq = {t for t in tokens if t and t != "OPP"}
    if len(uniq) < 2:
        return None
    return "|".join(sorted(uniq))


def count_canonical_games(players: Iterable[Any]) -> int:
    keys: set[str] = set()
    for p in players:
        if isinstance(p, dict):
            key = canonical_matchup_key(p.get("game_info"), p.get("team"), p.get("opponent"))
        else:
            key = canonical_matchup_key(
                getattr(p, "game_info", None),
                getattr(p, "team", None),
                getattr(p, "opponent", None),
            )
        if key:
            keys.add(key)
    return len(keys)
