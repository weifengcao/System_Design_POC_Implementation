from __future__ import annotations

import enum
from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


class CertificationStatus(str, enum.Enum):
    valid = "valid"
    pending = "pending"
    revoked = "revoked"
    expired = "expired"


class ProductLifecycleState(str, enum.Enum):
    draft = "draft"
    active = "active"
    inactive = "inactive"
    blocked = "blocked"


class SupplierOnboardingStatus(str, enum.Enum):
    pending = "pending"
    approved = "approved"
    suspended = "suspended"


class TemperatureBand(str, enum.Enum):
    frozen = "frozen"
    chilled = "chilled"
    ambient = "ambient"


class InventoryLotStatus(str, enum.Enum):
    available = "available"
    hold = "hold"
    quarantine = "quarantine"
    depleted = "depleted"


class Certification(Base):
    __tablename__ = "certifications"
    __table_args__ = (
        UniqueConstraint("certificate_number", "certifier", name="uq_certificate_identity"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    certifier: Mapped[str] = mapped_column(String(255), nullable=False)
    certificate_number: Mapped[str | None] = mapped_column(String(255))
    scope: Mapped[str | None] = mapped_column(String(255))
    issued_on: Mapped[date | None] = mapped_column(Date)
    expires_on: Mapped[date | None] = mapped_column(Date)
    status: Mapped[CertificationStatus] = mapped_column(
        Enum(CertificationStatus), default=CertificationStatus.pending, nullable=False
    )
    document_url: Mapped[str | None] = mapped_column(String(512))
    audit_notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    products: Mapped[list["Product"]] = relationship(
        "Product", back_populates="certification"
    )
    suppliers: Mapped[list["Supplier"]] = relationship(
        "Supplier",
        secondary="supplier_certifications",
        back_populates="certifications",
    )


class SupplierCertification(Base):
    __tablename__ = "supplier_certifications"
    __table_args__ = (
        UniqueConstraint(
            "supplier_id",
            "certification_id",
            name="uq_supplier_certification",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    supplier_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("suppliers.id", ondelete="CASCADE"), nullable=False
    )
    certification_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("certifications.id", ondelete="CASCADE"), nullable=False
    )
    linked_on: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    scope_note: Mapped[str | None] = mapped_column(String(255))


class Product(Base):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    sku: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    primary_category: Mapped[str | None] = mapped_column(String(128))
    supplier_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("suppliers.id", ondelete="RESTRICT"), index=True
    )
    lifecycle_state: Mapped[ProductLifecycleState] = mapped_column(
        Enum(ProductLifecycleState), default=ProductLifecycleState.draft, nullable=False
    )
    certification_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("certifications.id", ondelete="RESTRICT"), index=True
    )
    certification_required: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    halal_trust_badge: Mapped[str | None] = mapped_column(String(255))
    country_of_origin: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    certification: Mapped[Certification | None] = relationship("Certification", back_populates="products")
    supplier: Mapped["Supplier" | None] = relationship("Supplier", back_populates="products")
    inventory_lots: Mapped[list["InventoryLot"]] = relationship(
        "InventoryLot", back_populates="product", cascade="all, delete-orphan"
    )
    prices: Mapped[list["ProductPrice"]] = relationship(
        "ProductPrice", back_populates="product", cascade="all, delete-orphan"
    )
    order_items: Mapped[list["OrderItem"]] = relationship("OrderItem", back_populates="product")


