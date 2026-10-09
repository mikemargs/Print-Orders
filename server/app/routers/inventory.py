from decimal import Decimal
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_, select, update
from sqlalchemy.orm import Session

from ..database import (
    CatalogProduct,
    Employee,
    InventoryAdjustment,
    InventoryItem,
    Location,
    utcnow,
)
from ..schemas.assets import (
    InventoryAdjustmentCreate,
    InventoryItemCreate,
    InventoryItemUpdate,
)
from ..services.drilldowns import apply_view
from ..web_sessions import get_web_db, web_auth_context, web_mutation_context

router = APIRouter(prefix="/api/inventory", tags=["inventory"])


def _store(db: Session, auth, location_id: str):
    location = db.get(Location, location_id)
    if not location or location.company_id != auth.company_id or not location.active:
        raise HTTPException(400, "Choose an active store")
    return location


def _write_scope(db: Session, auth, location_id: str):
    location = _store(db, auth, location_id)
    if auth.role != "admin" and location_id != auth.location_id:
        raise HTTPException(403, "Switch to this store before changing its inventory")
    return location


def _manager_scope(db: Session, auth, location_id: str):
    if auth.role not in {"supervisor", "admin"}:
        raise HTTPException(403, "Supervisor permission is required to manage inventory items")
    return _write_scope(db, auth, location_id)



def _validate_catalog_link(db: Session, auth, catalog_product_id: str | None):
    if not catalog_product_id:
        return None
    product = db.get(CatalogProduct, catalog_product_id)
    if not product or product.company_id != auth.company_id or not product.active:
        raise HTTPException(400, "Choose an active catalog product")
    return product


def _serialize(db: Session, row: InventoryItem) -> dict:
    store = db.get(Location, row.location_id)
    quantity = Decimal(row.quantity or 0)
    reorder_point = Decimal(row.reorder_point or 0)
    cost_per_unit = Decimal(row.cost_per_unit or 0)
    return {
        "id": row.id,
        "location_id": row.location_id,
        "name": row.name,
        "sku": row.sku,
        "category": row.category,
        "unit": row.unit,
        "quantity": float(quantity),
        "reorder_point": float(reorder_point),
        "target_stock": float(row.target_stock or 0),
        "cost_per_unit": float(cost_per_unit),
        "vendor": row.vendor,
        "vendor_sku": row.vendor_sku,
        "catalog_product_id": row.catalog_product_id,
        "notes": row.notes,
        "active": row.active,
        "version": row.version,
        "created_by": row.created_by,
        "updated_by": row.updated_by,
        "created_at": row.created_at.isoformat(),
        "updated_at": row.updated_at.isoformat(),
        "low_stock": row.active and quantity <= reorder_point,
        "out_of_stock": row.active and quantity <= 0,
        "stock_value": float((quantity * cost_per_unit).quantize(Decimal("0.01"))),
        "store": (
            {
                "id": store.id,
                "name": store.name,
                "store_number": store.store_number,
            }
            if store
            else None
        ),
    }


def _serialize_adjustment(db: Session, row: InventoryAdjustment) -> dict:
    employee = db.get(Employee, row.adjusted_by)
    return {
        "id": row.id,
        "item_id": row.item_id,
        "location_id": row.location_id,
        "change_amount": float(row.change_amount),
        "resulting_quantity": float(row.resulting_quantity),
        "reason": row.reason,
        "notes": row.notes,
        "adjusted_by": row.adjusted_by,
        "adjusted_by_name": employee.name if employee else "",
        "created_at": row.created_at.isoformat(),
    }


