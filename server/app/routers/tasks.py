from uuid import uuid4
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_, select, update
from sqlalchemy.orm import Session

from ..database import (
    Customer,
    CustomerIssue,
    Employee,
    Location,
    OperationalTask,
    WorkOrder,
    utcnow,
)
from ..schemas.tasks import TaskCreate, TaskUpdate
from ..web_sessions import get_web_db, web_auth_context, web_mutation_context

router = APIRouter(prefix="/api/tasks", tags=["tasks"])


def _serialize(db: Session, row: OperationalTask) -> dict:
    store = db.get(Location, row.location_id)
    employee = db.get(Employee, row.assigned_employee_id) if row.assigned_employee_id else None
    customer = db.get(Customer, row.customer_id) if row.customer_id else None
    order = db.get(WorkOrder, row.work_order_id) if row.work_order_id else None
    issue = db.get(CustomerIssue, row.customer_issue_id) if row.customer_issue_id else None
    return {
        "id": row.id,
        "location_id": row.location_id,
        "title": row.title,
        "description": row.description,
        "status": row.status,
        "priority": row.priority,
        "due_date": row.due_date.isoformat() if row.due_date else None,
        "assigned_employee_id": row.assigned_employee_id,
        "customer_id": row.customer_id,
        "work_order_id": row.work_order_id,
        "customer_issue_id": row.customer_issue_id,
        "version": row.version,
        "created_by": row.created_by,
        "updated_by": row.updated_by,
        "created_at": row.created_at.isoformat(),
        "updated_at": row.updated_at.isoformat(),
        "completed_at": row.completed_at.isoformat() if row.completed_at else None,
        "store": {"id": store.id, "name": store.name, "store_number": store.store_number} if store else None,
        "assignee": {"id": employee.id, "name": employee.name} if employee else None,
        "customer": (
            {"id": customer.id, "company": customer.company, "first_name": customer.first_name, "last_name": customer.last_name}
            if customer else None
        ),
        "order_number": order.order_number if order else None,
        "issue_reference": issue.reference if issue else None,
    }


def _write_scope(db: Session, auth, location_id: str):
    location = db.get(Location, location_id)
    if not location or location.company_id != auth.company_id or not location.active:
        raise HTTPException(400, "Choose an active store")
    if auth.role != "admin" and location_id != auth.location_id:
        raise HTTPException(403, "Switch to this store before changing its tasks")
    return location


def _validate_links(db: Session, auth, body):
    _write_scope(db, auth, body.location_id)
    if body.assigned_employee_id:
        employee = db.get(Employee, body.assigned_employee_id)
        if not employee or employee.company_id != auth.company_id or not employee.active:
            raise HTTPException(400, "Choose an active employee")
        if employee.role != "admin" and employee.location_ids and body.location_id not in employee.location_ids:
            raise HTTPException(400, "Assigned employee is not eligible for this store")
    if body.customer_id:
        customer = db.get(Customer, body.customer_id)
        if not customer or customer.company_id != auth.company_id or customer.is_deleted:
            raise HTTPException(400, "Choose an active customer")
    if body.work_order_id:
        order = db.get(WorkOrder, body.work_order_id)
        if not order or order.company_id != auth.company_id or order.is_deleted or order.location_id != body.location_id:
            raise HTTPException(400, "Linked work order must belong to this store")
        if body.customer_id and order.customer_id != body.customer_id:
            raise HTTPException(400, "Linked work order must match the customer")
    if body.customer_issue_id:
        issue = db.get(CustomerIssue, body.customer_issue_id)
        if not issue or issue.company_id != auth.company_id or issue.location_id != body.location_id:
            raise HTTPException(400, "Linked customer issue must belong to this store")
        if body.customer_id and issue.customer_id != body.customer_id:
            raise HTTPException(400, "Linked customer issue must match the customer")


