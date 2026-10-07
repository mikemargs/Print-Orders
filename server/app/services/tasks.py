from datetime import UTC, date, datetime
from uuid import uuid4

from pydantic import ValidationError
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from ..database import Customer, CustomerIssue, Employee, Location, StoreTask, WorkOrder, utcnow
from ..schemas.tasks import TaskCreate, TaskUpdate
from .common import Conflict, Forbidden, Invalid, NotFound


def _json(value):
    if isinstance(value, datetime):
        return (value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)).isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return value


def _validate(schema, data):
    try:
        return schema(**data)
    except ValidationError as exc:
        raise Invalid(str(exc)) from exc


def get_task(db: Session, auth, task_id: str):
    row = db.scalar(
        select(StoreTask).where(StoreTask.id == task_id, StoreTask.company_id == auth.company_id)
    )
    if row is None:
        raise NotFound("Task not found")
    return row


def _write_scope(db: Session, auth, location_id: str):
    location = db.get(Location, location_id)
    if not location or location.company_id != auth.company_id or not location.active:
        raise Forbidden("Store is unavailable")
    if auth.role != "admin" and location_id != auth.location_id:
        raise Forbidden("Switch to this store before changing its tasks")


def _validate_links(db: Session, auth, data: dict):
    _write_scope(db, auth, data["location_id"])
    employee_id = data.get("assigned_employee_id")
    if employee_id:
        employee = db.get(Employee, employee_id)
        if not employee or employee.company_id != auth.company_id or not employee.active:
            raise Invalid("Choose an active employee in this company")
        if employee.role != "admin" and employee.location_ids and data["location_id"] not in employee.location_ids:
            raise Invalid("Assigned employee is not eligible for this store")
    customer_id = data.get("customer_id")
    if customer_id:
        customer = db.get(Customer, customer_id)
        if not customer or customer.company_id != auth.company_id or customer.is_deleted:
            raise Invalid("Linked customer is unavailable")
    work_order_id = data.get("work_order_id")
    if work_order_id:
        order = db.get(WorkOrder, work_order_id)
        if not order or order.company_id != auth.company_id or order.is_deleted or order.location_id != data["location_id"]:
            raise Invalid("Linked work order must belong to this store")
        if customer_id and order.customer_id != customer_id:
            raise Invalid("Linked work order must match the linked customer")
    issue_id = data.get("issue_id")
    if issue_id:
        issue = db.get(CustomerIssue, issue_id)
        if not issue or issue.company_id != auth.company_id or issue.location_id != data["location_id"]:
            raise Invalid("Linked customer issue must belong to this store")
        if customer_id and issue.customer_id != customer_id:
            raise Invalid("Linked customer issue must match the linked customer")


def serialize_task(db: Session, row: StoreTask) -> dict:
    result = {column.name: _json(getattr(row, column.name)) for column in row.__table__.columns}
    location = db.get(Location, row.location_id)
    employee = db.get(Employee, row.assigned_employee_id) if row.assigned_employee_id else None
    customer = db.get(Customer, row.customer_id) if row.customer_id else None
    result["store"] = {"id": location.id, "name": location.name, "store_number": location.store_number} if location and location.company_id == row.company_id else None
    result["assignee"] = {"id": employee.id, "name": employee.name} if employee and employee.company_id == row.company_id else None
    result["customer"] = {"id": customer.id, "company": customer.company, "first_name": customer.first_name, "last_name": customer.last_name} if customer and customer.company_id == row.company_id else None
    return result


def create_task(db: Session, auth, data: dict):
    values = _validate(TaskCreate, data).model_dump()
    _validate_links(db, auth, values)
    now = utcnow()
    row = StoreTask(
        id=str(uuid4()),
        company_id=auth.company_id,
        created_by=auth.employee_id,
        updated_by=auth.employee_id,
        created_at=now,
        updated_at=now,
        completed_at=now if values["status"] == "Completed" else None,
        **values,
    )
    db.add(row)
    db.flush()
    return row


def update_task(db: Session, auth, task_id: str, version: int, data: dict):
    values = _validate(TaskUpdate, dict(data, version=version)).model_dump(exclude_unset=True)
    values.pop("version")
    row = get_task(db, auth, task_id)
    _write_scope(db, auth, row.location_id)
    if row.version != version:
        raise Conflict(serialize_task(db, row), "This task changed on another device")
    merged = {column.name: getattr(row, column.name) for column in row.__table__.columns} | values
    _validate_links(db, auth, merged)
    if not values:
        return row
    old_completed = row.status == "Completed"
    new_completed = merged["status"] == "Completed"
    if old_completed != new_completed:
        values["completed_at"] = utcnow() if new_completed else None
    result = db.execute(
        update(StoreTask)
        .where(StoreTask.id == task_id, StoreTask.company_id == auth.company_id, StoreTask.version == version)
        .values(**values, version=version + 1, updated_at=utcnow(), updated_by=auth.employee_id)
        .execution_options(synchronize_session=False)
    )
    if result.rowcount != 1:
        raise Conflict(serialize_task(db, get_task(db, auth, task_id)), "This task changed on another device")
    db.refresh(row)
    return row
