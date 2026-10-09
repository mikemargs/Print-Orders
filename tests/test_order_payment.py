import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "server"))
os.environ.setdefault("JWT_SECRET", "payment-tests-secret-longer-than-thirty-two")

import test_assets_routes
from app.database import Customer, SyncEvent
from sqlalchemy import select


class OrderPaymentTests(unittest.TestCase):
    setUp = test_assets_routes.AssetRouteTests.setUp
    tearDown = test_assets_routes.AssetRouteTests.tearDown
    login = test_assets_routes.AssetRouteTests.login

    def create_order(self, **changes):
        with self.Session() as db:
            if not db.get(Customer, "c"):
                db.add(Customer(id="c", company_id="co", company="Payment customer", updated_by="s"))
                db.commit()
        body = {"customer_id": "c", "location_id": "l1", "received_date": "2026-10-09", "tax_rate": 8.625, "deposit": 30, "items": [{"item_name": "Poster", "quantity": 1, "unit_price": 100}]} | changes
        response = self.client.post("/api/orders", json=body, headers=self.headers)
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()

    def test_mark_paid_preserves_deposit_and_unmark_restores_balance(self):
        order = self.create_order()
        self.assertFalse(order["paid_in_full"])
        self.assertEqual(order["balance"], 78.63)
        url = f"/api/orders/{order['id']}"
        marked = self.client.patch(url, json={"version": 1, "paid_in_full": True}, headers=self.headers)
        self.assertEqual(marked.status_code, 200, marked.text)
        self.assertEqual(marked.json()["balance"], 0)
        self.assertEqual(marked.json()["deposit"], 30)
        self.assertEqual(marked.json()["total"], 108.63)
        self.assertEqual(marked.json()["status"], "New")
        with self.Session() as db:
            events = db.scalars(select(SyncEvent).where(SyncEvent.entity_id == order["id"]).order_by(SyncEvent.sequence)).all()
            self.assertTrue(events[-1].payload["paid_in_full"])
            self.assertEqual(events[-1].payload["balance"], 0)
        notes = self.client.patch(url, json={"version": 2, "description": "Payment confirmed"}, headers=self.headers)
        self.assertTrue(notes.json()["paid_in_full"])
        self.assertEqual(notes.json()["balance"], 0)
        unmarked = self.client.patch(url, json={"version": 3, "paid_in_full": False}, headers=self.headers)
        self.assertEqual(unmarked.status_code, 200, unmarked.text)
        self.assertFalse(unmarked.json()["paid_in_full"])
        self.assertEqual(unmarked.json()["balance"], 78.63)
        stale = self.client.patch(url, json={"version": 2, "paid_in_full": True}, headers=self.headers)
        self.assertEqual(stale.status_code, 409)
        self.assertFalse(self.client.get(url).json()["paid_in_full"])

    def test_paid_at_creation_and_strict_validation_and_store_scope(self):
        order = self.create_order(paid_in_full=True)
        self.assertTrue(order["paid_in_full"])
        self.assertEqual(order["balance"], 0)
        url = f"/api/orders/{order['id']}"
        for value in (None, "false", "true", 1):
            response = self.client.patch(url, json={"version": 1, "paid_in_full": value}, headers=self.headers)
            self.assertIn(response.status_code, (400, 422), response.text)
        self.login("s", "supervisor", "l2")
        response = self.client.patch(url, json={"version": 1, "paid_in_full": False}, headers=self.headers)
        self.assertEqual(response.status_code, 403)
