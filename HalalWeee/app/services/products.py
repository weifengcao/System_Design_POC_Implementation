from __future__ import annotations

from datetime import date
from typing import Iterable, Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models, schemas
from . import certifications as certification_service
from .events import enqueue_event


def create_product(db: Session, payload: schemas.ProductCreate) -> models.Product:
    product = models.Product(**payload.model_dump())
    _ensure_supplier_exists(db, product)
    _ensure_certification_constraints(db, product)
    _backfill_trust_badge(product)
    db.add(product)
    db.flush()
    enqueue_event(
        db,
        event_type="product.created",
        topic="catalog.product",
        payload={
            "product_id": product.id,
            "sku": product.sku,
            "supplier_id": product.supplier_id,
            "certification_id": product.certification_id,
            "lifecycle_state": product.lifecycle_state.value,
        },
    )
    db.commit()
    db.refresh(product)
    return product


def list_products(
    db: Session,
    *,
    lifecycle_states: Iterable[models.ProductLifecycleState] | None = None,
    certified_only: bool = False,
) -> Sequence[models.Product]:
    stmt = select(models.Product).order_by(models.Product.created_at.desc())
    if lifecycle_states:
        stmt = stmt.where(models.Product.lifecycle_state.in_(tuple(lifecycle_states)))
    if certified_only:
        stmt = stmt.join(models.Product.certification).where(
            models.Product.certification_required.is_(True),
            models.Certification.status == models.CertificationStatus.valid,
        )
    return db.scalars(stmt).all()


def get_product(db: Session, product_id: int) -> models.Product | None:
    return db.get(models.Product, product_id)


def update_product(
    db: Session, product: models.Product, payload: schemas.ProductUpdate
) -> models.Product:
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(product, field, value)
    _ensure_supplier_exists(db, product)
    _ensure_certification_constraints(db, product)
    _backfill_trust_badge(product)
    db.add(product)
    enqueue_event(
        db,
        event_type="product.updated",
        topic="catalog.product",
        payload={
            "product_id": product.id,
            "lifecycle_state": product.lifecycle_state.value,
            "supplier_id": product.supplier_id,
        },
    )
    db.commit()
    db.refresh(product)
    return product


def is_halal_verified(product: models.Product) -> bool:
    if not product.certification_required:
        return False
    return (
        product.certification is not None and product.certification.status == models.CertificationStatus.valid
    )


def product_inventory_summary(product: models.Product) -> schemas.InventorySummary:
    available_qty = 0
    reserved_qty = 0
    next_expiry: date | None = None
    for lot in product.inventory_lots:
        if lot.status != models.InventoryLotStatus.available or lot.telemetry_alert:
            continue
        available = max(lot.qty_on_hand - lot.qty_reserved, 0)
        if available <= 0:
            continue
        available_qty += available
        reserved_qty += lot.qty_reserved
        if lot.best_before:
            if next_expiry is None or lot.best_before < next_expiry:
                next_expiry = lot.best_before
    return schemas.InventorySummary(
        available_quantity=available_qty,
        reserved_quantity=reserved_qty,
        next_expiry_date=next_expiry,
    )


def create_inventory_lot(
    db: Session, product: models.Product, payload: schemas.InventoryLotCreate
) -> models.InventoryLot:
    warehouse = db.get(models.Warehouse, payload.warehouse_id)
    if warehouse is None:
        raise ValueError("warehouse not found")
    lot_data = payload.model_dump()
    lot_data["product_id"] = product.id
    lot = models.InventoryLot(**lot_data)
    _normalize_inventory_lot(lot)
    db.add(lot)
    db.flush()
    enqueue_event(
        db,
        event_type="inventory.lot.created",
        topic="inventory.lot",
        payload={
            "product_id": product.id,
            "lot_id": lot.id,
            "warehouse_id": lot.warehouse_id,
            "qty_on_hand": lot.qty_on_hand,
            "best_before": lot.best_before.isoformat() if lot.best_before else None,
            "status": lot.status.value,
        },
    )
    db.commit()
    db.refresh(lot)
    db.refresh(product)
    return lot


def list_inventory_lots_for_product(db: Session, product_id: int) -> Sequence[models.InventoryLot]:
    stmt = (
        select(models.InventoryLot)
        .where(models.InventoryLot.product_id == product_id)
        .order_by(models.InventoryLot.best_before.asc().nulls_last(), models.InventoryLot.created_at.asc())
    )
    return db.scalars(stmt).unique().all()


def get_inventory_lot(db: Session, lot_id: int) -> models.InventoryLot | None:
    return db.get(models.InventoryLot, lot_id)


