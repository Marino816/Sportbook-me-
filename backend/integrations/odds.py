import os
import httpx
import logging
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

class OddsAPI:
    BASE_URL = "https://api.the-odds-api.com/v4/sports"

    def __init__(self):
        self.api_key = os.getenv("ODDS_API_KEY")
        self.use_fallback = os.getenv("USE_DEMO_DATA_FALLBACK", "true").lower() == "true"

    async def get_nba_odds(self) -> List[Dict[str, Any]]:
        """Fetch spread and totals for NBA."""
        if not self.api_key and self.use_fallback:
            return self._demo_odds()

        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{self.BASE_URL}/basketball_nba/odds",
                params={
                    "apiKey": self.api_key,
                    "regions": "us",
                    "markets": "spreads,totals",
                    "oddsFormat": "american"
                }
            )
            if resp.status_code == 200:
                return resp.json()
            return []

    def _demo_odds(self):
        return [
            {
                "home_team": "Los Angeles Lakers",
                "away_team": "Denver Nuggets",
                "bookmakers": [
                    {
                        "markets": [
                            {"key": "totals", "outcomes": [{"name": "Over", "point": 224.5}]},
                            {"key": "spreads", "outcomes": [{"name": "Los Angeles Lakers", "point": -3.5}]}
                        ]
                    }
                ]
            }
        ]
