from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List

from .models import HealthSignal, ScoreResult, StartupProfile, StrategyRecommendation
from .services.monitoring import MonitoringService
from .services.scoring import ScoringService
from .services.strategy import FundConfig, StrategyService


@dataclass(frozen=True)
class PipelineResult:
    scores: List[ScoreResult]
    strategies: List[StrategyRecommendation]
    health_signals: List[HealthSignal]


class VCSelectorPipeline:
    def __init__(
        self,
        scoring_service: ScoringService,
        strategy_service: StrategyService,
        monitoring_service: MonitoringService,
    ) -> None:
        self.scoring_service = scoring_service
        self.strategy_service = strategy_service
        self.monitoring_service = monitoring_service

    def run(self, startups: Iterable[StartupProfile]) -> PipelineResult:
        score_results = self.scoring_service.rank(startups)
        score_index = {score.startup_id: score for score in score_results}

        strategies: List[StrategyRecommendation] = []
        health: List[HealthSignal] = []

        for startup in startups:
            score = score_index[startup.startup_id]
            strategy = self.strategy_service.recommend(startup, score)
            strategies.append(strategy)
            health.extend(self.monitoring_service.evaluate(startup))

        return PipelineResult(
            scores=score_results,
            strategies=strategies,
            health_signals=health,
        )

