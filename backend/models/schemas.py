from pydantic import BaseModel, ConfigDict
from typing import List, Optional, Dict, Any, Union
from datetime import datetime

class PlayerSchema(BaseModel):
    id: int
    sport: str
    name: str
    team: str
    active: bool

    model_config = ConfigDict(from_attributes=True)

class ProjectionSchema(BaseModel):
    id: int
    slate_id: int
    player_id: int
    salary: int
    roster_position: str
    projected_fp: float
    ceiling: float
    floor: float
    ownership: float
    leverage: float
    value: float
    player: Optional[PlayerSchema] = None

    model_config = ConfigDict(from_attributes=True)

class SlateSchema(BaseModel):
    id: int
    sport: str
    site: str
    date: datetime
    is_main_slate: bool

    model_config = ConfigDict(from_attributes=True)

class OptimizerSettings(BaseModel):
    """Settings for the lineup optimizer.

    All player-ID fields reference the canonical player ID in the players table.
    Supports both numeric IDs and player names for locking/exclusion.
    """
    platform: str = "draftkings"  # draftkings / fanduel
    strategy: str = "balanced"    # balanced / cash / gpp / aggressive / nuclear
    num_lineups: int = 20
    min_uniqueness: int = 2
    min_unique_players: Optional[int] = None  # overrides min_uniqueness when set from optimizer UI
    max_exposure: float = 1.0
    randomness: float = 0.0

    # Canonical field names — use these in new code
    locked_player_ids: List[Union[int, str]] = []
    excluded_player_ids: List[Union[int, str]] = []

    # Legacy aliases — preserved for backward compatibility
    # (mapped automatically by the optimizer)
    team_stacks: List[Dict[str, Any]] = []

    # Build & stacking rules (CP-SAT constraints)
    max_hitters_per_team: Optional[int] = None
    stack_size: Optional[int] = None
    pitcher_conflict: Optional[bool] = None
    min_salary: Optional[int] = None
    max_salary: Optional[int] = None
    max_exposure_pct: Optional[float] = None
    projection_overrides: List[Dict[str, Any]] = []
    regenerate_from_ids: List[List[str]] = []

    model_config = ConfigDict(populate_by_name=True)

class LineupRequest(BaseModel):
    slate_id: int
    settings: OptimizerSettings

class LineupResponse(BaseModel):
    total_salary: int
    projected_score: float
    players: List[ProjectionSchema]


# ── Authentication schemas ──────────────────────────────────

class UserRegisterRequest(BaseModel):
    username: str
    email: str
    password: str


class UserLoginRequest(BaseModel):
    password: str
    identifier: Optional[str] = None
    email: Optional[str] = None


class UsernameClaimRequest(BaseModel):
    username: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    plan: str = "Starter"
    email: str
    role: str = "user"
    username: Optional[str] = None


class UserResponse(BaseModel):
    id: int
    email: str
    role: str
    is_pro: bool
    is_active: bool
    created_at: datetime
    plan: str = "Starter"
    username: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class MessageResponse(BaseModel):
    message: str
