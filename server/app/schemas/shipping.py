from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

ShippingCaseType = Literal[
    "GSR",
    "Late Delivery",
    "Lost Package",
    "Damage Claim",
    "Shipping Claim",
    "Address Correction",
    "Other",
]
ShippingStatus = Literal[
    "Open",
    "Submitted",
    "Awaiting Carrier",
    "Awaiting Customer",
    "Approved",
    "Denied",
    "Refunded",
    "Resolved",
]


class StrictBody(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class ShippingCaseCreate(StrictBody):
    location_id: str = Field(min_length=1, max_length=36)
    customer_id: str = Field(min_length=1, max_length=36)
    customer_issue_id: str | None = Field(default=None, max_length=36)
    tracking_number: str = Field(min_length=1, max_length=120)
    carrier: str = Field(default="UPS", min_length=1, max_length=60)
    service_level: str = Field(default="", max_length=120)
    case_type: ShippingCaseType = "Late Delivery"
    status: ShippingStatus = "Open"
    ship_date: date | None = None
    promised_date: date | None = None
    delivered_date: date | None = None
    carrier_reference: str = Field(default="", max_length=160)
    amount_requested: Decimal = Field(default=Decimal(0), ge=0)
    amount_approved: Decimal = Field(default=Decimal(0), ge=0)
    next_action: str = Field(default="", max_length=2000)
    follow_up_date: date | None = None
    notes: str = Field(default="", max_length=10000)

    @model_validator(mode="after")
    def validate_dates_and_amounts(self):
        if self.delivered_date and self.ship_date and self.delivered_date < self.ship_date:
            raise ValueError("Delivered date cannot be before ship date")
        if self.amount_approved > self.amount_requested and self.amount_requested > 0:
            raise ValueError("Approved amount cannot exceed the requested amount")
        return self


class ShippingCaseUpdate(ShippingCaseCreate):
    version: int = Field(ge=1)
