from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Iterable, List


@dataclass(frozen=True)
class FundingHistory:
    total_raised_musd: float
    last_round_months_ago: int
    lead_investor: str


@dataclass(frozen=True)
class TeamProfile:
    founders: int
    founder_exits: int
    avg_years_experience: float


@dataclass(frozen=True)
class TractionSnapshot:
    arr_musd: float
    arr_growth_qoq_pct: float
    customers: int
    nps: float


@dataclass(frozen=True)
class MarketContext:
    tam_musd: float
    competition_intensity: str


@dataclass(frozen=True)
class PortfolioMetrics:
    burn_multiple: float
    runway_months: int


@dataclass(frozen=True)
class Signal:
    type: str
    score: float


@dataclass
class StartupProfile:
    startup_id: str
    name: str
    sector: str
    stage: str
    funding_history: FundingHistory
    team: TeamProfile
    traction: TractionSnapshot
    market: MarketContext
    signals: List[Signal]
    portfolio_metrics: PortfolioMetrics
    metadata: Dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class ScoreFactor:
    name: str
    weight: float
    value: float
    contribution: float
    reasoning: str


@dataclass(frozen=True)
class ScoreResult:
    startup_id: str
    total_score: float
    percentile: float
    factors: Iterable[ScoreFactor]


@dataclass(frozen=True)
class ThesisStatement:
    headline: str
    details: str


@dataclass(frozen=True)
class StrategyRecommendation:
    startup_id: str
    category: str
    recommended_check_musd: float
    follow_on_strategy: str
    ownership_target_pct: float
    theses: Iterable[ThesisStatement]


@dataclass(frozen=True)
class HealthSignal:
    startup_id: str
    severity: str
    indicator: str
    message: str

