from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

InventoryAdjustmentMode = Literal["add", "remove", "set"]
InventoryReason = Literal["Received", "Used", "Count Correction", "Waste", "Other"]
EquipmentStatus = Literal["Operational", "Needs Attention", "Out of Service", "Retired"]
EquipmentEventType = Literal["Maintenance", "Repair", "Inspection", "Service Call", "Issue Reported", "Other"]


class StrictBody(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class InventoryItemCreate(StrictBody):
    location_id: str = Field(min_length=1, max_length=36)
    catalog_product_id: str | None = Field(default=None, max_length=36)
    name: str = Field(min_length=1, max_length=220)
    sku: str = Field(default="", max_length=100)
    category: str = Field(default="General", min_length=1, max_length=80)
    unit: str = Field(default="each", min_length=1, max_length=40)
    quantity: Decimal = Field(default=Decimal(0), ge=0)
    reorder_point: Decimal = Field(default=Decimal(0), ge=0)
    target_stock: Decimal = Field(default=Decimal(0), ge=0)
    cost_per_unit: Decimal = Field(default=Decimal(0), ge=0)
    vendor: str = Field(default="", max_length=180)
    vendor_sku: str = Field(default="", max_length=120)
    notes: str = Field(default="", max_length=10000)
    active: bool = True

    @model_validator(mode="after")
    def target_not_below_reorder(self):
        if self.target_stock and self.target_stock < self.reorder_point:
            raise ValueError("Target stock cannot be below the reorder point")
        return self


class InventoryItemUpdate(InventoryItemCreate):
    version: int = Field(ge=1)


class InventoryAdjustmentCreate(StrictBody):
    version: int = Field(ge=1)
    mode: InventoryAdjustmentMode
    quantity: Decimal = Field(ge=0)
    reason: InventoryReason
    notes: str = Field(default="", max_length=10000)

    @model_validator(mode="after")
    def nonzero_delta(self):
        if self.mode != "set" and self.quantity == 0:
            raise ValueError("Adjustment quantity must be greater than zero")
        return self


class EquipmentAssetCreate(StrictBody):
    location_id: str = Field(min_length=1, max_length=36)
    name: str = Field(min_length=1, max_length=220)
    category: str = Field(default="Equipment", min_length=1, max_length=80)
    asset_tag: str = Field(default="", max_length=100)
    manufacturer: str = Field(default="", max_length=120)
    model: str = Field(default="", max_length=160)
    serial_number: str = Field(default="", max_length=160)
    status: EquipmentStatus = "Operational"
    purchase_date: date | None = None
    warranty_expiration: date | None = None
    vendor: str = Field(default="", max_length=180)
    service_provider: str = Field(default="", max_length=180)
    next_service_date: date | None = None
    notes: str = Field(default="", max_length=10000)
    active: bool = True


class EquipmentAssetUpdate(EquipmentAssetCreate):
    version: int = Field(ge=1)


class EquipmentIssueReport(StrictBody):
    version: int = Field(ge=1)
    summary: str = Field(min_length=1, max_length=10000)


class EquipmentServiceCreate(StrictBody):
    version: int = Field(ge=1)
    event_date: date
    event_type: EquipmentEventType
    summary: str = Field(min_length=1, max_length=10000)
    provider: str = Field(default="", max_length=180)
    cost: Decimal = Field(default=Decimal(0), ge=0)
    status_after: EquipmentStatus | None = None
    next_service_date: date | None = None
