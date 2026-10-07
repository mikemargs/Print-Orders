from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

ChecklistType = Literal["Opening", "Closing", "Daily", "Weekly", "Other"]
Cadence = Literal["Daily", "Weekdays", "Weekly"]


class StrictBody(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class ChecklistTemplateCreate(StrictBody):
    location_id: str = Field(min_length=1, max_length=36)
    name: str = Field(min_length=1, max_length=180)
    checklist_type: ChecklistType = "Daily"
    cadence: Cadence = "Daily"
    weekday: int | None = Field(default=None, ge=0, le=6)
    items: list[str] = Field(min_length=1, max_length=50)
    active: bool = True

    @field_validator("items")
    @classmethod
    def clean_items(cls, value):
        cleaned = [item.strip() for item in value if item.strip()]
        if not cleaned:
            raise ValueError("At least one checklist item is required")
        if any(len(item) > 300 for item in cleaned):
            raise ValueError("Checklist items cannot exceed 300 characters")
        return cleaned

    @model_validator(mode="after")
    def weekly_requires_day(self):
        if self.cadence == "Weekly" and self.weekday is None:
            raise ValueError("Weekly checklists require a weekday")
        if self.cadence != "Weekly":
            self.weekday = None
        return self


class ChecklistTemplateUpdate(ChecklistTemplateCreate):
    version: int = Field(ge=1)


class ChecklistGenerate(StrictBody):
    location_id: str = Field(min_length=1, max_length=36)
    business_date: date | None = None


class ChecklistItemInput(StrictBody):
    label: str = Field(min_length=1, max_length=300)
    completed: bool = False


class ChecklistRunUpdate(StrictBody):
    version: int = Field(ge=1)
    items: list[ChecklistItemInput] = Field(min_length=1, max_length=50)
