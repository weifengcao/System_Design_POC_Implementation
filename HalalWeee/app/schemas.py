from __future__ import annotations

from datetime import date, datetime
from typing import Optional, Sequence

from pydantic import BaseModel, Field, field_validator, model_validator

from .models import (
    CertificationStatus,
    PricingType,
    ProductLifecycleState,
    TemperatureBand,
    InventoryLotStatus,
    SupplierOnboardingStatus,
    OrderStatus,
    ReservationStatus,
    OutboxStatus,
)


class CertificationBase(BaseModel):
    certifier: str = Field(..., max_length=255)
    certificate_number: Optional[str] = Field(None, max_length=255)
    scope: Optional[str] = Field(None, max_length=255)
    issued_on: Optional[date]
    expires_on: Optional[date]
    status: CertificationStatus = CertificationStatus.pending
    document_url: Optional[str] = Field(None, max_length=512)
    audit_notes: Optional[str]

    @field_validator("expires_on")
    @classmethod
    def validate_chronology(cls, expires_on: Optional[date], values: dict) -> Optional[date]:
        issued_on = values.get("issued_on")
        if expires_on and issued_on and expires_on < issued_on:
            raise ValueError("expires_on cannot be earlier than issued_on")
        return expires_on


class CertificationCreate(CertificationBase):
    pass


class CertificationUpdate(BaseModel):
    certifier: Optional[str] = Field(None, max_length=255)
    certificate_number: Optional[str] = Field(None, max_length=255)
    scope: Optional[str] = Field(None, max_length=255)
    issued_on: Optional[date]
    expires_on: Optional[date]
    status: Optional[CertificationStatus]
    document_url: Optional[str] = Field(None, max_length=512)
    audit_notes: Optional[str]

    @field_validator("expires_on")
    @classmethod
    def validate_chronology(cls, expires_on: Optional[date], values: dict) -> Optional[date]:
        issued_on = values.get("issued_on")
        if expires_on and issued_on and expires_on < issued_on:
            raise ValueError("expires_on cannot be earlier than issued_on")
        return expires_on


class CertificationOut(CertificationBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ProductBase(BaseModel):
    sku: str = Field(..., max_length=64)
    name: str = Field(..., max_length=255)
    description: Optional[str]
    primary_category: Optional[str] = Field(None, max_length=128)
    supplier_id: int
    lifecycle_state: ProductLifecycleState = ProductLifecycleState.draft
    certification_id: Optional[int]
    certification_required: bool = True
    halal_trust_badge: Optional[str] = Field(None, max_length=255)
    country_of_origin: Optional[str] = Field(None, max_length=64)


class ProductCreate(ProductBase):
    pass


class ProductUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=255)
    description: Optional[str]
    primary_category: Optional[str] = Field(None, max_length=128)
    supplier_id: Optional[int]
    lifecycle_state: Optional[ProductLifecycleState]
    certification_id: Optional[int]
    certification_required: Optional[bool]
    halal_trust_badge: Optional[str] = Field(None, max_length=255)
    country_of_origin: Optional[str] = Field(None, max_length=64)


class ProductOut(ProductBase):
    id: int
    created_at: datetime
    updated_at: datetime
    certification: Optional[CertificationOut]
    supplier: Optional["SupplierOut"]
    is_halal_verified: bool = Field(
        False, description="True if product requires certification and linked certificate is valid."
    )
    inventory_summary: "InventorySummary" = Field(
        default_factory=lambda: InventorySummary(), description="Aggregated inventory snapshot."
    )
    pricing: list["ProductPriceOut"] = Field(default_factory=list)

    class Config:
        from_attributes = True


class SupplierBase(BaseModel):
    name: str = Field(..., max_length=255)
    onboarding_status: SupplierOnboardingStatus = SupplierOnboardingStatus.pending
    contact_email: Optional[str] = Field(None, max_length=255)
    contact_phone: Optional[str] = Field(None, max_length=32)
    address: Optional[str]
    compliance_notes: Optional[str]


class SupplierCreate(SupplierBase):
    pass


class SupplierUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=255)
    onboarding_status: Optional[SupplierOnboardingStatus]
    contact_email: Optional[str] = Field(None, max_length=255)
    contact_phone: Optional[str] = Field(None, max_length=32)
    address: Optional[str]
    compliance_notes: Optional[str]


class SupplierOut(SupplierBase):
    id: int
    created_at: datetime
    updated_at: datetime
    certifications: list[CertificationOut] = Field(default_factory=list)

    class Config:
        from_attributes = True


class SupplierCertificationLinkRequest(BaseModel):
    certification_id: int
    scope_note: Optional[str] = Field(None, max_length=255)


class WarehouseBase(BaseModel):
    name: str = Field(..., max_length=255)
    region: Optional[str] = Field(None, max_length=64)
    address: Optional[str]
    temp_capabilities: Optional[str] = Field(
        None, description="Comma-separated temperature bands supported (ambient,chilled,frozen)"
    )


class WarehouseCreate(WarehouseBase):
    pass


class WarehouseUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=255)
    region: Optional[str] = Field(None, max_length=64)
    address: Optional[str]
    temp_capabilities: Optional[str]


