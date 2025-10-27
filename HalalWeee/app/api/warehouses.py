from __future__ import annotations

from typing import List

from fastapi import APIRouter, HTTPException, status

from .. import schemas
from ..services import warehouses as warehouse_service
from .dependencies import DbSession

router = APIRouter(prefix="/warehouses", tags=["Warehouses"])


@router.post("", response_model=schemas.WarehouseOut, status_code=status.HTTP_201_CREATED)
def create_warehouse(payload: schemas.WarehouseCreate, db: DbSession):
    warehouse = warehouse_service.create_warehouse(db, payload)
    return schemas.WarehouseOut.model_validate(warehouse, from_attributes=True)


@router.get("", response_model=List[schemas.WarehouseOut])
def list_warehouses(db: DbSession):
    warehouses = warehouse_service.list_warehouses(db)
    return [schemas.WarehouseOut.model_validate(warehouse, from_attributes=True) for warehouse in warehouses]


@router.get("/{warehouse_id}", response_model=schemas.WarehouseOut)
def get_warehouse(warehouse_id: int, db: DbSession):
    warehouse = warehouse_service.get_warehouse(db, warehouse_id)
    if warehouse is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Warehouse not found")
    return schemas.WarehouseOut.model_validate(warehouse, from_attributes=True)


@router.patch("/{warehouse_id}", response_model=schemas.WarehouseOut)
def patch_warehouse(warehouse_id: int, payload: schemas.WarehouseUpdate, db: DbSession):
    warehouse = warehouse_service.get_warehouse(db, warehouse_id)
    if warehouse is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Warehouse not found")
    warehouse = warehouse_service.update_warehouse(db, warehouse, payload)
    return schemas.WarehouseOut.model_validate(warehouse, from_attributes=True)

