from __future__ import annotations

from datetime import UTC, date, datetime
from uuid import uuid4

from pydantic import ValidationError
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..database import Customer, CustomerIssue, Employee, IssueActivity, Location, WorkOrder, utcnow
from ..schemas.issues import CommunicationCreate, IssueCreate, IssueUpdate
from .common import Conflict, Forbidden, Invalid, NotFound


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


def get_issue(db, auth, issue_id):
    row = db.scalar(
        select(CustomerIssue)
        .where(CustomerIssue.id == issue_id, CustomerIssue.company_id == auth.company_id)
        .execution_options(populate_existing=True)
    )
    if row is None:
        raise NotFound("Customer issue not found")
    return row


def _write_scope(db, auth, location_id):
    location = db.get(Location, location_id)
    if not location or location.company_id != auth.company_id or not location.active:
        raise Forbidden("Store is unavailable")
    if auth.role != "admin" and location_id != auth.location_id:
        raise Forbidden("Switch to this store before changing its customer issues")


def _validate_links(db, auth, data):
    _write_scope(db, auth, data["location_id"])
    customer = db.get(Customer, data["customer_id"])
    if not customer or customer.company_id != auth.company_id or customer.is_deleted:
        raise Invalid("Choose an active customer in this company")
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
    order_id = data.get("work_order_id")
    if order_id:
        order = db.get(WorkOrder, order_id)
        if (
            not order
            or order.company_id != auth.company_id
            or order.is_deleted
            or order.customer_id != data["customer_id"]
            or order.location_id != data["location_id"]
        ):
            raise Invalid("Linked work order must match the customer and store")


def _activity(db, auth, row, summary, changed_fields=None, **extra):
    employee = db.get(Employee, auth.employee_id)
    if not employee or employee.company_id != auth.company_id:
        raise Forbidden("Employee is unavailable")
    entry = IssueActivity(
        id=str(uuid4()),
        company_id=auth.company_id,
        issue_id=row.id,
        activity_type="case change",
        occurred_at=utcnow(),
        author_employee_id=auth.employee_id,
        author_name=employee.name,
        summary=summary,
        changed_fields=changed_fields or {},
        **extra,
    )
    db.add(entry)
    return entry


def serialize_issue(db: Session, row: CustomerIssue) -> dict:
    result = {column.name: _json(getattr(row, column.name)) for column in row.__table__.columns}
    customer = db.get(Customer, row.customer_id)
    store = db.get(Location, row.location_id)
    employee = db.get(Employee, row.assigned_employee_id) if row.assigned_employee_id else None
    order = db.get(WorkOrder, row.work_order_id) if row.work_order_id else None
    result["customer"] = (
        {
            key: getattr(customer, key)
            for key in ["id", "company", "first_name", "last_name", "phone", "email"]
        }
        if customer and customer.company_id == row.company_id
        else None
    )
    result["store"] = (
        {key: getattr(store, key) for key in ["id", "name", "store_number", "timezone"]}
        if store and store.company_id == row.company_id
        else None
    )
    result["assignee"] = (
        {"id": employee.id, "name": employee.name, "active": employee.active}
        if employee and employee.company_id == row.company_id
        else None
    )
    result["order_number"] = (
        order.order_number if order and order.company_id == row.company_id else None
    )
    return result


def serialize_activity(row: IssueActivity) -> dict:
    return {
        column.name: _json(getattr(row, column.name))
        for column in row.__table__.columns
        if column.name not in {"company_id", "request_payload"}
    }


def create_issue(db: Session, auth, data: dict) -> CustomerIssue:
    values = _validate(IssueCreate, data).model_dump()
    _validate_links(db, auth, values)
    issue_id = str(uuid4())
    row = CustomerIssue(
        id=issue_id,
        company_id=auth.company_id,
        reference="CI-" + issue_id.replace("-", ""),
        created_by=auth.employee_id,
        updated_by=auth.employee_id,
        **values,
    )
    db.add(row)
    db.flush()
    _activity(db, auth, row, "Case opened", {"status": {"from": None, "to": "Open"}})
    db.flush()
    return row


def update_issue(db: Session, auth, issue_id: str, version: int, data: dict) -> CustomerIssue:
    values = _validate(IssueUpdate, dict(data, version=version)).model_dump(exclude_unset=True)
    values.pop("version")
    reason = values.pop("reopen_reason", "")
    row = get_issue(db, auth, issue_id)
    _write_scope(db, auth, row.location_id)
    if row.version != version:
        raise Conflict(serialize_issue(db, row), "This case changed on another device")
    merged = {column.name: getattr(row, column.name) for column in row.__table__.columns} | values
    _validate_links(db, auth, merged)
    if row.status == "Resolved" and merged["status"] != "Resolved" and not reason:
        raise Invalid("A reason is required to reopen the case")
    if merged["status"] == "Resolved" and not merged["resolution_summary"].strip():
        raise Invalid("A resolution summary is required")
    changed = {
        key: {"from": _json(getattr(row, key)), "to": _json(value)}
        for key, value in values.items()
        if getattr(row, key) != value
    }
    if not changed:
        return row
    if merged["status"] == "Resolved" and row.status != "Resolved":
        values["resolved_at"] = utcnow()
    elif row.status == "Resolved" and merged["status"] != "Resolved":
        values["resolved_at"] = None
    result = db.execute(
        update(CustomerIssue)
        .where(
            CustomerIssue.id == issue_id,
            CustomerIssue.company_id == auth.company_id,
            CustomerIssue.version == version,
        )
        .values(**values, version=version + 1, updated_at=utcnow(), updated_by=auth.employee_id)
        .execution_options(synchronize_session=False)
    )
    if result.rowcount != 1:
        raise Conflict(
            serialize_issue(db, get_issue(db, auth, issue_id)),
            "This case changed on another device",
        )
    db.refresh(row)
    _activity(db, auth, row, "Case reopened: " + reason if reason else "Case updated", changed)
    db.flush()
    return row


def append_communication(db: Session, auth, issue_id: str, data: dict) -> IssueActivity:
    body = _validate(CommunicationCreate, data)
    request = body.model_dump(mode="json", exclude_unset=True)
    request["occurred_at"] = body.occurred_at.astimezone(UTC).isoformat()
    operation_id = str(body.operation_id)
    row = get_issue(db, auth, issue_id)
    _write_scope(db, auth, row.location_id)

    def existing():
        entry = db.scalar(
            select(IssueActivity).where(
                IssueActivity.company_id == auth.company_id,
                IssueActivity.operation_id == operation_id,
            )
        )
        if entry and (
            entry.issue_id != issue_id
            or entry.request_payload != request
            or entry.author_employee_id != auth.employee_id
        ):
            raise Conflict(
                message="This communication operation ID was already used for a different request"
            )
        return entry

    prior = existing()
    if prior:
        return prior
    try:
        with db.begin_nested():
            followup = {
                key: getattr(body, key)
                for key in ("next_action", "follow_up_date")
                if key in body.model_fields_set
            }
            if followup:
                row = update_issue(db, auth, issue_id, body.version, followup)
            entry = _activity(
                db, auth, row, body.summary, operation_id=operation_id, request_payload=request
            )
            entry.activity_type = "communication"
            entry.channel = body.channel
            entry.occurred_at = body.occurred_at.astimezone(UTC)
            db.flush()
        return entry
    except IntegrityError:
        prior = existing()
        if prior:
            return prior
        raise
