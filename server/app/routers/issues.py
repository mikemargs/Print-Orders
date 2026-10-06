from zoneinfo import ZoneInfo

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from fastapi.responses import JSONResponse
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from ..database import Customer, CustomerIssue, Employee, IssueActivity, Location, utcnow
from ..schemas.issues import CommunicationCreate, IssueCreate, IssueUpdate
from ..services.common import Conflict, Forbidden, Invalid, NotFound
from ..services.issues import (
    append_communication,
    create_issue,
    get_issue,
    serialize_activity,
    serialize_issue,
    update_issue,
)
from ..services.notifications import queue_customer_issue_created
from ..web_sessions import get_web_db, web_auth_context, web_mutation_context

router = APIRouter(prefix="/api/issues", tags=["customer-issues"])


def filters(
    search: str = "",
    location_id: str = "",
    status: str = "",
    priority: str = "",
    category: str = "",
    assigned_employee_id: str = "",
    customer_id: str = "",
    unresolved_only: bool = False,
):
    return {
        "search": search,
        "location_id": location_id,
        "status": status,
        "priority": priority,
        "category": category,
        "assigned_employee_id": assigned_employee_id,
        "customer_id": customer_id,
        "unresolved_only": unresolved_only,
    }


def issue_query(auth, options):
    q = select(CustomerIssue).where(CustomerIssue.company_id == auth.company_id)
    for name in (
        "location_id",
        "status",
        "priority",
        "category",
        "assigned_employee_id",
        "customer_id",
    ):
        if options[name]:
            q = q.where(getattr(CustomerIssue, name) == options[name])
    if options["unresolved_only"]:
        q = q.where(CustomerIssue.status != "Resolved")
    if options["search"].strip():
        needle = (
            "%"
            + options["search"]
            .strip()
            .replace("\\", "\\\\")
            .replace("%", "\\%")
            .replace("_", "\\_")
            + "%"
        )
        q = q.join(
            Customer,
            (Customer.id == CustomerIssue.customer_id) & (Customer.company_id == auth.company_id),
        ).where(
            or_(
                *(
                    column.ilike(needle, escape="\\")
                    for column in (
                        CustomerIssue.title,
                        CustomerIssue.reference,
                        Customer.first_name,
                        Customer.last_name,
                        Customer.company,
                    )
                )
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
def list_issues(
    options=Depends(filters),
    limit: int = Query(50, ge=1, le=250),
    offset: int = Query(0, ge=0),
    auth=Depends(web_auth_context),
    db: Session = Depends(get_web_db),
):
    q = issue_query(auth, options)
    total = db.scalar(select(func.count()).select_from(q.subquery()))
    rows = db.scalars(
        q.order_by(
            CustomerIssue.follow_up_date.is_(None),
            CustomerIssue.follow_up_date,
            CustomerIssue.updated_at.desc(),
            CustomerIssue.id,
        )
        .offset(offset)
        .limit(limit)
    ).all()
    return {"issues": [serialize_issue(db, row) for row in rows], "total": total}


@router.get("/summary")
def summary(
    options=Depends(filters), auth=Depends(web_auth_context), db: Session = Depends(get_web_db)
):
    q = issue_query(auth, options).where(CustomerIssue.status != "Resolved")
    totals = {"open": 0, "overdue": 0, "high_priority": 0, "assigned_to_me": 0}
    rows = db.execute(
        q.with_only_columns(
            CustomerIssue.location_id,
            CustomerIssue.follow_up_date,
            CustomerIssue.priority,
            CustomerIssue.assigned_employee_id,
            func.count(),
        ).group_by(
            CustomerIssue.location_id,
            CustomerIssue.follow_up_date,
            CustomerIssue.priority,
            CustomerIssue.assigned_employee_id,
        )
    ).all()
    now = utcnow()
    locations = {
        x.id: x
        for x in db.scalars(select(Location).where(Location.company_id == auth.company_id)).all()
    }
    for location_id, due, priority, assignee, count in rows:
        location = locations.get(location_id)
        today = now.astimezone(
            ZoneInfo(location.timezone if location else "America/New_York")
        ).date()
        totals["open"] += count
        if due and due < today:
            totals["overdue"] += count
        if priority in ("High", "Urgent"):
            totals["high_priority"] += count
        if assignee == auth.employee_id:
            totals["assigned_to_me"] += count
    return totals


@router.get("/options")
def issue_options(auth=Depends(web_auth_context), db: Session = Depends(get_web_db)):
    rows = db.scalars(
        select(Employee)
        .where(Employee.company_id == auth.company_id, Employee.active.is_(True))
        .order_by(Employee.name)
    ).all()
    return {
        "employees": [
            {
                "id": e.id,
                "name": e.name,
                "role": e.role,
                "location_ids": e.location_ids or [],
                "active": e.active,
            }
            for e in rows
        ]
    }


@router.post("", status_code=201)
def new_issue(
    body: IssueCreate,
    background_tasks: BackgroundTasks,
    auth=Depends(web_mutation_context),
    db: Session = Depends(get_web_db),
):
    try:
        row = create_issue(db, auth, body.model_dump())
        db.commit()
        payload = serialize_issue(db, row)
        queue_customer_issue_created(background_tasks, db, row, auth.employee_id)
        return payload
    except Exception as exc:
        db.rollback()
        return error_response(exc)


@router.get("/{issue_id}")
def detail(issue_id: str, auth=Depends(web_auth_context), db: Session = Depends(get_web_db)):
    try:
        return serialize_issue(db, get_issue(db, auth, issue_id))
    except Exception as exc:
        return error_response(exc)


@router.patch("/{issue_id}")
def patch_issue(
    issue_id: str,
    body: IssueUpdate,
    auth=Depends(web_mutation_context),
    db: Session = Depends(get_web_db),
):
    data = body.model_dump(exclude_unset=True)
    version = data.pop("version")
    try:
        row = update_issue(db, auth, issue_id, version, data)
        db.commit()
        return serialize_issue(db, row)
    except Exception as exc:
        db.rollback()
        return error_response(exc)


@router.get("/{issue_id}/activities")
def activities(
    issue_id: str,
    limit: int = Query(50, ge=1, le=250),
    offset: int = Query(0, ge=0),
    auth=Depends(web_auth_context),
    db: Session = Depends(get_web_db),
):
    try:
        get_issue(db, auth, issue_id)
    except Exception as exc:
        return error_response(exc)
    q = select(IssueActivity).where(
        IssueActivity.company_id == auth.company_id, IssueActivity.issue_id == issue_id
    )
    total = db.scalar(select(func.count()).select_from(q.subquery()))
    rows = db.scalars(
        q.order_by(IssueActivity.occurred_at, IssueActivity.recorded_at, IssueActivity.id)
        .offset(offset)
        .limit(limit)
    ).all()
    return {"activities": [serialize_activity(row) for row in rows], "total": total}


@router.post("/{issue_id}/activities", status_code=201)
def log_communication(
    issue_id: str,
    body: CommunicationCreate,
    auth=Depends(web_mutation_context),
    db: Session = Depends(get_web_db),
):
    try:
        row = append_communication(db, auth, issue_id, body.model_dump(exclude_unset=True))
        db.commit()
        return serialize_activity(row)
    except Exception as exc:
        db.rollback()
        return error_response(exc)