@router.get("")
def list_inventory(
    view: str = "",
    search: str = "",
    location_id: str = "",
    category: str = "",
    low_stock: bool = False,
    include_inactive: bool = False,
    limit: int = Query(250, ge=1, le=500),
    offset: int = Query(0, ge=0),
    auth=Depends(web_auth_context),
    db: Session = Depends(get_web_db),
):
    q = select(InventoryItem).where(InventoryItem.company_id == auth.company_id)
    if location_id:
        q = q.where(InventoryItem.location_id == location_id)
    if category:
        q = q.where(InventoryItem.category == category)
    if not include_inactive:
        q = q.where(InventoryItem.active.is_(True))
    if low_stock:
        q = q.where(
            InventoryItem.active.is_(True),
            InventoryItem.quantity <= InventoryItem.reorder_point,
        )
    if search.strip():
        needle = f"%{search.strip()}%"
        q = q.where(
            or_(
                InventoryItem.name.ilike(needle),
                InventoryItem.sku.ilike(needle),
                InventoryItem.category.ilike(needle),
                InventoryItem.vendor.ilike(needle),
                InventoryItem.vendor_sku.ilike(needle),
            )
        )
    q = apply_view(db, auth, q, InventoryItem, view)
    total = db.scalar(select(func.count()).select_from(q.subquery()))
    rows = db.scalars(
        q.order_by(
            InventoryItem.quantity <= InventoryItem.reorder_point,
            InventoryItem.location_id,
            InventoryItem.category,
            InventoryItem.name,
        )
        .offset(offset)
        .limit(limit)
    ).all()
    rows = sorted(
        rows,
        key=lambda row: (
            not (row.active and Decimal(row.quantity or 0) <= Decimal(row.reorder_point or 0)),
            row.location_id,
            row.category.lower(),
            row.name.lower(),
        ),
    )
    return {"items": [_serialize(db, row) for row in rows], "total": total}


@router.get("/summary")
def inventory_summary(auth=Depends(web_auth_context), db: Session = Depends(get_web_db)):
    rows = db.scalars(
        select(InventoryItem).where(
            InventoryItem.company_id == auth.company_id,
            InventoryItem.active.is_(True),
        )
    ).all()
    locations = {
        row.id: row
        for row in db.scalars(
            select(Location).where(
                Location.company_id == auth.company_id,
                Location.active.is_(True),
            )
        ).all()
    }
    result = {
        "active_items": len(rows),
        "low_stock": 0,
        "out_of_stock": 0,
        "stock_value": 0.0,
        "stores": [],
    }
    by_store = {
        location_id: {
            "location_id": location_id,
            "store": f"{location.name} #{location.store_number}",
            "active_items": 0,
            "low_stock": 0,
            "out_of_stock": 0,
        }
        for location_id, location in locations.items()
    }
    total_value = Decimal(0)
    for row in rows:
        quantity = Decimal(row.quantity or 0)
        reorder_point = Decimal(row.reorder_point or 0)
        low = quantity <= reorder_point
        out = quantity <= 0
        total_value += quantity * Decimal(row.cost_per_unit or 0)
        if low:
            result["low_stock"] += 1
        if out:
            result["out_of_stock"] += 1
        store = by_store.get(row.location_id)
        if store:
            store["active_items"] += 1
            store["low_stock"] += int(low)
            store["out_of_stock"] += int(out)
    result["stock_value"] = float(total_value.quantize(Decimal("0.01")))
    result["stores"] = list(by_store.values())
    return result


@router.post("", status_code=201)
def create_inventory_item(
    body: InventoryItemCreate,
    auth=Depends(web_mutation_context),
    db: Session = Depends(get_web_db),
):
    _manager_scope(db, auth, body.location_id)
    _validate_catalog_link(db, auth, body.catalog_product_id)
    row = InventoryItem(
        id=str(uuid4()),
        company_id=auth.company_id,
        created_by=auth.employee_id,
        updated_by=auth.employee_id,
        **body.model_dump(),
    )
    db.add(row)
    if Decimal(body.quantity) > 0:
        # Persist the parent before its opening adjustment; these models have
        # no ORM relationship to order inserts. Keep both in one transaction.
        db.flush()
        db.add(
            InventoryAdjustment(
                id=str(uuid4()),
                company_id=auth.company_id,
                item_id=row.id,
                location_id=row.location_id,
                change_amount=Decimal(body.quantity),
                resulting_quantity=Decimal(body.quantity),
                reason="Count Correction",
                notes="Initial quantity",
                adjusted_by=auth.employee_id,
            )
        )
    db.commit()
    return _serialize(db, row)


