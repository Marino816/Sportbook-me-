"""
SB-Me Coach — Performance analysis, strategy evaluation, and recommendation engines.

All calculations are deterministic and testable.
"""

from typing import Dict, List, Optional


# ── Contest Evaluator ────────────────────────────────────────

class ContestEvaluator:
    """Evaluate a single contest result against projections and strategy."""

    @staticmethod
    def evaluate(result: dict) -> dict:
        """Return structured evaluation of a single contest result."""
        ev = {
            "contest_id": result.get("contest_id"),
            "cashed": False,
            "projection_error": None,
            "percentile": None,
            "score_vs_cash": None,
        }
        score = result.get("final_lineup_score")
        cash = result.get("cash_line")
        winning = result.get("winning_score")
        entries = result.get("entry_count")
        position = result.get("finishing_position")
        projected = result.get("projected_score")

        if cash is not None and score is not None:
            ev["cashed"] = score >= cash
            ev["score_vs_cash"] = round(score - cash, 1)
        if entries and position:
            ev["percentile"] = round((1.0 - position / entries) * 100, 1)
        if projected is not None and score is not None:
            ev["projection_error"] = round(score - projected, 1)

        return ev

    @staticmethod
    def batch_evaluate(results: List[dict]) -> dict:
        evals = [ContestEvaluator.evaluate(r) for r in results]
        cashed = sum(1 for e in evals if e["cashed"])
        errors = [e["projection_error"] for e in evals if e["projection_error"] is not None]
        return {
            "total": len(evals),
            "cashed": cashed,
            "cash_rate": round(cashed / max(len(evals), 1) * 100, 1),
            "avg_projection_error": round(sum(errors) / max(len(errors), 1), 1) if errors else None,
            "median_projection_error": round(sorted(errors)[len(errors)//2], 1) if errors else None,
            "evaluations": evals,
        }


# ── Performance Analyzer ─────────────────────────────────────

class PerformanceAnalyzer:
    """Calculate ROI, bankroll trends, and financial metrics."""

    @staticmethod
    def calculate_roi(results: List[dict]) -> dict:
        fees = [r.get("entry_fee") for r in results if r.get("entry_fee") is not None]
        payouts = [r.get("payout") for r in results if r.get("payout") is not None]
        total_fees = sum(fees)
        total_payouts = sum(payouts)
        return {
            "total_entries": len(results),
            "total_fees": round(total_fees, 2),
            "total_winnings": round(total_payouts, 2),
            "net_profit": round(total_payouts - total_fees, 2),
            "roi": round((total_payouts - total_fees) / max(total_fees, 0.01) * 100, 1),
            "entries_with_fee": len(fees),
            "entries_with_payout": len(payouts),
            "missing_fee_count": len(results) - len(fees),
            "missing_payout_count": len(results) - len(payouts),
        }

    @staticmethod
    def cash_rate(results: List[dict]) -> float:
        if not results:
            return 0.0
        cashed = sum(1 for r in results
                     if r.get("final_lineup_score") is not None
                     and r.get("cash_line") is not None
                     and r["final_lineup_score"] >= r["cash_line"])
        return round(cashed / len(results) * 100, 1)

    @staticmethod
    def projection_accuracy(results: List[dict]) -> dict:
        errors = []
        for r in results:
            proj = r.get("projected_score")
            actual = r.get("final_lineup_score")
            if proj is not None and actual is not None:
                errors.append(actual - proj)
        if not errors:
            return {"avg_error": None, "median_error": None, "mae": None, "count": 0}
        abs_errors = [abs(e) for e in errors]
        return {
            "avg_error": round(sum(errors) / len(errors), 2),
            "median_error": round(sorted(errors)[len(errors)//2], 2),
            "mae": round(sum(abs_errors) / len(abs_errors), 2),
            "count": len(errors),
        }


# ── Strategy Analyzer ────────────────────────────────────────

class StrategyAnalyzer:
    """Evaluate strategy performance across contests."""

    @staticmethod
    def analyze_by_strategy(results: List[dict]) -> List[dict]:
        groups = {}
        for r in results:
            s = r.get("strategy_profile", "unknown")
            if s not in groups:
                groups[s] = []
            groups[s].append(r)
        return [{
            "strategy": name,
            "entries": len(entries),
            "cash_rate": PerformanceAnalyzer.cash_rate(entries),
            "avg_finish": round(sum(e.get("finishing_position", 0) or 0 for e in entries) / max(len(entries), 1), 1),
            "recommendation": "favor" if PerformanceAnalyzer.cash_rate(entries) > 40 else "review",
            "sample_warning": "Small sample" if len(entries) < 5 else None,
        } for name, entries in sorted(groups.items())]

    @staticmethod
    def exposure_analysis(results: List[dict]) -> dict:
        """Aggregate player/team exposure across results."""
        players = {}
        teams = {}
        for r in results:
            stacks = r.get("stack_summary") or {}
            for p in stacks.get("players", []):
                pid = p.get("id")
                if pid:
                    players[pid] = players.get(pid, 0) + 1
            for t in stacks.get("teams", []):
                if t:
                    teams[t] = teams.get(t, 0) + 1
        total = max(len(results), 1)
        return {
            "player_exposure": {k: round(v / total * 100, 1) for k, v in sorted(players.items(), key=lambda x: -x[1])[:10]},
            "team_exposure": {k: round(v / total * 100, 1) for k, v in sorted(teams.items(), key=lambda x: -x[1])[:10]},
        }


# ── Recommendation Engine ────────────────────────────────────

class RecommendationEngine:
    """Generate actionable recommendations from performance data."""

    @staticmethod
    def generate(metrics: dict, findings: List[dict], results: List[dict]) -> List[dict]:
        recs = []
        sample = len(results)

        # Cash rate
        cr = metrics.get("cash_rate", 0)
        if cr < 30 and sample >= 5:
            recs.append({"rec": "Review strategy selection", "rationale": f"Cash rate {cr}% below 30%. Consider more conservative strategies.", "priority": "high", "sample": sample, "confidence": 0.7})

        # Projection error
        pa = metrics.get("projection_accuracy", {})
        mae = pa.get("mae")
        if mae is not None and mae > 15 and sample >= 3:
            recs.append({"rec": "Verify data freshness before lock", "rationale": f"Avg projection error {mae:.1f} FP. Scout alerts may be affecting accuracy.", "priority": "medium", "sample": sample, "confidence": 0.6})

        # ROI
        roi = metrics.get("roi", 0)
        if roi < -10 and sample >= 5:
            recs.append({"rec": "Reduce contest entry volume", "rationale": f"ROI {roi}%. Consider fewer, higher-quality single entries.", "priority": "high", "sample": sample, "confidence": 0.65})

        # Stale lineups
        stale = sum(1 for r in results if r.get("stale_at_lock"))
        if stale > 0:
            recs.append({"rec": "Refresh lineups closer to lock", "rationale": f"{stale}/{sample} lineups were stale at lock.", "priority": "medium", "sample": sample, "confidence": 0.8})

        # Small sample
        if sample < 5:
            recs.append({"rec": "Play more contests for reliable analysis", "rationale": f"Only {sample} results. Need 10+ for confident recommendations.", "priority": "low", "sample": sample, "confidence": 0.3})

        return recs


# ── Confidence Calculator ────────────────────────────────────

class ConfidenceCalculator:
    """Deterministic recommendation confidence based on data quality."""

    @staticmethod
    def calculate(sample_size: int, data_completeness: float, recency_days: int,
                  cross_contest_consistency: float = 0.5) -> float:
        sample_factor = min(1.0, sample_size / 20.0)
        recency_factor = max(0.1, 1.0 - recency_days / 90.0)
        score = (sample_factor * 0.5 + data_completeness * 0.3 + recency_factor * 0.1 + cross_contest_consistency * 0.1)
        return round(min(1.0, max(0.0, score)), 3)