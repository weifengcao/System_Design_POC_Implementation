from __future__ import annotations

from typing import Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models, schemas


def create_supplier(db: Session, payload: schemas.SupplierCreate) -> models.Supplier:
    supplier = models.Supplier(**payload.model_dump())
    db.add(supplier)
    db.commit()
    db.refresh(supplier)
    return supplier


def list_suppliers(db: Session) -> Sequence[models.Supplier]:
    stmt = select(models.Supplier).order_by(models.Supplier.created_at.desc())
    return db.scalars(stmt).unique().all()


def get_supplier(db: Session, supplier_id: int) -> models.Supplier | None:
    return db.get(models.Supplier, supplier_id)


def update_supplier(
    db: Session, supplier: models.Supplier, payload: schemas.SupplierUpdate
) -> models.Supplier:
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(supplier, field, value)
    db.add(supplier)
    db.commit()
    db.refresh(supplier)
    return supplier


def link_supplier_certification(
    db: Session, supplier: models.Supplier, certification: models.Certification, scope_note: str | None
) -> models.SupplierCertification:
    existing_stmt = select(models.SupplierCertification).where(
        models.SupplierCertification.supplier_id == supplier.id,
        models.SupplierCertification.certification_id == certification.id,
    )
    existing = db.scalars(existing_stmt).first()
    if existing:
        return existing
    link = models.SupplierCertification(
        supplier_id=supplier.id,
        certification_id=certification.id,
        scope_note=scope_note,
    )
    db.add(link)
    db.commit()
    db.refresh(link)
    db.refresh(supplier)
    return link

