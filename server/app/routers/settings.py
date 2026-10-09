from decimal import Decimal
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import update
from sqlalchemy.orm import Session

from ..database import Company
from ..web_sessions import get_web_db, web_auth_context, web_mutation_context

router = APIRouter(prefix="/api", tags=["settings"])


class SettingsUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    version: int = Field(ge=1)
    default_tax_rate: Decimal = Field(ge=0, le=100, max_digits=7, decimal_places=4)
    default_order_priority: Literal["Normal", "High", "Rush"]
    default_delivery_method: Literal["Pickup", "Delivery", "Ship"]


def order_defaults(company):
    return {
        "default_tax_rate": float(company.default_tax_rate),
        "default_order_priority": company.default_order_priority,
        "default_delivery_method": company.default_delivery_method,
        "version": company.settings_version,
    }


def require_admin(auth):
    if auth.role != "admin":
        raise HTTPException(403, "Admin permission is required")


@router.get("/order-defaults")
def get_order_defaults(auth=Depends(web_auth_context), db: Session = Depends(get_web_db)):
    return order_defaults(db.get(Company, auth.company_id))


@router.get("/settings")
def get_settings(auth=Depends(web_auth_context), db: Session = Depends(get_web_db)):
    require_admin(auth)
    return order_defaults(db.get(Company, auth.company_id))


@router.patch("/settings")
def update_settings(body: SettingsUpdate, auth=Depends(web_mutation_context), db: Session = Depends(get_web_db)):
    require_admin(auth)
    values = body.model_dump(exclude={"version"})
    result = db.execute(update(Company).where(
        Company.id == auth.company_id, Company.settings_version == body.version
    ).values(**values, settings_version=Company.settings_version + 1))
    if result.rowcount != 1:
        db.rollback()
        raise HTTPException(409, "Settings changed in another session. Reload before saving.")
    db.commit()
    db.expire_all()
    return order_defaults(db.get(Company, auth.company_id))
