from datetime import date
from uuid import uuid4
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..database import (
    Employee,
    Location,
    OperationsChecklistCompletion,
    OperationsChecklistTemplate,
    utcnow,
)
from ..schemas.operations import (
    ChecklistCompletionUpsert,
    ChecklistTemplateCreate,
    ChecklistTemplateUpdate,
)
from ..web_sessions import get_web_db, web_auth_context, web_mutation_context

router = APIRouter(prefix="/api/operations", tags=["operations"])


def _today(location: Location | None):
    return utcnow().astimezone(
        ZoneInfo(location.timezone if location else "America/New_York")
    ).date()


def _store(db: Session, auth, location_id: str):
    location = db.get(Location, location_id)
    if not location or location.company_id != auth.company_id or not location.active:
        raise HTTPException(400, "Choose an active store")
    return location


def _write_scope(db: Session, auth, location_id: str):
    location = _store(db, auth, location_id)
    if auth.role != "admin" and location_id != auth.location_id:
        raise HTTPException(403, "Switch to this store before changing its operations checklist")
    return location


def _manager_write_scope(db: Session, auth, location_id: str):
    if auth.role not in {"supervisor", "admin"}:
        raise HTTPException(403, "Supervisor permission is required to manage checklist items")
    return _write_scope(db, auth, location_id)


def _template_dict(row: OperationsChecklistTemplate, store: Location | None):
    return {
        "id": row.id,
        "location_id": row.location_id,
        "title": row.title,
        "description": row.description,
        "category": row.category,
        "active_days": row.active_days or [],
        "required": row.required,
        "active": row.active,
        "sort_order": row.sort_order,
        "version": row.version,
        "created_by": row.created_by,
        "updated_by": row.updated_by,
        "created_at": row.created_at.isoformat(),
        "updated_at": row.updated_at.isoformat(),
        "store": (
            {
                "id": store.id,
                "name": store.name,
                "store_number": store.store_number,
                "timezone": store.timezone,
            }
            if store
            else None
        ),
    }


def _completion_dict(db: Session, row: OperationsChecklistCompletion | None):
    if row is None:
        return None
    employee = db.get(Employee, row.completed_by)
    return {
        "id": row.id,
        "status": row.status,
        "notes": row.notes,
        "checklist_date": row.checklist_date.isoformat(),
        "completed_by": row.completed_by,
        "completed_by_name": employee.name if employee else "",
        "completed_at": row.completed_at.isoformat(),
        "version": row.version,
    }


def _item_dict(
    db: Session,
    template: OperationsChecklistTemplate,
    store: Location | None,
    completion: OperationsChecklistCompletion | None,
):
    return {
        **_template_dict(template, store),
        "completion": _completion_dict(db, completion),
    }


def _templates_for_date(db: Session, company_id: str, location_id: str, day: date):
    rows = db.scalars(
        select(OperationsChecklistTemplate)
        .where(
            OperationsChecklistTemplate.company_id == company_id,
            OperationsChecklistTemplate.location_id == location_id,
            OperationsChecklistTemplate.active.is_(True),
        )
        .order_by(
            OperationsChecklistTemplate.category,
            OperationsChecklistTemplate.sort_order,
            OperationsChecklistTemplate.title,
        )
    ).all()
    weekday = day.weekday()
    return [row for row in rows if weekday in (row.active_days or [])]


@router.get("/checklist")
def checklist(
    location_id: str = "",
    checklist_date: date | None = None,
    auth=Depends(web_auth_context),
    db: Session = Depends(get_web_db),
):
    selected_location = location_id or auth.location_id
    if selected_location == "all":
        stores = db.scalars(select(Location).where(
            Location.company_id == auth.company_id, Location.active.is_(True)
        ).order_by(Location.name)).all()
        items = []
        for store in stores:
            result = checklist(store.id, checklist_date, auth, db)
            items.extend({**item, "checklist_date": result["date"]} for item in result["items"])
        return {
            "location": {"id": "all", "name": "All stores", "store_number": "", "timezone": ""},
            "date": checklist_date.isoformat() if checklist_date else "Today in each store",
            "items": items,
        }
    store = _store(db, auth, selected_location)
    day = checklist_date or _today(store)
    templates = _templates_for_date(db, auth.company_id, selected_location, day)
    completions = {
        row.template_id: row
        for row in db.scalars(
            select(OperationsChecklistCompletion).where(
                OperationsChecklistCompletion.company_id == auth.company_id,
                OperationsChecklistCompletion.location_id == selected_location,
                OperationsChecklistCompletion.checklist_date == day,
            )
        ).all()
    }
    return {
        "location": {
            "id": store.id,
            "name": store.name,
            "store_number": store.store_number,
            "timezone": store.timezone,
        },
        "date": day.isoformat(),
        "items": [
            {**_item_dict(db, template, store, completions.get(template.id)), "checklist_date": day.isoformat()}
            for template in templates
        ],
    }


