from pydantic import BaseModel, ConfigDict
from typing import List, Optional, Dict, Any
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
    num_lineups: int = 20
    min_uniqueness: int = 2
    max_exposure: float = 1.0 # default 100%
    randomness: float = 0.0 # 0% variation
    locked_player_ids: List[int] = []
    excluded_player_ids: List[int] = []
    # Advanced stacks: [{"team": "LAL", "count": 2}]
    team_stacks: List[Dict[str, Any]] = []

class LineupRequest(BaseModel):
    slate_id: int
    settings: OptimizerSettings

class LineupResponse(BaseModel):
    total_salary: int
    projected_score: float
    players: List[ProjectionSchema]
