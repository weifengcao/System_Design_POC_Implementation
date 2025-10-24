from __future__ import annotations

import json
from typing import Annotated, List, Optional

from fastapi import Depends, FastAPI, HTTPException, Query, status
from sqlalchemy.orm import Session

from . import crud, models, schemas
from .database import Base, engine, get_db

Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="HalalWeee Catalog & Certification API",
    description="Initial slice providing certification and product management with halal safeguards.",
    version="0.1.0",
)

DbDep = Annotated[Session, Depends(get_db)]


def _serialize_product(product: models.Product) -> schemas.ProductOut:
    base = schemas.ProductOut.model_validate(product, from_attributes=True)
    inventory_summary = crud.product_inventory_summary(product)
    pricing = [
        schemas.ProductPriceOut.model_validate(price, from_attributes=True) for price in product.prices
    ]
    return base.model_copy(
        update={
            "is_halal_verified": crud.is_halal_verified(product),
            "inventory_summary": inventory_summary,
            "pricing": pricing,
        }
    )


def _serialize_order(order: models.Order) -> schemas.OrderOut:
    order_schema = schemas.OrderOut.model_validate(order, from_attributes=True)
    items = []
    for item in order.items:
        item_schema = schemas.OrderItemOut.model_validate(item, from_attributes=True)
        product = item.product
        items.append(
            item_schema.model_copy(
                update={
                    "product_name": product.name if product else None,
                    "sku": product.sku if product else None,
                }
            )
        )
    reservations = [
        schemas.ReservationOut.model_validate(reservation, from_attributes=True)
        for reservation in order.reservations
    ]
    return order_schema.model_copy(update={"items": items, "reservations": reservations})


def _serialize_event(event: models.OutboxEvent) -> schemas.OutboxEventOut:
    payload = json.loads(event.payload)
    return schemas.OutboxEventOut(
        id=event.id,
        event_type=event.event_type,
        topic=event.topic,
        payload=payload,
        status=event.status,
        publish_attempts=event.publish_attempts,
        available_at=event.available_at,
        created_at=event.created_at,
        updated_at=event.updated_at,
    )


# Certification endpoints ------------------------------------------------------------


