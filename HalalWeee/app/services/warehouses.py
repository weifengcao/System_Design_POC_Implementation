from __future__ import annotations

from typing import Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models, schemas


def create_warehouse(db: Session, payload: schemas.WarehouseCreate) -> models.Warehouse:
    warehouse = models.Warehouse(**payload.model_dump())
    db.add(warehouse)
    db.commit()
    db.refresh(warehouse)
    return warehouse


def list_warehouses(db: Session) -> Sequence[models.Warehouse]:
    stmt = select(models.Warehouse).order_by(models.Warehouse.created_at.desc())
    return db.scalars(stmt).all()


def get_warehouse(db: Session, warehouse_id: int) -> models.Warehouse | None:
    return db.get(models.Warehouse, warehouse_id)


def update_warehouse(
    db: Session, warehouse: models.Warehouse, payload: schemas.WarehouseUpdate
) -> models.Warehouse:
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(warehouse, field, value)
    db.add(warehouse)
    db.commit()
    db.refresh(warehouse)
    return warehouse

