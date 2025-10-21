from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List

from .models import Coupon, CouponState, DeactivationResult, ensure_utc
from .services.deactivation import DeactivationService
from .services.notification import NotificationService
from .storage import CouponRepository

logger = logging.getLogger(__name__)


@dataclass
class CouponProcessingRecord:
    coupon_id: str
    previous_state: CouponState
    new_state: CouponState
    deactivation_result: DeactivationResult
    notification_channels: List[str]


@dataclass
class ProcessingReport:
    started_at: datetime
    completed_at: datetime | None = None
    processed: List[CouponProcessingRecord] = field(default_factory=list)
    failures: Dict[str, str] = field(default_factory=dict)

    def mark_complete(self, completed_at: datetime) -> None:
        self.completed_at = completed_at

    def summary(self) -> Dict[str, int]:
        expired = sum(1 for r in self.processed if r.new_state == CouponState.EXPIRED)
        pending = sum(1 for r in self.processed if r.new_state == CouponState.PENDING_EXPIRATION)
        return {
            "processed": len(self.processed),
            "expired": expired,
            "pending": pending,
            "failures": len(self.failures),
        }


class ExpirationEngine:
    def __init__(
        self,
        repository: CouponRepository,
        deactivation_service: DeactivationService,
        notification_service: NotificationService,
    ) -> None:
        self.repository = repository
        self.deactivation_service = deactivation_service
        self.notification_service = notification_service

    def process_window(self, now: datetime, within_seconds: int) -> ProcessingReport:
        current = ensure_utc(now)
        due = self.repository.due_for_expiration(current, within_seconds)
        logger.info("Found %s coupons due by %s", len(due), current + timedelta(seconds=within_seconds))
        report = ProcessingReport(started_at=current)

        for coupon in due:
            original_state = coupon.state
            try:
                record = self._expire_coupon(coupon, current)
                report.processed.append(
                    CouponProcessingRecord(
                        coupon_id=coupon.coupon_id,
                        previous_state=original_state,
                        new_state=record["new_state"],
                        deactivation_result=record["deactivation_result"],
                        notification_channels=record["notification_channels"],
                    )
                )
            except Exception as exc:  # pragma: no cover - defensive.
                logger.exception("Failed processing coupon %s", coupon.coupon_id)
                report.failures[coupon.coupon_id] = str(exc)

        report.mark_complete(ensure_utc(datetime.utcnow()))
        return report

    def _expire_coupon(self, coupon: Coupon, current: datetime) -> Dict[str, object]:
        logger.debug("Processing coupon %s", coupon.coupon_id)
        self.repository.mark_state(coupon.coupon_id, CouponState.PENDING_EXPIRATION)

        deactivation = self.deactivation_service.deactivate(coupon)
        if deactivation.is_successful:
            new_state = CouponState.EXPIRED
            self.repository.mark_state(coupon.coupon_id, new_state)
        else:
            new_state = CouponState.PENDING_EXPIRATION
            logger.warning(
                "Coupon %s partial failure channels=%s",
                coupon.coupon_id,
                list(deactivation.failed_channels.keys()),
            )

        notification_channels = self.notification_service.notify(
            coupon=coupon,
            template="coupon_expired" if deactivation.is_successful else "coupon_expiration_delayed",
            payload={
                "coupon_id": coupon.coupon_id,
                "merchant_id": coupon.merchant_id,
                "state": new_state.value,
                "expires_at": coupon.expires_at.isoformat(),
            },
            scheduled_at=current,
        )

        return {
            "new_state": new_state,
            "deactivation_result": deactivation,
            "notification_channels": notification_channels,
        }
