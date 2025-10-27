from __future__ import annotations

import json

from .. import models, schemas
from ..services import products as product_service


def product(product: models.Product) -> schemas.ProductOut:
    base = schemas.ProductOut.model_validate(product, from_attributes=True)
    inventory_summary = product_service.product_inventory_summary(product)
    pricing = [schemas.ProductPriceOut.model_validate(price, from_attributes=True) for price in product.prices]
    return base.model_copy(
        update={
            "is_halal_verified": product_service.is_halal_verified(product),
            "inventory_summary": inventory_summary,
            "pricing": pricing,
        }
    )


def order(order: models.Order) -> schemas.OrderOut:
    order_schema = schemas.OrderOut.model_validate(order, from_attributes=True)
    items = []
    for item in order.items:
        item_schema = schemas.OrderItemOut.model_validate(item, from_attributes=True)
        product_obj = item.product
        items.append(
            item_schema.model_copy(
                update={
                    "product_name": product_obj.name if product_obj else None,
                    "sku": product_obj.sku if product_obj else None,
                }
            )
        )
    reservations = [
        schemas.ReservationOut.model_validate(reservation, from_attributes=True) for reservation in order.reservations
    ]
    return order_schema.model_copy(update={"items": items, "reservations": reservations})


def outbox_event(event: models.OutboxEvent) -> schemas.OutboxEventOut:
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

