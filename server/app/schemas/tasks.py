from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

TaskStatus = Literal["Open", "In Progress", "Waiting", "Completed", "Cancelled"]
TaskPriority = Literal["Low", "Normal", "High", "Urgent"]


class StrictBody(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class TaskCreate(StrictBody):
    location_id: str = Field(min_length=1, max_length=36)
    title: str = Field(min_length=1, max_length=220)
    description: str = Field(default="", max_length=10000)
    status: TaskStatus = "Open"
    priority: TaskPriority = "Normal"
    due_date: date | None = None
    assigned_employee_id: str | None = Field(default=None, max_length=36)
    customer_id: str | None = Field(default=None, max_length=36)
    work_order_id: str | None = Field(default=None, max_length=36)
    customer_issue_id: str | None = Field(default=None, max_length=36)


class TaskUpdate(TaskCreate):
    version: int = Field(ge=1)
