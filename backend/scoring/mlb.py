"""
MLB historical score-keeper — DraftKings official rules.

Takes a per-game SGO stat dict (the results.game.{playerID} object)
and returns a ScoringResult with the exact DraftKings fantasy-point
total, an exact/partial flag, and the list of missing categories.

FanDuel is stubbed — see scoring/platforms.py.

Summary of missing SGO fields:
  batting_runsScored   — hitter runs scored (2 DK pts each)
  pitching_hitBatters   — pitcher hit batters (-0.6 DK pts each)

When either is absent the score is labeled historical_partial and
the affected category is listed in missing_fields.  The unavailable
value is NOT silently substituted with zero — the category contribution
is simply omitted from the total.
"""

from __future__ import annotations

from typing import Optional

from scoring.models import (
    ScoringCategory,
    ScoringMode,
    ScoringPlatform,
    ScoringResult,
    Sport,
    PlayerRole,
)
from scoring.platforms import (
    DK_HITTER_CATEGORIES,
    DK_PITCHER_CATEGORIES,
)


class MLBScorekeeper:
    """Stateless: stat dict in → ScoringResult out."""

    def __init__(self, platform: ScoringPlatform = ScoringPlatform.DRAFTKINGS):
        if platform == ScoringPlatform.FANDUEL:
            raise NotImplementedError(
                "FanDuel MLB scoring is disabled until its current official "
                "2026 scoring rules are independently verified."
            )
        self.platform = platform
        self._hitter_categories = DK_HITTER_CATEGORIES
        self._pitcher_categories = DK_PITCHER_CATEGORIES

    # ── public ────────────────────────────────────────────────

    def score(self, sgo_stats: dict, *, event_status: Optional[dict] = None) -> ScoringResult:
        """Return a ScoringResult for one game.

        *sgo_stats* must be the raw dict from results.game.{playerID}.
        *event_status* is the parent event's status dict, used to
        derive CG/CGSO/No-hitter (optional — omitted for hitters).
        """
        role = _detect_role(sgo_stats)
        if role == PlayerRole.PITCHER:
            return self._score_pitcher(sgo_stats, event_status or {})
        else:
            return self._score_hitter(sgo_stats)

    def score_hitter(self, sgo_stats: dict) -> ScoringResult:
        return self._score_hitter(sgo_stats)

    def score_pitcher(self, sgo_stats: dict, event_status: Optional[dict] = None) -> ScoringResult:
        return self._score_pitcher(sgo_stats, event_status or {})

    # ── internals ─────────────────────────────────────────────

    def _score_hitter(self, stats: dict) -> ScoringResult:
        return self._score(stats, self._hitter_categories, PlayerRole.HITTER)

    def _score_pitcher(self, stats: dict, event_status: dict) -> ScoringResult:
        return self._score(
            stats, self._pitcher_categories, PlayerRole.PITCHER,
            event_status=event_status,
        )

    def _score(
        self,
        stats: dict,
        categories: list[ScoringCategory],
        role: PlayerRole,
        *,
        event_status: Optional[dict] = None,
    ) -> ScoringResult:
        calculated: dict[str, float] = {}
        missing: list[str] = []
        total = 0.0

        for cat in categories:
            val = stats.get(cat.sgo_field)

            # Derived categories (CG, CGSO, NH)
            if cat.name in ("completeGame", "cgShutout", "noHitter"):
                bonus = _derive_special_achievement(cat.name, stats, event_status or {})
                if bonus:
                    calculated[cat.name] = bonus
                    total += bonus
                continue

            # Direct categories
            if val is None:
                if cat.required:
                    missing.append(cat.name)
                continue

            try:
                numeric = float(val)
            except (TypeError, ValueError):
                if cat.required:
                    missing.append(cat.name)
                continue

            # pitching_outs → IP
            if cat.sgo_field == "pitching_outs":
                numeric = numeric / 3.0  # outs → innings

            contribution = round(numeric * cat.points, 2)
            calculated[cat.name] = contribution
            total += contribution

        total = round(total, 1)
        is_exact = len(missing) == 0
        mode = ScoringMode.HISTORICAL_EXACT if is_exact else ScoringMode.HISTORICAL_PARTIAL

        # Build raw_stats snapshot for auditability
        raw = {cat.sgo_field: stats.get(cat.sgo_field) for cat in categories}

        return ScoringResult(
            fantasy_points=total,
            is_exact=is_exact,
            scoring_mode=mode,
            platform=self.platform,
            sport=Sport.MLB,
            player_role=role,
            calculated_from=calculated,
            missing_fields=missing,
            raw_stats=raw,
        )


# ── Helpers ───────────────────────────────────────────────────

def _detect_role(stats: dict) -> PlayerRole:
    """Heuristic: if any pitching_* key is present, it's a pitcher."""
    for key in stats:
        if key.startswith("pitching_"):
            return PlayerRole.PITCHER
    return PlayerRole.HITTER


def _derive_special_achievement(
    name: str, stats: dict, event_status: dict,
) -> Optional[float]:
    """Derive CG / CGSO / No-Hitter from per-game data.

    These are NOT direct SGO fields but can be inferred from:
      pitching_outs ≥ 27  (9-inning complete game)
      status.displayShort == "F"  (final)
      opponent score == 0  (shutout)
      hits allowed == 0  (no-hitter)
    """
    outs = int(stats.get("pitching_outs", 0) or 0)

    # CG: at least 27 outs in a completed game
    if name == "completeGame":
        if outs >= 27 and event_status.get("displayShort") in ("F", "Final"):
            return 2.5
        return None

    if name == "cgShutout":
        # CG + opponent scored 0
        if outs >= 27 and event_status.get("displayShort") in ("F", "Final"):
            if _opponent_score_zero(stats, event_status):
                return 2.5
        return None

    if name == "noHitter":
        if outs >= 27 and event_status.get("displayShort") in ("F", "Final"):
            hits = stats.get("pitching_hits")
            if hits is not None and int(hits) == 0:
                return 5.0
        return None

    return None


def _opponent_score_zero(stats: dict, event_status: dict) -> bool:
    """Check whether the opposing team scored 0 runs.

    build_game_log injects _opponent_score into the enriched_status dict
    from the parent event's teams.home.score / teams.away.score.  Direct
    callers that don't pass this will get False (no false positives).
    """
    opp_score = event_status.get("_opponent_score")
    if opp_score is not None:
        return int(opp_score) == 0
    return False