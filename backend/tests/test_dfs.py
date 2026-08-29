"""Native DFS contest data layer tests."""

import pytest
from dfs.models import DFSContestPlayer, DFSSlate
from dfs.parsers import parse_draftkings_csv, parse_fanduel_csv
from dfs.reconciliation import reconcile_player

DK_SAMPLE = """Position,Name + ID,Name,ID,Roster Position,Salary,Game Info,TeamAbbrev,AvgPointsPerGame
P,Tarik Skubal (12345),Tarik Skubal,12345,SP,10500,DET@CLE 08/11/2026 07:10PM ET,DET,22.5
P,Zack Wheeler (67890),Zack Wheeler,67890,RP,9800,PHI@ATL 08/11/2026 07:20PM ET,PHI,19.8
C,J.T. Realmuto (11111),J.T. Realmuto,11111,C,4500,PHI@ATL 08/11/2026 07:20PM ET,PHI,8.2
1B,Pete Alonso (22222),Pete Alonso,22222,1B,5200,NYM@MIA 08/11/2026 06:40PM ET,NYM,9.1
2B,Ozzie Albies (33333),Ozzie Albies,33333,2B,5100,ATL@PHI 08/11/2026 07:20PM ET,ATL,8.5
3B,Austin Riley (44444),Austin Riley,44444,3B,5400,ATL@PHI 08/11/2026 07:20PM ET,ATL,9.2
SS,Francisco Lindor (55555),Francisco Lindor,55555,SS,5600,NYM@MIA 08/11/2026 06:40PM ET,NYM,9.8
OF,Ronald Acuna (66666),Ronald Acuna,66666,OF,6200,ATL@PHI 08/11/2026 07:20PM ET,ATL,10.5
OF,Mookie Betts (77777),Mookie Betts,77777,OF,6000,LAD@SD 08/11/2026 09:40PM ET,LAD,10.0
OF,Fernando Tatis (88888),Fernando Tatis,88888,OF,5500,SD@LAD 08/11/2026 09:40PM ET,SD,9.0
P,Corbin Burnes (99999),Corbin Burnes,99999,SP,9700,MIL@CHC 08/11/2026 08:05PM ET,MIL,18.5
"""

FD_SAMPLE = """Id,First Name,Last Name,Position,FPPG,Played,Salary,Game,Team,Opponent,Injury
12345,Tarik,Skubal,SP,22.5,1,10500,DET@CLE,DET,CLE,
67890,Zack,Wheeler,SP,19.8,1,9800,PHI@ATL,PHI,ATL,
11111,JT,Realmuto,C,8.2,1,4500,PHI@ATL,PHI,ATL,
"""

SGO_PLAYERS = [
    {"playerID": "12345", "name": "Tarik Skubal", "team": "DET", "position": "SP"},
    {"playerID": "67890", "name": "Zack Wheeler", "team": "PHI", "position": "SP"},
    {"playerID": "11111", "name": "J.T. Realmuto", "team": "PHI", "position": "C"},
    {"playerID": "22222", "name": "Pete Alonso", "team": "NYM", "position": "1B"},
    {"playerID": "55555", "name": "Francisco Lindor", "team": "NYM", "position": "SS"},
]


class TestDKParser:
    def test_parse_count(self):
        slate, players = parse_draftkings_csv(DK_SAMPLE)
        assert len(players) == 11
        assert slate.player_count == 11

    def test_parse_sport_detection(self):
        slate, _ = parse_draftkings_csv(DK_SAMPLE)
        assert slate.sport == "MLB"

    def test_parse_player_fields(self):
        _, players = parse_draftkings_csv(DK_SAMPLE)
        p = players[0]
        assert p.player_name == "Tarik Skubal"
        assert p.player_id == "12345"
        assert p.salary == 10500
        assert p.position == "P"  # SP → P slot mapping
        assert "SP" in p.eligible_positions
        assert p.team == "DET"
        assert p.opponent == "CLE"

    def test_to_optimizer_pool(self):
        _, players = parse_draftkings_csv(DK_SAMPLE)
        pool = DFSContestPlayer.list_to_pool(players)
        assert len(pool) == 11
        assert pool[0]["name"] == "Tarik Skubal"
        assert pool[0]["salary"] == 10500
        assert "projected_fp" in pool[0]


class TestFDParser:
    def test_parse_fd_csv(self):
        slate, players = parse_fanduel_csv(FD_SAMPLE)
        assert len(players) == 3
        assert slate.platform == "fanduel"
        assert slate.salary_cap == 35000

    def test_fd_player_name(self):
        _, players = parse_fanduel_csv(FD_SAMPLE)
        assert players[0].player_name == "Tarik Skubal"