@router.patch("/{item_id}")
def update_inventory_item(
    item_id: str,
    body: InventoryItemUpdate,
    auth=Depends(web_mutation_context),
    db: Session = Depends(get_web_db),
):
    row = db.scalar(
        select(InventoryItem).where(
            InventoryItem.id == item_id,
            InventoryItem.company_id == auth.company_id,
        )
    )
    if not row:
        raise HTTPException(404, "Inventory item not found")
    _manager_scope(db, auth, row.location_id)
    _manager_scope(db, auth, body.location_id)
    _validate_catalog_link(db, auth, body.catalog_product_id)
    if row.version != body.version:
        raise HTTPException(409, "This inventory item changed on another device")
    if Decimal(body.quantity) != Decimal(row.quantity):
        raise HTTPException(400, "Use a stock adjustment to change inventory quantity")
    values = body.model_dump()
    values.pop("version")
    values.pop("quantity")
    result = db.execute(
        update(InventoryItem)
        .where(
            InventoryItem.id == item_id,
            InventoryItem.company_id == auth.company_id,
            InventoryItem.version == body.version,
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
        raise HTTPException(409, "This inventory item changed on another device")
    db.commit()
    db.refresh(row)
    return _serialize(db, row)


@router.post("/{item_id}/adjust")
def adjust_inventory(
    item_id: str,
    body: InventoryAdjustmentCreate,
    auth=Depends(web_mutation_context),
    db: Session = Depends(get_web_db),
):
    row = db.scalar(
        select(InventoryItem).where(
            InventoryItem.id == item_id,
            InventoryItem.company_id == auth.company_id,
            InventoryItem.active.is_(True),
        )
    )
    if not row:
        raise HTTPException(404, "Inventory item not found")
    _write_scope(db, auth, row.location_id)
    if row.version != body.version:
        raise HTTPException(409, "This inventory item changed on another device")
    current = Decimal(row.quantity or 0)
    amount = Decimal(body.quantity)
    if body.mode == "add":
        new_quantity = current + amount
    elif body.mode == "remove":
        new_quantity = current - amount
    else:
        new_quantity = amount
    if new_quantity < 0:
        raise HTTPException(400, "Inventory quantity cannot be negative")
    change_amount = new_quantity - current
    result = db.execute(
        update(InventoryItem)
        .where(
            InventoryItem.id == item_id,
            InventoryItem.company_id == auth.company_id,
            InventoryItem.version == body.version,
        )
        .values(
            quantity=new_quantity,
            version=body.version + 1,
            updated_by=auth.employee_id,
            updated_at=utcnow(),
        )
        .execution_options(synchronize_session=False)
    )
    if result.rowcount != 1:
        db.rollback()
        raise HTTPException(409, "This inventory item changed on another device")
    db.add(
        InventoryAdjustment(
            id=str(uuid4()),
            company_id=auth.company_id,
            item_id=row.id,
            location_id=row.location_id,
            change_amount=change_amount,
            resulting_quantity=new_quantity,
            reason=body.reason,
            notes=body.notes,
            adjusted_by=auth.employee_id,
        )
    )
    db.commit()
    db.refresh(row)
    return _serialize(db, row)


@router.get("/{item_id}/history")
def inventory_history(
    item_id: str,
    limit: int = Query(100, ge=1, le=500),
    auth=Depends(web_auth_context),
    db: Session = Depends(get_web_db),
):
    item = db.scalar(
        select(InventoryItem).where(
            InventoryItem.id == item_id,
            InventoryItem.company_id == auth.company_id,
        )
    )
    if not item:
        raise HTTPException(404, "Inventory item not found")
    rows = db.scalars(
        select(InventoryAdjustment)
        .where(
            InventoryAdjustment.company_id == auth.company_id,
            InventoryAdjustment.item_id == item_id,
        )
        .order_by(InventoryAdjustment.created_at.desc())
        .limit(limit)
    ).all()
    return {"adjustments": [_serialize_adjustment(db, row) for row in rows]}
