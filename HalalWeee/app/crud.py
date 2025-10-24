from __future__ import annotations

import enum
import json
from datetime import date, datetime
from typing import Iterable, Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from . import models, schemas


# Certification CRUD ----------------------------------------------------------------

def create_certification(db: Session, payload: schemas.CertificationCreate) -> models.Certification:
    cert = models.Certification(**payload.model_dump())
    _sync_cert_status_by_dates(cert)
    db.add(cert)
    db.commit()
    db.refresh(cert)
    return cert


def list_certifications(db: Session, status: models.CertificationStatus | None = None) -> Sequence[models.Certification]:
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
    _sync_cert_status_by_dates(certification)
    db.add(certification)
    db.commit()
    db.refresh(certification)
    return certification


# Product CRUD ----------------------------------------------------------------------

def create_product(db: Session, payload: schemas.ProductCreate) -> models.Product:
    data = payload.model_dump()
    product = models.Product(**data)
    _ensure_supplier_exists(db, product)
    _ensure_certification_constraints(db, product)
    _backfill_trust_badge(product)
    db.add(product)
    db.flush()
    _enqueue_event(
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
    _enqueue_event(
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


# Helpers ----------------------------------------------------------------------------

def _sync_cert_status_by_dates(cert: models.Certification) -> None:
    today = date.today()
    if cert.expires_on and cert.expires_on < today:
        cert.status = models.CertificationStatus.expired
    elif cert.issued_on and cert.status == models.CertificationStatus.pending and cert.issued_on <= today:
        cert.status = models.CertificationStatus.valid


def _ensure_certification_constraints(db: Session, product: models.Product) -> None:
    if not product.certification_required:
        return
    if not product.certification_id:
        raise ValueError("certification_required products must provide certification_id")
    cert = db.get(models.Certification, product.certification_id)
    if cert is None:
        raise ValueError("linked certification not found")
    _sync_cert_status_by_dates(cert)
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


def is_halal_verified(product: models.Product) -> bool:
    if not product.certification_required:
        return False
    return (
        product.certification is not None
        and product.certification.status == models.CertificationStatus.valid
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


# Supplier CRUD ---------------------------------------------------------------------


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


def _ensure_supplier_exists(db: Session, product: models.Product) -> None:
    if product.supplier_id is None:
        raise ValueError("supplier_id is required for products in this slice")
    supplier = db.get(models.Supplier, product.supplier_id)
    if supplier is None:
        raise ValueError("supplier not found")


# Warehouse CRUD --------------------------------------------------------------------


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


# Inventory Lots --------------------------------------------------------------------


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
    _enqueue_event(
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
    _enqueue_event(
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


def _normalize_inventory_lot(lot: models.InventoryLot) -> None:
    if lot.qty_reserved > lot.qty_on_hand:
        raise ValueError("qty_reserved cannot exceed qty_on_hand")
    if lot.best_before and lot.manufactured_on and lot.best_before < lot.manufactured_on:
        raise ValueError("best_before cannot be earlier than manufactured_on")


# Pricing ---------------------------------------------------------------------------


def create_product_price(
    db: Session, product: models.Product, payload: schemas.ProductPriceCreate
) -> models.ProductPrice:
    price = models.ProductPrice(product_id=product.id, **payload.model_dump())
    _validate_unique_price_type(db, price)
    db.add(price)
    db.flush()
    _enqueue_event(
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
    _enqueue_event(
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
    _enqueue_event(
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


def _validate_unique_price_type(db: Session, price: models.ProductPrice) -> None:
    stmt = select(models.ProductPrice).where(
        models.ProductPrice.product_id == price.product_id,
        models.ProductPrice.price_type == price.price_type,
        models.ProductPrice.id != (price.id or 0),
    )
    existing = db.scalars(stmt).first()
    if existing:
        raise ValueError(f"{price.price_type} price already exists for this product")


# Orders ----------------------------------------------------------------------------


def create_order(db: Session, payload: schemas.OrderCreate) -> models.Order:
    order = models.Order(
        customer_email=payload.customer_email,
        delivery_slot=payload.delivery_slot,
        currency=payload.currency,
    )
    db.add(order)
    db.flush()

    total_cents = 0

    for item_payload in payload.items:
        product = db.get(models.Product, item_payload.product_id)
        if product is None:
            raise ValueError(f"product_id {item_payload.product_id} not found")

        price = _select_effective_price(db, product.id, item_payload.price_type)
        unit_price = price.amount_cents

        _reserve_inventory_for_item(db, order, product, item_payload.quantity)

        order_item = models.OrderItem(
            order_id=order.id,
            product_id=product.id,
            quantity=item_payload.quantity,
            unit_price_cents=unit_price,
            price_type=price.price_type,
        )
        db.add(order_item)
        total_cents += unit_price * item_payload.quantity

    order.total_amount_cents = total_cents
    db.add(order)
    db.flush()
    _enqueue_event(
        db,
        event_type="order.created",
        topic="commerce.order",
        payload={
            "order_id": order.id,
            "status": order.status.value,
            "total_amount_cents": order.total_amount_cents,
            "currency": order.currency,
        },
    )
    db.commit()
    db.refresh(order)
    return order


def list_orders(db: Session, status: models.OrderStatus | None = None) -> Sequence[models.Order]:
    stmt = select(models.Order).order_by(models.Order.created_at.desc())
    if status:
        stmt = stmt.where(models.Order.status == status)
    return db.scalars(stmt).unique().all()


def get_order(db: Session, order_id: int) -> models.Order | None:
    return db.get(models.Order, order_id)


def update_order(db: Session, order: models.Order, payload: schemas.OrderUpdate) -> models.Order:
    new_status = payload.status or order.status
    if payload.delivery_slot is not None:
        order.delivery_slot = payload.delivery_slot

    if payload.status and payload.status != order.status:
        _handle_order_status_transition(db, order, payload.status)
        order.status = payload.status
    elif payload.status is None:
        db.add(order)
    _enqueue_event(
        db,
        event_type="order.updated",
        topic="commerce.order",
        payload={
            "order_id": order.id,
            "status": order.status.value,
        },
    )
    db.commit()
    db.refresh(order)
    return order


def _handle_order_status_transition(db: Session, order: models.Order, target_status: models.OrderStatus) -> None:
    if target_status == models.OrderStatus.cancelled:
        _release_reservations(db, order, ReservationOutcome.Release)
    elif target_status == models.OrderStatus.fulfilled:
        _release_reservations(db, order, ReservationOutcome.Consume)
    db.add(order)


class ReservationOutcome(enum.Enum):
    Release = "release"
    Consume = "consume"


def _release_reservations(db: Session, order: models.Order, outcome: "ReservationOutcome") -> None:
    now = datetime.utcnow()
    for reservation in order.reservations:
        if reservation.status != models.ReservationStatus.active:
            continue
        lot = reservation.lot
        if outcome == ReservationOutcome.Release:
            reservation.status = models.ReservationStatus.released
            reservation.released_at = now
            if lot:
                lot.qty_reserved = max(lot.qty_reserved - reservation.reserved_qty, 0)
        elif outcome == ReservationOutcome.Consume:
            reservation.status = models.ReservationStatus.consumed
            reservation.released_at = now
            if lot:
                lot.qty_reserved = max(lot.qty_reserved - reservation.reserved_qty, 0)
                lot.qty_on_hand = max(lot.qty_on_hand - reservation.reserved_qty, 0)
        _enqueue_event(
            db,
            event_type="inventory.reservation.updated",
            topic="inventory.reservation",
            payload={
                "reservation_id": reservation.id,
                "order_id": order.id,
                "status": reservation.status.value,
                "product_id": reservation.product_id,
            },
        )
        else:
            raise ValueError("Unsupported reservation outcome")


def _select_effective_price(db: Session, product_id: int, requested_type: models.PricingType) -> models.ProductPrice:
    today = date.today()

    def _fetch(price_type: models.PricingType) -> models.ProductPrice | None:
        stmt = select(models.ProductPrice).where(
            models.ProductPrice.product_id == product_id,
            models.ProductPrice.price_type == price_type,
        )
        price = db.scalars(stmt).first()
        if not price:
            return None
        if price.starts_on and price.starts_on > today:
            return None
        if price.ends_on and price.ends_on < today:
            return None
        return price

    price = _fetch(requested_type)
    if price:
        return price
    price = _fetch(models.PricingType.regular)
    if price:
        return price
    raise ValueError(f"No active price available for product {product_id}")


def _reserve_inventory_for_item(
    db: Session, order: models.Order, product: models.Product, requested_qty: int
) -> None:
    remaining = requested_qty
    lots = list_inventory_lots_for_product(db, product.id)
    for lot in lots:
        if lot.status != models.InventoryLotStatus.available or lot.telemetry_alert:
            continue
        available = lot.qty_on_hand - lot.qty_reserved
        if available <= 0:
            continue
        take = min(available, remaining)
        if take <= 0:
            continue
        lot.qty_reserved += take
        reservation = models.InventoryReservation(
            order_id=order.id,
            product_id=product.id,
            lot_id=lot.id,
            warehouse_id=lot.warehouse_id,
            reserved_qty=take,
            status=models.ReservationStatus.active,
        )
        db.add(reservation)
        db.flush()
        _enqueue_event(
            db,
            event_type="inventory.reservation.created",
            topic="inventory.reservation",
            payload={
                "reservation_id": reservation.id,
                "order_id": order.id,
                "product_id": product.id,
                "lot_id": lot.id,
                "reserved_qty": take,
            },
        )
        remaining -= take
        if remaining == 0:
            break
    if remaining > 0:
        raise ValueError(
            f"Insufficient inventory to reserve {requested_qty} units for product {product.id}"
        )


# Outbox helpers --------------------------------------------------------------------


def _enqueue_event(
    db: Session,
    event_type: str,
    topic: str,
    payload: dict,
    status: models.OutboxStatus = models.OutboxStatus.pending,
) -> models.OutboxEvent:
    event = models.OutboxEvent(
        event_type=event_type,
        topic=topic,
        payload=json.dumps(payload),
        status=status,
    )
    db.add(event)
    return event


def list_outbox_events(
    db: Session,
    status: models.OutboxStatus | None = models.OutboxStatus.pending,
    limit: int = 100,
) -> Sequence[models.OutboxEvent]:
    stmt = select(models.OutboxEvent).order_by(models.OutboxEvent.created_at.asc()).limit(limit)
    if status:
        stmt = stmt.where(models.OutboxEvent.status == status)
    return db.scalars(stmt).all()


def get_outbox_event(db: Session, event_id: int) -> models.OutboxEvent | None:
    return db.get(models.OutboxEvent, event_id)


def mark_outbox_event(
    db: Session,
    event: models.OutboxEvent,
    status: models.OutboxStatus,
) -> models.OutboxEvent:
    event.status = status
    if status != models.OutboxStatus.pending:
        event.publish_attempts += 1
    db.add(event)
    db.commit()
    db.refresh(event)
    return event
