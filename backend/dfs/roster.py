"""
Sport + platform DFS roster templates.

Roster structure is keyed by BOTH sport and platform. MLB never leaks into
football (or NBA). Salary caps are only set when they exist in this repo's
verified platform configuration or were explicitly specified for this
product.

Salary-cap sources:
    MLB DK 50000 / FD 35000  — optimizer.mlb_optimizer.PLATFORM_CONFIG
    NBA DK 50000 / FD 60000  — builder.engine DK_CAP / FD_CAP
    NFL DK 50000 / NCAAF DK 50000 — production review + dfs.parsers DK default
    FanDuel NFL 60000 / FanDuel NCAAF 60000 — verified FanDuel contest
    reference (empty-lineup salary remaining + roster slot counts)

FLEX eligibility follows classic DraftKings / FanDuel football rules used
to fill the listed slot structure. Slot lists themselves match the
production-review templates.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


WEEKLY_SPORTS = frozenset({"NFL", "NCAAF"})

# Positions that may occupy FLEX / SUPER FLEX. These are eligibility rules
# for the listed slots, not invented extra roster spots.
_DK_NFL_FLEX = frozenset({"RB", "WR", "TE"})
_DK_NCAAF_FLEX = frozenset({"RB", "WR"})
_SFLX = frozenset({"QB", "RB", "WR", "TE"})
_FD_NFL_FLEX = frozenset({"RB", "WR", "TE"})
_FD_NCAAF_SFLX = frozenset({"QB", "RB", "WR"})


@dataclass(frozen=True)
class RosterTemplate:
    sport: str
    platform: str
    slots: tuple[str, ...]
    salary_cap: Optional[int]
    min_salary: int = 0
    filter_positions: tuple[str, ...] = ()
    flex_eligible: frozenset[str] = field(default_factory=frozenset)
    sflx_eligible: frozenset[str] = field(default_factory=frozenset)
    slot_labels: dict[str, str] = field(default_factory=dict)
    salary_cap_source: str = ""
    min_unique_default: int = 2

    @property
    def player_count(self) -> int:
        return len(self.slots)

    @property
    def salary_cap_verified(self) -> bool:
        return self.salary_cap is not None


def _tpl(**kwargs) -> RosterTemplate:
    sport = kwargs["sport"]
    platform = kwargs["platform"]
    slots = kwargs["slots"]
    filters = kwargs.get("filter_positions")
    if not filters:
        seen: list[str] = []
        for s in slots:
            if s in ("FLEX", "SFLX", "UTIL", "G", "F") or s in seen:
                continue
            seen.append(s)
        filters = tuple(seen)
    kwargs["filter_positions"] = filters
    return RosterTemplate(**kwargs)


# Display labels for compact slot codes.
_SFLX_LABEL = {"SFLX": "SUPER FLEX"}
_C1B_LABEL = {"C1B": "C/1B"}


ROSTER_TEMPLATES: dict[tuple[str, str], RosterTemplate] = {
    ("MLB", "draftkings"): _tpl(
        sport="MLB",
        platform="draftkings",
        slots=("P", "P", "C", "1B", "2B", "3B", "SS", "OF", "OF", "OF"),
        salary_cap=50000,
        min_salary=0,
        filter_positions=("P", "C", "1B", "2B", "3B", "SS", "OF"),
        salary_cap_source="mlb_optimizer.PLATFORM_CONFIG",
        min_unique_default=2,
    ),
    ("MLB", "fanduel"): _tpl(
        sport="MLB",
        platform="fanduel",
        slots=("P", "C1B", "2B", "3B", "SS", "OF", "OF", "OF", "UTIL"),
        salary_cap=35000,
        min_salary=28000,
        filter_positions=("P", "C", "1B", "2B", "3B", "SS", "OF"),
        slot_labels=_C1B_LABEL,
        salary_cap_source="mlb_optimizer.PLATFORM_CONFIG",
        min_unique_default=2,
    ),
    ("NFL", "draftkings"): _tpl(
        sport="NFL",
        platform="draftkings",
        slots=("QB", "RB", "RB", "WR", "WR", "WR", "TE", "FLEX", "DST"),
        salary_cap=50000,
        filter_positions=("QB", "RB", "WR", "TE", "DST"),
        flex_eligible=_DK_NFL_FLEX,
        salary_cap_source="production review + dfs.parsers DK default",
        min_unique_default=2,
    ),
    ("NFL", "fanduel"): _tpl(
        sport="NFL",
        platform="fanduel",
        slots=("QB", "RB", "RB", "WR", "WR", "WR", "TE", "FLEX", "DEF"),
        salary_cap=60000,
        filter_positions=("QB", "RB", "WR", "TE", "DEF"),
        flex_eligible=_FD_NFL_FLEX,
        salary_cap_source="FanDuel NFL contest reference (60k / 9 slots)",
        min_unique_default=2,
    ),
    ("NCAAF", "draftkings"): _tpl(
        sport="NCAAF",
        platform="draftkings",
        slots=("QB", "RB", "RB", "WR", "WR", "WR", "FLEX", "SFLX"),
        salary_cap=50000,
        filter_positions=("QB", "RB", "WR", "TE", "DST"),
        flex_eligible=_DK_NCAAF_FLEX,
        sflx_eligible=_SFLX,
        slot_labels=_SFLX_LABEL,
        salary_cap_source="production review + dfs.parsers DK default",
        min_unique_default=2,
    ),
    ("NCAAF", "fanduel"): _tpl(
        sport="NCAAF",
        platform="fanduel",
        slots=("QB", "RB", "RB", "WR", "WR", "WR", "SFLX"),
        salary_cap=60000,
        filter_positions=("QB", "RB", "WR", "TE"),
        sflx_eligible=_FD_NCAAF_SFLX,
        slot_labels=_SFLX_LABEL,
        salary_cap_source="FanDuel NCAAF contest reference (60k / 7 slots)",
        min_unique_default=2,
    ),
    ("NBA", "draftkings"): _tpl(
        sport="NBA",
        platform="draftkings",
        slots=("PG", "SG", "SF", "PF", "C", "G", "F", "UTIL"),
        salary_cap=50000,
        filter_positions=("PG", "SG", "SF", "PF", "C"),
        salary_cap_source="builder.engine.DK_CAP",
        min_unique_default=2,
    ),
    ("NBA", "fanduel"): _tpl(
        sport="NBA",
        platform="fanduel",
        slots=("PG", "PG", "SG", "SG", "SF", "SF", "PF", "PF", "C"),
        salary_cap=60000,
        filter_positions=("PG", "SG", "SF", "PF", "C"),
        salary_cap_source="builder.engine.FD_CAP",
        min_unique_default=2,
    ),
}


UNIQUE_LINEUP_UNAVAILABLE = (
    "No additional unique lineup is available under the current locks/exclusions."
)


def normalize_platform(platform: str | None) -> str:
    p = (platform or "draftkings").strip().lower().replace(" ", "")
    if p in ("dk", "draftkings"):
        return "draftkings"
    if p in ("fd", "fanduel"):
        return "fanduel"
    return p


def normalize_sport(sport: str | None) -> str:
    return (sport or "").strip().upper()


def get_roster(sport: str | None, platform: str | None) -> Optional[RosterTemplate]:
    key = (normalize_sport(sport), normalize_platform(platform))
    return ROSTER_TEMPLATES.get(key)


def slot_label(slot: str, roster: Optional[RosterTemplate] = None) -> str:
    if roster and slot in roster.slot_labels:
        return roster.slot_labels[slot]
    if slot == "SFLX":
        return "SUPER FLEX"
    if slot == "C1B":
        return "C/1B"
    return slot


def normalize_player_pos(raw: str | None) -> list[str]:
    """Split multi-eligible strings into canonical position codes."""
    text = (raw or "").upper().replace("SUPER FLEX", "SFLX").replace("SUPERFLEX", "SFLX")
    text = text.replace("D/ST", "DST").replace("D-ST", "DST")
    parts = [p.strip() for p in text.replace("/", ",").split(",") if p.strip()]
    out: list[str] = []
    for p in parts:
        if p in ("SP", "RP"):
            out.append("P")
        elif p in ("LF", "RF", "CF", "DH"):
            out.append("OF")
        elif p in ("DEF", "DST"):
            out.append(p)
        else:
            out.append(p)
    return out


def eligible_for_slot(player_pos: str | None, slot: str, roster: RosterTemplate) -> bool:
    positions = set(normalize_player_pos(player_pos))
    slot_n = (slot or "").upper()
    if slot_n == "SUPER FLEX" or slot_n == "SUPERFLEX":
        slot_n = "SFLX"
    if slot_n == "UTIL":
        return bool(positions - {"P"})
    if slot_n == "C1B":
        return bool(positions & {"C", "1B", "C1B"})
    if slot_n == "FLEX":
        return bool(positions & roster.flex_eligible)
    if slot_n == "SFLX":
        return bool(positions & roster.sflx_eligible)
    if slot_n in ("DST", "DEF"):
        return bool(positions & {"DST", "DEF"})
    if slot_n in ("G", "F") and roster.sport == "NBA":
        if slot_n == "G":
            return bool(positions & {"PG", "SG", "G"})
        return bool(positions & {"SF", "PF", "F"})
    return slot_n in positions


def uses_slot_optimizer(sport: str | None) -> bool:
    """Football contests use the generic slot CP-SAT solver (not MLB)."""
    return normalize_sport(sport) in {"NFL", "NCAAF"}


def average_remaining_per_player(remaining_salary: int, remaining_slots: int) -> int:
    """remaining salary / remaining open roster spots, rounded to dollars."""
    if remaining_slots <= 0:
        return 0
    return int(round(float(remaining_salary) / float(remaining_slots)))
