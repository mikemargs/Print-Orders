from __future__ import annotations

import uuid
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..auth_context import AuthContext
from ..database import Customer, Location, SyncEvent, WorkOrder, utcnow
from .common import Conflict, Forbidden, Invalid

CUSTOMER_FIELDS = {
    "company", "first_name", "last_name", "phone", "email", "address1", "address2",
    "city", "state", "postal_code", "tax_exempt", "notes",
}
ORDER_FIELDS = {
    "customer_id", "location_id", "order_number", "status", "priority", "received_date",
    "due_date", "assigned_to", "delivery_method", "po_number", "description", "artwork_path",
    "production_notes", "customer_notes", "tax_rate", "deposit", "discount",
    "discount_mode", "discount_percent", "items",
}
ORDER_STATUSES = {"Quote","New","Awaiting Artwork","Proof Sent","Proof Approved","In Production","Ready for Pickup","Completed","On Hold","Cancelled"}
PRIORITIES = {"Normal","Rush","High"}
DISCOUNT_MODES = {"amount", "percent"}
MAX_MONEY = Decimal("9999999999.99")
MAX_TAX_RATE = Decimal("999.9999")
MAX_DISCOUNT_PERCENT = Decimal(100)
CUSTOMER_TEXT_LIMITS = {
    "company": 180, "first_name": 100, "last_name": 100, "phone": 60, "email": 180,
    "address1": 180, "address2": 180, "city": 100, "state": 60, "postal_code": 30,
}
ORDER_TEXT_LIMITS = {
    "order_number": 70, "assigned_to": 120, "delivery_method": 50, "po_number": 80,
    "description": 300,
}


def _normalize_bounded_text(payload: dict, limits: dict[str, int]) -> None:
    for key, max_length in limits.items():
        if key not in payload:
            continue
        value = payload[key]
        if value is None:
            payload[key] = ""
            continue
        if not isinstance(value, str):
            raise Invalid(f"{key} must be text")
        if len(value) > max_length:
            raise Invalid(f"{key} must be {max_length} characters or fewer")


def serialize_record(record: Customer | WorkOrder) -> dict:
    fields = CUSTOMER_FIELDS if isinstance(record, Customer) else ORDER_FIELDS | {"subtotal", "total", "balance"}
    result = {}
    for key in fields:
        value = getattr(record, key)
        result[key] = float(value) if isinstance(value, Decimal) else value
    result.update({
        "id": record.id,
        "version": record.version,
        "is_deleted": record.is_deleted,
        "updated_at": record.updated_at.isoformat() if record.updated_at else "",
        "updated_by": record.updated_by,
    })
    return result


def _emit(db: Session, auth: AuthContext, record: Customer | WorkOrder, entity_type: str) -> None:
    db.add(SyncEvent(
        company_id=auth.company_id,
        entity_type=entity_type,
        entity_id=record.id,
        change_type="delete" if record.is_deleted else "upsert",
        payload=serialize_record(record),
    ))


def _check_expected(record, expected_version: int) -> None:
    if record and expected_version != record.version:
        raise Conflict(serialize_record(record))
    if not record and expected_version != 0:
        raise Conflict(None, "Record no longer exists")


def create_or_update_customer(db: Session, auth: AuthContext, customer_id: str, expected_version: int, payload: dict) -> Customer:
    payload = dict(payload)
    _normalize_bounded_text(payload, CUSTOMER_TEXT_LIMITS)
    record = db.scalar(select(Customer).where(Customer.id == customer_id).with_for_update())
    if record and record.company_id != auth.company_id:
        raise Forbidden("Record belongs to another company")
    _check_expected(record, expected_version)
    if not record:
        record = Customer(id=customer_id, company_id=auth.company_id)
        db.add(record)
    for key, value in payload.items():
        if key in CUSTOMER_FIELDS:
            if key == "tax_exempt":
                value = value is True or value == 1 or str(value).lower() in {"true", "yes"}
            setattr(record, key, value)
    record.is_deleted = False
    record.version = 1 if expected_version == 0 else record.version + 1
    record.updated_at = utcnow(); record.updated_by = auth.employee_id
    db.flush(); _emit(db, auth, record, "customer")
    return record


