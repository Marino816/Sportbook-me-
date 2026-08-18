"""
Scoring-platform configurations — official DFS category weights.

Each platform defines its scoring categories separately.  The MLBScoopekeeper
reads these configs and maps them to SGO fields.

FanDuel is stubbed (NotImplementedError) until its official 2026 rules
are independently verified.
"""

from __future__ import annotations

from scoring.models import ScoringCategory


# ══════════════════════════════════════════════════════════════
#  DraftKings MLB — official 2026 rules
#
#  Source: backend/projection/native.py:22 comment:
#    "DK: Single=3, Double=5, Triple=8, HR=10, RBI=2, R=2, BB=2, SB=5, HBP=2"
#
#  Pitchers: K=2, IP=2.25, W=4, ER=-2, H=-0.6, BB=-0.6, HB=-0.6
#            CG=2.5, CGSO=2.5, No-hitter=5
# ══════════════════════════════════════════════════════════════

DK_HITTER_CATEGORIES: list[ScoringCategory] = [
    ScoringCategory(
        name="single", points=3.0, sgo_field="batting_singles", required=True,
        description="Single — 3 DK pts",
    ),
    ScoringCategory(
        name="double", points=5.0, sgo_field="batting_doubles", required=True,
        description="Double — 5 DK pts",
    ),
    ScoringCategory(
        name="triple", points=8.0, sgo_field="batting_triples", required=True,
        description="Triple — 8 DK pts",
    ),
    ScoringCategory(
        name="homeRun", points=10.0, sgo_field="batting_homeRuns", required=True,
        description="Home Run — 10 DK pts",
    ),
    ScoringCategory(
        name="rbi", points=2.0, sgo_field="batting_RBI", required=True,
        description="RBI — 2 DK pts",
    ),
    ScoringCategory(
        name="run", points=2.0, sgo_field="batting_runsScored", required=True,
        description="Run scored — 2 DK pts (UNAVAILABLE in SGO Rookie)",
    ),
    ScoringCategory(
        name="walk", points=2.0, sgo_field="batting_basesOnBalls", required=True,
        description="Base on balls — 2 DK pts",
    ),
    ScoringCategory(
        name="stolenBase", points=5.0, sgo_field="batting_stolenBases", required=True,
        description="Stolen base — 5 DK pts",
    ),
    ScoringCategory(
        name="hitByPitch", points=2.0, sgo_field="batting_hitByPitch", required=True,
        description="Hit by pitch — 2 DK pts",
    ),
    ScoringCategory(
        name="strikeout", points=-0.5, sgo_field="batting_strikeouts", required=True,
        description="Strikeout (batter) — -0.5 DK pts",
    ),
]


DK_PITCHER_CATEGORIES: list[ScoringCategory] = [
    ScoringCategory(
        name="inningPitched", points=2.25, sgo_field="pitching_outs", required=True,
        description="Inning pitched — 2.25 DK pts per IP (0.75 per out)",
    ),
    ScoringCategory(
        name="strikeout", points=2.0, sgo_field="pitching_strikeouts", required=True,
        description="Strikeout — 2 DK pts",
    ),
    ScoringCategory(
        name="win", points=4.0, sgo_field="pitching_win", required=True,
        description="Win — 4 DK pts",
    ),
    ScoringCategory(
        name="earnedRun", points=-2.0, sgo_field="pitching_earnedRuns", required=True,
        description="Earned run allowed — -2 DK pts",
    ),
    ScoringCategory(
        name="hitAllowed", points=-0.6, sgo_field="pitching_hits", required=True,
        description="Hit allowed — -0.6 DK pts",
    ),
    ScoringCategory(
        name="walkAllowed", points=-0.6, sgo_field="pitching_basesOnBalls", required=True,
        description="Walk allowed — -0.6 DK pts",
    ),
    ScoringCategory(
        name="hitBatter", points=-0.6, sgo_field="pitching_hitBatters", required=True,
        description="Hit batter — -0.6 DK pts (UNAVAILABLE in SGO Rookie)",
    ),
    # Special achievements — derived, not direct SGO fields
    ScoringCategory(
        name="completeGame", points=2.5, sgo_field="pitching_outs", required=False,
        description="Complete Game — 2.5 DK pts (derived: outs ≥ 27 in a 9-inning game)",
    ),
    ScoringCategory(
        name="cgShutout", points=2.5, sgo_field="pitching_outs", required=False,
        description="CG Shutout — 2.5 DK pts (derived: CG + 0 opponent runs)",
    ),
    ScoringCategory(
        name="noHitter", points=5.0, sgo_field="pitching_hits", required=False,
        description="No-hitter — 5 DK pts (derived: outs ≥ 27 + H=0)",
    ),
]


# ══════════════════════════════════════════════════════════════
#  FanDuel MLB — STUBBED
#
#  FanDuel scoring is DISABLED until the current official FanDuel
#  MLB DFS scoring rules are independently verified from FanDuel's
#  published rules page.  Any attempt to score with FanDuel raises
#  NotImplementedError.
# ══════════════════════════════════════════════════════════════

FD_HITTER_CATEGORIES: list[ScoringCategory] = []   # stub
FD_PITCHER_CATEGORIES: list[ScoringCategory] = []   # stub