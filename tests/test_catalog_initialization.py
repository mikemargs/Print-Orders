import os
import sys
import unittest
from pathlib import Path

from sqlalchemy import create_engine, event, func, select
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "server"))
os.environ.setdefault("JWT_SECRET", "catalog-test-secret-longer-than-thirty-two")

from app.auth_context import AuthContext
from app.database import Base, CatalogImportBatch, CatalogPriceTier, CatalogProduct, Company
from app.services.catalog import ensure_initial_catalog
from app.services.common import Invalid
from app.services.records import validate_order_catalog_items


class CatalogInitializationTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite://")

        @event.listens_for(self.engine, "connect")
        def enforce_foreign_keys(connection, _):
            connection.execute("PRAGMA foreign_keys=ON")

        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine, autoflush=False)
        with self.Session() as db:
            db.add(Company(id="co", name="Company", code="CAT", password_hash="x"))
            db.commit()

    def tearDown(self):
        self.engine.dispose()

    def test_first_import_with_production_flush_settings_and_foreign_keys(self):
        with self.Session() as db:
            self.assertTrue(ensure_initial_catalog(db, "co"))
            db.commit()
            self.assertEqual(db.scalar(select(func.count()).select_from(CatalogProduct)), 1148)
            self.assertEqual(db.scalar(select(func.count()).select_from(CatalogPriceTier)), 1173)
            self.assertFalse(ensure_initial_catalog(db, "co"))
            db.commit()
            self.assertEqual(db.scalar(select(func.count()).select_from(CatalogImportBatch)), 1)

    def test_manual_price_requires_explicit_entry_even_for_zero(self):
        with self.Session() as db:
            db.add(CatalogProduct(id="manual", company_id="co", name="Custom job", manual_price=True, created_by="e", updated_by="e"))
            db.commit()
            auth = AuthContext("co", "e", "employee", "l", 1)
            item = {"catalog_product_id": "manual", "unit_price": 0, "price_overridden": False}
            with self.assertRaisesRegex(Invalid, "Enter a price"):
                validate_order_catalog_items(db, auth, [item])
            # Existing saved prices remain editable without retroactive repricing.
            validate_order_catalog_items(db, auth, [item], [dict(item)])
            validate_order_catalog_items(db, auth, [dict(item)], [{"item_name": "Custom", "unit_price": 5}, dict(item)])
            with self.assertRaisesRegex(Invalid, "Enter a price"):
                validate_order_catalog_items(db, auth, [dict(item), dict(item)], [dict(item)])
            item["price_overridden"] = True
            validate_order_catalog_items(db, auth, [item])


if __name__ == "__main__":
    unittest.main()