class TestReconciliation:
    def test_exact_match(self):
        dp = DFSContestPlayer(platform="draftkings", player_id="12345", player_name="Tarik Skubal", team="DET")
        result = reconcile_player(dp, SGO_PLAYERS)
        assert result == "12345"
        assert dp.sbme_confidence == 1.0

    def test_punctuation_variant(self):
        dp = DFSContestPlayer(platform="draftkings", player_id="11111", player_name="JT Realmuto", team="PHI")
        result = reconcile_player(dp, SGO_PLAYERS)
        assert result is not None
        assert dp.sbme_confidence >= 0.85

    def test_no_match(self):
        dp = DFSContestPlayer(platform="draftkings", player_id="99999", player_name="Nobody Jones", team="XXX")
        result = reconcile_player(dp, SGO_PLAYERS)
        assert result is None
        assert dp.sbme_confidence == 0.0


# ── Canonical Freshness (dfs/freshness.py) ──────────────────

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from dfs.freshness import (
    slate_freshness, is_stale_slate, is_current_slate, slate_date_et,
    is_customer_visible_slate, is_auto_publishable, is_optimizer_eligible_status,
)


class TestFreshness:
    def test_stale_past_date(self):
        """A slate date 3 days in the past is STALE."""
        past = datetime.now(ZoneInfo("America/New_York")) - timedelta(days=3)
        assert slate_freshness(past) == "STALE"
        assert is_stale_slate(past) is True

    def test_current_today(self):
        """Today in ET is CURRENT."""
        today = datetime.now(ZoneInfo("America/New_York"))
        assert slate_freshness(today) == "CURRENT"
        assert is_current_slate(today) is True

    def test_upcoming_future(self):
        """A slate date 3 days in the future is UPCOMING."""
        future = datetime.now(ZoneInfo("America/New_York")) + timedelta(days=3)
        assert slate_freshness(future) == "UPCOMING"
        assert is_stale_slate(future) is False
        assert is_current_slate(future) is False
        assert is_customer_visible_slate(future, "MLB") is False
        assert is_customer_visible_slate(future, "NFL") is True
        assert is_auto_publishable(future, "NCAAF") is True
        assert is_optimizer_eligible_status("DRAFT", future, "NFL") is True
        assert is_optimizer_eligible_status("DRAFT", future, "MLB") is False
        assert is_optimizer_eligible_status("PUBLISHED", future, "MLB") is True

    def test_none_start_time_is_stale(self):
        """Missing start_time → STALE (cannot be proven current)."""
        assert slate_freshness(None) == "STALE"
        assert is_stale_slate(None) is True

    def test_naive_datetime(self):
        """Naive datetime is interpreted relative to current system tz
        then converted to ET for comparison."""
        naive = datetime(2026, 1, 1, 12, 0)  # well in the past
        assert is_stale_slate(naive) is True

    def test_utc_midnight_edge(self):
        """A UTC time that maps to a different day in ET should be
        evaluated by its ET date."""
        utc = datetime(2026, 8, 11, 23, 0, tzinfo=timezone.utc)
        et_date = slate_date_et(utc)
        # 23:00 UTC = 19:00 ET, so it's still 8/11 in ET
        assert et_date is not None
        assert et_date.month == 8

    def test_current_not_stale(self):
        today = datetime.now(ZoneInfo("America/New_York"))
        assert is_stale_slate(today) is False


# ── Optimizer endpoint stale-slate gate ──────────────────────

import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from main import app
from models.database import Base, get_db
from dfs.db import DFSSlate, DFSPlayer

OPT_TEST_URL = "sqlite+aiosqlite://"
_opt_engine = create_async_engine(OPT_TEST_URL, echo=False)
_OptSession = async_sessionmaker(_opt_engine, class_=AsyncSession, expire_on_commit=False)


async def _opt_override_get_db():
    async with _OptSession() as s: yield s


app.dependency_overrides[get_db] = _opt_override_get_db


async def _opt_reset_db():
    async with _opt_engine.begin() as c:
        await c.run_sync(Base.metadata.drop_all)
        await c.run_sync(Base.metadata.create_all)


async def _opt_login(client, email="fresh@test.com"):
    await client.post("/api/auth/register", json={"email": email, "password": "securepass123"})
    r = await client.post("/api/auth/login", json={"email": email, "password": "securepass123"})
    return r.json()["access_token"]