@router.get("")
def list_tasks(
    search: str = "",
    location_id: str = "",
    status: str = "",
    priority: str = "",
    assigned_employee_id: str = "",
    open_only: bool = True,
    limit: int = Query(100, ge=1, le=250),
    offset: int = Query(0, ge=0),
    auth=Depends(web_auth_context),
    db: Session = Depends(get_web_db),
):
    q = select(OperationalTask).where(OperationalTask.company_id == auth.company_id)
    if location_id:
        q = q.where(OperationalTask.location_id == location_id)
    if status:
        q = q.where(OperationalTask.status == status)
    elif open_only:
        q = q.where(OperationalTask.status.notin_(["Completed", "Cancelled"]))
    if priority:
        q = q.where(OperationalTask.priority == priority)
    if assigned_employee_id:
        q = q.where(OperationalTask.assigned_employee_id == assigned_employee_id)
    if search.strip():
        needle = f"%{search.strip()}%"
        q = q.where(or_(OperationalTask.title.ilike(needle), OperationalTask.description.ilike(needle)))
    total = db.scalar(select(func.count()).select_from(q.subquery()))
    rows = db.scalars(
        q.order_by(
            OperationalTask.due_date.is_(None),
            OperationalTask.due_date,
            OperationalTask.priority.desc(),
            OperationalTask.updated_at.desc(),
        ).offset(offset).limit(limit)
    ).all()
    return {"tasks": [_serialize(db, row) for row in rows], "total": total}


@router.get("/summary")
def summary(auth=Depends(web_auth_context), db: Session = Depends(get_web_db)):
    rows = db.scalars(
        select(OperationalTask).where(
            OperationalTask.company_id == auth.company_id,
            OperationalTask.status.notin_(["Completed", "Cancelled"]),
        )
    ).all()
    locations = {x.id: x for x in db.scalars(select(Location).where(Location.company_id == auth.company_id)).all()}
    totals = {"open": len(rows), "overdue": 0, "high_priority": 0, "assigned_to_me": 0}
    now = utcnow()
    for row in rows:
        location = locations.get(row.location_id)
        today = now.astimezone(ZoneInfo(location.timezone if location else "America/New_York")).date()
        if row.due_date and row.due_date < today:
            totals["overdue"] += 1
        if row.priority in {"High", "Urgent"}:
            totals["high_priority"] += 1
        if row.assigned_employee_id == auth.employee_id:
            totals["assigned_to_me"] += 1
    return totals


@router.get("/options")
def options(auth=Depends(web_auth_context), db: Session = Depends(get_web_db)):
    employees = db.scalars(
        select(Employee).where(Employee.company_id == auth.company_id, Employee.active.is_(True)).order_by(Employee.name)
    ).all()
    customers = db.scalars(
        select(Customer).where(Customer.company_id == auth.company_id, Customer.is_deleted.is_(False)).order_by(Customer.company, Customer.last_name).limit(500)
    ).all()
    return {
        "employees": [{"id": x.id, "name": x.name, "location_ids": x.location_ids, "role": x.role} for x in employees],
        "customers": [{"id": x.id, "company": x.company, "first_name": x.first_name, "last_name": x.last_name} for x in customers],
    }


@router.post("", status_code=201)
def create_task(body: TaskCreate, auth=Depends(web_mutation_context), db: Session = Depends(get_web_db)):
    _validate_links(db, auth, body)
    row = OperationalTask(
        id=str(uuid4()),
        company_id=auth.company_id,
        created_by=auth.employee_id,
        updated_by=auth.employee_id,
        **body.model_dump(),
    )
    if row.status == "Completed":
        row.completed_at = utcnow()
    db.add(row)
    db.commit()
    return _serialize(db, row)


@router.patch("/{task_id}")
def update_task(task_id: str, body: TaskUpdate, auth=Depends(web_mutation_context), db: Session = Depends(get_web_db)):
    row = db.scalar(select(OperationalTask).where(OperationalTask.id == task_id, OperationalTask.company_id == auth.company_id))
    if not row:
        raise HTTPException(404, "Task not found")
    _write_scope(db, auth, row.location_id)
    if row.version != body.version:
        raise HTTPException(409, "This task changed on another device")
    _validate_links(db, auth, body)
    values = body.model_dump()
    values.pop("version")
    completed_at = row.completed_at
    if values["status"] == "Completed" and row.status != "Completed":
        completed_at = utcnow()
    elif row.status == "Completed" and values["status"] != "Completed":
        completed_at = None
    result = db.execute(
        update(OperationalTask)
        .where(OperationalTask.id == task_id, OperationalTask.company_id == auth.company_id, OperationalTask.version == body.version)
        .values(**values, version=body.version + 1, updated_by=auth.employee_id, updated_at=utcnow(), completed_at=completed_at)
        .execution_options(synchronize_session=False)
    )
    if result.rowcount != 1:
        db.rollback()
        raise HTTPException(409, "This task changed on another device")
    db.commit()
    db.refresh(row)
    return _serialize(db, row)
