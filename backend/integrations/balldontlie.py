import os
import httpx
import logging
import pandas as pd
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

class BallDontLieAPI:
    BASE_URL = "https://api.balldontlie.io/v1"

    def __init__(self):
        self.api_key = os.getenv("BALLDONTLIE_API_KEY")
        self.use_fallback = os.getenv("USE_DEMO_DATA_FALLBACK", "true").lower() == "true"
        self.headers = {"Authorization": self.api_key} if self.api_key else {}

    async def get_players(self, cursor: int = 0) -> List[Dict[str, Any]]:
        """Fetch all NBA players. Uses demo data if API key is not present."""
        if not self.api_key and self.use_fallback:
            logger.warning("No BALLDONTLIE_API_KEY found. Falling back to Demo Player Data.")
            return self._demo_players()

        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{self.BASE_URL}/players", headers=self.headers, params={"cursor": cursor})
            resp.raise_for_status()
            data = resp.json()
            return data.get('data', [])

    async def get_recent_game_logs(self, player_id: int) -> pd.DataFrame:
        if not self.api_key and self.use_fallback:
            return pd.DataFrame([{"pts": 25, "ast": 7, "reb": 5, "min": "34:00", "turnover": 2}])

        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{self.BASE_URL}/stats?player_ids[]={player_id}", headers=self.headers)
            if resp.status_code == 200:
                data = resp.json().get('data', [])
                return pd.DataFrame(data)
            return pd.DataFrame()

    def _demo_players(self):
        return [
            {"id": 1, "first_name": "LeBron", "last_name": "James", "position": "F", "team": {"abbreviation": "LAL"}},
            {"id": 2, "first_name": "Stephen", "last_name": "Curry", "position": "G", "team": {"abbreviation": "GSW"}},
            {"id": 3, "first_name": "Nikola", "last_name": "Jokic", "position": "C", "team": {"abbreviation": "DEN"}},
            {"id": 4, "first_name": "Luka", "last_name": "Doncic", "position": "G", "team": {"abbreviation": "DAL"}},
        ]
