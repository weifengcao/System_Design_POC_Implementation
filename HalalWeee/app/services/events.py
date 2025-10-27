from __future__ import annotations

import json
from typing import Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models


def enqueue_event(
    db: Session,
    *,
    event_type: str,
    topic: str,
    payload: dict,
    status: models.OutboxStatus = models.OutboxStatus.pending,
) -> models.OutboxEvent:
    event = models.OutboxEvent(
        event_type=event_type,
        topic=topic,
        payload=json.dumps(payload),
        status=status,
    )
    db.add(event)
    return event


def list_outbox_events(
    db: Session,
    *,
    status: models.OutboxStatus | None = models.OutboxStatus.pending,
    limit: int = 100,
) -> Sequence[models.OutboxEvent]:
    stmt = select(models.OutboxEvent).order_by(models.OutboxEvent.created_at.asc()).limit(limit)
    if status:
        stmt = stmt.where(models.OutboxEvent.status == status)
    return db.scalars(stmt).all()


def get_outbox_event(db: Session, event_id: int) -> models.OutboxEvent | None:
    return db.get(models.OutboxEvent, event_id)


def mark_outbox_event(
    db: Session,
    event: models.OutboxEvent,
    status: models.OutboxStatus,
) -> models.OutboxEvent:
    event.status = status
    if status != models.OutboxStatus.pending:
        event.publish_attempts += 1
    db.add(event)
    db.commit()
    db.refresh(event)
    return event

