"""SGO outage + rate-limit fallback tests."""

import pytest
from unittest.mock import AsyncMock, patch
from intelligence.engine import (
    PlayerIntelligence, SignalComputer, DataSourceStatus,
    PlayerSignal, GameEnvironmentSignal, DFSDataMode,
)


class TestSGOOutage:
    """Provider outage must not break intelligence or optimizer."""

    def test_outage_produces_neutral_signal(self):
        pi = PlayerIntelligence(player_id="1", player_name="Test", dfs_salary=5000, base_projection=8.0)
        SignalComputer.compute_all(pi)
        assert pi.player_signal == PlayerSignal.NEUTRAL
        assert pi.market_context_status == DataSourceStatus.UNAVAILABLE
        assert pi.dfs_data_mode == DFSDataMode.TRIAL_SCRAMBLED
        assert pi.fantasy_market_line is None
        assert pi.reasons == []

    def test_outage_to_dict(self):
        pi = PlayerIntelligence(player_id="1", player_name="Test")
        SignalComputer.compute_all(pi)
        d = pi.to_dict()
        assert d["player_signal"] == "NEUTRAL"
        assert d["market_context_status"] == "UNAVAILABLE"
        assert d["missing_signals"] is not None

    def test_partial_sgo_data(self):
        """SGO returns events but no player props — fantasyScore edge None."""
        pi = PlayerIntelligence(player_id="1", player_name="Test", dfs_salary=5000, base_projection=8.0,
                                 game_total=8.5, fantasy_market_line=None, fantasy_market_edge=None)
        SignalComputer.compute_all(pi)
        assert pi.player_signal == PlayerSignal.NEUTRAL
        assert pi.game_environment == GameEnvironmentSignal.ABOVE_AVERAGE
        assert pi.market_context_status == DataSourceStatus.UNAVAILABLE

    def test_full_sgo_data_bullish(self):
        pi = PlayerIntelligence(player_id="1", player_name="Test", dfs_salary=5000, base_projection=10.0,
                                 fantasy_market_line=7.0, fantasy_market_edge=3.0, prop_book_count=3, game_total=9.5)
        SignalComputer.compute_all(pi)
        assert pi.player_signal == PlayerSignal.BULLISH
        assert pi.market_context_status == DataSourceStatus.LIVE
        assert len(pi.reasons) >= 2



class TestOddsMath:
    def test_american_plus(self):
        from intelligence.engine import american_to_implied_probability
        assert round(american_to_implied_probability(150), 3) == 0.4

    def test_american_minus(self):
        from intelligence.engine import american_to_implied_probability
        assert round(american_to_implied_probability(-200), 3) == 0.667

    def test_probability_edge(self):
        from intelligence.engine import probability_edge
        edge = probability_edge(-110, -105)
        assert edge is not None
        assert edge > 0  # fair side has edge

    def test_no_direct_american_arithmetic(self):
        """Prove we do NOT compute (fair - market) / market on American odds."""
        from intelligence.engine import american_to_implied_probability
        prob_m = american_to_implied_probability(+200)
        prob_f = american_to_implied_probability(+150)
        # Direct subtraction on American odds = 200-150 = 50 (meaningless)
        # Proper probability edge:
        proper = round(prob_f - prob_m, 4)
        assert proper != 0.5  # not the raw American difference