@app.post(
    "/certifications",
    response_model=schemas.CertificationOut,
    status_code=status.HTTP_201_CREATED,
)
def create_certification(payload: schemas.CertificationCreate, db: DbDep):
    try:
        certification = crud.create_certification(db, payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return schemas.CertificationOut.model_validate(certification, from_attributes=True)


@app.get("/certifications", response_model=List[schemas.CertificationOut])
def list_certifications(
    status_filter: Optional[models.CertificationStatus] = Query(
        None, alias="status", description="Filter certifications by status."
    ),
    db: DbDep = Depends(get_db),
):
    certifications = crud.list_certifications(db, status=status_filter)
    return [
        schemas.CertificationOut.model_validate(cert, from_attributes=True) for cert in certifications
    ]


@app.get("/certifications/{certification_id}", response_model=schemas.CertificationOut)
def get_certification(certification_id: int, db: DbDep):
    certification = crud.get_certification(db, certification_id)
    if certification is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Certification not found")
    return schemas.CertificationOut.model_validate(certification, from_attributes=True)


@app.patch("/certifications/{certification_id}", response_model=schemas.CertificationOut)
def patch_certification(certification_id: int, payload: schemas.CertificationUpdate, db: DbDep):
    certification = crud.get_certification(db, certification_id)
    if certification is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Certification not found")
    try:
        certification = crud.update_certification(db, certification, payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return schemas.CertificationOut.model_validate(certification, from_attributes=True)


# Product endpoints -----------------------------------------------------------------


@app.post("/products", response_model=schemas.ProductOut, status_code=status.HTTP_201_CREATED)
def create_product(payload: schemas.ProductCreate, db: DbDep):
    try:
        product = crud.create_product(db, payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return _serialize_product(product)


@app.get("/products", response_model=List[schemas.ProductOut])
def list_products(
    lifecycle_state: Optional[List[models.ProductLifecycleState]] = Query(
        None,
        description="Filter by lifecycle states. Repeat the query param for multiple values.",
    ),
    certified_only: bool = Query(
        False, description="Return only products that require and have valid halal certification."
    ),
    db: DbDep = Depends(get_db),
):
    products = crud.list_products(
        db,
        lifecycle_states=lifecycle_state,
        certified_only=certified_only,
    )
    return [_serialize_product(product) for product in products]


@app.get("/products/{product_id}", response_model=schemas.ProductOut)
def get_product(product_id: int, db: DbDep):
    product = crud.get_product(db, product_id)
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    return _serialize_product(product)


@app.patch("/products/{product_id}", response_model=schemas.ProductOut)
def patch_product(product_id: int, payload: schemas.ProductUpdate, db: DbDep):
    product = crud.get_product(db, product_id)
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    try:
        product = crud.update_product(db, product, payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return _serialize_product(product)


@app.get("/products/{product_id}/inventory_lots", response_model=List[schemas.InventoryLotOut])
def list_product_lots(product_id: int, db: DbDep):
    product = crud.get_product(db, product_id)
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    lots = crud.list_inventory_lots_for_product(db, product_id)
    return [
        schemas.InventoryLotOut.model_validate(lot, from_attributes=True)
        for lot in lots
    ]


@app.post(
    "/products/{product_id}/inventory_lots",
    response_model=schemas.InventoryLotOut,
    status_code=status.HTTP_201_CREATED,
)
def create_inventory_lot(product_id: int, payload: schemas.InventoryLotCreate, db: DbDep):
    product = crud.get_product(db, product_id)
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    try:
        lot = crud.create_inventory_lot(db, product, payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return schemas.InventoryLotOut.model_validate(lot, from_attributes=True)


@app.patch("/inventory_lots/{lot_id}", response_model=schemas.InventoryLotOut)
def patch_inventory_lot(lot_id: int, payload: schemas.InventoryLotUpdate, db: DbDep):
    lot = crud.get_inventory_lot(db, lot_id)
    if lot is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Inventory lot not found")
    try:
        lot = crud.update_inventory_lot(db, lot, payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return schemas.InventoryLotOut.model_validate(lot, from_attributes=True)


@app.get("/products/{product_id}/prices", response_model=List[schemas.ProductPriceOut])
def list_product_prices(product_id: int, db: DbDep):
    product = crud.get_product(db, product_id)
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    prices = crud.list_product_prices(db, product_id)
    return [schemas.ProductPriceOut.model_validate(price, from_attributes=True) for price in prices]


@app.post(
    "/products/{product_id}/prices",
    response_model=schemas.ProductPriceOut,
    status_code=status.HTTP_201_CREATED,
)
def create_product_price(product_id: int, payload: schemas.ProductPriceCreate, db: DbDep):
    product = crud.get_product(db, product_id)
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    try:
        price = crud.create_product_price(db, product, payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return schemas.ProductPriceOut.model_validate(price, from_attributes=True)


@app.patch("/prices/{price_id}", response_model=schemas.ProductPriceOut)
def patch_product_price(price_id: int, payload: schemas.ProductPriceUpdate, db: DbDep):
    price = crud.get_product_price(db, price_id)
    if price is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Price not found")
    try:
        price = crud.update_product_price(db, price, payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return schemas.ProductPriceOut.model_validate(price, from_attributes=True)


@app.delete("/prices/{price_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_product_price(price_id: int, db: DbDep):
    price = crud.get_product_price(db, price_id)
    if price is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Price not found")
    crud.delete_product_price(db, price)
    return None


# Supplier endpoints ----------------------------------------------------------------


@app.post("/suppliers", response_model=schemas.SupplierOut, status_code=status.HTTP_201_CREATED)
def create_supplier(payload: schemas.SupplierCreate, db: DbDep):
    supplier = crud.create_supplier(db, payload)
    return schemas.SupplierOut.model_validate(supplier, from_attributes=True)


@app.get("/suppliers", response_model=List[schemas.SupplierOut])
def list_suppliers(db: DbDep = Depends(get_db)):
    suppliers = crud.list_suppliers(db)
    return [
        schemas.SupplierOut.model_validate(supplier, from_attributes=True) for supplier in suppliers
    ]


@app.get("/suppliers/{supplier_id}", response_model=schemas.SupplierOut)
def get_supplier(supplier_id: int, db: DbDep):
    supplier = crud.get_supplier(db, supplier_id)
    if supplier is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Supplier not found")
    return schemas.SupplierOut.model_validate(supplier, from_attributes=True)


@app.patch("/suppliers/{supplier_id}", response_model=schemas.SupplierOut)
def patch_supplier(supplier_id: int, payload: schemas.SupplierUpdate, db: DbDep):
    supplier = crud.get_supplier(db, supplier_id)
    if supplier is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Supplier not found")
    supplier = crud.update_supplier(db, supplier, payload)
    return schemas.SupplierOut.model_validate(supplier, from_attributes=True)


@app.post(
    "/suppliers/{supplier_id}/certifications",
    response_model=schemas.SupplierOut,
    status_code=status.HTTP_200_OK,
)
def link_certification_to_supplier(
    supplier_id: int, payload: schemas.SupplierCertificationLinkRequest, db: DbDep
):
    supplier = crud.get_supplier(db, supplier_id)
    if supplier is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Supplier not found")
    certification = crud.get_certification(db, payload.certification_id)
    if certification is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Certification not found")
    crud.link_supplier_certification(db, supplier, certification, payload.scope_note)
    db.refresh(supplier)
    return schemas.SupplierOut.model_validate(supplier, from_attributes=True)


# Warehouse endpoints ---------------------------------------------------------------


@app.post("/warehouses", response_model=schemas.WarehouseOut, status_code=status.HTTP_201_CREATED)
def create_warehouse(payload: schemas.WarehouseCreate, db: DbDep):
    warehouse = crud.create_warehouse(db, payload)
    return schemas.WarehouseOut.model_validate(warehouse, from_attributes=True)


@app.get("/warehouses", response_model=List[schemas.WarehouseOut])
def list_warehouses(db: DbDep = Depends(get_db)):
    warehouses = crud.list_warehouses(db)
    return [
        schemas.WarehouseOut.model_validate(warehouse, from_attributes=True)
        for warehouse in warehouses
    ]


@app.get("/warehouses/{warehouse_id}", response_model=schemas.WarehouseOut)
def get_warehouse(warehouse_id: int, db: DbDep):
    warehouse = crud.get_warehouse(db, warehouse_id)
    if warehouse is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Warehouse not found")
    return schemas.WarehouseOut.model_validate(warehouse, from_attributes=True)


@app.patch("/warehouses/{warehouse_id}", response_model=schemas.WarehouseOut)
def patch_warehouse(warehouse_id: int, payload: schemas.WarehouseUpdate, db: DbDep):
    warehouse = crud.get_warehouse(db, warehouse_id)
    if warehouse is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Warehouse not found")
    warehouse = crud.update_warehouse(db, warehouse, payload)
    return schemas.WarehouseOut.model_validate(warehouse, from_attributes=True)


# Order endpoints -------------------------------------------------------------------


@app.post("/orders", response_model=schemas.OrderOut, status_code=status.HTTP_201_CREATED)
def create_order(payload: schemas.OrderCreate, db: DbDep):
    try:
        order = crud.create_order(db, payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return _serialize_order(order)


@app.get("/orders", response_model=List[schemas.OrderOut])
def list_orders(
    status_filter: Optional[models.OrderStatus] = Query(None, alias="status"),
    db: DbDep = Depends(get_db),
):
    orders = crud.list_orders(db, status=status_filter)
    return [_serialize_order(order) for order in orders]


@app.get("/orders/{order_id}", response_model=schemas.OrderOut)
def get_order(order_id: int, db: DbDep):
    order = crud.get_order(db, order_id)
    if order is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
    return _serialize_order(order)


@app.patch("/orders/{order_id}", response_model=schemas.OrderOut)
def patch_order(order_id: int, payload: schemas.OrderUpdate, db: DbDep):
    order = crud.get_order(db, order_id)
    if order is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
    try:
        order = crud.update_order(db, order, payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return _serialize_order(order)


# Outbox event endpoints ------------------------------------------------------------


@app.get("/events/outbox", response_model=List[schemas.OutboxEventOut])
def list_outbox_events(
    status_filter: Optional[models.OutboxStatus] = Query(
        models.OutboxStatus.pending, alias="status", description="Filter events by status."
    ),
    limit: int = Query(100, ge=1, le=500),
    db: DbDep = Depends(get_db),
):
    events = crud.list_outbox_events(db, status=status_filter, limit=limit)
    return [_serialize_event(event) for event in events]


@app.post("/events/outbox/{event_id}/ack", response_model=schemas.OutboxEventOut)
def ack_outbox_event(
    event_id: int,
    status_update: models.OutboxStatus = Query(
        models.OutboxStatus.published,
        description="Status to set for the event (default published).",
    ),
    db: DbDep = Depends(get_db),
):
    event = crud.get_outbox_event(db, event_id)
    if event is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")
    event = crud.mark_outbox_event(db, event, status_update)
    return _serialize_event(event)


@app.get("/", tags=["Health"])
def health() -> dict[str, str]:
    return {"status": "ok"}
