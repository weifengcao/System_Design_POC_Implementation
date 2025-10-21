from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path

from src.ingestion import load_startups
from src.pipeline import VCSelectorPipeline
from src.services.monitoring import MonitoringService
from src.services.scoring import ScoringService
from src.services.strategy import FundConfig, StrategyService


def _setup_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )


def _default_data_path() -> Path:
    return Path(__file__).parent / "data" / "startups_fixture.json"


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="VCSelector POC runner")
    parser.add_argument(
        "--data-file",
        type=Path,
        default=_default_data_path(),
        help="Path to startup fixture data",
    )
    parser.add_argument(
        "--fund-name",
        type=str,
        default="Global Growth Fund",
        help="Fund configuration name",
    )
    parser.add_argument(
        "--check-size",
        type=float,
        default=5.0,
        help="Base check size in millions USD",
    )
    parser.add_argument(
        "--ownership-floor",
        type=float,
        default=7.5,
        help="Ownership floor percentage",
    )
    parser.add_argument("--verbose", action="store_true")
    return parser.parse_args()


def _format_score(score) -> dict:
    return {
        "startup_id": score.startup_id,
        "total_score": score.total_score,
        "percentile": score.percentile,
        "factors": [
            {
                "name": factor.name,
                "weight": factor.weight,
                "value": factor.value,
                "contribution": factor.contribution,
                "reasoning": factor.reasoning,
            }
            for factor in score.factors
        ],
    }


def _format_strategy(strategy) -> dict:
    return {
        "startup_id": strategy.startup_id,
        "category": strategy.category,
        "recommended_check_musd": strategy.recommended_check_musd,
        "follow_on_strategy": strategy.follow_on_strategy,
        "ownership_target_pct": strategy.ownership_target_pct,
        "theses": [
            {"headline": thesis.headline, "details": thesis.details}
            for thesis in strategy.theses
        ],
    }


def main() -> None:
    args = _parse_args()
    _setup_logging(args.verbose)

    startups = load_startups(args.data_file)
    logging.info("Loaded %s startups from %s", len(startups), args.data_file)

    pipeline = VCSelectorPipeline(
        scoring_service=ScoringService(),
        strategy_service=StrategyService(
            FundConfig(
                name=args.fund_name,
                target_check_size_musd=args.check_size,
                follow_on_ratio=0.6,
                ownership_floor_pct=args.ownership_floor,
            )
        ),
        monitoring_service=MonitoringService(),
    )

    result = pipeline.run(startups)

    payload = {
        "scores": [_format_score(score) for score in result.scores],
        "strategies": [_format_strategy(strategy) for strategy in result.strategies],
        "health_signals": [
            {
                "startup_id": signal.startup_id,
                "severity": signal.severity,
                "indicator": signal.indicator,
                "message": signal.message,
            }
            for signal in result.health_signals
        ],
    }
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()

