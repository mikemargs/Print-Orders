import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "server"))
os.environ.setdefault("JWT_SECRET", "settings-test-secret-longer-than-thirty-two")

import test_assets_routes
from app.database import Company, Customer


class SettingsTests(unittest.TestCase):
    setUp = test_assets_routes.AssetRouteTests.setUp
    tearDown = test_assets_routes.AssetRouteTests.tearDown
    login = test_assets_routes.AssetRouteTests.login

    def settings_body(self, **changes):
        return {"version": 1, "default_tax_rate": 8.625, "default_order_priority": "High", "default_delivery_method": "Ship"} | changes

    def test_only_admin_can_read_and_change_settings(self):
        for role, employee in (("employee", "e"), ("supervisor", "s")):
            self.login(employee, role, "l1")
            self.assertEqual(self.client.get("/api/settings").status_code, 403)
            self.assertEqual(self.client.patch("/api/settings", json=self.settings_body(), headers=self.headers).status_code, 403)
            self.assertEqual(self.client.get("/api/order-defaults").status_code, 200)
        self.login("a", "admin", "l1")
        self.assertEqual(self.client.get("/api/settings").json()["default_tax_rate"], 0)
        self.assertEqual(self.client.patch("/api/settings", json=self.settings_body()).status_code, 403)

    def test_validation_and_stale_save(self):
        self.login("a", "admin", "l1")
        for value in (-1, 101, "NaN", "Infinity", 8.12345):
            response = self.client.patch("/api/settings", json=self.settings_body(default_tax_rate=value), headers=self.headers)
            self.assertEqual(response.status_code, 422, response.text)
        for field in ("default_order_priority", "default_delivery_method"):
            self.assertEqual(self.client.patch("/api/settings", json=self.settings_body(**{field: "invalid"}), headers=self.headers).status_code, 422)
        saved = self.client.patch("/api/settings", json=self.settings_body(), headers=self.headers)
        self.assertEqual(saved.status_code, 200, saved.text)
        self.assertEqual(saved.json()["version"], 2)
        stale = self.client.patch("/api/settings", json=self.settings_body(default_tax_rate=0), headers=self.headers)
        self.assertEqual(stale.status_code, 409)
        self.assertEqual(self.client.get("/api/order-defaults").json()["default_tax_rate"], 8.625)

    def test_defaults_new_orders_overrides_and_preserved_history(self):
        with self.Session() as db:
            db.add(Company(id="other", name="Other", code="OTHER", password_hash="x"))
            db.add(Customer(id="c1", company_id="co", company="Customer", updated_by="a"))
            db.commit()
        self.login("a", "admin", "l1")
        saved = self.client.patch("/api/settings", json=self.settings_body(), headers=self.headers)
        self.assertEqual(saved.status_code, 200, saved.text)
        body = {"customer_id": "c1", "location_id": "l1", "received_date": "2026-10-09", "items": [{"item_name": "Poster", "quantity": 1, "unit_price": 100}]}
        self.login("e", "employee", "l1")
        created = self.client.post("/api/orders", json=body, headers=self.headers)
        self.assertEqual(created.status_code, 201, created.text)
        order = created.json()
        self.assertEqual(order["tax_rate"], 8.625)
        self.assertEqual(order["priority"], "High")
        self.assertEqual(order["delivery_method"], "Ship")
        self.assertEqual(order["total"], 108.63)
        overridden = self.client.post("/api/orders", json=body | {"tax_rate": 0, "priority": "Normal", "delivery_method": "Pickup"}, headers=self.headers)
        self.assertEqual(overridden.status_code, 201, overridden.text)
        self.assertEqual(overridden.json()["total"], 100)
        self.login("a", "admin", "l1")
        self.client.patch("/api/settings", json=self.settings_body(version=2, default_tax_rate=9), headers=self.headers)
        updated = self.client.patch(f"/api/orders/{order['id']}", json={"version": order["version"], "description": "Changed notes"}, headers=self.headers)
        self.assertEqual(updated.status_code, 200, updated.text)
        self.assertEqual(updated.json()["tax_rate"], 8.625)
        with self.Session() as db:
            self.assertEqual(db.get(Company, "other").default_tax_rate, 0)
