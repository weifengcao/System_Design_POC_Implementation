from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query

from .. import models, schemas
from ..services import orders as order_service
from .dependencies import DbSession
from .serializers import order as serialize_order

router = APIRouter(prefix="/orders", tags=["Orders"])


@router.post("", response_model=schemas.OrderOut, status_code=status.HTTP_201_CREATED)
def create_order(payload: schemas.OrderCreate, db: DbSession):
    try:
        order = order_service.create_order(db, payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return serialize_order(order)


@router.get("", response_model=List[schemas.OrderOut])
def list_orders(
    db: DbSession,
    status_filter: Optional[models.OrderStatus] = Query(None, alias="status"),
):
    orders = order_service.list_orders(db, status=status_filter)
    return [serialize_order(order) for order in orders]


@router.get("/{order_id}", response_model=schemas.OrderOut)
def get_order(order_id: int, db: DbSession):
    order = order_service.get_order(db, order_id)
    if order is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
    return serialize_order(order)


@router.patch("/{order_id}", response_model=schemas.OrderOut)
def patch_order(order_id: int, payload: schemas.OrderUpdate, db: DbSession):
    order = order_service.get_order(db, order_id)
    if order is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
    try:
        order = order_service.update_order(db, order, payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return serialize_order(order)
