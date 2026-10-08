"""Exercise first-use catalog import concurrently with production sessions."""
import sys
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "server"))

from app.database import (
    CatalogImportBatch,
    CatalogPriceTier,
    CatalogProduct,
    Company,
    SessionLocal,
    engine,
)
from app.services.catalog import ensure_initial_catalog
from sqlalchemy import delete, func, select


def main():
    if engine.dialect.name != "postgresql":
        raise SystemExit("Catalog smoke test requires PostgreSQL")
    company_id = str(uuid.uuid4())
    with SessionLocal() as db:
        db.add(Company(id=company_id, name="Catalog Smoke", code=company_id, password_hash="unused"))
        db.commit()
    barrier = Barrier(3)

    def seed():
        with SessionLocal() as db:
            db.execute(select(Company.id).where(Company.id == company_id))
            barrier.wait(timeout=15)
            imported = ensure_initial_catalog(db, company_id)
            db.commit()
            return imported

    try:
        with ThreadPoolExecutor(max_workers=3) as pool:
            results = list(pool.map(lambda _: seed(), range(3)))
        if results.count(True) != 1:
            raise AssertionError(f"Expected exactly one importer, got {results}")
        with SessionLocal() as db:
            for model, expected in [(CatalogProduct, 1148), (CatalogPriceTier, 1173), (CatalogImportBatch, 1)]:
                count = db.scalar(select(func.count()).select_from(model).where(model.company_id == company_id))
                if count != expected:
                    raise AssertionError(f"{model.__tablename__}: expected {expected}, got {count}")
            if ensure_initial_catalog(db, company_id):
                raise AssertionError("Repeat request imported the catalog again")
            db.commit()
    finally:
        with SessionLocal() as db:
            for model in [CatalogPriceTier, CatalogProduct, CatalogImportBatch]:
                db.execute(delete(model).where(model.company_id == company_id))
            db.execute(delete(Company).where(Company.id == company_id))
            db.commit()
    print("PostgreSQL concurrent catalog initialization passed")


if __name__ == "__main__":
    main()
