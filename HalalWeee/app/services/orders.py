from __future__ import annotations

import enum
from datetime import date, datetime
from typing import Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models, schemas
from .events import enqueue_event
from .products import list_inventory_lots_for_product


class ReservationOutcome(enum.Enum):
    release = "release"
    consume = "consume"


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
    enqueue_event(
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


def list_orders(db: Session, *, status: models.OrderStatus | None = None) -> Sequence[models.Order]:
    stmt = select(models.Order).order_by(models.Order.created_at.desc())
    if status:
        stmt = stmt.where(models.Order.status == status)
    return db.scalars(stmt).unique().all()


def get_order(db: Session, order_id: int) -> models.Order | None:
    return db.get(models.Order, order_id)


def update_order(db: Session, order: models.Order, payload: schemas.OrderUpdate) -> models.Order:
    if payload.delivery_slot is not None:
        order.delivery_slot = payload.delivery_slot

    if payload.status and payload.status != order.status:
        _handle_order_status_transition(db, order, payload.status)
        order.status = payload.status
    else:
        db.add(order)

    enqueue_event(
        db,
        event_type="order.updated",
        topic="commerce.order",
        payload={
            "order_id": order.id,
            "status": order.status.value,
            "total_amount_cents": order.total_amount_cents,
        },
    )
    db.commit()
    db.refresh(order)
    return order


def _handle_order_status_transition(db: Session, order: models.Order, new_status: models.OrderStatus) -> None:
    if new_status == models.OrderStatus.cancelled:
        _release_reservations(db, order, ReservationOutcome.release)
    elif new_status == models.OrderStatus.completed:
        _release_reservations(db, order, ReservationOutcome.consume)
    db.add(order)


def _select_effective_price(
    db: Session, product_id: int, requested_type: models.PricingType
) -> models.ProductPrice:
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
        enqueue_event(
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


def _release_reservations(db: Session, order: models.Order, outcome: ReservationOutcome) -> None:
    now = datetime.utcnow()
    for reservation in order.reservations:
        if reservation.status != models.ReservationStatus.active:
            continue
        lot = reservation.lot
        if outcome == ReservationOutcome.release:
            reservation.status = models.ReservationStatus.released
            reservation.released_at = now
            if lot:
                lot.qty_reserved = max(lot.qty_reserved - reservation.reserved_qty, 0)
        elif outcome == ReservationOutcome.consume:
            reservation.status = models.ReservationStatus.consumed
            reservation.released_at = now
            if lot:
                lot.qty_reserved = max(lot.qty_reserved - reservation.reserved_qty, 0)
                lot.qty_on_hand = max(lot.qty_on_hand - reservation.reserved_qty, 0)
        else:
            raise ValueError("Unsupported reservation outcome")

        enqueue_event(
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

