from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

ChecklistCategory = Literal[
    "Opening", "Closing", "Cleaning", "Equipment", "Deposit", "Supplies", "Safety", "Daily", "Other"
]
CompletionStatus = Literal["Completed", "Skipped"]


class StrictBody(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class ChecklistTemplateCreate(StrictBody):
    location_id: str = Field(min_length=1, max_length=36)
    title: str = Field(min_length=1, max_length=220)
    description: str = Field(default="", max_length=10000)
    category: ChecklistCategory = "Daily"
    active_days: list[int] = Field(default_factory=lambda: [0, 1, 2, 3, 4, 5, 6], min_length=1, max_length=7)
    required: bool = True
    active: bool = True
    sort_order: int = Field(default=0, ge=0, le=10000)

    @field_validator("active_days")
    @classmethod
    def valid_days(cls, value):
        if any(day < 0 or day > 6 for day in value) or len(set(value)) != len(value):
            raise ValueError("active_days must contain unique weekday numbers from 0 through 6")
        return sorted(value)


class ChecklistTemplateUpdate(ChecklistTemplateCreate):
    version: int = Field(ge=1)


class ChecklistCompletionUpsert(StrictBody):
    checklist_date: date
    status: CompletionStatus
    notes: str = Field(default="", max_length=10000)
    version: int | None = Field(default=None, ge=1)
