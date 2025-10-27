from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query, status

from .. import models, schemas
from ..services import products as product_service
from .dependencies import DbSession
from .serializers import product as serialize_product

products_router = APIRouter(prefix="/products", tags=["Products"])
inventory_router = APIRouter(prefix="/inventory_lots", tags=["Inventory"])
pricing_router = APIRouter(prefix="/prices", tags=["Pricing"])


@products_router.post("", response_model=schemas.ProductOut, status_code=status.HTTP_201_CREATED)
def create_product(payload: schemas.ProductCreate, db: DbSession):
    try:
        product = product_service.create_product(db, payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return serialize_product(product)


@products_router.get("", response_model=List[schemas.ProductOut])
def list_products(
    db: DbSession,
    lifecycle_state: Optional[List[models.ProductLifecycleState]] = Query(
        None,
        description="Filter by lifecycle states. Repeat the query param for multiple values.",
    ),
    certified_only: bool = Query(
        False, description="Return only products that require and have valid halal certification."
    ),
):
    products = product_service.list_products(
        db,
        lifecycle_states=lifecycle_state,
        certified_only=certified_only,
    )
    return [serialize_product(prod) for prod in products]


@products_router.get("/{product_id}", response_model=schemas.ProductOut)
def get_product(product_id: int, db: DbSession):
    product = product_service.get_product(db, product_id)
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    return serialize_product(product)


@products_router.patch("/{product_id}", response_model=schemas.ProductOut)
def patch_product(product_id: int, payload: schemas.ProductUpdate, db: DbSession):
    product = product_service.get_product(db, product_id)
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    try:
        product = product_service.update_product(db, product, payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return serialize_product(product)


@products_router.get("/{product_id}/inventory_lots", response_model=List[schemas.InventoryLotOut])
def list_product_lots(product_id: int, db: DbSession):
    product = product_service.get_product(db, product_id)
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    lots = product_service.list_inventory_lots_for_product(db, product_id)
    return [schemas.InventoryLotOut.model_validate(lot, from_attributes=True) for lot in lots]


@products_router.post(
    "/{product_id}/inventory_lots",
    response_model=schemas.InventoryLotOut,
    status_code=status.HTTP_201_CREATED,
)
def create_inventory_lot(product_id: int, payload: schemas.InventoryLotCreate, db: DbSession):
    product = product_service.get_product(db, product_id)
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    try:
        lot = product_service.create_inventory_lot(db, product, payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return schemas.InventoryLotOut.model_validate(lot, from_attributes=True)


@inventory_router.patch("/{lot_id}", response_model=schemas.InventoryLotOut)
def patch_inventory_lot(lot_id: int, payload: schemas.InventoryLotUpdate, db: DbSession):
    lot = product_service.get_inventory_lot(db, lot_id)
    if lot is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Inventory lot not found")
    try:
        lot = product_service.update_inventory_lot(db, lot, payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return schemas.InventoryLotOut.model_validate(lot, from_attributes=True)


@products_router.get("/{product_id}/prices", response_model=List[schemas.ProductPriceOut])
def list_product_prices(product_id: int, db: DbSession):
    product = product_service.get_product(db, product_id)
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    prices = product_service.list_product_prices(db, product_id)
    return [schemas.ProductPriceOut.model_validate(price, from_attributes=True) for price in prices]


@products_router.post(
    "/{product_id}/prices",
    response_model=schemas.ProductPriceOut,
    status_code=status.HTTP_201_CREATED,
)
def create_product_price(product_id: int, payload: schemas.ProductPriceCreate, db: DbSession):
    product = product_service.get_product(db, product_id)
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    try:
        price = product_service.create_product_price(db, product, payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return schemas.ProductPriceOut.model_validate(price, from_attributes=True)


@pricing_router.patch("/{price_id}", response_model=schemas.ProductPriceOut)
def patch_product_price(price_id: int, payload: schemas.ProductPriceUpdate, db: DbSession):
    price = product_service.get_product_price(db, price_id)
    if price is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Price not found")
    try:
        price = product_service.update_product_price(db, price, payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return schemas.ProductPriceOut.model_validate(price, from_attributes=True)


@pricing_router.delete("/{price_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_product_price(price_id: int, db: DbSession):
    price = product_service.get_product_price(db, price_id)
    if price is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Price not found")
    product_service.delete_product_price(db, price)
    return None

