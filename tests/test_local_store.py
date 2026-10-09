import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "client"))

from local_store import LocalStore


class LocalStoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.store = LocalStore(Path(self.temp.name) / "client.db")
        self.location_id = "loc-sayville"
        self.store.cache_bootstrap(
            {
                "locations": [
                    {
                        "id": self.location_id,
                        "name": "Sayville",
                        "store_number": "5127",
                        "active": True,
                    }
                ],
                "employees": [
                    {
                        "id": "emp-1",
                        "name": "Nick",
                        "role": "admin",
                        "location_ids": [self.location_id],
                        "active": True,
                    }
                ],
            }
        )

    def tearDown(self):
        self.temp.cleanup()

    def test_offline_save_calculations_and_outbox(self):
        customer_id = self.store.save_customer({"company": "Test Customer"})
        order_id = self.store.save_order(
            {
                "customer_id": customer_id,
                "location_id": self.location_id,
                "status": "New",
                "priority": "Rush",
                "received_date": "2026-09-16",
                "due_date": "2026-09-18",
                "tax_rate": 8.625,
                "discount": 10,
                "deposit": 25,
                "description": "Banner",
            },
            [{"item_name": "Banner", "quantity": 2, "unit_price": 50}],
        )
        self.assertEqual(self.store.pending_count(), 2)
        order = self.store.get_order(order_id)
        self.assertEqual(order["subtotal"], 100)
        self.assertAlmostEqual(order["total"], 97.76)
        self.assertAlmostEqual(order["balance"], 72.76)
        self.assertTrue(order["order_number"].startswith("WO-5127-"))

    def test_paid_order_keeps_deposit_and_payment_when_edited_by_desktop(self):
        customer_id = self.store.save_customer({"company": "Paid customer"})
        values = {"customer_id": customer_id, "location_id": self.location_id, "tax_rate": 0, "deposit": 25, "paid_in_full": True}
        items = [{"item_name": "Poster", "quantity": 1, "unit_price": 100}]
        order_id = self.store.save_order(values, items)
        self.assertEqual(self.store.get_order(order_id)["balance"], 0)
        self.assertEqual(self.store.get_order(order_id)["deposit"], 25)
        del values["paid_in_full"]
        self.store.save_order(values, items, order_id)
        self.assertTrue(self.store.get_order(order_id)["paid_in_full"])
        self.assertEqual(self.store.get_order(order_id)["balance"], 0)
        self.store.save_order(values | {"paid_in_full": False}, items, order_id)
        self.assertFalse(self.store.get_order(order_id)["paid_in_full"])
        self.assertEqual(self.store.get_order(order_id)["balance"], 75)

    def test_offline_save_supports_percent_discount(self):
        customer_id = self.store.save_customer({"company": "Percent Customer"})
        order_id = self.store.save_order(
            {
                "customer_id": customer_id,
                "location_id": self.location_id,
                "status": "New",
                "priority": "Normal",
                "received_date": "2026-10-05",
                "tax_rate": 8.625,
                "discount_mode": "percent",
                "discount_percent": 10,
                "discount": 0,
                "deposit": 0,
                "description": "Percent order",
            },
            [{"item_name": "Poster", "quantity": 1, "unit_price": 100}],
        )
        order = self.store.get_order(order_id)
        self.assertEqual(order["discount_mode"], "percent")
        self.assertEqual(order["discount_percent"], 10)
        self.assertEqual(order["discount"], 10)
        self.assertAlmostEqual(order["total"], 97.76)

    def test_pin_cache(self):
        self.store.cache_employee_pin("emp-1", "246810")
        self.assertTrue(self.store.verify_cached_pin("emp-1", "246810"))
        self.assertFalse(self.store.verify_cached_pin("emp-1", "111111"))

    def test_cached_pin_invalidates_when_auth_version_changes(self):
        self.store.cache_bootstrap({"employees": [{"id": "emp-1", "name": "Nick", "role": "admin", "location_ids": [self.location_id], "active": True, "auth_version": 1}]})
        self.store.cache_employee_pin("emp-1", "246810", 1)
        self.assertTrue(self.store.verify_cached_pin("emp-1", "246810"))
        self.store.cache_bootstrap({"employees": [{"id": "emp-1", "name": "Nick", "role": "admin", "location_ids": [self.location_id], "active": True, "auth_version": 2}]})
        self.assertFalse(self.store.verify_cached_pin("emp-1", "246810"))

    def test_cached_pin_rejects_inactive_employee(self):
        self.store.cache_employee_pin("emp-1", "246810", 1)
        self.store.cache_bootstrap({"employees": [{"id": "emp-1", "name": "Nick", "role": "admin", "location_ids": [self.location_id], "active": False, "auth_version": 2}]})
        self.assertFalse(self.store.verify_cached_pin("emp-1", "246810"))

    def test_later_remote_event_replaces_conflict_server_payload(self):
        customer_id = self.store.save_customer({"company": "Local"})
        first = {"id": customer_id, "version": 2, "updated_at": "2026-10-03T10:00:00+00:00", "updated_by": "a", "is_deleted": False, "company": "Server One", "first_name": "", "last_name": "", "phone": "", "email": "", "address1": "", "address2": "", "city": "", "state": "", "postal_code": "", "tax_exempt": False, "notes": ""}
        second = dict(first, version=3, company="Server Two")
        self.store.apply_events([{"entity_type": "customer", "entity_id": customer_id, "payload": first}], 1)
        self.store.apply_events([{"entity_type": "customer", "entity_id": customer_id, "payload": second}], 2)
        conflict = self.store.conflicts()[0]
        import json
        self.assertEqual(json.loads(conflict["server_payload"])["company"], "Server Two")

    def test_forbidden_result_is_rejection_not_resolvable_conflict(self):
        customer_id = self.store.save_customer({"company": "Local"})
        operation = self.store.pending_operations()[0]
        self.store.apply_push_results([{"operation_id": operation["operation_id"], "entity_type": "customer", "entity_id": customer_id, "status": "forbidden", "server": None, "message": "Denied"}])
        issue = self.store.conflicts()[0]
        self.assertEqual(issue["category"], "forbidden")
        with self.assertRaises(ValueError):
            self.store.resolve_conflict(issue["id"], "local")

    def test_apply_snapshot_initializes_empty_cache(self):
        snapshot = {
            "customers": [{"id": "c1", "version": 1, "updated_at": "2026-10-03T10:00:00+00:00", "updated_by": "emp", "is_deleted": False, "company": "Snapshot Co", "first_name": "", "last_name": "", "phone": "", "email": "", "address1": "", "address2": "", "city": "", "state": "", "postal_code": "", "tax_exempt": False, "notes": ""}],
            "orders": [], "cursor": 42
        }
        self.store.apply_snapshot(snapshot)
        self.assertEqual(self.store.get_customer("c1")["company"], "Snapshot Co")
        self.assertEqual(self.store.get_meta("sync_cursor"), "42")

    def test_conflict_resolution_keep_server(self):
        customer_id = self.store.save_customer({"company": "Local Name"})
        operation = self.store.pending_operations()[0]
        server = {
            "id": customer_id,
            "version": 2,
            "updated_at": "2026-09-16T12:00:00+00:00",
            "updated_by": "other",
            "is_deleted": False,
            "company": "Server Name",
            "first_name": "",
            "last_name": "",
            "phone": "",
            "email": "",
            "address1": "",
            "address2": "",
            "city": "",
            "state": "",
            "postal_code": "",
            "tax_exempt": False,
            "notes": "",
        }
        self.store.apply_push_results(
            [
                {
                    "operation_id": operation["operation_id"],
                    "entity_type": "customer",
                    "entity_id": customer_id,
                    "status": "conflict",
                    "server": server,
                    "message": "Version conflict",
                }
            ]
        )
        self.assertEqual(self.store.conflict_count(), 1)
        conflict = self.store.conflicts()[0]
        self.store.resolve_conflict(conflict["id"], "server")
        self.assertEqual(self.store.get_customer(customer_id)["company"], "Server Name")
        self.assertEqual(self.store.conflict_count(), 0)


if __name__ == "__main__":
    unittest.main()
