from __future__ import annotations

import os
import uuid
from collections import Counter, defaultdict
from contextlib import asynccontextmanager
from typing import Any, Literal

import jwt
from fastapi import Depends, FastAPI, Header, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .database import (
    Base,
    Company,
    Customer,
    Employee,
    Location,
    ProcessedOperation,
    SessionLocal,
    SyncEvent,
    WorkOrder,
    engine,
    utcnow,
)
from .security import decode_token, hash_secret, make_token, verify_secret

CUSTOMER_FIELDS = {
    "company",
    "first_name",
    "last_name",
    "phone",
    "email",
    "address1",
    "address2",
    "city",
    "state",
    "postal_code",
    "tax_exempt",
    "notes",
}
ORDER_FIELDS = {
    "customer_id",
    "location_id",
    "order_number",
    "status",
    "priority",
    "received_date",
    "due_date",
    "assigned_to",
    "delivery_method",
    "po_number",
    "description",
    "artwork_path",
    "production_notes",
    "customer_notes",
    "tax_rate",
    "deposit",
    "discount",
    "items",
}
VALID_ROLES = {"employee", "supervisor", "admin"}


class CompanyLogin(BaseModel):
    company_code: str
    password: str


class EmployeeLogin(BaseModel):
    employee_id: str
    pin: str
    location_id: str


class SyncOperation(BaseModel):
    operation_id: str
    entity_type: Literal["customer", "order"]
    action: Literal["upsert", "delete"]
    entity_id: str
    base_version: int = 0
    payload: dict[str, Any] = Field(default_factory=dict)


class SyncPush(BaseModel):
    operations: list[SyncOperation] = Field(default_factory=list, max_length=250)


class EmployeeCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    pin: str = Field(min_length=4, max_length=12)
    role: Literal["employee", "supervisor", "admin"] = "employee"
    location_ids: list[str] = Field(default_factory=list)


class EmployeeUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    pin: str | None = Field(default=None, min_length=4, max_length=12)
    role: Literal["employee", "supervisor", "admin"] | None = None
    location_ids: list[str] | None = None
    active: bool | None = None


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def token_claims(authorization: str = Header(default="")) -> dict:
    if not authorization.startswith("Bearer "):
        raise HTTPException(401, "Sign-in required")
    try:
        return decode_token(authorization[7:])
    except jwt.ExpiredSignatureError:
        raise HTTPException(401, "Sign-in expired")
    except (jwt.InvalidTokenError, RuntimeError):
        raise HTTPException(401, "Invalid sign-in")


def employee_claims(claims: dict = Depends(token_claims), db: Session = Depends(get_db)) -> dict:
    if claims.get("type") != "employee":
        raise HTTPException(403, "Employee sign-in required")
    employee = db.get(Employee, claims.get("employee_id", ""))
    if not employee or employee.company_id != claims.get("company_id") or not employee.active:
        raise HTTPException(403, "Employee access has been disabled")
    current = dict(claims)
    current["role"] = employee.role
    return current


def admin_claims(claims: dict = Depends(employee_claims)) -> dict:
    if claims.get("role") != "admin":
        raise HTTPException(403, "Administrator permission required")
    return claims


def supervisor_claims(claims: dict = Depends(employee_claims)) -> dict:
    if claims.get("role") not in {"supervisor", "admin"}:
        raise HTTPException(403, "Supervisor permission required")
    return claims


def bootstrap_from_environment() -> None:
    with SessionLocal() as db:
        if db.scalar(select(func.count()).select_from(Company)):
            return
        password = os.environ.get("BOOTSTRAP_COMPANY_PASSWORD", "")
        admin_pin = os.environ.get("BOOTSTRAP_ADMIN_PIN", "")
        if not password or not admin_pin:
            return
        company_id = str(uuid.uuid4())
        company = Company(
            id=company_id,
            name=os.environ.get("BOOTSTRAP_COMPANY_NAME", "Print Operations"),
            code=os.environ.get("BOOTSTRAP_COMPANY_CODE", "UPS-PRINT").strip().upper(),
            password_hash=hash_secret(password),
        )
        db.add(company)
        locations = [
            Location(
                id=str(uuid.uuid4()),
                company_id=company_id,
                name="Sayville",
                store_number="5127",
            ),
            Location(
                id=str(uuid.uuid4()),
                company_id=company_id,
                name="Selden",
                store_number="5345",
            ),
            Location(
                id=str(uuid.uuid4()),
                company_id=company_id,
                name="Mt. Sinai",
                store_number="3167",
            ),
        ]
        db.add_all(locations)
        db.add(
            Employee(
                id=str(uuid.uuid4()),
                company_id=company_id,
                name=os.environ.get("BOOTSTRAP_ADMIN_NAME", "Administrator"),
                pin_hash=hash_secret(admin_pin),
                role="admin",
                location_ids=[loc.id for loc in locations],
                active=True,
            )
        )
        db.commit()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    Base.metadata.create_all(engine)
    bootstrap_from_environment()
    yield