@router.get("/summary")
def summary(auth=Depends(web_auth_context), db: Session = Depends(get_web_db)):
    stores = db.scalars(
        select(Location).where(
            Location.company_id == auth.company_id,
            Location.active.is_(True),
        )
    ).all()
    result = {
        "expected": 0,
        "completed": 0,
        "skipped": 0,
        "pending": 0,
        "required_pending": 0,
        "stores": [],
    }
    for store in stores:
        day = _today(store)
        templates = _templates_for_date(db, auth.company_id, store.id, day)
        completions = {
            row.template_id: row
            for row in db.scalars(
                select(OperationsChecklistCompletion).where(
                    OperationsChecklistCompletion.company_id == auth.company_id,
                    OperationsChecklistCompletion.location_id == store.id,
                    OperationsChecklistCompletion.checklist_date == day,
                )
            ).all()
        }
        expected = len(templates)
        completed = sum(
            1
            for template in templates
            if completions.get(template.id)
            and completions[template.id].status == "Completed"
        )
        skipped = sum(
            1
            for template in templates
            if completions.get(template.id)
            and completions[template.id].status == "Skipped"
        )
        pending = expected - completed - skipped
        required_pending = sum(
            1
            for template in templates
            if template.required and not completions.get(template.id)
        )
        result["expected"] += expected
        result["completed"] += completed
        result["skipped"] += skipped
        result["pending"] += pending
        result["required_pending"] += required_pending
        result["stores"].append(
            {
                "location_id": store.id,
                "store": f"{store.name} #{store.store_number}",
                "date": day.isoformat(),
                "expected": expected,
                "completed": completed,
                "skipped": skipped,
                "pending": pending,
                "required_pending": required_pending,
            }
        )
    return result


@router.get("/templates")
def list_templates(
    location_id: str = "",
    include_inactive: bool = False,
    limit: int = Query(250, ge=1, le=500),
    auth=Depends(web_auth_context),
    db: Session = Depends(get_web_db),
):
    q = select(OperationsChecklistTemplate).where(
        OperationsChecklistTemplate.company_id == auth.company_id
    )
    if location_id:
        q = q.where(OperationsChecklistTemplate.location_id == location_id)
    if not include_inactive:
        q = q.where(OperationsChecklistTemplate.active.is_(True))
    rows = db.scalars(
        q.order_by(
            OperationsChecklistTemplate.location_id,
            OperationsChecklistTemplate.category,
            OperationsChecklistTemplate.sort_order,
            OperationsChecklistTemplate.title,
        ).limit(limit)
    ).all()
    stores = {
        row.id: row
        for row in db.scalars(
            select(Location).where(Location.company_id == auth.company_id)
        ).all()
    }
    return {
        "templates": [
            _template_dict(row, stores.get(row.location_id))
            for row in rows
        ]
    }


@router.post("/templates", status_code=201)
def create_template(
    body: ChecklistTemplateCreate,
    auth=Depends(web_mutation_context),
    db: Session = Depends(get_web_db),
):
    _manager_write_scope(db, auth, body.location_id)
    row = OperationsChecklistTemplate(
        id=str(uuid4()),
        company_id=auth.company_id,
        created_by=auth.employee_id,
        updated_by=auth.employee_id,
        **body.model_dump(),
    )
    db.add(row)
    db.commit()
    store = db.get(Location, row.location_id)
    return _template_dict(row, store)


