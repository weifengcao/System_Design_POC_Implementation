from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, List

from .models import ContactChannels, Coupon, CouponState, ensure_utc


def _parse_datetime(raw: str) -> datetime:
    if raw.endswith("Z"):
        raw = raw.replace("Z", "+00:00")
    return datetime.fromisoformat(raw).astimezone(timezone.utc)


def load_coupons_from_file(path: str | Path) -> List[Coupon]:
    with open(path, "r", encoding="utf-8") as handle:
        blobs: Iterable[dict] = json.load(handle)

    coupons: List[Coupon] = []
    for blob in blobs:
        coupon = Coupon(
            coupon_id=blob["coupon_id"],
            merchant_id=blob["merchant_id"],
            campaign=blob["campaign"],
            expires_at=ensure_utc(_parse_datetime(blob["expires_at"])),
            state=CouponState(blob["state"]),
            channels=blob.get("channels", []),
            face_value=float(blob.get("face_value", 0.0)),
            customer_contact=ContactChannels(
                email=blob.get("customer_contact", {}).get("email"),
                sms=blob.get("customer_contact", {}).get("sms"),
                push_token=blob.get("customer_contact", {}).get("push_token"),
            ),
            metadata={
                key: str(value)
                for key, value in blob.items()
                if key
                not in {
                    "coupon_id",
                    "merchant_id",
                    "campaign",
                    "expires_at",
                    "state",
                    "channels",
                    "face_value",
                    "customer_contact",
                }
            },
        )
        coupons.append(coupon)
    return coupons

