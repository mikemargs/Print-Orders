from __future__ import annotations

from collections.abc import Generator

from fastapi import APIRouter, Cookie, Depends, Header, HTTPException, Request, Response
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..auth_context import AuthContext
from ..database import Company, Employee, Location, SessionLocal
from ..security import clear_login_failures, login_allowed, record_login_failure, verify_secret
from ..web_sessions import (
    COMPANY_CHALLENGE_COOKIE,
    COMPANY_CHALLENGE_MINUTES,
    EMPLOYEE_SESSION_COOKIE,
    EMPLOYEE_SESSION_HOURS,
    cookie_secure,
    create_company_challenge,
    create_employee_session,
    decode_web_token,
    require_csrf,
    resolve_web_session,
)

router = APIRouter(prefix="/api/web", tags=["web-auth"])


class WebCompanyLogin(BaseModel):
    company_code: str
    password: str


class WebEmployeeLogin(BaseModel):
    employee_id: str
    pin: str
    location_id: str


class WebLocationSwitch(BaseModel):
    location_id: str


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def employee_public(employee: Employee) -> dict:
    return {
        "id": employee.id,
        "name": employee.name,
        "role": employee.role,
        "location_ids": employee.location_ids or [],
        "active": employee.active,
        "auth_version": int(employee.auth_version or 1),
    }


def location_public(location: Location) -> dict:
    return {
        "id": location.id,
        "name": location.name,
        "store_number": location.store_number,
        "timezone": location.timezone,
        "active": location.active,
    }


def active_locations(db: Session, company_id: str) -> list[Location]:
    return list(
        db.scalars(
            select(Location).where(Location.company_id == company_id, Location.active.is_(True))
        ).all()
    )


def session_payload(company: Company, employee: Employee, location: Location, locations: list[Location], csrf: str) -> dict:
    return {
        "csrf_token": csrf,
        "employee": employee_public(employee),
        "location": location_public(location),
        "locations": [location_public(x) for x in locations],
        "company": {"id": company.id, "name": company.name, "code": company.code},
    }


@router.post("/auth/company")
def web_company_login(body: WebCompanyLogin, request: Request, response: Response, db: Session = Depends(get_db)):
    code = body.company_code.strip().upper()
    ip = request.client.host if request.client else "unknown"
    key = f"web-company:{code}:{ip}"
    if not login_allowed(key):
        raise HTTPException(429, "Too many sign-in attempts. Try again later.")
    company = db.scalar(select(Company).where(Company.code == code))
    if not company or not company.active or not verify_secret(body.password, company.password_hash):
        record_login_failure(key)
        raise HTTPException(401, "Company code or password is incorrect")
    clear_login_failures(key)
    locations = db.scalars(select(Location).where(Location.company_id == company.id, Location.active.is_(True))).all()
    employees = db.scalars(select(Employee).where(Employee.company_id == company.id, Employee.active.is_(True))).all()
    response.set_cookie(
        COMPANY_CHALLENGE_COOKIE,
        create_company_challenge(company.id),
        max_age=COMPANY_CHALLENGE_MINUTES * 60,
        secure=cookie_secure(),
        httponly=True,
        samesite="strict",
        path="/",
    )
    return {
        "company": {"id": company.id, "name": company.name, "code": company.code},
        "locations": [location_public(x) for x in locations],
        "employees": [employee_public(x) for x in employees],
    }


