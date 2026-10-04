from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class VersionBody(BaseModel):
    version: int = Field(ge=1)

class CustomerCreate(BaseModel):
    model_config = ConfigDict(extra='forbid')
    company: str = Field(default='', max_length=180)
    first_name: str = Field(default='', max_length=100)
    last_name: str = Field(default='', max_length=100)
    phone: str = Field(default='', max_length=60)
    email: str = Field(default='', max_length=180)
    address1: str = Field(default='', max_length=180)
    address2: str = Field(default='', max_length=180)
    city: str = Field(default='', max_length=100)
    state: str = Field(default='', max_length=60)
    postal_code: str = Field(default='', max_length=30)
    tax_exempt: bool = False
    notes: str = ''

class CustomerUpdate(CustomerCreate):
    version: int = Field(ge=1)
    company: str | None = Field(default=None, max_length=180)
    first_name: str | None = Field(default=None, max_length=100)
    last_name: str | None = Field(default=None, max_length=100)
    phone: str | None = Field(default=None, max_length=60)
    email: str | None = Field(default=None, max_length=180)
    address1: str | None = Field(default=None, max_length=180)
    address2: str | None = Field(default=None, max_length=180)
    city: str | None = Field(default=None, max_length=100)
    state: str | None = Field(default=None, max_length=60)
    postal_code: str | None = Field(default=None, max_length=30)
    tax_exempt: bool | None = None
    notes: str | None = None

class OrderCreate(BaseModel):
    model_config = ConfigDict(extra='forbid')
    customer_id: str
    location_id: str
    order_number: str = ''
    status: str = 'New'
    priority: str = 'Normal'
    received_date: str
    due_date: str = ''
    assigned_to: str = ''
    delivery_method: str = 'Pickup'
    po_number: str = ''
    description: str = ''
    artwork_path: str = ''
    production_notes: str = ''
    customer_notes: str = ''
    tax_rate: Decimal = Decimal(0)
    deposit: Decimal = Decimal(0)
    discount: Decimal = Decimal(0)
    items: list[dict] = Field(default_factory=list)

class OrderUpdate(BaseModel):
    model_config = ConfigDict(extra='forbid')
    version: int = Field(ge=1)
    customer_id: str | None = None
    location_id: str | None = None
    order_number: str | None = None
    status: str | None = None
    priority: str | None = None
    received_date: str | None = None
    due_date: str | None = None
    assigned_to: str | None = None
    delivery_method: str | None = None
    po_number: str | None = None
    description: str | None = None
    artwork_path: str | None = None
    production_notes: str | None = None
    customer_notes: str | None = None
    tax_rate: Decimal | None = None
    deposit: Decimal | None = None
    discount: Decimal | None = None
    items: list[dict] | None = None

    # Backward compatibility for older cached PWA bundles that echoed the full
    # server representation during PATCH. These known server-managed fields are
    # accepted only so validation can proceed, then excluded from model_dump().
    id: str | None = Field(default=None, exclude=True)
    subtotal: Decimal | None = Field(default=None, exclude=True)
    total: Decimal | None = Field(default=None, exclude=True)
    balance: Decimal | None = Field(default=None, exclude=True)
    is_deleted: bool | None = Field(default=None, exclude=True)
    updated_at: str | None = Field(default=None, exclude=True)
    updated_by: str | None = Field(default=None, exclude=True)
