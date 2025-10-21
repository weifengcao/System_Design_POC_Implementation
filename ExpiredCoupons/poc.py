from __future__ import annotations

import argparse
import logging
from datetime import datetime, timezone
from pathlib import Path

from src.ingestion import load_coupons_from_file
from src.orchestrator import ExpirationEngine
from src.services.deactivation import DeactivationService, SimulatedChannelAdapter
from src.services.notification import LoggingNotificationChannel, NotificationService
from src.storage import CouponRepository


def _setup_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )


def _default_data_path() -> Path:
    return Path(__file__).parent / "data" / "sample_coupons.json"


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="ExpiredCoupons POC runner")
    parser.add_argument(
        "--data-file",
        type=Path,
        default=_default_data_path(),
        help="Path to coupon data file",
    )
    parser.add_argument(
        "--window-seconds",
        type=int,
        default=7200,
        help="Window interval for upcoming expirations",
    )
    parser.add_argument(
        "--current-time",
        type=str,
        default="2024-07-10T21:30:00Z",
        help="Current time seed (ISO-8601, defaults to near sample data)",
    )
    parser.add_argument("--verbose", action="store_true", help="Enable debug logging")
    return parser.parse_args()


def _parse_time(raw: str) -> datetime:
    if raw.endswith("Z"):
        raw = raw.replace("Z", "+00:00")
    return datetime.fromisoformat(raw).astimezone(timezone.utc)


def main() -> None:
    args = _parse_args()
    _setup_logging(args.verbose)

    coupons = load_coupons_from_file(args.data_file)
    repository = CouponRepository(coupons)

    deactivation = DeactivationService(
        adapters=[
            SimulatedChannelAdapter("ecommerce", failure_rate=0.05),
            SimulatedChannelAdapter("pos", failure_rate=0.15),
            SimulatedChannelAdapter("marketplace", failure_rate=0.2),
        ]
    )
    notification = NotificationService(
        channels=[
            LoggingNotificationChannel("email"),
            LoggingNotificationChannel("sms"),
            LoggingNotificationChannel("push"),
        ]
    )

    engine = ExpirationEngine(
        repository=repository,
        deactivation_service=deactivation,
        notification_service=notification,
    )

    now = _parse_time(args.current_time)
    report = engine.process_window(now=now, within_seconds=args.window_seconds)

    for record in report.processed:
        logging.info(
            "Coupon %s transitioned %s -> %s. Deactivation success=%s failed=%s notifications=%s",
            record.coupon_id,
            record.previous_state.value,
            record.new_state.value,
            record.deactivation_result.success_channels,
            record.deactivation_result.failed_channels,
            record.notification_channels,
        )

    logging.info("Processing summary: %s", report.summary())


if __name__ == "__main__":
    main()
