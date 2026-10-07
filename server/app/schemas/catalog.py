from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrictBody(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class CatalogPriceTierInput(StrictBody):
    min_qty: Decimal = Field(default=Decimal(0), ge=0)
    max_qty: Decimal | None = Field(default=None, ge=0)
    price: Decimal = Field(default=Decimal(0), ge=0)
    price_unit: Decimal = Field(default=Decimal(1), gt=0)
    is_default: bool = False
    sort_order: int = Field(default=0, ge=0, le=10000)

    @model_validator(mode="after")
    def valid_range(self):
        if self.max_qty is not None and self.max_qty < self.min_qty:
            raise ValueError("Maximum quantity cannot be below minimum quantity")
        return self


class CatalogProductCreate(StrictBody):
    source_item_code: str | None = Field(default=None, max_length=100)
    category: str = Field(default="General", min_length=1, max_length=120)
    name: str = Field(min_length=1, max_length=220)
    unit: str = Field(default="ea", min_length=1, max_length=40)
    currency: str = Field(default="USD", min_length=3, max_length=3)
    manual_price: bool = False
    active: bool = True
    tiers: list[CatalogPriceTierInput] = Field(default_factory=list, max_length=100)

    @model_validator(mode="after")
    def valid_pricing(self):
        default_count = sum(1 for tier in self.tiers if tier.is_default)
        if default_count > 1:
            raise ValueError("Only one default price tier is allowed")
        if not self.manual_price and not self.tiers:
            raise ValueError("Priced catalog items require at least one price tier")
        return self


class CatalogProductUpdate(CatalogProductCreate):
    version: int = Field(ge=1)
