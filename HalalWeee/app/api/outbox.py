from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query, status

from .. import models, schemas
from ..services import events as event_service
from .dependencies import DbSession
from .serializers import outbox_event as serialize_event

router = APIRouter(prefix="/events/outbox", tags=["Outbox"])


@router.get("", response_model=List[schemas.OutboxEventOut])
def list_outbox_events(
    db: DbSession,
    status_filter: Optional[models.OutboxStatus] = Query(
        models.OutboxStatus.pending, alias="status", description="Filter events by status."
    ),
    limit: int = Query(100, ge=1, le=500),
):
    events = event_service.list_outbox_events(db, status=status_filter, limit=limit)
    return [serialize_event(event) for event in events]


@router.post("/{event_id}/ack", response_model=schemas.OutboxEventOut)
def ack_outbox_event(
    event_id: int,
    db: DbSession,
    status_update: models.OutboxStatus = Query(
        models.OutboxStatus.published,
        description="Status to set for the event (default published).",
    ),
):
    event = event_service.get_outbox_event(db, event_id)
    if event is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")
    event = event_service.mark_outbox_event(db, event, status_update)
    return serialize_event(event)

