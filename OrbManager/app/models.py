from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, Optional


@dataclass
class Tenant:
    name: str
    contact_email: Optional[str] = None
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class Orb:
    tenant_id: str
    name: str
    orb_type: str
    firmware_version: str
    status: str = "inactive"
    last_seen_at: Optional[datetime] = None
    battery_pct: Optional[float] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class Telemetry:
    orb_id: str
    battery_pct: Optional[float] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    speed: Optional[float] = None
    payload: Dict[str, Any] = field(default_factory=dict)
    id: int = 0
    created_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class Command:
    orb_id: str
    command_type: str
    payload: Dict[str, Any] = field(default_factory=dict)
    status: str = "pending"
    dispatched_at: Optional[datetime] = None
    acknowledged_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    ack_payload: Optional[Dict[str, Any]] = None
    failure_reason: Optional[str] = None
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class Alert:
    orb_id: str
    level: str
    code: str
    message: str
    details: Dict[str, Any] = field(default_factory=dict)
    resolved: bool = False
    resolved_at: Optional[datetime] = None
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: datetime = field(default_factory=datetime.utcnow)