def delete_customer(db: Session, auth: AuthContext, customer_id: str, expected_version: int) -> Customer | None:
    record = db.scalar(select(Customer).where(Customer.id == customer_id).with_for_update())
    if record and record.company_id != auth.company_id:
        raise Forbidden("Record belongs to another company")
    _check_expected(record, expected_version)
    if not record:
        return None
    if auth.role not in {"supervisor", "admin"}:
        raise Forbidden("Supervisor permission is required to delete records")
    record.is_deleted = True; record.version += 1; record.updated_at = utcnow(); record.updated_by = auth.employee_id
    db.flush(); _emit(db, auth, record, "customer")
    return record


def _validate_date(value: str, label: str) -> None:
    if value:
        try: datetime.strptime(value, "%Y-%m-%d")
        except ValueError as exc: raise Invalid(f"{label} must use YYYY-MM-DD") from exc


def validate_order_payload(payload: dict) -> None:
    _normalize_bounded_text(payload, ORDER_TEXT_LIMITS)
    if "status" in payload and payload["status"] not in ORDER_STATUSES: raise Invalid("Invalid order status")
    if "priority" in payload and payload["priority"] not in PRIORITIES: raise Invalid("Invalid priority")
    if "discount_mode" in payload and payload["discount_mode"] not in DISCOUNT_MODES: raise Invalid("Invalid discount mode")
    if "received_date" in payload: _validate_date(payload.get("received_date") or "", "Received date")
    if "due_date" in payload: _validate_date(payload.get("due_date") or "", "Due date")
    for key in ("tax_rate", "deposit", "discount", "discount_percent"):
        if key not in payload:
            continue
        try:
            value = Decimal(str(payload.get(key) or 0))
        except (InvalidOperation, ValueError) as exc:
            raise Invalid(f"{key} must be numeric") from exc
        if not value.is_finite():
            raise Invalid(f"{key} must be a finite number")
        if value < 0:
            raise Invalid(f"{key} cannot be negative")
        if key == "discount_percent":
            maximum = MAX_DISCOUNT_PERCENT
        else:
            maximum = MAX_TAX_RATE if key == "tax_rate" else MAX_MONEY
        if value > maximum:
            raise Invalid(f"{key} exceeds the supported maximum")
    items = payload.get("items")
    if items is not None and not isinstance(items, list):
        raise Invalid("Order items must be a list")
    for item in items or []:
        if not isinstance(item, dict):
            raise Invalid("Each order item must be an object")
        item_name = item.get("item_name", "")
        if item_name is None:
            item_name = ""
        if not isinstance(item_name, str) or len(item_name) > 200:
            raise Invalid("Order item name must be text of 200 characters or fewer")
        try:
            quantity = Decimal(str(item.get("quantity", 0) or 0))
            unit_price = Decimal(str(item.get("unit_price", 0) or 0))
        except (InvalidOperation, ValueError) as exc:
            raise Invalid("Order item quantity and price must be numeric") from exc
        if not quantity.is_finite() or not unit_price.is_finite():
            raise Invalid("Order item quantity and price must be finite numbers")
        if quantity < 0 or unit_price < 0:
            raise Invalid("Order item quantity and price cannot be negative")
        if quantity > MAX_MONEY or unit_price > MAX_MONEY:
            raise Invalid("Order item quantity or price exceeds the supported maximum")


def validate_order_access(db: Session, auth: AuthContext, customer_id: str, location_id: str) -> None:
    if not customer_id or not location_id: raise Invalid("Order customer and location are required")
    customer = db.get(Customer, customer_id); location = db.get(Location, location_id)
    if not customer or customer.company_id != auth.company_id or customer.is_deleted: raise Invalid("Customer was not found")
    if not location or location.company_id != auth.company_id or not location.active: raise Invalid("Store location was not found")
    if auth.role != "admin" and auth.location_id != location_id: raise Forbidden("Employee is not signed in to this store")


