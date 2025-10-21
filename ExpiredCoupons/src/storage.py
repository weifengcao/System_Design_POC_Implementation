from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta
from typing import Dict, Iterable, List, Optional

from .models import Coupon, CouponState, ensure_utc


class CouponRepository:
    """In-memory coupon repository used by the POC."""

    def __init__(self, coupons: Optional[Iterable[Coupon]] = None) -> None:
        self._coupons: Dict[str, Coupon] = {}
        if coupons:
            for coupon in coupons:
                self._coupons[coupon.coupon_id] = coupon

    def list_all(self) -> List[Coupon]:
        return list(self._coupons.values())

    def upsert(self, coupon: Coupon) -> None:
        self._coupons[coupon.coupon_id] = coupon

    def get(self, coupon_id: str) -> Optional[Coupon]:
        return self._coupons.get(coupon_id)

    def mark_state(self, coupon_id: str, new_state: CouponState) -> Coupon:
        coupon = self._require(coupon_id)
        updated = replace(coupon, state=new_state)
        self.upsert(updated)
        return updated

    def due_for_expiration(
        self,
        now: datetime,
        within_seconds: int,
    ) -> List[Coupon]:
        current = ensure_utc(now)
        horizon = current + timedelta(seconds=within_seconds)
        due: List[Coupon] = []
        for coupon in self._coupons.values():
            if not coupon.is_active():
                continue
            if current <= coupon.expires_at <= horizon:
                due.append(coupon)
        return due

    def _require(self, coupon_id: str) -> Coupon:
        coupon = self.get(coupon_id)
        if not coupon:
            raise KeyError(f"Coupon {coupon_id} not found")
        return coupon