class Supplier(Base):
    __tablename__ = "suppliers"
    __table_args__ = (
        UniqueConstraint("name", name="uq_suppliers_name"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    onboarding_status: Mapped[SupplierOnboardingStatus] = mapped_column(
        Enum(SupplierOnboardingStatus), default=SupplierOnboardingStatus.pending, nullable=False
    )
    contact_email: Mapped[str | None] = mapped_column(String(255))
    contact_phone: Mapped[str | None] = mapped_column(String(32))
    address: Mapped[str | None] = mapped_column(Text)
    compliance_notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    certifications: Mapped[list[Certification]] = relationship(
        "Certification",
        secondary="supplier_certifications",
        back_populates="suppliers",
    )
    products: Mapped[list[Product]] = relationship("Product", back_populates="supplier")


class Warehouse(Base):
    __tablename__ = "warehouses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    region: Mapped[str | None] = mapped_column(String(64))
    address: Mapped[str | None] = mapped_column(Text)
    temp_capabilities: Mapped[str | None] = mapped_column(
        String(128), doc="Comma separated bands supported, e.g. frozen,chilled"
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    inventory_lots: Mapped[list["InventoryLot"]] = relationship("InventoryLot", back_populates="warehouse")
    reservation_records: Mapped[list["InventoryReservation"]] = relationship(
        "InventoryReservation", back_populates="warehouse"
    )


class InventoryLot(Base):
    __tablename__ = "inventory_lots"
    __table_args__ = (
        UniqueConstraint("product_id", "lot_number", name="uq_product_lot"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    product_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("products.id", ondelete="CASCADE"), nullable=False, index=True
    )
    warehouse_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("warehouses.id", ondelete="CASCADE"), nullable=False, index=True
    )
    lot_number: Mapped[str] = mapped_column(String(128), nullable=False)
    qty_on_hand: Mapped[int] = mapped_column(Integer, nullable=False)
    qty_reserved: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    temp_band: Mapped[TemperatureBand] = mapped_column(Enum(TemperatureBand), nullable=False)
    manufactured_on: Mapped[date | None] = mapped_column(Date)
    best_before: Mapped[date | None] = mapped_column(Date)
    status: Mapped[InventoryLotStatus] = mapped_column(
        Enum(InventoryLotStatus), default=InventoryLotStatus.available, nullable=False
    )
    telemetry_alert: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    product: Mapped[Product] = relationship("Product", back_populates="inventory_lots")
    warehouse: Mapped[Warehouse] = relationship("Warehouse", back_populates="inventory_lots")
    reservations: Mapped[list["InventoryReservation"]] = relationship(
        "InventoryReservation", back_populates="lot", cascade="all, delete-orphan"
    )


class PricingType(str, enum.Enum):
    regular = "regular"
    promotional = "promotional"
    subscription = "subscription"


class ProductPrice(Base):
    __tablename__ = "product_prices"
    __table_args__ = (
        UniqueConstraint("product_id", "price_type", name="uq_product_price_type"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    product_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("products.id", ondelete="CASCADE"), nullable=False, index=True
    )
    currency: Mapped[str] = mapped_column(String(8), nullable=False)
    amount_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    price_type: Mapped[PricingType] = mapped_column(Enum(PricingType), default=PricingType.regular, nullable=False)
    starts_on: Mapped[date | None] = mapped_column(Date)
    ends_on: Mapped[date | None] = mapped_column(Date)
    min_qty: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    product: Mapped[Product] = relationship("Product", back_populates="prices")


class OrderStatus(str, enum.Enum):
    created = "created"
    confirmed = "confirmed"
    cancelled = "cancelled"
    fulfilled = "fulfilled"


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    external_ref: Mapped[str | None] = mapped_column(String(64), unique=True)
    status: Mapped[OrderStatus] = mapped_column(Enum(OrderStatus), default=OrderStatus.created, nullable=False)
    customer_email: Mapped[str | None] = mapped_column(String(255))
    delivery_slot: Mapped[str | None] = mapped_column(String(64))
    total_amount_cents: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    currency: Mapped[str] = mapped_column(String(8), default="USD", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    items: Mapped[list["OrderItem"]] = relationship(
        "OrderItem", back_populates="order", cascade="all, delete-orphan"
    )
    reservations: Mapped[list["InventoryReservation"]] = relationship(
        "InventoryReservation", back_populates="order", cascade="all, delete-orphan"
    )


class OrderItem(Base):
    __tablename__ = "order_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    order_id: Mapped[int] = mapped_column(Integer, ForeignKey("orders.id", ondelete="CASCADE"), nullable=False)
    product_id: Mapped[int] = mapped_column(Integer, ForeignKey("products.id", ondelete="RESTRICT"), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_price_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    price_type: Mapped[PricingType] = mapped_column(Enum(PricingType), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    order: Mapped[Order] = relationship("Order", back_populates="items")
    product: Mapped[Product] = relationship("Product", back_populates="order_items")


class ReservationStatus(str, enum.Enum):
    active = "active"
    released = "released"
    consumed = "consumed"


class InventoryReservation(Base):
    __tablename__ = "inventory_reservations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    order_id: Mapped[int] = mapped_column(Integer, ForeignKey("orders.id", ondelete="CASCADE"), nullable=False)
    product_id: Mapped[int] = mapped_column(Integer, ForeignKey("products.id", ondelete="CASCADE"), nullable=False)
    lot_id: Mapped[int] = mapped_column(Integer, ForeignKey("inventory_lots.id", ondelete="SET NULL"))
    warehouse_id: Mapped[int] = mapped_column(Integer, ForeignKey("warehouses.id", ondelete="SET NULL"))
    reserved_qty: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[ReservationStatus] = mapped_column(
        Enum(ReservationStatus), default=ReservationStatus.active, nullable=False
    )
    reserved_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    released_at: Mapped[datetime | None] = mapped_column(DateTime)

    order: Mapped[Order] = relationship("Order", back_populates="reservations")
    lot: Mapped["InventoryLot" | None] = relationship("InventoryLot", back_populates="reservations")
    warehouse: Mapped["Warehouse" | None] = relationship("Warehouse", back_populates="reservation_records")


class OutboxStatus(str, enum.Enum):
    pending = "pending"
    published = "published"
    failed = "failed"


class OutboxEvent(Base):
    __tablename__ = "outbox_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    event_type: Mapped[str] = mapped_column(String(128), nullable=False)
    topic: Mapped[str] = mapped_column(String(128), nullable=False)
    payload: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[OutboxStatus] = mapped_column(
        Enum(OutboxStatus), default=OutboxStatus.pending, nullable=False
    )
    publish_attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    available_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )
