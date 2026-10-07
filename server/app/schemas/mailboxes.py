from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

MailboxStatus = Literal["Active", "Blocked", "Closing", "Closed"]
ForwardingStatus = Literal["None", "Scheduled", "Active"]


class StrictBody(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class MailboxCreate(StrictBody):
    location_id: str = Field(min_length=1, max_length=36)
    customer_id: str = Field(min_length=1, max_length=36)
    mailbox_number: str = Field(min_length=1, max_length=30)
    status: MailboxStatus = "Active"
    renewal_date: date | None = None
    balance_due: Decimal = Field(default=Decimal("0"), ge=0)
    primary_id_on_file: bool = False
    secondary_id_on_file: bool = False
    form_1583_complete: bool = False
    msa_complete: bool = False
    phone_verified: bool = False
    forwarding_status: ForwardingStatus = "None"
    forwarding_address: str = Field(default="", max_length=2000)
    notes: str = Field(default="", max_length=10000)

    @model_validator(mode="after")
    def forwarding_address_required(self):
        if self.forwarding_status != "None" and not self.forwarding_address:
            raise ValueError("A forwarding address is required when forwarding is scheduled or active")
        return self


class MailboxUpdate(MailboxCreate):
    version: int = Field(ge=1)
