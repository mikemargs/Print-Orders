from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

Category = Literal[
    "Shipping", "Print Order", "Mailbox", "Billing/Refund", "Customer Service", "Other"
]
Priority = Literal["Low", "Normal", "High", "Urgent"]
Status = Literal["Open", "In Progress", "Waiting on Customer", "Waiting on Third Party", "Resolved"]
Channel = Literal["phone", "email", "in person", "internal note", "other"]


class StrictBody(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class IssueCreate(StrictBody):
    customer_id: str = Field(min_length=1, max_length=36)
    location_id: str = Field(min_length=1, max_length=36)
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=1, max_length=10000)
    category: Category = "Customer Service"
    priority: Priority = "Normal"
    assigned_employee_id: str | None = Field(default=None, max_length=36)
    work_order_id: str | None = Field(default=None, max_length=36)
    next_action: str = Field(default="", max_length=2000)
    follow_up_date: date | None = None


class IssueUpdate(StrictBody):
    version: int = Field(ge=1)
    customer_id: str = Field(default="", min_length=1, max_length=36)
    location_id: str = Field(default="", min_length=1, max_length=36)
    title: str = Field(default="", min_length=1, max_length=200)
    description: str = Field(default="", min_length=1, max_length=10000)
    category: Category = "Customer Service"
    priority: Priority = "Normal"
    status: Status = "Open"
    assigned_employee_id: str | None = Field(default=None, max_length=36)
    work_order_id: str | None = Field(default=None, max_length=36)
    next_action: str = Field(default="", max_length=2000)
    follow_up_date: date | None = None
    resolution_summary: str = Field(default="", max_length=10000)
    reopen_reason: str = Field(default="", min_length=1, max_length=10000)

    @model_validator(mode="after")
    def resolution(self):
        if self.status == "Resolved" and not self.resolution_summary:
            raise ValueError("A resolution summary is required")
        return self


class CommunicationCreate(StrictBody):
    operation_id: UUID
    channel: Channel
    occurred_at: datetime
    summary: str = Field(min_length=1, max_length=10000)
    version: int | None = Field(default=None, ge=1)
    next_action: str = Field(default="", max_length=2000)
    follow_up_date: date | None = None

    @field_validator("occurred_at")
    @classmethod
    def aware_time(cls, value):
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("Occurrence time must include a timezone offset")
        return value

    @model_validator(mode="after")
    def requires_version(self):
        if {"next_action", "follow_up_date"} & self.model_fields_set and self.version is None:
            raise ValueError("Version is required when updating follow-up information")
        return self
