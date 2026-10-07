from datetime import timedelta
from decimal import Decimal
from uuid import uuid4
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..database import Customer, Location, Mailbox, utcnow
from ..schemas.mailboxes import MailboxCreate, MailboxUpdate
from ..web_sessions import get_web_db, web_auth_context, web_mutation_context

router = APIRouter(prefix="/api/mailboxes", tags=["mailboxes"])


def _today(location: Location | None):
    return utcnow().astimezone(
        ZoneInfo(location.timezone if location else "America/New_York")
    ).date()


def _missing(row: Mailbox) -> list[str]:
    result = []
    if not row.primary_id_on_file:
        result.append("Primary ID")
    if not row.secondary_id_on_file:
        result.append("Secondary ID")
    if not row.form_1583_complete:
        result.append("USPS Form 1583")
    if not row.msa_complete:
        result.append("MSA")
    if not row.phone_verified:
        result.append("Phone verification")
    return result


def _serialize(db: Session, row: Mailbox) -> dict:
    store = db.get(Location, row.location_id)
    customer = db.get(Customer, row.customer_id)
    today = _today(store)
    days_overdue = (
        max((today - row.renewal_date).days, 0)
        if row.renewal_date and row.renewal_date < today and row.status != "Closed"
        else 0
    )
    missing = _missing(row)
    return {
        "id": row.id,
        "location_id": row.location_id,
        "customer_id": row.customer_id,
        "mailbox_number": row.mailbox_number,
        "status": row.status,
        "renewal_date": row.renewal_date.isoformat() if row.renewal_date else None,
        "balance_due": float(row.balance_due or 0),
        "primary_id_on_file": row.primary_id_on_file,
        "secondary_id_on_file": row.secondary_id_on_file,
        "form_1583_complete": row.form_1583_complete,
        "msa_complete": row.msa_complete,
        "phone_verified": row.phone_verified,
        "forwarding_status": row.forwarding_status,
        "forwarding_address": row.forwarding_address,
        "notes": row.notes,
        "version": row.version,
        "created_by": row.created_by,
        "updated_by": row.updated_by,
        "created_at": row.created_at.isoformat(),
        "updated_at": row.updated_at.isoformat(),
        "closed_at": row.closed_at.isoformat() if row.closed_at else None,
        "days_overdue": days_overdue,
        "compliance_complete": not missing,
        "missing_compliance": missing,
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
        "customer": (
            {
                "id": customer.id,
                "company": customer.company,
                "first_name": customer.first_name,
                "last_name": customer.last_name,
                "phone": customer.phone,
                "email": customer.email,
            }
            if customer
            else None
        ),
    }


def _write_scope(db: Session, auth, location_id: str):
    location = db.get(Location, location_id)
    if not location or location.company_id != auth.company_id or not location.active:
        raise HTTPException(400, "Choose an active store")
    if auth.role != "admin" and location_id != auth.location_id:
        raise HTTPException(403, "Switch to this store before changing its mailboxes")
    return location


def _validate_customer(db: Session, auth, customer_id: str):
    customer = db.get(Customer, customer_id)
    if not customer or customer.company_id != auth.company_id or customer.is_deleted:
        raise HTTPException(400, "Choose an active customer")
    return customer


@router.get("")
def list_mailboxes(
    search: str = "",
    location_id: str = "",
    status: str = "",
    customer_id: str = "",
    missing_compliance: bool = False,
    overdue_only: bool = False,
    limit: int = Query(100, ge=1, le=250),
    offset: int = Query(0, ge=0),
    auth=Depends(web_auth_context),
    db: Session = Depends(get_web_db),
):
    q = select(Mailbox).where(Mailbox.company_id == auth.company_id)
    if location_id:
        q = q.where(Mailbox.location_id == location_id)
    if status:
        q = q.where(Mailbox.status == status)
    if customer_id:
        q = q.where(Mailbox.customer_id == customer_id)
    if missing_compliance:
        q = q.where(
            or_(
                Mailbox.primary_id_on_file.is_(False),
                Mailbox.secondary_id_on_file.is_(False),
                Mailbox.form_1583_complete.is_(False),
                Mailbox.msa_complete.is_(False),
                Mailbox.phone_verified.is_(False),
            )
        )
    if overdue_only:
        q = q.where(
            Mailbox.status != "Closed",
            Mailbox.renewal_date.is_not(None),
            Mailbox.renewal_date < utcnow().date(),
        )
    if search.strip():
        needle = f"%{search.strip()}%"
        q = q.join(
            Customer,
            (Customer.id == Mailbox.customer_id)
            & (Customer.company_id == auth.company_id),
        ).where(
            or_(
                Mailbox.mailbox_number.ilike(needle),
                Customer.company.ilike(needle),
                Customer.first_name.ilike(needle),
                Customer.last_name.ilike(needle),
                Customer.phone.ilike(needle),
                Customer.email.ilike(needle),
            )
        )
    total = db.scalar(select(func.count()).select_from(q.subquery()))
    rows = db.scalars(
        q.order_by(
            Mailbox.status == "Closed",
            Mailbox.renewal_date.is_(None),
            Mailbox.renewal_date,
            Mailbox.mailbox_number,
        )
        .offset(offset)
        .limit(limit)
    ).all()
    return {"mailboxes": [_serialize(db, row) for row in rows], "total": total}


