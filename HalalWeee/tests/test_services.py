from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy.orm import Session

from app import models, schemas
from app.services import certifications, events, orders, products, suppliers, warehouses


def _create_supplier(db: Session) -> models.Supplier:
    payload = schemas.SupplierCreate(
        name="Barakah Farms",
        onboarding_status="approved",
        contact_email="ops@barakahfarms.example",
        contact_phone="+1-555-0101",
        address="123 Crescent Way, Chicago, IL",
    )
    return suppliers.create_supplier(db, payload)


def _create_certification(db: Session, supplier: models.Supplier) -> models.Certification:
    today = date.today()
    payload = schemas.CertificationCreate(
        certifier="IFANCA",
        certificate_number="IF-2024-001",
        scope="Meat Processing",
        issued_on=today - timedelta(days=30),
        expires_on=today + timedelta(days=365),
        status="valid",
        document_url="https://example.com/certs/ifanca-2024-001.pdf",
        audit_notes="Approved after facility walkthrough.",
    )
    certification = certifications.create_certification(db, payload)
    suppliers.link_supplier_certification(db, supplier, certification, scope_note="primary facility")
    return certification


def _create_product(db: Session) -> models.Product:
    supplier = _create_supplier(db)
    certification = _create_certification(db, supplier)
    payload = schemas.ProductCreate(
        sku="HALAL-CHIC-001",
        name="Halal Free-Range Chicken (Whole)",
        description="Air chilled, hand slaughtered halal chicken.",
        primary_category="Meat & Poultry",
        lifecycle_state="active",
        certification_id=certification.id,
        certification_required=True,
        country_of_origin="USA",
        supplier_id=supplier.id,
    )
    return products.create_product(db, payload)


def test_product_creation_sets_trust_badge(db_session: Session) -> None:
    product = _create_product(db_session)
    assert product.halal_trust_badge is not None
    assert "Verified Halal" in product.halal_trust_badge


def test_inventory_reservation_and_order_creation(db_session: Session) -> None:
    product = _create_product(db_session)

    warehouse_payload = schemas.WarehouseCreate(
        name="Chicago Darkstore",
        region="US-IL",
        address="2200 S Halal Ave, Chicago, IL",
        temp_capabilities="ambient,chilled,frozen",
    )
    warehouse = warehouses.create_warehouse(db_session, warehouse_payload)

    lot_payload = schemas.InventoryLotCreate(
        warehouse_id=warehouse.id,
        lot_number="LOT-CHIC-APR24",
        qty_on_hand=120,
        qty_reserved=0,
        temp_band="chilled",
        manufactured_on=date.today() - timedelta(days=2),
        best_before=date.today() + timedelta(days=5),
        status="available",
        telemetry_alert=False,
    )
    products.create_inventory_lot(db_session, product, lot_payload)

    price_payload = schemas.ProductPriceCreate(
        currency="USD",
        amount_cents=1499,
        price_type="regular",
    )
    products.create_product_price(db_session, product, price_payload)

    order_payload = schemas.OrderCreate(
        customer_email="sara@example.com",
        delivery_slot="2024-04-20T18:00-19:00",
        currency="USD",
        items=[
            schemas.OrderItemCreate(
                product_id=product.id,
                quantity=2,
                price_type="regular",
            )
        ],
    )

    order = orders.create_order(db_session, order_payload)
    assert order.total_amount_cents == 2 * 1499
    assert len(order.reservations) == 1
    reservation = order.reservations[0]
    assert reservation.reserved_qty == 2

    lot = products.get_inventory_lot(db_session, reservation.lot_id)
    assert lot.qty_reserved == 2


def test_ack_outbox_event_updates_status(db_session: Session) -> None:
    event = events.enqueue_event(
        db_session,
        event_type="test.event",
        topic="test.topic",
        payload={"example": True},
    )
    db_session.commit()

    fetched = events.get_outbox_event(db_session, event.id)
    assert fetched is not None
    assert fetched.status == models.OutboxStatus.pending

    updated = events.mark_outbox_event(db_session, fetched, models.OutboxStatus.published)
    assert updated.status == models.OutboxStatus.published
    assert updated.publish_attempts == 1

