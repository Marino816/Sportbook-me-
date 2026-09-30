"""Curated US venue coordinates for outdoor weather matching.

These coordinates are an SB ME catalog for local Market Tools, not an official
league GIS feed. Roof status is typical stadium design, not a live roof sensor.
Unlisted teams do not get weather.
"""

from __future__ import annotations

# sport_key -> indoor label. Arena sports skip venue weather.
INDOOR_SPORTS = {
    "basketball_nba": "Indoor",
    "basketball_ncaab": "Indoor",
    "basketball_wnba": "Indoor",
    "icehockey_nhl": "Indoor",
}

# home_team exact Odds API name -> venue
VENUES = {
    "Arizona Cardinals": {"name": "State Farm Stadium", "lat": 33.5276, "lon": -112.2626, "roof": "retractable", "city": "Glendale, AZ"},
    "Atlanta Falcons": {"name": "Mercedes-Benz Stadium", "lat": 33.7554, "lon": -84.4008, "roof": "retractable", "city": "Atlanta, GA"},
    "Baltimore Ravens": {"name": "M&T Bank Stadium", "lat": 39.2780, "lon": -76.6227, "roof": "outdoor", "city": "Baltimore, MD"},
    "Buffalo Bills": {"name": "Highmark Stadium", "lat": 42.7738, "lon": -78.7870, "roof": "outdoor", "city": "Orchard Park, NY"},
    "Carolina Panthers": {"name": "Bank of America Stadium", "lat": 35.2258, "lon": -80.8528, "roof": "outdoor", "city": "Charlotte, NC"},
    "Chicago Bears": {"name": "Soldier Field", "lat": 41.8623, "lon": -87.6167, "roof": "outdoor", "city": "Chicago, IL"},
    "Cincinnati Bengals": {"name": "Paycor Stadium", "lat": 39.0954, "lon": -84.5160, "roof": "outdoor", "city": "Cincinnati, OH"},
    "Cleveland Browns": {"name": "Huntington Bank Field", "lat": 41.5061, "lon": -81.6995, "roof": "outdoor", "city": "Cleveland, OH"},
    "Dallas Cowboys": {"name": "AT&T Stadium", "lat": 32.7473, "lon": -97.0945, "roof": "retractable", "city": "Arlington, TX"},
    "Denver Broncos": {"name": "Empower Field at Mile High", "lat": 39.7439, "lon": -105.0201, "roof": "outdoor", "city": "Denver, CO"},
    "Detroit Lions": {"name": "Ford Field", "lat": 42.3400, "lon": -83.0456, "roof": "indoor", "city": "Detroit, MI"},
    "Green Bay Packers": {"name": "Lambeau Field", "lat": 44.5013, "lon": -88.0622, "roof": "outdoor", "city": "Green Bay, WI"},
    "Houston Texans": {"name": "NRG Stadium", "lat": 29.6847, "lon": -95.4107, "roof": "retractable", "city": "Houston, TX"},
    "Indianapolis Colts": {"name": "Lucas Oil Stadium", "lat": 39.7601, "lon": -86.1639, "roof": "retractable", "city": "Indianapolis, IN"},
    "Jacksonville Jaguars": {"name": "EverBank Stadium", "lat": 30.3239, "lon": -81.6373, "roof": "outdoor", "city": "Jacksonville, FL"},
    "Kansas City Chiefs": {"name": "GEHA Field at Arrowhead", "lat": 39.0489, "lon": -94.4839, "roof": "outdoor", "city": "Kansas City, MO"},
    "Las Vegas Raiders": {"name": "Allegiant Stadium", "lat": 36.0909, "lon": -115.1833, "roof": "indoor", "city": "Las Vegas, NV"},
    "Los Angeles Chargers": {"name": "SoFi Stadium", "lat": 33.9535, "lon": -118.3390, "roof": "indoor", "city": "Inglewood, CA"},
    "Los Angeles Rams": {"name": "SoFi Stadium", "lat": 33.9535, "lon": -118.3390, "roof": "indoor", "city": "Inglewood, CA"},
    "Miami Dolphins": {"name": "Hard Rock Stadium", "lat": 25.9580, "lon": -80.2389, "roof": "outdoor", "city": "Miami Gardens, FL"},
    "Minnesota Vikings": {"name": "U.S. Bank Stadium", "lat": 44.9738, "lon": -93.2575, "roof": "indoor", "city": "Minneapolis, MN"},
    "New England Patriots": {"name": "Gillette Stadium", "lat": 42.0909, "lon": -71.2643, "roof": "outdoor", "city": "Foxborough, MA"},
    "New Orleans Saints": {"name": "Caesars Superdome", "lat": 29.9511, "lon": -90.0812, "roof": "indoor", "city": "New Orleans, LA"},
    "New York Giants": {"name": "MetLife Stadium", "lat": 40.8128, "lon": -74.0742, "roof": "outdoor", "city": "East Rutherford, NJ"},
    "New York Jets": {"name": "MetLife Stadium", "lat": 40.8128, "lon": -74.0742, "roof": "outdoor", "city": "East Rutherford, NJ"},
    "Philadelphia Eagles": {"name": "Lincoln Financial Field", "lat": 39.9008, "lon": -75.1675, "roof": "outdoor", "city": "Philadelphia, PA"},
    "Pittsburgh Steelers": {"name": "Acrisure Stadium", "lat": 40.4468, "lon": -80.0158, "roof": "outdoor", "city": "Pittsburgh, PA"},
    "San Francisco 49ers": {"name": "Levi's Stadium", "lat": 37.4033, "lon": -121.9694, "roof": "outdoor", "city": "Santa Clara, CA"},
    "Seattle Seahawks": {"name": "Lumen Field", "lat": 47.5952, "lon": -122.3316, "roof": "outdoor", "city": "Seattle, WA"},
    "Tampa Bay Buccaneers": {"name": "Raymond James Stadium", "lat": 27.9759, "lon": -82.5033, "roof": "outdoor", "city": "Tampa, FL"},
    "Tennessee Titans": {"name": "Nissan Stadium", "lat": 36.1665, "lon": -86.7713, "roof": "outdoor", "city": "Nashville, TN"},
    "Washington Commanders": {"name": "Northwest Stadium", "lat": 38.9077, "lon": -76.8645, "roof": "outdoor", "city": "Landover, MD"},
    "Atlanta Braves": {"name": "Truist Park", "lat": 33.8908, "lon": -84.4678, "roof": "outdoor", "city": "Atlanta, GA"},
    "Houston Astros": {"name": "Minute Maid Park", "lat": 29.7573, "lon": -95.3555, "roof": "retractable", "city": "Houston, TX"},
    "New York Yankees": {"name": "Yankee Stadium", "lat": 40.8296, "lon": -73.9262, "roof": "outdoor", "city": "Bronx, NY"},
    "San Diego Padres": {"name": "Petco Park", "lat": 32.7076, "lon": -117.1570, "roof": "outdoor", "city": "San Diego, CA"},
    "Fixture Outdoor": {"name": "Huntington Bank Field", "lat": 41.5061, "lon": -81.6995, "roof": "outdoor", "city": "Cleveland, OH"},
    "Fixture Horizon": {"name": "Lambeau Field", "lat": 44.5013, "lon": -88.0622, "roof": "outdoor", "city": "Green Bay, WI"},
}

VENUE_SOURCE = (
    "SB ME curated venue catalog for local weather matching. "
    "Coordinates are not an official league GIS feed. "
    "Roof open/closed is not supplied."
)


def indoor_label(sport_key: str | None) -> str | None:
    return INDOOR_SPORTS.get(sport_key or "")


def venue_for_home(home_team: str | None) -> dict | None:
    name = (home_team or "").strip()
    if not name:
        return None
    row = VENUES.get(name)
    if not row:
        return None
    return {**row, "home_team": name, "catalog_source": VENUE_SOURCE}
