from __future__ import annotations

import uuid
from collections import defaultdict
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..database import (
    CatalogImportBatch,
    CatalogPriceTier,
    CatalogProduct,
    utcnow,
)
from ..schemas.catalog import CatalogProductCreate, CatalogProductUpdate
from ..services.catalog import (
    ensure_initial_catalog,
    replace_product_tiers,
    resolve_catalog_price,
)
from ..services.drilldowns import apply_view
from ..web_sessions import get_web_db, web_auth_context, web_mutation_context

router = APIRouter(prefix="/api/catalog", tags=["catalog"])


def _manager(auth):
    if auth.role not in {"supervisor", "admin"}:
        raise HTTPException(403, "Supervisor permission is required to manage the catalog")


def _ensure_seed(db: Session, company_id: str) -> None:
    if ensure_initial_catalog(db, company_id):
        db.commit()


def _tier_dict(tier: CatalogPriceTier) -> dict:
    return {
        "id": tier.id,
        "min_qty": float(tier.min_qty),
        "max_qty": float(tier.max_qty) if tier.max_qty is not None else None,
        "price": float(tier.price),
        "price_unit": float(tier.price_unit),
        "is_default": tier.is_default,
        "sort_order": tier.sort_order,
    }


def _serialize(
    row: CatalogProduct,
    tiers: list[CatalogPriceTier],
    quantity: Decimal = Decimal(1),
) -> dict:
    resolved, chosen = resolve_catalog_price(row, tiers, quantity)
    return {
        "id": row.id,
        "source_item_code": row.source_item_code,
        "category": row.category,
        "name": row.name,
        "unit": row.unit,
        "currency": row.currency,
        "manual_price": row.manual_price,
        "active": row.active,
        "version": row.version,
        "created_by": row.created_by,
        "updated_by": row.updated_by,
        "created_at": row.created_at.isoformat(),
        "updated_at": row.updated_at.isoformat(),
        "resolved_price": float(resolved) if resolved is not None else None,
        "resolved_tier_id": chosen.id if chosen else None,
        "tiers": [_tier_dict(tier) for tier in sorted(tiers, key=lambda x: x.sort_order)],
    }


def _tiers_by_product(db: Session, company_id: str, product_ids: list[str]):
    grouped: dict[str, list[CatalogPriceTier]] = defaultdict(list)
    if not product_ids:
        return grouped
    rows = db.scalars(
        select(CatalogPriceTier)
        .where(
            CatalogPriceTier.company_id == company_id,
            CatalogPriceTier.product_id.in_(product_ids),
        )
        .order_by(CatalogPriceTier.product_id, CatalogPriceTier.sort_order)
    ).all()
    for row in rows:
        grouped[row.product_id].append(row)
    return grouped


@router.get("")
def list_catalog(
    view: str = "",
    search: str = "",
    category: str = "",
    include_inactive: bool = False,
    quantity: Decimal = Query(Decimal(1), ge=0),
    limit: int = Query(250, ge=1, le=2000),
    offset: int = Query(0, ge=0),
    auth=Depends(web_auth_context),
    db: Session = Depends(get_web_db),
):
    _ensure_seed(db, auth.company_id)
    q = select(CatalogProduct).where(CatalogProduct.company_id == auth.company_id)
    if not include_inactive and view != "tiered":
        q = q.where(CatalogProduct.active.is_(True))
    if category:
        q = q.where(CatalogProduct.category == category)
    if search.strip():
        needle = f"%{search.strip()}%"
        q = q.where(
            or_(
                CatalogProduct.name.ilike(needle),
                CatalogProduct.category.ilike(needle),
                CatalogProduct.source_item_code.ilike(needle),
            )
        )
    q = apply_view(db, auth, q, CatalogProduct, view)
    total = db.scalar(select(func.count()).select_from(q.subquery()))
    rows = db.scalars(
        q.order_by(
            CatalogProduct.category,
            CatalogProduct.name,
            CatalogProduct.source_item_code,
        )
        .offset(offset)
        .limit(limit)
    ).all()
    grouped = _tiers_by_product(db, auth.company_id, [row.id for row in rows])
    return {
        "products": [
            _serialize(row, grouped.get(row.id, []), quantity)
            for row in rows
        ],
        "total": total,
    }


@router.get("/summary")
def catalog_summary(auth=Depends(web_auth_context), db: Session = Depends(get_web_db)):
    _ensure_seed(db, auth.company_id)
    rows = db.scalars(
        select(CatalogProduct).where(CatalogProduct.company_id == auth.company_id)
    ).all()
    tier_counts = dict(
        db.execute(
            select(
                CatalogPriceTier.product_id,
                func.count(CatalogPriceTier.id),
            )
            .where(CatalogPriceTier.company_id == auth.company_id)
            .group_by(CatalogPriceTier.product_id)
        ).all()
    )
    batch = db.scalar(
        select(CatalogImportBatch)
        .where(CatalogImportBatch.company_id == auth.company_id)
        .order_by(CatalogImportBatch.imported_at.desc())
    )
    return {
        "products": len(rows),
        "active_products": sum(1 for row in rows if row.active),
        "categories": len({row.category for row in rows if row.active}),
        "manual_price": sum(1 for row in rows if row.active and row.manual_price),
        "tiered_products": sum(1 for row in rows if tier_counts.get(row.id, 0) > 1),
        "initial_import": (
            {
                "source_name": batch.source_name,
                "product_count": batch.product_count,
                "price_row_count": batch.price_row_count,
                "imported_at": batch.imported_at.isoformat(),
            }
            if batch
            else None
        ),
    }


