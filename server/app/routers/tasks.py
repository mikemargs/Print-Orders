from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from ..database import Employee, Location, OperationsTask, utcnow
from ..schemas.tasks import TaskCreate, TaskUpdate
from ..services.common import Conflict, Forbidden, Invalid, NotFound
from ..services.tasks import CLOSED_STATUSES, create_task, get_task, serialize_task, update_task
from ..web_sessions import get_web_db, web_auth_context, web_mutation_context

router = APIRouter(prefix="/api/tasks", tags=["operations-tasks"])


def filters(
    search: str = "",
    location_id: str = "",
    status: str = "",
    priority: str = "",
    assigned_employee_id: str = "",
    customer_id: str = "",
    open_only: bool = False,
):
    return {
        "search": search,
        "location_id": location_id,
        "status": status,
        "priority": priority,
        "assigned_employee_id": assigned_employee_id,
        "customer_id": customer_id,
        "open_only": open_only,
    }


def task_query(auth, options):
    q = select(OperationsTask).where(OperationsTask.company_id == auth.company_id)
    for name in ("location_id", "status", "priority", "assigned_employee_id", "customer_id"):
        if options[name]:
            q = q.where(getattr(OperationsTask, name) == options[name])
    if options["open_only"]:
        q = q.where(OperationsTask.status.not_in(CLOSED_STATUSES))
    if options["search"].strip():
        needle = (
            "%"
            + options["search"].strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            + "%"
        )
        q = q.where(
            or_(
                OperationsTask.title.ilike(needle, escape="\\"),
                OperationsTask.description.ilike(needle, escape="\\"),
            )
        )
    return q


def error_response(exc):
    if isinstance(exc, Conflict):
        return JSONResponse(status_code=409, content={"detail": str(exc), "current": exc.current})
    if isinstance(exc, NotFound):
        raise HTTPException(404, str(exc))
    if isinstance(exc, Forbidden):
        raise HTTPException(403, str(exc))
    if isinstance(exc, Invalid):
        raise HTTPException(400, str(exc))
    raise exc


@router.get("")
def list_tasks(
    options=Depends(filters),
    limit: int = Query(50, ge=1, le=250),
    offset: int = Query(0, ge=0),
    auth=Depends(web_auth_context),
    db: Session = Depends(get_web_db),
):
    q = task_query(auth, options)
    total = db.scalar(select(func.count()).select_from(q.subquery()))
    rows = db.scalars(
        q.order_by(
            OperationsTask.status.in_(CLOSED_STATUSES),
            OperationsTask.due_date.is_(None),
            OperationsTask.due_date,
            OperationsTask.updated_at.desc(),
            OperationsTask.id,
        )
        .offset(offset)
        .limit(limit)
    ).all()
    return {"tasks": [serialize_task(db, row) for row in rows], "total": total}


@router.get("/summary")
def summary(
    options=Depends(filters),
    auth=Depends(web_auth_context),
    db: Session = Depends(get_web_db),
):
    q = task_query(auth, options).where(OperationsTask.status.not_in(CLOSED_STATUSES))
    totals = {"open": 0, "overdue": 0, "due_today": 0, "assigned_to_me": 0}
    rows = db.execute(
        q.with_only_columns(
            OperationsTask.location_id,
            OperationsTask.due_date,
            OperationsTask.assigned_employee_id,
            func.count(),
        ).group_by(
            OperationsTask.location_id,
            OperationsTask.due_date,
            OperationsTask.assigned_employee_id,
        )
    ).all()
    now = utcnow()
    locations = {
        location.id: location
        for location in db.scalars(
            select(Location).where(Location.company_id == auth.company_id)
        ).all()
    }
    for location_id, due, assignee, count in rows:
        location = locations.get(location_id)
        today = now.astimezone(
            ZoneInfo(location.timezone if location else "America/New_York")
        ).date()
        totals["open"] += count
        if due and due < today:
            totals["overdue"] += count
        if due and due == today:
            totals["due_today"] += count
        if assignee == auth.employee_id:
            totals["assigned_to_me"] += count
    return totals


@router.get("/options")
def options(auth=Depends(web_auth_context), db: Session = Depends(get_web_db)):
    employees = db.scalars(
        select(Employee)
        .where(Employee.company_id == auth.company_id, Employee.active.is_(True))
        .order_by(Employee.name)
    ).all()
    return {
        "employees": [
            {
                "id": employee.id,
                "name": employee.name,
                "role": employee.role,
                "location_ids": employee.location_ids or [],
                "active": employee.active,
            }
            for employee in employees
        ]
    }


@router.post("", status_code=201)
def new_task(
    body: TaskCreate,
    auth=Depends(web_mutation_context),
    db: Session = Depends(get_web_db),
):
    try:
        row = create_task(db, auth, body.model_dump())
        db.commit()
        return serialize_task(db, row)
    except Exception as exc:
        db.rollback()
        return error_response(exc)


@router.get("/{task_id}")
def detail(task_id: str, auth=Depends(web_auth_context), db: Session = Depends(get_web_db)):
    try:
        return serialize_task(db, get_task(db, auth, task_id))
    except Exception as exc:
        return error_response(exc)


@router.patch("/{task_id}")
def patch_task(
    task_id: str,
    body: TaskUpdate,
    auth=Depends(web_mutation_context),
    db: Session = Depends(get_web_db),
):
    data = body.model_dump(exclude_unset=True)
    version = data.pop("version")
    try:
        row = update_task(db, auth, task_id, version, data)
        db.commit()
        return serialize_task(db, row)
    except Exception as exc:
        db.rollback()
        return error_response(exc)
