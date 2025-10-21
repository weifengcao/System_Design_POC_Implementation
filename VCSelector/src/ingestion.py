from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable, List

from .models import (
    FundingHistory,
    MarketContext,
    PortfolioMetrics,
    Signal,
    StartupProfile,
    TeamProfile,
    TractionSnapshot,
)


def load_startups(path: Path) -> List[StartupProfile]:
    with path.open("r", encoding="utf-8") as handle:
        items: Iterable[dict] = json.load(handle)

    profiles: List[StartupProfile] = []
    for item in items:
        profile = StartupProfile(
            startup_id=item["startup_id"],
            name=item["name"],
            sector=item["sector"],
            stage=item["stage"],
            funding_history=FundingHistory(**item["funding_history"]),
            team=TeamProfile(**item["team"]),
            traction=TractionSnapshot(**item["traction"]),
            market=MarketContext(**item["market"]),
            signals=[Signal(**signal) for signal in item.get("signals", [])],
            portfolio_metrics=PortfolioMetrics(**item["portfolio_metrics"]),
            metadata={
                key: str(value)
                for key, value in item.items()
                if key
                not in {
                    "startup_id",
                    "name",
                    "sector",
                    "stage",
                    "funding_history",
                    "team",
                    "traction",
                    "market",
                    "signals",
                    "portfolio_metrics",
                }
            },
        )
        profiles.append(profile)
    return profiles

