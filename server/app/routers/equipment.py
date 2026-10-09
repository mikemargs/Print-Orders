from datetime import timedelta
from decimal import Decimal
from uuid import uuid4
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import and_, func, or_, select, update
from sqlalchemy.orm import Session

from ..database import (
    Employee,
    EquipmentAsset,
    EquipmentServiceEvent,
    Location,
    utcnow,
)
from ..schemas.assets import (
    EquipmentAssetCreate,
    EquipmentAssetUpdate,
    EquipmentIssueReport,
    EquipmentServiceCreate,
)
from ..services.drilldowns import apply_view, local_date_filter
from ..web_sessions import get_web_db, web_auth_context, web_mutation_context

router = APIRouter(prefix="/api/equipment", tags=["equipment"])


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
        raise HTTPException(403, "Switch to this store before changing its equipment")
    return location


def _manager_scope(db: Session, auth, location_id: str):
    if auth.role not in {"supervisor", "admin"}:
        raise HTTPException(403, "Supervisor permission is required to manage equipment")
    return _write_scope(db, auth, location_id)


def _serialize(db: Session, row: EquipmentAsset) -> dict:
    store = db.get(Location, row.location_id)
    today = _today(store)
    service_overdue = bool(
        row.active
        and row.status != "Retired"
        and row.next_service_date
        and row.next_service_date < today
    )
    service_due_30 = bool(
        row.active
        and row.status != "Retired"
        and row.next_service_date
        and today <= row.next_service_date <= today + timedelta(days=30)
    )
    return {
        "id": row.id,
        "location_id": row.location_id,
        "name": row.name,
        "category": row.category,
        "asset_tag": row.asset_tag,
        "manufacturer": row.manufacturer,
        "model": row.model,
        "serial_number": row.serial_number,
        "status": row.status,
        "purchase_date": row.purchase_date.isoformat() if row.purchase_date else None,
        "warranty_expiration": (
            row.warranty_expiration.isoformat() if row.warranty_expiration else None
        ),
        "vendor": row.vendor,
        "service_provider": row.service_provider,
        "next_service_date": (
            row.next_service_date.isoformat() if row.next_service_date else None
        ),
        "notes": row.notes,
        "active": row.active,
        "version": row.version,
        "created_by": row.created_by,
        "updated_by": row.updated_by,
        "created_at": row.created_at.isoformat(),
        "updated_at": row.updated_at.isoformat(),
        "service_overdue": service_overdue,
        "service_due_30": service_due_30,
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


def _serialize_event(db: Session, row: EquipmentServiceEvent) -> dict:
    employee = db.get(Employee, row.recorded_by)
    return {
        "id": row.id,
        "equipment_id": row.equipment_id,
        "location_id": row.location_id,
        "event_date": row.event_date.isoformat(),
        "event_type": row.event_type,
        "summary": row.summary,
        "provider": row.provider,
        "cost": float(row.cost or 0),
        "recorded_by": row.recorded_by,
        "recorded_by_name": employee.name if employee else "",
        "created_at": row.created_at.isoformat(),
    }


@router.get("")
def list_equipment(
    view: str = "",
    search: str = "",
    location_id: str = "",
    category: str = "",
    status: str = "",
    attention_only: bool = False,
    include_retired: bool = False,
    limit: int = Query(250, ge=1, le=500),
    offset: int = Query(0, ge=0),
    auth=Depends(web_auth_context),
    db: Session = Depends(get_web_db),
):
    q = select(EquipmentAsset).where(EquipmentAsset.company_id == auth.company_id)
    if location_id:
        q = q.where(EquipmentAsset.location_id == location_id)
    if category:
        q = q.where(EquipmentAsset.category == category)
    if status:
        q = q.where(EquipmentAsset.status == status)
    elif not include_retired:
        q = q.where(
            EquipmentAsset.active.is_(True),
            EquipmentAsset.status != "Retired",
        )
    if search.strip():
        needle = f"%{search.strip()}%"
        q = q.where(
            or_(
                EquipmentAsset.name.ilike(needle),
                EquipmentAsset.asset_tag.ilike(needle),
                EquipmentAsset.manufacturer.ilike(needle),
                EquipmentAsset.model.ilike(needle),
                EquipmentAsset.serial_number.ilike(needle),
                EquipmentAsset.category.ilike(needle),
                EquipmentAsset.vendor.ilike(needle),
                EquipmentAsset.service_provider.ilike(needle),
            )
        )
    q = apply_view(db, auth, q, EquipmentAsset, view)
    if attention_only:
        q = q.where(or_(
            EquipmentAsset.status.in_(["Needs Attention", "Out of Service"]),
            and_(EquipmentAsset.active.is_(True), EquipmentAsset.status != "Retired",
                 local_date_filter(db, auth, EquipmentAsset, EquipmentAsset.next_service_date)),
        ))
    total = db.scalar(select(func.count()).select_from(q.subquery()))
    rows = db.scalars(
        q.order_by(
            EquipmentAsset.location_id,
            EquipmentAsset.category,
            EquipmentAsset.name,
        )
        .offset(offset)
        .limit(limit)
    ).all()
    serialized = [_serialize(db, row) for row in rows]
    serialized.sort(
        key=lambda row: (
            not (
                row["status"] in {"Needs Attention", "Out of Service"}
                or row["service_overdue"]
            ),
            row["location_id"],
            row["category"].lower(),
            row["name"].lower(),
        )
    )
    return {"equipment": serialized, "total": total}


@router.get("/summary")
def equipment_summary(auth=Depends(web_auth_context), db: Session = Depends(get_web_db)):
    rows = db.scalars(
        select(EquipmentAsset).where(
            EquipmentAsset.company_id == auth.company_id,
            EquipmentAsset.active.is_(True),
            EquipmentAsset.status != "Retired",
        )
    ).all()
    stores = {
        row.id: row
        for row in db.scalars(
            select(Location).where(
                Location.company_id == auth.company_id,
                Location.active.is_(True),
            )
        ).all()
    }
    result = {
        "active_assets": len(rows),
        "needs_attention": 0,
        "out_of_service": 0,
        "service_overdue": 0,
        "service_due_30": 0,
        "stores": [],
    }
    by_store = {
        location_id: {
            "location_id": location_id,
            "store": f"{location.name} #{location.store_number}",
            "active_assets": 0,
            "needs_attention": 0,
            "out_of_service": 0,
            "service_overdue": 0,
        }
        for location_id, location in stores.items()
    }
    for row in rows:
        store = stores.get(row.location_id)
        today = _today(store)
        needs_attention = row.status == "Needs Attention"
        out_of_service = row.status == "Out of Service"
        overdue = bool(row.next_service_date and row.next_service_date < today)
        due_30 = bool(
            row.next_service_date
            and today <= row.next_service_date <= today + timedelta(days=30)
        )
        result["needs_attention"] += int(needs_attention)
        result["out_of_service"] += int(out_of_service)
        result["service_overdue"] += int(overdue)
        result["service_due_30"] += int(due_30)
        store_summary = by_store.get(row.location_id)
        if store_summary:
            store_summary["active_assets"] += 1
            store_summary["needs_attention"] += int(needs_attention)
            store_summary["out_of_service"] += int(out_of_service)
            store_summary["service_overdue"] += int(overdue)
    result["stores"] = list(by_store.values())
    return result


@router.post("", status_code=201)
def create_equipment(
    body: EquipmentAssetCreate,
    auth=Depends(web_mutation_context),
    db: Session = Depends(get_web_db),
):
    _manager_scope(db, auth, body.location_id)
    row = EquipmentAsset(
        id=str(uuid4()),
        company_id=auth.company_id,
        created_by=auth.employee_id,
        updated_by=auth.employee_id,
        **body.model_dump(),
    )
    db.add(row)
    db.commit()
    return _serialize(db, row)


@router.patch("/{equipment_id}")
def update_equipment(
    equipment_id: str,
    body: EquipmentAssetUpdate,
    auth=Depends(web_mutation_context),
    db: Session = Depends(get_web_db),
):
    row = db.scalar(
        select(EquipmentAsset).where(
            EquipmentAsset.id == equipment_id,
            EquipmentAsset.company_id == auth.company_id,
        )
    )
    if not row:
        raise HTTPException(404, "Equipment not found")
    _manager_scope(db, auth, row.location_id)
    _manager_scope(db, auth, body.location_id)
    if row.version != body.version:
        raise HTTPException(409, "This equipment record changed on another device")
    values = body.model_dump()
    values.pop("version")
    result = db.execute(
        update(EquipmentAsset)
        .where(
            EquipmentAsset.id == equipment_id,
            EquipmentAsset.company_id == auth.company_id,
            EquipmentAsset.version == body.version,
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
        raise HTTPException(409, "This equipment record changed on another device")
    db.commit()
    db.refresh(row)
    return _serialize(db, row)


@router.post("/{equipment_id}/report-issue")
def report_equipment_issue(
    equipment_id: str,
    body: EquipmentIssueReport,
    auth=Depends(web_mutation_context),
    db: Session = Depends(get_web_db),
):
    row = db.scalar(
        select(EquipmentAsset).where(
            EquipmentAsset.id == equipment_id,
            EquipmentAsset.company_id == auth.company_id,
            EquipmentAsset.active.is_(True),
        )
    )
    if not row:
        raise HTTPException(404, "Equipment not found")
    store = _write_scope(db, auth, row.location_id)
    if row.status == "Retired":
        raise HTTPException(400, "Retired equipment cannot receive new issue reports")
    if row.version != body.version:
        raise HTTPException(409, "This equipment record changed on another device")
    result = db.execute(
        update(EquipmentAsset)
        .where(
            EquipmentAsset.id == equipment_id,
            EquipmentAsset.company_id == auth.company_id,
            EquipmentAsset.version == body.version,
        )
        .values(
            status="Needs Attention",
            version=body.version + 1,
            updated_by=auth.employee_id,
            updated_at=utcnow(),
        )
        .execution_options(synchronize_session=False)
    )
    if result.rowcount != 1:
        db.rollback()
        raise HTTPException(409, "This equipment record changed on another device")
    db.add(
        EquipmentServiceEvent(
            id=str(uuid4()),
            company_id=auth.company_id,
            equipment_id=row.id,
            location_id=row.location_id,
            event_date=_today(store),
            event_type="Issue Reported",
            summary=body.summary,
            provider="",
            cost=Decimal(0),
            recorded_by=auth.employee_id,
        )
    )
    db.commit()
    db.refresh(row)
    return _serialize(db, row)


@router.post("/{equipment_id}/service-events", status_code=201)
def add_service_event(
    equipment_id: str,
    body: EquipmentServiceCreate,
    auth=Depends(web_mutation_context),
    db: Session = Depends(get_web_db),
):
    row = db.scalar(
        select(EquipmentAsset).where(
            EquipmentAsset.id == equipment_id,
            EquipmentAsset.company_id == auth.company_id,
        )
    )
    if not row:
        raise HTTPException(404, "Equipment not found")
    _manager_scope(db, auth, row.location_id)
    if row.version != body.version:
        raise HTTPException(409, "This equipment record changed on another device")
    values = {
        "version": body.version + 1,
        "updated_by": auth.employee_id,
        "updated_at": utcnow(),
    }
    if body.status_after is not None:
        values["status"] = body.status_after
        values["active"] = body.status_after != "Retired"
    if "next_service_date" in body.model_fields_set:
        values["next_service_date"] = body.next_service_date
    result = db.execute(
        update(EquipmentAsset)
        .where(
            EquipmentAsset.id == equipment_id,
            EquipmentAsset.company_id == auth.company_id,
            EquipmentAsset.version == body.version,
        )
        .values(**values)
        .execution_options(synchronize_session=False)
    )
    if result.rowcount != 1:
        db.rollback()
        raise HTTPException(409, "This equipment record changed on another device")
    event = EquipmentServiceEvent(
        id=str(uuid4()),
        company_id=auth.company_id,
        equipment_id=row.id,
        location_id=row.location_id,
        event_date=body.event_date,
        event_type=body.event_type,
        summary=body.summary,
        provider=body.provider,
        cost=Decimal(body.cost),
        recorded_by=auth.employee_id,
    )
    db.add(event)
    db.commit()
    db.refresh(row)
    return {"equipment": _serialize(db, row), "event": _serialize_event(db, event)}


@router.get("/{equipment_id}/history")
def equipment_history(
    equipment_id: str,
    limit: int = Query(100, ge=1, le=500),
    auth=Depends(web_auth_context),
    db: Session = Depends(get_web_db),
):
    asset = db.scalar(
        select(EquipmentAsset).where(
            EquipmentAsset.id == equipment_id,
            EquipmentAsset.company_id == auth.company_id,
        )
    )
    if not asset:
        raise HTTPException(404, "Equipment not found")
    rows = db.scalars(
        select(EquipmentServiceEvent)
        .where(
            EquipmentServiceEvent.company_id == auth.company_id,
            EquipmentServiceEvent.equipment_id == equipment_id,
        )
        .order_by(
            EquipmentServiceEvent.event_date.desc(),
            EquipmentServiceEvent.created_at.desc(),
        )
        .limit(limit)
    ).all()
    return {"events": [_serialize_event(db, row) for row in rows]}
