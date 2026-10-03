from __future__ import annotations

from dataclasses import dataclass

from fastapi import HTTPException
from sqlalchemy.orm import Session

from .database import Company, Employee, Location


@dataclass(frozen=True)
class AuthContext:
    company_id: str
    employee_id: str
    role: str
    location_id: str
    auth_version: int

    def __getitem__(self, key: str):
        return getattr(self, key)

    def get(self, key: str, default=None):
        return getattr(self, key, default)


def resolve_employee_context(db: Session, claims: dict) -> AuthContext:
    if claims.get("type") not in {"employee", "web_employee"}:
        raise HTTPException(403, "Employee sign-in required")
    company = db.get(Company, claims.get("company_id", ""))
    if not company or not company.active:
        raise HTTPException(403, "Company access has been disabled")
    employee = db.get(Employee, claims.get("employee_id", ""))
    if not employee or employee.company_id != company.id or not employee.active:
        raise HTTPException(403, "Employee access has been disabled")
    location_id = claims.get("location_id", "")
    if not location_id:
        raise HTTPException(401, "Employee sign-in must be refreshed")
    location = db.get(Location, location_id)
    if not location or location.company_id != company.id or not location.active:
        raise HTTPException(403, "Store access has been disabled")
    if employee.role != "admin" and employee.location_ids and location_id not in employee.location_ids:
        raise HTTPException(403, "Employee is no longer assigned to this store")
    if int(claims.get("auth_version", 0)) != int(employee.auth_version):
        raise HTTPException(401, "Employee sign-in must be refreshed")
    return AuthContext(
        company_id=company.id,
        employee_id=employee.id,
        role=employee.role,
        location_id=location_id,
        auth_version=int(employee.auth_version),
    )