def update_inventory_lot(
    db: Session, lot: models.InventoryLot, payload: schemas.InventoryLotUpdate
) -> models.InventoryLot:
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(lot, field, value)
    _normalize_inventory_lot(lot)
    db.add(lot)
    enqueue_event(
        db,
        event_type="inventory.lot.updated",
        topic="inventory.lot",
        payload={
            "lot_id": lot.id,
            "product_id": lot.product_id,
            "qty_on_hand": lot.qty_on_hand,
            "qty_reserved": lot.qty_reserved,
            "status": lot.status.value,
        },
    )
    db.commit()
    db.refresh(lot)
    return lot


def create_product_price(
    db: Session, product: models.Product, payload: schemas.ProductPriceCreate
) -> models.ProductPrice:
    price = models.ProductPrice(product_id=product.id, **payload.model_dump())
    _validate_unique_price_type(db, price)
    db.add(price)
    db.flush()
    enqueue_event(
        db,
        event_type="product.price.created",
        topic="catalog.price",
        payload={
            "product_id": product.id,
            "price_id": price.id,
            "price_type": price.price_type.value,
            "amount_cents": price.amount_cents,
            "currency": price.currency,
        },
    )
    db.commit()
    db.refresh(price)
    db.refresh(product)
    return price


def list_product_prices(db: Session, product_id: int) -> Sequence[models.ProductPrice]:
    stmt = (
        select(models.ProductPrice)
        .where(models.ProductPrice.product_id == product_id)
        .order_by(models.ProductPrice.price_type.asc())
    )
    return db.scalars(stmt).all()


def get_product_price(db: Session, price_id: int) -> models.ProductPrice | None:
    return db.get(models.ProductPrice, price_id)


def update_product_price(
    db: Session, price: models.ProductPrice, payload: schemas.ProductPriceUpdate
) -> models.ProductPrice:
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(price, field, value)
    _validate_unique_price_type(db, price)
    db.add(price)
    enqueue_event(
        db,
        event_type="product.price.updated",
        topic="catalog.price",
        payload={
            "product_id": price.product_id,
            "price_id": price.id,
            "price_type": price.price_type.value,
            "amount_cents": price.amount_cents,
            "currency": price.currency,
        },
    )
    db.commit()
    db.refresh(price)
    return price


def delete_product_price(db: Session, price: models.ProductPrice) -> None:
    db.delete(price)
    enqueue_event(
        db,
        event_type="product.price.deleted",
        topic="catalog.price",
        payload={
            "product_id": price.product_id,
            "price_id": price.id,
            "price_type": price.price_type.value,
        },
    )
    db.commit()


def _ensure_supplier_exists(db: Session, product: models.Product) -> None:
    if product.supplier_id is None:
        raise ValueError("supplier_id is required for products in this slice")
    supplier = db.get(models.Supplier, product.supplier_id)
    if supplier is None:
        raise ValueError("supplier not found")


def _ensure_certification_constraints(db: Session, product: models.Product) -> None:
    if not product.certification_required:
        return
    if not product.certification_id:
        raise ValueError("certification_required products must provide certification_id")
    cert = certification_service.get_certification(db, product.certification_id)
    if cert is None:
        raise ValueError("linked certification not found")
    certification_service.sync_status_by_dates(cert)
    if cert.status != models.CertificationStatus.valid:
        raise ValueError("linked certification is not valid")
    if product.supplier_id:
        supplier = db.get(models.Supplier, product.supplier_id)
        if supplier and cert not in supplier.certifications:
            raise ValueError("supplier is not linked to the provided certification")


def _backfill_trust_badge(product: models.Product) -> None:
    if product.certification and product.certification.status == models.CertificationStatus.valid:
        if not product.halal_trust_badge:
            product.halal_trust_badge = f"{product.certification.certifier} Verified Halal"
    elif not product.certification_required:
        product.halal_trust_badge = product.halal_trust_badge or "Self-attested (Non-food)"


def _normalize_inventory_lot(lot: models.InventoryLot) -> None:
    if lot.qty_reserved > lot.qty_on_hand:
        raise ValueError("qty_reserved cannot exceed qty_on_hand")
    if lot.best_before and lot.manufactured_on and lot.best_before < lot.manufactured_on:
        raise ValueError("best_before cannot be earlier than manufactured_on")


def _validate_unique_price_type(db: Session, price: models.ProductPrice) -> None:
    stmt = select(models.ProductPrice).where(
        models.ProductPrice.product_id == price.product_id,
        models.ProductPrice.price_type == price.price_type,
        models.ProductPrice.id != (price.id or 0),
    )
    existing = db.scalars(stmt).first()
    if existing:
        raise ValueError(f"{price.price_type} price already exists for this product")
