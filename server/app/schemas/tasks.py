from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

TaskPriority = Literal["Normal", "High", "Urgent"]
TaskStatus = Literal["Open", "In Progress", "Waiting", "Completed", "Cancelled"]


class StrictBody(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class TaskCreate(StrictBody):
    location_id: str = Field(min_length=1, max_length=36)
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=10000)
    status: TaskStatus = "Open"
    priority: TaskPriority = "Normal"
    assigned_employee_id: str | None = Field(default=None, max_length=36)
    due_date: date | None = None
    customer_id: str | None = Field(default=None, max_length=36)
    work_order_id: str | None = Field(default=None, max_length=36)
    issue_id: str | None = Field(default=None, max_length=36)


class TaskUpdate(StrictBody):
    version: int = Field(ge=1)
    location_id: str | None = Field(default=None, min_length=1, max_length=36)
    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=10000)
    status: TaskStatus | None = None
    priority: TaskPriority | None = None
    assigned_employee_id: str | None = Field(default=None, max_length=36)
    due_date: date | None = None
    customer_id: str | None = Field(default=None, max_length=36)
    work_order_id: str | None = Field(default=None, max_length=36)
    issue_id: str | None = Field(default=None, max_length=36)