@router.get("/categories")
def catalog_categories(auth=Depends(web_auth_context), db: Session = Depends(get_web_db)):
    _ensure_seed(db, auth.company_id)
    values = db.execute(
        select(CatalogProduct.category, func.count(CatalogProduct.id))
        .where(
            CatalogProduct.company_id == auth.company_id,
            CatalogProduct.active.is_(True),
        )
        .group_by(CatalogProduct.category)
        .order_by(CatalogProduct.category)
    ).all()
    return {"categories": [category for category, _ in values],
            "counts": [{"category": category, "count": count} for category, count in values]}


@router.get("/{product_id}/price")
def product_price(
    product_id: str,
    quantity: Decimal = Query(Decimal(1), ge=0),
    auth=Depends(web_auth_context),
    db: Session = Depends(get_web_db),
):
    _ensure_seed(db, auth.company_id)
    product = db.scalar(
        select(CatalogProduct).where(
            CatalogProduct.id == product_id,
            CatalogProduct.company_id == auth.company_id,
            CatalogProduct.active.is_(True),
        )
    )
    if not product:
        raise HTTPException(404, "Catalog product not found")
    tiers = db.scalars(
        select(CatalogPriceTier)
        .where(
            CatalogPriceTier.company_id == auth.company_id,
            CatalogPriceTier.product_id == product.id,
        )
        .order_by(CatalogPriceTier.sort_order)
    ).all()
    resolved, chosen = resolve_catalog_price(product, tiers, quantity)
    return {
        "product_id": product.id,
        "quantity": float(quantity),
        "manual_price": product.manual_price,
        "unit_price": float(resolved) if resolved is not None else None,
        "tier": _tier_dict(chosen) if chosen else None,
    }


@router.post("", status_code=201)
def create_product(
    body: CatalogProductCreate,
    auth=Depends(web_mutation_context),
    db: Session = Depends(get_web_db),
):
    _manager(auth)
    _ensure_seed(db, auth.company_id)
    row = CatalogProduct(
        id=str(uuid.uuid4()),
        company_id=auth.company_id,
        source_item_code=body.source_item_code or None,
        category=body.category,
        name=body.name,
        unit=body.unit,
        currency=body.currency.upper(),
        manual_price=body.manual_price,
        active=body.active,
        version=1,
        created_by=auth.employee_id,
        updated_by=auth.employee_id,
    )
    db.add(row)
    db.flush()
    replace_product_tiers(
        db,
        auth.company_id,
        row.id,
        [tier.model_dump() for tier in body.tiers],
    )
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, "That catalog item code is already in use") from exc
    tiers = db.scalars(
        select(CatalogPriceTier)
        .where(CatalogPriceTier.product_id == row.id)
        .order_by(CatalogPriceTier.sort_order)
    ).all()
    return _serialize(row, tiers)


@router.patch("/{product_id}")
def update_product(
    product_id: str,
    body: CatalogProductUpdate,
    auth=Depends(web_mutation_context),
    db: Session = Depends(get_web_db),
):
    _manager(auth)
    _ensure_seed(db, auth.company_id)
    row = db.scalar(
        select(CatalogProduct).where(
            CatalogProduct.id == product_id,
            CatalogProduct.company_id == auth.company_id,
        )
    )
    if not row:
        raise HTTPException(404, "Catalog product not found")
    if row.version != body.version:
        raise HTTPException(409, "This catalog product changed on another device")
    result = db.execute(
        update(CatalogProduct)
        .where(
            CatalogProduct.id == product_id,
            CatalogProduct.company_id == auth.company_id,
            CatalogProduct.version == body.version,
        )
        .values(
            source_item_code=body.source_item_code or None,
            category=body.category,
            name=body.name,
            unit=body.unit,
            currency=body.currency.upper(),
            manual_price=body.manual_price,
            active=body.active,
            version=body.version + 1,
            updated_by=auth.employee_id,
            updated_at=utcnow(),
        )
        .execution_options(synchronize_session=False)
    )
    if result.rowcount != 1:
        db.rollback()
        raise HTTPException(409, "This catalog product changed on another device")
    replace_product_tiers(
        db,
        auth.company_id,
        product_id,
        [tier.model_dump() for tier in body.tiers],
    )
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, "That catalog item code is already in use") from exc
    db.refresh(row)
    tiers = db.scalars(
        select(CatalogPriceTier)
        .where(CatalogPriceTier.product_id == row.id)
        .order_by(CatalogPriceTier.sort_order)
    ).all()
    return _serialize(row, tiers)
