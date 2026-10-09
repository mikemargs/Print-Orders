"""Summary-card predicates, applied before counting and pagination."""

from datetime import timedelta
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from sqlalchemy import and_, func, or_, select

from ..database import CatalogPriceTier, Location, utcnow


def local_date_filter(db, auth, model, column, upcoming=False, active_stores=False):
    locations = db.scalars(select(Location).where(Location.company_id == auth.company_id)).all()
    now = utcnow()
    groups = {}
    for location in locations:
        timezone = location.timezone if not active_stores or location.active else "America/New_York"
        groups.setdefault(timezone, []).append(location.id)
    clauses = []
    for timezone, ids in groups.items():
        day = now.astimezone(ZoneInfo(timezone)).date()
        date_clause = (
            and_(column >= day, column <= day + timedelta(days=30)) if upcoming else column < day
        )
        clauses.append(and_(model.location_id.in_(ids), date_clause))
    return (
        or_(*clauses) if clauses else column < now.astimezone(ZoneInfo("America/New_York")).date()
    )


def apply_view(db, auth, query, model, view):
    if not view:
        return query
    kind = model.__tablename__
    predicates = {}
    if kind == "work_orders":
        pending = model.status.notin_(["Completed", "Cancelled"])
        predicates = {
            "all": True,
            "pending": pending,
            "rush": and_(pending, model.priority == "Rush"),
            "ready": model.status == "Ready for Pickup",
            # Match the Main Dashboard's date boundary.
            "overdue": and_(
                pending, model.due_date != "", model.due_date < utcnow().date().isoformat()
            ),
            "sales": True,
            "outstanding": model.balance > 0,
        }
    elif kind == "catalog_products":
        tier_count = (
            select(func.count(CatalogPriceTier.id))
            .where(
                CatalogPriceTier.company_id == auth.company_id,
                CatalogPriceTier.product_id == model.id,
            )
            .scalar_subquery()
        )
        predicates = {
            "active": model.active.is_(True),
            "manual": and_(model.active.is_(True), model.manual_price.is_(True)),
            "tiered": tier_count > 1,
        }
    elif kind == "inventory_items":
        active = model.active.is_(True)
        predicates = {
            "active": active,
            "value": active,
            "low": and_(active, model.quantity <= model.reorder_point),
            "out": and_(active, model.quantity <= 0),
        }
    elif kind == "equipment_assets":
        active = and_(model.active.is_(True), model.status != "Retired")
        predicates = {
            "active": active,
            "needs_attention": and_(active, model.status == "Needs Attention"),
            "out_of_service": and_(active, model.status == "Out of Service"),
            "attention": and_(active, model.status.in_(["Needs Attention", "Out of Service"])),
            "service_overdue": and_(
                active,
                local_date_filter(db, auth, model, model.next_service_date, active_stores=True),
            ),
        }
    elif kind == "mailboxes":
        active = model.status != "Closed"
        missing = or_(
            *(
                getattr(model, name).is_(False)
                for name in (
                    "primary_id_on_file",
                    "secondary_id_on_file",
                    "form_1583_complete",
                    "msa_complete",
                    "phone_verified",
                )
            )
        )
        predicates = {
            "active": active,
            "missing_compliance": and_(active, missing),
            "overdue": and_(active, local_date_filter(db, auth, model, model.renewal_date)),
            "due_30": and_(
                active, local_date_filter(db, auth, model, model.renewal_date, upcoming=True)
            ),
        }
    elif kind == "shipping_cases":
        opened = model.status.notin_(["Denied", "Refunded", "Resolved"])
        predicates = {
            "open": opened,
            "overdue": and_(opened, local_date_filter(db, auth, model, model.follow_up_date)),
            "gsr": and_(opened, model.case_type == "GSR"),
            "claims": and_(
                opened, model.case_type.in_(["Lost Package", "Damage Claim", "Shipping Claim"])
            ),
        }
    elif kind in {"operational_tasks", "customer_issues"}:
        opened = (
            model.status != "Resolved"
            if kind == "customer_issues"
            else model.status.notin_(["Completed", "Cancelled"])
        )
        date_column = model.follow_up_date if kind == "customer_issues" else model.due_date
        predicates = {
            "open": opened,
            "overdue": and_(opened, local_date_filter(db, auth, model, date_column)),
            "high_priority": and_(opened, model.priority.in_(["High", "Urgent"])),
            "mine": and_(opened, model.assigned_employee_id == auth.employee_id),
        }
    if view not in predicates:
        raise HTTPException(400, "Unknown summary view")
    return query.where(predicates[view])