app = FastAPI(
    title="Print Order Manager Multi-Store API",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url=None,
    lifespan=lifespan,
)


@app.get("/api/health")
def health():
    return {"status": "ok", "time": utcnow().isoformat()}


@app.get("/api/setup/status")
def setup_status(db: Session = Depends(get_db)):
    return {"initialized": bool(db.scalar(select(func.count()).select_from(Company)))}


@app.post("/api/auth/company-login")
def company_login(body: CompanyLogin, db: Session = Depends(get_db)):
    company = db.scalar(select(Company).where(Company.code == body.company_code.strip().upper()))
    if not company or not company.active or not verify_secret(body.password, company.password_hash):
        raise HTTPException(401, "Company code or password is incorrect")
    return {
        "token": make_token(company.id, "company"),
        "company": {"id": company.id, "name": company.name, "code": company.code},
    }


@app.post("/api/auth/employee-login")
def employee_login(
    body: EmployeeLogin,
    claims: dict = Depends(token_claims),
    db: Session = Depends(get_db),
):
    if claims.get("type") != "company":
        raise HTTPException(403, "Company sign-in required")
    employee = db.get(Employee, body.employee_id)
    location = db.get(Location, body.location_id)
    if not employee or employee.company_id != claims["company_id"] or not employee.active:
        raise HTTPException(401, "Employee is not active")
    if not location or location.company_id != claims["company_id"] or not location.active:
        raise HTTPException(400, "Store location is not active")
    if (
        employee.location_ids
        and body.location_id not in employee.location_ids
        and employee.role != "admin"
    ):
        raise HTTPException(403, "Employee is not assigned to this store")
    if not verify_secret(body.pin, employee.pin_hash):
        raise HTTPException(401, "PIN is incorrect")
    return {
        "token": make_token(employee.company_id, "employee", employee.id, employee.role),
        "employee": public_employee(employee),
    }


@app.get("/api/bootstrap")
def bootstrap(claims: dict = Depends(token_claims), db: Session = Depends(get_db)):
    company_id = claims["company_id"]
    company = db.get(Company, company_id)
    if not company or not company.active:
        raise HTTPException(403, "Company is inactive")
    locations = db.scalars(
        select(Location).where(Location.company_id == company_id, Location.active)
    ).all()
    employees = db.scalars(
        select(Employee).where(Employee.company_id == company_id, Employee.active)
    ).all()
    return {
        "company": {"id": company.id, "name": company.name, "code": company.code},
        "locations": [public_location(x) for x in locations],
        "employees": [public_employee(x) for x in employees],
        "server_time": utcnow().isoformat(),
    }


@app.post("/api/sync/push")
def sync_push(
    body: SyncPush,
    claims: dict = Depends(employee_claims),
    db: Session = Depends(get_db),
):
    results = []
    for operation in body.operations:
        prior = db.get(ProcessedOperation, operation.operation_id)
        if prior:
            results.append(prior.result)
            continue
        if operation.action == "delete" and claims["role"] not in {
            "supervisor",
            "admin",
        }:
            result = sync_result(
                operation,
                "forbidden",
                message="Supervisor permission is required to delete records",
            )
        else:
            result = apply_operation(db, claims, operation)
        db.add(
            ProcessedOperation(
                id=operation.operation_id,
                company_id=claims["company_id"],
                result=result,
            )
        )
        db.commit()
        results.append(result)
    return {"results": results}


@app.get("/api/sync/pull")
def sync_pull(
    cursor: int = Query(default=0, ge=0),
    limit: int = Query(default=500, ge=1, le=1000),
    claims: dict = Depends(employee_claims),
    db: Session = Depends(get_db),
):
    events = db.scalars(
        select(SyncEvent)
        .where(SyncEvent.company_id == claims["company_id"], SyncEvent.sequence > cursor)
        .order_by(SyncEvent.sequence)
        .limit(limit)
    ).all()
    new_cursor = events[-1].sequence if events else cursor
    return {
        "events": [
            {
                "sequence": event.sequence,
                "entity_type": event.entity_type,
                "entity_id": event.entity_id,
                "change_type": event.change_type,
                "payload": event.payload,
            }
            for event in events
        ],
        "cursor": new_cursor,
        "has_more": len(events) == limit,
    }


