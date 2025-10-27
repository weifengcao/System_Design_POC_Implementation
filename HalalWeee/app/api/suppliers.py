from __future__ import annotations

from typing import List

from fastapi import APIRouter, HTTPException, status

from .. import schemas
from ..services import certifications as certification_service
from ..services import suppliers as supplier_service
from .dependencies import DbSession

router = APIRouter(prefix="/suppliers", tags=["Suppliers"])


@router.post("", response_model=schemas.SupplierOut, status_code=status.HTTP_201_CREATED)
def create_supplier(payload: schemas.SupplierCreate, db: DbSession):
    supplier = supplier_service.create_supplier(db, payload)
    return schemas.SupplierOut.model_validate(supplier, from_attributes=True)


@router.get("", response_model=List[schemas.SupplierOut])
def list_suppliers(db: DbSession):
    suppliers = supplier_service.list_suppliers(db)
    return [schemas.SupplierOut.model_validate(supplier, from_attributes=True) for supplier in suppliers]


@router.get("/{supplier_id}", response_model=schemas.SupplierOut)
def get_supplier(supplier_id: int, db: DbSession):
    supplier = supplier_service.get_supplier(db, supplier_id)
    if supplier is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Supplier not found")
    return schemas.SupplierOut.model_validate(supplier, from_attributes=True)


@router.patch("/{supplier_id}", response_model=schemas.SupplierOut)
def patch_supplier(supplier_id: int, payload: schemas.SupplierUpdate, db: DbSession):
    supplier = supplier_service.get_supplier(db, supplier_id)
    if supplier is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Supplier not found")
    supplier = supplier_service.update_supplier(db, supplier, payload)
    return schemas.SupplierOut.model_validate(supplier, from_attributes=True)


@router.post(
    "/{supplier_id}/certifications",
    response_model=schemas.SupplierOut,
    status_code=status.HTTP_200_OK,
)
def link_certification_to_supplier(supplier_id: int, payload: schemas.SupplierCertificationLinkRequest, db: DbSession):
    supplier = supplier_service.get_supplier(db, supplier_id)
    if supplier is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Supplier not found")
    certification = certification_service.get_certification(db, payload.certification_id)
    if certification is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Certification not found")
    supplier_service.link_supplier_certification(db, supplier, certification, payload.scope_note)
    return schemas.SupplierOut.model_validate(supplier, from_attributes=True)

