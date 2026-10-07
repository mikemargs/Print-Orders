from __future__ import annotations

import uuid
from collections import defaultdict
from decimal import Decimal

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from ..catalog_seed import (
    INITIAL_CATALOG_SOURCE_KEY,
    INITIAL_CATALOG_SOURCE_NAME,
    initial_catalog_rows,
)
from ..database import (
    CatalogImportBatch,
    CatalogPriceTier,
    CatalogProduct,
    utcnow,
)


def ensure_initial_catalog(db: Session, company_id: str) -> bool:
    imported = db.scalar(
        select(CatalogImportBatch).where(
            CatalogImportBatch.company_id == company_id,
            CatalogImportBatch.source_key == INITIAL_CATALOG_SOURCE_KEY,
        )
    )
    if imported:
        return False

    rows = initial_catalog_rows()
    grouped: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        grouped[row["source_item_code"]].append(row)

    actor = "catalog-import"
    product_count = 0
    price_row_count = 0

    for source_item_code, price_rows in grouped.items():
        first = price_rows[0]
        product_id = str(
            uuid.uuid5(
                uuid.NAMESPACE_URL,
                f"{company_id}:{INITIAL_CATALOG_SOURCE_KEY}:product:{source_item_code}",
            )
        )
        product = db.get(CatalogProduct, product_id)
        if not product:
            product = CatalogProduct(
                id=product_id,
                company_id=company_id,
                source_item_code=source_item_code,
                category=first["category"],
                name=first["name"],
                unit=first["unit"] or "ea",
                currency=first["currency"] or "USD",
                manual_price=first["manual_price"].lower() == "true",
                active=True,
                version=1,
                created_by=actor,
                updated_by=actor,
            )
            db.add(product)
        product_count += 1

        existing_tiers = {
            (
                Decimal(tier.min_qty),
                Decimal(tier.max_qty) if tier.max_qty is not None else None,
                Decimal(tier.price),
                Decimal(tier.price_unit),
                tier.is_default,
            )
            for tier in db.scalars(
                select(CatalogPriceTier).where(
                    CatalogPriceTier.company_id == company_id,
                    CatalogPriceTier.product_id == product_id,
                )
            ).all()
        }
        for sort_order, row in enumerate(price_rows):
            min_qty = Decimal(row["min_qty"])
            raw_max = Decimal(row["max_qty"])
            is_default = min_qty == 0 and raw_max == 0
            max_qty = None if raw_max == 0 else raw_max
            price = Decimal(row["price"])
            price_unit = Decimal(row["price_unit"])
            key = (min_qty, max_qty, price, price_unit, is_default)
            if key in existing_tiers:
                continue
            tier_id = str(
                uuid.uuid5(
                    uuid.NAMESPACE_URL,
                    (
                        f"{company_id}:{INITIAL_CATALOG_SOURCE_KEY}:tier:"
                        f"{source_item_code}:{min_qty}:{max_qty}:{price}:{price_unit}:{is_default}"
                    ),
                )
            )
            db.add(
                CatalogPriceTier(
                    id=tier_id,
                    company_id=company_id,
                    product_id=product_id,
                    min_qty=min_qty,
                    max_qty=max_qty,
                    price=price,
                    price_unit=price_unit,
                    is_default=is_default,
                    sort_order=sort_order,
                )
            )
            existing_tiers.add(key)
            price_row_count += 1

    db.add(
        CatalogImportBatch(
            id=str(
                uuid.uuid5(
                    uuid.NAMESPACE_URL,
                    f"{company_id}:{INITIAL_CATALOG_SOURCE_KEY}:batch",
                )
            ),
            company_id=company_id,
            source_key=INITIAL_CATALOG_SOURCE_KEY,
            source_name=INITIAL_CATALOG_SOURCE_NAME,
            product_count=product_count,
            price_row_count=price_row_count,
            imported_at=utcnow(),
        )
    )
    return True


def replace_product_tiers(
    db: Session,
    company_id: str,
    product_id: str,
    tiers: list[dict],
) -> None:
    db.execute(
        delete(CatalogPriceTier).where(
            CatalogPriceTier.company_id == company_id,
            CatalogPriceTier.product_id == product_id,
        )
    )
    for index, tier in enumerate(tiers):
        db.add(
            CatalogPriceTier(
                id=str(uuid.uuid4()),
                company_id=company_id,
                product_id=product_id,
                min_qty=tier["min_qty"],
                max_qty=tier["max_qty"],
                price=tier["price"],
                price_unit=tier["price_unit"],
                is_default=tier["is_default"],
                sort_order=tier.get("sort_order", index),
            )
        )


def resolve_catalog_price(
    product: CatalogProduct,
    tiers: list[CatalogPriceTier],
    quantity: Decimal,
) -> tuple[Decimal | None, CatalogPriceTier | None]:
    if product.manual_price:
        return None, None

    quantity = max(Decimal(quantity), Decimal(0))
    ranged = [
        tier
        for tier in tiers
        if not tier.is_default
        and quantity >= Decimal(tier.min_qty)
        and (tier.max_qty is None or quantity <= Decimal(tier.max_qty))
    ]
    chosen = None
    if ranged:
        chosen = sorted(
            ranged,
            key=lambda tier: (Decimal(tier.min_qty), tier.sort_order),
            reverse=True,
        )[0]
    else:
        defaults = [tier for tier in tiers if tier.is_default]
        if defaults:
            chosen = sorted(defaults, key=lambda tier: tier.sort_order)[0]
        elif tiers:
            chosen = sorted(
                tiers,
                key=lambda tier: (Decimal(tier.min_qty), tier.sort_order),
            )[0]

    if not chosen:
        return None, None

    price_unit = Decimal(chosen.price_unit or 1)
    if price_unit <= 0:
        price_unit = Decimal(1)
    return (Decimal(chosen.price) / price_unit), chosen