@app.get("/api/reports/summary")
def report_summary(
    location_id: str = "",
    start_date: str = "",
    end_date: str = "",
    claims: dict = Depends(supervisor_claims),
    db: Session = Depends(get_db),
):
    query = select(WorkOrder).where(
        WorkOrder.company_id == claims["company_id"], WorkOrder.is_deleted.is_(False)
    )
    if location_id:
        query = query.where(WorkOrder.location_id == location_id)
    if start_date:
        query = query.where(WorkOrder.received_date >= start_date)
    if end_date:
        query = query.where(WorkOrder.received_date <= end_date)
    orders = db.scalars(query).all()
    locations = {
        x.id: x
        for x in db.scalars(
            select(Location).where(Location.company_id == claims["company_id"])
        ).all()
    }
    grouped: dict[str, dict] = defaultdict(lambda: {"orders": 0, "sales": 0.0, "balance": 0.0})
    statuses = Counter()
    for order in orders:
        key = order.location_id
        grouped[key]["orders"] += 1
        grouped[key]["sales"] += order.total
        grouped[key]["balance"] += order.balance
        statuses[order.status] += 1
    return {
        "total_orders": len(orders),
        "total_sales": round(sum(x.total for x in orders), 2),
        "outstanding_balance": round(sum(x.balance for x in orders), 2),
        "by_status": dict(statuses),
        "by_location": [
            {
                "location_id": key,
                "location": f"{locations[key].name} #{locations[key].store_number}"
                if key in locations
                else key,
                **{k: round(v, 2) if isinstance(v, float) else v for k, v in values.items()},
            }
            for key, values in grouped.items()
        ],
    }


@app.get("/api/admin/employees")
def list_employees(_claims: dict = Depends(admin_claims), db: Session = Depends(get_db)):
    employees = db.scalars(
        select(Employee).where(Employee.company_id == _claims["company_id"])
    ).all()
    return {"employees": [public_employee(x) for x in employees]}


@app.post("/api/admin/employees")
def create_employee(
    body: EmployeeCreate,
    claims: dict = Depends(admin_claims),
    db: Session = Depends(get_db),
):
    validate_locations(db, claims["company_id"], body.location_ids)
    employee = Employee(
        id=str(uuid.uuid4()),
        company_id=claims["company_id"],
        name=body.name.strip(),
        pin_hash=hash_secret(body.pin),
        role=body.role,
        location_ids=body.location_ids,
        active=True,
    )
    db.add(employee)
    db.commit()
    return {"employee": public_employee(employee)}


@app.patch("/api/admin/employees/{employee_id}")
def update_employee(
    employee_id: str,
    body: EmployeeUpdate,
    claims: dict = Depends(admin_claims),
    db: Session = Depends(get_db),
):
    employee = db.get(Employee, employee_id)
    if not employee or employee.company_id != claims["company_id"]:
        raise HTTPException(404, "Employee not found")
    changes = body.model_dump(exclude_unset=True)
    if "location_ids" in changes:
        validate_locations(db, claims["company_id"], changes["location_ids"])
    if "pin" in changes:
        employee.pin_hash = hash_secret(changes.pop("pin"))
    for key, value in changes.items():
        setattr(employee, key, value.strip() if key == "name" else value)
    employee.updated_at = utcnow()
    db.commit()
    return {"employee": public_employee(employee)}


def validate_locations(db: Session, company_id: str, location_ids: list[str]) -> None:
    valid = set(
        db.scalars(
            select(Location.id).where(Location.company_id == company_id, Location.active)
        ).all()
    )
    if any(item not in valid for item in location_ids):
        raise HTTPException(400, "One or more store assignments are invalid")


