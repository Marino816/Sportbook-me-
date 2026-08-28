"""Shared DFS/SGO player-name folding.

Exact identity after Unicode NFD + accent stripping. Never fuzzy-matches.
"""

from __future__ import annotations

import re
import unicodedata


def fold_player_name(name: str | None) -> str:
    """Case-fold, strip combining marks, collapse whitespace.

    ``José Ramírez`` and ``Jose Ramirez`` become the same key.
    Distinct players that fold to the same string remain ambiguous to the caller.
    """
    folded = unicodedata.normalize("NFD", name or "")
    folded = "".join(ch for ch in folded if unicodedata.category(ch) != "Mn")
    return " ".join(folded.lower().strip().split())


def names_equal(a: str | None, b: str | None) -> bool:
    fa, fb = fold_player_name(a), fold_player_name(b)
    return bool(fa) and fa == fb
