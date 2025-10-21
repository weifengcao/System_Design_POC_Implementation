from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Iterable, List, Protocol

from ..models import ContactChannels, Coupon, Notification

logger = logging.getLogger(__name__)


class NotificationChannel(Protocol):
    name: str

    def send(self, notification: Notification, contact: ContactChannels) -> bool:
        ...


@dataclass
class LoggingNotificationChannel:
    name: str

    def send(self, notification: Notification, contact: ContactChannels) -> bool:
        logger.info(
            "Notify via %s coupon=%s template=%s payload=%s",
            self.name,
            notification.coupon_id,
            notification.template,
            notification.payload,
        )
        return True


class NotificationService:
    def __init__(self, channels: Iterable[NotificationChannel]) -> None:
        self._channels = {channel.name: channel for channel in channels}

    def notify(
        self,
        coupon: Coupon,
        template: str,
        payload: dict,
        scheduled_at: datetime,
    ) -> List[str]:
        notification = Notification(
            coupon_id=coupon.coupon_id,
            channels=coupon.customer_contact.available_channels(),
            template=template,
            payload=payload,
            scheduled_at=scheduled_at,
        )
        successes: List[str] = []
        for channel in notification.channels:
            handler = self._channels.get(channel)
            if not handler:
                logger.warning("No handler configured for channel=%s", channel)
                continue
            if handler.send(notification, coupon.customer_contact):
                successes.append(channel)
        return successes

