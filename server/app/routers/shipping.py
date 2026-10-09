from uuid import uuid4
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_, select, update
from sqlalchemy.orm import Session

from ..database import Customer, CustomerIssue, Location, ShippingCase, utcnow
from ..schemas.shipping import ShippingCaseCreate, ShippingCaseUpdate
from ..services.drilldowns import apply_view
from ..web_sessions import get_web_db, web_auth_context, web_mutation_context

router = APIRouter(prefix="/api/shipping-cases", tags=["shipping-cases"])

CLOSED_STATUSES = {"Denied", "Refunded", "Resolved"}
CLAIM_TYPES = {"Lost Package", "Damage Claim", "Shipping Claim"}


def _serialize(db: Session, row: ShippingCase) -> dict:
    store = db.get(Location, row.location_id)
    customer = db.get(Customer, row.customer_id)
    issue = db.get(CustomerIssue, row.customer_issue_id) if row.customer_issue_id else None
    return {
        "id": row.id,
        "location_id": row.location_id,
        "customer_id": row.customer_id,
        "customer_issue_id": row.customer_issue_id,
        "tracking_number": row.tracking_number,
        "carrier": row.carrier,
        "service_level": row.service_level,
        "case_type": row.case_type,
        "status": row.status,
        "ship_date": row.ship_date.isoformat() if row.ship_date else None,
        "promised_date": row.promised_date.isoformat() if row.promised_date else None,
        "delivered_date": row.delivered_date.isoformat() if row.delivered_date else None,
        "carrier_reference": row.carrier_reference,
        "amount_requested": float(row.amount_requested or 0),
        "amount_approved": float(row.amount_approved or 0),
        "next_action": row.next_action,
        "follow_up_date": row.follow_up_date.isoformat() if row.follow_up_date else None,
        "notes": row.notes,
        "version": row.version,
        "created_by": row.created_by,
        "updated_by": row.updated_by,
        "created_at": row.created_at.isoformat(),
        "updated_at": row.updated_at.isoformat(),
        "resolved_at": row.resolved_at.isoformat() if row.resolved_at else None,
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
        "issue_reference": issue.reference if issue else None,
        "issue_title": issue.title if issue else None,
    }


def _write_scope(db: Session, auth, location_id: str):
    location = db.get(Location, location_id)
    if not location or location.company_id != auth.company_id or not location.active:
        raise HTTPException(400, "Choose an active store")
    if auth.role != "admin" and location_id != auth.location_id:
        raise HTTPException(403, "Switch to this store before changing its shipping cases")
    return location


def _validate_links(db: Session, auth, body):
    _write_scope(db, auth, body.location_id)
    customer = db.get(Customer, body.customer_id)
    if not customer or customer.company_id != auth.company_id or customer.is_deleted:
        raise HTTPException(400, "Choose an active customer")
    if body.customer_issue_id:
        issue = db.get(CustomerIssue, body.customer_issue_id)
        if (
            not issue
            or issue.company_id != auth.company_id
            or issue.customer_id != body.customer_id
            or issue.location_id != body.location_id
        ):
            raise HTTPException(
                400, "Linked customer issue must match the customer and store"
            )


@router.get("")
def list_shipping_cases(
    view: str = "",
    search: str = "",
    location_id: str = "",
    customer_id: str = "",
    status: str = "",
    case_type: str = "",
    open_only: bool = True,
    limit: int = Query(100, ge=1, le=250),
    offset: int = Query(0, ge=0),
    auth=Depends(web_auth_context),
    db: Session = Depends(get_web_db),
):
    q = select(ShippingCase).where(ShippingCase.company_id == auth.company_id)
    if location_id:
        q = q.where(ShippingCase.location_id == location_id)
    if customer_id:
        q = q.where(ShippingCase.customer_id == customer_id)
    if status:
        q = q.where(ShippingCase.status == status)
    elif open_only:
        q = q.where(ShippingCase.status.notin_(CLOSED_STATUSES))
    if case_type:
        q = q.where(ShippingCase.case_type == case_type)
    if search.strip():
        needle = f"%{search.strip()}%"
        q = q.join(
            Customer,
            (Customer.id == ShippingCase.customer_id)
            & (Customer.company_id == auth.company_id),
        ).where(
            or_(
                ShippingCase.tracking_number.ilike(needle),
                ShippingCase.carrier_reference.ilike(needle),
                ShippingCase.service_level.ilike(needle),
                Customer.company.ilike(needle),
                Customer.first_name.ilike(needle),
                Customer.last_name.ilike(needle),
            )
        )
    q = apply_view(db, auth, q, ShippingCase, view)
    total = db.scalar(select(func.count()).select_from(q.subquery()))
    rows = db.scalars(
        q.order_by(
            ShippingCase.follow_up_date.is_(None),
            ShippingCase.follow_up_date,
            ShippingCase.updated_at.desc(),
        )
        .offset(offset)
        .limit(limit)
    ).all()
    return {"cases": [_serialize(db, row) for row in rows], "total": total}