# A feasibly solvable pool: 2 SP, 2 C, 2 1B, 2 2B, 2 3B, 2 SS, 4 OF = 16 players
_SLATE_POOL = [
    # id, name,          team, salary, pos
    ("1", "Ace Pitcher",   "HOU", 8500, "P"),
    ("2", "Mid Pitcher",   "LAD", 7500, "P"),
    ("3", "C1",            "NYY", 3500, "C"),
    ("4", "C2",            "BOS", 3200, "C"),
    ("5", "1B1",           "STL", 3700, "1B"),
    ("6", "1B2",           "CHC", 3400, "1B"),
    ("7", "2B1",           "ATL", 4000, "2B"),
    ("8", "2B2",           "MIA", 3600, "2B"),
    ("9", "3B1",           "TEX", 4000, "3B"),
    ("10","3B2",           "SEA", 3700, "3B"),
    ("11","SS1",           "SD",  4200, "SS"),
    ("12","SS2",           "ARI", 3900, "SS"),
    ("13","OF1",           "LAA", 3800, "OF"),
    ("14","OF2",           "CIN", 3600, "OF"),
    ("15","OF3",           "PIT", 3500, "OF"),
    ("16","OF4",           "COL", 3200, "OF"),
]


def _make_players(slate_id: int, pool: list = _SLATE_POOL):
    """Build DFSPlayer list from SLATE_POOL for insertion."""
    return [
        DFSPlayer(
            slate_id=slate_id,
            provider_player_id=pid,
            player_name=name,
            team=team,
            opponent="",
            position=pos,
            eligible_positions=[pos],
            salary=sal,
            game_info=f"{team}@OPP 08/11/2026 07:00PM ET",
        )
        for (pid, name, team, sal, pos) in pool
    ]


@pytest.fixture(autouse=True, scope="module")
async def _opt_module_setup():
    """Lifetime: module — create/drop tables once per test module."""
    await _opt_reset_db()
    yield
    await _opt_reset_db()


@pytest.fixture
async def opt_client():
    t = ASGITransport(app=app)
    async with AsyncClient(transport=t, base_url="http://test") as ac:
        yield ac


class TestOptimizerFreshnessGate:
    async def test_stale_published_slate_rejected(self, opt_client):
        """A published slate whose start_time is past → 400 stale error."""
        token = await _opt_login(opt_client)

        stale_time = datetime.now(timezone.utc) - timedelta(days=5)
        async with _OptSession() as s:
            s.add(DFSSlate(
                id=101, platform="draftkings", sport="MLB",
                slate_name="Old Slate", start_time=stale_time,
                status="PUBLISHED", player_count=len(_SLATE_POOL),
                data_source="native",
            ))
            for p in _make_players(101):
                s.add(p)
            await s.commit()

        resp = await opt_client.post(
            "/api/optimize",
            json={"slate_id": 101, "settings": {"platform": "draftkings", "strategy": "balanced", "num_lineups": 1}},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 400
        detail = resp.json()["detail"]
        assert "stale" in detail.lower()
        assert "upload or select" in detail.lower()

    async def test_current_published_slate_accepted(self, opt_client):
        """A published slate whose start_time is today (ET) must not be
        rejected by the freshness gate.  Projection data is mocked to satisfy
        the minimum-projected-players requirement (≥10 projected)."""
        from unittest.mock import patch

        token = await _opt_login(opt_client, "current@test.com")

        today_et = datetime.now(ZoneInfo("America/New_York"))
        async with _OptSession() as s:
            s.add(DFSSlate(
                id=102, platform="draftkings", sport="MLB",
                slate_name="Today Slate", start_time=today_et,
                status="PUBLISHED", player_count=len(_SLATE_POOL),
                data_source="native",
            ))
            for p in _make_players(102):
                s.add(p)
            await s.commit()

        # Mock build_sgo_intelligence to return enough projected player data
        # so the optimizer has ≥10 projected players to build a roster.
        mock_sgo = {}
        # _SLATE_POOL IDs are "1"–"16".  Give 14 players enough props
        # to meet the MIN_PROJECTED=10 threshold.
        for pid, name, team, sal, pos in _SLATE_POOL:
            if pos == "P":
                mock_sgo[pid] = {
                    "fantasyScore": 18.0,
                    "props": {"pitchingStrikeouts": 5.0, "pitchingOuts": 18.0},
                }
            else:
                mock_sgo[pid] = {"fantasyScore": 8.5}

        with patch("projection.sgo_intelligence.build_sgo_intelligence", return_value=mock_sgo) as mock_sgo_fn:
            # Make the mock awaitable
            import asyncio
            async def _mock(*a, **kw): return mock_sgo
            mock_sgo_fn.side_effect = _mock
            resp = await opt_client.post(
                "/api/optimize",
                json={"slate_id": 102, "settings": {"platform": "draftkings", "strategy": "balanced", "num_lineups": 1}},
                headers={"Authorization": f"Bearer {token}"},
            )
        # The freshness gate must not reject a current slate.
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        body = resp.json()
        assert body.get("data", {}).get("generated_lineups", -1) >= 1
        assert body.get("data", {}).get("source") == "native"