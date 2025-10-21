from __future__ import annotations

import logging
import random
from dataclasses import dataclass
from typing import Dict, Iterable, List, Protocol

from ..models import Coupon, DeactivationResult

logger = logging.getLogger(__name__)


class ChannelAdapter(Protocol):
    channel_name: str

    def deactivate(self, coupon: Coupon) -> bool:
        ...


@dataclass
class SimulatedChannelAdapter:
    channel_name: str
    failure_rate: float = 0.0

    def deactivate(self, coupon: Coupon) -> bool:
        # Simulates success/failure for demo purposes.
        roll = random.random()
        success = roll >= self.failure_rate
        logger.debug(
            "Channel %s processing coupon %s: roll=%.3f success=%s",
            self.channel_name,
            coupon.coupon_id,
            roll,
            success,
        )
        return success


class DeactivationService:
    def __init__(self, adapters: Iterable[ChannelAdapter]) -> None:
        self._adapters: Dict[str, ChannelAdapter] = {
            adapter.channel_name: adapter for adapter in adapters
        }

    def deactivate(self, coupon: Coupon) -> DeactivationResult:
        success: List[str] = []
        failed: Dict[str, str] = {}

        for channel in coupon.channels:
            adapter = self._adapters.get(channel)
            if not adapter:
                failed[channel] = "no_adapter_configured"
                continue
            try:
                if adapter.deactivate(coupon):
                    success.append(channel)
                else:
                    failed[channel] = "simulated_failure"
            except Exception as exc:  # pragma: no cover - defensive logging.
                logger.exception("Channel %s failed for coupon %s", channel, coupon.coupon_id)
                failed[channel] = f"exception:{exc}"

        return DeactivationResult(
            coupon_id=coupon.coupon_id,
            success_channels=success,
            failed_channels=failed,
        )

