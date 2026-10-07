import os
import sys
import unittest
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "server"))
os.environ.setdefault("JWT_SECRET", "catalog-route-test-secret-longer-than-thirty-two")

from app.auth_context import AuthContext
from app.catalog_seed import initial_catalog_rows
from app.database import Base, Company, Employee, Location
from app.main import app
from app.web_sessions import create_employee_session, get_web_db


class CatalogRouteTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine, expire_on_commit=False)
        with self.Session() as db:
            db.add(Company(id="co", name="Company", code="CAT", password_hash="x"))
            db.add(Location(id="l1", company_id="co", name="Sayville", store_number="5127"))
            db.add_all(
                [
                    Employee(
                        id="e",
                        company_id="co",
                        name="Employee",
                        pin_hash="x",
                        role="employee",
                        location_ids=["l1"],
                        auth_version=1,
                    ),
                    Employee(
                        id="s",
                        company_id="co",
                        name="Supervisor",
                        pin_hash="x",
                        role="supervisor",
                        location_ids=["l1"],
                        auth_version=1,
                    ),
                ]
            )
            db.commit()

        def db_dependency():
            with self.Session() as db:
                yield db

        app.dependency_overrides[get_web_db] = db_dependency
        self.client = TestClient(app, base_url="https://testserver")
        self.login("s", "supervisor")

    def tearDown(self):
        app.dependency_overrides.clear()
        self.client.close()
        self.engine.dispose()

    def login(self, employee_id, role):
        token, csrf = create_employee_session(
            AuthContext("co", employee_id, role, "l1", 1)
        )
        self.client.cookies.set("pom_session", token)
        self.headers = {"X-CSRF-Token": csrf}

    def test_initial_excel_import_pricing_and_management(self):
        raw_rows = initial_catalog_rows()
        self.assertEqual(len(raw_rows), 1173)
        self.assertEqual(len({row["source_item_code"] for row in raw_rows}), 1148)

        response = self.client.get("/api/catalog", params={"limit": 2000})
        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()
        self.assertEqual(payload["total"], 1148)
        self.assertEqual(len(payload["products"]), 1148)

        summary = self.client.get("/api/catalog/summary").json()
        self.assertEqual(summary["active_products"], 1148)
        self.assertEqual(summary["categories"], 19)
        self.assertEqual(summary["tiered_products"], 12)
        self.assertEqual(summary["manual_price"], 16)
        self.assertEqual(summary["initial_import"]["product_count"], 1148)
        self.assertEqual(summary["initial_import"]["price_row_count"], 1173)
        self.assertEqual(summary["initial_import"]["source_name"], "Store Prices 10.7.26.xlsx")

        copies = next(
            product
            for product in payload["products"]
            if product["source_item_code"] == "36001"
        )
        self.assertEqual(len(copies["tiers"]), 4)

        for quantity, expected in [(1, 0.30), (100, 0.25), (500, 0.15), (1000, 0.08)]:
            price = self.client.get(
                f"/api/catalog/{copies['id']}/price",
                params={"quantity": quantity},
            )
            self.assertEqual(price.status_code, 200, price.text)
            self.assertAlmostEqual(price.json()["unit_price"], expected)

        manual = next(
            product
            for product in payload["products"]
            if product["source_item_code"] == "39220"
        )
        self.assertTrue(manual["manual_price"])
        price = self.client.get(
            f"/api/catalog/{manual['id']}/price",
            params={"quantity": 1},
        ).json()
        self.assertIsNone(price["unit_price"])

        self.login("e", "employee")
        denied = self.client.post(
            "/api/catalog",
            json={
                "source_item_code": "NEW-1",
                "category": "Printing",
                "name": "New Item",
                "unit": "ea",
                "currency": "USD",
                "manual_price": False,
                "active": True,
                "tiers": [
                    {
                        "min_qty": 0,
                        "max_qty": None,
                        "price": 5,
                        "price_unit": 1,
                        "is_default": True,
                        "sort_order": 0,
                    }
                ],
            },
            headers=self.headers,
        )
        self.assertEqual(denied.status_code, 403)

        self.login("s", "supervisor")
        created = self.client.post(
            "/api/catalog",
            json={
                "source_item_code": "NEW-1",
                "category": "Printing",
                "name": "New Item",
                "unit": "ea",
                "currency": "USD",
                "manual_price": False,
                "active": True,
                "tiers": [
                    {
                        "min_qty": 0,
                        "max_qty": None,
                        "price": 5,
                        "price_unit": 1,
                        "is_default": True,
                        "sort_order": 0,
                    }
                ],
            },
            headers=self.headers,
        )
        self.assertEqual(created.status_code, 201, created.text)
        self.assertEqual(created.json()["resolved_price"], 5)


if __name__ == "__main__":
    unittest.main()
