from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query, status

from .. import models, schemas
from ..services import certifications as certification_service
from .dependencies import DbSession

router = APIRouter(prefix="/certifications", tags=["Certifications"])


@router.post("", response_model=schemas.CertificationOut, status_code=status.HTTP_201_CREATED)
def create_certification(payload: schemas.CertificationCreate, db: DbSession):
    try:
        certification = certification_service.create_certification(db, payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return schemas.CertificationOut.model_validate(certification, from_attributes=True)


@router.get("", response_model=List[schemas.CertificationOut])
def list_certifications(
    db: DbSession,
    status_filter: Optional[models.CertificationStatus] = Query(
        None, alias="status", description="Filter certifications by status."
    ),
):
    certifications = certification_service.list_certifications(db, status=status_filter)
    return [schemas.CertificationOut.model_validate(cert, from_attributes=True) for cert in certifications]


@router.get("/{certification_id}", response_model=schemas.CertificationOut)
def get_certification(certification_id: int, db: DbSession):
    certification = certification_service.get_certification(db, certification_id)
    if certification is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Certification not found")
    return schemas.CertificationOut.model_validate(certification, from_attributes=True)


@router.patch("/{certification_id}", response_model=schemas.CertificationOut)
def patch_certification(certification_id: int, payload: schemas.CertificationUpdate, db: DbSession):
    certification = certification_service.get_certification(db, certification_id)
    if certification is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Certification not found")
    try:
        certification = certification_service.update_certification(db, certification, payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return schemas.CertificationOut.model_validate(certification, from_attributes=True)
