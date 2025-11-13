from __future__ import annotations

import asyncio
import contextlib
from datetime import datetime, timedelta
from typing import List, Optional

from fastapi import FastAPI, HTTPException, Query

from . import models, schemas
from .database import InMemoryStore, get_store
from .rules import evaluate_low_battery

app = FastAPI(title="OrbManager Control Plane", version="0.2.0")
store: InMemoryStore = get_store()


async def command_expiration_worker(interval_seconds: int = 5) -> None:
    while True:
        now = datetime.utcnow()
        for command in list(store.commands.values()):
            if (
                command.status in {"pending", "dispatched"}
                and command.expires_at
                and command.expires_at < now
            ):
                command.status = "expired"
                command.failure_reason = "Command expired before acknowledgement"
        await asyncio.sleep(interval_seconds)


@app.on_event("startup")
async def startup_event() -> None:
    app.state.command_task = asyncio.create_task(command_expiration_worker())


@app.on_event("shutdown")
async def shutdown_event() -> None:
    task: Optional[asyncio.Task] = getattr(app.state, "command_task", None)
    if task:
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task


@app.get("/health", response_model=schemas.HealthResponse)
async def health() -> schemas.HealthResponse:
    return schemas.HealthResponse(status="ok", service_time=datetime.utcnow())


@app.post("/tenants", response_model=schemas.TenantRead, status_code=201)
def create_tenant(payload: schemas.TenantCreate):
    if any(t.name == payload.name for t in store.tenants.values()):
        raise HTTPException(status_code=409, detail="Tenant name already exists")
    tenant = models.Tenant(**payload.model_dump())
    store.add_tenant(tenant)
    return tenant


@app.get("/tenants", response_model=List[schemas.TenantRead])
def list_tenants():
    return sorted(store.tenants.values(), key=lambda t: t.created_at)


@app.post("/orbs/register", response_model=schemas.OrbRead, status_code=201)
def register_orb(payload: schemas.OrbCreate):
    tenant = store.tenants.get(payload.tenant_id)
    if tenant is None:
        raise HTTPException(status_code=404, detail="Tenant not found")
    orb = models.Orb(**payload.model_dump(), status="registered")
    store.add_orb(orb)
    return orb


@app.get("/orbs", response_model=List[schemas.OrbRead])
def list_orbs(tenant_id: Optional[str] = Query(default=None)):
    orbs = list(store.orbs.values())
    if tenant_id:
        orbs = [orb for orb in orbs if orb.tenant_id == tenant_id]
    return sorted(orbs, key=lambda o: o.created_at, reverse=True)


@app.get("/orbs/{orb_id}", response_model=schemas.OrbRead)
def get_orb(orb_id: str):
    orb = store.orbs.get(orb_id)
    if orb is None:
        raise HTTPException(status_code=404, detail="Orb not found")
    return orb


@app.post("/telemetry", response_model=schemas.TelemetryRead, status_code=201)
def ingest_telemetry(payload: schemas.TelemetryIn):
    orb = store.orbs.get(payload.orb_id)
    if orb is None:
        raise HTTPException(status_code=404, detail="Orb not found")

    telemetry = models.Telemetry(**payload.model_dump())
    store.add_telemetry(telemetry)

    now = datetime.utcnow()
    orb.last_seen_at = now
    orb.status = "online"
    orb.updated_at = now
    if payload.battery_pct is not None:
        orb.battery_pct = payload.battery_pct
    if payload.latitude is not None:
        orb.latitude = payload.latitude
    if payload.longitude is not None:
        orb.longitude = payload.longitude

    evaluate_low_battery(store, orb)
    return telemetry


@app.get("/telemetry/{orb_id}", response_model=List[schemas.TelemetryRead])
def list_telemetry(
    orb_id: str, limit: int = Query(default=20, le=200)
):
    return store.get_recent_telemetry(orb_id, limit)


@app.post("/commands", response_model=schemas.CommandRead, status_code=201)
def create_command(payload: schemas.CommandCreate):
    orb = store.orbs.get(payload.orb_id)
    if orb is None:
        raise HTTPException(status_code=404, detail="Orb not found")

    expires_at = None
    if payload.expires_in_seconds:
        expires_at = datetime.utcnow() + timedelta(seconds=payload.expires_in_seconds)

    command = models.Command(
        orb_id=payload.orb_id,
        command_type=payload.command_type,
        payload=payload.payload,
        expires_at=expires_at,
    )
    store.add_command(command)
    return command


@app.get(
    "/commands/pending/{orb_id}", response_model=schemas.PendingCommandsResponse
)
def get_pending_commands(orb_id: str):
    pending = store.list_commands(orb_id, status="pending")
    now = datetime.utcnow()
    for command in pending:
        command.status = "dispatched"
        command.dispatched_at = now
    return schemas.PendingCommandsResponse(orb_id=orb_id, commands=pending)


@app.post("/commands/{command_id}/ack", response_model=schemas.CommandRead)
def ack_command(command_id: str, payload: schemas.CommandAck):
    command = store.commands.get(command_id)
    if command is None:
        raise HTTPException(status_code=404, detail="Command not found")

    if command.status in {"acknowledged", "failed"}:
        return command

    now = datetime.utcnow()
    if payload.status == "acknowledged":
        command.status = "acknowledged"
        command.ack_payload = payload.payload
    else:
        command.status = "failed"
        command.failure_reason = payload.payload.get("error") or "Device reported failure"
        command.ack_payload = payload.payload
    command.acknowledged_at = now
    return command


@app.get("/alerts", response_model=List[schemas.AlertRead])
def list_alerts(
    orb_id: Optional[str] = Query(default=None),
    only_open: bool = Query(default=True),
):
    return store.list_alerts(orb_id, only_open)
