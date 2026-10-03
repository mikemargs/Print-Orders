"""Production-engine smoke check used by GitHub Actions after Alembic upgrade."""
from __future__ import annotations

import sys
import uuid
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "server"))

from app.auth_context import AuthContext
from app.database import Company, Location, SessionLocal, SyncEvent, engine
from app.services.records import create_or_update_customer, create_or_update_order
from sqlalchemy import func, select


def main() -> None:
    if engine.dialect.name != "postgresql":
        raise SystemExit(
            f"PostgreSQL smoke test requires PostgreSQL; got {engine.dialect.name!r}"
        )

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
            create_or_update_customer(
                db, auth, customer_id, 0, {"company": "PostgreSQL Customer"}
            )
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
                    "tax_rate": "8.625",
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

            events = db.scalar(
                select(func.count()).select_from(SyncEvent).where(
                    SyncEvent.company_id == company_id
                )
            )
            if events != 3:
                raise AssertionError(f"Expected 3 sync events, got {events}")
        finally:
            db.rollback()

    print("PostgreSQL application smoke test passed")


if __name__ == "__main__":
    main()
