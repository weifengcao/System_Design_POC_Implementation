from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class BaseSchema(BaseModel):
    model_config = {"from_attributes": True}


class TenantCreate(BaseSchema):
    name: str
    contact_email: Optional[str] = None


class TenantRead(BaseSchema):
    id: str
    name: str
    contact_email: Optional[str] = None
    created_at: datetime


class OrbCreate(BaseSchema):
    tenant_id: str
    name: str
    orb_type: str
    firmware_version: str


class OrbUpdate(BaseSchema):
    firmware_version: Optional[str] = None
    status: Optional[str] = None


class OrbRead(BaseSchema):
    id: str
    tenant_id: str
    name: str
    orb_type: str
    firmware_version: str
    status: str
    last_seen_at: Optional[datetime]
    battery_pct: Optional[float]
    latitude: Optional[float]
    longitude: Optional[float]
    created_at: datetime
    updated_at: datetime


class TelemetryIn(BaseSchema):
    orb_id: str
    battery_pct: Optional[float] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    speed: Optional[float] = None
    payload: Dict[str, Any] = Field(default_factory=dict)


class TelemetryRead(BaseSchema):
    id: int
    orb_id: str
    battery_pct: Optional[float]
    latitude: Optional[float]
    longitude: Optional[float]
    speed: Optional[float]
    payload: Dict[str, Any]
    created_at: datetime


class CommandCreate(BaseSchema):
    orb_id: str
    command_type: str
    payload: Dict[str, Any] = Field(default_factory=dict)
    expires_in_seconds: Optional[int] = Field(default=300, ge=30, le=86400)


class CommandRead(BaseSchema):
    id: str
    orb_id: str
    command_type: str
    payload: Dict[str, Any]
    status: str
    created_at: datetime
    dispatched_at: Optional[datetime]
    acknowledged_at: Optional[datetime]
    expires_at: Optional[datetime]
    ack_payload: Optional[Dict[str, Any]]
    failure_reason: Optional[str]


class CommandAck(BaseSchema):
    status: str = Field(pattern="^(acknowledged|failed)$")
    payload: Dict[str, Any] = Field(default_factory=dict)


class AlertRead(BaseSchema):
    id: str
    orb_id: str
    level: str
    code: str
    message: str
    details: Dict[str, Any]
    resolved: bool
    created_at: datetime
    resolved_at: Optional[datetime]


class PendingCommandsResponse(BaseSchema):
    orb_id: str
    commands: List[CommandRead]


class HealthResponse(BaseSchema):
    status: str
    service_time: datetime
