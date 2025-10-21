from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List

from ..models import ScoreResult, StrategyRecommendation, ThesisStatement, StartupProfile


@dataclass(frozen=True)
class FundConfig:
    name: str
    target_check_size_musd: float
    follow_on_ratio: float
    ownership_floor_pct: float


class StrategyService:
    def __init__(self, fund_config: FundConfig) -> None:
        self.fund_config = fund_config

    def recommend(self, startup: StartupProfile, score: ScoreResult) -> StrategyRecommendation:
        category = self._classify(score.total_score, startup.stage)
        check_multiplier = {
            "invest": 1.2,
            "watchlist": 0.6,
            "pass": 0.0,
        }[category]
        recommended_check = round(self.fund_config.target_check_size_musd * check_multiplier, 2)

        theses: List[ThesisStatement] = [
            ThesisStatement(
                headline="Strength: Growth momentum",
                details=f"QoQ ARR growth at {startup.traction.arr_growth_qoq_pct}% with ARR ${startup.traction.arr_musd}M.",
            ),
            ThesisStatement(
                headline="Market outlook",
                details=f"TAM ${startup.market.tam_musd}M with {startup.market.competition_intensity} competition.",
            ),
        ]

        if category == "pass":
            theses.append(
                ThesisStatement(
                    headline="Risk factors",
                    details="Current data suggests limited fit for the fund's mandate; reevaluate next quarter.",
                )
            )

        follow_on = "reserve" if category == "invest" else "defer"

        return StrategyRecommendation(
            startup_id=startup.startup_id,
            category=category,
            recommended_check_musd=recommended_check,
            follow_on_strategy=follow_on,
            ownership_target_pct=self._ownership_target(category),
            theses=theses,
        )

    def _classify(self, total_score: float, stage: str) -> str:
        if total_score >= 1.5:
            return "invest"
        if total_score >= 0.8:
            return "watchlist"
        if stage.lower() in {"seed", "pre-seed"} and total_score >= 0.7:
            return "watchlist"
        return "pass"

    def _ownership_target(self, category: str) -> float:
        if category == "invest":
            return max(self.fund_config.ownership_floor_pct, 15.0)
        if category == "watchlist":
            return max(self.fund_config.ownership_floor_pct / 2, 5.0)
        return 0.0

