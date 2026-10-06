from __future__ import annotations

from datetime import UTC, date, datetime
from uuid import uuid4

from pydantic import ValidationError
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from ..database import (
    Customer,
    CustomerIssue,
    Employee,
    Location,
    OperationsTask,
    WorkOrder,
    utcnow,
)
from ..schemas.tasks import TaskCreate, TaskUpdate
from .common import Conflict, Forbidden, Invalid, NotFound

CLOSED_STATUSES = {"Completed", "Cancelled"}


def _json(value):
    if isinstance(value, datetime):
        return (
            value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)
        ).isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return value


def _validate(schema, data):
    try:
        return schema(**data)
    except ValidationError as exc:
        raise Invalid(str(exc)) from exc


def get_task(db: Session, auth, task_id: str) -> OperationsTask:
    row = db.scalar(
        select(OperationsTask)
        .where(OperationsTask.id == task_id, OperationsTask.company_id == auth.company_id)
        .execution_options(populate_existing=True)
    )
    if row is None:
        raise NotFound("Task not found")
    return row


def _write_scope(db: Session, auth, location_id: str) -> Location:
    location = db.get(Location, location_id)
    if not location or location.company_id != auth.company_id or not location.active:
        raise Forbidden("Store is unavailable")
    if auth.role != "admin" and location_id != auth.location_id:
        raise Forbidden("Switch to this store before changing its tasks")
    return location


def _validate_links(db: Session, auth, data: dict) -> None:
    _write_scope(db, auth, data["location_id"])

    employee_id = data.get("assigned_employee_id")
    if employee_id:
        employee = db.get(Employee, employee_id)
        if not employee or employee.company_id != auth.company_id or not employee.active:
            raise Invalid("Choose an active employee in this company")
        if (
            employee.role != "admin"
            and employee.location_ids
            and data["location_id"] not in employee.location_ids
        ):
            raise Invalid("Assigned employee is not eligible for this store")

    customer_id = data.get("customer_id")
    if customer_id:
        customer = db.get(Customer, customer_id)
        if not customer or customer.company_id != auth.company_id or customer.is_deleted:
            raise Invalid("Choose an active customer in this company")

    order_id = data.get("work_order_id")
    if order_id:
        order = db.get(WorkOrder, order_id)
        if not order or order.company_id != auth.company_id or order.is_deleted:
            raise Invalid("Choose an active work order in this company")
        if order.location_id != data["location_id"]:
            raise Invalid("Linked work order must belong to the task store")
        if customer_id and order.customer_id != customer_id:
            raise Invalid("Linked work order must match the selected customer")

    issue_id = data.get("issue_id")
    if issue_id:
        issue = db.get(CustomerIssue, issue_id)
        if not issue or issue.company_id != auth.company_id:
            raise Invalid("Choose a customer issue in this company")
        if issue.location_id != data["location_id"]:
            raise Invalid("Linked customer issue must belong to the task store")
        if customer_id and issue.customer_id != customer_id:
            raise Invalid("Linked customer issue must match the selected customer")


def serialize_task(db: Session, row: OperationsTask) -> dict:
    result = {column.name: _json(getattr(row, column.name)) for column in row.__table__.columns}
    store = db.get(Location, row.location_id)
    employee = db.get(Employee, row.assigned_employee_id) if row.assigned_employee_id else None
    customer = db.get(Customer, row.customer_id) if row.customer_id else None
    order = db.get(WorkOrder, row.work_order_id) if row.work_order_id else None
    issue = db.get(CustomerIssue, row.issue_id) if row.issue_id else None

    result["store"] = (
        {"id": store.id, "name": store.name, "store_number": store.store_number, "timezone": store.timezone}
        if store and store.company_id == row.company_id
        else None
    )
    result["assignee"] = (
        {"id": employee.id, "name": employee.name, "active": employee.active}
        if employee and employee.company_id == row.company_id
        else None
    )
    result["customer"] = (
        {
            "id": customer.id,
            "company": customer.company,
            "first_name": customer.first_name,
            "last_name": customer.last_name,
        }
        if customer and customer.company_id == row.company_id
        else None
    )
    result["order"] = (
        {"id": order.id, "order_number": order.order_number, "description": order.description}
        if order and order.company_id == row.company_id
        else None
    )
    result["issue"] = (
        {"id": issue.id, "reference": issue.reference, "title": issue.title}
        if issue and issue.company_id == row.company_id
        else None
    )
    return result


def create_task(db: Session, auth, data: dict) -> OperationsTask:
    values = _validate(TaskCreate, data).model_dump()
    _validate_links(db, auth, values)
    row = OperationsTask(
        id=str(uuid4()),
        company_id=auth.company_id,
        created_by=auth.employee_id,
        updated_by=auth.employee_id,
        **values,
    )
    if row.status == "Completed":
        row.completed_at = utcnow()
    db.add(row)
    db.flush()
    return row


def update_task(
    db: Session, auth, task_id: str, version: int, data: dict
) -> OperationsTask:
    values = _validate(TaskUpdate, dict(data, version=version)).model_dump(exclude_unset=True)
    values.pop("version")
    row = get_task(db, auth, task_id)
    _write_scope(db, auth, row.location_id)
    if row.version != version:
        raise Conflict(serialize_task(db, row), "This task changed on another device")

    merged = {column.name: getattr(row, column.name) for column in row.__table__.columns} | values
    _validate_links(db, auth, merged)

    changed = {key: value for key, value in values.items() if getattr(row, key) != value}
    if not changed:
        return row

    old_status = row.status
    new_status = merged["status"]
    if new_status == "Completed" and old_status != "Completed":
        values["completed_at"] = utcnow()
    elif old_status == "Completed" and new_status != "Completed":
        values["completed_at"] = None

    result = db.execute(
        update(OperationsTask)
        .where(
            OperationsTask.id == task_id,
            OperationsTask.company_id == auth.company_id,
            OperationsTask.version == version,
        )
        .values(
            **values,
            version=version + 1,
            updated_at=utcnow(),
            updated_by=auth.employee_id,
        )
        .execution_options(synchronize_session=False)
    )
    if result.rowcount != 1:
        raise Conflict(
            serialize_task(db, get_task(db, auth, task_id)),
            "This task changed on another device",
        )
    db.refresh(row)
    return row