def calculate_order(order: WorkOrder) -> None:
    cents = Decimal("0.01"); subtotal = Decimal(0); clean_items = []
    for item in order.items or []:
        clean = dict(item); quantity = Decimal(str(clean.get("quantity",0) or 0)); unit_price = Decimal(str(clean.get("unit_price",0) or 0))
        if quantity < 0 or unit_price < 0: raise Invalid("Order item quantity and price cannot be negative")
        clean["quantity"] = float(quantity); clean["unit_price"] = float(unit_price); clean_items.append(clean); subtotal += quantity * unit_price
    order.items = clean_items
    order.tax_rate = max(Decimal(str(order.tax_rate or 0)), Decimal(0))
    order.deposit = max(Decimal(str(order.deposit or 0)), Decimal(0))
    order.discount_mode = order.discount_mode if order.discount_mode in DISCOUNT_MODES else "amount"
    order.discount_percent = max(Decimal(str(order.discount_percent or 0)), Decimal(0))
    if order.discount_percent > MAX_DISCOUNT_PERCENT:
        raise Invalid("discount_percent exceeds the supported maximum")
    if order.discount_mode == "percent":
        order.discount = (subtotal * order.discount_percent / Decimal(100)).quantize(cents, rounding=ROUND_HALF_UP)
    else:
        order.discount = max(Decimal(str(order.discount or 0)), Decimal(0))
        order.discount_percent = Decimal(0)
    if not all(value.is_finite() for value in (subtotal, order.tax_rate, order.discount, order.discount_percent, order.deposit)):
        raise Invalid("Order monetary values must be finite numbers")
    if subtotal > MAX_MONEY:
        raise Invalid("Order total exceeds the supported maximum")
    taxable = max(subtotal - order.discount, Decimal(0))
    raw_total = taxable * (Decimal(1) + order.tax_rate / Decimal(100))
    if raw_total > MAX_MONEY:
        raise Invalid("Order total exceeds the supported maximum")
    order.subtotal = subtotal.quantize(cents, rounding=ROUND_HALF_UP)
    order.total = raw_total.quantize(cents, rounding=ROUND_HALF_UP)
    order.balance = max(order.total - order.deposit, Decimal(0)).quantize(cents, rounding=ROUND_HALF_UP)
    if any(value > MAX_MONEY for value in (order.subtotal, order.total, order.balance)):
        raise Invalid("Order total exceeds the supported maximum")


def create_or_update_order(db: Session, auth: AuthContext, order_id: str, expected_version: int, payload: dict) -> WorkOrder:
    payload = dict(payload)
    validate_order_payload(payload)
    record = db.scalar(select(WorkOrder).where(WorkOrder.id == order_id).with_for_update())
    if record and record.company_id != auth.company_id: raise Forbidden("Record belongs to another company")
    _check_expected(record, expected_version)
    effective_customer = payload.get("customer_id") or (record.customer_id if record else "")
    effective_location = payload.get("location_id") or (record.location_id if record else "")
    validate_order_access(db, auth, effective_customer, effective_location)
    location = db.get(Location, effective_location)
    if not record:
        record = WorkOrder(id=order_id, company_id=auth.company_id)
        if not payload.get("order_number"):
            payload = dict(payload)
            payload["order_number"] = f"WO-{location.store_number}-{datetime.now():%y%m%d}-{uuid.uuid4().hex[:5].upper()}"
        db.add(record)
    for key, value in payload.items():
        if key in ORDER_FIELDS: setattr(record, key, value)
    if not record.order_number:
        record.order_number = f"WO-{location.store_number}-{datetime.now():%y%m%d}-{uuid.uuid4().hex[:5].upper()}"
    record.is_deleted = False; calculate_order(record)
    record.version = 1 if expected_version == 0 else record.version + 1
    record.updated_at = utcnow(); record.updated_by = auth.employee_id
    db.flush(); _emit(db, auth, record, "order")
    return record


def delete_order(db: Session, auth: AuthContext, order_id: str, expected_version: int) -> WorkOrder | None:
    record = db.scalar(select(WorkOrder).where(WorkOrder.id == order_id).with_for_update())
    if record and record.company_id != auth.company_id: raise Forbidden("Record belongs to another company")
    _check_expected(record, expected_version)
    if not record: return None
    if auth.role not in {"supervisor","admin"}: raise Forbidden("Supervisor permission is required to delete records")
    validate_order_access(db, auth, record.customer_id, record.location_id)
    record.is_deleted = True; record.version += 1; record.updated_at = utcnow(); record.updated_by = auth.employee_id
    db.flush(); _emit(db, auth, record, "order")
    return record