@router.get("/summary")
def summary(auth=Depends(web_auth_context), db: Session = Depends(get_web_db)):
    rows = db.scalars(select(Mailbox).where(Mailbox.company_id == auth.company_id)).all()
    locations = {
        row.id: row
        for row in db.scalars(
            select(Location).where(Location.company_id == auth.company_id)
        ).all()
    }
    result = {
        "active": 0,
        "overdue": 0,
        "due_30": 0,
        "missing_compliance": 0,
        "blocked": 0,
    }
    now = utcnow()
    for row in rows:
        if row.status == "Closed":
            continue
        result["active"] += 1
        location = locations.get(row.location_id)
        today = now.astimezone(
            ZoneInfo(location.timezone if location else "America/New_York")
        ).date()
        if row.renewal_date and row.renewal_date < today:
            result["overdue"] += 1
        elif row.renewal_date and row.renewal_date <= today + timedelta(days=30):
            result["due_30"] += 1
        if _missing(row):
            result["missing_compliance"] += 1
        if row.status == "Blocked":
            result["blocked"] += 1
    return result


@router.get("/options")
def options(auth=Depends(web_auth_context), db: Session = Depends(get_web_db)):
    customers = db.scalars(
        select(Customer)
        .where(
            Customer.company_id == auth.company_id,
            Customer.is_deleted.is_(False),
        )
        .order_by(Customer.company, Customer.last_name, Customer.first_name)
        .limit(500)
    ).all()
    return {
        "customers": [
            {
                "id": row.id,
                "company": row.company,
                "first_name": row.first_name,
                "last_name": row.last_name,
                "phone": row.phone,
                "email": row.email,
            }
            for row in customers
        ]
    }


@router.post("", status_code=201)
def create_mailbox(
    body: MailboxCreate,
    auth=Depends(web_mutation_context),
    db: Session = Depends(get_web_db),
):
    _write_scope(db, auth, body.location_id)
    _validate_customer(db, auth, body.customer_id)
    row = Mailbox(
        id=str(uuid4()),
        company_id=auth.company_id,
        created_by=auth.employee_id,
        updated_by=auth.employee_id,
        **body.model_dump(),
    )
    if row.status == "Closed":
        row.closed_at = utcnow()
    db.add(row)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, "That mailbox number already exists at this store") from exc
    return _serialize(db, row)


@router.patch("/{mailbox_id}")
def update_mailbox(
    mailbox_id: str,
    body: MailboxUpdate,
    auth=Depends(web_mutation_context),
    db: Session = Depends(get_web_db),
):
    row = db.scalar(
        select(Mailbox).where(
            Mailbox.id == mailbox_id,
            Mailbox.company_id == auth.company_id,
        )
    )
    if not row:
        raise HTTPException(404, "Mailbox not found")
    _write_scope(db, auth, row.location_id)
    _write_scope(db, auth, body.location_id)
    _validate_customer(db, auth, body.customer_id)
    if row.version != body.version:
        raise HTTPException(409, "This mailbox changed on another device")
    values = body.model_dump()
    values.pop("version")
    values["balance_due"] = Decimal(values["balance_due"])
    closed_at = row.closed_at
    if values["status"] == "Closed" and row.status != "Closed":
        closed_at = utcnow()
    elif row.status == "Closed" and values["status"] != "Closed":
        closed_at = None
    result = db.execute(
        update(Mailbox)
        .where(
            Mailbox.id == mailbox_id,
            Mailbox.company_id == auth.company_id,
            Mailbox.version == body.version,
        )
        .values(
            **values,
            version=body.version + 1,
            updated_by=auth.employee_id,
            updated_at=utcnow(),
            closed_at=closed_at,
        )
        .execution_options(synchronize_session=False)
    )
    if result.rowcount != 1:
        db.rollback()
        raise HTTPException(409, "This mailbox changed on another device")
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, "That mailbox number already exists at this store") from exc
    db.refresh(row)
    return _serialize(db, row)