class WarehouseOut(WarehouseBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class InventoryLotBase(BaseModel):
    lot_number: str = Field(..., max_length=128)
    qty_on_hand: int = Field(..., ge=0)
    qty_reserved: int = Field(0, ge=0)
    temp_band: TemperatureBand
    manufactured_on: Optional[date]
    best_before: Optional[date]
    status: InventoryLotStatus = InventoryLotStatus.available
    telemetry_alert: bool = False

    @model_validator(mode="after")
    def validate_quantities(cls, values: "InventoryLotBase") -> "InventoryLotBase":
        if values.qty_reserved > values.qty_on_hand:
            raise ValueError("qty_reserved cannot exceed qty_on_hand")
        if values.best_before and values.manufactured_on and values.best_before < values.manufactured_on:
            raise ValueError("best_before cannot be earlier than manufactured_on")
        return values


class InventoryLotCreate(InventoryLotBase):
    warehouse_id: int


class InventoryLotUpdate(BaseModel):
    qty_on_hand: Optional[int] = Field(None, ge=0)
    qty_reserved: Optional[int] = Field(None, ge=0)
    temp_band: Optional[TemperatureBand]
    manufactured_on: Optional[date]
    best_before: Optional[date]
    status: Optional[InventoryLotStatus]
    telemetry_alert: Optional[bool]

    @model_validator(mode="after")
    def validate_quantities(cls, values: "InventoryLotUpdate") -> "InventoryLotUpdate":
        qty_on_hand = values.qty_on_hand
        qty_reserved = values.qty_reserved
        if qty_on_hand is not None and qty_reserved is not None and qty_reserved > qty_on_hand:
            raise ValueError("qty_reserved cannot exceed qty_on_hand")
        if values.best_before and values.manufactured_on and values.best_before < values.manufactured_on:
            raise ValueError("best_before cannot be earlier than manufactured_on")
        return values


class InventoryLotOut(InventoryLotBase):
    id: int
    product_id: int
    warehouse: WarehouseOut
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class InventorySummary(BaseModel):
    available_quantity: int = 0
    reserved_quantity: int = 0
    next_expiry_date: Optional[date] = None


class ProductPriceBase(BaseModel):
    currency: str = Field(..., max_length=8)
    amount_cents: int = Field(..., ge=0)
    price_type: PricingType = PricingType.regular
    starts_on: Optional[date]
    ends_on: Optional[date]
    min_qty: Optional[int] = Field(None, ge=1)

    @model_validator(mode="after")
    def validate_dates(cls, values: "ProductPriceBase") -> "ProductPriceBase":
        if values.starts_on and values.ends_on and values.ends_on < values.starts_on:
            raise ValueError("ends_on cannot be earlier than starts_on")
        return values


class ProductPriceCreate(ProductPriceBase):
    pass


class ProductPriceUpdate(BaseModel):
    currency: Optional[str] = Field(None, max_length=8)
    amount_cents: Optional[int] = Field(None, ge=0)
    price_type: Optional[PricingType]
    starts_on: Optional[date]
    ends_on: Optional[date]
    min_qty: Optional[int] = Field(None, ge=1)

    @model_validator(mode="after")
    def validate_dates(cls, values: "ProductPriceUpdate") -> "ProductPriceUpdate":
        if values.starts_on and values.ends_on and values.ends_on < values.starts_on:
            raise ValueError("ends_on cannot be earlier than starts_on")
        return values


class ProductPriceOut(ProductPriceBase):
    id: int
    product_id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ReservationOut(BaseModel):
    id: int
    product_id: int
    lot_id: Optional[int]
    warehouse_id: Optional[int]
    reserved_qty: int
    status: ReservationStatus
    reserved_at: datetime
    released_at: Optional[datetime]

    class Config:
        from_attributes = True


class OrderItemBase(BaseModel):
    product_id: int
    quantity: int = Field(..., ge=1)
    price_type: PricingType = PricingType.regular


class OrderItemCreate(OrderItemBase):
    pass


class OrderItemOut(OrderItemBase):
    id: int
    unit_price_cents: int
    created_at: datetime
    product_name: Optional[str] = None
    sku: Optional[str] = None

    class Config:
        from_attributes = True


class OrderBase(BaseModel):
    customer_email: Optional[str] = Field(None, max_length=255)
    delivery_slot: Optional[str] = Field(None, max_length=64)
    currency: str = Field("USD", max_length=8)


class OrderCreate(OrderBase):
    items: Sequence[OrderItemCreate]

    @model_validator(mode="after")
    def validate_items(cls, values: "OrderCreate") -> "OrderCreate":
        if not values.items:
            raise ValueError("Order must contain at least one item")
        return values


class OrderUpdate(BaseModel):
    status: Optional[OrderStatus]
    delivery_slot: Optional[str] = Field(None, max_length=64)


class OrderOut(OrderBase):
    id: int
    status: OrderStatus
    total_amount_cents: int
    created_at: datetime
    updated_at: datetime
    items: list[OrderItemOut]
    reservations: list[ReservationOut]

    class Config:
        from_attributes = True


class OutboxEventOut(BaseModel):
    id: int
    event_type: str
    topic: str
    payload: dict
    status: OutboxStatus
    publish_attempts: int
    available_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime


ProductOut.model_rebuild()
SupplierOut.model_rebuild()
