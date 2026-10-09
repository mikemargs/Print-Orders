"""Production-engine smoke check used by GitHub Actions after Alembic upgrade."""

from __future__ import annotations

import sys
import uuid
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "server"))

from app.auth_context import AuthContext
from app.database import (
    Company,
    Employee,
    InventoryAdjustment,
    InventoryItem,
    Location,
    SessionLocal,
    SyncEvent,
    engine,
)
from app.routers.inventory import create_inventory_item
from app.schemas.assets import InventoryItemCreate
from app.services.records import create_or_update_customer, create_or_update_order
from sqlalchemy import func, select


def inventory_smoke() -> None:
    # Let the real route commit inside a savepoint while the outer transaction
    # rolls back all smoke-test data, including when an assertion fails.
    with engine.connect() as connection:
        transaction = connection.begin()
        try:
            with SessionLocal(bind=connection, join_transaction_mode="create_savepoint") as db:
                company_id, location_id, employee_id = (str(uuid.uuid4()) for _ in range(3))
                db.add(
                    Company(
                        id=company_id,
                        name="Inventory CI",
                        code=f"CI-{uuid.uuid4().hex}",
                        password_hash="x",
                    )
                )
                db.flush()
                db.add(
                    Location(
                        id=location_id, company_id=company_id, name="CI Store", store_number="CI"
                    )
                )
                db.add(
                    Employee(
                        id=employee_id,
                        company_id=company_id,
                        name="CI Admin",
                        pin_hash="x",
                        role="admin",
                        location_ids=[],
                    )
                )
                db.flush()
                auth = AuthContext(company_id, employee_id, "admin", location_id, 1)
                for quantity in (Decimal("10.5"), Decimal(0)):
                    item = create_inventory_item(
                        InventoryItemCreate(
                            location_id=location_id, name="CI paper", quantity=quantity
                        ),
                        auth=auth,
                        db=db,
                    )
                    saved = db.get(InventoryItem, item["id"])
                    assert saved.quantity == quantity
                    adjustments = db.scalars(
                        select(InventoryAdjustment).where(InventoryAdjustment.item_id == item["id"])
                    ).all()
                    assert len(adjustments) == (1 if quantity > 0 else 0)
                    if adjustments:
                        assert adjustments[0].change_amount == quantity
                        assert adjustments[0].resulting_quantity == quantity
                        assert adjustments[0].adjusted_by == employee_id
        finally:
            transaction.rollback()


def main() -> None:
    if engine.dialect.name != "postgresql":
        raise SystemExit(f"PostgreSQL smoke test requires PostgreSQL; got {engine.dialect.name!r}")

    company_id = str(uuid.uuid4())
    location_id = str(uuid.uuid4())
    employee_id = str(uuid.uuid4())
    customer_id = str(uuid.uuid4())
    order_id = str(uuid.uuid4())
    code = f"CI-{uuid.uuid4().hex[:12].upper()}"

    with SessionLocal() as db:
        try:
            db.add(
                Company(
                    id=company_id,
                    name="CI PostgreSQL Smoke",
                    code=code,
                    password_hash="not-used-in-smoke-test",
                    active=True,
                    default_tax_rate=Decimal("8.625"),
                )
            )
            db.add(
                Location(
                    id=location_id,
                    company_id=company_id,
                    name="CI Store",
                    store_number="CI01",
                    active=True,
                )
            )
            db.flush()

            auth = AuthContext(company_id, employee_id, "admin", location_id, 1)
            create_or_update_customer(db, auth, customer_id, 0, {"company": "PostgreSQL Customer"})
            order = create_or_update_order(
                db,
                auth,
                order_id,
                0,
                {
                    "customer_id": customer_id,
                    "location_id": location_id,
                    "status": "New",
                    "priority": "Normal",
                    "received_date": "2026-10-03",
                    "items": [{"item_name": "Poster", "quantity": 1, "unit_price": "100"}],
                },
            )
            if Decimal(order.total) != Decimal("108.63"):
                raise AssertionError(f"Unexpected PostgreSQL total: {order.total!r}")

            updated = create_or_update_order(
                db,
                auth,
                order_id,
                1,
                {"description": "FOR UPDATE path exercised"},
            )
            if updated.version != 2:
                raise AssertionError(f"Expected version 2, got {updated.version}")

            # SessionLocal intentionally disables autoflush, so persist the final
            # pending SyncEvent before asserting database-visible event count.
            db.flush()
            events = db.scalar(
                select(func.count())
                .select_from(SyncEvent)
                .where(SyncEvent.company_id == company_id)
            )
            if events != 3:
                raise AssertionError(f"Expected 3 sync events, got {events}")
        finally:
            db.rollback()

    inventory_smoke()
    print("PostgreSQL application and inventory smoke tests passed")


if __name__ == "__main__":
    main()
