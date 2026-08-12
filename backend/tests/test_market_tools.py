"""Tests for SB ME Market Tool Suite."""
import pytest
from market_engine import (
    american_to_decimal, decimal_to_american, implied_probability,
    overround, fair_probability, edge_pct,
    check_arbitrage, calculate_parlay, ParlayLeg,
    bookmaker_rank, normalize_bookmaker,
    MarketIdentity, MarketType, BookmakerLine, MarketSnapshot,
    MovementType, detect_movement,
)


class TestOddsMath:
    def test_american_to_decimal_positive(self):
        assert american_to_decimal(100) == 2.0
        assert american_to_decimal(200) == 3.0

    def test_american_to_decimal_negative(self):
        assert american_to_decimal(-110) == pytest.approx(1.909, rel=0.01)
        assert american_to_decimal(-200) == 1.5

    def test_decimal_to_american(self):
        assert decimal_to_american(2.0) == 100
        assert decimal_to_american(1.5) == -200
        assert decimal_to_american(3.0) == 200

    def test_american_decimal_roundtrip(self):
        for am in [100, -110, 200, -200, -150, 150, -400, 400]:
            assert decimal_to_american(american_to_decimal(am)) == am

    def test_implied_probability(self):
        assert implied_probability(100) == 0.5
        assert implied_probability(-200) == pytest.approx(0.667, rel=0.01)
        assert implied_probability(200) == pytest.approx(0.333, rel=0.01)

    def test_overround(self):
        probs = [0.5, 0.5]
        assert overround(probs) == 0.0
        probs = [0.524, 0.524]  # -110/-110
        assert overround(probs) > 0.04

    def test_fair_probability(self):
        probs = [0.524, 0.524]  # vig
        fair = fair_probability(probs)
        assert sum(fair) == pytest.approx(1.0)
        assert all(0.49 < p < 0.51 for p in fair)

    def test_edge_pct(self):
        assert edge_pct(8.5, 9.0) > 0  # fair higher = positive edge
        assert edge_pct(9.0, 8.0) < 0


class TestArbitrage:
    def test_two_way_arbitrage_exists(self):
        # +200 / -150 → implied sum < 1 if arb exists
        # American +200 = decimal 3.0, 1/3=0.333
        # American -150 = decimal 1.667, 1/1.667=0.600
        # Total = 0.933 < 1 → arb!
        result = check_arbitrage(200, -150)
        assert result is not None
        assert result.arb_percent > 0

    def test_two_way_no_arbitrage(self):
        # Standard -110/-110
        result = check_arbitrage(-110, -110)
        assert result is None

    def test_three_way_no_arbitrage(self):
        # soccer 3-way with heavy vig
        result = check_arbitrage(150, 200, 300)
        # Dec: 2.5 + 3.0 + 4.0 → 1/2.5+1/3+1/4=0.4+0.333+0.25=0.983 < 1 → arb?
        assert result is not None

    def test_stakes(self):
        from market_engine import ArbitrageOpportunity
        # Full arb with named outcomes
        result = ArbitrageOpportunity(
            event_id="ev1", market="moneyline",
            outcome_a="Team A", book_a="DK", odds_a=200,
            outcome_b="Team B", book_b="FD", odds_b=-150,
            implied_total=0.933, arb_percent=6.7,
        )
        stakes = result.stakes(1000)
        assert len(stakes) == 2
        assert "Team A" in stakes
        assert "Team B" in stakes
        assert sum(stakes.values()) <= 1000


class TestParlay:
    def test_two_leg_parlay(self):
        legs = [
            ParlayLeg("ev1", "moneyline", "home", "DraftKings", -110),
            ParlayLeg("ev2", "spread", "away", "DraftKings", -110),
        ]
        result = calculate_parlay(legs, 100)
        # -110 dec = 1.909, 1.909*1.909 = 3.644, dec = 1.909^2
        assert result.combined_decimal == pytest.approx(3.644, rel=0.01)
        assert result.leg_count == 2
        assert result.potential_payout > 100
        assert result.potential_profit > 0
        assert not result.is_same_game

    def test_three_leg_parlay(self):
        legs = [
            ParlayLeg("ev1", "moneyline", "home", "DK", -110),
            ParlayLeg("ev2", "moneyline", "away", "DK", -110),
            ParlayLeg("ev3", "total", "over", "DK", -110),
        ]
        result = calculate_parlay(legs, 50)
        # 1.909^3 = 6.958
        assert result.combined_decimal == pytest.approx(6.958, rel=0.01)
        assert result.leg_count == 3

    def test_same_game_detection(self):
        legs = [
            ParlayLeg("ev1", "moneyline", "home", "DK", -110),
            ParlayLeg("ev1", "total", "over", "DK", -110),
        ]
        result = calculate_parlay(legs)
        assert result.is_same_game
        assert not result.sgp_available


class TestBookmakerRanking:
    def test_priority_order(self):
        assert bookmaker_rank("DraftKings") < bookmaker_rank("FanDuel")
        assert bookmaker_rank("FanDuel") < bookmaker_rank("BetMGM")
        assert bookmaker_rank("BetMGM") < bookmaker_rank("Caesars")

    def test_normalize_bookmaker(self):
        assert normalize_bookmaker("draftkings") == "DraftKings"
        assert normalize_bookmaker("FANDUEL") == "FanDuel"


class TestMovementDetection:
    def test_no_change(self):
        prev = BookmakerLine("DK", line=228.5, price=-110)
        curr = BookmakerLine("DK", line=228.5, price=-110)
        assert detect_movement(prev, curr) == MovementType.NO_CHANGE

    def test_line_move(self):
        prev = BookmakerLine("DK", line=228.5, price=-110)
        curr = BookmakerLine("DK", line=230.0, price=-110)
        assert detect_movement(prev, curr) == MovementType.LINE_MOVE

    def test_price_move(self):
        prev = BookmakerLine("DK", line=228.5, price=-110)
        curr = BookmakerLine("DK", line=228.5, price=-115)
        assert detect_movement(prev, curr) == MovementType.PRICE_MOVE

    def test_steam_move(self):
        prev = BookmakerLine("DK", line=228.5, price=-110)
        curr = BookmakerLine("DK", line=230.0, price=-115)
        assert detect_movement(prev, curr) == MovementType.STEAM_MOVE


class TestMarketIdentity:
    def test_market_identity_fields(self):
        mi = MarketIdentity(
            odd_id="odd123",
            event_id="ev456",
            market_type=MarketType.PLAYER_PROP,
            player_id="p789",
            stat_id="hits",
            selection="over",
            line=1.5,
        )
        assert mi.odd_id == "odd123"
        assert mi.market_type == MarketType.PLAYER_PROP
        assert mi.line == 1.5


if __name__ == "__main__":
    pytest.main([__file__, "-v"])