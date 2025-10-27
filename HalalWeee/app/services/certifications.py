from __future__ import annotations

from datetime import date
from typing import Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models, schemas


def create_certification(db: Session, payload: schemas.CertificationCreate) -> models.Certification:
    certification = models.Certification(**payload.model_dump())
    sync_status_by_dates(certification)
    db.add(certification)
    db.commit()
    db.refresh(certification)
    return certification


def list_certifications(
    db: Session, *, status: models.CertificationStatus | None = None
) -> Sequence[models.Certification]:
    stmt = select(models.Certification)
    if status:
        stmt = stmt.where(models.Certification.status == status)
    stmt = stmt.order_by(models.Certification.created_at.desc())
    return db.scalars(stmt).all()


def get_certification(db: Session, certification_id: int) -> models.Certification | None:
    return db.get(models.Certification, certification_id)


def update_certification(
    db: Session, certification: models.Certification, payload: schemas.CertificationUpdate
) -> models.Certification:
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(certification, field, value)
    sync_status_by_dates(certification)
    db.add(certification)
    db.commit()
    db.refresh(certification)
    return certification


def sync_status_by_dates(cert: models.Certification) -> None:
    today = date.today()
    if cert.expires_on and cert.expires_on < today:
        cert.status = models.CertificationStatus.expired
    elif cert.issued_on and cert.status == models.CertificationStatus.pending and cert.issued_on <= today:
        cert.status = models.CertificationStatus.valid
