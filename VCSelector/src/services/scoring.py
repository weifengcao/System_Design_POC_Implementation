from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Iterable, List, Tuple

from ..models import ScoreFactor, ScoreResult, StartupProfile


@dataclass(frozen=True)
class ScoringWeights:
    growth_weight: float = 0.3
    revenue_weight: float = 0.2
    team_weight: float = 0.2
    market_weight: float = 0.15
    signal_weight: float = 0.1
    efficiency_weight: float = 0.05


class ScoringService:
    def __init__(self, weights: ScoringWeights | None = None) -> None:
        self.weights = weights or ScoringWeights()

    def score(self, startup: StartupProfile) -> ScoreResult:
        factors: List[ScoreFactor] = []

        def add_factor(name: str, weight: float, value: float, reasoning: str) -> None:
            contribution = max(value, 0.0) * weight
            factors.append(
                ScoreFactor(
                    name=name,
                    weight=weight,
                    value=round(value, 3),
                    contribution=round(contribution, 3),
                    reasoning=reasoning,
                )
            )

        growth_score = min(startup.traction.arr_growth_qoq_pct / 50.0, 2.0)
        add_factor(
            "Growth momentum",
            self.weights.growth_weight,
            growth_score,
            f"QoQ ARR growth {startup.traction.arr_growth_qoq_pct}%",
        )

        revenue_base = math.log1p(startup.traction.arr_musd) / math.log(1 + 25)
        add_factor(
            "Revenue scale",
            self.weights.revenue_weight,
            revenue_base,
            f"ARR ${startup.traction.arr_musd}M",
        )

        team_score = (
            (startup.team.founders * 0.1)
            + (startup.team.founder_exits * 0.4)
            + (startup.team.avg_years_experience / 10.0)
        ) / 2.5
        add_factor(
            "Team strength",
            self.weights.team_weight,
            min(team_score, 1.5),
            "Experience and past exits",
        )

        competition_modifier = {
            "low": 1.2,
            "medium": 1.0,
            "high": 0.75,
        }.get(startup.market.competition_intensity.lower(), 1.0)
        market_score = (startup.market.tam_musd / 2000.0) * competition_modifier
        add_factor(
            "Market quality",
            self.weights.market_weight,
            min(market_score, 2.0),
            f"TAM ${startup.market.tam_musd}M, competition {startup.market.competition_intensity}",
        )

        if startup.signals:
            signal_value = sum(signal.score for signal in startup.signals) / len(startup.signals)
        else:
            signal_value = 0.4
        add_factor(
            "External signals",
            self.weights.signal_weight,
            signal_value,
            "Aggregated sentiment/news/product signals",
        )

        burn_multiple = startup.portfolio_metrics.burn_multiple
        runway = startup.portfolio_metrics.runway_months
        efficiency_score = max(0.0, min(1.5, (runway / 18.0) * (2.5 - burn_multiple)))
        add_factor(
            "Capital efficiency",
            self.weights.efficiency_weight,
            efficiency_score,
            f"Burn multiple {burn_multiple}, runway {runway} months",
        )

        total = round(sum(f.contribution for f in factors), 3)
        percentile = round(min(99.9, total * 33), 2)

        return ScoreResult(
            startup_id=startup.startup_id,
            total_score=total,
            percentile=percentile,
            factors=factors,
        )

    def rank(self, startups: Iterable[StartupProfile]) -> List[ScoreResult]:
        results = [self.score(startup) for startup in startups]
        return sorted(results, key=lambda res: res.total_score, reverse=True)

