from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy.orm import Session

from . import crud, database, schemas


def main() -> None:
    database.Base.metadata.create_all(database.engine)
    db: Session = database.SessionLocal()
    try:
        existing_products = crud.list_products(db)
        if existing_products:
            print("Database already seeded; skipping.")
            return

        supplier_payload = schemas.SupplierCreate(
            name="Barakah Farms",
            onboarding_status="approved",
            contact_email="ops@barakahfarms.example",
            contact_phone="+1-555-0101",
            address="123 Crescent Way, Chicago, IL",
        )
        supplier = crud.create_supplier(db, supplier_payload)

        today = date.today()
        cert_payload = schemas.CertificationCreate(
            certifier="IFANCA",
            certificate_number="IF-2024-001",
            scope="Meat Processing",
            issued_on=today - timedelta(days=30),
            expires_on=today + timedelta(days=365),
            status="valid",
            document_url="https://example.com/certs/ifanca-2024-001.pdf",
            audit_notes="Approved after facility walkthrough.",
        )
        cert = crud.create_certification(db, cert_payload)
        crud.link_supplier_certification(
            db,
            supplier,
            cert,
            scope_note="Primary processing facility certificate.",
        )

        warehouse_payload = schemas.WarehouseCreate(
            name="Chicago Darkstore",
            region="US-IL",
            address="2200 S Halal Ave, Chicago, IL",
            temp_capabilities="ambient,chilled,frozen",
        )
        warehouse = crud.create_warehouse(db, warehouse_payload)

        product_payload = schemas.ProductCreate(
            sku="HALAL-CHIC-001",
            name="Halal Free-Range Chicken (Whole)",
            description="Air chilled, hand slaughtered halal chicken.",
            primary_category="Meat & Poultry",
            lifecycle_state="active",
            certification_id=cert.id,
            certification_required=True,
            country_of_origin="USA",
            supplier_id=supplier.id,
        )
        product = crud.create_product(db, product_payload)

        lot_payload = schemas.InventoryLotCreate(
            warehouse_id=warehouse.id,
            lot_number="LOT-CHIC-APR24",
            qty_on_hand=120,
            qty_reserved=10,
            temp_band="chilled",
            manufactured_on=today - timedelta(days=2),
            best_before=today + timedelta(days=5),
            status="available",
            telemetry_alert=False,
        )
        crud.create_inventory_lot(db, product, lot_payload)

        price_payload = schemas.ProductPriceCreate(
            currency="USD",
            amount_cents=1499,
            price_type="regular",
        )
        crud.create_product_price(db, product, price_payload)

        promo_payload = schemas.ProductPriceCreate(
            currency="USD",
            amount_cents=1299,
            price_type="promotional",
            starts_on=today - timedelta(days=1),
            ends_on=today + timedelta(days=3),
        )
        crud.create_product_price(db, product, promo_payload)

        order_payload = schemas.OrderCreate(
            customer_email="sara@example.com",
            delivery_slot="2024-04-20T18:00-19:00",
            currency="USD",
            items=[
                schemas.OrderItemCreate(
                    product_id=product.id,
                    quantity=2,
                    price_type="promotional",
                )
            ],
        )
        crud.create_order(db, order_payload)

        print("Seed data inserted.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
