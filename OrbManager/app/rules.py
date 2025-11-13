from __future__ import annotations

from datetime import datetime

from . import models
from .database import InMemoryStore

LOW_BATTERY_THRESHOLD = 25.0  # percent
LOW_BATTERY_CLEAR = 35.0


def evaluate_low_battery(store: InMemoryStore, orb: models.Orb) -> None:
    if orb.battery_pct is None:
        return

    open_alerts = [alert for alert in store.list_alerts(orb.id, only_open=True) if alert.code == "LOW_BATTERY"]
    alert = open_alerts[0] if open_alerts else None

    if orb.battery_pct <= LOW_BATTERY_THRESHOLD and alert is None:
        store.add_alert(
            models.Alert(
                orb_id=orb.id,
                level="warning",
                code="LOW_BATTERY",
                message=f"Orb battery is critically low at {orb.battery_pct:.1f}%",
                details={"battery_pct": orb.battery_pct},
            )
        )
    elif orb.battery_pct >= LOW_BATTERY_CLEAR and alert:
        alert.resolved = True
        alert.resolved_at = datetime.utcnow()
        alert.details = {"battery_pct": orb.battery_pct}