@router.patch("/templates/{template_id}")
def update_template(
    template_id: str,
    body: ChecklistTemplateUpdate,
    auth=Depends(web_mutation_context),
    db: Session = Depends(get_web_db),
):
    row = db.scalar(
        select(OperationsChecklistTemplate).where(
            OperationsChecklistTemplate.id == template_id,
            OperationsChecklistTemplate.company_id == auth.company_id,
        )
    )
    if not row:
        raise HTTPException(404, "Checklist item not found")
    _manager_write_scope(db, auth, row.location_id)
    _manager_write_scope(db, auth, body.location_id)
    if row.version != body.version:
        raise HTTPException(409, "This checklist item changed on another device")
    values = body.model_dump()
    values.pop("version")
    result = db.execute(
        update(OperationsChecklistTemplate)
        .where(
            OperationsChecklistTemplate.id == template_id,
            OperationsChecklistTemplate.company_id == auth.company_id,
            OperationsChecklistTemplate.version == body.version,
        )
        .values(
            **values,
            version=body.version + 1,
            updated_by=auth.employee_id,
            updated_at=utcnow(),
        )
        .execution_options(synchronize_session=False)
    )
    if result.rowcount != 1:
        db.rollback()
        raise HTTPException(409, "This checklist item changed on another device")
    db.commit()
    db.refresh(row)
    store = db.get(Location, row.location_id)
    return _template_dict(row, store)


@router.put("/checklist/{template_id}")
def complete_item(
    template_id: str,
    body: ChecklistCompletionUpsert,
    auth=Depends(web_mutation_context),
    db: Session = Depends(get_web_db),
):
    template = db.scalar(
        select(OperationsChecklistTemplate).where(
            OperationsChecklistTemplate.id == template_id,
            OperationsChecklistTemplate.company_id == auth.company_id,
            OperationsChecklistTemplate.active.is_(True),
        )
    )
    if not template:
        raise HTTPException(404, "Checklist item not found")
    _write_scope(db, auth, template.location_id)
    if body.checklist_date.weekday() not in (template.active_days or []):
        raise HTTPException(400, "This checklist item is not scheduled for that date")
    row = db.scalar(
        select(OperationsChecklistCompletion).where(
            OperationsChecklistCompletion.company_id == auth.company_id,
            OperationsChecklistCompletion.template_id == template.id,
            OperationsChecklistCompletion.location_id == template.location_id,
            OperationsChecklistCompletion.checklist_date == body.checklist_date,
        )
    )
    if row:
        if body.version is not None and row.version != body.version:
            raise HTTPException(409, "This checklist completion changed on another device")
        row.status = body.status
        row.notes = body.notes
        row.completed_by = auth.employee_id
        row.completed_at = utcnow()
        row.version += 1
    else:
        if body.version is not None:
            raise HTTPException(409, "This checklist completion no longer matches the current state")
        row = OperationsChecklistCompletion(
            id=str(uuid4()),
            company_id=auth.company_id,
            template_id=template.id,
            location_id=template.location_id,
            checklist_date=body.checklist_date,
            status=body.status,
            notes=body.notes,
            completed_by=auth.employee_id,
            completed_at=utcnow(),
        )
        db.add(row)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, "This checklist item was completed on another device") from exc
    db.refresh(row)
    store = db.get(Location, template.location_id)
    return _item_dict(db, template, store, row)


@router.delete("/checklist/{template_id}", status_code=204)
def reset_item(
    template_id: str,
    checklist_date: date,
    auth=Depends(web_mutation_context),
    db: Session = Depends(get_web_db),
):
    template = db.scalar(
        select(OperationsChecklistTemplate).where(
            OperationsChecklistTemplate.id == template_id,
            OperationsChecklistTemplate.company_id == auth.company_id,
        )
    )
    if not template:
        raise HTTPException(404, "Checklist item not found")
    _write_scope(db, auth, template.location_id)
    row = db.scalar(
        select(OperationsChecklistCompletion).where(
            OperationsChecklistCompletion.company_id == auth.company_id,
            OperationsChecklistCompletion.template_id == template.id,
            OperationsChecklistCompletion.location_id == template.location_id,
            OperationsChecklistCompletion.checklist_date == checklist_date,
        )
    )
    if row:
        db.delete(row)
        db.commit()
