from datetime import date

from pydantic import BaseModel, Field, field_validator

STATUSES = {"Open", "In Progress", "Waiting", "Completed", "Cancelled"}
PRIORITIES = {"Low", "Normal", "High", "Urgent"}


class TaskCreate(BaseModel):
    location_id: str
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=5000)
    status: str = "Open"
    priority: str = "Normal"
    due_date: date | None = None
    assigned_employee_id: str | None = None
    customer_id: str | None = None
    work_order_id: str | None = None
    issue_id: str | None = None

    @field_validator("title", "description")
    @classmethod
    def trim_text(cls, value: str):
        return value.strip()

    @field_validator("status")
    @classmethod
    def valid_status(cls, value: str):
        if value not in STATUSES:
            raise ValueError("Invalid task status")
        return value

    @field_validator("priority")
    @classmethod
    def valid_priority(cls, value: str):
        if value not in PRIORITIES:
            raise ValueError("Invalid task priority")
        return value


class TaskUpdate(BaseModel):
    version: int = Field(ge=1)
    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=5000)
    status: str | None = None
    priority: str | None = None
    due_date: date | None = None
    assigned_employee_id: str | None = None
    customer_id: str | None = None
    work_order_id: str | None = None
    issue_id: str | None = None

    @field_validator("title", "description")
    @classmethod
    def trim_optional_text(cls, value: str | None):
        return value.strip() if value is not None else value

    @field_validator("status")
    @classmethod
    def valid_status(cls, value: str | None):
        if value is not None and value not in STATUSES:
            raise ValueError("Invalid task status")
        return value

    @field_validator("priority")
    @classmethod
    def valid_priority(cls, value: str | None):
        if value is not None and value not in PRIORITIES:
            raise ValueError("Invalid task priority")
        return value
