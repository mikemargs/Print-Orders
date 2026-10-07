from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..database import Employee, Location, StoreTask, utcnow
from ..schemas.tasks import TaskCreate, TaskUpdate
from ..services.common import Conflict, Forbidden, Invalid, NotFound
from ..services.tasks import create_task, get_task, serialize_task, update_task
from ..web_sessions import get_web_db, web_auth_context, web_mutation_context

router = APIRouter(prefix="/api/tasks", tags=["tasks"])


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
    location_id: str = "",
    status: str = "",
    assigned_employee_id: str = "",
    open_only: bool = False,
    limit: int = Query(100, ge=1, le=250),
    offset: int = Query(0, ge=0),
    auth=Depends(web_auth_context),
    db: Session = Depends(get_web_db),
):
    q = select(StoreTask).where(StoreTask.company_id == auth.company_id)
    if location_id:
        q = q.where(StoreTask.location_id == location_id)
    if status:
        q = q.where(StoreTask.status == status)
    if assigned_employee_id:
        q = q.where(StoreTask.assigned_employee_id == assigned_employee_id)
    if open_only:
        q = q.where(StoreTask.status.notin_(("Completed", "Cancelled")))
    total = db.scalar(select(func.count()).select_from(q.subquery()))
    rows = db.scalars(
        q.order_by(StoreTask.due_date.is_(None), StoreTask.due_date, StoreTask.updated_at.desc())
        .offset(offset)
        .limit(limit)
    ).all()
    return {"tasks": [serialize_task(db, row) for row in rows], "total": total}


@router.get("/summary")
def summary(auth=Depends(web_auth_context), db: Session = Depends(get_web_db)):
    rows = db.scalars(
        select(StoreTask).where(
            StoreTask.company_id == auth.company_id,
            StoreTask.status.notin_(("Completed", "Cancelled")),
        )
    ).all()
    locations = {
        row.id: row
        for row in db.scalars(select(Location).where(Location.company_id == auth.company_id)).all()
    }
    now = utcnow()
    result = {"open": len(rows), "overdue": 0, "due_today": 0, "assigned_to_me": 0}
    for row in rows:
        location = locations.get(row.location_id)
        today = now.astimezone(ZoneInfo(location.timezone if location else "America/New_York")).date()
        if row.due_date and row.due_date < today:
            result["overdue"] += 1
        if row.due_date == today:
            result["due_today"] += 1
        if row.assigned_employee_id == auth.employee_id:
            result["assigned_to_me"] += 1
    return result


@router.get("/options")
def options(auth=Depends(web_auth_context), db: Session = Depends(get_web_db)):
    employees = db.scalars(
        select(Employee)
        .where(Employee.company_id == auth.company_id, Employee.active.is_(True))
        .order_by(Employee.name)
    ).all()
    return {"employees": [{"id": row.id, "name": row.name, "role": row.role, "location_ids": row.location_ids or []} for row in employees]}


@router.post("", status_code=201)
def new_task(body: TaskCreate, auth=Depends(web_mutation_context), db: Session = Depends(get_web_db)):
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
def patch_task(task_id: str, body: TaskUpdate, auth=Depends(web_mutation_context), db: Session = Depends(get_web_db)):
    data = body.model_dump(exclude_unset=True)
    version = data.pop("version")
    try:
        row = update_task(db, auth, task_id, version, data)
        db.commit()
        return serialize_task(db, row)
    except Exception as exc:
        db.rollback()
        return error_response(exc)