@router.get("/summary")
def summary(auth=Depends(web_auth_context), db: Session = Depends(get_web_db)):
    rows = db.scalars(
        select(ShippingCase).where(ShippingCase.company_id == auth.company_id)
    ).all()
    locations = {
        row.id: row
        for row in db.scalars(
            select(Location).where(Location.company_id == auth.company_id)
        ).all()
    }
    result = {
        "open": 0,
        "overdue_followups": 0,
        "gsr_pending": 0,
        "claims_pending": 0,
        "approved": 0,
    }
    now = utcnow()
    for row in rows:
        if row.status in CLOSED_STATUSES:
            continue
        result["open"] += 1
        location = locations.get(row.location_id)
        today = now.astimezone(
            ZoneInfo(location.timezone if location else "America/New_York")
        ).date()
        if row.follow_up_date and row.follow_up_date < today:
            result["overdue_followups"] += 1
        if row.case_type == "GSR":
            result["gsr_pending"] += 1
        if row.case_type in CLAIM_TYPES:
            result["claims_pending"] += 1
        if row.status == "Approved":
            result["approved"] += 1
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
    issues = db.scalars(
        select(CustomerIssue)
        .where(
            CustomerIssue.company_id == auth.company_id,
            CustomerIssue.status != "Resolved",
        )
        .order_by(CustomerIssue.updated_at.desc())
        .limit(500)
    ).all()
    return {
        "customers": [
            {
                "id": row.id,
                "company": row.company,
                "first_name": row.first_name,
                "last_name": row.last_name,
            }
            for row in customers
        ],
        "issues": [
            {
                "id": row.id,
                "reference": row.reference,
                "title": row.title,
                "customer_id": row.customer_id,
                "location_id": row.location_id,
            }
            for row in issues
        ],
    }


@router.post("", status_code=201)
def create_shipping_case(
    body: ShippingCaseCreate,
    auth=Depends(web_mutation_context),
    db: Session = Depends(get_web_db),
):
    _validate_links(db, auth, body)
    row = ShippingCase(
        id=str(uuid4()),
        company_id=auth.company_id,
        created_by=auth.employee_id,
        updated_by=auth.employee_id,
        **body.model_dump(),
    )
    if row.status in CLOSED_STATUSES:
        row.resolved_at = utcnow()
    db.add(row)
    db.commit()
    return _serialize(db, row)


@router.patch("/{case_id}")
def update_shipping_case(
    case_id: str,
    body: ShippingCaseUpdate,
    auth=Depends(web_mutation_context),
    db: Session = Depends(get_web_db),
):
    row = db.scalar(
        select(ShippingCase).where(
            ShippingCase.id == case_id,
            ShippingCase.company_id == auth.company_id,
        )
    )
    if not row:
        raise HTTPException(404, "Shipping case not found")
    _write_scope(db, auth, row.location_id)
    _validate_links(db, auth, body)
    if row.version != body.version:
        raise HTTPException(409, "This shipping case changed on another device")
    values = body.model_dump()
    values.pop("version")
    resolved_at = row.resolved_at
    if values["status"] in CLOSED_STATUSES and row.status not in CLOSED_STATUSES:
        resolved_at = utcnow()
    elif row.status in CLOSED_STATUSES and values["status"] not in CLOSED_STATUSES:
        resolved_at = None
    result = db.execute(
        update(ShippingCase)
        .where(
            ShippingCase.id == case_id,
            ShippingCase.company_id == auth.company_id,
            ShippingCase.version == body.version,
        )
        .values(
            **values,
            version=body.version + 1,
            updated_by=auth.employee_id,
            updated_at=utcnow(),
            resolved_at=resolved_at,
        )
        .execution_options(synchronize_session=False)
    )
    if result.rowcount != 1:
        db.rollback()
        raise HTTPException(409, "This shipping case changed on another device")
    db.commit()
    db.refresh(row)
    return _serialize(db, row)