def apply_operation(db: Session, claims: dict, operation: SyncOperation) -> dict:
    model = Customer if operation.entity_type == "customer" else WorkOrder
    record = db.scalar(select(model).where(model.id == operation.entity_id).with_for_update())
    if record and record.company_id != claims["company_id"]:
        return sync_result(operation, "forbidden", message="Record belongs to another company")
    if record and operation.base_version != record.version:
        return sync_result(operation, "conflict", server=serialize_record(record))
    if not record and operation.base_version != 0:
        return sync_result(operation, "conflict", message="Record no longer exists")
    if operation.action == "delete":
        if not record:
            return sync_result(operation, "applied", version=operation.base_version)
        record.is_deleted = True
    else:
        payload = operation.payload
        allowed = CUSTOMER_FIELDS if operation.entity_type == "customer" else ORDER_FIELDS
        if not record:
            if operation.entity_type == "customer":
                record = Customer(id=operation.entity_id, company_id=claims["company_id"])
            else:
                if not payload.get("customer_id") or not payload.get("location_id"):
                    return sync_result(
                        operation,
                        "invalid",
                        message="Order customer and location are required",
                    )
                customer = db.get(Customer, payload["customer_id"])
                location = db.get(Location, payload["location_id"])
                if not customer or customer.company_id != claims["company_id"]:
                    return sync_result(operation, "invalid", message="Customer was not found")
                if not location or location.company_id != claims["company_id"]:
                    return sync_result(operation, "invalid", message="Store location was not found")
                record = WorkOrder(id=operation.entity_id, company_id=claims["company_id"])
            db.add(record)
        for key, value in payload.items():
            if key in allowed:
                if isinstance(record, Customer) and key == "tax_exempt":
                    value = value is True or value == 1 or str(value).lower() in {"true", "yes"}
                setattr(record, key, value)
        record.is_deleted = False
        if isinstance(record, WorkOrder):
            calculate_order(record)
    record.version = (record.version if record.id and record.version else 0) + (
        0 if operation.base_version == 0 and record.version == 1 else 1
    )
    if operation.base_version == 0:
        record.version = 1
    record.updated_at = utcnow()
    record.updated_by = claims["employee_id"]
    db.flush()
    payload = serialize_record(record)
    db.add(
        SyncEvent(
            company_id=claims["company_id"],
            entity_type=operation.entity_type,
            entity_id=record.id,
            change_type="delete" if record.is_deleted else "upsert",
            payload=payload,
        )
    )
    return sync_result(operation, "applied", version=record.version, server=payload)


def calculate_order(order: WorkOrder) -> None:
    subtotal = 0.0
    clean_items = []
    for item in order.items or []:
        clean = dict(item)
        quantity = max(float(clean.get("quantity", 0) or 0), 0)
        unit_price = max(float(clean.get("unit_price", 0) or 0), 0)
        clean["quantity"], clean["unit_price"] = quantity, unit_price
        clean_items.append(clean)
        subtotal += quantity * unit_price
    order.items = clean_items
    order.tax_rate = max(float(order.tax_rate or 0), 0)
    order.discount = max(float(order.discount or 0), 0)
    order.deposit = max(float(order.deposit or 0), 0)
    taxable = max(subtotal - order.discount, 0)
    order.subtotal = round(subtotal, 2)
    order.total = round(taxable * (1 + order.tax_rate / 100), 2)
    order.balance = round(max(order.total - order.deposit, 0), 2)


def serialize_record(record: Customer | WorkOrder) -> dict:
    fields = (
        CUSTOMER_FIELDS
        if isinstance(record, Customer)
        else ORDER_FIELDS | {"subtotal", "total", "balance"}
    )
    result = {key: getattr(record, key) for key in fields}
    result.update(
        {
            "id": record.id,
            "version": record.version,
            "is_deleted": record.is_deleted,
            "updated_at": record.updated_at.isoformat() if record.updated_at else "",
            "updated_by": record.updated_by,
        }
    )
    return result


def sync_result(
    operation: SyncOperation,
    status: str,
    version: int | None = None,
    server: dict | None = None,
    message: str = "",
) -> dict:
    return {
        "operation_id": operation.operation_id,
        "entity_type": operation.entity_type,
        "entity_id": operation.entity_id,
        "status": status,
        "version": version,
        "server": server,
        "message": message,
    }


def public_employee(employee: Employee) -> dict:
    return {
        "id": employee.id,
        "name": employee.name,
        "role": employee.role,
        "location_ids": employee.location_ids or [],
        "active": employee.active,
        "updated_at": employee.updated_at.isoformat() if employee.updated_at else "",
    }


def public_location(location: Location) -> dict:
    return {
        "id": location.id,
        "name": location.name,
        "store_number": location.store_number,
        "timezone": location.timezone,
        "active": location.active,
    }
