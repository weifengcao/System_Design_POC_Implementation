from __future__ import annotations

from typing import Dict, List, Optional

from . import models


class InMemoryStore:
    """Simple mutable storage for the OrbManager POC."""

    def __init__(self) -> None:
        self.tenants: Dict[str, models.Tenant] = {}
        self.orbs: Dict[str, models.Orb] = {}
        self.telemetry: Dict[int, models.Telemetry] = {}
        self.commands: Dict[str, models.Command] = {}
        self.alerts: Dict[str, models.Alert] = {}
        self._telemetry_seq = 0

    # Tenant helpers
    def add_tenant(self, tenant: models.Tenant) -> models.Tenant:
        self.tenants[tenant.id] = tenant
        return tenant

    # Orb helpers
    def add_orb(self, orb: models.Orb) -> models.Orb:
        self.orbs[orb.id] = orb
        return orb

    # Telemetry helpers
    def add_telemetry(self, telemetry: models.Telemetry) -> models.Telemetry:
        self._telemetry_seq += 1
        telemetry.id = self._telemetry_seq
        self.telemetry[telemetry.id] = telemetry
        return telemetry

    def get_recent_telemetry(self, orb_id: str, limit: int) -> List[models.Telemetry]:
        rows = [t for t in self.telemetry.values() if t.orb_id == orb_id]
        rows.sort(key=lambda t: t.created_at, reverse=True)
        return rows[:limit]

    # Command helpers
    def add_command(self, command: models.Command) -> models.Command:
        self.commands[command.id] = command
        return command

    def list_commands(self, orb_id: str, status: Optional[str] = None) -> List[models.Command]:
        commands = [c for c in self.commands.values() if c.orb_id == orb_id]
        if status:
            commands = [c for c in commands if c.status == status]
        commands.sort(key=lambda c: c.created_at)
        return commands

    # Alert helpers
    def add_alert(self, alert: models.Alert) -> models.Alert:
        self.alerts[alert.id] = alert
        return alert

    def list_alerts(self, orb_id: Optional[str], only_open: bool) -> List[models.Alert]:
        rows = list(self.alerts.values())
        if orb_id:
            rows = [a for a in rows if a.orb_id == orb_id]
        if only_open:
            rows = [a for a in rows if not a.resolved]
        rows.sort(key=lambda a: a.created_at, reverse=True)
        return rows


store = InMemoryStore()


def get_store() -> InMemoryStore:
    return store
