from __future__ import annotations

import enum
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, Iterable, List, Optional


class CouponState(str, enum.Enum):
    ISSUED = "issued"
    RESERVED = "reserved"
    REDEEMED = "redeemed"
    EXPIRED = "expired"
    EXTENDED = "extended"
    PENDING_EXPIRATION = "pending_expiration"


@dataclass(frozen=True)
class ContactChannels:
    email: Optional[str] = None
    sms: Optional[str] = None
    push_token: Optional[str] = None

    def available_channels(self) -> List[str]:
        channels: List[str] = []
        if self.email:
            channels.append("email")
        if self.sms:
            channels.append("sms")
        if self.push_token:
            channels.append("push")
        return channels


@dataclass
class Coupon:
    coupon_id: str
    merchant_id: str
    campaign: str
    expires_at: datetime
    state: CouponState
    channels: List[str]
    face_value: float
    customer_contact: ContactChannels
    metadata: Dict[str, str] = field(default_factory=dict)

    def is_expired(self, now: datetime) -> bool:
        return now >= self.expires_at

    def is_active(self) -> bool:
        return self.state in {
            CouponState.ISSUED,
            CouponState.RESERVED,
            CouponState.PENDING_EXPIRATION,
        }


@dataclass
class DeactivationResult:
    coupon_id: str
    success_channels: List[str]
    failed_channels: Dict[str, str]

    @property
    def is_successful(self) -> bool:
        return not self.failed_channels


@dataclass
class Notification:
    coupon_id: str
    channels: Iterable[str]
    template: str
    payload: Dict[str, str]
    scheduled_at: datetime


def ensure_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)