@router.post("/auth/employee")
def web_employee_login(
    body: WebEmployeeLogin,
    request: Request,
    response: Response,
    challenge: str = Cookie(default="", alias=COMPANY_CHALLENGE_COOKIE),
    db: Session = Depends(get_db),
):
    claims = decode_web_token(challenge, "web_company_challenge")
    company_id = claims["company_id"]
    company = db.get(Company, company_id)
    employee = db.get(Employee, body.employee_id)
    location = db.get(Location, body.location_id)
    if not company or not company.active:
        raise HTTPException(403, "Company access has been disabled")
    if not employee or employee.company_id != company_id or not employee.active:
        raise HTTPException(401, "Employee is not active")
    if not location or location.company_id != company_id or not location.active:
        raise HTTPException(400, "Store location is not active")
    if employee.role != "admin" and employee.location_ids and body.location_id not in employee.location_ids:
        raise HTTPException(403, "Employee is not assigned to this store")
    ip = request.client.host if request.client else "unknown"
    key = f"web-employee:{company_id}:{employee.id}:{ip}"
    if not login_allowed(key):
        raise HTTPException(429, "Too many PIN attempts. Try again later.")
    if not verify_secret(body.pin, employee.pin_hash):
        record_login_failure(key)
        raise HTTPException(401, "PIN is incorrect")
    clear_login_failures(key)
    auth = AuthContext(company_id, employee.id, employee.role, location.id, int(employee.auth_version or 1))
    session_token, csrf = create_employee_session(auth)
    response.set_cookie(
        EMPLOYEE_SESSION_COOKIE,
        session_token,
        max_age=EMPLOYEE_SESSION_HOURS * 3600,
        secure=cookie_secure(),
        httponly=True,
        samesite="strict",
        path="/",
    )
    response.delete_cookie(COMPANY_CHALLENGE_COOKIE, path="/", secure=cookie_secure(), httponly=True, samesite="strict")
    locations = active_locations(db, company_id)
    return session_payload(company, employee, location, locations, csrf)


@router.post("/auth/location")
def web_switch_location(
    body: WebLocationSwitch,
    response: Response,
    session_token: str = Cookie(default="", alias=EMPLOYEE_SESSION_COOKIE),
    csrf_token: str = Header(default="", alias="X-CSRF-Token"),
    db: Session = Depends(get_db),
):
    auth, claims = resolve_web_session(db, session_token)
    require_csrf(claims, csrf_token)
    company = db.get(Company, auth.company_id)
    employee = db.get(Employee, auth.employee_id)
    location = db.get(Location, body.location_id)
    if not company or not company.active:
        raise HTTPException(403, "Company access has been disabled")
    if not employee or not employee.active:
        raise HTTPException(403, "Employee access has been disabled")
    if not location or location.company_id != company.id or not location.active:
        raise HTTPException(400, "Store location is not active")
    if employee.role != "admin" and employee.location_ids and location.id not in employee.location_ids:
        raise HTTPException(403, "Employee is not assigned to this store")

    next_auth = AuthContext(
        company.id,
        employee.id,
        employee.role,
        location.id,
        int(employee.auth_version or 1),
    )
    next_session_token, csrf = create_employee_session(next_auth)
    response.set_cookie(
        EMPLOYEE_SESSION_COOKIE,
        next_session_token,
        max_age=EMPLOYEE_SESSION_HOURS * 3600,
        secure=cookie_secure(),
        httponly=True,
        samesite="strict",
        path="/",
    )
    return session_payload(company, employee, location, active_locations(db, company.id), csrf)


@router.get("/session")
def web_session(session_token: str = Cookie(default="", alias=EMPLOYEE_SESSION_COOKIE), db: Session = Depends(get_db)):
    auth, claims = resolve_web_session(db, session_token)
    company = db.get(Company, auth.company_id)
    employee = db.get(Employee, auth.employee_id)
    location = db.get(Location, auth.location_id)
    locations = active_locations(db, auth.company_id)
    return session_payload(company, employee, location, locations, claims["csrf"])


@router.post("/auth/logout")
def web_logout(
    response: Response,
    session_token: str = Cookie(default="", alias=EMPLOYEE_SESSION_COOKIE),
    csrf_token: str = Header(default="", alias="X-CSRF-Token"),
    db: Session = Depends(get_db),
):
    if session_token:
        _auth, claims = resolve_web_session(db, session_token)
        require_csrf(claims, csrf_token)
    response.delete_cookie(EMPLOYEE_SESSION_COOKIE, path="/", secure=cookie_secure(), httponly=True, samesite="strict")
    response.delete_cookie(COMPANY_CHALLENGE_COOKIE, path="/", secure=cookie_secure(), httponly=True, samesite="strict")
    return {"ok": True}
